"""Immutable deterministic input models for P17 inspection reporting.

This module is deliberately independent of P16 persistence, SQLite,
Streamlit, ROS, Gazebo, detector inference, and LLM APIs.

These DTOs represent only facts available from the frozen P16 reporting
boundary. They intentionally contain no dimensions, structural severity,
structural-safety assessment, or inferred inspection-completeness field.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ReportStructure:
    """Persisted structure facts used by a deterministic report."""

    structure_id: int
    name: str
    description: str
    location_text: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReportInspection:
    """Persisted inspection facts used by a deterministic report."""

    inspection_id: int
    structure_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    system_version: str
    notes: str | None


@dataclass(frozen=True, slots=True)
class ReportEvidence:
    """Persisted evidence facts belonging to one reported defect."""

    evidence_id: int
    defect_id: str
    frame_id: str
    timestamp: datetime
    image_path: str | None
    crop_path: str | None
    confidence: float
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float


@dataclass(frozen=True, slots=True)
class ReportDefect:
    """Persisted machine and human-review facts for one defect."""

    defect_id: str
    inspection_id: int
    track_id: str | None
    class_name: str
    confidence: float
    x_m: float
    y_m: float
    z_m: float
    coordinate_frame: str
    observation_count: int
    first_seen: datetime
    last_seen: datetime
    model_version: str
    review_status: str
    review_notes: str | None
    created_at: datetime
    updated_at: datetime
    evidence: tuple[ReportEvidence, ...]


@dataclass(frozen=True, slots=True)
class InspectionReport:
    """Complete normalized deterministic input to the P17 renderer."""

    structure: ReportStructure
    inspection: ReportInspection
    defects: tuple[ReportDefect, ...]
