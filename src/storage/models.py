"""P16 storage domain models and persistence boundary DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ReviewStatus(str, Enum):
    """Human review states for a persisted defect."""

    UNREVIEWED = "UNREVIEWED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    NEEDS_INVESTIGATION = "NEEDS_INVESTIGATION"


class InspectionStatus(str, Enum):
    """Supported Tuesday inspection lifecycle states."""

    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PROCESSING = "PROCESSING"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class StructureCreate:
    """Input DTO for creating a structure."""

    name: str
    description: str
    location_text: str | None = None


@dataclass(frozen=True)
class InspectionCreate:
    """Input DTO for creating an inspection."""

    structure_id: int
    started_at: datetime
    completed_at: datetime | None
    status: InspectionStatus
    system_version: str
    notes: str | None = None


@dataclass(frozen=True)
class MappedDefectRecord:
    """Already-decided mapped defect received from the P15/P16 boundary."""

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


@dataclass(frozen=True)
class EvidenceCreate:
    """Input DTO for provenance evidence attached to a defect."""

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


@dataclass(frozen=True)
class Structure:
    """Persisted structure record."""

    structure_id: int
    name: str
    description: str
    location_text: str | None
    created_at: datetime


@dataclass(frozen=True)
class Inspection:
    """Persisted inspection record."""

    inspection_id: int
    structure_id: int
    started_at: datetime
    completed_at: datetime | None
    status: InspectionStatus
    system_version: str
    notes: str | None


@dataclass(frozen=True)
class Defect:
    """Persisted mapped-defect record including human review state."""

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
    review_status: ReviewStatus
    review_notes: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Evidence:
    """Persisted provenance evidence record."""

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
