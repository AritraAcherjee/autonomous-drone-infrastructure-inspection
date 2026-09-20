"""Authoritative run-scoped sensor-batch telemetry contract and reference model."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Sequence

from .contracts import ContractError, canonical_json_bytes, require_text, sha256_bytes


TELEMETRY_SCHEMA = "aegisinspect.p19.sensor_batch_telemetry.v1"
CLASSIFICATIONS = {
    "NON_ACQUISITION_BATCH", "RGBD_ONLY", "TRUTH_ONLY",
    "BOTH_GENERATED_VALID", "BOTH_GENERATED_INVALID",
}


@dataclass(frozen=True)
class SensorBatchTelemetry:
    schema: str
    run_id: str
    last_batch_sequence: int
    last_classification: str
    total_manager_batches: int
    non_acquisition_batches: int
    relevant_candidate_batches: int
    both_generated_valid: int
    rgbd_only: int
    truth_only: int
    both_generated_invalid: int
    certificate_count: int
    current_consecutive_valid_streak: int
    max_consecutive_valid_streak: int
    accounting_valid: bool


def validate_batch_telemetry(item: SensorBatchTelemetry) -> None:
    if item.schema != TELEMETRY_SCHEMA:
        raise ContractError("sensor-batch telemetry schema mismatch")
    require_text(item.run_id, "run_id")
    if item.last_classification not in CLASSIFICATIONS:
        raise ContractError("invalid batch classification")
    for name in (
        "last_batch_sequence", "total_manager_batches", "non_acquisition_batches",
        "relevant_candidate_batches", "both_generated_valid", "rgbd_only",
        "truth_only", "both_generated_invalid", "certificate_count",
        "current_consecutive_valid_streak", "max_consecutive_valid_streak",
    ):
        value = getattr(item, name)
        if type(value) is not int or value < 0:
            raise ContractError(f"invalid telemetry counter: {name}")
    if type(item.accounting_valid) is not bool or not item.accounting_valid:
        raise ContractError("sensor-batch accounting is not valid")
    if item.last_batch_sequence != item.total_manager_batches:
        raise ContractError("batch sequence / total mismatch")
    if item.total_manager_batches != (
            item.non_acquisition_batches + item.relevant_candidate_batches):
        raise ContractError("manager-batch partition invariant failed")
    if item.relevant_candidate_batches != (
            item.both_generated_valid + item.rgbd_only + item.truth_only
            + item.both_generated_invalid):
        raise ContractError("relevant-batch partition invariant failed")
    if item.certificate_count != item.both_generated_valid:
        raise ContractError("certificate count does not match successful emission")
    if item.current_consecutive_valid_streak > item.max_consecutive_valid_streak:
        raise ContractError("current streak exceeds maximum streak")
    if item.max_consecutive_valid_streak > item.both_generated_valid:
        raise ContractError("maximum streak exceeds valid batch count")


def parse_batch_telemetry(text: str) -> SensorBatchTelemetry:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError("invalid sensor-batch telemetry JSON") from exc
    if set(value) != set(SensorBatchTelemetry.__dataclass_fields__):
        raise ContractError("sensor-batch telemetry fields mismatch")
    item = SensorBatchTelemetry(**value)
    validate_batch_telemetry(item)
    return item


def telemetry_bytes(item: SensorBatchTelemetry) -> bytes:
    validate_batch_telemetry(item)
    return canonical_json_bytes(asdict(item))


def telemetry_hash(item: SensorBatchTelemetry) -> str:
    return sha256_bytes(telemetry_bytes(item))


def validate_telemetry_progression(items: Sequence[SensorBatchTelemetry], run_id: str) -> None:
    require_text(run_id, "run_id")
    previous = None
    counter_names = (
        "total_manager_batches", "non_acquisition_batches",
        "relevant_candidate_batches", "both_generated_valid", "rgbd_only",
        "truth_only", "both_generated_invalid", "certificate_count",
        "max_consecutive_valid_streak",
    )
    for item in items:
        validate_batch_telemetry(item)
        if item.run_id != run_id:
            raise ContractError("stale or wrong telemetry run ID")
        if previous is not None:
            if item.last_batch_sequence <= previous.last_batch_sequence:
                raise ContractError("telemetry batch sequence is stale or restarted")
            if any(getattr(item, name) < getattr(previous, name) for name in counter_names):
                raise ContractError("whole-run telemetry counter decreased")
        previous = item


class BatchTelemetryAccumulator:
    """Pure reference state machine matching the native batch-close accounting."""

    def __init__(self, run_id: str):
        require_text(run_id, "run_id")
        self.run_id = run_id
        self.counts = {name: 0 for name in (
            "total_manager_batches", "non_acquisition_batches",
            "relevant_candidate_batches", "both_generated_valid", "rgbd_only",
            "truth_only", "both_generated_invalid", "certificate_count",
            "current_consecutive_valid_streak", "max_consecutive_valid_streak",
        )}
        self.last_classification = "NON_ACQUISITION_BATCH"

    def close(self, *, rgb_generated: bool, depth_generated: bool,
              truth_generated: bool, eligibility_valid: bool,
              certificate_emitted: bool, ambiguous_generation: bool = False,
              lifecycle_valid: bool = True) -> SensorBatchTelemetry:
        if not lifecycle_valid:
            raise ContractError("invalid native batch lifecycle cannot be accounted")
        rgbd_any = rgb_generated or depth_generated
        complete = rgb_generated and depth_generated and truth_generated
        if not rgbd_any and not truth_generated:
            classification = "NON_ACQUISITION_BATCH"
        elif rgbd_any and not truth_generated:
            classification = "RGBD_ONLY"
        elif truth_generated and not rgbd_any:
            classification = "TRUTH_ONLY"
        elif (complete and eligibility_valid and certificate_emitted
              and not ambiguous_generation):
            classification = "BOTH_GENERATED_VALID"
        else:
            classification = "BOTH_GENERATED_INVALID"
        if certificate_emitted != (classification == "BOTH_GENERATED_VALID"):
            raise ContractError("certificate outcome / classification mismatch")
        self.counts["total_manager_batches"] += 1
        if classification == "NON_ACQUISITION_BATCH":
            self.counts["non_acquisition_batches"] += 1
        else:
            self.counts["relevant_candidate_batches"] += 1
            key = {
                "RGBD_ONLY": "rgbd_only", "TRUTH_ONLY": "truth_only",
                "BOTH_GENERATED_VALID": "both_generated_valid",
                "BOTH_GENERATED_INVALID": "both_generated_invalid",
            }[classification]
            self.counts[key] += 1
        if classification == "BOTH_GENERATED_VALID":
            self.counts["certificate_count"] += 1
            self.counts["current_consecutive_valid_streak"] += 1
            self.counts["max_consecutive_valid_streak"] = max(
                self.counts["max_consecutive_valid_streak"],
                self.counts["current_consecutive_valid_streak"])
        elif classification != "NON_ACQUISITION_BATCH":
            self.counts["current_consecutive_valid_streak"] = 0
        self.last_classification = classification
        result = SensorBatchTelemetry(
            schema=TELEMETRY_SCHEMA, run_id=self.run_id,
            last_batch_sequence=self.counts["total_manager_batches"],
            last_classification=classification, accounting_valid=True,
            **self.counts,
        )
        validate_batch_telemetry(result)
        return result
