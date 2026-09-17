"""Pure P19 3D defect-localization evaluation.

This module evaluates already-mapped defect estimates against explicit
evaluation-only simulation ground truth. It does not perform operational
localization, ROS transforms, nearest-neighbour matching, or threshold-based
acceptance decisions.

Signed residual convention:
    estimated map coordinate - ground-truth map coordinate

Ground truth is supplied in ``world`` and converted with the externally
provided evaluation-only rigid transform ``T_map_from_world``:

    p_map = T_map_from_world * p_world

No transform is fitted from evaluated defects.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


_NUMERICAL_EPSILON = 1e-15


class DefectLocalizationError(ValueError):
    """Raised when P19 defect-localization evaluation must fail closed."""


@dataclass(frozen=True, slots=True)
class GroundTruthDefect:
    """Evaluation-only simulation ground-truth defect."""

    gt_defect_id: str
    class_name: str
    x_m: float
    y_m: float
    z_m: float
    coordinate_frame: str


@dataclass(frozen=True, slots=True)
class EstimatedDefect:
    """Pure normalized mapped-defect estimate consumed by P19."""

    estimated_defect_id: str
    class_name: str
    x_m: float
    y_m: float
    z_m: float
    coordinate_frame: str


@dataclass(frozen=True, slots=True)
class DefectCorrespondence:
    """Explicit one-to-one evaluation identity mapping."""

    estimated_defect_id: str
    gt_defect_id: str


@dataclass(frozen=True, slots=True)
class MapFromWorldTransform:
    """Evaluation-only 4x4 rigid homogeneous T_map_from_world."""

    matrix: tuple[
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
        tuple[float, float, float, float],
    ]


@dataclass(frozen=True, slots=True)
class DefectMatchError:
    """Per-match residuals after GT world->map transformation."""

    estimated_defect_id: str
    gt_defect_id: str
    class_name: str

    signed_x_error_m: float
    signed_y_error_m: float
    signed_z_error_m: float

    absolute_x_error_m: float
    absolute_y_error_m: float
    absolute_z_error_m: float

    euclidean_error_m: float


@dataclass(frozen=True, slots=True)
class DefectLocalizationResult:
    """Deterministic P19 3D localization result."""

    matches: tuple[DefectMatchError, ...]

    matched_count: int
    unmatched_estimated_count: int
    unmatched_gt_count: int

    unmatched_estimated_ids: tuple[str, ...]
    unmatched_gt_ids: tuple[str, ...]

    mean_euclidean_error_m: float | None
    median_euclidean_error_m: float | None
    rmse_euclidean_error_m: float | None
    p95_euclidean_error_m: float | None


def _fail(message: str) -> None:
    raise DefectLocalizationError(message)


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{name} must be a nonempty string")

    return value


def _finite_real(name: str, value: object) -> float:
    if type(value) not in {int, float}:
        _fail(f"{name} must be a finite real number")

    result = float(value)

    if not math.isfinite(result):
        _fail(f"{name} must be a finite real number")

    return result


def validate_ground_truth_defect(
    defect: GroundTruthDefect,
) -> GroundTruthDefect:
    """Validate one initial simulation GT defect."""

    if not isinstance(defect, GroundTruthDefect):
        _fail("ground truth must be a GroundTruthDefect")

    _text("gt_defect_id", defect.gt_defect_id)
    _text("class_name", defect.class_name)

    _finite_real("x_m", defect.x_m)
    _finite_real("y_m", defect.y_m)
    _finite_real("z_m", defect.z_m)

    if defect.coordinate_frame != "world":
        _fail(
            'ground-truth coordinate_frame must be exactly "world"'
        )

    return defect


def validate_estimated_defect(
    defect: EstimatedDefect,
) -> EstimatedDefect:
    """Validate one P15/P16-normalized map-frame estimate."""

    if not isinstance(defect, EstimatedDefect):
        _fail("estimate must be an EstimatedDefect")

    _text(
        "estimated_defect_id",
        defect.estimated_defect_id,
    )

    _text("class_name", defect.class_name)

    _finite_real("x_m", defect.x_m)
    _finite_real("y_m", defect.y_m)
    _finite_real("z_m", defect.z_m)

    if defect.coordinate_frame != "map":
        _fail(
            'estimated coordinate_frame must be exactly "map"'
        )

    return defect


def _as_transform_matrix(
    transform: MapFromWorldTransform,
) -> np.ndarray:
    if not isinstance(transform, MapFromWorldTransform):
        _fail(
            "T_map_from_world must be a MapFromWorldTransform"
        )

    try:
        matrix = np.asarray(
            transform.matrix,
            dtype=float,
        )
    except (TypeError, ValueError) as exc:
        raise DefectLocalizationError(
            "T_map_from_world must be a finite 4x4 matrix"
        ) from exc

    if matrix.shape != (4, 4):
        _fail("T_map_from_world must be exactly 4x4")

    if not np.isfinite(matrix).all():
        _fail(
            "T_map_from_world must contain finite values"
        )

    return matrix


def validate_t_map_from_world(
    transform: MapFromWorldTransform,
) -> MapFromWorldTransform:
    """Require a proper scale-1 homogeneous SE(3) transform."""

    matrix = _as_transform_matrix(transform)

    if not np.allclose(
        matrix[3],
        np.asarray(
            (0.0, 0.0, 0.0, 1.0),
            dtype=float,
        ),
        rtol=0.0,
        atol=1e-12,
    ):
        _fail(
            "T_map_from_world must have homogeneous bottom row "
            "[0, 0, 0, 1]"
        )

    rotation = matrix[:3, :3]

    if not np.allclose(
        rotation.T @ rotation,
        np.eye(3, dtype=float),
        rtol=0.0,
        atol=1e-9,
    ):
        _fail(
            "T_map_from_world rotation must be orthonormal "
            "with scale 1.0"
        )

    determinant = float(
        np.linalg.det(rotation)
    )

    if not math.isclose(
        determinant,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        _fail(
            "T_map_from_world rotation must have det(R)=+1"
        )

    return transform


def transform_ground_truth_to_map(
    defect: GroundTruthDefect,
    transform: MapFromWorldTransform | None,
) -> tuple[float, float, float]:
    """Transform one GT point from world into map.

    A missing transform fails closed. The transform is never inferred from
    estimated defects or fitted through nearest-neighbour correspondences.
    """

    validate_ground_truth_defect(defect)

    if transform is None:
        _fail(
            "T_map_from_world is required for 3D defect evaluation"
        )

    validate_t_map_from_world(transform)

    matrix = _as_transform_matrix(transform)

    point_world = np.asarray(
        (
            float(defect.x_m),
            float(defect.y_m),
            float(defect.z_m),
            1.0,
        ),
        dtype=float,
    )

    point_map = matrix @ point_world

    if not math.isclose(
        float(point_map[3]),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        _fail(
            "T_map_from_world produced an invalid homogeneous point"
        )

    return (
        float(point_map[0]),
        float(point_map[1]),
        float(point_map[2]),
    )


def _validate_unique_estimates(
    estimates: Sequence[EstimatedDefect],
) -> tuple[EstimatedDefect, ...]:
    if (
        isinstance(estimates, (str, bytes))
        or not isinstance(estimates, Sequence)
    ):
        _fail(
            "estimates must be a sequence of EstimatedDefect"
        )

    normalized = tuple(estimates)
    ids: set[str] = set()

    for defect in normalized:
        validate_estimated_defect(defect)

        if defect.estimated_defect_id in ids:
            _fail(
                "estimated defects contain duplicate "
                "estimated_defect_id"
            )

        ids.add(defect.estimated_defect_id)

    return normalized


def _validate_unique_ground_truth(
    defects: Sequence[GroundTruthDefect],
) -> tuple[GroundTruthDefect, ...]:
    if (
        isinstance(defects, (str, bytes))
        or not isinstance(defects, Sequence)
    ):
        _fail(
            "ground_truth must be a sequence of GroundTruthDefect"
        )

    normalized = tuple(defects)
    ids: set[str] = set()

    for defect in normalized:
        validate_ground_truth_defect(defect)

        if defect.gt_defect_id in ids:
            _fail(
                "ground truth contains duplicate gt_defect_id"
            )

        ids.add(defect.gt_defect_id)

    return normalized


def _validate_correspondences(
    correspondences: Sequence[DefectCorrespondence],
) -> tuple[DefectCorrespondence, ...]:
    if (
        isinstance(correspondences, (str, bytes))
        or not isinstance(correspondences, Sequence)
    ):
        _fail(
            "correspondences must be a sequence "
            "of DefectCorrespondence"
        )

    normalized = tuple(correspondences)

    estimated_ids: set[str] = set()
    gt_ids: set[str] = set()

    for correspondence in normalized:
        if not isinstance(
            correspondence,
            DefectCorrespondence,
        ):
            _fail(
                "correspondence entries must be "
                "DefectCorrespondence records"
            )

        _text(
            "estimated_defect_id",
            correspondence.estimated_defect_id,
        )

        _text(
            "gt_defect_id",
            correspondence.gt_defect_id,
        )

        if (
            correspondence.estimated_defect_id
            in estimated_ids
        ):
            _fail(
                "duplicate correspondence for estimated defect"
            )

        if correspondence.gt_defect_id in gt_ids:
            _fail(
                "duplicate correspondence for GT defect"
            )

        estimated_ids.add(
            correspondence.estimated_defect_id
        )

        gt_ids.add(
            correspondence.gt_defect_id
        )

    return normalized


def _rmse(values: Sequence[float]) -> float:
    normalized = tuple(
        _finite_real(
            "metric value",
            value,
        )
        for value in values
    )

    if not normalized:
        _fail("RMSE requires at least one value")

    return math.sqrt(
        sum(
            value * value
            for value in normalized
        )
        / len(normalized)
    )


def _median(values: Sequence[float]) -> float:
    normalized = sorted(
        _finite_real(
            "metric value",
            value,
        )
        for value in values
    )

    if not normalized:
        _fail("median requires at least one value")

    count = len(normalized)

    if count % 2:
        return normalized[count // 2]

    return (
        normalized[count // 2 - 1]
        + normalized[count // 2]
    ) / 2.0


def _linear_percentile(
    values: Sequence[float],
    percentile: float,
) -> float:
    normalized = sorted(
        _finite_real(
            "metric value",
            value,
        )
        for value in values
    )

    if not normalized:
        _fail("percentile requires at least one value")

    percentile = _finite_real(
        "percentile",
        percentile,
    )

    if not 0.0 <= percentile <= 100.0:
        _fail(
            "percentile must lie within [0, 100]"
        )

    if len(normalized) == 1:
        return normalized[0]

    position = (
        (len(normalized) - 1)
        * percentile
        / 100.0
    )

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return normalized[lower]

    fraction = position - lower

    return (
        normalized[lower]
        + fraction
        * (
            normalized[upper]
            - normalized[lower]
        )
    )


def evaluate_defect_localization(
    estimates: Sequence[EstimatedDefect],
    ground_truth: Sequence[GroundTruthDefect],
    correspondences: Sequence[DefectCorrespondence],
    *,
    t_map_from_world: MapFromWorldTransform | None,
) -> DefectLocalizationResult:
    """Evaluate only explicit defect identity correspondences.

    No proximity search, nearest-neighbour fallback, or spatial tolerance is
    present. Missing mappings remain visible through unmatched counts.
    """

    normalized_estimates = _validate_unique_estimates(
        estimates
    )

    normalized_gt = _validate_unique_ground_truth(
        ground_truth
    )

    normalized_correspondences = (
        _validate_correspondences(
            correspondences
        )
    )

    if t_map_from_world is None:
        _fail(
            "T_map_from_world is required for 3D defect evaluation"
        )

    validate_t_map_from_world(
        t_map_from_world
    )

    estimates_by_id = {
        defect.estimated_defect_id: defect
        for defect in normalized_estimates
    }

    gt_by_id = {
        defect.gt_defect_id: defect
        for defect in normalized_gt
    }

    matched_estimated_ids: set[str] = set()
    matched_gt_ids: set[str] = set()

    matches: list[DefectMatchError] = []

    for correspondence in sorted(
        normalized_correspondences,
        key=lambda value: (
            value.estimated_defect_id,
            value.gt_defect_id,
        ),
    ):
        try:
            estimate = estimates_by_id[
                correspondence.estimated_defect_id
            ]
        except KeyError as exc:
            raise DefectLocalizationError(
                "correspondence references missing estimated defect"
            ) from exc

        try:
            truth = gt_by_id[
                correspondence.gt_defect_id
            ]
        except KeyError as exc:
            raise DefectLocalizationError(
                "correspondence references missing GT defect"
            ) from exc

        if estimate.class_name != truth.class_name:
            _fail(
                "explicit defect correspondence requires "
                "exact class-name agreement"
            )

        gt_x, gt_y, gt_z = (
            transform_ground_truth_to_map(
                truth,
                t_map_from_world,
            )
        )

        # Frozen residual convention:
        # estimated map coordinate - GT map coordinate.
        signed_x = float(estimate.x_m) - gt_x
        signed_y = float(estimate.y_m) - gt_y
        signed_z = float(estimate.z_m) - gt_z

        absolute_x = abs(signed_x)
        absolute_y = abs(signed_y)
        absolute_z = abs(signed_z)

        euclidean = math.sqrt(
            signed_x * signed_x
            + signed_y * signed_y
            + signed_z * signed_z
        )

        matches.append(
            DefectMatchError(
                estimated_defect_id=(
                    estimate.estimated_defect_id
                ),
                gt_defect_id=truth.gt_defect_id,
                class_name=estimate.class_name,
                signed_x_error_m=signed_x,
                signed_y_error_m=signed_y,
                signed_z_error_m=signed_z,
                absolute_x_error_m=absolute_x,
                absolute_y_error_m=absolute_y,
                absolute_z_error_m=absolute_z,
                euclidean_error_m=euclidean,
            )
        )

        matched_estimated_ids.add(
            estimate.estimated_defect_id
        )

        matched_gt_ids.add(
            truth.gt_defect_id
        )

    unmatched_estimated_ids = tuple(
        sorted(
            set(estimates_by_id)
            - matched_estimated_ids
        )
    )

    unmatched_gt_ids = tuple(
        sorted(
            set(gt_by_id)
            - matched_gt_ids
        )
    )

    errors = tuple(
        match.euclidean_error_m
        for match in matches
    )

    if errors:
        mean_error: float | None = (
            sum(errors) / len(errors)
        )

        median_error: float | None = (
            _median(errors)
        )

        rmse_error: float | None = (
            _rmse(errors)
        )

        p95_error: float | None = (
            _linear_percentile(
                errors,
                95.0,
            )
        )
    else:
        mean_error = None
        median_error = None
        rmse_error = None
        p95_error = None

    return DefectLocalizationResult(
        matches=tuple(matches),
        matched_count=len(matches),
        unmatched_estimated_count=len(
            unmatched_estimated_ids
        ),
        unmatched_gt_count=len(
            unmatched_gt_ids
        ),
        unmatched_estimated_ids=(
            unmatched_estimated_ids
        ),
        unmatched_gt_ids=unmatched_gt_ids,
        mean_euclidean_error_m=mean_error,
        median_euclidean_error_m=median_error,
        rmse_euclidean_error_m=rmse_error,
        p95_euclidean_error_m=p95_error,
    )