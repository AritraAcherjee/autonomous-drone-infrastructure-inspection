"""Deterministic synthetic fixtures for P16 storage tests."""

from __future__ import annotations

from datetime import datetime, timezone

from src.storage.models import (
    EvidenceCreate,
    InspectionCreate,
    InspectionStatus,
    MappedDefectRecord,
    StructureCreate,
)


T0 = datetime(2026, 9, 16, 16, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 16, 16, 0, 2, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 16, 16, 0, 4, tzinfo=timezone.utc)


def make_structure() -> StructureCreate:
    return StructureCreate(
        name="P16 Synthetic Concrete Test Structure",
        description=(
            "Synthetic/test-only structure for P16 validation."
        ),
        location_text="Synthetic Test Environment",
    )


def make_inspection(
    structure_id: int = 1,
) -> InspectionCreate:
    return InspectionCreate(
        structure_id=structure_id,
        started_at=T0,
        completed_at=None,
        status=InspectionStatus.REVIEW,
        system_version="p16-tuesday-demo",
        notes="SYNTHETIC TEST DATA — not detector or inspection evidence.",
    )


def make_defect(
    inspection_id: int = 1,
    **overrides: object,
) -> MappedDefectRecord:
    values = {
        "defect_id": "synthetic-defect-001",
        "inspection_id": inspection_id,
        "track_id": "synthetic-track-001",
        "class_name": "Crack",
        "confidence": 0.92,
        "x_m": 1.25,
        "y_m": 0.40,
        "z_m": 2.10,
        "coordinate_frame": "map",
        "observation_count": 4,
        "first_seen": T0,
        "last_seen": T2,
        "model_version": "synthetic-test-model-v1",
    }
    values.update(overrides)
    return MappedDefectRecord(**values)


def make_evidence(
    defect_id: str = "synthetic-defect-001",
    **overrides: object,
) -> EvidenceCreate:
    values = {
        "defect_id": defect_id,
        "frame_id": "synthetic-frame-001",
        "timestamp": T1,
        "image_path": None,
        "crop_path": None,
        "confidence": 0.92,
        "bbox_x1": 100.0,
        "bbox_y1": 70.0,
        "bbox_x2": 185.0,
        "bbox_y2": 160.0,
    }
    values.update(overrides)
    return EvidenceCreate(**values)
