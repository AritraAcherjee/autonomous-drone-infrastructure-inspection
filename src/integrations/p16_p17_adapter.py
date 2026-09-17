"""Read-only integration boundary from canonical P16 persistence to P17.

The adapter consumes only the existing P16 InspectionService read API:

- get_inspection
- get_structure
- list_inspection_defects
- list_evidence

It performs no persistence writes, human-review decisions, inferred
relationships, severity classification, safety assessment, localization,
or report-time data fabrication.
"""

from __future__ import annotations

from src.reporting.models import (
    InspectionReport,
    ReportDefect,
    ReportEvidence,
    ReportInspection,
    ReportStructure,
)
from src.reporting.validation import (
    ReportValidationError,
    validate_defect,
    validate_evidence,
    validate_report,
)
from src.storage.models import (
    Defect,
    Evidence,
    Inspection,
    InspectionStatus,
    ReviewStatus,
    Structure,
)
from src.storage.service import InspectionService


class P16P17AdapterError(ValueError):
    """Raised when persisted P16 data cannot form a truthful P17 report."""


def _require_inspection_status(value: object) -> str:
    if not isinstance(value, InspectionStatus):
        raise P16P17AdapterError(
            "inspection status is not a canonical InspectionStatus"
        )

    return value.value


def _require_review_status(value: object) -> str:
    if not isinstance(value, ReviewStatus):
        raise P16P17AdapterError(
            "defect review status is not a canonical ReviewStatus"
        )

    return value.value


def structure_to_report(record: Structure) -> ReportStructure:
    """Convert one persisted P16 Structure without inference."""

    if not isinstance(record, Structure):
        raise P16P17AdapterError(
            "record must be a canonical P16 Structure"
        )

    return ReportStructure(
        structure_id=record.structure_id,
        name=record.name,
        description=record.description,
        location_text=record.location_text,
        created_at=record.created_at,
    )


def inspection_to_report(record: Inspection) -> ReportInspection:
    """Convert one persisted P16 Inspection without inference."""

    if not isinstance(record, Inspection):
        raise P16P17AdapterError(
            "record must be a canonical P16 Inspection"
        )

    return ReportInspection(
        inspection_id=record.inspection_id,
        structure_id=record.structure_id,
        started_at=record.started_at,
        completed_at=record.completed_at,
        status=_require_inspection_status(record.status),
        system_version=record.system_version,
        notes=record.notes,
    )


def evidence_to_report(record: Evidence) -> ReportEvidence:
    """Convert one persisted P16 Evidence record exactly."""

    if not isinstance(record, Evidence):
        raise P16P17AdapterError(
            "record must be canonical P16 Evidence"
        )

    converted = ReportEvidence(
        evidence_id=record.evidence_id,
        defect_id=record.defect_id,
        frame_id=record.frame_id,
        timestamp=record.timestamp,
        image_path=record.image_path,
        crop_path=record.crop_path,
        confidence=record.confidence,
        bbox_x1=record.bbox_x1,
        bbox_y1=record.bbox_y1,
        bbox_x2=record.bbox_x2,
        bbox_y2=record.bbox_y2,
    )

    try:
        validate_evidence(converted)
    except ReportValidationError as exc:
        raise P16P17AdapterError(
            "persisted P16 evidence is invalid for P17"
        ) from exc

    return converted


def defect_to_report(
    record: Defect,
    evidence: tuple[ReportEvidence, ...],
) -> ReportDefect:
    """Convert one persisted P16 Defect and its owned evidence."""

    if not isinstance(record, Defect):
        raise P16P17AdapterError(
            "record must be a canonical P16 Defect"
        )

    if not isinstance(evidence, tuple):
        raise P16P17AdapterError(
            "evidence must be a tuple of ReportEvidence"
        )

    for item in evidence:
        if item.defect_id != record.defect_id:
            raise P16P17AdapterError(
                "evidence defect_id does not match owning defect"
            )

    converted = ReportDefect(
        defect_id=record.defect_id,
        inspection_id=record.inspection_id,
        track_id=record.track_id,
        class_name=record.class_name,
        confidence=record.confidence,
        x_m=record.x_m,
        y_m=record.y_m,
        z_m=record.z_m,
        coordinate_frame=record.coordinate_frame,
        observation_count=record.observation_count,
        first_seen=record.first_seen,
        last_seen=record.last_seen,
        model_version=record.model_version,
        review_status=_require_review_status(
            record.review_status
        ),
        review_notes=record.review_notes,
        created_at=record.created_at,
        updated_at=record.updated_at,
        evidence=evidence,
    )

    try:
        validate_defect(converted)
    except ReportValidationError as exc:
        raise P16P17AdapterError(
            "persisted P16 defect is invalid for P17"
        ) from exc

    return converted


def build_inspection_report(
    service: InspectionService,
    inspection_id: int,
) -> InspectionReport:
    """Read canonical P16 facts and build a validated P17 report model."""

    if (
        isinstance(inspection_id, bool)
        or not isinstance(inspection_id, int)
        or inspection_id < 1
    ):
        raise P16P17AdapterError(
            "inspection_id must be a positive integer"
        )

    inspection = service.get_inspection(inspection_id)

    if inspection is None:
        raise P16P17AdapterError(
            f"inspection {inspection_id} does not exist"
        )

    structure = service.get_structure(
        inspection.structure_id
    )

    if structure is None:
        raise P16P17AdapterError(
            "inspection references a structure that does not exist"
        )

    report_structure = structure_to_report(structure)
    report_inspection = inspection_to_report(inspection)

    report_defects: list[ReportDefect] = []

    for defect in service.list_inspection_defects(
        inspection_id
    ):
        if defect.inspection_id != inspection_id:
            raise P16P17AdapterError(
                "P16 returned a defect belonging to another inspection"
            )

        report_evidence: list[ReportEvidence] = []

        for evidence in service.list_evidence(
            defect.defect_id
        ):
            if evidence.defect_id != defect.defect_id:
                raise P16P17AdapterError(
                    "P16 returned evidence belonging to another defect"
                )

            report_evidence.append(
                evidence_to_report(evidence)
            )

        ordered_evidence = tuple(
            sorted(
                report_evidence,
                key=lambda item: (
                    item.timestamp,
                    item.evidence_id,
                ),
            )
        )

        report_defects.append(
            defect_to_report(
                defect,
                ordered_evidence,
            )
        )

    report = InspectionReport(
        structure=report_structure,
        inspection=report_inspection,
        defects=tuple(
            sorted(
                report_defects,
                key=lambda defect: defect.defect_id,
            )
        ),
    )

    try:
        validate_report(report)
    except ReportValidationError as exc:
        raise P16P17AdapterError(
            "persisted P16 records cannot form a valid P17 report"
        ) from exc

    return report
