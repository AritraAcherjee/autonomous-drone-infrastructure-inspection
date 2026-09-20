"""Bounded passive /proc observations for supervisor-owned descendants."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import time
from typing import Any, Mapping


SCHEMA = "aegisinspect.p19.runtime_diagnostic_observability.v1"
MAX_PROCESSES = 64
RELEVANT_LIBRARY_PREFIXES = (
    "libp19_sensor_batch_certificate.so", "libp19_update_attestor.so",
    "libp19_batch_scene_configurator.so", "libgz-sim-sensors-system.so",
    "libgz-sensors-camera.so", "libgz-sensors-rgbd_camera.so",
    "libgz-sensors-segmentation_camera.so",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _process(proc_root: Path, pid: int) -> dict[str, Any]:
    root = proc_root / str(pid)
    try:
        raw = (root / "stat").read_text(encoding="utf-8")
        close = raw.rfind(")")
        fields = raw[close + 2:].split()
        return {
            "pid": pid, "ppid": int(fields[1]), "pgid": int(fields[2]),
            "sid": int(fields[3]), "state": fields[0],
            "start_ticks": int(fields[19]),
            "executable": os.readlink(root / "exe"),
            "command_line": (root / "cmdline").read_bytes().replace(
                b"\0", b" ").decode(errors="replace").strip(),
        }
    except FileNotFoundError:
        return {"pid": pid, "lookup_status": "PROCESS_EXITED"}
    except PermissionError as exc:
        return {"pid": pid, "lookup_status": "PROC_IDENTITY_UNREADABLE",
                "read_error": f"{type(exc).__name__}: {exc}"}
    except (OSError, ValueError) as exc:
        return {"pid": pid, "lookup_status": "PROC_IDENTITY_UNREADABLE",
                "read_error": f"{type(exc).__name__}: {exc}"}


class ProcessMappingObserver:
    """Keep one bounded, latest record per process without changing its lifetime."""

    def __init__(self, pgid: int, required: Mapping[str, str], *,
                 proc_root: Path = Path("/proc")) -> None:
        self.pgid = pgid
        self.required = dict(required)
        self.proc_root = proc_root
        self.records: dict[int, dict[str, Any]] = {}
        self.sample_count = 0
        self.hash_cache: dict[str, tuple[str | None, str | None]] = {}

    def sample(self, wall_time_ns: int | None = None) -> None:
        self.sample_count += 1
        observed_at = time.time_ns() if wall_time_ns is None else wall_time_ns
        try:
            entries = sorted((e for e in self.proc_root.iterdir() if e.name.isdigit()),
                             key=lambda value: int(value.name))
        except (FileNotFoundError, PermissionError, OSError):
            return
        candidates = []
        for entry in entries:
            item = _process(self.proc_root, int(entry.name))
            if item.get("pgid") == self.pgid:
                candidates.append(item)
        for item in candidates[:MAX_PROCESSES]:
            pid = item["pid"]
            item["maps_lookup_wall_time_ns"] = observed_at
            maps_path = self.proc_root / str(pid) / "maps"
            try:
                text = maps_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                item["maps_lookup_status"] = "PROCESS_EXITED"
                self.records[pid] = item
                continue
            except (PermissionError, OSError) as exc:
                item["maps_lookup_status"] = "PROC_MAPS_UNREADABLE"
                item["maps_read_error"] = f"{type(exc).__name__}: {exc}"
                self.records[pid] = item
                continue
            mapped = sorted({line.split(maxsplit=5)[-1].removesuffix(" (deleted)")
                             for line in text.splitlines()
                             if len(line.split(maxsplit=5)) == 6 and
                             line.split(maxsplit=5)[-1].startswith("/")})
            item["maps_lookup_status"] = "READABLE"
            item["mapped_relevant_libraries"] = []
            for path in mapped:
                if Path(path).name.startswith(RELEVANT_LIBRARY_PREFIXES):
                    if path not in self.hash_cache:
                        try:
                            self.hash_cache[path] = (_sha256(Path(path)), None)
                        except OSError as exc:
                            self.hash_cache[path] = (
                                None, f"{type(exc).__name__}: {exc}")
                    digest, error = self.hash_cache[path]
                    item["mapped_relevant_libraries"].append({
                        "path": path, "sha256": digest, "hash_read_error": error})
            item["required_mappings"] = []
            for expected, expected_hash in sorted(self.required.items()):
                exact = expected in mapped
                same_name = [path for path in mapped
                             if Path(path).name == Path(expected).name]
                status = "EXPECTED_MAPPING_FOUND" if exact else (
                    "MATCHER_MISMATCH" if same_name else "EXPECTED_PATH_ABSENT")
                record = {"expected_path": expected, "expected_sha256": expected_hash,
                          "status": status, "mapped_paths_with_same_name": same_name}
                if exact:
                    if expected not in self.hash_cache:
                        try:
                            self.hash_cache[expected] = (_sha256(Path(expected)), None)
                        except OSError as exc:
                            self.hash_cache[expected] = (
                                None, f"{type(exc).__name__}: {exc}")
                    digest, error = self.hash_cache[expected]
                    if digest is not None:
                        record["mapped_sha256"] = digest
                        record["hash_matches"] = digest == expected_hash
                    else:
                        record["hash_read_error"] = error
                        record["hash_matches"] = False
                item["required_mappings"].append(record)
            self.records[pid] = item

    def snapshot(self) -> dict[str, Any]:
        records = [self.records[key] for key in sorted(self.records)]
        return {
            "schema": SCHEMA, "boundary_family": "host_process_mapping",
            "root_process_group": self.pgid, "sample_count": self.sample_count,
            "process_record_limit": MAX_PROCESSES,
            "processes": records,
            "discovery_status": "PROCESS_NOT_DISCOVERED" if not records else "PROCESSES_OBSERVED",
        }
