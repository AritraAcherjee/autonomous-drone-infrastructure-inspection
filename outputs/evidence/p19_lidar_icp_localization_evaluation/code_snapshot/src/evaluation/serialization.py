"""Deterministic canonical serialization for P19 spatial evaluation.

The serializer is pure and has no clock, filesystem, ROS, Gazebo, CUDA,
detector-runtime, or network dependency. It never invents timestamps.

Canonical bytes are exactly:

    json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
import json
import math
from typing import Mapping, Sequence

from src.evaluation.defect_localization import (
    DefectLocalizationResult,
)
from src.evaluation.trajectory import (
    TrajectoryAssociationResult,
    TrajectoryMetricResult,
)


class SpatialSerializationError(ValueError):
    """Raised when a spatial result cannot be serialized canonically."""


TRAJECTORY_GEO_METRIC_NAMES = (
    "vio_ate_translation_rmse_m",
    "vio_rpe_translation_rmse_m_1s",
    "vio_rpe_rotation_rmse_deg_1s",
    "vio_aligned_sample_count",
    "vio_timestamp_alignment_coverage",
    "vio_evaluated_duration_s",
)

DEFECT_GEO_METRIC_NAMES = (
    "defect_localization_mean_error_m",
    "defect_localization_median_error_m",
    "defect_localization_rmse_m",
    "defect_localization_p95_error_m",
    "defect_localization_matched_count",
    "defect_localization_unmatched_estimated_count",
    "defect_localization_unmatched_gt_count",
)

SPATIAL_GEO_METRIC_NAMES = (
    TRAJECTORY_GEO_METRIC_NAMES
    + DEFECT_GEO_METRIC_NAMES
)


def _fail(message: str) -> None:
    raise SpatialSerializationError(message)


def _finite_number(
    name: str,
    value: object,
) -> int | float:
    if type(value) not in {int, float}:
        _fail(f"{name} must be a finite int or float")

    if not math.isfinite(value):
        _fail(f"{name} must be finite")

    return value


def normalize_for_json(value: object) -> object:
    """Convert approved pure values into deterministic JSON primitives."""

    if value is None:
        return None

    if type(value) is bool:
        return value

    if type(value) is int:
        return value

    if type(value) is float:
        if not math.isfinite(value):
            _fail("nonfinite floats are not serializable")

        return value

    if isinstance(value, str):
        return value

    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: normalize_for_json(
                getattr(value, field.name)
            )
            for field in fields(value)
        }

    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}

        for key, item in value.items():
            if not isinstance(key, str):
                _fail(
                    "canonical JSON mappings require string keys"
                )

            normalized[key] = normalize_for_json(item)

        return normalized

    if (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
    ):
        return [
            normalize_for_json(item)
            for item in value
        ]

    _fail(
        "unsupported canonical JSON value type: "
        f"{type(value).__name__}"
    )


def canonical_json_bytes(value: object) -> bytes:
    """Return the frozen UTF-8 canonical JSON representation."""

    normalized = normalize_for_json(value)

    try:
        text = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SpatialSerializationError(
            "value cannot be represented as canonical JSON"
        ) from exc

    return text.encode("utf-8")


def trajectory_geo_metric_values(
    metrics: TrajectoryMetricResult,
    association: TrajectoryAssociationResult,
) -> dict[str, int | float]:
    """Expose exactly the frozen P19 trajectory GEO scalar metrics."""

    if not isinstance(metrics, TrajectoryMetricResult):
        _fail(
            "metrics must be a TrajectoryMetricResult"
        )

    if not isinstance(
        association,
        TrajectoryAssociationResult,
    ):
        _fail(
            "association must be a TrajectoryAssociationResult"
        )

    values: dict[str, int | float] = {
        "vio_ate_translation_rmse_m": _finite_number(
            "vio_ate_translation_rmse_m",
            metrics.ate.rmse_translation_error_m,
        ),
        "vio_rpe_translation_rmse_m_1s": _finite_number(
            "vio_rpe_translation_rmse_m_1s",
            metrics.rpe.translation_rmse_m,
        ),
        "vio_rpe_rotation_rmse_deg_1s": _finite_number(
            "vio_rpe_rotation_rmse_deg_1s",
            metrics.rpe.rotation_rmse_deg,
        ),
        "vio_aligned_sample_count": _finite_number(
            "vio_aligned_sample_count",
            association.aligned_sample_count,
        ),
        "vio_timestamp_alignment_coverage": _finite_number(
            "vio_timestamp_alignment_coverage",
            association.timestamp_alignment_coverage,
        ),
        "vio_evaluated_duration_s": _finite_number(
            "vio_evaluated_duration_s",
            association.evaluated_duration_s,
        ),
    }

    if set(values) != set(TRAJECTORY_GEO_METRIC_NAMES):
        _fail(
            "trajectory GEO metric extraction violated frozen taxonomy"
        )

    return values


def defect_geo_metric_values(
    result: DefectLocalizationResult,
) -> dict[str, int | float | None]:
    """Expose exactly the frozen P19 defect-localization GEO metrics."""

    if not isinstance(result, DefectLocalizationResult):
        _fail(
            "result must be a DefectLocalizationResult"
        )

    aggregate_values = {
        "defect_localization_mean_error_m": (
            result.mean_euclidean_error_m
        ),
        "defect_localization_median_error_m": (
            result.median_euclidean_error_m
        ),
        "defect_localization_rmse_m": (
            result.rmse_euclidean_error_m
        ),
        "defect_localization_p95_error_m": (
            result.p95_euclidean_error_m
        ),
    }

    normalized: dict[str, int | float | None] = {}

    for name, value in aggregate_values.items():
        if value is None:
            normalized[name] = None
        else:
            normalized[name] = _finite_number(
                name,
                value,
            )

    normalized[
        "defect_localization_matched_count"
    ] = _finite_number(
        "defect_localization_matched_count",
        result.matched_count,
    )

    normalized[
        "defect_localization_unmatched_estimated_count"
    ] = _finite_number(
        "defect_localization_unmatched_estimated_count",
        result.unmatched_estimated_count,
    )

    normalized[
        "defect_localization_unmatched_gt_count"
    ] = _finite_number(
        "defect_localization_unmatched_gt_count",
        result.unmatched_gt_count,
    )

    if set(normalized) != set(DEFECT_GEO_METRIC_NAMES):
        _fail(
            "defect GEO metric extraction violated frozen taxonomy"
        )

    return normalized