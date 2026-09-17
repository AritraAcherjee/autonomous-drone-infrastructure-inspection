"""Create the deterministic synthetic/test-only P16 demo database."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


from src.storage.models import (  # noqa: E402
    EvidenceCreate,
    InspectionCreate,
    InspectionStatus,
    MappedDefectRecord,
    StructureCreate,
)
from src.storage.service import InspectionService  # noqa: E402


DEFAULT_DATABASE_PATH = (
    REPOSITORY_ROOT
    / "database"
    / "aegisinspect.sqlite3"
)


def utc(
    hour: int,
    minute: int,
    second: int = 0,
) -> datetime:
    """Return one fixed UTC timestamp for deterministic demo data."""

    return datetime(
        2026,
        9,
        16,
        hour,
        minute,
        second,
        tzinfo=timezone.utc,
    )


def seed_database(database_path: Path) -> None:
    """Recreate and populate the synthetic P16 demonstration database."""

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if database_path.exists():
        database_path.unlink()

    service = InspectionService.from_database_path(
        database_path
    )
    service.initialize()

    structure = service.create_structure(
        StructureCreate(
            name="P16 Synthetic Concrete Test Structure",
            description=(
                "Synthetic/test-only structure for the P16 "
                "database and dashboard milestone."
            ),
            location_text="Synthetic Test Environment",
        )
    )

    inspection = service.create_inspection(
        InspectionCreate(
            structure_id=structure.structure_id,
            started_at=utc(16, 0),
            completed_at=utc(16, 10),
            status=InspectionStatus.REVIEW,
            system_version="p16-tuesday-demo",
            notes=(
                "SYNTHETIC TEST DATA ONLY. "
                "Not field inspection evidence."
            ),
        )
    )

    defect_001 = service.ingest_mapped_defect(
        MappedDefectRecord(
            defect_id="synthetic-defect-001",
            inspection_id=inspection.inspection_id,
            track_id="synthetic-track-001",
            class_name="Crack",
            confidence=0.92,
            x_m=1.25,
            y_m=0.40,
            z_m=2.10,
            coordinate_frame="map",
            observation_count=4,
            first_seen=utc(16, 1, 0),
            last_seen=utc(16, 1, 8),
            model_version="synthetic-test-model-v1",
        )
    )

    defect_002 = service.ingest_mapped_defect(
        MappedDefectRecord(
            defect_id="synthetic-defect-002",
            inspection_id=inspection.inspection_id,
            track_id="synthetic-track-002",
            class_name="Breakage",
            confidence=0.78,
            x_m=3.60,
            y_m=-0.25,
            z_m=1.55,
            coordinate_frame="map",
            observation_count=2,
            first_seen=utc(16, 3, 0),
            last_seen=utc(16, 3, 4),
            model_version="synthetic-test-model-v1",
        )
    )

    defect_003 = service.ingest_mapped_defect(
        MappedDefectRecord(
            defect_id="synthetic-defect-003",
            inspection_id=inspection.inspection_id,
            track_id="synthetic-track-003",
            class_name="Exposed Reinforcement",
            confidence=0.84,
            x_m=5.15,
            y_m=0.90,
            z_m=1.20,
            coordinate_frame="map",
            observation_count=3,
            first_seen=utc(16, 5, 0),
            last_seen=utc(16, 5, 6),
            model_version="synthetic-test-model-v1",
        )
    )

    evidence_records = [
        EvidenceCreate(
            defect_id=defect_001.defect_id,
            frame_id="synthetic-frame-001",
            timestamp=utc(16, 1, 0),
            image_path="synthetic/evidence/frame-001.jpg",
            crop_path="synthetic/evidence/crop-001.jpg",
            confidence=0.92,
            bbox_x1=100.0,
            bbox_y1=70.0,
            bbox_x2=185.0,
            bbox_y2=160.0,
        ),
        EvidenceCreate(
            defect_id=defect_001.defect_id,
            frame_id="synthetic-frame-002",
            timestamp=utc(16, 1, 8),
            image_path="synthetic/evidence/frame-002.jpg",
            crop_path="synthetic/evidence/crop-002.jpg",
            confidence=0.90,
            bbox_x1=104.0,
            bbox_y1=72.0,
            bbox_x2=188.0,
            bbox_y2=162.0,
        ),
        EvidenceCreate(
            defect_id=defect_002.defect_id,
            frame_id="synthetic-frame-010",
            timestamp=utc(16, 3, 2),
            image_path="synthetic/evidence/frame-010.jpg",
            crop_path=None,
            confidence=0.78,
            bbox_x1=220.0,
            bbox_y1=95.0,
            bbox_x2=310.0,
            bbox_y2=180.0,
        ),
        EvidenceCreate(
            defect_id=defect_003.defect_id,
            frame_id="synthetic-frame-020",
            timestamp=utc(16, 5, 3),
            image_path=None,
            crop_path=None,
            confidence=0.84,
            bbox_x1=330.0,
            bbox_y1=120.0,
            bbox_x2=430.0,
            bbox_y2=225.0,
        ),
    ]

    for evidence in evidence_records:
        service.add_evidence(evidence)

    print(f"Database: {database_path}")
    print(f"Structure ID: {structure.structure_id}")
    print(f"Inspection ID: {inspection.inspection_id}")
    print("Synthetic defects: 3")
    print("Synthetic evidence rows: 4")
    print("Synthetic demo seed: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create the P16 synthetic/test-only demo database."
        )
    )

    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help="SQLite database path",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seed_database(args.database.resolve())


if __name__ == "__main__":
    main()
