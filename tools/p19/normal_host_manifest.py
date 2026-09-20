#!/usr/bin/env python3
"""Production normal-host manifest generation and execution binding checks."""

from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any
import xml.etree.ElementTree as ET


DIAGNOSTIC_SCHEMA = "aegisinspect.p19.runtime_diagnostic_observability.v1"
DIAGNOSTIC_SCHEMA_SHA256 = (
    "2504563582575c64e67d33d5868a83e3f943064097ec25751daadec4869abbf1"
)
ACCEPTED_OVERLAY = Path("/tmp/p19-passive-observability-build/install")
STATIC_EVIDENCE_SHA256 = (
    "28d771b56553318aa8c1d96c20c2ddcdb53cfe692d1bb65cc327f2aedbce0be7"
)
STATIC_EVIDENCE_CLASSIFICATION = (
    "P19 PASSIVE DIAGNOSTIC OBSERVABILITY — IMPLEMENTATION/STATIC PASS"
)

SOURCE_WORLD_RELATIVE = Path(
    "ros2_ws/src/aegisinspect_p19_eval/worlds/"
    "p19_correspondence_readiness_batch_v1.sdf"
)
INSTALLED_WORLD_RELATIVE = Path(
    "aegisinspect_p19_eval/share/aegisinspect_p19_eval/worlds/"
    "p19_correspondence_readiness_batch_v1.sdf"
)
EXPECTED_SENSORS_PATH = Path(
    "/tmp/p19-gazebo-instrumented/lib/gz-sim-10/plugins/"
    "libgz-sim-sensors-system.so.10.5.0"
)
EXPECTED_SENSORS_CANONICAL_PATH = EXPECTED_SENSORS_PATH
EXPECTED_SENSORS_SHA256 = (
    "99b44134931986c500e40464864c00d6a09c8328c37d4e451b96f0e8ab7229e2"
)
EXPECTED_SENSORS_NAME = "gz::sim::systems::Sensors"
EXPECTED_RENDER_ENGINE = "ogre2"
SENSORS_RESOLUTION_RESULT = "PASS"
SENSORS_RESOLUTION_CONTRACT = (
    "absolute-existing-path-short-circuits-gz-common-find-shared-library-v1"
)

P19_LIBRARY_HASHES = {
    "libp19_sensor_batch_certificate.so":
        "24401f49cde03541811a02a131aa08f52b15ae50a2bcbfebf1d2547c25c0d178",
    "libp19_update_attestor.so":
        "c22d5ae9b03b9811013281bf9f61cd465c47856af8fff8182cf93d7b4e7e04d9",
    "libp19_batch_scene_configurator.so":
        "a46dadf6ddb791531efaf6c7f9ec925d01320c24f23ba21efd634a8c97ee8cf0",
}

DIAGNOSTIC_SOURCE_HASHES = {
    "ros2_ws/src/aegisinspect_p19_eval/aegisinspect_p19_eval/diagnostic_observability.py":
        "52b02451c1eb274086b486757fb5f4842979aed9f4e81c51be690652aa606880",
    "ros2_ws/src/aegisinspect_p19_eval/launch/no_start_readiness.launch.py":
        "52cf7619c8c45689f1748ee15ed9bd09a474fe7033a0c4374d3c49300eea4cbd",
    "ros2_ws/src/aegisinspect_p19_eval/scripts/readiness_node.py":
        "7befdaa29c83fd1eecfa56c686ce6e6371ccda141e63ffeb0e2e81982d46ea17",
    "tools/p19/process_observability.py":
        "7179354f449cff72332671cb45dfe98b0fddc2b2f9497586e95a74ca0f5ca68b",
    "tools/p19/readiness_supervisor.py":
        "5c65272129dd43261028cd2d5f4d9a26a230398131746553793d233986ae5be1",
    "ros2_ws/src/aegisinspect_p19_eval/config/runtime_diagnostic_observability.v1.schema.json":
        DIAGNOSTIC_SCHEMA_SHA256,
}

SCIENTIFIC_KEYS = (
    "gt_defect_id", "target_class", "target_scene_identity", "gt_world_x",
    "gt_world_y", "gt_world_z", "gt_coordinate_convention", "scene_model",
    "scene_link", "scene_visual", "visual_asset_path", "visual_asset_sha256",
    "asset_generator_sha256", "asset_provenance", "material_sha256",
    "model_sha256", "scene_sha256", "camera_config_sha256",
    "calibration_configuration", "p13_trajectory_sha256", "p13_config_sha256",
    "det_final_v1_checkpoint_sha256", "detector_inference_config_sha256",
    "certificate_rule", "certificate_schema", "correspondence_generation_rule",
    "observation_to_gt_binding_rule", "readiness_rules",
    "t_map_from_world_source_rule", "exposure_selection_rule",
    "timeout_failure_rules", "no_start_safety",
)


class BindingError(RuntimeError):
    """An accepted execution or provenance identity did not match."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def library_paths(overlay: Path) -> dict[str, Path]:
    base = overlay / "aegisinspect_p19_eval/lib"
    return {name: base / name for name in P19_LIBRARY_HASHES}


def _require_file_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise BindingError(f"missing {label}: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise BindingError(f"{label} SHA-256 expected={expected} actual={actual}")


def verify_gz_sim_sensors_system_selection(
    *, root: Path, overlay: Path,
) -> dict[str, Any]:
    """Verify the exact project-controlled Sensors system request and install."""
    source_world = root / SOURCE_WORLD_RELATIVE
    installed_world = overlay / INSTALLED_WORLD_RELATIVE
    if not source_world.is_file():
        raise BindingError(f"missing source readiness world: {source_world}")
    if not installed_world.is_file():
        raise BindingError(f"missing installed readiness world: {installed_world}")
    source_bytes = source_world.read_bytes()
    installed_bytes = installed_world.read_bytes()
    if source_bytes != installed_bytes:
        raise BindingError("source and installed readiness world bytes differ")
    try:
        document = ET.fromstring(installed_bytes)
    except ET.ParseError as exc:
        raise BindingError(f"malformed installed readiness world XML: {exc}") from exc
    sensors_plugins = [
        plugin for plugin in document.findall("./world/plugin")
        if plugin.get("name") == EXPECTED_SENSORS_NAME
    ]
    if len(sensors_plugins) != 1:
        raise BindingError(
            "expected exactly one world-level Sensors plugin, "
            f"found={len(sensors_plugins)}"
        )
    plugin = sensors_plugins[0]
    requested = plugin.get("filename")
    if not requested:
        raise BindingError("Sensors plugin filename is missing")
    requested_path = Path(requested)
    if not requested_path.is_absolute():
        raise BindingError(f"Sensors plugin path is not absolute: {requested}")
    if requested_path != EXPECTED_SENSORS_PATH:
        raise BindingError(
            f"Sensors plugin path expected={EXPECTED_SENSORS_PATH} actual={requested_path}"
        )
    if not requested_path.is_file():
        raise BindingError(f"missing requested Sensors plugin: {requested_path}")
    canonical = requested_path.resolve(strict=True)
    if canonical != EXPECTED_SENSORS_CANONICAL_PATH:
        raise BindingError(
            "Sensors plugin canonical path "
            f"expected={EXPECTED_SENSORS_CANONICAL_PATH} actual={canonical}"
        )
    _require_file_hash(
        canonical, EXPECTED_SENSORS_SHA256, "requested Sensors plugin"
    )
    render = plugin.find("render_engine")
    render_engine = None if render is None else render.text
    if render_engine != EXPECTED_RENDER_ENGINE:
        raise BindingError(
            f"Sensors render engine expected={EXPECTED_RENDER_ENGINE} "
            f"actual={render_engine}"
        )
    return {
        "result": SENSORS_RESOLUTION_RESULT,
        "source_world_path": str(source_world),
        "source_world_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "installed_world_path": str(installed_world),
        "installed_world_sha256": hashlib.sha256(installed_bytes).hexdigest(),
        "sensors_plugin_count": len(sensors_plugins),
        "sensors_plugin_name": plugin.get("name"),
        "sensors_requested_filename": requested,
        "sensors_requested_path_is_absolute": requested_path.is_absolute(),
        "sensors_requested_canonical_path": str(canonical),
        "sensors_requested_sha256": sha256_file(canonical),
        "expected_sensors_path": str(EXPECTED_SENSORS_PATH),
        "expected_sensors_sha256": EXPECTED_SENSORS_SHA256,
        "render_engine": render_engine,
        "source_installed_world_bytes_match": True,
        "resolution_contract": SENSORS_RESOLUTION_CONTRACT,
    }


def verify_execution_bindings(
    *, root: Path, implementation_sha: str, actual_head: str,
    overlay: Path, runner_path: Path, static_evidence_path: Path,
) -> dict[str, Any]:
    root = root.resolve()
    overlay = overlay.resolve()
    if implementation_sha != actual_head:
        raise BindingError(
            f"implementation HEAD expected={implementation_sha} actual={actual_head}"
        )
    if overlay != ACCEPTED_OVERLAY:
        raise BindingError(f"overlay expected={ACCEPTED_OVERLAY} actual={overlay}")
    if not (overlay / "setup.bash").is_file():
        raise BindingError(f"missing accepted overlay: {overlay}")
    for name, path in library_paths(overlay).items():
        _require_file_hash(path, P19_LIBRARY_HASHES[name], name)
    for relative, expected in DIAGNOSTIC_SOURCE_HASHES.items():
        _require_file_hash(root / relative, expected, relative)
    schema_path = root / next(
        relative for relative in DIAGNOSTIC_SOURCE_HASHES
        if relative.endswith("runtime_diagnostic_observability.v1.schema.json")
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("$id") != DIAGNOSTIC_SCHEMA:
        raise BindingError(
            f"diagnostic schema expected={DIAGNOSTIC_SCHEMA} actual={schema.get('$id')}"
        )
    _require_file_hash(
        static_evidence_path, STATIC_EVIDENCE_SHA256, "static evidence package"
    )
    if not runner_path.is_file():
        raise BindingError(f"missing runner: {runner_path}")
    sensors_selection = verify_gz_sim_sensors_system_selection(
        root=root, overlay=overlay
    )
    producer_path = Path(__file__).resolve()
    return {
        "implementation_sha": implementation_sha,
        "runner_sha256": sha256_file(runner_path),
        "overlay_prefix": str(overlay),
        "manifest_producer_sha256": sha256_file(producer_path),
        "p19_native_library_sha256": dict(sorted(P19_LIBRARY_HASHES.items())),
        "diagnostic_schema": DIAGNOSTIC_SCHEMA,
        "diagnostic_schema_sha256": DIAGNOSTIC_SCHEMA_SHA256,
        "diagnostic_runtime_source_sha256": dict(sorted(DIAGNOSTIC_SOURCE_HASHES.items())),
        "static_evidence_sha256": STATIC_EVIDENCE_SHA256,
        "static_evidence_classification": STATIC_EVIDENCE_CLASSIFICATION,
        "gz_sim_sensors_system_selection": sensors_selection,
    }


def _changed_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        result: list[str] = []
        for key in sorted(set(left) | set(right)):
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                result.append(path)
            else:
                result.extend(_changed_paths(left[key], right[key], path))
        return result
    return [] if left == right else [prefix]


def _validate_sensors_selection_provenance(selection: Any) -> None:
    if not isinstance(selection, dict):
        raise BindingError("missing or malformed Sensors selection provenance")
    expected = {
        "result": SENSORS_RESOLUTION_RESULT,
        "sensors_plugin_count": 1,
        "sensors_plugin_name": EXPECTED_SENSORS_NAME,
        "sensors_requested_filename": str(EXPECTED_SENSORS_PATH),
        "sensors_requested_path_is_absolute": True,
        "sensors_requested_canonical_path": str(EXPECTED_SENSORS_CANONICAL_PATH),
        "sensors_requested_sha256": EXPECTED_SENSORS_SHA256,
        "expected_sensors_path": str(EXPECTED_SENSORS_PATH),
        "expected_sensors_sha256": EXPECTED_SENSORS_SHA256,
        "render_engine": EXPECTED_RENDER_ENGINE,
        "source_installed_world_bytes_match": True,
        "resolution_contract": SENSORS_RESOLUTION_CONTRACT,
    }
    for field, value in expected.items():
        if selection.get(field) != value:
            raise BindingError(
                f"Sensors selection provenance {field} expected={value!r} "
                f"actual={selection.get(field)!r}"
            )
    if selection.get("source_world_sha256") != selection.get("installed_world_sha256"):
        raise BindingError("Sensors selection provenance world hashes differ")


def build_runtime_manifest(
    *, prior: dict[str, Any], execution_bindings: dict[str, Any],
    host_identity_sha256: str, host_capability_path: Path,
    host_capability_sha256: str, static_evidence_path: Path,
    creation_timestamp: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    required = {
        "implementation_sha", "runner_sha256", "overlay_prefix",
        "manifest_producer_sha256", "p19_native_library_sha256",
        "diagnostic_schema", "diagnostic_schema_sha256",
        "diagnostic_runtime_source_sha256", "static_evidence_sha256",
        "static_evidence_classification", "gz_sim_sensors_system_selection",
    }
    missing = sorted(required - execution_bindings.keys())
    if missing:
        raise BindingError(f"missing required execution provenance: {missing}")
    _validate_sensors_selection_provenance(
        execution_bindings["gz_sim_sensors_system_selection"]
    )
    new = copy.deepcopy(prior)
    new["creation_timestamp"] = creation_timestamp
    new["manifest_identity"] = "P19-3D-CORRESPONDENCE-NORMAL-HOST-READINESS-v3"
    new["execution_environment"] = {
        "class": "normal-msi-ubuntu-wsl-host",
        "host_identity_sha256": host_identity_sha256,
        "prohibited_origin": "Codex execution sandbox",
    }
    new["accepted_host_capability_evidence"] = {
        "archive_path": str(host_capability_path),
        "archive_sha256": host_capability_sha256,
        "manifest_result": "20/20 PASS; 0 missing; 0 mismatches",
    }
    new["accepted_static_evidence"] = {
        "archive_path": str(static_evidence_path),
        "archive_sha256": execution_bindings["static_evidence_sha256"],
        "classification": execution_bindings["static_evidence_classification"],
        "role": "engineering provenance only; not a scientific runtime input",
    }
    new["normal_host_execution_rules"] = {
        "automatic_retry": False,
        "readiness_deadline_owner": "readiness_supervisor",
        "readiness_deadline_seconds": 120,
        "p13_start_calls": 0,
        "detector_inferences": 0,
        "p15_scientific_observations": 0,
        "p16_ingestions": 0,
        "p19_3d_evaluations": 0,
    }
    new["relevant_git_shas"]["p19_runtime_candidate"] = execution_bindings[
        "implementation_sha"
    ]
    native = execution_bindings["p19_native_library_sha256"]
    instrumentation = new["instrumentation_provenance"]
    instrumentation["certificate_library_sha256"] = native[
        "libp19_sensor_batch_certificate.so"
    ]
    instrumentation["update_attestor_library_sha256"] = native[
        "libp19_update_attestor.so"
    ]
    instrumentation["batch_scene_configurator_library_sha256"] = native[
        "libp19_batch_scene_configurator.so"
    ]
    new["evidence_interface_provenance"] = {
        "implementation_sha": execution_bindings["implementation_sha"],
        "certificate_schema": "aegisinspect.p19.sensor_batch_certificate.v1",
        "startup_alignment_schema": "aegisinspect.p19.startup_alignment.v2",
        "sensor_batch_telemetry_schema": "aegisinspect.p19.sensor_batch_telemetry.v1",
        "certificate_library_sha256": native["libp19_sensor_batch_certificate.so"],
        "update_attestor_library_sha256": native["libp19_update_attestor.so"],
        "batch_scene_configurator_library_sha256": native[
            "libp19_batch_scene_configurator.so"
        ],
    }
    new["diagnostic_execution_provenance"] = copy.deepcopy(execution_bindings)

    changes = _changed_paths(prior, new)
    allowed = {
        "creation_timestamp", "manifest_identity", "execution_environment",
        "accepted_host_capability_evidence", "accepted_static_evidence",
        "normal_host_execution_rules", "evidence_interface_provenance",
        "diagnostic_execution_provenance",
        "relevant_git_shas.p19_runtime_candidate",
        "instrumentation_provenance.certificate_library_sha256",
        "instrumentation_provenance.update_attestor_library_sha256",
        "instrumentation_provenance.batch_scene_configurator_library_sha256",
    }
    unexpected = [
        path for path in changes
        if not any(path == item or path.startswith(item + ".") for item in allowed)
    ]
    science = {key: prior.get(key) == new.get(key) for key in SCIENTIFIC_KEYS}
    gz_unchanged = (
        prior["instrumentation_provenance"].get("gz_sim")
        == new["instrumentation_provenance"].get("gz_sim")
        and prior["instrumentation_provenance"].get("gz_sensors")
        == new["instrumentation_provenance"].get("gz_sensors")
    )
    equal = not unexpected and all(science.values()) and gz_unchanged
    comparison = {
        "scientific_field_differences": 0 if equal else 1,
        "scientific_behavior_fields_changed": not equal,
        "provenance_classification": "ENGINEERING_PROVENANCE_ADDITION",
        "all_changed_paths": changes,
        "unexpected_difference_paths": unexpected,
        "scientific_fields_unchanged": science,
        "gz_sim_gz_sensors_provenance_unchanged": gz_unchanged,
    }
    if not equal:
        raise BindingError(f"scientific manifest comparison failed: {comparison}")
    return new, comparison


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--prior-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--host-identity", type=Path, required=True)
    parser.add_argument("--host-capability-path", type=Path, required=True)
    parser.add_argument("--host-capability-sha256", required=True)
    parser.add_argument("--static-evidence-path", type=Path, required=True)
    parser.add_argument("--implementation-sha", required=True)
    parser.add_argument("--runner-path", type=Path, required=True)
    parser.add_argument("--overlay-prefix", type=Path, required=True)
    parser.add_argument("--creation-timestamp")
    args = parser.parse_args()
    actual_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=args.root, text=True
    ).strip()
    bindings = verify_execution_bindings(
        root=args.root, implementation_sha=args.implementation_sha,
        actual_head=actual_head, overlay=args.overlay_prefix,
        runner_path=args.runner_path,
        static_evidence_path=args.static_evidence_path,
    )
    prior = json.loads(args.prior_manifest.read_text(encoding="utf-8"))
    timestamp = args.creation_timestamp or datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat().replace("+00:00", "Z")
    manifest, comparison = build_runtime_manifest(
        prior=prior, execution_bindings=bindings,
        host_identity_sha256=sha256_file(args.host_identity),
        host_capability_path=args.host_capability_path,
        host_capability_sha256=args.host_capability_sha256,
        static_evidence_path=args.static_evidence_path,
        creation_timestamp=timestamp,
    )
    args.output.write_bytes(canonical_json_bytes(manifest) + b"\n")
    args.comparison.write_bytes(canonical_json_bytes(comparison) + b"\n")


if __name__ == "__main__":
    main()
