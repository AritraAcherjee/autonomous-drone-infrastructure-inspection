"""SQLite repository for the P16 inspection persistence layer."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import (
    Defect,
    Evidence,
    EvidenceCreate,
    Inspection,
    InspectionCreate,
    InspectionStatus,
    MappedDefectRecord,
    ReviewStatus,
    Structure,
    StructureCreate,
)
from .schema import load_schema_sql
from .validation import (
    ValidationError,
    validate_confidence,
    validate_evidence_create,
    validate_inspection_create,
    validate_mapped_defect,
    validate_review_status,
    validate_structure_create,
)


class DuplicateDefectError(RuntimeError):
    """Raised when create_defect receives an existing defect_id."""


class DefectNotFoundError(LookupError):
    """Raised when an operation requires a defect that does not exist."""


class DuplicateEvidenceError(RuntimeError):
    """Raised when exact evidence is inserted more than once."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _datetime_to_text(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _text_to_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _row_to_defect(row: sqlite3.Row) -> Defect:
    return Defect(
        defect_id=row["defect_id"],
        inspection_id=row["inspection_id"],
        track_id=row["track_id"],
        class_name=row["class_name"],
        confidence=row["confidence"],
        x_m=row["x_m"],
        y_m=row["y_m"],
        z_m=row["z_m"],
        coordinate_frame=row["coordinate_frame"],
        observation_count=row["observation_count"],
        first_seen=_text_to_datetime(row["first_seen"]),
        last_seen=_text_to_datetime(row["last_seen"]),
        model_version=row["model_version"],
        review_status=ReviewStatus(row["review_status"]),
        review_notes=row["review_notes"],
        created_at=_text_to_datetime(row["created_at"]),
        updated_at=_text_to_datetime(row["updated_at"]),
    )


def _row_to_evidence(row: sqlite3.Row) -> Evidence:
    return Evidence(
        evidence_id=row["evidence_id"],
        defect_id=row["defect_id"],
        frame_id=row["frame_id"],
        timestamp=_text_to_datetime(row["timestamp"]),
        image_path=row["image_path"],
        crop_path=row["crop_path"],
        confidence=row["confidence"],
        bbox_x1=row["bbox_x1"],
        bbox_y1=row["bbox_y1"],
        bbox_x2=row["bbox_x2"],
        bbox_y2=row["bbox_y2"],
    )


class SQLiteInspectionRepository:
    """SQLite persistence repository for the P16 product layer."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def _connect(self) -> sqlite3.Connection:
        if str(self.database_path) != ":memory:":
            self.database_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        connection = sqlite3.connect(str(self.database_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]

        if foreign_keys != 1:
            connection.close()
            raise RuntimeError(
                "SQLite foreign key enforcement could not be enabled"
            )

        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a transaction-managed connection and always close it."""

        connection = self._connect()

        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create the frozen Tuesday P16 schema if it does not exist."""

        with self._connection() as connection:
            connection.executescript(load_schema_sql())

    def create_structure(
        self,
        record: StructureCreate,
    ) -> Structure:
        """Persist and return a new Structure."""

        validate_structure_create(record)
        created_at = _utc_now()

        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO structures (
                    name,
                    description,
                    location_text,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    record.name.strip(),
                    record.description,
                    record.location_text,
                    _datetime_to_text(created_at),
                ),
            )
            structure_id = int(cursor.lastrowid)

        return Structure(
            structure_id=structure_id,
            name=record.name.strip(),
            description=record.description,
            location_text=record.location_text,
            created_at=created_at,
        )

    def get_structure(
        self,
        structure_id: int,
    ) -> Structure | None:
        """Return one structure or None when it does not exist."""

        if (
            isinstance(structure_id, bool)
            or not isinstance(structure_id, int)
            or structure_id < 1
        ):
            raise ValidationError(
                "structure_id must be a positive integer"
            )

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    structure_id,
                    name,
                    description,
                    location_text,
                    created_at
                FROM structures
                WHERE structure_id = ?
                """,
                (structure_id,),
            ).fetchone()

        if row is None:
            return None

        return Structure(
            structure_id=row["structure_id"],
            name=row["name"],
            description=row["description"],
            location_text=row["location_text"],
            created_at=_text_to_datetime(row["created_at"]),
        )

    def create_inspection(
        self,
        record: InspectionCreate,
    ) -> Inspection:
        """Persist and return a new Inspection."""

        validate_inspection_create(record)

        with self._connection() as connection:
            cursor = connection.execute(
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
                    record.structure_id,
                    _datetime_to_text(record.started_at),
                    (
                        _datetime_to_text(record.completed_at)
                        if record.completed_at is not None
                        else None
                    ),
                    record.status.value,
                    record.system_version.strip(),
                    record.notes,
                ),
            )
            inspection_id = int(cursor.lastrowid)

        return Inspection(
            inspection_id=inspection_id,
            structure_id=record.structure_id,
            started_at=record.started_at.astimezone(timezone.utc),
            completed_at=(
                record.completed_at.astimezone(timezone.utc)
                if record.completed_at is not None
                else None
            ),
            status=record.status,
            system_version=record.system_version.strip(),
            notes=record.notes,
        )

    def get_inspection(
        self,
        inspection_id: int,
    ) -> Inspection | None:
        """Return one inspection or None when it does not exist."""

        if (
            isinstance(inspection_id, bool)
            or not isinstance(inspection_id, int)
            or inspection_id < 1
        ):
            raise ValidationError(
                "inspection_id must be a positive integer"
            )

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT
                    inspection_id,
                    structure_id,
                    started_at,
                    completed_at,
                    status,
                    system_version,
                    notes
                FROM inspections
                WHERE inspection_id = ?
                """,
                (inspection_id,),
            ).fetchone()

        if row is None:
            return None

        return Inspection(
            inspection_id=row["inspection_id"],
            structure_id=row["structure_id"],
            started_at=_text_to_datetime(row["started_at"]),
            completed_at=(
                _text_to_datetime(row["completed_at"])
                if row["completed_at"] is not None
                else None
            ),
            status=InspectionStatus(row["status"]),
            system_version=row["system_version"],
            notes=row["notes"],
        )

    def list_inspections(
        self,
    ) -> list[Inspection]:
        """Return inspections in deterministic newest-first order."""

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    inspection_id,
                    structure_id,
                    started_at,
                    completed_at,
                    status,
                    system_version,
                    notes
                FROM inspections
                ORDER BY started_at DESC, inspection_id DESC
                """
            ).fetchall()

        return [
            Inspection(
                inspection_id=row["inspection_id"],
                structure_id=row["structure_id"],
                started_at=_text_to_datetime(row["started_at"]),
                completed_at=(
                    _text_to_datetime(row["completed_at"])
                    if row["completed_at"] is not None
                    else None
                ),
                status=InspectionStatus(row["status"]),
                system_version=row["system_version"],
                notes=row["notes"],
            )
            for row in rows
        ]

    def create_defect(
        self,
        record: MappedDefectRecord,
    ) -> Defect:
        """Persist an already-decided mapped defect."""

        validate_mapped_defect(record)

        if self.get_defect(record.defect_id) is not None:
            raise DuplicateDefectError(
                f"defect_id already exists: {record.defect_id}"
            )

        now = _utc_now()

        try:
            with self._connection() as connection:
                connection.execute(
                    """
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
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'UNREVIEWED', NULL, ?, ?
                    )
                    """,
                    (
                        record.defect_id.strip(),
                        record.inspection_id,
                        record.track_id,
                        record.class_name.strip(),
                        float(record.confidence),
                        float(record.x_m),
                        float(record.y_m),
                        float(record.z_m),
                        record.coordinate_frame.strip(),
                        record.observation_count,
                        _datetime_to_text(record.first_seen),
                        _datetime_to_text(record.last_seen),
                        record.model_version.strip(),
                        _datetime_to_text(now),
                        _datetime_to_text(now),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise RuntimeError(
                f"Could not create defect {record.defect_id}: {exc}"
            ) from exc

        defect = self.get_defect(record.defect_id)

        if defect is None:
            raise RuntimeError(
                f"Defect creation could not be verified: {record.defect_id}"
            )

        return defect

    def update_defect(
        self,
        record: MappedDefectRecord,
    ) -> Defect:
        """Update machine-produced fields without changing human review."""

        validate_mapped_defect(record)

        existing = self.get_defect(record.defect_id)

        if existing is None:
            raise DefectNotFoundError(record.defect_id)

        if existing.inspection_id != record.inspection_id:
            raise ValidationError(
                "inspection_id cannot change for an existing defect"
            )

        updated_at = _utc_now()

        with self._connection() as connection:
            connection.execute(
                """
                UPDATE defects
                SET
                    track_id = ?,
                    class_name = ?,
                    confidence = ?,
                    x_m = ?,
                    y_m = ?,
                    z_m = ?,
                    coordinate_frame = ?,
                    observation_count = ?,
                    first_seen = ?,
                    last_seen = ?,
                    model_version = ?,
                    updated_at = ?
                WHERE defect_id = ?
                """,
                (
                    record.track_id,
                    record.class_name.strip(),
                    float(record.confidence),
                    float(record.x_m),
                    float(record.y_m),
                    float(record.z_m),
                    record.coordinate_frame.strip(),
                    record.observation_count,
                    _datetime_to_text(record.first_seen),
                    _datetime_to_text(record.last_seen),
                    record.model_version.strip(),
                    _datetime_to_text(updated_at),
                    record.defect_id.strip(),
                ),
            )

        updated = self.get_defect(record.defect_id)

        if updated is None:
            raise RuntimeError(
                f"Defect update could not be verified: {record.defect_id}"
            )

        return updated

    def get_defect(
        self,
        defect_id: str,
    ) -> Defect | None:
        """Return one persisted defect."""

        if not isinstance(defect_id, str) or not defect_id.strip():
            raise ValidationError(
                "defect_id must be a non-empty string"
            )

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM defects
                WHERE defect_id = ?
                """,
                (defect_id.strip(),),
            ).fetchone()

        if row is None:
            return None

        return _row_to_defect(row)

    def list_defects(
        self,
        *,
        inspection_id: int | None = None,
        class_name: str | None = None,
        review_status: ReviewStatus | None = None,
        min_confidence: float | None = None,
    ) -> list[Defect]:
        """List defects using the frozen Tuesday dashboard filters."""

        clauses: list[str] = []
        parameters: list[object] = []

        if inspection_id is not None:
            if (
                isinstance(inspection_id, bool)
                or not isinstance(inspection_id, int)
                or inspection_id < 1
            ):
                raise ValidationError(
                    "inspection_id must be a positive integer"
                )
            clauses.append("inspection_id = ?")
            parameters.append(inspection_id)

        if class_name is not None:
            if not isinstance(class_name, str) or not class_name.strip():
                raise ValidationError(
                    "class_name must be a non-empty string"
                )
            clauses.append("class_name = ?")
            parameters.append(class_name.strip())

        if review_status is not None:
            validate_review_status(review_status)
            clauses.append("review_status = ?")
            parameters.append(review_status.value)

        if min_confidence is not None:
            validate_confidence(
                min_confidence,
                "min_confidence",
            )
            clauses.append("confidence >= ?")
            parameters.append(float(min_confidence))

        query = "SELECT * FROM defects"

        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        query += " ORDER BY defect_id ASC"

        with self._connection() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [_row_to_defect(row) for row in rows]

    def list_inspection_defects(
        self,
        inspection_id: int,
    ) -> list[Defect]:
        """List all defects belonging to one inspection."""

        return self.list_defects(
            inspection_id=inspection_id,
        )

    def set_review_status(
        self,
        defect_id: str,
        status: ReviewStatus,
        notes: str | None = None,
    ) -> Defect:
        """Update human review state without changing machine fields."""

        if not isinstance(defect_id, str) or not defect_id.strip():
            raise ValidationError(
                "defect_id must be a non-empty string"
            )

        validate_review_status(status)

        if notes is not None and not isinstance(notes, str):
            raise ValidationError(
                "notes must be a string or None"
            )

        if self.get_defect(defect_id) is None:
            raise DefectNotFoundError(defect_id)

        updated_at = _utc_now()

        with self._connection() as connection:
            if notes is None:
                connection.execute(
                    """
                    UPDATE defects
                    SET
                        review_status = ?,
                        updated_at = ?
                    WHERE defect_id = ?
                    """,
                    (
                        status.value,
                        _datetime_to_text(updated_at),
                        defect_id.strip(),
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE defects
                    SET
                        review_status = ?,
                        review_notes = ?,
                        updated_at = ?
                    WHERE defect_id = ?
                    """,
                    (
                        status.value,
                        notes,
                        _datetime_to_text(updated_at),
                        defect_id.strip(),
                    ),
                )

        updated = self.get_defect(defect_id)

        if updated is None:
            raise RuntimeError(
                f"Review update could not be verified: {defect_id}"
            )

        return updated

    def add_evidence(
        self,
        record: EvidenceCreate,
    ) -> Evidence:
        """Attach one validated provenance record to a persisted defect."""

        validate_evidence_create(record)

        if self.get_defect(record.defect_id) is None:
            raise DefectNotFoundError(record.defect_id)

        try:
            with self._connection() as connection:
                cursor = connection.execute(
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
                        record.defect_id.strip(),
                        record.frame_id.strip(),
                        _datetime_to_text(record.timestamp),
                        record.image_path,
                        record.crop_path,
                        float(record.confidence),
                        float(record.bbox_x1),
                        float(record.bbox_y1),
                        float(record.bbox_x2),
                        float(record.bbox_y2),
                    ),
                )

                evidence_id = int(cursor.lastrowid)

        except sqlite3.IntegrityError as exc:
            raise DuplicateEvidenceError(
                "Exact evidence already exists for this defect/frame/bbox"
            ) from exc

        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()

        if row is None:
            raise RuntimeError(
                f"Evidence creation could not be verified: {evidence_id}"
            )

        return _row_to_evidence(row)

    def list_evidence(
        self,
        defect_id: str,
    ) -> list[Evidence]:
        """Return evidence in deterministic timestamp/id order."""

        if not isinstance(defect_id, str) or not defect_id.strip():
            raise ValidationError(
                "defect_id must be a non-empty string"
            )

        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM evidence
                WHERE defect_id = ?
                ORDER BY timestamp ASC, evidence_id ASC
                """,
                (defect_id.strip(),),
            ).fetchall()

        return [_row_to_evidence(row) for row in rows]
