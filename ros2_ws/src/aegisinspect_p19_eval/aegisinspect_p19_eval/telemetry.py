"""Bounded passive counters for readiness acquisition and exact-time joins."""

from __future__ import annotations

from collections import Counter, deque
from typing import Mapping


STREAMS = ("rgb", "depth", "camera_info", "truth", "attestation")


class PassiveJoinTelemetry:
    def __init__(self, history_limit: int = 500) -> None:
        self.seen = Counter({name: 0 for name in STREAMS})
        self.scene_identity_seen = 0
        self.join_attempts = 0
        self.receipts_created = 0
        self.rejections = Counter()
        self.history = deque(maxlen=history_limit)

    def record_seen(self, stream: str) -> None:
        self.seen[stream] += 1

    def record_scene_identity(self) -> None:
        self.scene_identity_seen += 1

    def record_join(self, key: int, presence: Mapping[str, bool], scene_seen: bool) -> None:
        self.join_attempts += 1
        missing = [name for name in STREAMS if not presence[name]]
        reason = "SCENE_IDENTITY_MISSING" if not scene_seen else (
            "MISSING_" + "_".join(name.upper() for name in missing) if missing else
            "ELIGIBILITY_VALIDATION_PENDING")
        if reason != "ELIGIBILITY_VALIDATION_PENDING":
            self.rejections[reason] += 1
        self.history.append({
            "candidate_timestamp": key,
            "rgb_seen": presence["rgb"],
            "depth_seen": presence["depth"],
            "camera_info_seen": presence["camera_info"],
            "truth_seen": presence["truth"],
            "render_attestation_seen": presence["attestation"],
            "scene_identity_seen": scene_seen,
            "exact_time_key_available": scene_seen and not missing,
            "rejected_key": None if reason == "ELIGIBILITY_VALIDATION_PENDING" else key,
            "rejection_reason": reason,
            "observation_token_state": "NOT_CREATED",
        })

    def record_rejection(self, key: int, reason: str) -> None:
        normalized = "VALIDATION_REJECTED:" + reason
        self.rejections[normalized] += 1
        self.history.append({
            "candidate_timestamp": key,
            "rejected_key": key,
            "rejection_reason": normalized,
            "observation_token_state": "REJECTED",
        })

    def record_receipt(self, key: int, token: str) -> None:
        self.receipts_created += 1
        self.history.append({
            "candidate_timestamp": key,
            "rejected_key": None,
            "rejection_reason": None,
            "observation_token_state": "CREATED",
            "observation_token": token,
        })

    def snapshot(self, outcome: str) -> dict:
        return {
            "schema": "aegisinspect.p19.passive-join-telemetry.v1",
            "outcome": outcome,
            "stream_seen_counts": dict(self.seen),
            "scene_identity_seen_count": self.scene_identity_seen,
            "join_attempt_count": self.join_attempts,
            "receipt_count": self.receipts_created,
            "join_rejection_counts": dict(self.rejections),
            "recent_attempts": list(self.history),
            "eligibility_logic_modified": False,
        }
