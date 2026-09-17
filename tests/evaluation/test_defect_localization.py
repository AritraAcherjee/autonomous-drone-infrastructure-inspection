"""Synthetic-only tests for frozen P19 3D defect localization."""

from __future__ import annotations

from dataclasses import fields
import math
from pathlib import Path

import pytest

from src.evaluation.defect_localization import (
    DefectCorrespondence,
    DefectLocalizationError,
    EstimatedDefect,
    GroundTruthDefect,
    MapFromWorldTransform,
    evaluate_defect_localization,
    transform_ground_truth_to_map,
    validate_t_map_from_world,
)


ROOT = Path(__file__).resolve().parents[2]


IDENTITY = MapFromWorldTransform(
    matrix=(
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
)


def estimated(
    defect_id: str,
    class_name: str,
    xyz: tuple[float, float, float],
) -> EstimatedDefect:
    return EstimatedDefect(
        estimated_defect_id=defect_id,
        class_name=class_name,
        x_m=xyz[0],
        y_m=xyz[1],
        z_m=xyz[2],
        coordinate_frame="map",
    )


def truth(
    defect_id: str,
    class_name: str,
    xyz: tuple[float, float, float],
) -> GroundTruthDefect:
    return GroundTruthDefect(
        gt_defect_id=defect_id,
        class_name=class_name,
        x_m=xyz[0],
        y_m=xyz[1],
        z_m=xyz[2],
        coordinate_frame="world",
    )


def correspondence(
    estimated_id: str,
    gt_id: str,
) -> DefectCorrespondence:
    return DefectCorrespondence(
        estimated_defect_id=estimated_id,
        gt_defect_id=gt_id,
    )


def test_ground_truth_defect_has_frozen_fields() -> None:
    assert [
        field.name
        for field in fields(GroundTruthDefect)
    ] == [
        "gt_defect_id",
        "class_name",
        "x_m",
        "y_m",
        "z_m",
        "coordinate_frame",
    ]


def test_identical_points_have_zero_error() -> None:
    result = evaluate_defect_localization(
        (estimated("est-1", "Crack", (1.0, 2.0, 3.0)),),
        (truth("gt-1", "Crack", (1.0, 2.0, 3.0)),),
        (correspondence("est-1", "gt-1"),),
        t_map_from_world=IDENTITY,
    )

    assert result.matched_count == 1
    assert result.unmatched_estimated_count == 0
    assert result.unmatched_gt_count == 0

    match = result.matches[0]

    assert match.signed_x_error_m == 0.0
    assert match.signed_y_error_m == 0.0
    assert match.signed_z_error_m == 0.0

    assert match.absolute_x_error_m == 0.0
    assert match.absolute_y_error_m == 0.0
    assert match.absolute_z_error_m == 0.0

    assert match.euclidean_error_m == 0.0

    assert result.mean_euclidean_error_m == 0.0
    assert result.median_euclidean_error_m == 0.0
    assert result.rmse_euclidean_error_m == 0.0
    assert result.p95_euclidean_error_m == 0.0


def test_signed_axis_errors_use_estimate_minus_ground_truth() -> None:
    result = evaluate_defect_localization(
        (estimated("est", "Hole", (3.0, -1.0, 8.0)),),
        (truth("gt", "Hole", (1.0, 2.0, 4.0)),),
        (correspondence("est", "gt"),),
        t_map_from_world=IDENTITY,
    )

    match = result.matches[0]

    assert match.signed_x_error_m == pytest.approx(2.0)
    assert match.signed_y_error_m == pytest.approx(-3.0)
    assert match.signed_z_error_m == pytest.approx(4.0)

    assert match.absolute_x_error_m == pytest.approx(2.0)
    assert match.absolute_y_error_m == pytest.approx(3.0)
    assert match.absolute_z_error_m == pytest.approx(4.0)


def test_known_euclidean_error() -> None:
    result = evaluate_defect_localization(
        (estimated("est", "Crack", (3.0, 4.0, 12.0)),),
        (truth("gt", "Crack", (0.0, 0.0, 0.0)),),
        (correspondence("est", "gt"),),
        t_map_from_world=IDENTITY,
    )

    assert result.matches[0].euclidean_error_m == pytest.approx(
        13.0
    )


def test_world_to_map_transform_fixture() -> None:
    # Rz(+90 deg) with translation (10, -2, 3).
    transform = MapFromWorldTransform(
        matrix=(
            (0.0, -1.0, 0.0, 10.0),
            (1.0, 0.0, 0.0, -2.0),
            (0.0, 0.0, 1.0, 3.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    )

    point = transform_ground_truth_to_map(
        truth("gt", "Breakage", (2.0, 1.0, 4.0)),
        transform,
    )

    assert point == pytest.approx(
        (9.0, 0.0, 7.0)
    )

    result = evaluate_defect_localization(
        (estimated("est", "Breakage", (9.0, 0.0, 7.0)),),
        (truth("gt", "Breakage", (2.0, 1.0, 4.0)),),
        (correspondence("est", "gt"),),
        t_map_from_world=transform,
    )

    assert result.matches[0].euclidean_error_m == pytest.approx(
        0.0,
        abs=1e-12,
    )


def test_missing_world_to_map_transform_fails_closed() -> None:
    with pytest.raises(
        DefectLocalizationError,
        match="T_map_from_world is required",
    ):
        evaluate_defect_localization(
            (estimated("est", "Crack", (0.0, 0.0, 0.0)),),
            (truth("gt", "Crack", (0.0, 0.0, 0.0)),),
            (correspondence("est", "gt"),),
            t_map_from_world=None,
        )


@pytest.mark.parametrize(
    "transform",
    [
        MapFromWorldTransform(
            matrix=(
                (1.0, 0.0, 0.0, 0.0),
                (0.0, 1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 0.0),
            )  # type: ignore[arg-type]
        ),
        MapFromWorldTransform(
            matrix=(
                (2.0, 0.0, 0.0, 0.0),
                (0.0, 1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
            )
        ),
        MapFromWorldTransform(
            matrix=(
                (-1.0, 0.0, 0.0, 0.0),
                (0.0, 1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
            )
        ),
        MapFromWorldTransform(
            matrix=(
                (1.0, 0.0, 0.0, 0.0),
                (0.0, 1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 0.0),
                (0.0, 0.0, 1.0, 1.0),
            )
        ),
        MapFromWorldTransform(
            matrix=(
                (1.0, 0.0, 0.0, float("nan")),
                (0.0, 1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 0.0),
                (0.0, 0.0, 0.0, 1.0),
            )
        ),
    ],
)
def test_invalid_nonrigid_transform_rejected(
    transform: MapFromWorldTransform,
) -> None:
    with pytest.raises(DefectLocalizationError):
        validate_t_map_from_world(transform)


def test_estimate_must_be_exact_map_frame() -> None:
    invalid = EstimatedDefect(
        estimated_defect_id="est",
        class_name="Crack",
        x_m=0.0,
        y_m=0.0,
        z_m=0.0,
        coordinate_frame="odom",
    )

    with pytest.raises(
        DefectLocalizationError,
        match='exactly "map"',
    ):
        evaluate_defect_localization(
            (invalid,),
            (truth("gt", "Crack", (0.0, 0.0, 0.0)),),
            (correspondence("est", "gt"),),
            t_map_from_world=IDENTITY,
        )


def test_ground_truth_must_be_world_frame() -> None:
    invalid = GroundTruthDefect(
        gt_defect_id="gt",
        class_name="Crack",
        x_m=0.0,
        y_m=0.0,
        z_m=0.0,
        coordinate_frame="map",
    )

    with pytest.raises(
        DefectLocalizationError,
        match='exactly "world"',
    ):
        evaluate_defect_localization(
            (estimated("est", "Crack", (0.0, 0.0, 0.0)),),
            (invalid,),
            (correspondence("est", "gt"),),
            t_map_from_world=IDENTITY,
        )


def test_duplicate_estimated_id_rejected() -> None:
    estimates = (
        estimated("est", "Crack", (0.0, 0.0, 0.0)),
        estimated("est", "Crack", (1.0, 0.0, 0.0)),
    )

    with pytest.raises(
        DefectLocalizationError,
        match="duplicate estimated",
    ):
        evaluate_defect_localization(
            estimates,
            (truth("gt", "Crack", (0.0, 0.0, 0.0)),),
            (),
            t_map_from_world=IDENTITY,
        )


def test_duplicate_gt_id_rejected() -> None:
    ground_truth = (
        truth("gt", "Crack", (0.0, 0.0, 0.0)),
        truth("gt", "Crack", (1.0, 0.0, 0.0)),
    )

    with pytest.raises(
        DefectLocalizationError,
        match="duplicate gt_defect_id",
    ):
        evaluate_defect_localization(
            (),
            ground_truth,
            (),
            t_map_from_world=IDENTITY,
        )


def test_duplicate_estimated_correspondence_rejected() -> None:
    mappings = (
        correspondence("est", "gt-1"),
        correspondence("est", "gt-2"),
    )

    with pytest.raises(
        DefectLocalizationError,
        match="duplicate correspondence for estimated",
    ):
        evaluate_defect_localization(
            (estimated("est", "Crack", (0.0, 0.0, 0.0)),),
            (
                truth("gt-1", "Crack", (0.0, 0.0, 0.0)),
                truth("gt-2", "Crack", (0.0, 0.0, 0.0)),
            ),
            mappings,
            t_map_from_world=IDENTITY,
        )


def test_duplicate_gt_correspondence_rejected() -> None:
    mappings = (
        correspondence("est-1", "gt"),
        correspondence("est-2", "gt"),
    )

    with pytest.raises(
        DefectLocalizationError,
        match="duplicate correspondence for GT",
    ):
        evaluate_defect_localization(
            (
                estimated("est-1", "Crack", (0.0, 0.0, 0.0)),
                estimated("est-2", "Crack", (0.0, 0.0, 0.0)),
            ),
            (truth("gt", "Crack", (0.0, 0.0, 0.0)),),
            mappings,
            t_map_from_world=IDENTITY,
        )


def test_class_mismatch_rejected() -> None:
    with pytest.raises(
        DefectLocalizationError,
        match="class-name agreement",
    ):
        evaluate_defect_localization(
            (estimated("est", "Crack", (0.0, 0.0, 0.0)),),
            (truth("gt", "Hole", (0.0, 0.0, 0.0)),),
            (correspondence("est", "gt"),),
            t_map_from_world=IDENTITY,
        )


def test_correspondence_to_missing_estimate_rejected() -> None:
    with pytest.raises(
        DefectLocalizationError,
        match="missing estimated defect",
    ):
        evaluate_defect_localization(
            (),
            (truth("gt", "Crack", (0.0, 0.0, 0.0)),),
            (correspondence("missing", "gt"),),
            t_map_from_world=IDENTITY,
        )


def test_correspondence_to_missing_gt_rejected() -> None:
    with pytest.raises(
        DefectLocalizationError,
        match="missing GT defect",
    ):
        evaluate_defect_localization(
            (estimated("est", "Crack", (0.0, 0.0, 0.0)),),
            (),
            (correspondence("est", "missing"),),
            t_map_from_world=IDENTITY,
        )


def test_unmatched_records_are_preserved() -> None:
    result = evaluate_defect_localization(
        (
            estimated("est-a", "Crack", (0.0, 0.0, 0.0)),
            estimated("est-b", "Hole", (5.0, 5.0, 5.0)),
        ),
        (
            truth("gt-a", "Crack", (0.0, 0.0, 0.0)),
            truth("gt-b", "Hole", (5.0, 5.0, 5.0)),
        ),
        (correspondence("est-a", "gt-a"),),
        t_map_from_world=IDENTITY,
    )

    assert result.matched_count == 1
    assert result.unmatched_estimated_count == 1
    assert result.unmatched_gt_count == 1

    assert result.unmatched_estimated_ids == (
        "est-b",
    )

    assert result.unmatched_gt_ids == (
        "gt-b",
    )


def test_no_proximity_matching_fallback() -> None:
    # Unmapped estimate and GT occupy the exact same position.
    # They must remain unmatched because identity mapping is explicit-only.
    result = evaluate_defect_localization(
        (
            estimated("mapped-est", "Crack", (1.0, 0.0, 0.0)),
            estimated("near-est", "Hole", (9.0, 9.0, 9.0)),
        ),
        (
            truth("mapped-gt", "Crack", (0.0, 0.0, 0.0)),
            truth("near-gt", "Hole", (9.0, 9.0, 9.0)),
        ),
        (
            correspondence(
                "mapped-est",
                "mapped-gt",
            ),
        ),
        t_map_from_world=IDENTITY,
    )

    assert result.matched_count == 1

    assert result.unmatched_estimated_ids == (
        "near-est",
    )

    assert result.unmatched_gt_ids == (
        "near-gt",
    )


def test_empty_mapping_preserves_all_as_unmatched() -> None:
    result = evaluate_defect_localization(
        (
            estimated("est-2", "Crack", (0.0, 0.0, 0.0)),
            estimated("est-1", "Hole", (1.0, 0.0, 0.0)),
        ),
        (
            truth("gt-2", "Crack", (0.0, 0.0, 0.0)),
            truth("gt-1", "Hole", (1.0, 0.0, 0.0)),
        ),
        (),
        t_map_from_world=IDENTITY,
    )

    assert result.matched_count == 0
    assert result.unmatched_estimated_count == 2
    assert result.unmatched_gt_count == 2

    assert result.unmatched_estimated_ids == (
        "est-1",
        "est-2",
    )

    assert result.unmatched_gt_ids == (
        "gt-1",
        "gt-2",
    )

    assert result.mean_euclidean_error_m is None
    assert result.median_euclidean_error_m is None
    assert result.rmse_euclidean_error_m is None
    assert result.p95_euclidean_error_m is None


def test_mean_median_rmse_and_p95_are_deterministic() -> None:
    # Explicit Euclidean errors: [1, 2, 3, 4].
    estimates = tuple(
        estimated(
            f"est-{index}",
            "Crack",
            (float(error), 0.0, 0.0),
        )
        for index, error in enumerate(
            (1, 2, 3, 4),
            start=1,
        )
    )

    ground_truth = tuple(
        truth(
            f"gt-{index}",
            "Crack",
            (0.0, 0.0, 0.0),
        )
        for index in range(1, 5)
    )

    mappings = tuple(
        correspondence(
            f"est-{index}",
            f"gt-{index}",
        )
        for index in range(1, 5)
    )

    result = evaluate_defect_localization(
        estimates,
        ground_truth,
        mappings,
        t_map_from_world=IDENTITY,
    )

    assert result.matched_count == 4

    assert result.mean_euclidean_error_m == pytest.approx(
        2.5
    )

    assert result.median_euclidean_error_m == pytest.approx(
        2.5
    )

    assert result.rmse_euclidean_error_m == pytest.approx(
        math.sqrt(7.5)
    )

    # Linear percentile with position 0.95 * (4 - 1) = 2.85.
    assert result.p95_euclidean_error_m == pytest.approx(
        3.85
    )


def test_output_match_order_is_deterministic_by_estimated_id() -> None:
    estimates = (
        estimated("est-z", "Crack", (0.0, 0.0, 0.0)),
        estimated("est-a", "Crack", (0.0, 0.0, 0.0)),
    )

    ground_truth = (
        truth("gt-z", "Crack", (0.0, 0.0, 0.0)),
        truth("gt-a", "Crack", (0.0, 0.0, 0.0)),
    )

    mappings = (
        correspondence("est-z", "gt-z"),
        correspondence("est-a", "gt-a"),
    )

    result = evaluate_defect_localization(
        estimates,
        ground_truth,
        mappings,
        t_map_from_world=IDENTITY,
    )

    assert tuple(
        match.estimated_defect_id
        for match in result.matches
    ) == (
        "est-a",
        "est-z",
    )


def test_input_order_does_not_change_result() -> None:
    estimates = (
        estimated("est-b", "Crack", (2.0, 0.0, 0.0)),
        estimated("est-a", "Crack", (1.0, 0.0, 0.0)),
    )

    ground_truth = (
        truth("gt-b", "Crack", (0.0, 0.0, 0.0)),
        truth("gt-a", "Crack", (0.0, 0.0, 0.0)),
    )

    mappings = (
        correspondence("est-b", "gt-b"),
        correspondence("est-a", "gt-a"),
    )

    forward = evaluate_defect_localization(
        estimates,
        ground_truth,
        mappings,
        t_map_from_world=IDENTITY,
    )

    reverse = evaluate_defect_localization(
        tuple(reversed(estimates)),
        tuple(reversed(ground_truth)),
        tuple(reversed(mappings)),
        t_map_from_world=IDENTITY,
    )

    assert forward == reverse


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("x_m", float("nan")),
        ("y_m", float("inf")),
        ("z_m", float("-inf")),
    ],
)
def test_nonfinite_estimated_xyz_rejected(
    field_name: str,
    value: float,
) -> None:
    kwargs = {
        "estimated_defect_id": "est",
        "class_name": "Crack",
        "x_m": 0.0,
        "y_m": 0.0,
        "z_m": 0.0,
        "coordinate_frame": "map",
    }

    kwargs[field_name] = value

    invalid = EstimatedDefect(**kwargs)

    with pytest.raises(DefectLocalizationError):
        evaluate_defect_localization(
            (invalid,),
            (truth("gt", "Crack", (0.0, 0.0, 0.0)),),
            (correspondence("est", "gt"),),
            t_map_from_world=IDENTITY,
        )


def test_pure_source_has_no_ros_gazebo_runtime_imports() -> None:
    import ast

    path = (
        ROOT
        / "src"
        / "evaluation"
        / "defect_localization.py"
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


def test_source_contains_no_nearest_neighbor_matching_path() -> None:
    import ast

    path = (
        ROOT
        / "src"
        / "evaluation"
        / "defect_localization.py"
    )

    tree = ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )

    called_names = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            called_names.add(node.func.id)

        elif isinstance(node.func, ast.Attribute):
            called_names.add(node.func.attr)

    forbidden_calls = {
        "cdist",
        "KDTree",
        "cKDTree",
        "nearest",
        "nearest_neighbor",
    }

    assert called_names.isdisjoint(
        forbidden_calls
    )