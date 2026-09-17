"""Schema loading helpers for P16 SQLite persistence."""

from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "database" / "schema.sql"


def load_schema_sql() -> str:
    """Load the frozen P16 SQLite schema."""

    return SCHEMA_PATH.read_text(encoding="utf-8-sig")
