"""Fail-closed validation for deterministic P17 report inputs.

Validation is intentionally independent of P16 persistence implementation.
It does not repair, normalize, infer, or fabricate report values.
"""

from __future__ import annotations

from datetime import datetime
import math

from .models import (
    InspectionReport,
    ReportDefect,
    ReportEvidence,
    ReportInspection,
    ReportStructure,
)


INSPECTION_STATUSES = frozenset(
    {
        "PLANNED",
        "RUNNING",
        "PROCESSING",
        "REVIEW",
        "COMPLETED",
        "FAILED",
    }
)

REVIEW_STATUSES = frozenset(
    {
        "UNREVIEWED",
        "CONFIRMED",
        "REJECTED",
        "NEEDS_INVESTIGATION",
    }
)


class ReportValidationError(ValueError):
    """Raised when deterministic report input violates the frozen contract."""


def _require_positive_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ReportValidationError(
            f"{field_name} must be a positive integer"
        )


def _require_nonempty_string(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ReportValidationError(
            f"{field_name} must be a non-empty string"
        )


def _require_optional_string(
    value: object,
    field_name: str,
) -> None:
    if value is None:
        return

    _require_nonempty_string(value, field_name)


def _require_finite_number(
    value: object,
    field_name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReportValidationError(
            f"{field_name} must be a finite number"
        )

    numeric = float(value)

    if not math.isfinite(numeric):
        raise ReportValidationError(
            f"{field_name} must be a finite number"
        )

    return numeric


def _require_confidence(
    value: object,
    field_name: str,
) -> None:
    numeric = _require_finite_number(value, field_name)

    if not 0.0 <= numeric <= 1.0:
        raise ReportValidationError(
            f"{field_name} must be within [0, 1]"
        )


def _require_aware_datetime(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise ReportValidationError(
            f"{field_name} must be a timezone-aware datetime"
        )

    if value.tzinfo is None or value.utcoffset() is None:
        raise ReportValidationError(
            f"{field_name} must be timezone-aware"
        )

    return value


def validate_structure(record: ReportStructure) -> None:
    if not isinstance(record, ReportStructure):
        raise ReportValidationError(
            "structure must be a ReportStructure"
        )

    _require_positive_int(
        record.structure_id,
        "structure.structure_id",
    )
    _require_nonempty_string(
        record.name,
        "structure.name",
    )
    _require_nonempty_string(
        record.description,
        "structure.description",
    )
    _require_optional_string(
        record.location_text,
        "structure.location_text",
    )
    _require_aware_datetime(
        record.created_at,
        "structure.created_at",
    )


def validate_inspection(record: ReportInspection) -> None:
    if not isinstance(record, ReportInspection):
        raise ReportValidationError(
            "inspection must be a ReportInspection"
        )

    _require_positive_int(
        record.inspection_id,
        "inspection.inspection_id",
    )
    _require_positive_int(
        record.structure_id,
        "inspection.structure_id",
    )

    started_at = _require_aware_datetime(
        record.started_at,
        "inspection.started_at",
    )

    if record.completed_at is not None:
        completed_at = _require_aware_datetime(
            record.completed_at,
            "inspection.completed_at",
        )

        if completed_at < started_at:
            raise ReportValidationError(
                "inspection.completed_at must be greater than "
                "or equal to inspection.started_at"
            )

    if record.status not in INSPECTION_STATUSES:
        raise ReportValidationError(
            "inspection.status is not a canonical InspectionStatus value"
        )

    _require_nonempty_string(
        record.system_version,
        "inspection.system_version",
    )
    _require_optional_string(
        record.notes,
        "inspection.notes",
    )


def validate_evidence(record: ReportEvidence) -> None:
    if not isinstance(record, ReportEvidence):
        raise ReportValidationError(
            "evidence must be a ReportEvidence"
        )

    _require_positive_int(
        record.evidence_id,
        "evidence.evidence_id",
    )
    _require_nonempty_string(
        record.defect_id,
        "evidence.defect_id",
    )
    _require_nonempty_string(
        record.frame_id,
        "evidence.frame_id",
    )
    _require_aware_datetime(
        record.timestamp,
        "evidence.timestamp",
    )

    _require_optional_string(
        record.image_path,
        "evidence.image_path",
    )
    _require_optional_string(
        record.crop_path,
        "evidence.crop_path",
    )

    _require_confidence(
        record.confidence,
        "evidence.confidence",
    )

    x1 = _require_finite_number(
        record.bbox_x1,
        "evidence.bbox_x1",
    )
    y1 = _require_finite_number(
        record.bbox_y1,
        "evidence.bbox_y1",
    )
    x2 = _require_finite_number(
        record.bbox_x2,
        "evidence.bbox_x2",
    )
    y2 = _require_finite_number(
        record.bbox_y2,
        "evidence.bbox_y2",
    )

    if x1 < 0.0:
        raise ReportValidationError(
            "evidence.bbox_x1 must be greater than or equal to 0"
        )

    if y1 < 0.0:
        raise ReportValidationError(
            "evidence.bbox_y1 must be greater than or equal to 0"
        )

    if x2 <= x1:
        raise ReportValidationError(
            "evidence.bbox_x2 must be greater than evidence.bbox_x1"
        )

    if y2 <= y1:
        raise ReportValidationError(
            "evidence.bbox_y2 must be greater than evidence.bbox_y1"
        )


def validate_defect(record: ReportDefect) -> None:
    if not isinstance(record, ReportDefect):
        raise ReportValidationError(
            "defect must be a ReportDefect"
        )

    _require_nonempty_string(
        record.defect_id,
        "defect.defect_id",
    )
    _require_positive_int(
        record.inspection_id,
        "defect.inspection_id",
    )
    _require_optional_string(
        record.track_id,
        "defect.track_id",
    )
    _require_nonempty_string(
        record.class_name,
        "defect.class_name",
    )

    _require_confidence(
        record.confidence,
        "defect.confidence",
    )

    _require_finite_number(
        record.x_m,
        "defect.x_m",
    )
    _require_finite_number(
        record.y_m,
        "defect.y_m",
    )
    _require_finite_number(
        record.z_m,
        "defect.z_m",
    )

    _require_nonempty_string(
        record.coordinate_frame,
        "defect.coordinate_frame",
    )

    if (
        isinstance(record.observation_count, bool)
        or not isinstance(record.observation_count, int)
        or record.observation_count < 1
    ):
        raise ReportValidationError(
            "defect.observation_count must be an integer of at least 1"
        )

    first_seen = _require_aware_datetime(
        record.first_seen,
        "defect.first_seen",
    )
    last_seen = _require_aware_datetime(
        record.last_seen,
        "defect.last_seen",
    )

    if last_seen < first_seen:
        raise ReportValidationError(
            "defect.last_seen must be greater than or equal to "
            "defect.first_seen"
        )

    _require_nonempty_string(
        record.model_version,
        "defect.model_version",
    )

    if record.review_status not in REVIEW_STATUSES:
        raise ReportValidationError(
            "defect.review_status is not a canonical ReviewStatus value"
        )

    _require_optional_string(
        record.review_notes,
        "defect.review_notes",
    )

    _require_aware_datetime(
        record.created_at,
        "defect.created_at",
    )
    _require_aware_datetime(
        record.updated_at,
        "defect.updated_at",
    )

    if not isinstance(record.evidence, tuple):
        raise ReportValidationError(
            "defect.evidence must be a tuple"
        )

    for evidence in record.evidence:
        validate_evidence(evidence)

        if evidence.defect_id != record.defect_id:
            raise ReportValidationError(
                "evidence.defect_id must match the owning defect.defect_id"
            )


def validate_report(report: InspectionReport) -> None:
    """Validate the full frozen P17 deterministic report boundary."""

    if not isinstance(report, InspectionReport):
        raise ReportValidationError(
            "report must be an InspectionReport"
        )

    validate_structure(report.structure)
    validate_inspection(report.inspection)

    if (
        report.inspection.structure_id
        != report.structure.structure_id
    ):
        raise ReportValidationError(
            "inspection.structure_id must match structure.structure_id"
        )

    if not isinstance(report.defects, tuple):
        raise ReportValidationError(
            "report.defects must be a tuple"
        )

    for defect in report.defects:
        validate_defect(defect)

        if defect.inspection_id != report.inspection.inspection_id:
            raise ReportValidationError(
                "defect.inspection_id must match "
                "report.inspection.inspection_id"
            )
