"""Deterministic inspection reporting domain for AegisInspect."""

from .models import (
    InspectionReport,
    ReportDefect,
    ReportEvidence,
    ReportInspection,
    ReportStructure,
)
from .rendering import (
    SECTION_HEADINGS,
    UNAVAILABLE,
    ReportFormattingError,
    format_number,
    format_optional_text,
    format_timestamp,
    render_report,
)
from .validation import (
    INSPECTION_STATUSES,
    REVIEW_STATUSES,
    ReportValidationError,
    validate_defect,
    validate_evidence,
    validate_inspection,
    validate_report,
    validate_structure,
)

__all__ = [
    "INSPECTION_STATUSES",
    "REVIEW_STATUSES",
    "SECTION_HEADINGS",
    "UNAVAILABLE",
    "InspectionReport",
    "ReportDefect",
    "ReportEvidence",
    "ReportFormattingError",
    "ReportInspection",
    "ReportStructure",
    "ReportValidationError",
    "format_number",
    "format_optional_text",
    "format_timestamp",
    "render_report",
    "validate_defect",
    "validate_evidence",
    "validate_inspection",
    "validate_report",
    "validate_structure",
]
