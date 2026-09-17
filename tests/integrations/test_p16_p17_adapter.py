from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.integrations.p16_p17_adapter import (
    P16P17AdapterError,
    build_inspection_report,
    defect_to_report,
    evidence_to_report,
    inspection_to_report,
    structure_to_report,
)
from src.reporting import render_report
from src.storage.models import (
    Defect,
    Evidence,
    Inspection,
    InspectionStatus,
    ReviewStatus,
    Structure,
)


T0 = datetime(2026, 9, 17, 12, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 9, 17, 12, 1, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 17, 12, 2, 0, tzinfo=timezone.utc)


def make_structure() -> Structure:
    return Structure(
        structure_id=7,
        name="Synthetic Bridge",
        description="Canonical P16 integration fixture",
        location_text="Synthetic location",
        created_at=T0,
    )


def make_inspection() -> Inspection:
    return Inspection(
        inspection_id=11,
        structure_id=7,
        started_at=T0,
        completed_at=T2,
        status=InspectionStatus.COMPLETED,
        system_version="aegis-system-v1",
        notes="Persisted inspection note.",
    )


def make_defect(
    *,
    defect_id: str = "P15D-a",
    inspection_id: int = 11,
    review_status: ReviewStatus = ReviewStatus.CONFIRMED,
) -> Defect:
    return Defect(
        defect_id=defect_id,
        inspection_id=inspection_id,
        track_id="track-17",
        class_name="Crack",
        confidence=0.923456789,
        x_m=1.2345678901234567,
        y_m=-2.5,
        z_m=3.75,
        coordinate_frame="map",
        observation_count=7,
        first_seen=T1,
        last_seen=T2,
        model_version="DET-FINAL-v1",
        review_status=review_status,
        review_notes="Persisted human review.",
        created_at=T1,
        updated_at=T2,
    )


def make_evidence(
    *,
    evidence_id: int = 1,
    defect_id: str = "P15D-a",
    timestamp: datetime = T1,
) -> Evidence:
    return Evidence(
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


class ReadOnlyServiceSpy:
    """P16 read-boundary test double using canonical P16 DTOs."""

    def __init__(
        self,
        *,
        inspection: Inspection | None = None,
        structure: Structure | None = None,
        defects: tuple[Defect, ...] = (),
        evidence_by_defect: dict[str, tuple[Evidence, ...]] | None = None,
    ) -> None:
        self.inspection = inspection
        self.structure = structure
        self.defects = defects
        self.evidence_by_defect = evidence_by_defect or {}

        self.read_calls: list[tuple[str, object]] = []
        self.write_calls: list[str] = []

    def get_inspection(
        self,
        inspection_id: int,
    ) -> Inspection | None:
        self.read_calls.append(("get_inspection", inspection_id))

        if (
            self.inspection is not None
            and self.inspection.inspection_id == inspection_id
        ):
            return self.inspection

        return None

    def get_structure(
        self,
        structure_id: int,
    ) -> Structure | None:
        self.read_calls.append(("get_structure", structure_id))

        if (
            self.structure is not None
            and self.structure.structure_id == structure_id
        ):
            return self.structure

        return None

    def list_inspection_defects(
        self,
        inspection_id: int,
    ) -> list[Defect]:
        self.read_calls.append(
            ("list_inspection_defects", inspection_id)
        )

        return list(self.defects)

    def list_evidence(
        self,
        defect_id: str,
    ) -> list[Evidence]:
        self.read_calls.append(("list_evidence", defect_id))

        return list(
            self.evidence_by_defect.get(
                defect_id,
                (),
            )
        )

    def _write_forbidden(self, name: str) -> None:
        self.write_calls.append(name)

        raise AssertionError(
            f"report assembly attempted forbidden write: {name}"
        )

    def initialize(self) -> None:
        self._write_forbidden("initialize")

    def create_structure(self, *args, **kwargs):
        self._write_forbidden("create_structure")

    def create_inspection(self, *args, **kwargs):
        self._write_forbidden("create_inspection")

    def ingest_mapped_defect(self, *args, **kwargs):
        self._write_forbidden("ingest_mapped_defect")

    def update_mapped_defect(self, *args, **kwargs):
        self._write_forbidden("update_mapped_defect")

    def add_evidence(self, *args, **kwargs):
        self._write_forbidden("add_evidence")

    def set_review_status(self, *args, **kwargs):
        self._write_forbidden("set_review_status")


def make_service(
    *,
    defects: tuple[Defect, ...] = (),
    evidence_by_defect: dict[str, tuple[Evidence, ...]] | None = None,
) -> ReadOnlyServiceSpy:
    return ReadOnlyServiceSpy(
        inspection=make_inspection(),
        structure=make_structure(),
        defects=defects,
        evidence_by_defect=evidence_by_defect,
    )


def test_structure_conversion_preserves_source_values() -> None:
    source = make_structure()

    result = structure_to_report(source)

    assert result.structure_id == source.structure_id
    assert result.name == source.name
    assert result.description == source.description
    assert result.location_text == source.location_text
    assert result.created_at == source.created_at


def test_inspection_conversion_preserves_source_values() -> None:
    source = make_inspection()

    result = inspection_to_report(source)

    assert result.inspection_id == source.inspection_id
    assert result.structure_id == source.structure_id
    assert result.started_at == source.started_at
    assert result.completed_at == source.completed_at
    assert result.status == source.status.value
    assert result.system_version == source.system_version
    assert result.notes == source.notes


def test_evidence_conversion_preserves_source_values() -> None:
    source = make_evidence()

    result = evidence_to_report(source)

    assert result.evidence_id == source.evidence_id
    assert result.defect_id == source.defect_id
    assert result.frame_id == source.frame_id
    assert result.timestamp == source.timestamp
    assert result.image_path == source.image_path
    assert result.crop_path == source.crop_path
    assert result.confidence == source.confidence
    assert result.bbox_x1 == source.bbox_x1
    assert result.bbox_y1 == source.bbox_y1
    assert result.bbox_x2 == source.bbox_x2
    assert result.bbox_y2 == source.bbox_y2


def test_defect_conversion_preserves_machine_and_review_values() -> None:
    source = make_defect()
    evidence = evidence_to_report(make_evidence())

    result = defect_to_report(
        source,
        (evidence,),
    )

    assert result.defect_id == source.defect_id
    assert result.inspection_id == source.inspection_id
    assert result.track_id == source.track_id
    assert result.class_name == source.class_name
    assert result.confidence == source.confidence
    assert result.x_m == source.x_m
    assert result.y_m == source.y_m
    assert result.z_m == source.z_m
    assert result.coordinate_frame == source.coordinate_frame
    assert result.observation_count == source.observation_count
    assert result.first_seen == source.first_seen
    assert result.last_seen == source.last_seen
    assert result.model_version == source.model_version
    assert result.review_status == source.review_status.value
    assert result.review_notes == source.review_notes
    assert result.created_at == source.created_at
    assert result.updated_at == source.updated_at
    assert result.evidence == (evidence,)


def test_zero_defect_adapter_path() -> None:
    service = make_service()

    report = build_inspection_report(
        service,  # type: ignore[arg-type]
        11,
    )

    assert report.structure.structure_id == 7
    assert report.inspection.inspection_id == 11
    assert report.defects == ()

    rendered = render_report(report)

    assert "- Total Defects: 0" in rendered
    assert "- Inspection Status: COMPLETED" in rendered


def test_adapter_collects_only_each_defects_evidence() -> None:
    defect_a = make_defect(defect_id="P15D-a")
    defect_b = make_defect(defect_id="P15D-b")

    evidence_a = make_evidence(
        evidence_id=1,
        defect_id="P15D-a",
    )
    evidence_b = make_evidence(
        evidence_id=2,
        defect_id="P15D-b",
    )

    service = make_service(
        defects=(defect_b, defect_a),
        evidence_by_defect={
            "P15D-a": (evidence_a,),
            "P15D-b": (evidence_b,),
        },
    )

    report = build_inspection_report(
        service,  # type: ignore[arg-type]
        11,
    )

    assert [
        defect.defect_id
        for defect in report.defects
    ] == [
        "P15D-a",
        "P15D-b",
    ]

    assert [
        evidence.defect_id
        for evidence in report.defects[0].evidence
    ] == [
        "P15D-a",
    ]

    assert [
        evidence.defect_id
        for evidence in report.defects[1].evidence
    ] == [
        "P15D-b",
    ]


def test_adapter_orders_evidence_by_timestamp_then_id() -> None:
    defect = make_defect()

    late = make_evidence(
        evidence_id=3,
        timestamp=T2,
    )
    same_time_two = make_evidence(
        evidence_id=2,
        timestamp=T1,
    )
    same_time_one = make_evidence(
        evidence_id=1,
        timestamp=T1,
    )

    service = make_service(
        defects=(defect,),
        evidence_by_defect={
            defect.defect_id: (
                late,
                same_time_two,
                same_time_one,
            )
        },
    )

    report = build_inspection_report(
        service,  # type: ignore[arg-type]
        11,
    )

    assert [
        evidence.evidence_id
        for evidence in report.defects[0].evidence
    ] == [
        1,
        2,
        3,
    ]


def test_missing_inspection_fails_closed() -> None:
    service = ReadOnlyServiceSpy(
        inspection=None,
        structure=make_structure(),
    )

    with pytest.raises(
        P16P17AdapterError,
        match="does not exist",
    ):
        build_inspection_report(
            service,  # type: ignore[arg-type]
            11,
        )


def test_missing_structure_fails_closed() -> None:
    service = ReadOnlyServiceSpy(
        inspection=make_inspection(),
        structure=None,
    )

    with pytest.raises(
        P16P17AdapterError,
        match="structure",
    ):
        build_inspection_report(
            service,  # type: ignore[arg-type]
            11,
        )


def test_cross_inspection_defect_fails_closed() -> None:
    wrong = make_defect(
        defect_id="P15D-wrong",
        inspection_id=999,
    )

    service = make_service(
        defects=(wrong,),
    )

    with pytest.raises(
        P16P17AdapterError,
        match="another inspection",
    ):
        build_inspection_report(
            service,  # type: ignore[arg-type]
            11,
        )


def test_cross_defect_evidence_fails_closed() -> None:
    defect = make_defect(
        defect_id="P15D-a",
    )

    wrong_evidence = make_evidence(
        evidence_id=1,
        defect_id="P15D-other",
    )

    service = make_service(
        defects=(defect,),
        evidence_by_defect={
            "P15D-a": (wrong_evidence,),
        },
    )

    with pytest.raises(
        P16P17AdapterError,
        match="another defect",
    ):
        build_inspection_report(
            service,  # type: ignore[arg-type]
            11,
        )


@pytest.mark.parametrize(
    "inspection_id",
    [
        0,
        -1,
        True,
        1.5,
        "11",
    ],
)
def test_invalid_inspection_id_fails_closed(
    inspection_id: object,
) -> None:
    service = make_service()

    with pytest.raises(
        P16P17AdapterError,
        match="positive integer",
    ):
        build_inspection_report(
            service,  # type: ignore[arg-type]
            inspection_id,  # type: ignore[arg-type]
        )


def test_report_assembly_performs_no_persistence_writes() -> None:
    defect = make_defect()
    evidence = make_evidence()

    service = make_service(
        defects=(defect,),
        evidence_by_defect={
            defect.defect_id: (evidence,),
        },
    )

    report = build_inspection_report(
        service,  # type: ignore[arg-type]
        11,
    )

    assert len(report.defects) == 1
    assert service.write_calls == []


def test_adapter_uses_only_frozen_read_methods() -> None:
    defect = make_defect()
    evidence = make_evidence()

    service = make_service(
        defects=(defect,),
        evidence_by_defect={
            defect.defect_id: (evidence,),
        },
    )

    build_inspection_report(
        service,  # type: ignore[arg-type]
        11,
    )

    assert service.read_calls == [
        ("get_inspection", 11),
        ("get_structure", 7),
        ("list_inspection_defects", 11),
        ("list_evidence", "P15D-a"),
    ]


def test_canonical_source_values_survive_adapter_and_renderer() -> None:
    defect = make_defect()
    evidence = make_evidence()

    service = make_service(
        defects=(defect,),
        evidence_by_defect={
            defect.defect_id: (evidence,),
        },
    )

    rendered = render_report(
        build_inspection_report(
            service,  # type: ignore[arg-type]
            11,
        )
    )

    expected = (
        "- Inspection Status: COMPLETED",
        "- Class: Crack",
        "- Confidence: 0.923456789",
        "- X (m): 1.2345678901234567",
        "- Y (m): -2.5",
        "- Z (m): 3.75",
        "- Observation Count: 7",
        "- Model Version: DET-FINAL-v1",
        "- Review Status: CONFIRMED",
        "- Review Notes: Persisted human review.",
        "- Image Path: evidence/frame-001.png",
        "- Crop Path: evidence/crop-001.png",
        "- Bounding Box X1: 10.125",
        "- Bounding Box Y1: 20.25",
        "- Bounding Box X2: 30.5",
        "- Bounding Box Y2: 40.75",
    )

    for value in expected:
        assert value in rendered


def test_adapter_does_not_infer_severity_dimensions_or_safety() -> None:
    defect = make_defect()
    service = make_service(
        defects=(defect,),
    )

    rendered = render_report(
        build_inspection_report(
            service,  # type: ignore[arg-type]
            11,
        )
    ).lower()

    assert "severity:" not in rendered
    assert "dimension:" not in rendered
    assert "structurally safe" not in rendered
    assert "structurally unsafe" not in rendered
