import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from aegisinspect_p19_eval.telemetry import PassiveJoinTelemetry


ROOT = Path(__file__).resolve().parents[4]
SUPERVISOR_PATH = ROOT / "tools/p19/readiness_supervisor.py"
SPEC = importlib.util.spec_from_file_location("readiness_supervisor", SUPERVISOR_PATH)
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)
BASE = "14c600e2220559dcf1df02b18bb88f56242704b1"


def command(script):
    return [sys.executable, "-c", script]


def run(tmp_path, script, deadline=2.0, caller="sandbox-ns", markers=()):
    return supervisor.run_supervised(
        command(script), cwd=tmp_path, output_directory=tmp_path / "evidence",
        log_path=tmp_path / "stdout.log", lifecycle_path=tmp_path / "lifecycle.json",
        deadline_seconds=deadline, shutdown_grace_seconds=0.5,
        caller_pid_namespace=caller, residual_markers=markers,
    )


def writer(status="PASS", delay=0.1, linger=0.0):
    return (
        "import json,pathlib,time; time.sleep(%r); p=pathlib.Path('evidence'); "
        "p.mkdir(); (p/'runtime_result.json').write_text(json.dumps({'status':%r})); "
        "print('terminal-log-line',flush=True); time.sleep(%r)" % (delay, status, linger)
    )


def test_yielded_execution_waits_for_actual_terminal_result(tmp_path):
    result = run(tmp_path, writer(delay=0.2))
    assert result["outcome"] == "PASS" and result["collector_terminal_result"]["status"] == "PASS"


def test_long_running_collector_remains_owned_until_result(tmp_path):
    started = time.monotonic(); result = run(tmp_path, writer(delay=0.25, linger=30))
    assert time.monotonic() - started >= 0.25 and result["trigger"] == "COLLECTOR_TERMINAL_RESULT"


@pytest.mark.parametrize("status", ["PASS", "BLOCKED"])
def test_terminal_states_remain_distinct(tmp_path, status):
    assert run(tmp_path, writer(status=status))["outcome"] == status


def test_missing_result_is_distinct(tmp_path):
    assert run(tmp_path, "print('no result')")["outcome"] == "MISSING_RESULT"


def test_deadline_interruption_and_signal_status_preserved(tmp_path):
    result = run(tmp_path, "import time; time.sleep(30)", deadline=0.2)
    assert result["outcome"] == "INTERRUPTED"
    assert result["trigger"] == "READINESS_DEADLINE_EXPIRED"
    assert result["cleanup"]["signals"] and result["launch_returncode"] is not None


def test_namespace_mismatch_is_recorded_not_treated_as_exit(tmp_path):
    result = run(tmp_path, writer(), caller="definitely-another-namespace")
    assert result["pid_namespace_mismatch"] is True and result["outcome"] == "PASS"


def test_residual_marker_ignores_supervisor_ancestry():
    marker = f"pytest-ancestor-{os.getpid()}"
    assert supervisor.marker_processes(
        [marker], excluded_pids=supervisor.ancestor_pids(),
    ) == []


def test_shell_child_and_native_grandchild_are_reaped(tmp_path):
    script = (
        "import json,pathlib,subprocess,time; p=pathlib.Path('evidence'); p.mkdir(); "
        "subprocess.Popen(['sh','-c','sleep 30']); "
        "(p/'runtime_result.json').write_text(json.dumps({'status':'PASS'})); time.sleep(30)"
    )
    result = run(tmp_path, script)
    assert result["host_group_residual_count"] == 0
    assert result["cleanup"]["final_members"] == []
    assert result["adopted_children_reaped"]


def test_sigterm_escalation_is_visible(tmp_path):
    script = "import signal,time; signal.signal(signal.SIGINT,lambda *_:None); time.sleep(30)"
    # Leave enough time for the child interpreter to install its handler even
    # when this test runs under CTest load.
    result = run(tmp_path, script, deadline=1.0)
    assert result["cleanup"]["signals"][:2] == ["SIGINT", "SIGTERM"]


def test_log_is_closed_and_hashed_before_lifecycle_record(tmp_path):
    result = run(tmp_path, writer())
    assert result["log_closed_before_lifecycle_record"] is True
    assert (tmp_path / "stdout.log").read_text().strip() == "terminal-log-line"
    assert json.loads((tmp_path / "lifecycle.json").read_text())["log_sha256_after_close"]


def test_exactly_one_readiness_deadline_owner():
    source = SUPERVISOR_PATH.read_text()
    assert source.count("READINESS_DEADLINE_SECONDS = 120.0") == 1
    assert "subprocess.run" not in source and " timeout " not in source


def test_passive_telemetry_observes_without_eligibility_decision():
    telemetry = PassiveJoinTelemetry(history_limit=2)
    telemetry.record_seen("rgb")
    telemetry.record_join(10, {name: name == "rgb" for name in telemetry.seen}, False)
    snapshot = telemetry.snapshot("INTERRUPTED")
    assert snapshot["stream_seen_counts"]["rgb"] == 1
    assert snapshot["receipt_count"] == 0 and snapshot["eligibility_logic_modified"] is False


def test_twenty_pair_and_alignment_rules_unchanged():
    collector = (ROOT / "ros2_ws/src/aegisinspect_p19_eval/scripts/readiness_node.py").read_text()
    contracts = (ROOT / "ros2_ws/src/aegisinspect_p19_eval/aegisinspect_p19_eval/contracts.py").read_text()
    assert "len(self.receipts) == 20" in collector
    assert 'ALIGNMENT_RULE = "first-exact-positive-startup-world-map-base-pair-v1"' in contracts


def test_frozen_target_and_scene_paths_equal_pre_harness_commit():
    protected = [
        "ros2_ws/src/aegisinspect_p19_eval/models/p19_defect_target_001/model.sdf",
        "ros2_ws/src/aegisinspect_p19_eval/models/aegis_drone_p19_eval/model.sdf",
        "ros2_ws/src/aegisinspect_p19_eval/worlds/p19_correspondence_readiness.sdf",
    ]
    for relative in protected:
        expected = subprocess.check_output(["git", "show", f"{BASE}:{relative}"], cwd=ROOT)
        assert (ROOT / relative).read_bytes() == expected


def test_authorized_evidence_interfaces_preserve_scientific_rules():
    contracts = (ROOT / "ros2_ws/src/aegisinspect_p19_eval/aegisinspect_p19_eval/contracts.py").read_text()
    certificate = (ROOT / "ros2_ws/src/aegisinspect_p19_eval/aegisinspect_p19_eval/batch_certificate.py").read_text()
    assert 'CERTIFICATE_SCHEMA = "aegisinspect.p19.sensor_batch_certificate.v1"' in certificate
    assert 'ALIGNMENT_RULE = "first-exact-positive-startup-world-map-base-pair-v1"' in contracts
    assert "if len(receipts) < 20:" in contracts


def test_manifest_hash_and_core_underlay_remain_frozen():
    import hashlib
    manifest = ROOT / "outputs/evidence/p19_3d_correspondence_no_start_readiness/manifest/PRE_START_MANIFEST.json"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == "0291d6f4cd8fce5c6557a45d62750f3bb2246b64035afcd41509554dad3c0c50"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd="/mnt/c/Dev/aegisinspect-p18-integration", text=True).strip() == "7b9ff556956c9c8995262515f53ff5382ffacf1b"
