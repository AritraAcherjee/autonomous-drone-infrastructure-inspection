"""Pure deterministic trajectory contracts for P19 spatial evaluation.

This module contains no ROS, Gazebo, CUDA, detector-runtime, filesystem,
network, or wall-clock dependency. Runtime-specific adapters must normalize
their inputs into TrajectorySample records before entering this layer.

All values produced by tests in this module are synthetic fixture values only.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


NANOSECONDS_PER_SECOND = 1_000_000_000

MAX_GT_BRACKET_SPAN_NS = 50_000_000

PRIMARY_WINDOW_START_NS = 3_000_000_000
PRIMARY_WINDOW_END_NS = 18_000_000_000

SECONDARY_WINDOW_START_NS = 0
SECONDARY_WINDOW_END_NS = 20_000_000_000

_NUMERICAL_EPSILON = 1e-15


class TrajectoryValidationError(ValueError):
    """Raised when trajectory input violates the frozen P19 contract."""


@dataclass(frozen=True, slots=True)
class TrajectorySample:
    """One normalized 6-DoF pose sample."""

    timestamp_ns: int
    x_m: float
    y_m: float
    z_m: float
    qx: float
    qy: float
    qz: float
    qw: float
    frame_id: str
    child_frame_id: str


@dataclass(frozen=True, slots=True)
class AlignedTrajectorySample:
    """One estimator pose paired with GT at the exact estimator timestamp."""

    timestamp_ns: int
    estimated: TrajectorySample
    ground_truth: TrajectorySample


@dataclass(frozen=True, slots=True)
class TrajectoryAssociationResult:
    """Deterministic timestamp-association result for one evaluation window."""

    aligned: tuple[AlignedTrajectorySample, ...]
    estimator_sample_count: int
    aligned_sample_count: int
    dropped_sample_count: int
    timestamp_alignment_coverage: float
    evaluated_duration_s: float


def _fail(message: str) -> None:
    raise TrajectoryValidationError(message)


def _finite_real(name: str, value: object) -> float:
    if type(value) not in {int, float}:
        _fail(f"{name} must be a finite real number")

    result = float(value)

    if not math.isfinite(result):
        _fail(f"{name} must be a finite real number")

    return result


def _nonnegative_timestamp(value: object) -> int:
    if type(value) is not int or value < 0:
        _fail("timestamp_ns must be a nonnegative integer")

    return value


def _nonempty_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{name} must be a nonempty string")

    return value


def _quaternion(sample: TrajectorySample) -> tuple[float, float, float, float]:
    quaternion = (
        _finite_real("qx", sample.qx),
        _finite_real("qy", sample.qy),
        _finite_real("qz", sample.qz),
        _finite_real("qw", sample.qw),
    )

    norm_sq = sum(component * component for component in quaternion)

    if norm_sq <= _NUMERICAL_EPSILON:
        _fail("quaternion must have nonzero norm")

    return quaternion


def _normalize_quaternion(
    quaternion: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    norm = math.sqrt(sum(component * component for component in quaternion))

    if not math.isfinite(norm) or norm <= _NUMERICAL_EPSILON:
        _fail("quaternion must have nonzero finite norm")

    return tuple(
        float(component / norm)
        for component in quaternion
    )


def validate_trajectory_sample(sample: TrajectorySample) -> TrajectorySample:
    """Validate one sample without silently repairing or mutating it."""

    if not isinstance(sample, TrajectorySample):
        _fail("sample must be a TrajectorySample")

    _nonnegative_timestamp(sample.timestamp_ns)

    _finite_real("x_m", sample.x_m)
    _finite_real("y_m", sample.y_m)
    _finite_real("z_m", sample.z_m)

    _quaternion(sample)

    _nonempty_text("frame_id", sample.frame_id)
    _nonempty_text("child_frame_id", sample.child_frame_id)

    return sample


def validate_trajectory(
    samples: Sequence[TrajectorySample],
    *,
    expected_frame_id: str | None = None,
    expected_child_frame_id: str | None = None,
) -> tuple[TrajectorySample, ...]:
    """Validate one strictly timestamp-ordered trajectory."""

    if isinstance(samples, (str, bytes)) or not isinstance(samples, Sequence):
        _fail("trajectory must be a sequence of TrajectorySample records")

    normalized = tuple(samples)

    if not normalized:
        _fail("trajectory must contain at least one sample")

    if expected_frame_id is not None:
        _nonempty_text("expected_frame_id", expected_frame_id)

    if expected_child_frame_id is not None:
        _nonempty_text("expected_child_frame_id", expected_child_frame_id)

    previous_timestamp: int | None = None
    first_frame: str | None = None
    first_child: str | None = None

    for sample in normalized:
        validate_trajectory_sample(sample)

        if previous_timestamp is not None and sample.timestamp_ns <= previous_timestamp:
            _fail("trajectory timestamps must be strictly increasing")

        if first_frame is None:
            first_frame = sample.frame_id
            first_child = sample.child_frame_id
        else:
            if sample.frame_id != first_frame:
                _fail("trajectory frame_id must remain constant")

            if sample.child_frame_id != first_child:
                _fail("trajectory child_frame_id must remain constant")

        if expected_frame_id is not None and sample.frame_id != expected_frame_id:
            _fail(
                f"trajectory frame_id must be exactly {expected_frame_id!r}"
            )

        if (
            expected_child_frame_id is not None
            and sample.child_frame_id != expected_child_frame_id
        ):
            _fail(
                "trajectory child_frame_id must be exactly "
                f"{expected_child_frame_id!r}"
            )

        previous_timestamp = sample.timestamp_ns

    return normalized


def slerp_quaternion(
    q0: tuple[float, float, float, float],
    q1: tuple[float, float, float, float],
    fraction: float,
) -> tuple[float, float, float, float]:
    """Shortest-path quaternion SLERP with q/-q equivalence."""

    fraction = _finite_real("fraction", fraction)

    if not 0.0 <= fraction <= 1.0:
        _fail("fraction must be within [0, 1]")

    a = _normalize_quaternion(tuple(_finite_real("q0", v) for v in q0))
    b = _normalize_quaternion(tuple(_finite_real("q1", v) for v in q1))

    dot = sum(left * right for left, right in zip(a, b))

    if dot < 0.0:
        b = tuple(-component for component in b)
        dot = -dot

    dot = max(-1.0, min(1.0, dot))

    if dot > 0.9995:
        blended = tuple(
            left + fraction * (right - left)
            for left, right in zip(a, b)
        )
        return _normalize_quaternion(blended)

    theta_0 = math.acos(dot)
    sin_theta_0 = math.sin(theta_0)

    if abs(sin_theta_0) <= _NUMERICAL_EPSILON:
        return a

    theta = theta_0 * fraction

    weight_a = math.sin(theta_0 - theta) / sin_theta_0
    weight_b = math.sin(theta) / sin_theta_0

    result = tuple(
        weight_a * left + weight_b * right
        for left, right in zip(a, b)
    )

    return _normalize_quaternion(result)


def interpolate_ground_truth_sample(
    left: TrajectorySample,
    right: TrajectorySample,
    timestamp_ns: int,
) -> TrajectorySample:
    """Interpolate GT translation linearly and orientation with SLERP."""

    validate_trajectory_sample(left)
    validate_trajectory_sample(right)

    timestamp_ns = _nonnegative_timestamp(timestamp_ns)

    if left.frame_id != right.frame_id:
        _fail("ground-truth interpolation requires one frame_id")

    if left.child_frame_id != right.child_frame_id:
        _fail("ground-truth interpolation requires one child_frame_id")

    if right.timestamp_ns <= left.timestamp_ns:
        _fail("ground-truth interpolation bracket must be strictly ordered")

    if not left.timestamp_ns <= timestamp_ns <= right.timestamp_ns:
        _fail("interpolation timestamp must lie inside the GT bracket")

    fraction = (
        (timestamp_ns - left.timestamp_ns)
        / (right.timestamp_ns - left.timestamp_ns)
    )

    quaternion = slerp_quaternion(
        _quaternion(left),
        _quaternion(right),
        fraction,
    )

    def linear(a: float, b: float) -> float:
        return a + fraction * (b - a)

    return TrajectorySample(
        timestamp_ns=timestamp_ns,
        x_m=linear(float(left.x_m), float(right.x_m)),
        y_m=linear(float(left.y_m), float(right.y_m)),
        z_m=linear(float(left.z_m), float(right.z_m)),
        qx=quaternion[0],
        qy=quaternion[1],
        qz=quaternion[2],
        qw=quaternion[3],
        frame_id=left.frame_id,
        child_frame_id=left.child_frame_id,
    )


def associate_ground_truth(
    estimator_samples: Sequence[TrajectorySample],
    ground_truth_samples: Sequence[TrajectorySample],
    *,
    max_gt_bracket_span_ns: int = MAX_GT_BRACKET_SPAN_NS,
) -> TrajectoryAssociationResult:
    """Associate each eligible estimator timestamp to interpolated GT.

    Exact GT timestamp matches are accepted directly. Otherwise a bracketing
    pair is required, its span must not exceed the frozen 50 ms maximum, and
    interpolation occurs at the estimator timestamp. No extrapolation occurs.
    """

    estimated = validate_trajectory(estimator_samples)
    ground_truth = validate_trajectory(ground_truth_samples)

    if (
        type(max_gt_bracket_span_ns) is not int
        or max_gt_bracket_span_ns < 0
    ):
        _fail("max_gt_bracket_span_ns must be a nonnegative integer")

    gt_timestamps = tuple(
        sample.timestamp_ns
        for sample in ground_truth
    )

    aligned: list[AlignedTrajectorySample] = []

    for estimator in estimated:
        index = bisect_left(gt_timestamps, estimator.timestamp_ns)

        if (
            index < len(ground_truth)
            and gt_timestamps[index] == estimator.timestamp_ns
        ):
            gt_sample = ground_truth[index]
        else:
            if index == 0 or index == len(ground_truth):
                continue

            left = ground_truth[index - 1]
            right = ground_truth[index]

            span_ns = right.timestamp_ns - left.timestamp_ns

            if span_ns > max_gt_bracket_span_ns:
                continue

            gt_sample = interpolate_ground_truth_sample(
                left,
                right,
                estimator.timestamp_ns,
            )

        aligned.append(
            AlignedTrajectorySample(
                timestamp_ns=estimator.timestamp_ns,
                estimated=estimator,
                ground_truth=gt_sample,
            )
        )

    estimator_count = len(estimated)
    aligned_count = len(aligned)
    dropped_count = estimator_count - aligned_count

    coverage = aligned_count / estimator_count

    if estimator_count >= 2:
        duration_s = (
            estimated[-1].timestamp_ns
            - estimated[0].timestamp_ns
        ) / NANOSECONDS_PER_SECOND
    else:
        duration_s = 0.0

    return TrajectoryAssociationResult(
        aligned=tuple(aligned),
        estimator_sample_count=estimator_count,
        aligned_sample_count=aligned_count,
        dropped_sample_count=dropped_count,
        timestamp_alignment_coverage=coverage,
        evaluated_duration_s=duration_s,
    )


def window_trajectory(
    samples: Sequence[TrajectorySample],
    *,
    run_start_timestamp_ns: int,
    start_offset_ns: int,
    end_offset_ns: int,
) -> tuple[TrajectorySample, ...]:
    """Select a deterministic interval relative to explicit P13 START."""

    trajectory = validate_trajectory(samples)

    run_start_timestamp_ns = _nonnegative_timestamp(
        run_start_timestamp_ns
    )

    if type(start_offset_ns) is not int or start_offset_ns < 0:
        _fail("start_offset_ns must be a nonnegative integer")

    if type(end_offset_ns) is not int or end_offset_ns < start_offset_ns:
        _fail("end_offset_ns must be >= start_offset_ns")

    start_timestamp = run_start_timestamp_ns + start_offset_ns
    end_timestamp = run_start_timestamp_ns + end_offset_ns

    return tuple(
        sample
        for sample in trajectory
        if start_timestamp <= sample.timestamp_ns <= end_timestamp
    )


def primary_window(
    samples: Sequence[TrajectorySample],
    *,
    run_start_timestamp_ns: int,
) -> tuple[TrajectorySample, ...]:
    """Frozen headline 3–18 s P13-relative window."""

    return window_trajectory(
        samples,
        run_start_timestamp_ns=run_start_timestamp_ns,
        start_offset_ns=PRIMARY_WINDOW_START_NS,
        end_offset_ns=PRIMARY_WINDOW_END_NS,
    )


def secondary_window(
    samples: Sequence[TrajectorySample],
    *,
    run_start_timestamp_ns: int,
) -> tuple[TrajectorySample, ...]:
    """Frozen secondary 0–20 s P13-relative diagnostic window."""

    return window_trajectory(
        samples,
        run_start_timestamp_ns=run_start_timestamp_ns,
        start_offset_ns=SECONDARY_WINDOW_START_NS,
        end_offset_ns=SECONDARY_WINDOW_END_NS,
    )

RPE_DELTA_NS = 1_000_000_000
RPE_MAX_DELTA_MISMATCH_NS = 50_000_000


@dataclass(frozen=True, slots=True)
class RigidAlignment:
    """Rigid no-scale transform mapping estimated coordinates into GT."""

    rotation: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    translation_m: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class AteResult:
    """Translation ATE statistics after frozen rigid alignment."""

    mean_translation_error_m: float
    median_translation_error_m: float
    rmse_translation_error_m: float
    p95_translation_error_m: float
    aligned_sample_count: int
    per_sample_translation_error_m: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class RpePairResult:
    """One accepted frozen-delta RPE pair."""

    start_timestamp_ns: int
    end_timestamp_ns: int
    actual_delta_ns: int
    translation_error_m: float
    rotation_error_deg: float


@dataclass(frozen=True, slots=True)
class RpeResult:
    """Frozen 1-second RPE summary."""

    translation_rmse_m: float
    rotation_rmse_deg: float
    evaluated_pair_count: int
    pairs: tuple[RpePairResult, ...]


@dataclass(frozen=True, slots=True)
class TrajectoryMetricResult:
    """Complete pure trajectory metric result for one aligned window."""

    alignment: RigidAlignment
    ate: AteResult
    rpe: RpeResult


def _validate_aligned_samples(
    records: Sequence[AlignedTrajectorySample],
) -> tuple[AlignedTrajectorySample, ...]:
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        _fail(
            "aligned trajectory must be a sequence of "
            "AlignedTrajectorySample records"
        )

    normalized = tuple(records)

    if not normalized:
        _fail("aligned trajectory must contain at least one sample")

    previous: int | None = None

    for record in normalized:
        if not isinstance(record, AlignedTrajectorySample):
            _fail(
                "aligned trajectory entries must be "
                "AlignedTrajectorySample records"
            )

        _nonnegative_timestamp(record.timestamp_ns)

        validate_trajectory_sample(record.estimated)
        validate_trajectory_sample(record.ground_truth)

        if record.estimated.timestamp_ns != record.timestamp_ns:
            _fail(
                "aligned estimator timestamp must equal record timestamp"
            )

        if record.ground_truth.timestamp_ns != record.timestamp_ns:
            _fail(
                "aligned ground-truth timestamp must equal record timestamp"
            )

        if (
            record.estimated.child_frame_id
            != record.ground_truth.child_frame_id
        ):
            _fail(
                "aligned estimator and ground truth must represent "
                "the same child frame"
            )

        if previous is not None and record.timestamp_ns <= previous:
            _fail(
                "aligned trajectory timestamps must be strictly increasing"
            )

        previous = record.timestamp_ns

    return normalized


def _rotation_array(
    alignment: RigidAlignment,
) -> np.ndarray:
    try:
        rotation = np.asarray(
            alignment.rotation,
            dtype=float,
        )
    except (TypeError, ValueError) as exc:
        raise TrajectoryValidationError(
            "alignment rotation must be a finite 3x3 matrix"
        ) from exc

    if rotation.shape != (3, 3):
        _fail("alignment rotation must be a 3x3 matrix")

    if not np.isfinite(rotation).all():
        _fail("alignment rotation must contain finite values")

    identity = np.eye(3, dtype=float)

    if not np.allclose(
        rotation.T @ rotation,
        identity,
        rtol=0.0,
        atol=1e-9,
    ):
        _fail("alignment rotation must be orthonormal")

    determinant = float(np.linalg.det(rotation))

    if not math.isclose(
        determinant,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        _fail("alignment rotation must be proper SE(3), det(R)=+1")

    return rotation


def _translation_array(
    alignment: RigidAlignment,
) -> np.ndarray:
    try:
        translation = np.asarray(
            alignment.translation_m,
            dtype=float,
        )
    except (TypeError, ValueError) as exc:
        raise TrajectoryValidationError(
            "alignment translation must be a finite 3-vector"
        ) from exc

    if translation.shape != (3,):
        _fail("alignment translation must be a 3-vector")

    if not np.isfinite(translation).all():
        _fail("alignment translation must contain finite values")

    return translation


def validate_rigid_alignment(
    alignment: RigidAlignment,
) -> RigidAlignment:
    if not isinstance(alignment, RigidAlignment):
        _fail("alignment must be a RigidAlignment")

    _rotation_array(alignment)
    _translation_array(alignment)

    return alignment


def _quaternion_to_rotation_matrix(
    quaternion: tuple[float, float, float, float],
) -> np.ndarray:
    x, y, z, w = _normalize_quaternion(
        tuple(
            _finite_real("quaternion component", value)
            for value in quaternion
        )
    )

    return np.asarray(
        (
            (
                1.0 - 2.0 * (y * y + z * z),
                2.0 * (x * y - z * w),
                2.0 * (x * z + y * w),
            ),
            (
                2.0 * (x * y + z * w),
                1.0 - 2.0 * (x * x + z * z),
                2.0 * (y * z - x * w),
            ),
            (
                2.0 * (x * z - y * w),
                2.0 * (y * z + x * w),
                1.0 - 2.0 * (x * x + y * y),
            ),
        ),
        dtype=float,
    )


def _rotation_matrix_to_quaternion(
    rotation: np.ndarray,
) -> tuple[float, float, float, float]:
    rotation = np.asarray(rotation, dtype=float)

    if rotation.shape != (3, 3):
        _fail("rotation matrix must be 3x3")

    if not np.isfinite(rotation).all():
        _fail("rotation matrix must be finite")

    trace = float(np.trace(rotation))

    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        qw = 0.25 * scale
        qx = (rotation[2, 1] - rotation[1, 2]) / scale
        qy = (rotation[0, 2] - rotation[2, 0]) / scale
        qz = (rotation[1, 0] - rotation[0, 1]) / scale
    else:
        diagonal = np.diag(rotation)
        index = int(np.argmax(diagonal))

        if index == 0:
            scale = math.sqrt(
                max(
                    0.0,
                    1.0
                    + rotation[0, 0]
                    - rotation[1, 1]
                    - rotation[2, 2],
                )
            ) * 2.0

            qx = 0.25 * scale
            qy = (rotation[0, 1] + rotation[1, 0]) / scale
            qz = (rotation[0, 2] + rotation[2, 0]) / scale
            qw = (rotation[2, 1] - rotation[1, 2]) / scale

        elif index == 1:
            scale = math.sqrt(
                max(
                    0.0,
                    1.0
                    + rotation[1, 1]
                    - rotation[0, 0]
                    - rotation[2, 2],
                )
            ) * 2.0

            qx = (rotation[0, 1] + rotation[1, 0]) / scale
            qy = 0.25 * scale
            qz = (rotation[1, 2] + rotation[2, 1]) / scale
            qw = (rotation[0, 2] - rotation[2, 0]) / scale

        else:
            scale = math.sqrt(
                max(
                    0.0,
                    1.0
                    + rotation[2, 2]
                    - rotation[0, 0]
                    - rotation[1, 1],
                )
            ) * 2.0

            qx = (rotation[0, 2] + rotation[2, 0]) / scale
            qy = (rotation[1, 2] + rotation[2, 1]) / scale
            qz = 0.25 * scale
            qw = (rotation[1, 0] - rotation[0, 1]) / scale

    quaternion = _normalize_quaternion(
        (qx, qy, qz, qw)
    )

    # Canonicalize the sign only for deterministic serialization.
    # q and -q continue to represent the same physical rotation.
    for component in (
        quaternion[3],
        quaternion[0],
        quaternion[1],
        quaternion[2],
    ):
        if abs(component) <= _NUMERICAL_EPSILON:
            continue

        if component < 0.0:
            quaternion = tuple(
                -value
                for value in quaternion
            )

        break

    return quaternion


def _position_array(
    sample: TrajectorySample,
) -> np.ndarray:
    validate_trajectory_sample(sample)

    return np.asarray(
        (
            float(sample.x_m),
            float(sample.y_m),
            float(sample.z_m),
        ),
        dtype=float,
    )


def fit_rigid_alignment(
    records: Sequence[AlignedTrajectorySample],
) -> RigidAlignment:
    """Fit frozen least-squares Umeyama SE(3) alignment with scale=1.

    The fit maps estimated odom coordinates into GT world coordinates.
    Sim(3) and scale correction are deliberately not supported.
    """

    aligned = _validate_aligned_samples(records)

    if len(aligned) < 3:
        _fail(
            "at least three aligned samples are required "
            "for rigid trajectory alignment"
        )

    estimated = np.asarray(
        [
            _position_array(record.estimated)
            for record in aligned
        ],
        dtype=float,
    )

    ground_truth = np.asarray(
        [
            _position_array(record.ground_truth)
            for record in aligned
        ],
        dtype=float,
    )

    estimated_mean = estimated.mean(axis=0)
    ground_truth_mean = ground_truth.mean(axis=0)

    estimated_centered = estimated - estimated_mean
    ground_truth_centered = ground_truth - ground_truth_mean

    estimated_rank = int(
        np.linalg.matrix_rank(estimated_centered)
    )

    ground_truth_rank = int(
        np.linalg.matrix_rank(ground_truth_centered)
    )

    if estimated_rank < 2 or ground_truth_rank < 2:
        _fail(
            "rigid alignment requires at least three "
            "non-collinear trajectory positions"
        )

    covariance = (
        ground_truth_centered.T
        @ estimated_centered
    ) / len(aligned)

    left, _, right_t = np.linalg.svd(
        covariance,
        full_matrices=True,
    )

    correction = np.eye(3, dtype=float)

    if float(
        np.linalg.det(left)
        * np.linalg.det(right_t)
    ) < 0.0:
        correction[-1, -1] = -1.0

    rotation = left @ correction @ right_t
    translation = (
        ground_truth_mean
        - rotation @ estimated_mean
    )

    result = RigidAlignment(
        rotation=tuple(
            tuple(float(value) for value in row)
            for row in rotation
        ),
        translation_m=tuple(
            float(value)
            for value in translation
        ),
    )

    return validate_rigid_alignment(result)


def apply_rigid_alignment(
    sample: TrajectorySample,
    alignment: RigidAlignment,
    *,
    target_frame_id: str,
) -> TrajectorySample:
    """Apply the same frozen rigid transform to position and orientation."""

    validate_trajectory_sample(sample)
    validate_rigid_alignment(alignment)
    _nonempty_text("target_frame_id", target_frame_id)

    rotation = _rotation_array(alignment)
    translation = _translation_array(alignment)

    position = (
        rotation @ _position_array(sample)
        + translation
    )

    source_orientation = _quaternion_to_rotation_matrix(
        _quaternion(sample)
    )

    target_orientation = (
        rotation
        @ source_orientation
    )

    quaternion = _rotation_matrix_to_quaternion(
        target_orientation
    )

    return TrajectorySample(
        timestamp_ns=sample.timestamp_ns,
        x_m=float(position[0]),
        y_m=float(position[1]),
        z_m=float(position[2]),
        qx=quaternion[0],
        qy=quaternion[1],
        qz=quaternion[2],
        qw=quaternion[3],
        frame_id=target_frame_id,
        child_frame_id=sample.child_frame_id,
    )


def _rmse(values: Sequence[float]) -> float:
    normalized = tuple(
        _finite_real("metric value", value)
        for value in values
    )

    if not normalized:
        _fail("metric requires at least one value")

    return math.sqrt(
        sum(value * value for value in normalized)
        / len(normalized)
    )


def _linear_percentile(
    values: Sequence[float],
    percentile: float,
) -> float:
    normalized = sorted(
        _finite_real("metric value", value)
        for value in values
    )

    if not normalized:
        _fail("percentile requires at least one value")

    percentile = _finite_real(
        "percentile",
        percentile,
    )

    if not 0.0 <= percentile <= 100.0:
        _fail("percentile must lie within [0, 100]")

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


def compute_ate(
    records: Sequence[AlignedTrajectorySample],
    alignment: RigidAlignment,
) -> AteResult:
    """Compute frozen translation ATE statistics after rigid alignment."""

    aligned = _validate_aligned_samples(records)
    validate_rigid_alignment(alignment)

    if len(aligned) < 3:
        _fail(
            "ATE requires at least three aligned samples"
        )

    errors: list[float] = []

    for record in aligned:
        transformed = apply_rigid_alignment(
            record.estimated,
            alignment,
            target_frame_id=record.ground_truth.frame_id,
        )

        residual = (
            _position_array(transformed)
            - _position_array(record.ground_truth)
        )

        errors.append(
            float(np.linalg.norm(residual))
        )

    ordered = sorted(errors)
    count = len(errors)

    if count % 2:
        median = ordered[count // 2]
    else:
        median = (
            ordered[count // 2 - 1]
            + ordered[count // 2]
        ) / 2.0

    return AteResult(
        mean_translation_error_m=sum(errors) / count,
        median_translation_error_m=median,
        rmse_translation_error_m=_rmse(errors),
        p95_translation_error_m=_linear_percentile(
            errors,
            95.0,
        ),
        aligned_sample_count=count,
        per_sample_translation_error_m=tuple(errors),
    )


def _pose_arrays(
    sample: TrajectorySample,
) -> tuple[np.ndarray, np.ndarray]:
    return (
        _quaternion_to_rotation_matrix(
            _quaternion(sample)
        ),
        _position_array(sample),
    )


def _relative_pose(
    first: TrajectorySample,
    second: TrajectorySample,
) -> tuple[np.ndarray, np.ndarray]:
    rotation_first, position_first = _pose_arrays(first)
    rotation_second, position_second = _pose_arrays(second)

    rotation_delta = (
        rotation_first.T
        @ rotation_second
    )

    translation_delta = (
        rotation_first.T
        @ (
            position_second
            - position_first
        )
    )

    return rotation_delta, translation_delta


def _rotation_error_degrees(
    rotation: np.ndarray,
) -> float:
    cosine = (
        float(np.trace(rotation))
        - 1.0
    ) / 2.0

    cosine = max(
        -1.0,
        min(1.0, cosine),
    )

    return math.degrees(
        math.acos(cosine)
    )


def compute_rpe(
    records: Sequence[AlignedTrajectorySample],
    alignment: RigidAlignment,
    *,
    delta_ns: int = RPE_DELTA_NS,
    max_delta_mismatch_ns: int = RPE_MAX_DELTA_MISMATCH_NS,
) -> RpeResult:
    """Compute frozen nearest-1-second relative pose errors.

    For every eligible start sample, the aligned sample nearest t+delta is
    selected. Ties are resolved deterministically toward the earlier sample.
    Pairs outside the frozen +/-50 ms delta tolerance are rejected.
    """

    aligned = _validate_aligned_samples(records)
    validate_rigid_alignment(alignment)

    if type(delta_ns) is not int or delta_ns <= 0:
        _fail("delta_ns must be a positive integer")

    if (
        type(max_delta_mismatch_ns) is not int
        or max_delta_mismatch_ns < 0
    ):
        _fail(
            "max_delta_mismatch_ns must be a nonnegative integer"
        )

    if len(aligned) < 2:
        _fail("RPE requires at least two aligned samples")

    transformed_estimated = tuple(
        apply_rigid_alignment(
            record.estimated,
            alignment,
            target_frame_id=record.ground_truth.frame_id,
        )
        for record in aligned
    )

    timestamps = tuple(
        record.timestamp_ns
        for record in aligned
    )

    pair_results: list[RpePairResult] = []

    for start_index, start_timestamp in enumerate(
        timestamps
    ):
        if start_index == len(timestamps) - 1:
            break

        target = start_timestamp + delta_ns

        insertion = bisect_left(
            timestamps,
            target,
            lo=start_index + 1,
        )

        candidate_indices: list[int] = []

        if (
            insertion - 1 > start_index
            and insertion - 1 < len(timestamps)
        ):
            candidate_indices.append(
                insertion - 1
            )

        if insertion < len(timestamps):
            candidate_indices.append(
                insertion
            )

        if not candidate_indices:
            continue

        end_index = min(
            candidate_indices,
            key=lambda index: (
                abs(timestamps[index] - target),
                timestamps[index],
            ),
        )

        actual_delta = (
            timestamps[end_index]
            - start_timestamp
        )

        if (
            abs(actual_delta - delta_ns)
            > max_delta_mismatch_ns
        ):
            continue

        est_rotation_delta, est_translation_delta = (
            _relative_pose(
                transformed_estimated[start_index],
                transformed_estimated[end_index],
            )
        )

        gt_rotation_delta, gt_translation_delta = (
            _relative_pose(
                aligned[start_index].ground_truth,
                aligned[end_index].ground_truth,
            )
        )

        error_rotation = (
            gt_rotation_delta.T
            @ est_rotation_delta
        )

        error_translation = (
            gt_rotation_delta.T
            @ (
                est_translation_delta
                - gt_translation_delta
            )
        )

        pair_results.append(
            RpePairResult(
                start_timestamp_ns=start_timestamp,
                end_timestamp_ns=timestamps[end_index],
                actual_delta_ns=actual_delta,
                translation_error_m=float(
                    np.linalg.norm(
                        error_translation
                    )
                ),
                rotation_error_deg=_rotation_error_degrees(
                    error_rotation
                ),
            )
        )

    if not pair_results:
        _fail(
            "no eligible RPE pairs satisfy the frozen delta policy"
        )

    translation_errors = tuple(
        result.translation_error_m
        for result in pair_results
    )

    rotation_errors = tuple(
        result.rotation_error_deg
        for result in pair_results
    )

    return RpeResult(
        translation_rmse_m=_rmse(
            translation_errors
        ),
        rotation_rmse_deg=_rmse(
            rotation_errors
        ),
        evaluated_pair_count=len(pair_results),
        pairs=tuple(pair_results),
    )


def evaluate_trajectory_metrics(
    records: Sequence[AlignedTrajectorySample],
) -> TrajectoryMetricResult:
    """Fit one no-scale alignment and compute frozen ATE and RPE."""

    aligned = _validate_aligned_samples(records)

    alignment = fit_rigid_alignment(
        aligned
    )

    return TrajectoryMetricResult(
        alignment=alignment,
        ate=compute_ate(
            aligned,
            alignment,
        ),
        rpe=compute_rpe(
            aligned,
            alignment,
        ),
    )
