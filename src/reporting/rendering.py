"""Deterministic scalar formatting and Markdown rendering for P17.

Frozen presentation rules:
- optional None -> exactly "Unavailable"
- finite float -> Python repr(value)
- integer -> ordinary base-10 string
- timestamps -> UTC ISO 8601 with a trailing Z
- defects -> lexical defect_id ascending
- evidence -> timestamp ascending, then evidence_id ascending
- no locale dependency
- no current-time dependency
- no severity, safety, dimensions, or inspection-completeness inference
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import math

from .models import (
    InspectionReport,
    ReportDefect,
    ReportEvidence,
)
from .validation import validate_report


UNAVAILABLE = "Unavailable"

SECTION_HEADINGS = (
    "## 1. Inspection Summary",
    "## 2. Structure / Inspection Metadata",
    "## 3. Defect Summary",
    "## 4. Individual Defect Records",
    "## 5. Evidence / Provenance",
    "## 6. Human Review Status",
    "## 7. Method / Model Metadata",
    "## 8. Limitations",
)


class ReportFormattingError(ValueError):
    """Raised when a scalar cannot be rendered truthfully."""


def format_optional_text(value: str | None) -> str:
    """Render an optional persisted text value without inference."""

    if value is None:
        return UNAVAILABLE

    if not isinstance(value, str):
        raise ReportFormattingError(
            "optional text must be a string or None"
        )

    return value


def format_number(value: int | float) -> str:
    """Render a finite machine numeric value without rounding."""

    if isinstance(value, bool):
        raise ReportFormattingError(
            "boolean is not a report numeric value"
        )

    if isinstance(value, int):
        return str(value)

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ReportFormattingError(
                "floating-point report value must be finite"
            )

        return repr(value)

    raise ReportFormattingError(
        "report numeric value must be an int or float"
    )


def format_timestamp(value: datetime) -> str:
    """Render the exact instant as deterministic UTC ISO 8601."""

    if not isinstance(value, datetime):
        raise ReportFormattingError(
            "report timestamp must be a datetime"
        )

    if value.tzinfo is None or value.utcoffset() is None:
        raise ReportFormattingError(
            "report timestamp must be timezone-aware"
        )

    utc_value = value.astimezone(timezone.utc)

    return utc_value.isoformat().replace("+00:00", "Z")


def _ordered_defects(
    defects: Iterable[ReportDefect],
) -> tuple[ReportDefect, ...]:
    return tuple(
        sorted(
            defects,
            key=lambda defect: defect.defect_id,
        )
    )


def _ordered_evidence(
    evidence: Iterable[ReportEvidence],
) -> tuple[ReportEvidence, ...]:
    return tuple(
        sorted(
            evidence,
            key=lambda item: (
                item.timestamp,
                item.evidence_id,
            ),
        )
    )


def _append_machine_defect(
    lines: list[str],
    defect: ReportDefect,
) -> None:
    lines.extend(
        [
            f"### Defect `{defect.defect_id}`",
            "",
            "#### Machine-Produced Fields",
            "",
            f"- Defect ID: {defect.defect_id}",
            f"- Inspection ID: {format_number(defect.inspection_id)}",
            f"- Track ID: {format_optional_text(defect.track_id)}",
            f"- Class: {defect.class_name}",
            f"- Confidence: {format_number(defect.confidence)}",
            f"- X (m): {format_number(defect.x_m)}",
            f"- Y (m): {format_number(defect.y_m)}",
            f"- Z (m): {format_number(defect.z_m)}",
            f"- Coordinate Frame: {defect.coordinate_frame}",
            (
                "- Observation Count: "
                f"{format_number(defect.observation_count)}"
            ),
            f"- First Seen: {format_timestamp(defect.first_seen)}",
            f"- Last Seen: {format_timestamp(defect.last_seen)}",
            f"- Model Version: {defect.model_version}",
            f"- Created At: {format_timestamp(defect.created_at)}",
            f"- Updated At: {format_timestamp(defect.updated_at)}",
            "",
        ]
    )


def _append_evidence(
    lines: list[str],
    defect: ReportDefect,
) -> None:
    lines.extend(
        [
            f"### Defect `{defect.defect_id}`",
            "",
            (
                "- Evidence Record Count: "
                f"{format_number(len(defect.evidence))}"
            ),
            "",
        ]
    )

    ordered = _ordered_evidence(defect.evidence)

    if not ordered:
        lines.extend(
            [
                "No evidence records are present for this defect.",
                "",
            ]
        )
        return

    for item in ordered:
        lines.extend(
            [
                f"#### Evidence {format_number(item.evidence_id)}",
                "",
                f"- Evidence ID: {format_number(item.evidence_id)}",
                f"- Defect ID: {item.defect_id}",
                f"- Frame ID: {item.frame_id}",
                f"- Timestamp: {format_timestamp(item.timestamp)}",
                f"- Image Path: {format_optional_text(item.image_path)}",
                f"- Crop Path: {format_optional_text(item.crop_path)}",
                f"- Confidence: {format_number(item.confidence)}",
                f"- Bounding Box X1: {format_number(item.bbox_x1)}",
                f"- Bounding Box Y1: {format_number(item.bbox_y1)}",
                f"- Bounding Box X2: {format_number(item.bbox_x2)}",
                f"- Bounding Box Y2: {format_number(item.bbox_y2)}",
                "",
            ]
        )


def render_report(report: InspectionReport) -> str:
    """Render validated report facts as byte-deterministic Markdown."""

    validate_report(report)

    defects = _ordered_defects(report.defects)

    lines: list[str] = [
        "# AegisInspect Inspection Report",
        "",
        SECTION_HEADINGS[0],
        "",
        (
            "- Inspection ID: "
            f"{format_number(report.inspection.inspection_id)}"
        ),
        f"- Inspection Status: {report.inspection.status}",
        f"- Started At: {format_timestamp(report.inspection.started_at)}",
        (
            "- Completed At: "
            + (
                format_timestamp(report.inspection.completed_at)
                if report.inspection.completed_at is not None
                else UNAVAILABLE
            )
        ),
        (
            "- Structure ID: "
            f"{format_number(report.inspection.structure_id)}"
        ),
        f"- Defect Count: {format_number(len(defects))}",
        f"- System Version: {report.inspection.system_version}",
        "",
        SECTION_HEADINGS[1],
        "",
        "### Structure",
        "",
        (
            "- Structure ID: "
            f"{format_number(report.structure.structure_id)}"
        ),
        f"- Name: {report.structure.name}",
        f"- Description: {report.structure.description}",
        (
            "- Location: "
            f"{format_optional_text(report.structure.location_text)}"
        ),
        (
            "- Structure Created At: "
            f"{format_timestamp(report.structure.created_at)}"
        ),
        "",
        "### Inspection",
        "",
        (
            "- Inspection ID: "
            f"{format_number(report.inspection.inspection_id)}"
        ),
        (
            "- Structure ID: "
            f"{format_number(report.inspection.structure_id)}"
        ),
        f"- Status: {report.inspection.status}",
        f"- Started At: {format_timestamp(report.inspection.started_at)}",
        (
            "- Completed At: "
            + (
                format_timestamp(report.inspection.completed_at)
                if report.inspection.completed_at is not None
                else UNAVAILABLE
            )
        ),
        f"- System Version: {report.inspection.system_version}",
        f"- Notes: {format_optional_text(report.inspection.notes)}",
        "",
        SECTION_HEADINGS[2],
        "",
        f"- Total Defects: {format_number(len(defects))}",
        "",
    ]

    if defects:
        lines.append("### Defect IDs")
        lines.append("")

        for defect in defects:
            lines.append(f"- {defect.defect_id}")

        lines.append("")
    else:
        lines.extend(
            [
                "No defect records are present.",
                "",
            ]
        )

    lines.extend(
        [
            SECTION_HEADINGS[3],
            "",
        ]
    )

    if defects:
        for defect in defects:
            _append_machine_defect(lines, defect)
    else:
        lines.extend(
            [
                "No defect records are present.",
                "",
            ]
        )

    lines.extend(
        [
            SECTION_HEADINGS[4],
            "",
        ]
    )

    if defects:
        for defect in defects:
            _append_evidence(lines, defect)
    else:
        lines.extend(
            [
                "No defect records are present.",
                "",
            ]
        )

    lines.extend(
        [
            SECTION_HEADINGS[5],
            "",
        ]
    )

    if defects:
        for defect in defects:
            lines.extend(
                [
                    f"### Defect `{defect.defect_id}`",
                    "",
                    f"- Review Status: {defect.review_status}",
                    (
                        "- Review Notes: "
                        f"{format_optional_text(defect.review_notes)}"
                    ),
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "No defect records are present.",
                "",
            ]
        )

    lines.extend(
        [
            SECTION_HEADINGS[6],
            "",
            (
                "- Inspection System Version: "
                f"{report.inspection.system_version}"
            ),
        ]
    )

    model_versions = tuple(
        sorted(
            {
                defect.model_version
                for defect in defects
            }
        )
    )

    if model_versions:
        lines.extend(
            [
                "- Defect Model Versions:",
                "",
            ]
        )

        for model_version in model_versions:
            lines.append(f"  - {model_version}")
    else:
        lines.append(
            f"- Defect Model Versions: {UNAVAILABLE}"
        )

    lines.extend(
        [
            "",
            SECTION_HEADINGS[7],
            "",
            (
                "- This report presents persisted deterministic inspection, "
                "defect, evidence, and human-review facts."
            ),
            (
                "- Defect dimensions are not reported because no canonical "
                "P16 dimension field is available to P17."
            ),
            (
                "- Structural severity is not inferred from detector "
                "confidence or human-review status."
            ),
            (
                "- This report does not provide structural-safety "
                "conclusions."
            ),
            (
                "- Inspection completeness is not inferred. The inspection "
                "status shown in this report is the persisted status."
            ),
            (
                "- Missing optional values are rendered exactly as "
                f"`{UNAVAILABLE}`."
            ),
            "",
        ]
    )

    return "\n".join(lines)
