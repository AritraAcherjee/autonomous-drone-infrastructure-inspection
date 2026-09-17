"""Validation rules for the P16 persistence boundary."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from .models import (
    EvidenceCreate,
    InspectionCreate,
    InspectionStatus,
    MappedDefectRecord,
    ReviewStatus,
    StructureCreate,
)


class ValidationError(ValueError):
    """Raised when a P16 boundary record violates a frozen contract."""


def _require_nonempty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string")
    return value


def _require_optional_string(value: object, field_name: str) -> None:
    if value is not None and not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string or None")


def _require_finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{field_name} must be numeric")

    numeric_value = float(value)

    if not math.isfinite(numeric_value):
        raise ValidationError(f"{field_name} must be finite")

    return numeric_value


def _require_aware_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValidationError(f"{field_name} must be a datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(f"{field_name} must be timezone-aware")

    try:
        value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValidationError(
            f"{field_name} must be UTC-convertible"
        ) from exc

    return value


def validate_confidence(value: object, field_name: str = "confidence") -> None:
    numeric_value = _require_finite_number(value, field_name)

    if not 0.0 <= numeric_value <= 1.0:
        raise ValidationError(
            f"{field_name} must be between 0.0 and 1.0 inclusive"
        )


def validate_observation_count(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("observation_count must be an integer")

    if value < 1:
        raise ValidationError("observation_count must be at least 1")


def validate_review_status(status: object) -> None:
    if not isinstance(status, ReviewStatus):
        raise ValidationError("status must be a ReviewStatus")


def validate_structure_create(record: StructureCreate) -> None:
    if not isinstance(record, StructureCreate):
        raise ValidationError("record must be a StructureCreate")

    _require_nonempty_string(record.name, "name")

    if not isinstance(record.description, str):
        raise ValidationError("description must be a string")

    _require_optional_string(record.location_text, "location_text")


def validate_inspection_create(record: InspectionCreate) -> None:
    if not isinstance(record, InspectionCreate):
        raise ValidationError("record must be an InspectionCreate")

    if (
        isinstance(record.structure_id, bool)
        or not isinstance(record.structure_id, int)
        or record.structure_id < 1
    ):
        raise ValidationError("structure_id must be a positive integer")

    started_at = _require_aware_datetime(
        record.started_at,
        "started_at",
    )

    if record.completed_at is not None:
        completed_at = _require_aware_datetime(
            record.completed_at,
            "completed_at",
        )

        if completed_at < started_at:
            raise ValidationError(
                "completed_at must be greater than or equal to started_at"
            )

    if not isinstance(record.status, InspectionStatus):
        raise ValidationError("status must be an InspectionStatus")

    _require_nonempty_string(record.system_version, "system_version")
    _require_optional_string(record.notes, "notes")


def validate_mapped_defect(record: MappedDefectRecord) -> None:
    if not isinstance(record, MappedDefectRecord):
        raise ValidationError("record must be a MappedDefectRecord")

    _require_nonempty_string(record.defect_id, "defect_id")

    if (
        isinstance(record.inspection_id, bool)
        or not isinstance(record.inspection_id, int)
        or record.inspection_id < 1
    ):
        raise ValidationError("inspection_id must be a positive integer")

    _require_optional_string(record.track_id, "track_id")
    _require_nonempty_string(record.class_name, "class_name")

    validate_confidence(record.confidence)

    _require_finite_number(record.x_m, "x_m")
    _require_finite_number(record.y_m, "y_m")
    _require_finite_number(record.z_m, "z_m")

    _require_nonempty_string(
        record.coordinate_frame,
        "coordinate_frame",
    )

    validate_observation_count(record.observation_count)

    first_seen = _require_aware_datetime(
        record.first_seen,
        "first_seen",
    )
    last_seen = _require_aware_datetime(
        record.last_seen,
        "last_seen",
    )

    if last_seen < first_seen:
        raise ValidationError(
            "last_seen must be greater than or equal to first_seen"
        )

    _require_nonempty_string(record.model_version, "model_version")


def validate_evidence_create(record: EvidenceCreate) -> None:
    if not isinstance(record, EvidenceCreate):
        raise ValidationError("record must be an EvidenceCreate")

    _require_nonempty_string(record.defect_id, "defect_id")
    _require_nonempty_string(record.frame_id, "frame_id")
    _require_aware_datetime(record.timestamp, "timestamp")

    _require_optional_string(record.image_path, "image_path")
    _require_optional_string(record.crop_path, "crop_path")

    validate_confidence(record.confidence)

    x1 = _require_finite_number(record.bbox_x1, "bbox_x1")
    y1 = _require_finite_number(record.bbox_y1, "bbox_y1")
    x2 = _require_finite_number(record.bbox_x2, "bbox_x2")
    y2 = _require_finite_number(record.bbox_y2, "bbox_y2")

    if x1 < 0:
        raise ValidationError("bbox_x1 must be greater than or equal to 0")

    if y1 < 0:
        raise ValidationError("bbox_y1 must be greater than or equal to 0")

    if x2 <= x1:
        raise ValidationError("bbox_x2 must be greater than bbox_x1")

    if y2 <= y1:
        raise ValidationError("bbox_y2 must be greater than bbox_y1")
