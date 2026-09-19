"""Static/synthetic Desktop handoff checks; all execution functions are tripwired."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from scripts.low_light import prepare_desktop_handoff as h
from scripts.low_light import evaluate_low_light as cli
from src.low_light import evaluation as e
from src.low_light.manifest import deterministic_json_bytes


@pytest.fixture
def passing_gates(tmp_path, monkeypatch):
    """Only synthetic receipts/sources; never modify the accepted evidence."""
    from detection.training.trainer import implementation_identity
    for relative in ("src/detection/training/dataset.py", "scripts/train_detector.py",
                     "scripts/verify_detector_exif.py", "scripts/check_detector_training.py"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic source\n", encoding="utf-8")
    package = tmp_path / "synthetic_install/ultralytics"
    for relative in ("__init__.py", "data/base.py", "data/dataset.py", "data/utils.py",
                     "data/augment.py", "utils/patches.py"):
        path = package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("raise AssertionError('loader must only be hashed, never imported')\n", encoding="utf-8")
    original_spec = h.importlib.util.find_spec
    monkeypatch.setattr(h.importlib.util, "find_spec", lambda name: (
        SimpleNamespace(origin=str(package / "__init__.py")) if name == "ultralytics" else original_spec(name)))
    evidence_path = tmp_path / Path(h.TEST_GATE).parent / "synthetic_tests.txt"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_bytes(b"synthetic passing test evidence\n")
    receipts = {
        h.TEST_GATE: dict(status="PASS", implementation=implementation_identity(tmp_path),
                         evidence_sha256={evidence_path.relative_to(tmp_path).as_posix(): h.sha256_file(evidence_path)}),
        h.GEOMETRY_GATE: dict(status="PASS", checked=594, passed=594, test_accessed=False,
                             raw_immutability={"status": "PASS"}, source_identity=h.geometry_source_identity(tmp_path)),
    }
    for relative, payload in receipts.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(deterministic_json_bytes(payload))
    return receipts


@pytest.fixture
def preflight_environment(tmp_path, monkeypatch, passing_gates):
    from detection.training import config as training_config
    import subprocess
    calls = []
    def git(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="")
    monkeypatch.setattr(e, "git_identity", lambda _: dict(branch=e.BRANCH, sha="a" * 40, source_status=""))
    monkeypatch.setattr(subprocess, "run", git)
    monkeypatch.setattr(h, "load_benchmark_config", lambda _: {})
    monkeypatch.setattr(h.ll, "load_config", lambda _: {"data": {"test_policy": "prohibited"}})
    monkeypatch.setattr(e, "checkpoint_identity", lambda *a: {"checkpoint_sha256": e.CHECKPOINT_SHA256})
    monkeypatch.setattr(e, "environment_identity", lambda: dict(versions=e.REQUIRED_VERSIONS.copy(), host="synthetic"))
    monkeypatch.setattr(training_config, "load_development_data", lambda _: ({}, {"train": [], "valid": []}))
    return calls


def test_required_stages_and_exact_commands():
    payload = h.handoff()
    assert [s["number"] for s in payload["stages"]] == list(range(1, 14))
    text = deterministic_json_bytes(payload).decode()
    for phrase in ("checkout", "environment", "checkpoint/hash", "dataset identity", "full validation benchmark",
                   "manifests/sanity", "DET-FINAL raw", "CLAHE + DET-FINAL", "smoke training", "100-epoch",
                   "LL-DETECTOR-01 L0-L4", "latency protocol", "return evidence"):
        assert phrase in text
    for stage in payload["stages"]:
        assert stage["commands"] and all(isinstance(c, str) and c for c in stage["commands"])
    assert payload["accepted_commit"] == "TBD"
    assert payload["branch"] == "04/low-light-detector"
    assert payload["canonical_base"] == "013067277d331246959af1f6176584b5305828f4"


def test_handoff_frozen_identity_roots_and_test_lock():
    payload = h.handoff()
    assert payload["det_final"]["checkpoint_sha256"] == "4c7a32c9b40c0795bbe59aca5952a0631e1524ec731ad2c7441cccb1b44f71c3"
    assert payload["configs"] == ["configs/low_light/benchmark_v1.yaml", "configs/low_light/ll_detector_01.yaml"]
    assert payload["output_roots"]["benchmark"] == "outputs/experiments/low_light/benchmark_v1"
    assert payload["output_roots"]["evaluation"] == "outputs/experiments/low_light/evaluation"
    assert payload["output_roots"]["training"] == "outputs/training/low_light/LL-DETECTOR-01"
    assert "PROHIBITED" in payload["locked_test"]
    assert "--source-split test" not in deterministic_json_bytes(payload).decode()


def test_return_evidence_complete():
    checklist = h.handoff()["return_evidence"]
    assert set(checklist) == {"benchmark", "det_final_raw", "clahe", "ll_smoke", "ll_detector_01", "post_training", "latency"}
    assert set(checklist["ll_smoke"]) == {"smoke config", "finite-loss evidence", "optimizer-update evidence",
        "validation evidence", "checkpoint-save evidence", "no-OOM evidence", "raw immutability result", "locked-test non-access statement"}
    assert {"best.pt", "last.pt", "best epoch", "environment/provenance", "training log", "checkpoint hashes"} <= set(checklist["ll_detector_01"])
    assert {"mean", "median", "p95", "end-to-end FPS", "hardware identity", "batch=1", "imgsz=640", "50 untimed warmups"} <= set(checklist["latency"])
    assert {"normal-light regression deltas", "low-light retention metrics"} <= set(checklist["post_training"])


def test_handoff_deterministic_and_no_performance_claim():
    assert deterministic_json_bytes(h.handoff()) == deterministic_json_bytes(h.handoff())
    assert h.handoff()["scientific_performance_claim"] is False
    assert h.handoff()["smoke"]["evidence"] == e.NON_OFFICIAL


@pytest.mark.parametrize("commit", [None, "main", "TBD", "a" * 39, e.CANONICAL_BASE])
def test_preflight_requires_exact_commit_before_any_access(tmp_path, commit, monkeypatch):
    monkeypatch.setattr(e, "git_identity", lambda *_: pytest.fail("unexpected Git access"))
    with pytest.raises(ValueError):
        h.preflight(tmp_path, commit)


def test_preflight_is_static_no_train_inference_or_test_image_access(tmp_path, monkeypatch, preflight_environment):
    from detection.training import trainer
    monkeypatch.setattr(h, "run_smoke", lambda *a: pytest.fail("preflight invoked training"))
    monkeypatch.setattr(h, "run_full", lambda *a: pytest.fail("preflight invoked full training"))
    monkeypatch.setattr(trainer, "run", lambda *a, **k: pytest.fail("preflight invoked trainer"))
    monkeypatch.setattr(trainer, "trainer_class", lambda *a: pytest.fail("preflight constructed a trainer"))
    monkeypatch.setattr(e, "run_evaluation", lambda *a: pytest.fail("preflight invoked inference"))
    from src.low_light import validation_variants
    monkeypatch.setattr(validation_variants, "generate_validation_variants", lambda *a, **k: pytest.fail("preflight generated benchmark"))
    original = Path.open
    def no_images(path, *a, **k):
        if "raw" in path.parts or "test" in path.parts or path.suffix.lower() in (".jpg", ".png"):
            pytest.fail("preflight attempted image/test data access")
        return original(path, *a, **k)
    monkeypatch.setattr(Path, "open", no_images)
    before_modules = set(sys.modules)
    report = h.preflight(tmp_path, "a" * 40)
    assert report["status"] == "STATIC_PREFLIGHT_PASS"
    assert report["training_executed"] is report["inference_executed"] is report["locked_test_accessed"] is False
    assert report["benchmark_generation_executed"] is report["desktop_execution_authorized"] is False
    assert report["detector_safety_gates"]["status"] == "PASS"
    assert report["accepted_commit"] == "a" * 40
    assert report["environment"]["versions"] == e.REQUIRED_VERSIONS
    assert report["cuda_required"] is True and report["cuda_checked"] is False
    assert not any(name.startswith(("torch", "ultralytics")) for name in set(sys.modules) - before_modules)
    assert ["git", "merge-base", "--is-ancestor", e.CANONICAL_BASE, "a" * 40] in preflight_environment
    assert any(command[:3] == ["git", "ls-files", "--error-unmatch"] and
               all(path in command for path in h.GATE_PATHS) for command in preflight_environment)


def test_preflight_rejects_wrong_branch(tmp_path, monkeypatch):
    monkeypatch.setattr(e, "git_identity", lambda _: dict(branch="main", sha="a" * 40, source_status=""))
    with pytest.raises(ValueError, match="branch/commit"):
        h.preflight(tmp_path, "a" * 40)


def test_static_cli_writes_only_explicit_artifact(tmp_path, capsys):
    assert h.main(["--repo-root", str(tmp_path), "--mode", "static", "--write"]) == 0
    capsys.readouterr()
    path = tmp_path / h.HANDOFF_PATH
    payload = h.handoff(repo=tmp_path)
    assert path.read_bytes() == deterministic_json_bytes(payload)
    assert payload["engineering_readiness"]["status"] == "BLOCKED"
    assert payload["readiness"] == "04 ENGINEERING HANDOFF — BLOCKED"
    assert not (tmp_path / "outputs").exists()
    with pytest.raises(SystemExit):
        h.main(["--repo-root", str(tmp_path), "--mode", "static", "--write"])


@pytest.mark.parametrize("main", [h.main, cli.main])
def test_cli_help_is_safe(main, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "--mode" in capsys.readouterr().out


def test_evaluation_defaults_to_plan(monkeypatch, capsys):
    monkeypatch.setattr(e, "run_evaluation", lambda *a, **k: pytest.fail("plan invoked inference"))
    assert cli.main(["--strategy", e.STRATEGIES[0], "--severity", "L0", "--config", h.BENCHMARK_CONFIG]) == 0
    assert '"detector_inference_executed": false' in capsys.readouterr().out


@pytest.mark.parametrize("args", [[], ["--strategy", "other", "--severity", "L0", "--config", h.BENCHMARK_CONFIG],
    ["--strategy", e.STRATEGIES[0], "--severity", "L0", "--config", h.BENCHMARK_CONFIG, "--source-split", "test"]])
def test_cli_unsupported_inputs_fail_closed(args):
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code != 0


def test_smoke_is_tiny_bounded_and_separate():
    config = h.smoke_config()
    assert config["epochs"] == 1 and config["train_images"] == 16 and config["valid_images"] == 8
    assert config["cuda_required"] is True and config["test_policy"] == "prohibited"
    assert config["output_root"] != e.TRAINING_ROOT
    assert h.ll.load_config()["training"]["epochs"] == 100


def test_full_training_requires_smoke_evidence(tmp_path):
    with pytest.raises(FileNotFoundError):
        h.smoke_passed(tmp_path, "a" * 40)


def test_checked_artifact_matches_generator(tmp_path, passing_gates, monkeypatch):
    from detection.training import exif
    monkeypatch.setattr(exif, "source_identity", lambda: h.geometry_source_identity(tmp_path))
    # Keep the checked contract independent of the live receipt that binds this test.
    expected = h.handoff(repo=tmp_path)
    assert expected["engineering_readiness"]["status"] == "READY_FOR_FINAL_COMMIT"
    assert expected["engineering_readiness"]["blocker"] is None
    assert expected["readiness"] == "04 ENGINEERING HANDOFF — READY FOR FINAL COMMIT"
    assert expected["accepted_commit"] == "TBD"
    assert expected["desktop_execution_authorized"] is False
    assert (ROOT / h.HANDOFF_PATH).read_bytes() == deterministic_json_bytes(expected)


def test_training_gates_report_stale_receipt_without_rewriting(tmp_path, monkeypatch):
    from detection.training import trainer
    monkeypatch.setattr(trainer, "implementation_identity", lambda _: {"new.py": "new-hash"})
    receipt = tmp_path / "outputs/validation/defect_detection/training_pipeline/before/ready.json"
    receipt.parent.mkdir(parents=True)
    before = deterministic_json_bytes(dict(status="PASS", implementation={"old.py": "old-hash"}, evidence_sha256={}))
    receipt.write_bytes(before)
    report = h.training_gate_diagnostics(tmp_path)
    assert report["status"] == "BLOCKED"
    assert "stale" in report["blockers"][0]
    assert receipt.read_bytes() == before


def test_best_epoch_recorded_at_save_not_from_final_history(tmp_path, monkeypatch):
    from detection.training import trainer as existing
    monkeypatch.setattr(h, "smoke_passed", lambda *a: {})
    class FakeTrainer:
        def save_model(self):
            pass
    monkeypatch.setattr(existing, "trainer_class", lambda: FakeTrainer)
    def fake_run(*args, **kwargs):
        selected = existing.trainer_class()()
        for epoch, fitness, best in ((0, .4, .4), (1, .6, .6), (2, .5, .6)):
            selected.epoch, selected.fitness, selected.best_fitness = epoch, fitness, best
            selected.save_model()
        path = tmp_path / e.TRAINING_ROOT / "weights/best.pt"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"synthetic checkpoint, never loaded")
        return {"status": "PASS"}
    monkeypatch.setattr(existing, "run", fake_run)
    assert h.run_full(tmp_path, "a" * 40) == {"status": "PASS"}
    report = h.strict_json_loads((tmp_path / e.EVALUATION_ROOT / "training_checkpoint_selection.json").read_bytes())
    assert report["best_epoch_zero_based"] == 1
    assert report["fitness"] == .6


def test_handoff_declares_refreshed_gates_and_distinct_readiness(tmp_path, passing_gates, monkeypatch):
    from detection.training import exif
    monkeypatch.setattr(exif, "source_identity", lambda: h.geometry_source_identity(tmp_path))
    payload = h.handoff(repo=tmp_path)
    assert payload["existing_training_gate_paths"] == [
        "outputs/validation/defect_detection/exif_alignment/geometry.json",
        "outputs/validation/defect_detection/training_pipeline/before/ready.json",
    ]
    text = deterministic_json_bytes(payload).decode()
    for obsolete in ("source-specific geometry/test receipts are available", "hard-codes old evidence paths",
                     "separately authorized isolated gate path/wrapper", "geometry receipt is stale",
                     "test receipt is stale"):
        assert obsolete not in text
    assert "refreshed after the authorized Workstream 04 changes" in payload["gate_resolution"]
    assert "must travel with the accepted 04 commit" in payload["gate_resolution"]
    assert payload["engineering_readiness"]["status"] == "READY_FOR_FINAL_COMMIT"
    assert payload["engineering_readiness"]["blocker"] is None
    assert payload["readiness"] == "04 ENGINEERING HANDOFF — READY FOR FINAL COMMIT"
    assert payload["accepted_commit"] == "TBD"
    assert payload["desktop_execution_authorized"] is False
    for phrase in ("ENGINEERING HANDOFF READY", "DESKTOP EXECUTION AUTHORIZED", "ARMOURY", "cleanly", "preflight"):
        assert phrase in payload["execution_authorization"]


def test_passing_refreshed_gates_are_read_only(tmp_path, passing_gates):
    before = {relative: (tmp_path / relative).read_bytes() for relative in h.GATE_PATHS}
    report = h.training_gate_diagnostics(tmp_path)
    assert report["status"] == "PASS" and report["blockers"] == []
    assert report["paths"] == list(h.GATE_PATHS)
    assert before == {relative: (tmp_path / relative).read_bytes() for relative in h.GATE_PATHS}


@pytest.mark.parametrize("gate", h.GATE_PATHS)
def test_missing_gate_fails_preflight_closed(tmp_path, preflight_environment, gate):
    (tmp_path / gate).unlink()
    with pytest.raises(ValueError, match="detector safety gates blocked"):
        h.preflight(tmp_path, "a" * 40)
    report = h.training_gate_diagnostics(tmp_path)
    assert report["status"] == "BLOCKED"
    assert any(gate in reason for reason in report["blockers"])


@pytest.mark.parametrize("gate,changes,reason", [
    (h.GEOMETRY_GATE, {"status": "FAIL"}, "geometry status"),
    (h.GEOMETRY_GATE, {"checked": 593}, "594/594"),
    (h.GEOMETRY_GATE, {"passed": 593}, "594/594"),
    (h.GEOMETRY_GATE, {"test_accessed": True}, "test_accessed"),
    (h.GEOMETRY_GATE, {"test_accessed": None}, "test_accessed"),
    (h.GEOMETRY_GATE, {"raw_immutability": {"status": "FAIL"}}, "raw immutability"),
    (h.GEOMETRY_GATE, {"raw_immutability": {}}, "raw immutability"),
    (h.GEOMETRY_GATE, {"source_identity": {}}, "source hashes"),
    (h.TEST_GATE, {"status": "FAIL"}, "ready.json status"),
    (h.TEST_GATE, {"implementation": {"old.py": "0" * 64}}, "implementation hash mismatch"),
    (h.TEST_GATE, {"implementation": {}}, "implementation hashes are missing"),
    (h.TEST_GATE, {"evidence_sha256": {}}, "evidence hashes are missing"),
])
def test_invalid_gate_fails_preflight_closed(tmp_path, preflight_environment, passing_gates, gate, changes, reason):
    payload = deepcopy(passing_gates[gate])
    payload.update(changes)
    before = deterministic_json_bytes(payload)
    (tmp_path / gate).write_bytes(before)
    report = h.training_gate_diagnostics(tmp_path)
    assert report["status"] == "BLOCKED"
    assert any(reason in blocker for blocker in report["blockers"])
    with pytest.raises(ValueError, match="detector safety gates blocked"):
        h.preflight(tmp_path, "a" * 40)
    assert (tmp_path / gate).read_bytes() == before


@pytest.mark.parametrize("gate,blob", [(gate, blob) for gate in h.GATE_PATHS for blob in (b"{", b"[]", b"null")])
def test_malformed_gate_fails_closed(tmp_path, passing_gates, gate, blob):
    (tmp_path / gate).write_bytes(blob)
    assert h.training_gate_diagnostics(tmp_path)["status"] == "BLOCKED"


@pytest.mark.parametrize("relative", ["src/detection/training/dataset.py", "synthetic_install/ultralytics/data/base.py",
                                    "outputs/validation/defect_detection/training_pipeline/before/synthetic_tests.txt"])
def test_source_or_evidence_change_fails_closed(tmp_path, preflight_environment, relative):
    (tmp_path / relative).write_bytes(b"changed after acceptance\n")
    with pytest.raises(ValueError, match="detector safety gates blocked"):
        h.preflight(tmp_path, "a" * 40)


@pytest.mark.parametrize("identity", [dict(branch=e.BRANCH, sha="b" * 40, source_status=""),
                                    dict(branch=e.BRANCH, sha="a" * 40, source_status=" M tracked.py")])
def test_preflight_requires_exact_clean_accepted_checkout(tmp_path, monkeypatch, identity):
    monkeypatch.setattr(e, "git_identity", lambda _: identity)
    with pytest.raises(ValueError, match="branch/commit/source cleanliness"):
        h.preflight(tmp_path, "a" * 40)


@pytest.mark.parametrize("status", [" M " + h.GEOMETRY_GATE + "\n", "?? " + h.TEST_GATE + "\n", " M README.md\n"])
def test_preflight_rejects_dirty_or_untracked_gate_checkout(tmp_path, monkeypatch, preflight_environment, status):
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=status))
    with pytest.raises(ValueError, match="clean accepted checkout"):
        h.preflight(tmp_path, "a" * 40)


@pytest.mark.parametrize("failure", ["merge-base", "ls-files"])
def test_preflight_rejects_nonancestor_or_uncommitted_evidence(tmp_path, monkeypatch, preflight_environment, failure):
    import subprocess
    def git(command, **kwargs):
        if failure in command:
            raise subprocess.CalledProcessError(1, command)
        return SimpleNamespace(returncode=0, stdout="")
    monkeypatch.setattr(subprocess, "run", git)
    with pytest.raises(subprocess.CalledProcessError):
        h.preflight(tmp_path, "a" * 40)


def test_generated_outputs_do_not_hide_tracked_receipt_changes(tmp_path, monkeypatch, preflight_environment):
    import subprocess
    status = f"?? {e.EVALUATION_ROOT}/result.json\n"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=status))
    assert h.preflight(tmp_path, "a" * 40)["status"] == "STATIC_PREFLIGHT_PASS"
    status += " M " + h.TEST_GATE + "\n"
    with pytest.raises(ValueError, match="clean accepted checkout"):
        h.preflight(tmp_path, "a" * 40)


def test_canonical_base_never_becomes_accepted_commit():
    with pytest.raises(ValueError, match="canonical base"):
        h.handoff(e.CANONICAL_BASE)
    assert h.handoff()["accepted_commit"] == "TBD"
    assert h.handoff("a" * 40)["desktop_execution_authorized"] is False


@pytest.mark.parametrize("mode", ["preflight", "desktop-check", "validate-benchmark", "smoke", "train-full", "compare", "bundle"])
@pytest.mark.parametrize("commit", ["TBD", e.CANONICAL_BASE])
def test_executable_modes_reject_placeholder_and_base_before_access(monkeypatch, mode, commit):
    monkeypatch.setattr(e, "git_identity", lambda *a: pytest.fail("unexpected checkout access"))
    monkeypatch.setattr(e, "require_desktop", lambda *a: pytest.fail("unexpected desktop access"))
    with pytest.raises(SystemExit) as exc:
        h.main(["--mode", mode, "--accepted-commit", commit, "--host", "ARMOURY"])
    assert exc.value.code == 1
