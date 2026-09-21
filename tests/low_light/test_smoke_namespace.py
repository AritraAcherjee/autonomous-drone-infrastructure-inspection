"""Static/synthetic checks for the bounded LL-DETECTOR smoke namespace interface."""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from scripts.low_light import prepare_desktop_handoff as h
from src.low_light import evaluation as e
from src.low_light.manifest import deterministic_json_bytes, sha256_file


V1 = h.SMOKE_EXECUTION_V1
V2 = h.SMOKE_EXECUTION_V2


def test_default_and_explicit_v1_preserve_historical_mapping():
    expected = h.SmokeNamespace(V1, "LL-DETECTOR-01-SMOKE",
                                "outputs/training/low_light/LL-DETECTOR-01-SMOKE")
    assert h.resolve_smoke_namespace() == expected
    assert h.resolve_smoke_namespace(V1) == expected
    assert h.smoke_config() == h.smoke_config(V1)
    assert h.smoke_config()["id"] == expected.run_name
    assert h.smoke_config()["output_root"] == expected.training_root


def test_explicit_v2_mapping_and_all_derived_paths():
    namespace = h.resolve_smoke_namespace(V2)
    root = "outputs/training/low_light/LL-DETECTOR-01-SMOKE-V2"
    assert namespace == h.SmokeNamespace(V2, "LL-DETECTOR-01-SMOKE-V2", root)
    config = h.smoke_config(V2)
    manifest = h.smoke_execution_manifest("a" * 40, V2)
    arguments = h.smoke_runtime_arguments({"project": str(ROOT / "outputs/training/low_light"),
                                           "name": "LL-DETECTOR-01"}, V2)
    assert config["id"] == arguments["name"] == namespace.run_name
    assert config["output_root"] == manifest["training_root"] == root
    assert Path(arguments["project"]) / arguments["name"] == ROOT / root
    assert manifest["trainer_log"] == f"{root}/trainer.log"
    assert manifest["results_csv"] == f"{root}/results.csv"
    assert manifest["checkpoint_directory"] == f"{root}/weights"
    assert manifest["manifest"] == f"{root}/execution_manifest.json"
    assert all(path.startswith(root + "/") for path in h.smoke_bundle_paths(V2))
    assert h.smoke_bundle_report_path(V2).startswith(root + "/")


def test_v1_v2_roots_are_canonically_distinct_and_not_nested(tmp_path):
    assert h.smoke_namespaces_non_overlapping(tmp_path) is True
    v1 = (tmp_path / h.resolve_smoke_namespace(V1).training_root).resolve()
    v2 = (tmp_path / h.resolve_smoke_namespace(V2).training_root).resolve()
    assert v1 != v2 and not v1.is_relative_to(v2) and not v2.is_relative_to(v1)


@pytest.mark.parametrize("identity", [
    "", " ", "unknown", "ws04_ll_detector_01_smoke_v2", "WS04_LL_DETECTOR_01_SMOKE_V3",
    "/tmp/run", r"C:\\tmp\\run", "C:run", "..", "../", r"..\\", "a/b", r"a\\b",
    "WS04_LL_DETECTOR_01_SMOKE_V1/alias", "WS04_LL_DETECTOR_01_SMOKE_V2-suffix",
    "LL-DETECTOR-01-SMOKE", "LL-DETECTOR-01-SMOKE-V2", "$(touch injected)", "V2;rm",
])
def test_non_allowlisted_identity_fails_closed(identity):
    with pytest.raises(ValueError, match="unsupported smoke execution identity"):
        h.resolve_smoke_namespace(identity)


def test_existing_selected_destination_fails_without_rename_or_mutation(tmp_path):
    selected = tmp_path / h.resolve_smoke_namespace(V2).training_root
    selected.mkdir(parents=True)
    sentinel = selected / "sentinel.txt"
    sentinel.write_text("immutable\n", encoding="utf-8")
    with pytest.raises(ValueError, match="already exists"):
        h.require_smoke_destination_absent(tmp_path, V2)
    assert sentinel.read_text(encoding="utf-8") == "immutable\n"
    assert sorted(selected.parent.iterdir()) == [selected]


def _write_passing_smoke(root: Path, execution_id: str, *, recorded_identity: str | None = None,
                         manifest_identity: str | None = None):
    namespace = h.resolve_smoke_namespace(execution_id)
    out = root / namespace.training_root
    (out / "weights").mkdir(parents=True)
    checkpoints = {}
    for name in ("best.pt", "last.pt"):
        path = out / "weights" / name
        path.write_bytes((execution_id + name).encode())
        checkpoints[name] = sha256_file(path)
    report = dict(status="PASS", git_sha="a" * 40, execution_id=recorded_identity or execution_id,
                  smoke_config=h.smoke_config(execution_id), locked_test_accessed=False,
                  raw_immutability="PASS", finite_losses=True, no_oom=True, epochs=1,
                  optimizer_steps=1, parameter_updates=1, validation_calls=1,
                  parent_checkpoint={"checkpoint_sha256": "parent"}, checkpoints=checkpoints)
    (out / "smoke_evidence.json").write_bytes(deterministic_json_bytes(report))
    if execution_id == V2:
        manifest = h.smoke_execution_manifest("a" * 40, manifest_identity or execution_id)
        (out / "execution_manifest.json").write_bytes(deterministic_json_bytes(manifest))
    return out


def test_verification_reads_only_selected_namespace(tmp_path, monkeypatch):
    v1 = _write_passing_smoke(tmp_path, V1)
    v2 = _write_passing_smoke(tmp_path, V2)
    monkeypatch.setattr(e, "checkpoint_identity", lambda *_: {"checkpoint_sha256": "parent"})
    assert h.smoke_passed(tmp_path, "a" * 40, V1)["execution_id"] == V1
    assert h.smoke_passed(tmp_path, "a" * 40, V2)["execution_id"] == V2
    assert v1 != v2


def test_verification_identity_output_mismatch_fails_closed(tmp_path, monkeypatch):
    _write_passing_smoke(tmp_path, V2, recorded_identity=V1)
    monkeypatch.setattr(e, "checkpoint_identity", lambda *_: {"checkpoint_sha256": "parent"})
    with pytest.raises(ValueError, match="passing smoke evidence"):
        h.smoke_passed(tmp_path, "a" * 40, V2)


def test_manifest_identity_output_mismatch_fails_closed(tmp_path, monkeypatch):
    out = _write_passing_smoke(tmp_path, V2)
    bad = h.smoke_execution_manifest("a" * 40, V1)
    (out / "execution_manifest.json").write_bytes(deterministic_json_bytes(bad))
    monkeypatch.setattr(e, "checkpoint_identity", lambda *_: {"checkpoint_sha256": "parent"})
    with pytest.raises(ValueError, match="execution identity/output mismatch"):
        h.smoke_passed(tmp_path, "a" * 40, V2)


def test_bundle_fails_on_identity_mismatch_before_other_bundle_work(tmp_path, monkeypatch):
    _write_passing_smoke(tmp_path, V2, recorded_identity=V1)
    monkeypatch.setattr(h, "verify_result_bundle", lambda *_: pytest.fail("bundle continued after mismatch"))
    with pytest.raises(ValueError, match="passing smoke evidence"):
        h.bundle(tmp_path, "a" * 40, V2)


def test_v1_and_v2_bundle_inputs_and_outputs_do_not_cross():
    v1 = set(h.smoke_bundle_paths(V1))
    v2 = set(h.smoke_bundle_paths(V2))
    assert v1.isdisjoint(v2)
    assert all(path.startswith(h.resolve_smoke_namespace(V1).training_root + "/") for path in v1)
    assert all(path.startswith(h.resolve_smoke_namespace(V2).training_root + "/") for path in v2)
    assert h.smoke_bundle_report_path(V1) != h.smoke_bundle_report_path(V2)


def test_collision_guard_precedes_runtime_imports_loaders_and_trainer():
    source = (ROOT / "scripts/low_light/prepare_desktop_handoff.py").read_text(encoding="utf-8")
    start = source.index("def run_smoke(")
    body = source[start:source.index("\ndef compare_results", start)]
    collision = body.index("require_smoke_destination_absent")
    for later in ("configure_runtime(repo)", "stage_offline_arial_font(repo)", "import torch",
                  "load_development_data(repo)", "trainer_class()"):
        assert collision < body.index(later)


def test_cli_exposes_only_bounded_execution_identity(capsys):
    with pytest.raises(SystemExit) as exc:
        h.main(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--smoke-execution-id" in help_text
    assert V1 in help_text and V2 in help_text
    assert "--output-root" not in help_text and "--run-name" not in help_text
