from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime, timezone
from pathlib import Path
import ast

from src.reporting import (
    InspectionReport,
    ReportDefect,
    ReportEvidence,
    ReportInspection,
    ReportStructure,
    render_report,
)


UTC = timezone.utc

T0 = datetime(2026, 9, 17, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 9, 17, 12, 1, 0, tzinfo=UTC)
T2 = datetime(2026, 9, 17, 12, 2, 0, tzinfo=UTC)


def make_evidence(
    *,
    evidence_id: int,
    defect_id: str,
    timestamp: datetime,
) -> ReportEvidence:
    return ReportEvidence(
        evidence_id=evidence_id,
        defect_id=defect_id,
        frame_id=f"frame-{evidence_id:03d}",
        timestamp=timestamp,
        image_path=f"evidence/frame-{evidence_id:03d}.png",
        crop_path=f"evidence/crop-{evidence_id:03d}.png",
        confidence=0.87654321,
        bbox_x1=10.125,
        bbox_y1=20.25,
        bbox_x2=30.5,
        bbox_y2=40.75,
    )


def make_defect(
    *,
    defect_id: str = "P15D-a",
    class_name: str = "Crack",
    confidence: float = 0.923456789,
    track_id: str | None = "track-17",
    review_status: str = "CONFIRMED",
    review_notes: str | None = "Human-reviewed note.",
    evidence: tuple[ReportEvidence, ...] = (),
) -> ReportDefect:
    return ReportDefect(
        defect_id=defect_id,
        inspection_id=11,
        track_id=track_id,
        class_name=class_name,
        confidence=confidence,
        x_m=1.2345678901234567,
        y_m=-2.5,
        z_m=3.75,
        coordinate_frame="map",
        observation_count=7,
        first_seen=T1,
        last_seen=T2,
        model_version="DET-FINAL-v1",
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
            description="Pure-domain contract fixture",
            location_text="Synthetic location",
            created_at=T0,
        ),
        inspection=ReportInspection(
            inspection_id=11,
            structure_id=7,
            started_at=T0,
            completed_at=T2,
            status="COMPLETED",
            system_version="aegis-system-v1",
            notes="Inspection note.",
        ),
        defects=defects,
    )


def test_zero_one_and_multiple_defect_reports_render() -> None:
    zero = render_report(make_report(()))

    one_defect = make_defect()
    one = render_report(make_report((one_defect,)))

    second = make_defect(
        defect_id="P15D-b",
        class_name="Breakage",
        confidence=0.81,
    )
    multiple = render_report(
        make_report((second, one_defect))
    )

    assert "- Total Defects: 0" in zero
    assert "- Total Defects: 1" in one
    assert "- Total Defects: 2" in multiple


def test_exact_machine_values_are_preserved_in_markdown() -> None:
    defect = make_defect()

    rendered = render_report(
        make_report((defect,))
    )

    expected = (
        "- Class: Crack",
        "- Confidence: 0.923456789",
        "- X (m): 1.2345678901234567",
        "- Y (m): -2.5",
        "- Z (m): 3.75",
        "- Coordinate Frame: map",
        "- Observation Count: 7",
        "- First Seen: 2026-09-17T12:01:00Z",
        "- Last Seen: 2026-09-17T12:02:00Z",
        "- Model Version: DET-FINAL-v1",
        "- Track ID: track-17",
    )

    for value in expected:
        assert value in rendered


def test_exact_evidence_values_are_preserved() -> None:
    evidence = make_evidence(
        evidence_id=5,
        defect_id="P15D-a",
        timestamp=T1,
    )

    defect = make_defect(
        evidence=(evidence,),
    )

    rendered = render_report(
        make_report((defect,))
    )

    expected = (
        "- Frame ID: frame-005",
        "- Timestamp: 2026-09-17T12:01:00Z",
        "- Image Path: evidence/frame-005.png",
        "- Crop Path: evidence/crop-005.png",
        "- Confidence: 0.87654321",
        "- Bounding Box X1: 10.125",
        "- Bounding Box Y1: 20.25",
        "- Bounding Box X2: 30.5",
        "- Bounding Box Y2: 40.75",
    )

    for value in expected:
        assert value in rendered


def test_human_review_fields_are_preserved_verbatim() -> None:
    defect = make_defect(
        review_status="CONFIRMED",
        review_notes="Human-reviewed note.",
    )

    rendered = render_report(
        make_report((defect,))
    )

    assert "- Review Status: CONFIRMED" in rendered
    assert "- Review Notes: Human-reviewed note." in rendered


def test_all_optional_none_fields_render_exact_unavailable() -> None:
    evidence = replace(
        make_evidence(
            evidence_id=1,
            defect_id="P15D-a",
            timestamp=T1,
        ),
        image_path=None,
        crop_path=None,
    )

    defect = replace(
        make_defect(evidence=(evidence,)),
        track_id=None,
        review_notes=None,
    )

    report = make_report((defect,))
    report = replace(
        report,
        structure=replace(
            report.structure,
            location_text=None,
        ),
        inspection=replace(
            report.inspection,
            completed_at=None,
            notes=None,
        ),
    )

    rendered = render_report(report)

    assert rendered.count("Unavailable") >= 7

    for forbidden in (
        "Not provided",
        "N/A",
        "Unknown",
    ):
        assert forbidden not in rendered


def test_inspection_status_is_preserved_not_inferred() -> None:
    report = make_report(())

    report = replace(
        report,
        inspection=replace(
            report.inspection,
            status="RUNNING",
            completed_at=None,
        ),
    )

    rendered = render_report(report)

    assert "- Inspection Status: RUNNING" in rendered
    assert "- Status: RUNNING" in rendered
    assert "Inspection Status: COMPLETED" not in rendered


def test_defect_order_is_independent_of_input_tuple_order() -> None:
    a = make_defect(defect_id="P15D-a")
    b = make_defect(defect_id="P15D-b")
    z = make_defect(defect_id="P15D-z")

    first = render_report(
        make_report((z, a, b))
    )
    second = render_report(
        make_report((b, z, a))
    )

    assert first == second


def test_evidence_order_is_independent_of_input_tuple_order() -> None:
    early_one = make_evidence(
        evidence_id=1,
        defect_id="P15D-a",
        timestamp=T1,
    )
    early_two = make_evidence(
        evidence_id=2,
        defect_id="P15D-a",
        timestamp=T1,
    )
    late = make_evidence(
        evidence_id=3,
        defect_id="P15D-a",
        timestamp=T2,
    )

    first = make_defect(
        evidence=(late, early_two, early_one),
    )
    second = make_defect(
        evidence=(early_one, late, early_two),
    )

    assert (
        render_report(make_report((first,)))
        == render_report(make_report((second,)))
    )


def test_repeated_render_is_byte_identical() -> None:
    evidence = make_evidence(
        evidence_id=1,
        defect_id="P15D-a",
        timestamp=T1,
    )
    report = make_report(
        (
            make_defect(
                evidence=(evidence,),
            ),
        )
    )

    first = render_report(report).encode("utf-8")
    second = render_report(report).encode("utf-8")

    assert first == second


def test_dto_schema_has_no_forbidden_truthfulness_fields() -> None:
    forbidden = {
        "dimension",
        "dimensions",
        "severity",
        "structural_severity",
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
        names = {
            field.name
            for field in fields(model)
        }

        assert names.isdisjoint(forbidden)


def test_renderer_contains_no_positive_structural_safety_claim() -> None:
    rendered = render_report(
        make_report((make_defect(),))
    ).lower()

    for forbidden_claim in (
        "structurally safe",
        "structurally unsafe",
        "safe for use",
        "unsafe for use",
    ):
        assert forbidden_claim not in rendered


def test_pure_reporting_imports_have_no_forbidden_dependencies() -> None:
    root = Path("src/reporting")

    forbidden_prefixes = (
        "src.storage",
        "sqlite3",
        "streamlit",
        "rclpy",
        "tf2",
        "gazebo",
        "ultralytics",
        "torch",
        "openai",
        "anthropic",
    )

    violations: list[str] = []

    for path in sorted(root.glob("*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )

        for node in ast.walk(tree):
            imported: list[str] = []

            if isinstance(node, ast.Import):
                imported = [
                    alias.name
                    for alias in node.names
                ]

            elif (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
            ):
                imported = [node.module]

            for name in imported:
                if name.startswith(forbidden_prefixes):
                    violations.append(
                        f"{path.as_posix()}: {name}"
                    )

    assert violations == []
