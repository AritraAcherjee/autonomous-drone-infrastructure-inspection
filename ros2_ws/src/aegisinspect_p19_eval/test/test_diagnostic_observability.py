import importlib.util
import json
import os
from pathlib import Path

import pytest

from aegisinspect_p19_eval.diagnostic_observability import (
    CALLBACK_NAMES, CollectorDiagnosticState, DIAGNOSTIC_SCHEMA,
    diagnostic_bytes, parse_diagnostic_artifact,
)


ROOT = Path(__file__).resolve().parents[4]
PKG = Path(__file__).resolve().parents[1]
PROCESS_PATH = ROOT / "tools/p19/process_observability.py"
SPEC = importlib.util.spec_from_file_location("process_observability_test", PROCESS_PATH)
process_observability = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(process_observability)


def collector(**changes):
    state = CollectorDiagnosticState("run-1")
    values = dict(
        reason="TEST", terminal_classification="MISSING",
        alignment_available=False, scene_available=False,
        camera_info_available=False, calibration_available=False,
        rgb_hash_match_available=False, depth_hash_match_available=False,
        truth_available=False, certificate_available=False,
        telemetry_available=False, persisted_receipt_count=0,
        current_valid_streak=0, max_valid_streak=0,
    )
    values.update(changes)
    return state, state.snapshot(**values)


def test_diagnostic_schema_is_dedicated_and_accepted_schemas_unchanged():
    assert DIAGNOSTIC_SCHEMA == "aegisinspect.p19.runtime_diagnostic_observability.v1"
    native = (PKG / "src/sensor_batch_certificate.cpp").read_text()
    assert "aegisinspect.p19.sensor_batch_certificate.v1" in native
    assert "aegisinspect.p19.sensor_batch_telemetry.v1" in native
    schema = json.loads((PKG / "config/runtime_diagnostic_observability.v1.schema.json").read_text())
    assert schema["$id"] == DIAGNOSTIC_SCHEMA and len(schema["oneOf"]) == 3


def test_no_callbacks_is_bounded_and_reports_all_pending_conditions():
    state, item = collector()
    assert item["callback_counts"] == {name: 0 for name in CALLBACK_NAMES}
    assert item["current_pending_predicate"] == "MULTIPLE_PREREQUISITES_PENDING"
    assert "WAITING_FOR_CERTIFICATE" in item["pending_predicates"]
    assert item["readiness_decision_modified"] is False
    assert parse_diagnostic_artifact(diagnostic_bytes(item)) == item


def test_alignment_only_and_scene_absent_are_distinguishable():
    state, _ = collector()
    state.callback("startup_alignment")
    item = state.snapshot(
        reason="INTERRUPTED", terminal_classification="INTERRUPTED",
        alignment_available=True, scene_available=False,
        camera_info_available=False, calibration_available=False,
        rgb_hash_match_available=False, depth_hash_match_available=False,
        truth_available=False, certificate_available=False,
        telemetry_available=False, persisted_receipt_count=0,
        current_valid_streak=0, max_valid_streak=0)
    assert item["callback_counts"]["startup_alignment"] == 1
    assert "WAITING_FOR_STARTUP_ALIGNMENT" not in item["pending_predicates"]
    assert "WAITING_FOR_SCENE_IDENTITY" in item["pending_predicates"]


@pytest.mark.parametrize("missing,expected", [
    ("certificate_available", "WAITING_FOR_CERTIFICATE"),
    ("rgb_hash_match_available", "WAITING_FOR_RGB_BINDING"),
    ("depth_hash_match_available", "WAITING_FOR_DEPTH_BINDING"),
    ("camera_info_available", "WAITING_FOR_CAMERA_INFO"),
])
def test_each_missing_collector_prerequisite_is_visible(missing, expected):
    kwargs = dict(alignment_available=True, scene_available=True,
                  camera_info_available=True, calibration_available=True,
                  rgb_hash_match_available=True, depth_hash_match_available=True,
                  truth_available=True, certificate_available=True,
                  telemetry_available=True, persisted_receipt_count=20,
                  current_valid_streak=20, max_valid_streak=20)
    kwargs[missing] = False
    _, item = collector(**kwargs)
    assert item["current_pending_predicate"] == expected


def test_complete_prerequisites_below_twenty_and_at_twenty():
    common = dict(alignment_available=True, scene_available=True,
                  camera_info_available=True, calibration_available=True,
                  rgb_hash_match_available=True, depth_hash_match_available=True,
                  truth_available=True, certificate_available=True,
                  telemetry_available=True)
    _, below = collector(**common, persisted_receipt_count=19,
                         current_valid_streak=19, max_valid_streak=19)
    _, complete = collector(**common, persisted_receipt_count=20,
                            current_valid_streak=20, max_valid_streak=20)
    assert below["current_pending_predicate"] == "WAITING_FOR_QUALIFYING_RECEIPT"
    assert complete["current_pending_predicate"] == "NO_PREREQUISITE_PENDING"


def test_certificate_acceptance_and_rejection_are_separate_bounded_counters():
    state, _ = collector()
    state.certificate_accepted_count = 2
    state.certificate_rejected_count = 1
    item = state.snapshot(
        reason="TEST", terminal_classification="MISSING",
        alignment_available=False, scene_available=False,
        camera_info_available=False, calibration_available=False,
        rgb_hash_match_available=False, depth_hash_match_available=False,
        truth_available=False, certificate_available=True,
        telemetry_available=False, persisted_receipt_count=0,
        current_valid_streak=0, max_valid_streak=0)
    assert item["certificate_accepted_count"] == 2
    assert item["certificate_rejected_count"] == 1


def test_interruption_snapshot_does_not_change_terminal_classification():
    state, item = collector(reason="COLLECTOR_FINALIZATION",
                            terminal_classification="INTERRUPTED")
    assert item["terminal_classification_unchanged"] == "INTERRUPTED"
    assert item["readiness_decision_modified"] is False
    source = (PKG / "scripts/readiness_node.py").read_text()
    assert 'write_diagnostic_snapshot("COLLECTOR_FINALIZATION")' in source
    assert "READINESS_DEADLINE_SECONDS = 120.0" in (
        ROOT / "tools/p19/readiness_supervisor.py").read_text()


def _fake_process(root: Path, pid: int, ppid: int, pgid: int,
                  mappings: list[str]) -> None:
    item = root / str(pid); item.mkdir(parents=True)
    fields = ["S", str(ppid), str(pgid), str(pgid)] + ["0"] * 15 + [str(pid * 10)]
    (item / "stat").write_text(f"{pid} (test) " + " ".join(fields))
    (item / "cmdline").write_bytes(f"test-{pid}\0--child\0".encode())
    (item / "exe").symlink_to("/usr/bin/test")
    (item / "maps").write_text("".join(
        f"00400000-00401000 r-xp 00000000 00:00 0 {path}\n" for path in mappings))


def test_process_mapping_expected_and_wrapped_child_discovered(tmp_path):
    library = tmp_path / "libexpected.so"; library.write_bytes(b"accepted")
    digest = __import__("hashlib").sha256(library.read_bytes()).hexdigest()
    proc = tmp_path / "proc"; proc.mkdir()
    _fake_process(proc, 10, 1, 10, [])
    _fake_process(proc, 11, 10, 10, [str(library)])
    observer = process_observability.ProcessMappingObserver(
        10, {str(library): digest}, proc_root=proc)
    observer.sample(123)
    snapshot = observer.snapshot()
    assert [item["pid"] for item in snapshot["processes"]] == [10, 11]
    child = snapshot["processes"][1]
    assert child["required_mappings"][0]["status"] == "EXPECTED_MAPPING_FOUND"
    assert child["required_mappings"][0]["hash_matches"] is True
    assert child["mapped_relevant_libraries"] == []


def test_expected_mapping_absent_and_matcher_mismatch(tmp_path):
    proc = tmp_path / "proc"; proc.mkdir()
    expected = tmp_path / "expected/libsame.so"
    _fake_process(proc, 20, 1, 20, ["/different/libs/libsame.so"])
    observer = process_observability.ProcessMappingObserver(
        20, {str(expected): "0" * 64}, proc_root=proc)
    observer.sample()
    assert observer.snapshot()["processes"][0]["required_mappings"][0]["status"] == "MATCHER_MISMATCH"
    _fake_process(proc, 21, 20, 20, ["/different/libs/unrelated.so"])
    observer.sample()
    records = {item["pid"]: item for item in observer.snapshot()["processes"]}
    assert records[21]["required_mappings"][0]["status"] == "EXPECTED_PATH_ABSENT"


def test_maps_permission_failure_remains_distinct(tmp_path, monkeypatch):
    proc = tmp_path / "proc"; proc.mkdir(); _fake_process(proc, 30, 1, 30, [])
    original = Path.read_text
    def denied(self, *args, **kwargs):
        if self.name == "maps":
            raise PermissionError("denied")
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", denied)
    observer = process_observability.ProcessMappingObserver(30, {}, proc_root=proc)
    observer.sample()
    item = observer.snapshot()["processes"][0]
    assert item["maps_lookup_status"] == "PROC_MAPS_UNREADABLE"
    assert "PermissionError" in item["maps_read_error"]


def test_process_disappears_and_multiple_candidates_are_bounded(tmp_path, monkeypatch):
    proc = tmp_path / "proc"; proc.mkdir(); _fake_process(proc, 40, 1, 40, [])
    original = process_observability._process
    def disappears(root, pid):
        item = original(root, pid)
        (root / str(pid) / "maps").unlink()
        return item
    monkeypatch.setattr(process_observability, "_process", disappears)
    observer = process_observability.ProcessMappingObserver(40, {}, proc_root=proc)
    observer.sample()
    assert observer.snapshot()["processes"][0]["maps_lookup_status"] == "PROCESS_EXITED"
    assert observer.snapshot()["process_record_limit"] == 64


def test_process_not_discovered_is_distinct(tmp_path):
    proc = tmp_path / "proc"; proc.mkdir()
    observer = process_observability.ProcessMappingObserver(99, {}, proc_root=proc)
    observer.sample()
    assert observer.snapshot()["discovery_status"] == "PROCESS_NOT_DISCOVERED"


def test_native_progress_counters_are_at_existing_hooks_only():
    source = (PKG / "src/sensor_batch_certificate.cpp").read_text()
    assert source.count("++diagnostic.batchOpen") == 1
    assert source.count("++diagnostic.batchClose") == 1
    assert source.count("++rgbGenerationCount") == 1
    assert source.count("++depthGenerationCount") == 1
    assert source.count("++truthGenerationCount") == 1
    for reason in ("MISSING_RGB", "MISSING_DEPTH", "MISSING_TRUTH",
                   "INCOMPLETE_BATCH", "IDENTITY_MISMATCH",
                   "CALIBRATION_UNAVAILABLE"):
        assert f'Reject("{reason}"' in source
    assert "telemetryPublisher.Publish" in source
    assert "publisher.Publish" in source
    assert "std::atexit(WriteDiagnosticSnapshot)" in source
    assert "Diagnostic diagnostic;" in source and "Telemetry telemetry;" in source
    assert "new Sensor" not in source and "Capture(" not in source


def test_no_new_scientific_publication_or_schema_change():
    native = (PKG / "src/sensor_batch_certificate.cpp").read_text()
    assert native.count("Advertise<gz::msgs::StringMsg>") == 2
    assert "/runtime_diagnostic" not in native
    patch = (PKG / "gazebo_patch/gz-sim-10.5.0-sensor-batch.patch").read_text()
    assert patch.count("p19_batch_open") == 1 and patch.count("p19_batch_close") == 1
    assert "+      this->sensorManager.RunOnce" not in patch
