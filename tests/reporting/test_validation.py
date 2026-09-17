from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from src.reporting import (
    InspectionReport,
    ReportDefect,
    ReportEvidence,
    ReportInspection,
    ReportStructure,
    ReportValidationError,
    validate_report,
)


T0 = datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 17, 12, 1, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 17, 12, 2, 0, tzinfo=timezone.utc)


def make_report() -> InspectionReport:
    evidence = ReportEvidence(
        evidence_id=1,
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
        structure=ReportStructure(
            structure_id=7,
            name="Synthetic Bridge",
            description="Deterministic reporting fixture",
            location_text=None,
            created_at=T0,
        ),
        inspection=ReportInspection(
            inspection_id=11,
            structure_id=7,
            started_at=T0,
            completed_at=None,
            status="RUNNING",
            system_version="aegis-test-v1",
            notes=None,
        ),
        defects=(defect,),
    )


def test_valid_report_passes_without_mutation() -> None:
    report = make_report()
    original = report

    assert validate_report(report) is None
    assert report == original


def test_zero_defect_report_is_valid() -> None:
    report = replace(make_report(), defects=())

    assert validate_report(report) is None


def test_inspection_structure_relationship_mismatch_fails_closed() -> None:
    report = make_report()
    bad = replace(
        report,
        inspection=replace(
            report.inspection,
            structure_id=999,
        ),
    )

    with pytest.raises(
        ReportValidationError,
        match="inspection.structure_id",
    ):
        validate_report(bad)


def test_defect_inspection_relationship_mismatch_fails_closed() -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        inspection_id=999,
    )
    bad = replace(report, defects=(defect,))

    with pytest.raises(
        ReportValidationError,
        match="defect.inspection_id",
    ):
        validate_report(bad)


def test_evidence_defect_relationship_mismatch_fails_closed() -> None:
    report = make_report()
    defect = report.defects[0]
    evidence = replace(
        defect.evidence[0],
        defect_id="P15D-other",
    )
    bad_defect = replace(
        defect,
        evidence=(evidence,),
    )

    with pytest.raises(
        ReportValidationError,
        match="evidence.defect_id",
    ):
        validate_report(
            replace(report, defects=(bad_defect,))
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("confidence", float("nan")),
        ("confidence", float("inf")),
        ("x_m", float("nan")),
        ("y_m", float("-inf")),
        ("z_m", float("inf")),
    ],
)
def test_nonfinite_defect_numbers_are_rejected(
    field_name: str,
    value: float,
) -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        **{field_name: value},
    )

    with pytest.raises(ReportValidationError):
        validate_report(
            replace(report, defects=(defect,))
        )


@pytest.mark.parametrize(
    "confidence",
    [-0.0001, 1.0001],
)
def test_defect_confidence_outside_closed_interval_is_rejected(
    confidence: float,
) -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        confidence=confidence,
    )

    with pytest.raises(
        ReportValidationError,
        match=r"\[0, 1\]",
    ):
        validate_report(
            replace(report, defects=(defect,))
        )


@pytest.mark.parametrize(
    "confidence",
    [0.0, 1.0],
)
def test_confidence_closed_interval_edges_are_valid(
    confidence: float,
) -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        confidence=confidence,
    )

    assert validate_report(
        replace(report, defects=(defect,))
    ) is None


@pytest.mark.parametrize(
    "observation_count",
    [0, -1, True, 1.5],
)
def test_invalid_observation_count_is_rejected(
    observation_count: object,
) -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        observation_count=observation_count,  # type: ignore[arg-type]
    )

    with pytest.raises(
        ReportValidationError,
        match="observation_count",
    ):
        validate_report(
            replace(report, defects=(defect,))
        )


def test_naive_inspection_timestamp_is_rejected() -> None:
    report = make_report()
    bad = replace(
        report,
        inspection=replace(
            report.inspection,
            started_at=datetime(2026, 9, 17, 12, 0, 0),
        ),
    )

    with pytest.raises(
        ReportValidationError,
        match="timezone-aware",
    ):
        validate_report(bad)


def test_naive_defect_timestamp_is_rejected() -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        first_seen=datetime(2026, 9, 17, 12, 1, 0),
    )

    with pytest.raises(
        ReportValidationError,
        match="timezone-aware",
    ):
        validate_report(
            replace(report, defects=(defect,))
        )


def test_naive_evidence_timestamp_is_rejected() -> None:
    report = make_report()
    defect = report.defects[0]
    evidence = replace(
        defect.evidence[0],
        timestamp=datetime(2026, 9, 17, 12, 1, 0),
    )
    defect = replace(
        defect,
        evidence=(evidence,),
    )

    with pytest.raises(
        ReportValidationError,
        match="timezone-aware",
    ):
        validate_report(
            replace(report, defects=(defect,))
        )


def test_all_other_persisted_timestamps_are_timezone_aware() -> None:
    report = make_report()

    bad_structure = replace(
        report.structure,
        created_at=datetime(2026, 9, 17, 12, 0, 0),
    )

    with pytest.raises(
        ReportValidationError,
        match="timezone-aware",
    ):
        validate_report(
            replace(report, structure=bad_structure)
        )

    bad_defect = replace(
        report.defects[0],
        updated_at=datetime(2026, 9, 17, 12, 2, 0),
    )

    with pytest.raises(
        ReportValidationError,
        match="timezone-aware",
    ):
        validate_report(
            replace(report, defects=(bad_defect,))
        )


def test_last_seen_before_first_seen_is_rejected() -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        first_seen=T2,
        last_seen=T1,
    )

    with pytest.raises(
        ReportValidationError,
        match="last_seen",
    ):
        validate_report(
            replace(report, defects=(defect,))
        )


def test_completed_at_before_started_at_is_rejected() -> None:
    report = make_report()
    inspection = replace(
        report.inspection,
        started_at=T2,
        completed_at=T1,
    )

    with pytest.raises(
        ReportValidationError,
        match="completed_at",
    ):
        validate_report(
            replace(report, inspection=inspection)
        )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("bbox_x1", -1.0),
        ("bbox_y1", -1.0),
        ("bbox_x2", 10.0),
        ("bbox_y2", 20.0),
        ("bbox_x2", float("nan")),
    ],
)
def test_invalid_evidence_bbox_is_rejected(
    field_name: str,
    value: float,
) -> None:
    report = make_report()
    defect = report.defects[0]
    evidence = replace(
        defect.evidence[0],
        **{field_name: value},
    )
    defect = replace(
        defect,
        evidence=(evidence,),
    )

    with pytest.raises(ReportValidationError):
        validate_report(
            replace(report, defects=(defect,))
        )


@pytest.mark.parametrize(
    "confidence",
    [-0.1, 1.1, float("nan")],
)
def test_invalid_evidence_confidence_is_rejected(
    confidence: float,
) -> None:
    report = make_report()
    defect = report.defects[0]
    evidence = replace(
        defect.evidence[0],
        confidence=confidence,
    )
    defect = replace(
        defect,
        evidence=(evidence,),
    )

    with pytest.raises(ReportValidationError):
        validate_report(
            replace(report, defects=(defect,))
        )


def test_unknown_inspection_status_is_rejected() -> None:
    report = make_report()
    inspection = replace(
        report.inspection,
        status="INFERRED_COMPLETE",
    )

    with pytest.raises(
        ReportValidationError,
        match="InspectionStatus",
    ):
        validate_report(
            replace(report, inspection=inspection)
        )


def test_unknown_review_status_is_rejected() -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        review_status="SEVERE",
    )

    with pytest.raises(
        ReportValidationError,
        match="ReviewStatus",
    ):
        validate_report(
            replace(report, defects=(defect,))
        )


def test_none_optional_values_are_valid() -> None:
    report = make_report()

    assert report.structure.location_text is None
    assert report.inspection.completed_at is None
    assert report.inspection.notes is None
    assert report.defects[0].track_id is None
    assert report.defects[0].review_notes is None
    assert report.defects[0].evidence[0].image_path is None
    assert report.defects[0].evidence[0].crop_path is None

    assert validate_report(report) is None


def test_non_tuple_defects_are_rejected() -> None:
    report = make_report()
    bad = replace(
        report,
        defects=list(report.defects),  # type: ignore[arg-type]
    )

    with pytest.raises(
        ReportValidationError,
        match="report.defects",
    ):
        validate_report(bad)


def test_non_tuple_evidence_is_rejected() -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        evidence=list(  # type: ignore[arg-type]
            report.defects[0].evidence
        ),
    )

    with pytest.raises(
        ReportValidationError,
        match="defect.evidence",
    ):
        validate_report(
            replace(report, defects=(defect,))
        )


@pytest.mark.parametrize(
    ("target", "field_name"),
    [
        ("defect_id", "defect.defect_id"),
        ("class_name", "defect.class_name"),
        ("coordinate_frame", "defect.coordinate_frame"),
        ("model_version", "defect.model_version"),
    ],
)
def test_required_defect_strings_cannot_be_empty(
    target: str,
    field_name: str,
) -> None:
    report = make_report()
    defect = replace(
        report.defects[0],
        **{target: "   "},
    )

    with pytest.raises(
        ReportValidationError,
        match=field_name,
    ):
        validate_report(
            replace(report, defects=(defect,))
        )
