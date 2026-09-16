"""Service-layer tests for the frozen P16 application boundary."""

from __future__ import annotations

from dataclasses import fields, replace

from src.storage.models import (
    MappedDefectRecord,
    ReviewStatus,
)
from src.storage.service import InspectionService
from tests.storage.fixtures import (
    make_defect,
    make_evidence,
    make_inspection,
    make_structure,
)


def make_initialized_service(
    tmp_path,
) -> tuple[InspectionService, int]:
    database_path = tmp_path / "p16-service.sqlite3"

    service = InspectionService.from_database_path(
        database_path
    )
    service.initialize()

    structure = service.create_structure(
        make_structure()
    )

    inspection = service.create_inspection(
        make_inspection(structure.structure_id)
    )

    return service, inspection.inspection_id


def test_machine_ingest_starts_unreviewed(
    tmp_path,
) -> None:
    service, inspection_id = make_initialized_service(
        tmp_path
    )

    defect = service.ingest_mapped_defect(
        make_defect(inspection_id=inspection_id)
    )

    assert defect.review_status == ReviewStatus.UNREVIEWED
    assert defect.review_notes is None


def test_human_review_updates_through_service(
    tmp_path,
) -> None:
    service, inspection_id = make_initialized_service(
        tmp_path
    )

    defect = service.ingest_mapped_defect(
        make_defect(inspection_id=inspection_id)
    )

    confirmed = service.set_review_status(
        defect.defect_id,
        ReviewStatus.CONFIRMED,
        "Synthetic confirmed review",
    )

    assert confirmed.review_status == ReviewStatus.CONFIRMED
    assert confirmed.review_notes == "Synthetic confirmed review"

    investigation = service.set_review_status(
        defect.defect_id,
        ReviewStatus.NEEDS_INVESTIGATION,
        "Synthetic investigation review",
    )

    assert (
        investigation.review_status
        == ReviewStatus.NEEDS_INVESTIGATION
    )
    assert (
        investigation.review_notes
        == "Synthetic investigation review"
    )


def test_service_exposes_evidence_and_filters(
    tmp_path,
) -> None:
    service, inspection_id = make_initialized_service(
        tmp_path
    )

    defect = service.ingest_mapped_defect(
        make_defect(inspection_id=inspection_id)
    )

    service.add_evidence(
        make_evidence(defect_id=defect.defect_id)
    )

    service.set_review_status(
        defect.defect_id,
        ReviewStatus.NEEDS_INVESTIGATION,
    )

    evidence = service.list_evidence(
        defect.defect_id
    )

    results = service.list_defects(
        inspection_id=inspection_id,
        class_name="Crack",
        review_status=ReviewStatus.NEEDS_INVESTIGATION,
        min_confidence=0.90,
    )

    assert len(evidence) == 1
    assert evidence[0].defect_id == defect.defect_id

    assert len(results) == 1
    assert results[0].defect_id == defect.defect_id


def test_machine_service_update_preserves_human_review(
    tmp_path,
) -> None:
    service, inspection_id = make_initialized_service(
        tmp_path
    )

    original = make_defect(
        inspection_id=inspection_id
    )

    defect = service.ingest_mapped_defect(original)

    service.set_review_status(
        defect.defect_id,
        ReviewStatus.CONFIRMED,
        "Synthetic human decision",
    )

    machine_update = replace(
        original,
        confidence=0.96,
        x_m=1.45,
        y_m=0.55,
        z_m=2.30,
        observation_count=6,
        model_version="synthetic-test-model-v2",
    )

    updated = service.update_mapped_defect(
        machine_update
    )

    assert updated.confidence == 0.96
    assert updated.x_m == 1.45
    assert updated.y_m == 0.55
    assert updated.z_m == 2.30
    assert updated.observation_count == 6

    assert updated.review_status == ReviewStatus.CONFIRMED
    assert updated.review_notes == "Synthetic human decision"


def test_mapped_defect_boundary_cannot_supply_review_fields() -> None:
    names = {
        field.name
        for field in fields(MappedDefectRecord)
    }

    assert "review_status" not in names
    assert "review_notes" not in names


def test_service_lists_inspections(
    tmp_path,
) -> None:
    service, inspection_id = make_initialized_service(
        tmp_path
    )

    inspections = service.list_inspections()

    assert len(inspections) == 1
    assert inspections[0].inspection_id == inspection_id
    assert inspections[0].status.value == "REVIEW"
    assert inspections[0].system_version == "p16-tuesday-demo"
