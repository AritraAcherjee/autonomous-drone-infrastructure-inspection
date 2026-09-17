from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.reporting import (
    UNAVAILABLE,
    ReportFormattingError,
    format_number,
    format_optional_text,
    format_timestamp,
)


def test_unavailable_marker_is_exactly_frozen_value() -> None:
    assert UNAVAILABLE == "Unavailable"
    assert format_optional_text(None) == "Unavailable"


def test_optional_text_is_preserved_verbatim() -> None:
    value = "Operator note: inspect west face."

    assert format_optional_text(value) == value


def test_optional_text_rejects_non_string_non_none() -> None:
    with pytest.raises(ReportFormattingError):
        format_optional_text(42)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0"),
        (1, "1"),
        (-17, "-17"),
        (0.0, "0.0"),
        (1.0, "1.0"),
        (0.92, "0.92"),
        (1.25, "1.25"),
        (-0.0, "-0.0"),
        (1.2345678901234567, "1.2345678901234567"),
    ],
)
def test_numeric_rendering_uses_frozen_policy(
    value: int | float,
    expected: str,
) -> None:
    assert format_number(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_nonfinite_float_is_rejected(value: float) -> None:
    with pytest.raises(
        ReportFormattingError,
        match="finite",
    ):
        format_number(value)


def test_boolean_is_not_treated_as_integer() -> None:
    with pytest.raises(
        ReportFormattingError,
        match="boolean",
    ):
        format_number(True)


def test_non_numeric_value_is_rejected() -> None:
    with pytest.raises(ReportFormattingError):
        format_number("0.92")  # type: ignore[arg-type]


def test_utc_timestamp_renders_iso8601_z() -> None:
    value = datetime(
        2026,
        9,
        17,
        12,
        34,
        56,
        123456,
        tzinfo=timezone.utc,
    )

    assert (
        format_timestamp(value)
        == "2026-09-17T12:34:56.123456Z"
    )


def test_non_utc_offset_is_normalized_to_same_instant_in_utc() -> None:
    offset = timezone(timedelta(hours=-6))

    value = datetime(
        2026,
        9,
        17,
        6,
        30,
        0,
        tzinfo=offset,
    )

    assert (
        format_timestamp(value)
        == "2026-09-17T12:30:00Z"
    )


def test_timestamp_without_microseconds_does_not_fabricate_precision() -> None:
    value = datetime(
        2026,
        9,
        17,
        12,
        30,
        0,
        tzinfo=timezone.utc,
    )

    assert format_timestamp(value) == "2026-09-17T12:30:00Z"


def test_naive_timestamp_is_rejected() -> None:
    value = datetime(2026, 9, 17, 12, 30, 0)

    with pytest.raises(
        ReportFormattingError,
        match="timezone-aware",
    ):
        format_timestamp(value)


def test_non_datetime_timestamp_is_rejected() -> None:
    with pytest.raises(ReportFormattingError):
        format_timestamp(  # type: ignore[arg-type]
            "2026-09-17T12:30:00Z"
        )


def test_repeated_formatting_is_deterministic() -> None:
    timestamp = datetime(
        2026,
        9,
        17,
        12,
        30,
        0,
        500000,
        tzinfo=timezone.utc,
    )

    first = (
        format_optional_text(None),
        format_number(0.923456789),
        format_number(4),
        format_timestamp(timestamp),
    )

    second = (
        format_optional_text(None),
        format_number(0.923456789),
        format_number(4),
        format_timestamp(timestamp),
    )

    assert first == second


def test_formatting_does_not_translate_confidence_to_severity() -> None:
    rendered = format_number(0.99)

    assert rendered == "0.99"
    assert "severity" not in rendered.lower()
    assert "safe" not in rendered.lower()
