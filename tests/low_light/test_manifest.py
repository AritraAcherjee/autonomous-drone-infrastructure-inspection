"""Task C contract tests. All images, labels, and source metadata are synthetic."""

from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path, PureWindowsPath
import shutil

import cv2
import numpy as np
import pytest
import yaml

from src.low_light import canonical_config, derive_seed
from src.low_light import manifest as m
from src.low_light import validation_variants as v


REAL_REPO = Path(__file__).resolve().parents[2]
LABEL_BYTES = b"1  0.500000 0.50  0.25 0.125\r\n3\t0.2 0.30 0.1 0.10\n\n"


@pytest.fixture(autouse=True)
def synthetic_only_io(monkeypatch):
    """Tripwire: Task C tests cannot open any actual repository dataset file."""
    original = Path.open

    def guarded(path, *args, **kwargs):
        resolved = path.resolve()
        if resolved.is_relative_to(REAL_REPO / "data"):
            pytest.fail(f"unit test attempted real dataset access: {path}")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


def write_source_metadata(root: Path, rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=v.SOURCE_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    data = stream.getvalue().encode("utf-8")
    path = root / m.VALID_MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    (root / m.SOURCE_VERSION).write_bytes(m.deterministic_json_bytes({
        "dataset": "GYU-DET", "source_version": "v3", "processed_specification_version": "baseline-v1",
        "manifest_sha256": {"valid": m.sha256_bytes(data)},
    }))
    return data


def synthetic_repository(root: Path, names=("z.jpg", "a.png")) -> list[dict]:
    """Build a portable approved-metadata facsimile, entirely below tmp_path."""
    rows = []
    for name in names:
        image_relative = (m.VALID_SOURCE_ROOT / "images" / name).as_posix()
        label_relative = (m.VALID_SOURCE_ROOT / "labels" / (Path(name).stem + ".txt")).as_posix()
        yy, xx = np.indices((23, 31), dtype=np.uint16)
        pixels = np.stack(((xx * 7 + yy * 3) % 256, (xx * 2 + yy * 11) % 256,
                           (xx * 13 + yy * 5) % 256), axis=-1).astype(np.uint8)
        ok, encoded = cv2.imencode(Path(name).suffix, pixels)
        assert ok
        image = root / image_relative
        label = root / label_relative
        image.parent.mkdir(parents=True, exist_ok=True)
        label.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(encoded.tobytes())
        label.write_bytes(LABEL_BYTES)
        rows.append(dict(zip(v.SOURCE_FIELDS, (
            "valid", "valid", image_relative, label_relative, m.sha256_file(image), "2", "[1, 3]",
            "", "", "EXACT_PAIR_SOURCE_SPLIT_PRESERVED", "",
        ))))
    write_source_metadata(root, rows)
    config = root / "configs/low_light/benchmark_v1.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(yaml.safe_dump(canonical_config()), encoding="utf-8")
    return rows


@pytest.fixture
def generated(tmp_path):
    synthetic_repository(tmp_path)
    summary = v.generate_validation_variants(tmp_path)
    data = (tmp_path / m.BENCHMARK_ROOT / "manifests/validation_manifest.json").read_bytes()
    return tmp_path, m.read_manifest_json(data), summary


def test_required_fields_and_resolved_task_b_parameters(generated):
    _, records, _ = generated
    for record in records:
        assert set(record) == set(m.CSV_FIELDS)
        assert record["protocol_version"] == "aegis-low-light-benchmark-v1"
        assert record["global_seed"] == 42
        assert record["source_split"] == "valid"
        assert record["generation_status"] == "generated"
        assert record["label_identity"] == "sha256:" + record["source_label_sha256"]
        severity = record["severity"]
        assert record["resolved_transform_parameters"] == canonical_config()["severities"][severity]["parameters"]
        expected = None if severity == "L0" else derive_seed("valid", record["source_relative_path"], severity)
        assert record["derived_seed"] == expected


def test_manifest_order_and_deterministic_json(generated):
    _, records, _ = generated
    assert [(r["source_relative_path"], r["severity"]) for r in records] == sorted(
        (r["source_relative_path"], r["severity"]) for r in records)
    assert [r["severity"] for r in records[:5]] == ["L0", "L1", "L2", "L3", "L4"]
    assert m.manifest_json_bytes(records) == m.manifest_json_bytes(reversed(records))
    reordered_keys = [dict(reversed(list(r.items()))) for r in records]
    assert m.manifest_json_bytes(records) == m.manifest_json_bytes(reordered_keys)
    assert m.deterministic_json_bytes({"b": 2, "a": 1}) == b'{\n  "a": 1,\n  "b": 2\n}\n'


def test_csv_field_order_is_explicit_stable_and_roundtrippable(generated):
    _, records, _ = generated
    expected_fields = (
        "protocol_version", "global_seed", "source_relative_path", "source_split", "severity",
        "derived_seed", "resolved_transform_parameters", "output_relative_path", "source_sha256",
        "generated_image_sha256", "source_label_relative_path", "output_label_relative_path",
        "source_label_sha256", "generated_label_sha256", "source_width", "source_height",
        "generated_width", "generated_height", "label_identity", "generation_status", "generation_scope",
        "mean_luminance", "median_luminance", "near_black_percentage",
    )
    data = m.manifest_csv_bytes(records)
    assert m.CSV_FIELDS == expected_fields
    assert data.splitlines()[0].decode() == ",".join(expected_fields)
    assert data == m.manifest_csv_bytes(reversed(records))
    assert b"\r\n" not in data
    rows = list(csv.DictReader(io.StringIO(data.decode())))
    assert len(rows) == 10
    for row, record in zip(rows, records):
        assert json.loads(row["resolved_transform_parameters"]) == record["resolved_transform_parameters"]


@pytest.mark.parametrize("path", [r"data\raw\example.png", PureWindowsPath("data/raw/example.png"),
                                  Path("data/raw/example.png"), "data/raw/example.png"])
def test_posix_path_normalization(path):
    assert m.relative_posix(path) == "data/raw/example.png"


def test_manifest_paths_normalize_backslashes(generated):
    _, records, _ = generated
    windows = copy.deepcopy(records)
    for record in windows:
        for field in ("source_relative_path", "source_label_relative_path", "output_relative_path", "output_label_relative_path"):
            record[field] = record[field].replace("/", "\\")
    assert m.manifest_json_bytes(windows) == m.manifest_json_bytes(records)
    assert m.manifest_csv_bytes(windows) == m.manifest_csv_bytes(records)


@pytest.mark.parametrize("path", ["", "/absolute", "C:/raw", "//server/raw", "a/../raw", "a/./raw",
                                  "a//raw", "a/", "a/space ", "a/name.", "a|b", "a\x00b", b"a/b", None])
def test_ambiguous_paths_fail_closed(path):
    with pytest.raises(ValueError):
        m.relative_posix(path)


def test_l0_and_labels_are_byte_identical_and_all_hashes_match(generated):
    root, records, _ = generated
    for record in records:
        source = root / record["source_relative_path"]
        artifact = root / record["output_relative_path"]
        source_label = root / record["source_label_relative_path"]
        copied_label = root / record["output_label_relative_path"]
        assert m.sha256_file(source) == record["source_sha256"]
        assert m.sha256_file(artifact) == record["generated_image_sha256"]
        assert source_label.read_bytes() == copied_label.read_bytes() == LABEL_BYTES
        assert record["source_label_sha256"] == record["generated_label_sha256"] == m.sha256_file(copied_label)
        assert artifact.stem == copied_label.stem
        if record["severity"] == "L0":
            assert source.read_bytes() == artifact.read_bytes()
            assert record["source_sha256"] == record["generated_image_sha256"]
            assert source.suffix == artifact.suffix
        else:
            assert artifact.suffix == ".png"
        pixels = cv2.imdecode(np.frombuffer(artifact.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        assert pixels.dtype == np.uint8
        assert pixels.shape == (23, 31, 3)
        assert record["source_width"] == record["generated_width"] == 31
        assert record["source_height"] == record["generated_height"] == 23


def test_l0_never_calls_transform_or_encoder(tmp_path, monkeypatch):
    synthetic_repository(tmp_path, ("a.jpg",))
    transform, encode = v.apply_low_light, cv2.imencode
    severities, encodings = [], []

    def record_transform(image, severity, **kwargs):
        severities.append(severity)
        return transform(image, severity, **kwargs)

    def record_encode(extension, image, *args):
        encodings.append(extension)
        return encode(extension, image, *args)

    monkeypatch.setattr(v, "apply_low_light", record_transform)
    monkeypatch.setattr(cv2, "imencode", record_encode)
    v.generate_validation_variants(tmp_path)
    assert severities == ["L1", "L2", "L3", "L4"]
    assert encodings == [".png"] * 4


def test_no_source_mutation_and_repeat_generation_bytes(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    synthetic_repository(first)
    shutil.copytree(first, second)
    before = {p.relative_to(first): p.read_bytes() for p in first.rglob("*") if p.is_file()}
    summary1 = v.generate_validation_variants(first)
    summary2 = v.generate_validation_variants(second)
    assert summary1 == summary2
    for relative, data in before.items():
        assert (first / relative).read_bytes() == (second / relative).read_bytes() == data
    outputs = [p.relative_to(first) for p in (first / m.BENCHMARK_ROOT).rglob("*") if p.is_file()]
    assert len(outputs) == 23
    for relative in outputs:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()


@pytest.mark.parametrize("target", ["image", "label"])
def test_changed_source_detected_even_during_generation(tmp_path, monkeypatch, target):
    rows = synthetic_repository(tmp_path, ("a.png",))
    transform = v.apply_low_light
    path = tmp_path / rows[0]["image_relative_path" if target == "image" else "label_relative_path"]

    def tamper(image, severity, **kwargs):
        result = transform(image, severity, **kwargs)
        if severity == "L2":
            path.write_bytes(path.read_bytes() + b"synthetic concurrent mutation")
        return result

    monkeypatch.setattr(v, "apply_low_light", tamper)
    with pytest.raises(ValueError, match="immutability"):
        v.generate_validation_variants(tmp_path)
    assert not (tmp_path / m.BENCHMARK_ROOT / "manifests/benchmark_summary.json").exists()


@pytest.mark.parametrize("target", ["image", "label"])
def test_tampered_generated_file_detected(generated, target):
    root, records, _ = generated
    v.verify_generated_files(root, records)
    field = "output_relative_path" if target == "image" else "output_label_relative_path"
    (root / records[1][field]).write_bytes(b"wrong artifact")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        v.verify_generated_files(root, records)


def test_wrong_statistics_detected_from_actual_artifact(generated):
    root, records, _ = generated
    records[1]["mean_luminance"] += 1
    with pytest.raises(ValueError, match="statistics"):
        v.verify_generated_files(root, records)


def test_luminance_definition_and_frozen_near_black_boundary():
    levels = np.array([[0, 10, 11, 255]], dtype=np.uint8)
    image = np.repeat(levels[:, :, None], 3, axis=2)
    expected = {"mean_luminance": 69.0, "median_luminance": 10.5, "near_black_percentage": 50.0}
    assert m.luminance_statistics(image) == m.luminance_statistics(image.copy()) == expected
    color = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
    gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
    assert m.luminance_statistics(color)["mean_luminance"] == float(gray.mean())
    assert m.SANITY["near_black_operator"] == "<="
    assert m.SANITY["near_black_threshold"] == 10
    assert m.SANITY["version"] == "aegis-low-light-benchmark-sanity-v1"
    with pytest.raises(TypeError):
        m.SANITY["near_black_threshold"] = 11


def test_statistics_match_artifacts_and_summary(generated):
    root, records, summary = generated
    for record in records:
        image = cv2.imdecode(np.frombuffer((root / record["output_relative_path"]).read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        assert all(record[key] == value for key, value in m.luminance_statistics(image).items())
    for severity in ("L0", "L1", "L2", "L3", "L4"):
        means = [r["mean_luminance"] for r in records if r["severity"] == severity]
        assert summary["aggregate_luminance_by_severity"][severity]["mean_luminance"] == sum(means) / len(means)
    assert summary["luminance_progression_status"] == "not_assessed"


def test_summary_counts_hashes_and_no_wall_clock_identity(generated):
    root, _, summary = generated
    assert summary["source_image_count"] == 2
    assert summary["total_variant_count"] == 10
    assert summary["variant_count_by_severity"] == dict.fromkeys(("L0", "L1", "L2", "L3", "L4"), 2)
    assert summary["source_split"] == "valid"
    assert summary["global_seed"] == 42
    assert summary["generation_scope"] == "full_validation"
    assert summary["scientific_evaluation_evidence"] is False
    assert summary["generation_timestamp_policy"].startswith("omitted:")
    assert not {"timestamp", "created_at", "generated_at", "duration", "elapsed"}.intersection(summary)
    assert summary["benchmark_sanity"] == dict(m.SANITY)
    for name, digest in summary["manifest_hashes"].items():
        assert m.sha256_file(root / m.BENCHMARK_ROOT / "manifests" / name) == digest
    summary_path = root / m.BENCHMARK_ROOT / "manifests/benchmark_summary.json"
    assert summary_path.read_bytes() == m.deterministic_json_bytes(summary)


def test_frozen_output_namespace(generated):
    root, records, _ = generated
    expected = "outputs/experiments/low_light/benchmark_v1"
    assert m.BENCHMARK_ROOT.as_posix() == expected
    for record in records:
        name = {"L0": "normal", "L1": "mild", "L2": "moderate", "L3": "heavy", "L4": "extreme"}[record["severity"]]
        assert Path(record["output_relative_path"]).parent.as_posix() == f"{expected}/validation/{name}/images"
        assert Path(record["output_label_relative_path"]).parent.as_posix() == f"{expected}/validation/{name}/labels"
    assert sorted(p.name for p in (root / expected / "manifests").iterdir()) == [
        "benchmark_summary.json", "validation_manifest.csv", "validation_manifest.json"]


@pytest.mark.parametrize("limit,expected", [(1, 1), (2, 2), (100, 2)])
def test_bounded_selection_is_deterministic_and_labelled(tmp_path, limit, expected):
    synthetic_repository(tmp_path)
    sources, _ = v.load_validation_sources(tmp_path)
    chosen = v.select_development_sources(list(reversed(sources)), limit)
    assert chosen == v.select_development_sources(sources, limit)
    assert chosen[0].source_relative_path.endswith("a.png")
    summary = v.generate_validation_variants(tmp_path, limit=limit)
    assert summary["source_image_count"] == expected
    assert summary["total_variant_count"] == expected * 5
    assert summary["generation_scope"] == "development_sample"
    assert summary["selection"]["development_limit"] == limit
    assert summary["scientific_evaluation_evidence"] is False
    records = m.read_manifest_json((tmp_path / m.BENCHMARK_ROOT / "manifests/validation_manifest.json").read_bytes())
    assert all(r["generation_scope"] == "development_sample" for r in records)


def test_no_label_copy_retains_source_identity(tmp_path):
    synthetic_repository(tmp_path)
    v.generate_validation_variants(tmp_path, copy_labels=False)
    records = m.read_manifest_json((tmp_path / m.BENCHMARK_ROOT / "manifests/validation_manifest.json").read_bytes())
    assert all(r["output_label_relative_path"] is None and r["generated_label_sha256"] is None for r in records)
    assert all(r["source_label_sha256"] == m.sha256_bytes(LABEL_BYTES) for r in records)
    assert not list((tmp_path / m.BENCHMARK_ROOT / "validation").rglob("*.txt"))
    v.verify_generated_files(tmp_path, records)


@pytest.mark.parametrize("field,value", [
    ("protocol_version", "other"), ("global_seed", True), ("source_split", "test"),
    ("severity", "L5"), ("derived_seed", 12), ("resolved_transform_parameters", {}),
    ("source_sha256", "bad"), ("generated_image_sha256", "BAD"), ("generated_width", 22),
    ("source_height", True), ("generated_label_sha256", "0" * 64),
    ("label_identity", "unverified"), ("generation_status", "failed"),
    ("generation_scope", "evaluation"), ("mean_luminance", float("nan")),
    ("median_luminance", -1), ("near_black_percentage", 101),
    ("output_relative_path", "data/raw/bad.png"), ("output_label_relative_path", "wrong.txt"),
])
def test_malformed_record_fails_closed(generated, field, value):
    _, records, _ = generated
    records[1][field] = value
    with pytest.raises(ValueError):
        m.manifest_json_bytes(records)


def test_incomplete_duplicate_and_inconsistent_records_fail_closed(generated):
    _, records, _ = generated
    for bad in ([], records[:-1], records + [records[0]], [{k: val for k, val in records[0].items() if k != "severity"}]):
        with pytest.raises(ValueError):
            m.manifest_json_bytes(bad)
    records[1]["source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source identity"):
        m.manifest_json_bytes(records)


@pytest.mark.parametrize("change", ["config", "sanity", "extra", "missing", "order"])
def test_malformed_manifest_payload_fails_closed(generated, change):
    _, records, _ = generated
    payload = json.loads(m.manifest_json_bytes(records))
    if change == "config":
        payload["transform_config"]["global_seed"] = 7
    elif change == "sanity":
        payload["benchmark_sanity"]["near_black_threshold"] = 11
    elif change == "extra":
        payload["timestamp"] = "2026-01-01"
    elif change == "missing":
        del payload["protocol_version"]
    else:
        payload["records"].reverse()
    with pytest.raises(ValueError):
        m.read_manifest_json(json.dumps(payload))


@pytest.mark.parametrize("payload", [b"{", b"[]", b'{"records":null}', b'{"x":1,"x":2}',
                                     b'{"x":NaN}', b'{"x":Infinity}', b"\xff"])
def test_malformed_json_fails_closed(payload):
    with pytest.raises(ValueError):
        m.read_manifest_json(payload)
