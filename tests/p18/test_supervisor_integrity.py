"""Exercise pre-capture Git ordering and the unchanged accepted liveness guard."""
import ast
import json
import os
from pathlib import Path
import time
import traceback
from types import SimpleNamespace

import pytest


REPO = Path(__file__).resolve().parents[2]
SUPERVISOR = REPO / "scripts/p18/supervisor.py"
ACCEPTED_GUARD = Path("/mnt/c/Dev/aegisinspect-07-vio/outputs/evidence/07_lidar_icp_stationary_gate/gate.py")
EXPECTED_HEAD = "e5fbfeef65a2851333bb2de0a222dc1df82163a6"


def accepted_step(spin_once):
    """Execute the accepted production method; do not duplicate its threshold."""
    tree = ast.parse(ACCEPTED_GUARD.read_text())
    gate = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Gate")
    step = next(node for node in gate.body if isinstance(node, ast.FunctionDef) and node.name == "step")
    scope = {"time": time, "rclpy": SimpleNamespace(spin_once=spin_once)}
    exec(compile(ast.Module(body=[step], type_ignores=[]), str(ACCEPTED_GUARD), "exec"), scope)
    return scope["step"]


def guard_subject():
    now = time.monotonic()
    node = SimpleNamespace(
        next_ps=float("inf"), next_graph=float("inf"), phase="pre_start",
        sensor_enforced=True, shutdown_started=False,
        last={"clock": now, "lidar": now}, errors=[],
    )
    node.fail = node.errors.append
    return node


def load_entrypoints(tmp_path, git_status="", git_head=EXPECTED_HEAD, delay=0):
    events = []
    capture = tmp_path / "capture"
    capture.mkdir()
    (capture / "assets.json").write_text(json.dumps({"p18_head": EXPECTED_HEAD}))
    gate = tmp_path / "outputs/evidence/stop_b_p18_integration_base/base_gate_result.json"
    gate.parent.mkdir(parents=True)
    gate.write_text(json.dumps({"classification": "P18 INTEGRATION BASE — PASS"}))

    def save(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def check_output(argv, **kwargs):
        assert "ros_init" not in events
        assert "capture_constructed" not in events
        events.append(tuple(argv))
        if argv == ["git", "status", "--short"]:
            time.sleep(delay)
            events.append("slow_integrity_finished")
            return git_status
        assert argv == ["git", "rev-parse", "HEAD"]
        return git_head + "\n"

    def spin_once(node, **kwargs):
        events.append("callbacks_serviced")
        node.last.update(clock=time.monotonic(), lidar=time.monotonic())

    step = accepted_step(spin_once)

    class Capture:
        def __init__(self):
            events.append("capture_constructed")
            self.subject = guard_subject()
            self.results = {"runtime_pass": False, "RELEVANT_RESIDUAL_PROCESS_COUNT": 0}

        def run(self):
            events.append("live_monitoring")
            step(self.subject)
            assert not self.subject.errors
            self.results["runtime_pass"] = True

        def shutdown(self):
            events.append("shutdown")

        def destroy_node(self):
            pass

    scope = {
        "REPO": tmp_path, "ROOT": capture, "PACKAGE": tmp_path,
        "json": json, "os": os, "traceback": traceback,
        "subprocess": SimpleNamespace(check_output=check_output),
        "save": save, "utc": lambda: "test-time",
        "inventory": lambda: {"count": 0},
        "get_package_prefix": lambda name: "/test/" + name,
        "accepted": SimpleNamespace(rclpy=SimpleNamespace(
            init=lambda **kwargs: events.append("ros_init"), try_shutdown=lambda: None)),
        "P18Runtime": Capture,
    }
    tree = ast.parse(SUPERVISOR.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name in {"verify_integrity_before_capture", "main"}]
    assert len(functions) == 2
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SUPERVISOR), "exec"), scope)
    return scope, events, capture


def test_git_work_is_absent_from_live_supervisor_methods():
    tree = ast.parse(SUPERVISOR.read_text())
    runtime = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "P18Runtime")
    assert not any(isinstance(node, ast.Name) and node.id == "subprocess" for node in ast.walk(runtime))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    calls = {ast.unparse(node.func): node.lineno for node in ast.walk(main) if isinstance(node, ast.Call)}
    assert calls["verify_integrity_before_capture"] < calls["accepted.rclpy.init"] < calls["P18Runtime"]


def test_slow_integrity_over_two_seconds_precedes_capture_without_false_lidar_failure(tmp_path):
    scope, events, capture = load_entrypoints(tmp_path, delay=2.1)
    start = time.monotonic()
    assert scope["main"]() == 0
    assert time.monotonic() - start >= 2.1
    assert events.index("slow_integrity_finished") < events.index("ros_init")
    assert events.index("ros_init") < events.index("capture_constructed") < events.index("callbacks_serviced")
    assert not (capture / "exception.txt").exists()


@pytest.mark.parametrize("status,head,error", [
    (" M source.py\n", EXPECTED_HEAD, "P18_WORKTREE_NOT_CLEAN"),
    ("", "0" * 40, "P18_HEAD_MISMATCH"),
])
def test_invalid_integrity_fails_before_ros_initialization(tmp_path, status, head, error):
    scope, events, capture = load_entrypoints(tmp_path, git_status=status, git_head=head)
    with pytest.raises(AssertionError, match=error):
        scope["main"]()
    assert "ros_init" not in events and "capture_constructed" not in events
    assert not (capture / "runtime_invocation.json").exists()


@pytest.mark.parametrize("stream", ["clock", "lidar"])
def test_accepted_guard_still_rejects_actual_staleness_over_two_seconds(stream):
    node = guard_subject()
    node.last[stream] = time.monotonic() - 2.01
    with pytest.raises(RuntimeError, match="ACTIVE_STREAM_LOST_" + stream):
        accepted_step(lambda *args, **kwargs: None)(node)
