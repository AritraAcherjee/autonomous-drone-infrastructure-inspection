"""Validation tests for the frozen P16 persistence boundary."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from src.storage.models import MappedDefectRecord
from src.storage.validation import (
    ValidationError,
    validate_confidence,
    validate_evidence_create,
    validate_inspection_create,
    validate_mapped_defect,
    validate_observation_count,
    validate_structure_create,
)
from tests.storage.fixtures import (
    T0,
    make_defect,
    make_evidence,
    make_inspection,
    make_structure,
)


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("x_m", float("nan")),
        ("y_m", float("nan")),
        ("z_m", float("nan")),
        ("x_m", float("inf")),
        ("y_m", float("-inf")),
        ("z_m", float("inf")),
    ],
)
def test_rejects_nonfinite_mapped_coordinates(
    field_name: str,
    bad_value: float,
) -> None:
    record = make_defect(**{field_name: bad_value})

    with pytest.raises(ValidationError):
        validate_mapped_defect(record)


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        "   ",
        None,
    ],
)
def test_rejects_missing_defect_identity(
    bad_id: object,
) -> None:
    record = make_defect(defect_id=bad_id)

    with pytest.raises(ValidationError):
        validate_mapped_defect(record)


@pytest.mark.parametrize(
    "bad_frame",
    [
        "",
        "   ",
        None,
    ],
)
def test_rejects_missing_coordinate_frame(
    bad_frame: object,
) -> None:
    record = make_defect(coordinate_frame=bad_frame)

    with pytest.raises(ValidationError):
        validate_mapped_defect(record)


@pytest.mark.parametrize(
    "value",
    [
        0.0,
        1.0,
    ],
)
def test_confidence_accepts_closed_interval_edges(
    value: float,
) -> None:
    validate_confidence(value)


@pytest.mark.parametrize(
    "value",
    [
        -0.01,
        1.01,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_confidence_rejects_invalid_values(
    value: float,
) -> None:
    with pytest.raises(ValidationError):
        validate_confidence(value)


def test_observation_count_accepts_one() -> None:
    validate_observation_count(1)


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
        1.5,
        True,
        False,
    ],
)
def test_observation_count_rejects_invalid_values(
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        validate_observation_count(value)


def test_accepts_timezone_aware_timestamps() -> None:
    validate_mapped_defect(make_defect())


def test_rejects_naive_timestamp() -> None:
    record = make_defect(
        first_seen=datetime(2026, 9, 16, 16, 0, 0),
    )

    with pytest.raises(ValidationError):
        validate_mapped_defect(record)


def test_rejects_last_seen_before_first_seen() -> None:
    record = make_defect(
        first_seen=T0,
        last_seen=T0.replace(second=0, minute=0, hour=15),
    )

    with pytest.raises(ValidationError):
        validate_mapped_defect(record)


def test_accepts_valid_bbox() -> None:
    validate_evidence_create(make_evidence())


@pytest.mark.parametrize(
    "overrides",
    [
        {"bbox_x1": float("nan")},
        {"bbox_y1": float("inf")},
        {"bbox_x2": float("-inf")},
        {"bbox_y2": float("nan")},
        {"bbox_x1": -1.0},
        {"bbox_y1": -1.0},
        {"bbox_x2": 100.0},
        {"bbox_y2": 70.0},
        {"bbox_x2": 99.0},
        {"bbox_y2": 69.0},
    ],
)
def test_rejects_invalid_bbox(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        validate_evidence_create(
            make_evidence(**overrides)
        )


def test_structure_validation_accepts_synthetic_fixture() -> None:
    validate_structure_create(make_structure())


def test_inspection_validation_accepts_synthetic_fixture() -> None:
    validate_inspection_create(make_inspection())


def test_rejects_completed_at_before_started_at() -> None:
    inspection = make_inspection()
    invalid = replace(
        inspection,
        completed_at=T0.replace(hour=15),
    )

    with pytest.raises(ValidationError):
        validate_inspection_create(invalid)


def test_mapped_defect_dto_has_no_review_status_field() -> None:
    field_names = set(MappedDefectRecord.__dataclass_fields__)

    assert "review_status" not in field_names
    assert "review_notes" not in field_names
