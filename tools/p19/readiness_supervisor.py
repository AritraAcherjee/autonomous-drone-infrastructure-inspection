#!/usr/bin/env python3
"""Host-visible owner for one bounded P19 no-START readiness launch."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any, Sequence

try:
    from process_observability import ProcessMappingObserver
except ModuleNotFoundError:
    _observer_path = Path(__file__).with_name("process_observability.py")
    _observer_spec = importlib.util.spec_from_file_location(
        "p19_process_observability", _observer_path)
    if _observer_spec is None or _observer_spec.loader is None:
        raise
    _observer_module = importlib.util.module_from_spec(_observer_spec)
    _observer_spec.loader.exec_module(_observer_module)
    ProcessMappingObserver = _observer_module.ProcessMappingObserver


READINESS_DEADLINE_SECONDS = 120.0
POLL_SECONDS = 0.1
SHUTDOWN_GRACE_SECONDS = 5.0


def pid_namespace() -> str:
    return os.readlink("/proc/self/ns/pid")


def enable_child_subreaper() -> None:
    if sys.platform != "linux":
        raise RuntimeError("host-visible readiness supervisor requires Linux")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def process_record(pid: int) -> dict[str, Any] | None:
    path = Path(f"/proc/{pid}")
    try:
        raw = (path / "stat").read_text(encoding="utf-8")
        close = raw.rfind(")")
        fields = raw[close + 2:].split()
        command = (path / "cmdline").read_bytes().replace(b"\0", b" ").decode(
            errors="replace").strip()
        return {
            "pid": pid,
            "ppid": int(fields[1]),
            "pgid": int(fields[2]),
            "sid": int(fields[3]),
            "state": fields[0],
            "command_line": command,
        }
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError):
        return None


def process_group_members(pgid: int, *, include_zombies: bool = True) -> list[dict[str, Any]]:
    members = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            record = process_record(int(entry.name))
            if (record is not None and record["pgid"] == pgid and
                    (include_zombies or record["state"] != "Z")):
                members.append(record)
    return sorted(members, key=lambda item: item["pid"])


def ancestor_pids(pid: int | None = None) -> set[int]:
    ancestors: set[int] = set()
    current = os.getpid() if pid is None else pid
    while current > 0 and current not in ancestors:
        ancestors.add(current)
        record = process_record(current)
        if record is None:
            break
        current = record["ppid"]
    return ancestors


def marker_processes(
    markers: Sequence[str], *, excluded_pids: Sequence[int] = (),
) -> list[dict[str, Any]]:
    if not markers:
        return []
    matches = []
    excluded = set(excluded_pids)
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit() or int(entry.name) in excluded:
            continue
        record = process_record(int(entry.name))
        if record is not None and any(marker in record["command_line"] for marker in markers):
            matches.append(record)
    return sorted(matches, key=lambda item: item["pid"])


def wait_until_empty(pgid: int, seconds: float) -> list[dict[str, Any]]:
    deadline = time.monotonic() + seconds
    while True:
        members = process_group_members(pgid, include_zombies=False)
        if not members or time.monotonic() >= deadline:
            return members
        time.sleep(min(POLL_SECONDS, max(0.0, deadline - time.monotonic())))


def terminate_process_group(pgid: int, grace_seconds: float) -> dict[str, Any]:
    record: dict[str, Any] = {"pgid": pgid, "signals": [], "kill_required": False}
    survivors = process_group_members(pgid, include_zombies=False)
    record["initial_members"] = survivors
    for sig, label in ((signal.SIGINT, "SIGINT"), (signal.SIGTERM, "SIGTERM")):
        if not survivors:
            break
        try:
            os.killpg(pgid, sig)
            record["signals"].append(label)
        except ProcessLookupError:
            survivors = []
            break
        survivors = wait_until_empty(pgid, grace_seconds)
    if survivors:
        record["kill_required"] = True
        os.killpg(pgid, signal.SIGKILL)
        record["signals"].append("SIGKILL")
        survivors = wait_until_empty(pgid, grace_seconds)
    record["final_members"] = survivors
    return record


def reap_adopted_children(seconds: float) -> list[dict[str, int]]:
    reaped = []
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        found = False
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                pid = 0
            if pid <= 0:
                break
            found = True
            reaped.append({"pid": pid, "wait_status": status})
        if not found:
            time.sleep(POLL_SECONDS)
    return reaped


def canonical_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8")


def read_terminal_result(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if value.get("status") in {"PASS", "BLOCKED"} else None


def run_supervised(
    command: Sequence[str], *, cwd: Path, output_directory: Path, log_path: Path,
    lifecycle_path: Path, deadline_seconds: float = READINESS_DEADLINE_SECONDS,
    shutdown_grace_seconds: float = SHUTDOWN_GRACE_SECONDS,
    caller_pid_namespace: str = "UNKNOWN", residual_markers: Sequence[str] = (),
    environment: dict[str, str] | None = None,
    process_diagnostic_path: Path | None = None,
    required_libraries: dict[str, str] | None = None,
) -> dict[str, Any]:
    if deadline_seconds <= 0:
        raise ValueError("readiness deadline must be positive")
    if output_directory.exists():
        raise FileExistsError(f"output directory already exists: {output_directory}")
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lifecycle_path.parent.mkdir(parents=True, exist_ok=True)
    host_namespace = pid_namespace()
    enable_child_subreaper()
    started_wall_ns = time.time_ns()
    started_monotonic = time.monotonic()
    terminal_result = None
    trigger = None
    launch_returncode = None
    cleanup: dict[str, Any] = {}
    process: subprocess.Popen[bytes] | None = None
    interrupted = False
    process_observer: ProcessMappingObserver | None = None
    next_process_sample = started_monotonic
    if process_diagnostic_path is None:
        process_diagnostic_path = output_directory / "host_process_mapping_diagnostic.json"

    with log_path.open("xb", buffering=0) as log_file:
        process = subprocess.Popen(
            list(command), cwd=cwd, env=environment, stdout=log_file,
            stderr=subprocess.STDOUT, start_new_session=True,
        )
        launch_pgid = os.getpgid(process.pid)
        process_observer = ProcessMappingObserver(
            launch_pgid, required_libraries or {})
        try:
            while True:
                now = time.monotonic()
                if process_observer is not None and now >= next_process_sample:
                    process_observer.sample()
                    next_process_sample = now + 0.5
                terminal_result = read_terminal_result(output_directory / "runtime_result.json")
                if terminal_result is not None:
                    trigger = "COLLECTOR_TERMINAL_RESULT"
                    break
                launch_returncode = process.poll()
                if launch_returncode is not None:
                    trigger = "LAUNCH_EXITED_WITHOUT_TERMINAL_RESULT"
                    break
                if time.monotonic() - started_monotonic >= deadline_seconds:
                    trigger = "READINESS_DEADLINE_EXPIRED"
                    break
                time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:
            interrupted = True
            trigger = "SUPERVISOR_INTERRUPTED"

        if terminal_result is not None and process.poll() is None:
            try:
                launch_returncode = process.wait(timeout=shutdown_grace_seconds)
            except subprocess.TimeoutExpired:
                pass
        cleanup = terminate_process_group(launch_pgid, shutdown_grace_seconds)
        try:
            launch_returncode = process.wait(timeout=shutdown_grace_seconds)
        except subprocess.TimeoutExpired:
            launch_returncode = process.poll()
        adopted_children_reaped = reap_adopted_children(shutdown_grace_seconds)
        log_file.flush()
        os.fsync(log_file.fileno())

    residual_group = process_group_members(launch_pgid)
    # The calling shell and execution harness include command arguments in
    # their own command lines. Exclude the supervisor ancestry so a residual
    # marker cannot mistake its still-active owner for a leaked descendant.
    marker_exclusions = ancestor_pids()
    residual_marker_matches = marker_processes(
        residual_markers, excluded_pids=marker_exclusions,
    )
    if terminal_result is not None:
        outcome = terminal_result["status"]
    elif interrupted or trigger == "READINESS_DEADLINE_EXPIRED":
        outcome = "INTERRUPTED"
    else:
        outcome = "MISSING_RESULT"
    lifecycle = {
        "schema": "aegisinspect.p19.readiness-supervisor.v1",
        "outcome": outcome,
        "trigger": trigger,
        "deadline_owner": "readiness_supervisor",
        "deadline_seconds": deadline_seconds,
        "command": list(command),
        "cwd": str(cwd),
        "supervisor_pid": os.getpid(),
        "launch_pid": process.pid if process is not None else None,
        "launch_pgid": launch_pgid,
        "launch_returncode": launch_returncode,
        "collector_terminal_result": terminal_result,
        "caller_pid_namespace": caller_pid_namespace,
        "host_pid_namespace": host_namespace,
        "pid_namespace_mismatch": caller_pid_namespace not in {"UNKNOWN", host_namespace},
        "cleanup": cleanup,
        "adopted_children_reaped": adopted_children_reaped,
        "host_group_residual_count": len(residual_group),
        "host_marker_residual_count": len(residual_marker_matches),
        "host_residual_processes": residual_group + residual_marker_matches,
        "log_path": str(log_path),
        "log_sha256_after_close": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        "log_closed_before_lifecycle_record": True,
        "started_wall_ns": started_wall_ns,
        "finished_wall_ns": time.time_ns(),
    }
    if process_observer is not None:
        canonical_write(process_diagnostic_path, process_observer.snapshot())
        lifecycle["process_diagnostic_path"] = str(process_diagnostic_path)
        lifecycle["process_diagnostic_written_after_active_sampling"] = True
    canonical_write(lifecycle_path, lifecycle)
    return lifecycle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--log-path", type=Path, required=True)
    parser.add_argument("--lifecycle-path", type=Path, required=True)
    parser.add_argument("--caller-pid-namespace", default="UNKNOWN")
    parser.add_argument("--residual-marker", action="append", default=[])
    parser.add_argument("--deadline-seconds", type=float, default=READINESS_DEADLINE_SECONDS)
    parser.add_argument("--process-diagnostic-path", type=Path)
    parser.add_argument("--required-library", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a launch command is required after --")
    required_libraries = {}
    for value in args.required_library:
        path, separator, digest = value.rpartition("=")
        if (not separator or not path.startswith("/") or len(digest) != 64 or
                any(character not in "0123456789abcdef" for character in digest)):
            parser.error("--required-library must be ABSOLUTE_PATH=LOWERCASE_SHA256")
        required_libraries[path] = digest
    lifecycle = run_supervised(
        command, cwd=args.cwd.resolve(), output_directory=args.output_directory.resolve(),
        log_path=args.log_path.resolve(), lifecycle_path=args.lifecycle_path.resolve(),
        deadline_seconds=args.deadline_seconds,
        caller_pid_namespace=args.caller_pid_namespace,
        residual_markers=args.residual_marker, environment=dict(os.environ),
        process_diagnostic_path=(args.process_diagnostic_path.resolve()
                                 if args.process_diagnostic_path else None),
        required_libraries=required_libraries,
    )
    print(json.dumps(lifecycle, sort_keys=True))
    if lifecycle["host_group_residual_count"] or lifecycle["host_marker_residual_count"]:
        return 5
    return {"PASS": 0, "BLOCKED": 2, "INTERRUPTED": 3, "MISSING_RESULT": 4}[
        lifecycle["outcome"]]


if __name__ == "__main__":
    sys.exit(main())
