"""Task E synthetic metrics/adapter tests. No real data, model inference or training."""

from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from src.low_light import evaluation as e
from src.low_light.manifest import deterministic_json_bytes


@pytest.fixture(autouse=True)
def no_real_dataset(monkeypatch):
    original = Path.open
    def guarded(path, *args, **kwargs):
        if path.resolve().is_relative_to(ROOT / "data"):
            pytest.fail("Task E unit test attempted real GYU data access")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)


def metrics(tp=3, fp=1, fn=2, ap=.6):
    counts = {c: (tp, fp, fn) for c in range(6)}
    aps = {c: (ap, ap / 2) if tp + fn else (None, None) for c in range(6)}
    return e.metric_payload(aps, counts)


def result(strategy=e.STRATEGIES[0], severity="L0", values=None):
    ll = strategy == e.STRATEGIES[2]
    model = dict(id=e.EXPERIMENT_ID if ll else e.PARENT_ID, architecture="YOLO26s",
                 checkpoint=e.TRAINING_ROOT + "/weights/best.pt" if ll else e.CHECKPOINT_PATH,
                 checkpoint_sha256="a" * 64 if ll else e.CHECKPOINT_SHA256)
    return e.make_result(strategy=strategy, severity=severity, model=model,
        benchmark=dict(protocol_id=e.PROTOCOL_ID, manifest=f"{e.BENCHMARK_ROOT}/manifests/validation_manifest.json",
                       manifest_sha256="1" * 64, summary_sha256="2" * 64, source_manifest_sha256="3" * 64, scope="full_validation"),
        metrics=values or metrics(), git_sha="1" * 40,
        environment=dict(versions=e.REQUIRED_VERSIONS.copy(), system="Windows", machine="AMD64", host="Laptop 1"))


def test_operating_formulas_and_undefined_ground_truth():
    value = e.operating_metrics(3, 1, 2)
    assert value["precision"] == .75
    assert value["recall"] == .6
    assert value["F1"] == pytest.approx(2 * .75 * .6 / (.75 + .6))
    assert value["false_negative_rate"] == .4
    assert e.operating_metrics(0, 0, 2)["F1"] == 0
    assert e.operating_metrics(0, 0, 0)["F1"] == 0
    assert e.operating_metrics(0, 0, 0)["false_negative_rate"] is None


@pytest.mark.parametrize("counts", [(-1, 0, 0), (True, 0, 0), (1.0, 1, 1), (0, float("nan"), 0)])
def test_invalid_counts_rejected(counts):
    with pytest.raises(ValueError):
        e.operating_metrics(*counts)


@pytest.mark.parametrize("strategy", e.STRATEGIES)
@pytest.mark.parametrize("severity", e.SEVERITY_IDS)
def test_same_confidence_for_every_strategy_severity(strategy, severity):
    e.require_condition(strategy, severity, confidence=.25)
    for value in (.001, .249, .251, .5, True, "0.25", float("nan")):
        with pytest.raises(ValueError):
            e.require_condition(strategy, severity, confidence=value)
    assert result(strategy, severity)["confidence_policy"]["operating_confidence"] == .25


def test_ap_sweep_is_independent_of_operating_counts():
    payload = metrics(tp=0, fp=0, fn=2, ap=.9)
    assert payload["aggregate"]["mAP50"] == pytest.approx(.9)
    assert payload["aggregate"]["recall"] == 0
    assert payload["aggregate"]["F1"] == 0
    assert e.confidence_policy()["AP"]["confidence_floor"] == .001
    assert e.confidence_policy()["AP"]["confidence_sweep"] is True
    assert len(e.confidence_policy()["AP"]["iou_thresholds"]) == 10


@pytest.mark.parametrize("key", e.AGGREGATE_FIELDS)
def test_required_aggregate_schema(key):
    payload = metrics()
    del payload["aggregate"][key]
    with pytest.raises(ValueError):
        e.validate_metrics(payload)


@pytest.mark.parametrize("key", e.PER_CLASS_FIELDS)
def test_required_per_class_schema(key):
    payload = metrics()
    del payload["per_class"][0][key]
    with pytest.raises(ValueError):
        e.validate_metrics(payload)


@pytest.mark.parametrize("location", ["aggregate", "per_class"])
def test_accuracy_is_not_accepted(location):
    payload = metrics()
    target = payload[location] if location == "aggregate" else payload[location][0]
    target["accuracy"] = .9
    with pytest.raises(ValueError):
        e.validate_metrics(payload)


@pytest.mark.parametrize("split", ["train", "test", "val", "TEST", "valid/test", None])
def test_validation_only(split):
    with pytest.raises(ValueError):
        e.require_condition(e.STRATEGIES[0], "L0", split)


def test_unsupported_strategy_and_severity_fail_closed():
    for strategy, severity in (("other", "L0"), (e.STRATEGIES[0], "Normal")):
        with pytest.raises(ValueError):
            e.require_condition(strategy, severity)


@pytest.mark.parametrize("key,value", [("id", "DET-FINAL-v2"), ("architecture", "YOLO26n"),
                                      ("checkpoint_sha256", "0" * 64), ("checkpoint", "another.pt")])
def test_det_final_identity_frozen(key, value):
    payload = result()
    payload["model"][key] = value
    with pytest.raises(ValueError):
        e.validate_result(payload)
    assert e.CHECKPOINT_SHA256 == "4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3"


def test_missing_ll_checkpoint_rejected_without_model_import(tmp_path):
    with pytest.raises(FileNotFoundError, match="required local checkpoint absent"):
        e.checkpoint_identity(tmp_path, e.STRATEGIES[2])
    assert not (tmp_path / e.TRAINING_ROOT).exists()


def test_bad_parent_hash_rejected(tmp_path):
    path = tmp_path / e.CHECKPOINT_PATH
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic checkpoint, never loaded")
    with pytest.raises(ValueError, match="SHA-256"):
        e.checkpoint_identity(tmp_path, e.STRATEGIES[0])


def test_clahe_is_task_b_function(monkeypatch):
    image = np.full((16, 24, 3), 30, np.uint8)
    sentinel = image.copy()
    calls = []
    def task_b(pixels):
        calls.append(pixels)
        return sentinel
    monkeypatch.setattr(e.clahe, "apply_clahe", task_b)
    assert e.enhance(image, e.STRATEGIES[1]) is sentinel
    for strategy in (e.STRATEGIES[0], e.STRATEGIES[2]):
        assert e.enhance(image, strategy) is image
    assert len(calls) == 1 and calls[0] is image


def test_result_determinism_and_order():
    assert deterministic_json_bytes(result()) == deterministic_json_bytes(result())
    rows = [result(s, level) for s in reversed(e.STRATEGIES) for level in reversed(e.SEVERITY_IDS)]
    assert [(r["strategy"], r["severity"]) for r in e.order_results(rows)] == [
        (s, level) for s in e.STRATEGIES for level in e.SEVERITY_IDS]
    assert e.comparisons(rows) == e.comparisons(list(reversed(rows)))


def test_no_wall_clock_identity():
    payload = result()
    assert "timestamp" not in deterministic_json_bytes(payload).decode()
    payload["started_utc"] = "2026-01-01"
    with pytest.raises(ValueError):
        e.validate_result(payload)
    payload = result()
    payload["environment"]["timestamp"] = "now"
    with pytest.raises(ValueError):
        e.validate_result(payload)


def test_laptop_label_cannot_claim_official():
    payload = result()
    assert payload["evidence"]["label"] == e.NON_OFFICIAL
    assert payload["evidence"]["official_scientific_performance"] is False
    payload["evidence"]["official_scientific_performance"] = True
    with pytest.raises(ValueError):
        e.validate_result(payload)


def test_regression_and_retention():
    rows = [result(s, level, metrics(tp=1 if level != "L0" else 3, fp=1, fn=2,
                ap=.3 if level != "L0" else (.6 if s == e.STRATEGIES[0] else .5)))
            for s in e.STRATEGIES for level in e.SEVERITY_IDS]
    report = e.comparisons(rows)
    assert report["normal_light_regression"][1]["deltas"]["mAP50"] == pytest.approx(-.1)
    assert report["normal_light_regression"][1]["deltas"]["mAP50-95"] == pytest.approx(-.05)
    assert all(v == 0 for v in report["normal_light_regression"][0]["deltas"].values())
    first = report["low_light_retention"][0]
    assert first["metric_retention"]["mAP50"] == .5
    assert first["metric_retention"]["recall"] == pytest.approx((1 / 3) / (3 / 5))
    assert first["false_negative_rate_ratio"] == pytest.approx((2 / 3) / (2 / 5))


@pytest.mark.parametrize("low,normal", [(0, 0), (.3, 0), (None, .5), (.3, None)])
def test_undefined_retention(low, normal):
    assert e.retention(low, normal) is None


def test_comparison_rejects_partial_and_mixed_provenance():
    with pytest.raises(ValueError):
        e.comparisons([result()])
    rows = [result(s, level) for s in e.STRATEGIES for level in e.SEVERITY_IDS]
    rows[-1]["benchmark"]["manifest_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="mixed"):
        e.comparisons(rows)


def test_count_adapter_keeps_ap_predictions_and_rematches():
    import torch
    from ultralytics.models.yolo.detect import DetectionValidator
    class FakeBase:
        def __init__(self):
            self.niou = 10
            self.iouv = torch.linspace(.5, .95, 10)
            self.device = torch.device("cpu")
        _process_batch = DetectionValidator._process_batch
        match_predictions = DetectionValidator.match_predictions
        def _prepare_batch(self, i, batch):
            return batch
        def update_metrics(self, preds, batch):
            self.ap_predictions = preds
    validator = e.validator_adapter(FakeBase)()
    predictions = [{"conf": torch.tensor([.249, .25, .8]), "cls": torch.tensor([0., 0., 0.]),
                    "bboxes": torch.tensor([[0., 0., 10., 10.], [0., 0., 10., 10.], [0., 0., 10., 10.]])}]
    truth = {"cls": torch.tensor([0., 0.]), "bboxes": torch.tensor([[0., 0., 10., 10.], [20., 20., 30., 30.]])}
    validator.update_metrics(predictions, truth)
    assert validator.operating_counts[0] == [1, 1, 1]
    assert validator.ap_predictions is predictions
    assert len(validator.ap_predictions[0]["conf"]) == 3


def test_raw_access_guard_denies_all_raw_splits(tmp_path):
    for split in ("train", "valid", "test"):
        path = tmp_path / "data/raw/gyu_det/v3/extracted" / split / split / "synthetic.jpg"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"synthetic")
        with e.no_raw_access(tmp_path), pytest.raises(PermissionError):
            path.read_bytes()


def test_exclusive_output_write(tmp_path):
    relative = e.EVALUATION_ROOT + "/synthetic/result.json"
    e.write_new(tmp_path, relative, result())
    with pytest.raises(FileExistsError):
        e.write_new(tmp_path, relative, result())
    with pytest.raises(ValueError):
        e.write_new(tmp_path, "data/raw/result.json", result())


def test_desktop_gate_rejects_laptop_before_inference(tmp_path, monkeypatch):
    monkeypatch.setattr(e, "git_identity", lambda _: dict(branch=e.BRANCH, sha="1" * 40, source_status=""))
    monkeypatch.setattr(e, "environment_identity", lambda: result()["environment"])
    with pytest.raises(ValueError, match="ARMOURY"):
        e.require_desktop(tmp_path, "1" * 40, "ARMOURY")


@pytest.fixture
def desktop_identity(tmp_path, monkeypatch):
    identity = dict(branch=e.BRANCH, sha="1" * 40, source_status="")
    monkeypatch.setattr(e, "git_identity", lambda _: identity)
    monkeypatch.setattr(e.platform, "node", lambda: "AritraA")
    monkeypatch.setattr(e.platform, "system", lambda: "Linux")
    monkeypatch.setattr(e.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(e.platform, "python_version", lambda: e.REQUIRED_VERSIONS["python"])
    monkeypatch.setattr(e.importlib.metadata, "version", lambda name: e.REQUIRED_VERSIONS[name])
    calls = []
    monkeypatch.setattr(e.subprocess, "run", lambda command, **kwargs: calls.append(command))
    return identity, calls


@pytest.mark.parametrize("hostname", ["AritraA", "aritraa", "ARITRAA"])
def test_desktop_machine_identity_accepts_exact_physical_hostname(tmp_path, monkeypatch, desktop_identity, hostname):
    monkeypatch.setattr(e.platform, "node", lambda: hostname)
    provenance = e.require_desktop(tmp_path, "1" * 40, "ARMOURY")
    assert provenance["environment"] == dict(versions=e.REQUIRED_VERSIONS, system="Linux", machine="x86_64", host=hostname)
    assert desktop_identity[1] == [["git", "merge-base", "--is-ancestor", e.CANONICAL_BASE, "1" * 40]]


@pytest.mark.parametrize("hostname", ["OtherMachine", "armoury-dev", "AritraA-test", "localhost", "armoury", " AritraA"])
def test_desktop_machine_identity_role_does_not_authorize_hostname(tmp_path, monkeypatch, desktop_identity, hostname):
    monkeypatch.setattr(e.platform, "node", lambda: hostname)
    with pytest.raises(ValueError, match="ARMOURY machine identity"):
        e.require_desktop(tmp_path, "1" * 40, "ARMOURY")
    assert desktop_identity[1] == []


@pytest.mark.parametrize("role", [None, "AritraA", "armoury", "OtherMachine"])
def test_desktop_machine_identity_requires_logical_acknowledgement(tmp_path, desktop_identity, role):
    with pytest.raises(ValueError, match="explicit ARMOURY host"):
        e.require_desktop(tmp_path, "1" * 40, role)


@pytest.mark.parametrize("package", list(e.REQUIRED_VERSIONS))
def test_desktop_machine_identity_preserves_version_gate(tmp_path, monkeypatch, desktop_identity, package):
    env = e.environment_identity()
    env["versions"][package] = "wrong"
    monkeypatch.setattr(e, "environment_identity", lambda: env)
    with pytest.raises(ValueError, match="required software versions differ"):
        e.require_desktop(tmp_path, "1" * 40, "ARMOURY")


@pytest.mark.parametrize("key,value", [("branch", "main"), ("sha", "2" * 40), ("source_status", " M src/low_light/evaluation.py")])
def test_desktop_machine_identity_preserves_checkout_gate(tmp_path, desktop_identity, key, value):
    desktop_identity[0][key] = value
    with pytest.raises(ValueError, match="exact accepted branch/commit"):
        e.require_desktop(tmp_path, "1" * 40, "ARMOURY")


@pytest.mark.parametrize("hostname,authorized", [("AritraA", True), ("aritraa", True), ("ARITRAA", True), ("armoury", False), ("OtherMachine", False)])
def test_result_machine_identity_requires_physical_hostname(hostname, authorized):
    payload = result()
    payload["environment"]["host"] = hostname
    payload["evidence"]["label"] = "ARMOURY VALIDATION DEVELOPMENT — NOT LOCKED-TEST EVIDENCE"
    if authorized:
        e.validate_result(payload)
    else:
        with pytest.raises(ValueError, match="smoke/debug label"):
            e.validate_result(payload)


def test_benchmark_exif_restoration_and_no_raw_pixels(tmp_path):
    from PIL import Image
    import cv2
    from src.low_light.manifest import sha256_file
    rows = []
    for level, extension in (("L0", ".jpg"), ("L1", ".png")):
        relative = f"{e.BENCHMARK_ROOT}/valid/{level}/images/example{extension}"
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        pixels = np.zeros((12, 20, 3), np.uint8)
        pixels[:, :10, 0] = 200
        image = Image.fromarray(pixels)
        exif = Image.Exif()
        if level == "L0":
            exif[274] = 6
        image.save(path, exif=exif)
        rows.append(dict(source_relative_path="synthetic/example.jpg", output_relative_path=relative,
                         severity=level, generated_height=12, generated_width=20, generated_image_sha256=sha256_file(path)))
    reader, shape = e.benchmark_reader(tmp_path, rows, e.STRATEGIES[0])
    for row in rows:
        path = tmp_path / row["output_relative_path"]
        stored = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
        assert np.array_equal(reader(path), cv2.rotate(stored, cv2.ROTATE_90_CLOCKWISE))
        assert shape(path) == (20, 12)


def test_metric_schema_rejects_inconsistent_aggregate():
    payload = metrics()
    payload["aggregate"]["F1"] = .99
    with pytest.raises(ValueError):
        e.validate_metrics(payload)


def test_all_regression_deltas_follow_normal_baseline():
    rows = [result(s, level, metrics(tp=3 if s == e.STRATEGIES[0] else 2, fp=1, fn=2, ap=.6))
            for s in e.STRATEGIES for level in e.SEVERITY_IDS]
    report = e.comparisons(rows)
    baseline = rows[0]["metrics"]["aggregate"]
    candidate = rows[5]["metrics"]["aggregate"]
    assert report["normal_light_regression"][1]["deltas"] == {
        k: candidate[k] - baseline[k] for k in e.AGGREGATE_FIELDS}


def test_benchmark_load_binds_source_hash_and_checks_generated_pixels(tmp_path, monkeypatch):
    from tests.low_light.test_manifest import synthetic_repository
    from src.low_light import validation_variants as v
    from detection.training import config as detector_config
    synthetic_repository(tmp_path)
    v.generate_validation_variants(tmp_path)
    source_hash = e.sha256_file(tmp_path / e.VALID_MANIFEST)
    monkeypatch.setitem(detector_config.APPROVED_HASHES, e.VALID_MANIFEST.as_posix(), source_hash)
    # Verification can open only metadata/generated files, never source pixels.
    with e.no_raw_access(tmp_path):
        records, identity = e.load_benchmark(tmp_path, Path("configs/low_light/benchmark_v1.yaml"))
    assert len(records) == 10 and identity["source_manifest_sha256"] == source_hash
    output = tmp_path / records[0]["output_relative_path"]
    output.write_bytes(b"tampered synthetic image")
    with e.no_raw_access(tmp_path), pytest.raises(ValueError, match="SHA-256"):
        e.load_benchmark(tmp_path, Path("configs/low_light/benchmark_v1.yaml"))


def test_synthetic_development_prefix_cannot_be_scientific_benchmark(tmp_path, monkeypatch):
    from tests.low_light.test_manifest import synthetic_repository
    from src.low_light import validation_variants as v
    from detection.training import config as detector_config
    synthetic_repository(tmp_path)
    v.generate_validation_variants(tmp_path, limit=1)
    monkeypatch.setitem(detector_config.APPROVED_HASHES, e.VALID_MANIFEST.as_posix(), e.sha256_file(tmp_path / e.VALID_MANIFEST))
    with pytest.raises(ValueError, match="full validation membership"):
        e.load_benchmark(tmp_path, Path("configs/low_light/benchmark_v1.yaml"))
