"""Public application service for the P16 persistence boundary."""

from __future__ import annotations

from pathlib import Path

from .models import (
    Defect,
    Evidence,
    EvidenceCreate,
    Inspection,
    InspectionCreate,
    MappedDefectRecord,
    ReviewStatus,
    Structure,
    StructureCreate,
)
from .repository import SQLiteInspectionRepository


class InspectionService:
    """Thin P16 application boundary over inspection persistence."""

    def __init__(
        self,
        repository: SQLiteInspectionRepository,
    ):
        self.repository = repository

    @classmethod
    def from_database_path(
        cls,
        database_path: str | Path,
    ) -> "InspectionService":
        """Construct a service using the standard SQLite repository."""

        return cls(SQLiteInspectionRepository(database_path))

    def initialize(self) -> None:
        """Initialize the persistence schema."""

        self.repository.initialize()

    def create_structure(
        self,
        record: StructureCreate,
    ) -> Structure:
        return self.repository.create_structure(record)

    def get_structure(
        self,
        structure_id: int,
    ) -> Structure | None:
        return self.repository.get_structure(structure_id)

    def create_inspection(
        self,
        record: InspectionCreate,
    ) -> Inspection:
        return self.repository.create_inspection(record)

    def get_inspection(
        self,
        inspection_id: int,
    ) -> Inspection | None:
        return self.repository.get_inspection(inspection_id)

    def list_inspections(
        self,
    ) -> list[Inspection]:
        return self.repository.list_inspections()

    def ingest_mapped_defect(
        self,
        defect: MappedDefectRecord,
    ) -> Defect:
        """Persist one already-decided mapped defect from the P15 boundary."""

        return self.repository.create_defect(defect)

    def update_mapped_defect(
        self,
        defect: MappedDefectRecord,
    ) -> Defect:
        """Update machine fields while preserving human review state."""

        return self.repository.update_defect(defect)

    def get_defect(
        self,
        defect_id: str,
    ) -> Defect | None:
        return self.repository.get_defect(defect_id)

    def list_defects(
        self,
        *,
        inspection_id: int | None = None,
        class_name: str | None = None,
        review_status: ReviewStatus | None = None,
        min_confidence: float | None = None,
    ) -> list[Defect]:
        return self.repository.list_defects(
            inspection_id=inspection_id,
            class_name=class_name,
            review_status=review_status,
            min_confidence=min_confidence,
        )

    def list_inspection_defects(
        self,
        inspection_id: int,
    ) -> list[Defect]:
        return self.repository.list_inspection_defects(
            inspection_id
        )

    def add_evidence(
        self,
        record: EvidenceCreate,
    ) -> Evidence:
        return self.repository.add_evidence(record)

    def list_evidence(
        self,
        defect_id: str,
    ) -> list[Evidence]:
        return self.repository.list_evidence(defect_id)

    def set_review_status(
        self,
        defect_id: str,
        status: ReviewStatus,
        notes: str | None = None,
    ) -> Defect:
        return self.repository.set_review_status(
            defect_id,
            status,
            notes,
        )
