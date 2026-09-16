"""SQLite schema/backstop constraint tests for P16."""

from __future__ import annotations

import sqlite3

import pytest

from src.storage.repository import SQLiteInspectionRepository
from tests.storage.fixtures import (
    make_defect,
    make_evidence,
    make_inspection,
    make_structure,
)


def build_seeded_database(tmp_path):
    database_path = tmp_path / "p16-schema.sqlite3"

    repository = SQLiteInspectionRepository(database_path)
    repository.initialize()

    structure = repository.create_structure(
        make_structure()
    )

    inspection = repository.create_inspection(
        make_inspection(structure.structure_id)
    )

    defect = repository.create_defect(
        make_defect(
            inspection_id=inspection.inspection_id
        )
    )

    repository.add_evidence(
        make_evidence(
            defect_id=defect.defect_id
        )
    )

    return (
        database_path,
        structure.structure_id,
        inspection.inspection_id,
        defect.defect_id,
    )


def connect(database_path):
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def defect_values(
    *,
    defect_id,
    inspection_id,
    confidence=0.80,
    observation_count=1,
    review_status="UNREVIEWED",
):
    return (
        defect_id,
        inspection_id,
        None,
        "Crack",
        confidence,
        1.0,
        2.0,
        3.0,
        "map",
        observation_count,
        "2026-09-16T16:00:00Z",
        "2026-09-16T16:00:04Z",
        "schema-test-model",
        review_status,
        None,
        "2026-09-16T16:00:05Z",
        "2026-09-16T16:00:05Z",
    )


DEFECT_INSERT = """
INSERT INTO defects (
    defect_id,
    inspection_id,
    track_id,
    class_name,
    confidence,
    x_m,
    y_m,
    z_m,
    coordinate_frame,
    observation_count,
    first_seen,
    last_seen,
    model_version,
    review_status,
    review_notes,
    created_at,
    updated_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def test_repository_connections_enable_foreign_keys(
    tmp_path,
) -> None:
    database_path = tmp_path / "foreign-keys.sqlite3"

    repository = SQLiteInspectionRepository(database_path)
    repository.initialize()

    connection = repository._connect()

    try:
        enabled = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
    finally:
        connection.close()

    assert enabled == 1


@pytest.mark.parametrize(
    "confidence",
    [
        -0.01,
        1.01,
    ],
)
def test_schema_rejects_invalid_defect_confidence(
    tmp_path,
    confidence,
) -> None:
    (
        database_path,
        _,
        inspection_id,
        _,
    ) = build_seeded_database(tmp_path)

    connection = connect(database_path)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                DEFECT_INSERT,
                defect_values(
                    defect_id="schema-invalid-confidence",
                    inspection_id=inspection_id,
                    confidence=confidence,
                ),
            )
    finally:
        connection.close()


def test_schema_rejects_zero_observation_count(
    tmp_path,
) -> None:
    (
        database_path,
        _,
        inspection_id,
        _,
    ) = build_seeded_database(tmp_path)

    connection = connect(database_path)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                DEFECT_INSERT,
                defect_values(
                    defect_id="schema-invalid-observation-count",
                    inspection_id=inspection_id,
                    observation_count=0,
                ),
            )
    finally:
        connection.close()


def test_schema_rejects_invalid_review_status(
    tmp_path,
) -> None:
    (
        database_path,
        _,
        inspection_id,
        _,
    ) = build_seeded_database(tmp_path)

    connection = connect(database_path)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                DEFECT_INSERT,
                defect_values(
                    defect_id="schema-invalid-review",
                    inspection_id=inspection_id,
                    review_status="AUTO_CONFIRMED",
                ),
            )
    finally:
        connection.close()


def test_schema_rejects_invalid_inspection_status(
    tmp_path,
) -> None:
    (
        database_path,
        structure_id,
        _,
        _,
    ) = build_seeded_database(tmp_path)

    connection = connect(database_path)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO inspections (
                    structure_id,
                    started_at,
                    completed_at,
                    status,
                    system_version,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    structure_id,
                    "2026-09-16T17:00:00Z",
                    None,
                    "INVALID_STATUS",
                    "schema-test",
                    None,
                ),
            )
    finally:
        connection.close()


def test_schema_rejects_missing_inspection_foreign_key(
    tmp_path,
) -> None:
    (
        database_path,
        _,
        _,
        _,
    ) = build_seeded_database(tmp_path)

    connection = connect(database_path)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                DEFECT_INSERT,
                defect_values(
                    defect_id="schema-invalid-fk",
                    inspection_id=999999,
                ),
            )
    finally:
        connection.close()


def test_schema_rejects_invalid_evidence_confidence(
    tmp_path,
) -> None:
    (
        database_path,
        _,
        _,
        defect_id,
    ) = build_seeded_database(tmp_path)

    connection = connect(database_path)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO evidence (
                    defect_id,
                    frame_id,
                    timestamp,
                    image_path,
                    crop_path,
                    confidence,
                    bbox_x1,
                    bbox_y1,
                    bbox_x2,
                    bbox_y2
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    defect_id,
                    "schema-invalid-evidence-frame",
                    "2026-09-16T16:00:03Z",
                    None,
                    None,
                    1.50,
                    10.0,
                    20.0,
                    30.0,
                    40.0,
                ),
            )
    finally:
        connection.close()


def test_structure_delete_is_restricted_when_inspection_exists(
    tmp_path,
) -> None:
    (
        database_path,
        structure_id,
        _,
        _,
    ) = build_seeded_database(tmp_path)

    connection = connect(database_path)

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM structures WHERE structure_id = ?",
                (structure_id,),
            )
    finally:
        connection.close()


def test_inspection_delete_cascades_defects_and_evidence(
    tmp_path,
) -> None:
    (
        database_path,
        _,
        inspection_id,
        defect_id,
    ) = build_seeded_database(tmp_path)

    connection = connect(database_path)

    try:
        connection.execute(
            "DELETE FROM inspections WHERE inspection_id = ?",
            (inspection_id,),
        )
        connection.commit()

        defect_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM defects
            WHERE defect_id = ?
            """,
            (defect_id,),
        ).fetchone()[0]

        evidence_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM evidence
            WHERE defect_id = ?
            """,
            (defect_id,),
        ).fetchone()[0]

        assert defect_count == 0
        assert evidence_count == 0
    finally:
        connection.close()
