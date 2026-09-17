from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from src.reporting import (
    SECTION_HEADINGS,
    InspectionReport,
    ReportDefect,
    ReportEvidence,
    ReportInspection,
    ReportStructure,
    ReportValidationError,
    render_report,
)


UTC = timezone.utc
OFFSET = timezone(timedelta(hours=-6))

T0 = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 9, 17, 12, 1, 0, tzinfo=UTC)
T2 = datetime(2026, 9, 17, 12, 2, 0, tzinfo=UTC)


def make_evidence(
    *,
    evidence_id: int,
    defect_id: str,
    timestamp: datetime,
    frame_id: str,
    image_path: str | None = None,
    crop_path: str | None = None,
) -> ReportEvidence:
    return ReportEvidence(
        evidence_id=evidence_id,
        defect_id=defect_id,
        frame_id=frame_id,
        timestamp=timestamp,
        image_path=image_path,
        crop_path=crop_path,
        confidence=0.91,
        bbox_x1=10.0,
        bbox_y1=20.0,
        bbox_x2=30.0,
        bbox_y2=40.0,
    )


def make_defect(
    *,
    defect_id: str,
    class_name: str,
    confidence: float,
    x_m: float,
    model_version: str = "DET-FINAL-v1",
    evidence: tuple[ReportEvidence, ...] = (),
    review_status: str = "UNREVIEWED",
    review_notes: str | None = None,
) -> ReportDefect:
    return ReportDefect(
        defect_id=defect_id,
        inspection_id=11,
        track_id=None,
        class_name=class_name,
        confidence=confidence,
        x_m=x_m,
        y_m=0.4,
        z_m=2.1,
        coordinate_frame="map",
        observation_count=4,
        first_seen=T1,
        last_seen=T2,
        model_version=model_version,
        review_status=review_status,
        review_notes=review_notes,
        created_at=T1,
        updated_at=T2,
        evidence=evidence,
    )


def make_report(
    defects: tuple[ReportDefect, ...],
) -> InspectionReport:
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
        defects=defects,
    )


def test_all_eight_sections_are_present_in_frozen_order() -> None:
    rendered = render_report(make_report(()))

    positions = [
        rendered.index(heading)
        for heading in SECTION_HEADINGS
    ]

    assert positions == sorted(positions)
    assert len(positions) == 8


def test_zero_defect_inspection_renders_deterministically() -> None:
    report = make_report(())

    rendered = render_report(report)

    assert "- Defect Count: 0" in rendered
    assert "- Total Defects: 0" in rendered
    assert "No defect records are present." in rendered
    assert "- Defect Model Versions: Unavailable" in rendered


def test_one_defect_preserves_machine_values_exactly() -> None:
    defect = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.923456789,
        x_m=1.2345678901234567,
    )

    rendered = render_report(
        make_report((defect,))
    )

    assert "- Class: Crack" in rendered
    assert "- Confidence: 0.923456789" in rendered
    assert "- X (m): 1.2345678901234567" in rendered
    assert "- Y (m): 0.4" in rendered
    assert "- Z (m): 2.1" in rendered
    assert "- Coordinate Frame: map" in rendered
    assert "- Observation Count: 4" in rendered
    assert "- Model Version: DET-FINAL-v1" in rendered


def test_optional_none_values_use_exact_unavailable_marker() -> None:
    defect = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.92,
        x_m=1.25,
        evidence=(
            make_evidence(
                evidence_id=1,
                defect_id="P15D-a",
                timestamp=T1,
                frame_id="frame-001",
            ),
        ),
    )

    rendered = render_report(
        make_report((defect,))
    )

    assert "- Location: Unavailable" in rendered
    assert "- Completed At: Unavailable" in rendered
    assert "- Notes: Unavailable" in rendered
    assert "- Track ID: Unavailable" in rendered
    assert "- Review Notes: Unavailable" in rendered
    assert "- Image Path: Unavailable" in rendered
    assert "- Crop Path: Unavailable" in rendered

    assert "Not provided" not in rendered
    assert "N/A" not in rendered
    assert "Unknown" not in rendered


def test_defects_are_sorted_by_lexical_defect_id() -> None:
    defect_z = make_defect(
        defect_id="P15D-z",
        class_name="Hole",
        confidence=0.80,
        x_m=3.0,
    )
    defect_a = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.90,
        x_m=1.0,
    )

    rendered = render_report(
        make_report((defect_z, defect_a))
    )

    section = rendered.split(
        "## 3. Defect Summary",
        1,
    )[1].split(
        "## 4. Individual Defect Records",
        1,
    )[0]

    assert section.index("P15D-a") < section.index("P15D-z")


def test_evidence_is_sorted_by_timestamp_then_id() -> None:
    same_time = T1

    evidence = (
        make_evidence(
            evidence_id=20,
            defect_id="P15D-a",
            timestamp=T2,
            frame_id="frame-late",
        ),
        make_evidence(
            evidence_id=2,
            defect_id="P15D-a",
            timestamp=same_time,
            frame_id="frame-same-2",
        ),
        make_evidence(
            evidence_id=1,
            defect_id="P15D-a",
            timestamp=same_time,
            frame_id="frame-same-1",
        ),
    )

    defect = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.92,
        x_m=1.25,
        evidence=evidence,
    )

    rendered = render_report(
        make_report((defect,))
    )

    section = rendered.split(
        "## 5. Evidence / Provenance",
        1,
    )[1].split(
        "## 6. Human Review Status",
        1,
    )[0]

    assert (
        section.index("frame-same-1")
        < section.index("frame-same-2")
        < section.index("frame-late")
    )


def test_human_review_is_visibly_separate_from_machine_fields() -> None:
    defect = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.92,
        x_m=1.25,
        review_status="NEEDS_INVESTIGATION",
        review_notes="Inspect manually.",
    )

    rendered = render_report(
        make_report((defect,))
    )

    machine_section = rendered.split(
        "## 4. Individual Defect Records",
        1,
    )[1].split(
        "## 5. Evidence / Provenance",
        1,
    )[0]

    review_section = rendered.split(
        "## 6. Human Review Status",
        1,
    )[1].split(
        "## 7. Method / Model Metadata",
        1,
    )[0]

    assert "Review Status" not in machine_section
    assert "Review Notes" not in machine_section

    assert (
        "- Review Status: NEEDS_INVESTIGATION"
        in review_section
    )
    assert (
        "- Review Notes: Inspect manually."
        in review_section
    )


def test_timestamp_values_are_normalized_to_utc() -> None:
    offset_time = datetime(
        2026,
        9,
        17,
        6,
        1,
        0,
        tzinfo=OFFSET,
    )

    evidence = make_evidence(
        evidence_id=1,
        defect_id="P15D-a",
        timestamp=offset_time,
        frame_id="frame-001",
    )

    defect = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.92,
        x_m=1.25,
        evidence=(evidence,),
    )

    rendered = render_report(
        make_report((defect,))
    )

    assert "- Timestamp: 2026-09-17T12:01:00Z" in rendered


def test_evidence_paths_bbox_and_confidence_are_preserved() -> None:
    evidence = make_evidence(
        evidence_id=7,
        defect_id="P15D-a",
        timestamp=T1,
        frame_id="frame-007",
        image_path="evidence/frame-007.png",
        crop_path="evidence/crops/P15D-a.png",
    )

    defect = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.92,
        x_m=1.25,
        evidence=(evidence,),
    )

    rendered = render_report(
        make_report((defect,))
    )

    assert "- Image Path: evidence/frame-007.png" in rendered
    assert "- Crop Path: evidence/crops/P15D-a.png" in rendered
    assert "- Confidence: 0.91" in rendered
    assert "- Bounding Box X1: 10.0" in rendered
    assert "- Bounding Box Y1: 20.0" in rendered
    assert "- Bounding Box X2: 30.0" in rendered
    assert "- Bounding Box Y2: 40.0" in rendered


def test_model_versions_are_deterministically_unique_and_sorted() -> None:
    z = make_defect(
        defect_id="P15D-z",
        class_name="Hole",
        confidence=0.8,
        x_m=3.0,
        model_version="model-z",
    )
    a = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.9,
        x_m=1.0,
        model_version="model-a",
    )
    b = make_defect(
        defect_id="P15D-b",
        class_name="Breakage",
        confidence=0.85,
        x_m=2.0,
        model_version="model-a",
    )

    rendered = render_report(
        make_report((z, b, a))
    )

    section = rendered.split(
        "## 7. Method / Model Metadata",
        1,
    )[1].split(
        "## 8. Limitations",
        1,
    )[0]

    assert section.count("model-a") == 1
    assert section.count("model-z") == 1
    assert section.index("model-a") < section.index("model-z")


def test_rendering_is_byte_deterministic_for_same_input() -> None:
    defect = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.92,
        x_m=1.25,
    )
    report = make_report((defect,))

    first = render_report(report).encode("utf-8")
    second = render_report(report).encode("utf-8")

    assert first == second


def test_input_tuple_order_does_not_control_report_order() -> None:
    a = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.92,
        x_m=1.0,
    )
    z = make_defect(
        defect_id="P15D-z",
        class_name="Hole",
        confidence=0.82,
        x_m=2.0,
    )

    first = render_report(make_report((z, a)))
    second = render_report(make_report((a, z)))

    assert first == second


def test_renderer_validates_input_before_output() -> None:
    defect = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=1.5,
        x_m=1.25,
    )

    with pytest.raises(ReportValidationError):
        render_report(
            make_report((defect,))
        )


def test_report_does_not_fabricate_dimension_or_severity_fields() -> None:
    defect = make_defect(
        defect_id="P15D-a",
        class_name="Crack",
        confidence=0.99,
        x_m=1.25,
    )

    rendered = render_report(
        make_report((defect,))
    )

    lower = rendered.lower()

    assert "dimension:" not in lower
    assert "severity:" not in lower
    assert "severity = " not in lower


def test_report_contains_no_structural_safety_conclusion() -> None:
    rendered = render_report(make_report(()))

    assert (
        "This report does not provide structural-safety conclusions."
        in rendered
    )

    assert "structurally safe" not in rendered.lower()
    assert "structurally unsafe" not in rendered.lower()


def test_inspection_status_is_persisted_value_not_inferred() -> None:
    report = make_report(())
    report = replace(
        report,
        inspection=replace(
            report.inspection,
            status="RUNNING",
        ),
    )

    rendered = render_report(report)

    assert "- Inspection Status: RUNNING" in rendered
    assert "- Status: RUNNING" in rendered
    assert "Inspection Status: COMPLETED" not in rendered


def test_limitations_explicitly_block_truthfulness_violations() -> None:
    rendered = render_report(make_report(()))

    assert (
        "Structural severity is not inferred from detector "
        "confidence or human-review status."
        in rendered
    )
    assert (
        "Inspection completeness is not inferred."
        in rendered
    )
    assert (
        "Missing optional values are rendered exactly as "
        "`Unavailable`."
        in rendered
    )
