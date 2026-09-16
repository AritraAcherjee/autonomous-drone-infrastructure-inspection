"""Repository tests for P16 SQLite persistence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from src.storage.models import ReviewStatus
from src.storage.repository import (
    DuplicateDefectError,
    DuplicateEvidenceError,
    SQLiteInspectionRepository,
)
from tests.storage.fixtures import (
    T0,
    T1,
    T2,
    make_defect,
    make_evidence,
    make_inspection,
    make_structure,
)


def make_initialized_repository(
    tmp_path,
) -> tuple[SQLiteInspectionRepository, int]:
    database_path = tmp_path / "p16-repository.sqlite3"

    repository = SQLiteInspectionRepository(database_path)
    repository.initialize()

    structure = repository.create_structure(
        make_structure()
    )

    inspection = repository.create_inspection(
        make_inspection(structure.structure_id)
    )

    return repository, inspection.inspection_id


def test_create_and_retrieve_structure_inspection_defect(
    tmp_path,
) -> None:
    repository, inspection_id = make_initialized_repository(
        tmp_path
    )

    defect_record = make_defect(
        inspection_id=inspection_id,
    )

    created = repository.create_defect(defect_record)
    loaded = repository.get_defect(defect_record.defect_id)

    assert loaded is not None

    assert loaded.defect_id == defect_record.defect_id
    assert loaded.inspection_id == inspection_id
    assert loaded.track_id == defect_record.track_id
    assert loaded.class_name == "Crack"
    assert loaded.confidence == 0.92

    assert loaded.x_m == 1.25
    assert loaded.y_m == 0.40
    assert loaded.z_m == 2.10

    assert loaded.coordinate_frame == "map"
    assert loaded.observation_count == 4
    assert loaded.model_version == "synthetic-test-model-v1"

    assert loaded.first_seen == T0
    assert loaded.last_seen == T2

    assert created.review_status == ReviewStatus.UNREVIEWED
    assert loaded.review_status == ReviewStatus.UNREVIEWED
    assert loaded.review_notes is None


def test_multiple_evidence_rows_are_supported_and_ordered(
    tmp_path,
) -> None:
    repository, inspection_id = make_initialized_repository(
        tmp_path
    )

    defect = repository.create_defect(
        make_defect(inspection_id=inspection_id)
    )

    later = make_evidence(
        defect_id=defect.defect_id,
        frame_id="synthetic-frame-002",
        timestamp=T2,
        bbox_x1=120.0,
        bbox_y1=80.0,
        bbox_x2=200.0,
        bbox_y2=170.0,
    )

    earlier = make_evidence(
        defect_id=defect.defect_id,
        frame_id="synthetic-frame-001",
        timestamp=T1,
    )

    repository.add_evidence(later)
    repository.add_evidence(earlier)

    evidence = repository.list_evidence(
        defect.defect_id
    )

    assert len(evidence) == 2
    assert [
        item.frame_id for item in evidence
    ] == [
        "synthetic-frame-001",
        "synthetic-frame-002",
    ]


def test_duplicate_defect_is_rejected(
    tmp_path,
) -> None:
    repository, inspection_id = make_initialized_repository(
        tmp_path
    )

    defect_record = make_defect(
        inspection_id=inspection_id,
    )

    repository.create_defect(defect_record)

    with pytest.raises(DuplicateDefectError):
        repository.create_defect(defect_record)


def test_exact_duplicate_evidence_is_rejected(
    tmp_path,
) -> None:
    repository, inspection_id = make_initialized_repository(
        tmp_path
    )

    defect = repository.create_defect(
        make_defect(inspection_id=inspection_id)
    )

    evidence = make_evidence(
        defect_id=defect.defect_id,
    )

    repository.add_evidence(evidence)

    with pytest.raises(DuplicateEvidenceError):
        repository.add_evidence(evidence)


def test_class_filter(
    tmp_path,
) -> None:
    repository, inspection_id = make_initialized_repository(
        tmp_path
    )

    repository.create_defect(
        make_defect(
            inspection_id=inspection_id,
            defect_id="synthetic-defect-001",
            class_name="Crack",
            confidence=0.92,
        )
    )

    repository.create_defect(
        make_defect(
            inspection_id=inspection_id,
            defect_id="synthetic-defect-002",
            class_name="Breakage",
            confidence=0.78,
        )
    )

    results = repository.list_defects(
        class_name="Crack"
    )

    assert [item.defect_id for item in results] == [
        "synthetic-defect-001"
    ]


def test_review_status_filter(
    tmp_path,
) -> None:
    repository, inspection_id = make_initialized_repository(
        tmp_path
    )

    first = repository.create_defect(
        make_defect(
            inspection_id=inspection_id,
            defect_id="synthetic-defect-001",
        )
    )

    repository.create_defect(
        make_defect(
            inspection_id=inspection_id,
            defect_id="synthetic-defect-002",
            class_name="Breakage",
        )
    )

    repository.set_review_status(
        first.defect_id,
        ReviewStatus.REJECTED,
    )

    results = repository.list_defects(
        review_status=ReviewStatus.REJECTED
    )

    assert [item.defect_id for item in results] == [
        "synthetic-defect-001"
    ]


def test_minimum_confidence_filter(
    tmp_path,
) -> None:
    repository, inspection_id = make_initialized_repository(
        tmp_path
    )

    repository.create_defect(
        make_defect(
            inspection_id=inspection_id,
            defect_id="synthetic-defect-001",
            confidence=0.92,
        )
    )

    repository.create_defect(
        make_defect(
            inspection_id=inspection_id,
            defect_id="synthetic-defect-002",
            confidence=0.78,
        )
    )

    results = repository.list_defects(
        min_confidence=0.90
    )

    assert [item.defect_id for item in results] == [
        "synthetic-defect-001"
    ]


def test_inspection_filter(
    tmp_path,
) -> None:
    database_path = tmp_path / "p16-inspection-filter.sqlite3"

    repository = SQLiteInspectionRepository(database_path)
    repository.initialize()

    structure = repository.create_structure(
        make_structure()
    )

    inspection_a = repository.create_inspection(
        make_inspection(structure.structure_id)
    )

    inspection_b_record = replace(
        make_inspection(structure.structure_id),
        started_at=T1,
    )

    inspection_b = repository.create_inspection(
        inspection_b_record
    )

    repository.create_defect(
        make_defect(
            inspection_id=inspection_a.inspection_id,
            defect_id="synthetic-defect-001",
        )
    )

    repository.create_defect(
        make_defect(
            inspection_id=inspection_b.inspection_id,
            defect_id="synthetic-defect-002",
        )
    )

    results = repository.list_inspection_defects(
        inspection_a.inspection_id
    )

    assert [item.defect_id for item in results] == [
        "synthetic-defect-001"
    ]


def test_combined_dashboard_filters_use_and_semantics(
    tmp_path,
) -> None:
    repository, inspection_id = make_initialized_repository(
        tmp_path
    )

    crack = repository.create_defect(
        make_defect(
            inspection_id=inspection_id,
            defect_id="synthetic-defect-001",
            class_name="Crack",
            confidence=0.92,
        )
    )

    breakage = repository.create_defect(
        make_defect(
            inspection_id=inspection_id,
            defect_id="synthetic-defect-002",
            class_name="Breakage",
            confidence=0.78,
        )
    )

    reinforcement = repository.create_defect(
        make_defect(
            inspection_id=inspection_id,
            defect_id="synthetic-defect-003",
            class_name="Exposed Reinforcement",
            confidence=0.84,
        )
    )

    repository.set_review_status(
        crack.defect_id,
        ReviewStatus.CONFIRMED,
    )

    repository.set_review_status(
        breakage.defect_id,
        ReviewStatus.REJECTED,
    )

    repository.set_review_status(
        reinforcement.defect_id,
        ReviewStatus.CONFIRMED,
    )

    results = repository.list_defects(
        inspection_id=inspection_id,
        class_name="Crack",
        review_status=ReviewStatus.CONFIRMED,
        min_confidence=0.90,
    )

    assert len(results) == 1
    assert results[0].defect_id == "synthetic-defect-001"


def test_machine_update_preserves_human_review(
    tmp_path,
) -> None:
    repository, inspection_id = make_initialized_repository(
        tmp_path
    )

    original_record = make_defect(
        inspection_id=inspection_id,
    )

    defect = repository.create_defect(
        original_record
    )

    repository.set_review_status(
        defect.defect_id,
        ReviewStatus.CONFIRMED,
        "Synthetic human review note",
    )

    updated_record = replace(
        original_record,
        confidence=0.97,
        x_m=1.50,
        y_m=0.50,
        z_m=2.25,
        observation_count=5,
        model_version="synthetic-test-model-v2",
    )

    updated = repository.update_defect(
        updated_record
    )

    assert updated.confidence == 0.97
    assert updated.x_m == 1.50
    assert updated.y_m == 0.50
    assert updated.z_m == 2.25
    assert updated.observation_count == 5
    assert updated.model_version == "synthetic-test-model-v2"

    assert updated.review_status == ReviewStatus.CONFIRMED
    assert updated.review_notes == "Synthetic human review note"


def test_list_inspections_returns_newest_first(
    tmp_path,
) -> None:
    database_path = tmp_path / "p16-list-inspections.sqlite3"

    repository = SQLiteInspectionRepository(database_path)
    repository.initialize()

    structure = repository.create_structure(
        make_structure()
    )

    first = repository.create_inspection(
        make_inspection(structure.structure_id)
    )

    second_record = replace(
        make_inspection(structure.structure_id),
        started_at=T1,
    )

    second = repository.create_inspection(
        second_record
    )

    inspections = repository.list_inspections()

    assert [
        item.inspection_id for item in inspections
    ] == [
        second.inspection_id,
        first.inspection_id,
    ]
