from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

from src.reporting import (
    InspectionReport,
    ReportDefect,
    ReportEvidence,
    ReportInspection,
    ReportStructure,
)


T0 = datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 17, 12, 1, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 17, 12, 2, 0, tzinfo=timezone.utc)


def make_report() -> InspectionReport:
    structure = ReportStructure(
        structure_id=7,
        name="Synthetic Bridge",
        description="Deterministic reporting fixture",
        location_text=None,
        created_at=T0,
    )

    inspection = ReportInspection(
        inspection_id=11,
        structure_id=7,
        started_at=T0,
        completed_at=None,
        status="RUNNING",
        system_version="aegis-test-v1",
        notes=None,
    )

    evidence = ReportEvidence(
        evidence_id=13,
        defect_id="P15D-example",
        frame_id="frame-001",
        timestamp=T1,
        image_path=None,
        crop_path=None,
        confidence=0.91,
        bbox_x1=10.0,
        bbox_y1=20.0,
        bbox_x2=30.0,
        bbox_y2=40.0,
    )

    defect = ReportDefect(
        defect_id="P15D-example",
        inspection_id=11,
        track_id=None,
        class_name="Crack",
        confidence=0.92,
        x_m=1.25,
        y_m=0.4,
        z_m=2.1,
        coordinate_frame="map",
        observation_count=4,
        first_seen=T1,
        last_seen=T2,
        model_version="DET-FINAL-v1",
        review_status="UNREVIEWED",
        review_notes=None,
        created_at=T1,
        updated_at=T2,
        evidence=(evidence,),
    )

    return InspectionReport(
        structure=structure,
        inspection=inspection,
        defects=(defect,),
    )


def test_exact_report_structure_fields() -> None:
    assert [field.name for field in fields(ReportStructure)] == [
        "structure_id",
        "name",
        "description",
        "location_text",
        "created_at",
    ]


def test_exact_report_inspection_fields() -> None:
    assert [field.name for field in fields(ReportInspection)] == [
        "inspection_id",
        "structure_id",
        "started_at",
        "completed_at",
        "status",
        "system_version",
        "notes",
    ]


def test_exact_report_evidence_fields() -> None:
    assert [field.name for field in fields(ReportEvidence)] == [
        "evidence_id",
        "defect_id",
        "frame_id",
        "timestamp",
        "image_path",
        "crop_path",
        "confidence",
        "bbox_x1",
        "bbox_y1",
        "bbox_x2",
        "bbox_y2",
    ]


def test_exact_report_defect_fields() -> None:
    assert [field.name for field in fields(ReportDefect)] == [
        "defect_id",
        "inspection_id",
        "track_id",
        "class_name",
        "confidence",
        "x_m",
        "y_m",
        "z_m",
        "coordinate_frame",
        "observation_count",
        "first_seen",
        "last_seen",
        "model_version",
        "review_status",
        "review_notes",
        "created_at",
        "updated_at",
        "evidence",
    ]


def test_exact_inspection_report_fields() -> None:
    assert [field.name for field in fields(InspectionReport)] == [
        "structure",
        "inspection",
        "defects",
    ]


def test_models_are_immutable() -> None:
    report = make_report()

    with pytest.raises(FrozenInstanceError):
        report.inspection = report.inspection  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        report.defects[0].confidence = 0.5  # type: ignore[misc]


def test_source_values_are_preserved_without_interpretation() -> None:
    report = make_report()
    defect = report.defects[0]

    assert report.inspection.status == "RUNNING"
    assert defect.class_name == "Crack"
    assert defect.confidence == 0.92
    assert (defect.x_m, defect.y_m, defect.z_m) == (1.25, 0.4, 2.1)
    assert defect.coordinate_frame == "map"
    assert defect.observation_count == 4
    assert defect.model_version == "DET-FINAL-v1"
    assert defect.review_status == "UNREVIEWED"


def test_nested_collections_are_tuples() -> None:
    report = make_report()

    assert isinstance(report.defects, tuple)
    assert isinstance(report.defects[0].evidence, tuple)


def test_models_do_not_expose_fabricated_fields() -> None:
    forbidden = {
        "dimensions",
        "dimension",
        "severity",
        "safety",
        "safety_assessment",
        "structural_safety",
        "inspection_complete",
        "inspection_completeness",
    }

    for model in (
        ReportStructure,
        ReportInspection,
        ReportEvidence,
        ReportDefect,
        InspectionReport,
    ):
        names = {field.name for field in fields(model)}
        assert names.isdisjoint(forbidden)
