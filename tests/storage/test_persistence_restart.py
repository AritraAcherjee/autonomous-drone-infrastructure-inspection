"""On-disk restart persistence test for P16 SQLite storage."""

from __future__ import annotations

from src.storage.models import ReviewStatus
from src.storage.service import InspectionService
from tests.storage.fixtures import (
    make_defect,
    make_evidence,
    make_inspection,
    make_structure,
)


def test_p16_data_survives_service_restart(
    tmp_path,
) -> None:
    database_path = tmp_path / "p16-restart.sqlite3"

    service_a = InspectionService.from_database_path(
        database_path
    )
    service_a.initialize()

    structure = service_a.create_structure(
        make_structure()
    )

    inspection = service_a.create_inspection(
        make_inspection(structure.structure_id)
    )

    defect = service_a.ingest_mapped_defect(
        make_defect(
            inspection_id=inspection.inspection_id
        )
    )

    evidence = service_a.add_evidence(
        make_evidence(
            defect_id=defect.defect_id
        )
    )

    reviewed = service_a.set_review_status(
        defect.defect_id,
        ReviewStatus.CONFIRMED,
        "Synthetic persisted review",
    )

    assert database_path.exists()
    assert reviewed.review_status == ReviewStatus.CONFIRMED
    assert evidence.evidence_id >= 1

    # Construct a completely fresh service/repository instance
    # against the same on-disk SQLite file.
    service_b = InspectionService.from_database_path(
        database_path
    )

    loaded_structure = service_b.get_structure(
        structure.structure_id
    )
    loaded_inspection = service_b.get_inspection(
        inspection.inspection_id
    )
    loaded_defect = service_b.get_defect(
        defect.defect_id
    )
    loaded_evidence = service_b.list_evidence(
        defect.defect_id
    )

    assert loaded_structure is not None
    assert loaded_structure.name == (
        "P16 Synthetic Concrete Test Structure"
    )

    assert loaded_inspection is not None
    assert loaded_inspection.system_version == (
        "p16-tuesday-demo"
    )

    assert loaded_defect is not None
    assert loaded_defect.defect_id == (
        "synthetic-defect-001"
    )
    assert loaded_defect.coordinate_frame == "map"
    assert loaded_defect.x_m == 1.25
    assert loaded_defect.y_m == 0.40
    assert loaded_defect.z_m == 2.10
    assert loaded_defect.observation_count == 4
    assert loaded_defect.model_version == (
        "synthetic-test-model-v1"
    )

    assert loaded_defect.review_status == (
        ReviewStatus.CONFIRMED
    )
    assert loaded_defect.review_notes == (
        "Synthetic persisted review"
    )

    assert len(loaded_evidence) == 1
    assert loaded_evidence[0].frame_id == (
        "synthetic-frame-001"
    )
    assert loaded_evidence[0].defect_id == (
        defect.defect_id
    )
