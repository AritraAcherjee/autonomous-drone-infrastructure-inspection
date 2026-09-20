"""Passive, bounded P19 runtime diagnostic evidence contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping

from .contracts import ContractError, canonical_json_bytes


DIAGNOSTIC_SCHEMA = "aegisinspect.p19.runtime_diagnostic_observability.v1"
CALLBACK_NAMES = (
    "startup_alignment", "scene_identity", "telemetry", "certificate",
    "rgb", "depth", "truth", "camera_info",
)


def parse_diagnostic_artifact(data: str | bytes) -> dict[str, Any]:
    try:
        item = json.loads(data)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ContractError("invalid diagnostic observability JSON") from exc
    if not isinstance(item, dict) or item.get("schema") != DIAGNOSTIC_SCHEMA:
        raise ContractError("diagnostic observability schema mismatch")
    if item.get("boundary_family") not in {
        "host_process_mapping", "native_authoritative_progress", "collector_snapshot",
    }:
        raise ContractError("diagnostic observability boundary family mismatch")
    return item


def diagnostic_bytes(item: Mapping[str, Any]) -> bytes:
    parse_diagnostic_artifact(json.dumps(dict(item)))
    return canonical_json_bytes(dict(item))


@dataclass
class CollectorDiagnosticState:
    """In-memory-only callback and prerequisite state for one collector run."""

    run_id: str
    callback_counts: dict[str, int] = field(
        default_factory=lambda: {name: 0 for name in CALLBACK_NAMES})
    latest_telemetry_run_id: str | None = None
    latest_telemetry_batch_id: str | None = None
    latest_certificate_run_id: str | None = None
    latest_certificate_batch_id: str | None = None
    latest_rejection_or_blocking_predicate: str | None = None
    certificate_accepted_count: int = 0
    certificate_rejected_count: int = 0

    def callback(self, name: str) -> None:
        if name not in self.callback_counts:
            raise ValueError(f"unknown diagnostic callback: {name}")
        self.callback_counts[name] += 1

    def telemetry(self, run_id: str, batch_sequence: int) -> None:
        self.callback("telemetry")
        self.latest_telemetry_run_id = run_id
        self.latest_telemetry_batch_id = f"{run_id}:batch:{batch_sequence}"

    def certificate(self, run_id: str, batch_id: str) -> None:
        self.callback("certificate")
        self.latest_certificate_run_id = run_id
        self.latest_certificate_batch_id = batch_id

    def snapshot(
        self, *, reason: str, terminal_classification: str,
        alignment_available: bool, scene_available: bool,
        camera_info_available: bool, calibration_available: bool,
        rgb_hash_match_available: bool, depth_hash_match_available: bool,
        truth_available: bool, certificate_available: bool,
        telemetry_available: bool, persisted_receipt_count: int,
        current_valid_streak: int, max_valid_streak: int,
    ) -> dict[str, Any]:
        available = {
            "startup_alignment_available": alignment_available,
            "scene_identity_available": scene_available,
            "camera_info_available": camera_info_available,
            "calibration_available": calibration_available,
            "operational_rgb_hash_match_available": rgb_hash_match_available,
            "operational_depth_hash_match_available": depth_hash_match_available,
            "truth_available": truth_available,
            "certificate_available": certificate_available,
            "telemetry_available": telemetry_available,
        }
        pending = []
        names = {
            "startup_alignment_available": "WAITING_FOR_STARTUP_ALIGNMENT",
            "scene_identity_available": "WAITING_FOR_SCENE_IDENTITY",
            "certificate_available": "WAITING_FOR_CERTIFICATE",
            "operational_rgb_hash_match_available": "WAITING_FOR_RGB_BINDING",
            "operational_depth_hash_match_available": "WAITING_FOR_DEPTH_BINDING",
            "truth_available": "WAITING_FOR_TRUTH",
            "camera_info_available": "WAITING_FOR_CAMERA_INFO",
            "calibration_available": "WAITING_FOR_CALIBRATION",
            "telemetry_available": "WAITING_FOR_TELEMETRY",
        }
        for key, label in names.items():
            if not available[key]:
                pending.append(label)
        if persisted_receipt_count < 20:
            pending.append("WAITING_FOR_QUALIFYING_RECEIPT")
        current = pending[0] if len(pending) == 1 else (
            "MULTIPLE_PREREQUISITES_PENDING" if pending else "NO_PREREQUISITE_PENDING")
        return {
            "schema": DIAGNOSTIC_SCHEMA,
            "boundary_family": "collector_snapshot",
            "run_id": self.run_id,
            "snapshot_reason": reason,
            "terminal_classification_unchanged": terminal_classification,
            "startup_alignment_status":
                "AVAILABLE" if alignment_available else "MISSING",
            "callback_counts": dict(self.callback_counts),
            "latest_telemetry_run_id": self.latest_telemetry_run_id,
            "latest_telemetry_batch_id": self.latest_telemetry_batch_id,
            "latest_certificate_run_id": self.latest_certificate_run_id,
            "latest_certificate_batch_id": self.latest_certificate_batch_id,
            "target_sensor_identity_available":
                self.latest_certificate_run_id is not None,
            "certificate_accepted_count": self.certificate_accepted_count,
            "certificate_rejected_count": self.certificate_rejected_count,
            "prerequisite_availability": available,
            "persisted_receipt_count": persisted_receipt_count,
            "current_valid_streak": current_valid_streak,
            "max_valid_streak": max_valid_streak,
            "current_pending_predicate": current,
            "pending_predicates": pending,
            "latest_rejection_or_blocking_predicate":
                self.latest_rejection_or_blocking_predicate,
            "readiness_decision_modified": False,
        }
