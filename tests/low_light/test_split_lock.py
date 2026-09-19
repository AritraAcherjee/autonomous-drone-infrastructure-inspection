"""Fail-closed split/output gates using synthetic temporary repositories only."""

from __future__ import annotations

import ast
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from src.low_light import manifest as m
from src.low_light import validation_variants as v
from .test_manifest import synthetic_only_io, synthetic_repository, write_source_metadata


def forbid_raw_reads(monkeypatch):
    original = Path.open

    def guarded(path, *args, **kwargs):
        if "/data/raw/" in path.as_posix():
            pytest.fail(f"gate opened a source file before rejecting metadata: {path}")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)


def test_exact_valid_split_is_accepted(tmp_path):
    synthetic_repository(tmp_path)
    sources, digest = v.load_validation_sources(tmp_path, source_split="valid")
    assert len(sources) == 2
    assert all(s.source_split == "valid" for s in sources)
    assert digest == m.sha256_file(tmp_path / m.VALID_MANIFEST)


@pytest.mark.parametrize("split", ["train", "test", "unknown", "validation", "val", "VALID", "Valid",
                                   " valid", "valid ", "valid\n", "", None, 42, True, ["valid"]])
def test_split_rejected_before_any_source_access(tmp_path, monkeypatch, split):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid split must fail before file access")

    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(ValueError, match="exactly 'valid'"):
        v.generate_validation_variants(tmp_path, source_split=split)


@pytest.mark.parametrize("field", ["raw_split", "processed_split"])
@pytest.mark.parametrize("split", ["train", "test", "val", "unknown", "", "Valid", "valid "])
def test_every_source_row_must_be_valid_even_beyond_limit(tmp_path, monkeypatch, field, split):
    rows = synthetic_repository(tmp_path)
    rows[0][field] = split  # z.jpg falls outside a one-source lexical prefix.
    write_source_metadata(tmp_path, rows)
    forbid_raw_reads(monkeypatch)
    with pytest.raises(ValueError, match="exactly 'valid'"):
        v.generate_validation_variants(tmp_path, limit=1)
    assert not (tmp_path / m.BENCHMARK_ROOT).exists()


@pytest.mark.parametrize("split", ["train", "test"])
@pytest.mark.parametrize("field", ["image_relative_path", "label_relative_path"])
def test_relabelling_nonvalidation_path_does_not_bypass_gate(tmp_path, monkeypatch, split, field):
    rows = synthetic_repository(tmp_path)
    rows[0][field] = rows[0][field].replace("/valid/valid/", f"/{split}/{split}/")
    # Both metadata split fields still say valid: path identity must also agree.
    write_source_metadata(tmp_path, rows)
    forbid_raw_reads(monkeypatch)
    with pytest.raises(ValueError, match="canonical raw valid"):
        v.generate_validation_variants(tmp_path, output_root=tmp_path / m.BENCHMARK_ROOT)


@pytest.mark.parametrize("path", [
    "data/manifests/gyu_det_v3_baseline_v1/test.csv",
    "data/manifests/gyu_det_v3_baseline_v1/train.csv",
    "data/processed/gyu_det_v3_baseline_v1/splits/test.txt",
    "data/processed/gyu_det_v3_baseline_v1/splits/valid.txt",
    "custom/valid.csv", "data/manifests/gyu_det_v3_baseline_v1/../gyu_det_v3_baseline_v1/valid.csv",
])
def test_alternate_source_paths_rejected_without_opening(tmp_path, monkeypatch, path):
    def forbidden(*args, **kwargs):
        pytest.fail("alternate source path must fail before any metadata access")

    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(ValueError, match="canonical validation manifest"):
        v.load_validation_sources(tmp_path, source_manifest=path)


def test_no_random_resplit_api_exists(tmp_path):
    parameters = set(inspect.signature(v.generate_validation_variants).parameters)
    assert parameters == {"repo_root", "source_split", "output_root", "source_manifest", "config_path", "limit", "copy_labels"}
    for option in ("seed", "random_state", "shuffle", "test_size", "split_assignment", "records"):
        with pytest.raises(TypeError):
            v.generate_validation_variants(tmp_path, **{option: 42})
    tree = ast.parse(inspect.getsource(v))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imported.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert not {"random", "sklearn", "sklearn.model_selection", "ultralytics", "torch"}.intersection(imported)
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert not {"shuffle", "permutation", "choice", "train_test_split", "train", "predict", "val"}.intersection(calls)


@pytest.mark.parametrize("path", ["data/raw/variants", "outputs/../data/raw/variants",
                                  "data/raw/gyu_det/v3/extracted/valid/valid/images",
                                  "outputs/experiments/low_light/benchmark_v1/../../../../data/raw/variants"])
def test_raw_and_traversal_outputs_rejected(tmp_path, path):
    with pytest.raises(ValueError, match="protected raw"):
        v.generate_validation_variants(tmp_path, output_root=path)
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("path", ["outputs/elsewhere", "data/manifests/new", "../outside", "outputs/experiments/low_light/benchmark_v2"])
def test_noncanonical_output_root_rejected(tmp_path, path):
    with pytest.raises(ValueError, match="frozen namespace"):
        v.generate_validation_variants(tmp_path, output_root=path)


def make_directory_redirect(link: Path, target: Path):
    """Use a Windows junction if unprivileged directory symlinks are unavailable."""
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            raise
        quoted_link = str(link).replace("'", "''")
        quoted_target = str(target).replace("'", "''")
        subprocess.run([
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            f"New-Item -ItemType Junction -Path '{quoted_link}' -Target '{quoted_target}' -ErrorAction Stop | Out-Null",
        ], check=True, capture_output=True, text=True)
    assert link.resolve() == target.resolve()


@pytest.mark.parametrize("position", ["root", "nested", "parent"])
def test_output_symlink_or_junction_cannot_redirect_to_raw(tmp_path, position):
    rows = synthetic_repository(tmp_path)
    source = tmp_path / rows[0]["image_relative_path"]
    before = source.read_bytes()
    raw = tmp_path / "data/raw"
    if position == "root":
        redirect = tmp_path / m.BENCHMARK_ROOT
    elif position == "parent":
        redirect = tmp_path / "outputs"
    else:
        redirect = tmp_path / m.BENCHMARK_ROOT / "validation/normal/images"
    make_directory_redirect(redirect, raw)
    try:
        if position == "nested":
            image, _ = m.variant_paths(rows[0]["image_relative_path"], "L0")
            with pytest.raises(ValueError, match="protected raw"):
                v._write_new(tmp_path, image, b"must not write")
        else:
            with pytest.raises(ValueError, match="protected raw"):
                v.generate_validation_variants(tmp_path)
        assert source.read_bytes() == before
    finally:
        # Remove only the link itself, never recurse into the target raw fixture.
        if redirect.is_symlink():
            redirect.unlink()
        else:
            redirect.rmdir()


def test_source_directory_redirect_rejected_before_raw_read(tmp_path, monkeypatch):
    rows = synthetic_repository(tmp_path)
    directory = tmp_path / m.VALID_SOURCE_ROOT / "images"
    moved = tmp_path / "synthetic_redirect_target"
    directory.rename(moved)
    make_directory_redirect(directory, moved)
    try:
        forbid_raw_reads(monkeypatch)
        with pytest.raises(ValueError, match="redirected"):
            v.generate_validation_variants(tmp_path)
    finally:
        if directory.is_symlink():
            directory.unlink()
        else:
            directory.rmdir()


def test_existing_hardlink_output_never_truncates_source(tmp_path):
    rows = synthetic_repository(tmp_path)
    source = tmp_path / rows[0]["image_relative_path"]
    before = source.read_bytes()
    relative, _ = m.variant_paths(rows[0]["image_relative_path"], "L0")
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    os.link(source, target)
    with pytest.raises(FileExistsError):
        v._write_new(tmp_path, relative, b"must not truncate")
    with pytest.raises(ValueError, match="never overwritten"):
        v.generate_validation_variants(tmp_path)
    assert source.read_bytes() == target.read_bytes() == before


def test_direct_write_to_source_image_or_label_is_prohibited(tmp_path):
    rows = synthetic_repository(tmp_path)
    for field in ("image_relative_path", "label_relative_path"):
        path = tmp_path / rows[0][field]
        before = path.read_bytes()
        with pytest.raises(ValueError, match="protected raw"):
            v._write_new(tmp_path, rows[0][field], b"must not write")
        assert path.read_bytes() == before


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "2"])
def test_invalid_development_limit_rejected_before_source_read(tmp_path, monkeypatch, limit):
    synthetic_repository(tmp_path)
    forbid_raw_reads(monkeypatch)
    with pytest.raises(ValueError, match="positive integer"):
        v.generate_validation_variants(tmp_path, limit=limit)
    assert not (tmp_path / m.BENCHMARK_ROOT).exists()


def test_full_run_opens_only_approved_synthetic_sources_and_no_split_lists(tmp_path, monkeypatch):
    rows = synthetic_repository(tmp_path)
    allowed = {tmp_path / row[field] for row in rows for field in ("image_relative_path", "label_relative_path")}
    original = Path.open
    opened = set()

    def guarded(path, *args, **kwargs):
        if "/data/raw/" in path.as_posix():
            assert path in allowed
            opened.add(path)
        assert path.name not in ("test.csv", "train.csv", "test.txt", "train.txt", "valid.txt")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    v.generate_validation_variants(tmp_path)
    assert opened == allowed


@pytest.mark.parametrize("corruption", ["manifest_hash", "version", "duplicate", "missing_column", "extra_cell",
                                        "short_row", "empty", "excluded", "image_hash", "traversal", "label_pair"])
def test_malformed_source_metadata_fails_closed(tmp_path, monkeypatch, corruption):
    rows = synthetic_repository(tmp_path)
    if corruption == "manifest_hash":
        (tmp_path / m.VALID_MANIFEST).write_bytes(b"changed manifest")
    elif corruption == "version":
        (tmp_path / m.SOURCE_VERSION).write_text('{"manifest_sha256": null}', encoding="utf-8")
    elif corruption == "duplicate":
        write_source_metadata(tmp_path, rows + [rows[0]])
    elif corruption == "empty":
        write_source_metadata(tmp_path, [])
    elif corruption in ("excluded", "image_hash", "traversal", "label_pair"):
        field, value = {
            "excluded": ("exclusion_reason", "excluded"), "image_hash": ("image_sha256", "invalid"),
            "traversal": ("image_relative_path", "data/raw/../test/image.jpg"),
            "label_pair": ("label_relative_path", rows[1]["label_relative_path"]),
        }[corruption]
        rows[0][field] = value
        write_source_metadata(tmp_path, rows)
    else:
        data = (tmp_path / m.VALID_MANIFEST).read_bytes()
        if corruption == "missing_column":
            data = data.replace(b"processed_split,", b"", 1)
        elif corruption == "extra_cell":
            data = data.rstrip(b"\n") + b",extra\n"
        else:
            data += b"valid,valid\n"
        (tmp_path / m.VALID_MANIFEST).write_bytes(data)
        version = json.loads((tmp_path / m.SOURCE_VERSION).read_bytes())
        version["manifest_sha256"]["valid"] = m.sha256_bytes(data)
        (tmp_path / m.SOURCE_VERSION).write_bytes(m.deterministic_json_bytes(version))
    forbid_raw_reads(monkeypatch)
    with pytest.raises(ValueError):
        v.generate_validation_variants(tmp_path)
    assert not (tmp_path / m.BENCHMARK_ROOT).exists()


def test_source_content_must_match_approved_manifest(tmp_path):
    rows = synthetic_repository(tmp_path)
    path = tmp_path / rows[1]["image_relative_path"]
    path.write_bytes(path.read_bytes() + b"changed before generation")
    with pytest.raises(ValueError, match="source image hash differs"):
        v.generate_validation_variants(tmp_path)
    assert not (tmp_path / m.BENCHMARK_ROOT).exists()


@pytest.mark.parametrize("text", ["bad: config\n", "{", "global_seed: 42\nglobal_seed: 43\n"])
def test_bad_config_rejected_without_source_access(tmp_path, monkeypatch, text):
    synthetic_repository(tmp_path)
    config = tmp_path / "bad.yaml"
    config.write_text(text, encoding="utf-8")
    forbid_raw_reads(monkeypatch)
    with pytest.raises(ValueError):
        v.generate_validation_variants(tmp_path, config_path=config)
    assert not (tmp_path / m.BENCHMARK_ROOT).exists()


def test_existing_artifacts_not_overwritten(tmp_path):
    synthetic_repository(tmp_path)
    v.generate_validation_variants(tmp_path, limit=1)
    summary = tmp_path / m.BENCHMARK_ROOT / "manifests/benchmark_summary.json"
    before = summary.read_bytes()
    with pytest.raises(ValueError, match="never overwritten"):
        v.generate_validation_variants(tmp_path)
    assert summary.read_bytes() == before


def test_filename_collision_is_rejected_before_writes(tmp_path, monkeypatch):
    rows = synthetic_repository(tmp_path)
    original = v.variant_paths
    monkeypatch.setattr(v, "variant_paths", lambda source, severity: original(rows[0]["image_relative_path"], severity))
    forbid_raw_reads(monkeypatch)
    with pytest.raises(ValueError, match="collision"):
        v.generate_validation_variants(tmp_path)
    assert not (tmp_path / m.BENCHMARK_ROOT).exists()


@pytest.mark.parametrize("path", ["data/raw/gyu_det/v3/extracted/test/test/images/locked.jpg",
                                  "data/processed/gyu_det_v3_baseline_v1/splits/test.txt",
                                  "data/manifests/gyu_det_v3_baseline_v1/test.csv", "data/config.yaml"])
def test_config_argument_cannot_open_dataset_files(tmp_path, monkeypatch, path):
    def forbidden(*args, **kwargs):
        pytest.fail("dataset file disguised as config must not be opened")

    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(ValueError, match="outside dataset storage"):
        v.generate_validation_variants(tmp_path, config_path=path)


def run_cli(*args):
    script = Path(__file__).resolve().parents[2] / "scripts/low_light/generate_validation_variants.py"
    return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, text=True, check=False)


def test_cli_help():
    result = run_cli("--help")
    assert result.returncode == 0
    assert "--repo-root" in result.stdout
    assert "--source-split {valid}" in result.stdout
    assert "development sample" in result.stdout
    assert "--limit" in result.stdout


@pytest.mark.parametrize("split", ["test", "train", "validation"])
def test_cli_rejects_other_splits(tmp_path, split):
    result = run_cli("--repo-root", tmp_path, "--source-split", split)
    assert result.returncode != 0
    assert "invalid choice" in result.stderr
    assert not list(tmp_path.iterdir())


def test_cli_generation_and_contract_violation_exit_codes(tmp_path):
    synthetic_repository(tmp_path)
    result = run_cli("--repo-root", tmp_path, "--limit", 1)
    assert result.returncode == 0, result.stderr
    assert "development_sample: 1 validation sources, 5 variants" in result.stdout
    assert "No scientific evaluation performed" in result.stdout
    rejected = run_cli("--repo-root", tmp_path, "--output-root", "data/raw/forbidden")
    assert rejected.returncode != 0
    assert "Generation refused" in rejected.stderr
    assert not (tmp_path / "data/raw/forbidden").exists()
