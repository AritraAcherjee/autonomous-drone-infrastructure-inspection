"""Synthetic-only tests for the frozen P19 trajectory foundation."""

from __future__ import annotations

from dataclasses import fields
import json
import math
from pathlib import Path

import pytest

from src.evaluation.trajectory import (
    MAX_GT_BRACKET_SPAN_NS,
    PRIMARY_WINDOW_END_NS,
    PRIMARY_WINDOW_START_NS,
    SECONDARY_WINDOW_END_NS,
    SECONDARY_WINDOW_START_NS,
    TrajectorySample,
    TrajectoryValidationError,
    associate_ground_truth,
    interpolate_ground_truth_sample,
    primary_window,
    secondary_window,
    slerp_quaternion,
    validate_trajectory,
    validate_trajectory_sample,
)


ROOT = Path(__file__).resolve().parents[2]


def sample(
    timestamp_ns: int,
    *,
    x_m: float = 0.0,
    y_m: float = 0.0,
    z_m: float = 0.0,
    qx: float = 0.0,
    qy: float = 0.0,
    qz: float = 0.0,
    qw: float = 1.0,
    frame_id: str = "odom",
    child_frame_id: str = "base_link",
) -> TrajectorySample:
    return TrajectorySample(
        timestamp_ns=timestamp_ns,
        x_m=x_m,
        y_m=y_m,
        z_m=z_m,
        qx=qx,
        qy=qy,
        qz=qz,
        qw=qw,
        frame_id=frame_id,
        child_frame_id=child_frame_id,
    )


def gt(
    timestamp_ns: int,
    **kwargs,
) -> TrajectorySample:
    return sample(
        timestamp_ns,
        frame_id="world",
        child_frame_id="base_link",
        **kwargs,
    )


def test_protocol_matches_frozen_control_center_contract() -> None:
    protocol = json.loads(
        (
            ROOT
            / "configs"
            / "evaluation"
            / "p19_spatial_protocol.yaml"
        ).read_text(encoding="utf-8")
    )

    assert protocol["state"] == "FROZEN"
    assert protocol["workstream"] == "P19"
    assert protocol["real_project_metrics_authorized"] is False

    trajectory = protocol["trajectory"]

    assert (
        trajectory["timestamp_association"]["max_gt_bracket_span_ns"]
        == 50_000_000
    )

    assert trajectory["alignment"] == {
        "method": "least_squares_umeyama_rigid_se3",
        "scale": 1.0,
        "rescale_estimated_trajectory": False,
    }

    assert trajectory["rpe"]["headline_delta_ns"] == 1_000_000_000
    assert trajectory["rpe"]["max_delta_mismatch_ns"] == 50_000_000

    assert trajectory["windows"]["primary"] == {
        "start_offset_ns": 3_000_000_000,
        "end_offset_ns": 18_000_000_000,
    }

    assert trajectory["windows"]["secondary"] == {
        "start_offset_ns": 0,
        "end_offset_ns": 20_000_000_000,
    }


def test_trajectory_sample_has_exact_frozen_fields() -> None:
    assert [field.name for field in fields(TrajectorySample)] == [
        "timestamp_ns",
        "x_m",
        "y_m",
        "z_m",
        "qx",
        "qy",
        "qz",
        "qw",
        "frame_id",
        "child_frame_id",
    ]


def test_valid_sample_is_preserved_without_mutation() -> None:
    value = sample(
        123,
        x_m=1.25,
        y_m=-2.5,
        z_m=3.75,
    )

    assert validate_trajectory_sample(value) is value


@pytest.mark.parametrize(
    ("field_name", "invalid"),
    [
        ("x_m", float("nan")),
        ("y_m", float("inf")),
        ("z_m", float("-inf")),
        ("qx", float("nan")),
        ("qw", float("inf")),
    ],
)
def test_nonfinite_values_fail_closed(
    field_name: str,
    invalid: float,
) -> None:
    values = {
        "timestamp_ns": 0,
        "x_m": 0.0,
        "y_m": 0.0,
        "z_m": 0.0,
        "qx": 0.0,
        "qy": 0.0,
        "qz": 0.0,
        "qw": 1.0,
        "frame_id": "odom",
        "child_frame_id": "base_link",
    }

    values[field_name] = invalid

    with pytest.raises(TrajectoryValidationError):
        validate_trajectory_sample(
            TrajectorySample(**values)
        )


@pytest.mark.parametrize(
    "timestamp_ns",
    [
        -1,
        True,
        1.0,
    ],
)
def test_invalid_timestamp_fails_closed(timestamp_ns: object) -> None:
    with pytest.raises(TrajectoryValidationError):
        validate_trajectory_sample(
            sample(timestamp_ns)  # type: ignore[arg-type]
        )


def test_zero_norm_quaternion_is_rejected() -> None:
    with pytest.raises(
        TrajectoryValidationError,
        match="nonzero",
    ):
        validate_trajectory_sample(
            sample(
                0,
                qx=0.0,
                qy=0.0,
                qz=0.0,
                qw=0.0,
            )
        )


def test_timestamp_ordering_is_strict() -> None:
    validate_trajectory(
        (
            sample(1),
            sample(2),
            sample(3),
        )
    )

    with pytest.raises(
        TrajectoryValidationError,
        match="strictly increasing",
    ):
        validate_trajectory(
            (
                sample(1),
                sample(3),
                sample(2),
            )
        )


def test_duplicate_timestamps_are_rejected() -> None:
    with pytest.raises(
        TrajectoryValidationError,
        match="strictly increasing",
    ):
        validate_trajectory(
            (
                sample(10),
                sample(10),
            )
        )


def test_trajectory_frames_must_remain_constant() -> None:
    with pytest.raises(
        TrajectoryValidationError,
        match="frame_id",
    ):
        validate_trajectory(
            (
                sample(1, frame_id="odom"),
                sample(2, frame_id="map"),
            )
        )


def test_exact_gt_timestamp_is_associated_directly() -> None:
    estimated = (
        sample(10_000_000, x_m=99.0),
    )

    truth = (
        gt(0, x_m=0.0),
        gt(10_000_000, x_m=1.0),
        gt(20_000_000, x_m=2.0),
    )

    result = associate_ground_truth(
        estimated,
        truth,
    )

    assert result.estimator_sample_count == 1
    assert result.aligned_sample_count == 1
    assert result.dropped_sample_count == 0
    assert result.timestamp_alignment_coverage == 1.0
    assert result.aligned[0].ground_truth.x_m == 1.0


def test_translation_is_linearly_interpolated() -> None:
    interpolated = interpolate_ground_truth_sample(
        gt(
            0,
            x_m=0.0,
            y_m=2.0,
            z_m=-2.0,
        ),
        gt(
            40_000_000,
            x_m=4.0,
            y_m=6.0,
            z_m=2.0,
        ),
        20_000_000,
    )

    assert interpolated.timestamp_ns == 20_000_000
    assert interpolated.x_m == pytest.approx(2.0)
    assert interpolated.y_m == pytest.approx(4.0)
    assert interpolated.z_m == pytest.approx(0.0)


def test_slerp_halfway_rotation_is_deterministic() -> None:
    result = slerp_quaternion(
        (0.0, 0.0, 0.0, 1.0),
        (0.0, 0.0, 1.0, 0.0),
        0.5,
    )

    root_half = math.sqrt(0.5)

    assert result[0] == pytest.approx(0.0)
    assert result[1] == pytest.approx(0.0)
    assert abs(result[2]) == pytest.approx(root_half)
    assert abs(result[3]) == pytest.approx(root_half)


def test_quaternion_q_and_negative_q_are_equivalent() -> None:
    q = (
        0.1,
        -0.2,
        0.3,
        0.9,
    )

    negative = tuple(-value for value in q)

    a = slerp_quaternion(q, q, 0.5)
    b = slerp_quaternion(q, negative, 0.5)

    assert a == pytest.approx(b)


def test_fifty_ms_gt_bracket_is_accepted() -> None:
    estimated = (
        sample(25_000_000),
    )

    truth = (
        gt(0, x_m=0.0),
        gt(MAX_GT_BRACKET_SPAN_NS, x_m=1.0),
    )

    result = associate_ground_truth(
        estimated,
        truth,
    )

    assert result.aligned_sample_count == 1
    assert (
        result.aligned[0].ground_truth.x_m
        == pytest.approx(0.5)
    )


def test_more_than_fifty_ms_gt_bracket_is_rejected() -> None:
    estimated = (
        sample(25_000_000),
    )

    truth = (
        gt(0),
        gt(MAX_GT_BRACKET_SPAN_NS + 1),
    )

    result = associate_ground_truth(
        estimated,
        truth,
    )

    assert result.estimator_sample_count == 1
    assert result.aligned_sample_count == 0
    assert result.dropped_sample_count == 1
    assert result.timestamp_alignment_coverage == 0.0


def test_no_extrapolation_before_or_after_gt() -> None:
    estimated = (
        sample(1),
        sample(10),
        sample(30),
    )

    truth = (
        gt(5),
        gt(10),
        gt(20),
    )

    result = associate_ground_truth(
        estimated,
        truth,
    )

    assert tuple(
        record.timestamp_ns
        for record in result.aligned
    ) == (10,)

    assert result.estimator_sample_count == 3
    assert result.aligned_sample_count == 1
    assert result.dropped_sample_count == 2
    assert result.timestamp_alignment_coverage == pytest.approx(
        1.0 / 3.0
    )


def test_coverage_and_duration_accounting() -> None:
    estimated = (
        sample(0),
        sample(10_000_000),
        sample(20_000_000),
        sample(30_000_000),
    )

    truth = (
        gt(0),
        gt(20_000_000),
    )

    result = associate_ground_truth(
        estimated,
        truth,
    )

    assert result.estimator_sample_count == 4
    assert result.aligned_sample_count == 3
    assert result.dropped_sample_count == 1
    assert result.timestamp_alignment_coverage == pytest.approx(0.75)
    assert result.evaluated_duration_s == pytest.approx(0.03)


def test_primary_window_is_three_to_eighteen_seconds_from_explicit_start() -> None:
    start = 100_000_000_000

    trajectory = tuple(
        sample(start + offset)
        for offset in (
            2_999_999_999,
            PRIMARY_WINDOW_START_NS,
            10_000_000_000,
            PRIMARY_WINDOW_END_NS,
            18_000_000_001,
        )
    )

    selected = primary_window(
        trajectory,
        run_start_timestamp_ns=start,
    )

    assert tuple(
        value.timestamp_ns - start
        for value in selected
    ) == (
        3_000_000_000,
        10_000_000_000,
        18_000_000_000,
    )


def test_secondary_window_is_zero_to_twenty_seconds_from_explicit_start() -> None:
    start = 50_000_000_000

    trajectory = tuple(
        sample(start + offset)
        for offset in (
            SECONDARY_WINDOW_START_NS,
            3_000_000_000,
            SECONDARY_WINDOW_END_NS,
            20_000_000_001,
        )
    )

    selected = secondary_window(
        trajectory,
        run_start_timestamp_ns=start,
    )

    assert tuple(
        value.timestamp_ns - start
        for value in selected
    ) == (
        0,
        3_000_000_000,
        20_000_000_000,
    )


def test_window_origin_is_explicit_p13_start_not_first_vio_output() -> None:
    run_start = 10_000_000_000

    trajectory = (
        sample(15_000_000_000),
        sample(20_000_000_000),
        sample(29_000_000_000),
    )

    selected = primary_window(
        trajectory,
        run_start_timestamp_ns=run_start,
    )

    assert tuple(
        value.timestamp_ns
        for value in selected
    ) == (
        15_000_000_000,
        20_000_000_000,
    )


def test_repeated_association_is_identical() -> None:
    estimated = (
        sample(10_000_000),
        sample(20_000_000),
        sample(30_000_000),
    )

    truth = (
        gt(0, x_m=0.0),
        gt(40_000_000, x_m=4.0),
    )

    first = associate_ground_truth(
        estimated,
        truth,
    )

    second = associate_ground_truth(
        estimated,
        truth,
    )

    assert first == second


def test_no_ros_gazebo_or_runtime_dependencies_in_pure_module() -> None:
    import ast

    path = (
        ROOT
        / "src"
        / "evaluation"
        / "trajectory.py"
    )

    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )

    forbidden = (
        "rclpy",
        "rospy",
        "tf2",
        "gazebo",
        "nav_msgs",
        "geometry_msgs",
        "sensor_msgs",
        "ultralytics",
        "torch",
    )

    violations = []

    for node in ast.walk(tree):
        imported = []

        if isinstance(node, ast.Import):
            imported = [
                alias.name
                for alias in node.names
            ]

        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
        ):
            imported = [node.module]

        for name in imported:
            if name.startswith(forbidden):
                violations.append(name)

    assert violations == []


from src.evaluation.trajectory import (
    AlignedTrajectorySample,
    RPE_DELTA_NS,
    RPE_MAX_DELTA_MISMATCH_NS,
    RigidAlignment,
    apply_rigid_alignment,
    compute_ate,
    compute_rpe,
    fit_rigid_alignment,
    validate_rigid_alignment,
)


_IDENTITY_ALIGNMENT = RigidAlignment(
    rotation=(
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    ),
    translation_m=(0.0, 0.0, 0.0),
)


def _aligned(
    timestamp_ns: int,
    *,
    estimated_xyz: tuple[float, float, float],
    ground_truth_xyz: tuple[float, float, float],
    estimated_quaternion: tuple[
        float,
        float,
        float,
        float,
    ] = (0.0, 0.0, 0.0, 1.0),
    ground_truth_quaternion: tuple[
        float,
        float,
        float,
        float,
    ] = (0.0, 0.0, 0.0, 1.0),
) -> AlignedTrajectorySample:
    estimated = sample(
        timestamp_ns,
        x_m=estimated_xyz[0],
        y_m=estimated_xyz[1],
        z_m=estimated_xyz[2],
        qx=estimated_quaternion[0],
        qy=estimated_quaternion[1],
        qz=estimated_quaternion[2],
        qw=estimated_quaternion[3],
    )

    truth = gt(
        timestamp_ns,
        x_m=ground_truth_xyz[0],
        y_m=ground_truth_xyz[1],
        z_m=ground_truth_xyz[2],
        qx=ground_truth_quaternion[0],
        qy=ground_truth_quaternion[1],
        qz=ground_truth_quaternion[2],
        qw=ground_truth_quaternion[3],
    )

    return AlignedTrajectorySample(
        timestamp_ns=timestamp_ns,
        estimated=estimated,
        ground_truth=truth,
    )


def _axis_points() -> tuple[
    tuple[float, float, float],
    ...,
]:
    return (
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
    )


def test_frozen_no_scale_umeyama_recovers_known_rigid_transform() -> None:
    root_half = math.sqrt(0.5)

    gt_quaternion = (
        0.0,
        0.0,
        root_half,
        root_half,
    )

    def transform(
        point: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        x, y, z = point

        # Rz(+90 deg) plus translation (5, -2, 3).
        return (
            -y + 5.0,
            x - 2.0,
            z + 3.0,
        )

    records = tuple(
        _aligned(
            index * RPE_DELTA_NS,
            estimated_xyz=point,
            ground_truth_xyz=transform(point),
            ground_truth_quaternion=gt_quaternion,
        )
        for index, point in enumerate(
            _axis_points()
        )
    )

    alignment = fit_rigid_alignment(records)

    assert alignment.translation_m == pytest.approx(
        (5.0, -2.0, 3.0),
        abs=1e-12,
    )

    transformed = apply_rigid_alignment(
        records[0].estimated,
        alignment,
        target_frame_id="world",
    )

    assert (
        transformed.x_m,
        transformed.y_m,
        transformed.z_m,
    ) == pytest.approx(
        records[0].ground_truth.position
        if hasattr(records[0].ground_truth, "position")
        else (
            records[0].ground_truth.x_m,
            records[0].ground_truth.y_m,
            records[0].ground_truth.z_m,
        ),
        abs=1e-12,
    )

    assert abs(transformed.qz) == pytest.approx(
        root_half,
        abs=1e-12,
    )

    assert abs(transformed.qw) == pytest.approx(
        root_half,
        abs=1e-12,
    )


def test_known_rigid_offset_has_zero_ate_after_alignment() -> None:
    def transform(
        point: tuple[float, float, float],
    ) -> tuple[float, float, float]:
        x, y, z = point
        return (
            -y + 10.0,
            x + 4.0,
            z - 7.0,
        )

    records = tuple(
        _aligned(
            index * RPE_DELTA_NS,
            estimated_xyz=point,
            ground_truth_xyz=transform(point),
        )
        for index, point in enumerate(
            _axis_points()
        )
    )

    alignment = fit_rigid_alignment(records)
    ate = compute_ate(records, alignment)

    assert ate.aligned_sample_count == 6
    assert ate.mean_translation_error_m == pytest.approx(
        0.0,
        abs=1e-12,
    )
    assert ate.median_translation_error_m == pytest.approx(
        0.0,
        abs=1e-12,
    )
    assert ate.rmse_translation_error_m == pytest.approx(
        0.0,
        abs=1e-12,
    )
    assert ate.p95_translation_error_m == pytest.approx(
        0.0,
        abs=1e-12,
    )


def test_no_scale_alignment_does_not_hide_scale_error() -> None:
    records = tuple(
        _aligned(
            index * RPE_DELTA_NS,
            estimated_xyz=point,
            ground_truth_xyz=tuple(
                2.0 * value
                for value in point
            ),
        )
        for index, point in enumerate(
            _axis_points()
        )
    )

    alignment = fit_rigid_alignment(records)
    ate = compute_ate(records, alignment)

    # Frozen SE(3) cannot rescale unit-radius estimates to radius 2.
    assert ate.rmse_translation_error_m == pytest.approx(
        1.0,
        abs=1e-12,
    )

    assert ate.mean_translation_error_m == pytest.approx(
        1.0,
        abs=1e-12,
    )

    assert ate.median_translation_error_m == pytest.approx(
        1.0,
        abs=1e-12,
    )

    assert ate.p95_translation_error_m == pytest.approx(
        1.0,
        abs=1e-12,
    )


def test_alignment_requires_non_collinear_positions() -> None:
    records = tuple(
        _aligned(
            index * RPE_DELTA_NS,
            estimated_xyz=(float(index), 0.0, 0.0),
            ground_truth_xyz=(float(index), 0.0, 0.0),
        )
        for index in range(4)
    )

    with pytest.raises(
        TrajectoryValidationError,
        match="non-collinear",
    ):
        fit_rigid_alignment(records)


def test_alignment_rejects_fewer_than_three_samples() -> None:
    records = (
        _aligned(
            0,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
        ),
        _aligned(
            RPE_DELTA_NS,
            estimated_xyz=(1.0, 0.0, 0.0),
            ground_truth_xyz=(1.0, 0.0, 0.0),
        ),
    )

    with pytest.raises(
        TrajectoryValidationError,
        match="at least three",
    ):
        fit_rigid_alignment(records)


def test_invalid_reflection_is_not_a_valid_se3_alignment() -> None:
    invalid = RigidAlignment(
        rotation=(
            (-1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        translation_m=(0.0, 0.0, 0.0),
    )

    with pytest.raises(
        TrajectoryValidationError,
        match=r"det\(R\)=\+1",
    ):
        validate_rigid_alignment(invalid)


def test_known_one_second_rpe_translation_error() -> None:
    records = (
        _aligned(
            0,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
        ),
        _aligned(
            RPE_DELTA_NS,
            estimated_xyz=(2.0, 0.0, 0.0),
            ground_truth_xyz=(1.0, 0.0, 0.0),
        ),
    )

    result = compute_rpe(
        records,
        _IDENTITY_ALIGNMENT,
    )

    assert result.evaluated_pair_count == 1
    assert result.translation_rmse_m == pytest.approx(
        1.0,
        abs=1e-12,
    )
    assert result.rotation_rmse_deg == pytest.approx(
        0.0,
        abs=1e-12,
    )
    assert result.pairs[0].actual_delta_ns == RPE_DELTA_NS


def test_known_one_second_rpe_rotation_error_in_degrees() -> None:
    q10 = (
        0.0,
        0.0,
        math.sin(math.radians(5.0)),
        math.cos(math.radians(5.0)),
    )

    q20 = (
        0.0,
        0.0,
        math.sin(math.radians(10.0)),
        math.cos(math.radians(10.0)),
    )

    records = (
        _aligned(
            0,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
        ),
        _aligned(
            RPE_DELTA_NS,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
            estimated_quaternion=q20,
            ground_truth_quaternion=q10,
        ),
    )

    result = compute_rpe(
        records,
        _IDENTITY_ALIGNMENT,
    )

    assert result.evaluated_pair_count == 1
    assert result.translation_rmse_m == pytest.approx(
        0.0,
        abs=1e-12,
    )
    assert result.rotation_rmse_deg == pytest.approx(
        10.0,
        abs=1e-9,
    )


def test_rpe_q_and_negative_q_are_equivalent() -> None:
    q = (
        0.0,
        0.0,
        math.sin(math.radians(15.0)),
        math.cos(math.radians(15.0)),
    )

    negative_q = tuple(
        -value
        for value in q
    )

    records = (
        _aligned(
            0,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
        ),
        _aligned(
            RPE_DELTA_NS,
            estimated_xyz=(1.0, 0.0, 0.0),
            ground_truth_xyz=(1.0, 0.0, 0.0),
            estimated_quaternion=negative_q,
            ground_truth_quaternion=q,
        ),
    )

    result = compute_rpe(
        records,
        _IDENTITY_ALIGNMENT,
    )

    assert result.translation_rmse_m == pytest.approx(
        0.0,
        abs=1e-12,
    )
    assert result.rotation_rmse_deg == pytest.approx(
        0.0,
        abs=1e-9,
    )


def test_rpe_exact_fifty_ms_delta_mismatch_is_accepted() -> None:
    actual_delta = (
        RPE_DELTA_NS
        + RPE_MAX_DELTA_MISMATCH_NS
    )

    records = (
        _aligned(
            0,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
        ),
        _aligned(
            actual_delta,
            estimated_xyz=(1.0, 0.0, 0.0),
            ground_truth_xyz=(1.0, 0.0, 0.0),
        ),
    )

    result = compute_rpe(
        records,
        _IDENTITY_ALIGNMENT,
    )

    assert result.evaluated_pair_count == 1
    assert result.pairs[0].actual_delta_ns == actual_delta


def test_rpe_more_than_fifty_ms_delta_mismatch_fails_closed() -> None:
    actual_delta = (
        RPE_DELTA_NS
        + RPE_MAX_DELTA_MISMATCH_NS
        + 1
    )

    records = (
        _aligned(
            0,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
        ),
        _aligned(
            actual_delta,
            estimated_xyz=(1.0, 0.0, 0.0),
            ground_truth_xyz=(1.0, 0.0, 0.0),
        ),
    )

    with pytest.raises(
        TrajectoryValidationError,
        match="no eligible RPE pairs",
    ):
        compute_rpe(
            records,
            _IDENTITY_ALIGNMENT,
        )


def test_rpe_nearest_target_tie_prefers_earlier_timestamp() -> None:
    records = (
        _aligned(
            0,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
        ),
        _aligned(
            960_000_000,
            estimated_xyz=(1.0, 0.0, 0.0),
            ground_truth_xyz=(1.0, 0.0, 0.0),
        ),
        _aligned(
            1_040_000_000,
            estimated_xyz=(2.0, 0.0, 0.0),
            ground_truth_xyz=(2.0, 0.0, 0.0),
        ),
    )

    result = compute_rpe(
        records,
        _IDENTITY_ALIGNMENT,
    )

    assert result.pairs[0].start_timestamp_ns == 0
    assert result.pairs[0].end_timestamp_ns == 960_000_000


def test_rpe_shortest_rotation_angle_is_used() -> None:
    q350 = (
        0.0,
        0.0,
        math.sin(math.radians(175.0)),
        math.cos(math.radians(175.0)),
    )

    records = (
        _aligned(
            0,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
        ),
        _aligned(
            RPE_DELTA_NS,
            estimated_xyz=(0.0, 0.0, 0.0),
            ground_truth_xyz=(0.0, 0.0, 0.0),
            estimated_quaternion=q350,
        ),
    )

    result = compute_rpe(
        records,
        _IDENTITY_ALIGNMENT,
    )

    assert result.rotation_rmse_deg == pytest.approx(
        10.0,
        abs=1e-9,
    )


def test_repeated_ate_and_rpe_results_are_identical() -> None:
    records = tuple(
        _aligned(
            index * RPE_DELTA_NS,
            estimated_xyz=point,
            ground_truth_xyz=point,
        )
        for index, point in enumerate(
            _axis_points()
        )
    )

    alignment_a = fit_rigid_alignment(records)
    alignment_b = fit_rigid_alignment(records)

    assert alignment_a == alignment_b

    assert (
        compute_ate(records, alignment_a)
        == compute_ate(records, alignment_b)
    )

    assert (
        compute_rpe(records, alignment_a)
        == compute_rpe(records, alignment_b)
    )



def test_alignment_output_quaternion_uses_builtin_python_floats() -> None:
    records = tuple(
        _aligned(
            index * RPE_DELTA_NS,
            estimated_xyz=point,
            ground_truth_xyz=point,
        )
        for index, point in enumerate(
            _axis_points()
        )
    )

    alignment = fit_rigid_alignment(records)

    transformed = apply_rigid_alignment(
        records[0].estimated,
        alignment,
        target_frame_id="world",
    )

    assert type(transformed.qx) is float
    assert type(transformed.qy) is float
    assert type(transformed.qz) is float
    assert type(transformed.qw) is float

    validate_trajectory_sample(transformed)
