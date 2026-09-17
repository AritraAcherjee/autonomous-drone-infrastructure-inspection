"""Synthetic-only P19 serialization and registry integration tests."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path

import pytest

from src.evaluation.defect_localization import (
    DefectLocalizationResult,
)
from src.evaluation.framework import (
    FIELDS,
    METRICS,
    SPATIAL_GEO_METRICS,
    WORKSTREAMS_ACCEPTED,
    WORKSTREAMS_CURRENT,
    WORKSTREAMS_HISTORICAL,
    validate_experiment,
    validate_metric,
)
from src.evaluation.serialization import (
    DEFECT_GEO_METRIC_NAMES,
    SPATIAL_GEO_METRIC_NAMES,
    TRAJECTORY_GEO_METRIC_NAMES,
    SpatialSerializationError,
    canonical_json_bytes,
    defect_geo_metric_values,
    normalize_for_json,
    trajectory_geo_metric_values,
)
from src.evaluation.trajectory import (
    AteResult,
    RigidAlignment,
    RpeResult,
    TrajectoryAssociationResult,
    TrajectoryMetricResult,
)


ROOT = Path(__file__).resolve().parents[2]


EXPECTED_SPATIAL_METRICS = {
    "vio_ate_translation_rmse_m",
    "vio_rpe_translation_rmse_m_1s",
    "vio_rpe_rotation_rmse_deg_1s",
    "vio_aligned_sample_count",
    "vio_timestamp_alignment_coverage",
    "vio_evaluated_duration_s",
    "defect_localization_mean_error_m",
    "defect_localization_median_error_m",
    "defect_localization_rmse_m",
    "defect_localization_p95_error_m",
    "defect_localization_matched_count",
    "defect_localization_unmatched_estimated_count",
    "defect_localization_unmatched_gt_count",
}


def protocol() -> dict:
    return json.loads(
        (
            ROOT
            / "configs"
            / "evaluation"
            / "stop_a_protocol.yaml"
        ).read_text(encoding="utf-8")
    )


def p19_experiment() -> dict:
    record = dict.fromkeys(
        FIELDS["experiment"]
    )

    record.update(
        experiment_id="synthetic-p19-spatial-unit",
        name="Synthetic P19 spatial fixture",
        claim_id="unit",
        workstream="P19",
        owner="unit",
        status="PLANNED",
        evidence_type="GEO",
        dataset="synthetic-spatial-fixture",
        dataset_version="unit",
        split="unit",
        accepted=False,
        synthetic=True,
    )

    return record


def pending_evidence(
    experiment: dict,
) -> dict:
    record = dict.fromkeys(
        FIELDS["evidence"]
    )

    for key in set(experiment) & set(record):
        record[key] = experiment[key]

    record.update(
        evidence_id="synthetic-p19-evidence",
        description="Synthetic-only P19 unit evidence",
        artifact_path=None,
        artifact_sha256=None,
        config_ref=None,
        command_ref=None,
        generated_at=None,
        machine=None,
        environment_ref=None,
        acceptance_status="PENDING",
        reviewer_note=None,
        synthetic=True,
    )

    return record


def pending_metric(
    experiment: dict,
    metric_name: str,
) -> dict:
    record = dict.fromkeys(
        FIELDS["metric"]
    )

    record.update(
        metric_id=f"synthetic-{metric_name}",
        experiment_id=experiment["experiment_id"],
        dataset=experiment["dataset"],
        split=experiment["split"],
        scope="synthetic-unit",
        metric=metric_name,
        value=None,
        unit="unit",
        status="PENDING",
        source_artifact=None,
        evidence_type="GEO",
    )

    return record


def test_canonical_json_key_order_and_utf8_are_frozen() -> None:
    value = {
        "z": "é",
        "a": 1,
    }

    assert canonical_json_bytes(value) == (
        b'{"a":1,"z":"\xc3\xa9"}'
    )


def test_equivalent_mapping_insertion_order_has_identical_bytes() -> None:
    first = {
        "b": {
            "y": 2,
            "x": 1,
        },
        "a": [3, 4],
    }

    second = {
        "a": [3, 4],
        "b": {
            "x": 1,
            "y": 2,
        },
    }

    assert canonical_json_bytes(first) == canonical_json_bytes(
        second
    )


@pytest.mark.parametrize(
    "invalid",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_nonfinite_json_values_fail_closed(
    invalid: float,
) -> None:
    with pytest.raises(
        SpatialSerializationError,
        match="nonfinite",
    ):
        canonical_json_bytes(
            {
                "value": invalid,
            }
        )


def test_non_string_mapping_key_is_rejected() -> None:
    with pytest.raises(
        SpatialSerializationError,
        match="string keys",
    ):
        canonical_json_bytes(
            {
                1: "not allowed",
            }
        )


@dataclass(frozen=True)
class Example:
    z: tuple[int, ...]
    a: str


def test_dataclass_and_tuple_normalization_is_deterministic() -> None:
    normalized = normalize_for_json(
        Example(
            z=(3, 2, 1),
            a="fixture",
        )
    )

    assert normalized == {
        "z": [3, 2, 1],
        "a": "fixture",
    }

    assert canonical_json_bytes(
        Example(
            z=(3, 2, 1),
            a="fixture",
        )
    ) == (
        b'{"a":"fixture","z":[3,2,1]}'
    )


def test_serializer_does_not_generate_timestamp_fields() -> None:
    payload = {
        "kind": "synthetic-unit",
        "value": 1,
    }

    decoded = json.loads(
        canonical_json_bytes(payload)
    )

    assert decoded == payload

    source = (
        ROOT
        / "src"
        / "evaluation"
        / "serialization.py"
    ).read_text(encoding="utf-8")

    assert "datetime.now" not in source
    assert "time.time" not in source
    assert "generated_at" not in source


def test_exact_frozen_spatial_metric_name_set() -> None:
    assert set(
        SPATIAL_GEO_METRIC_NAMES
    ) == EXPECTED_SPATIAL_METRICS

    assert (
        set(TRAJECTORY_GEO_METRIC_NAMES)
        | set(DEFECT_GEO_METRIC_NAMES)
    ) == EXPECTED_SPATIAL_METRICS

    assert SPATIAL_GEO_METRICS == EXPECTED_SPATIAL_METRICS


def test_every_frozen_spatial_metric_is_geo_in_framework() -> None:
    for metric_name in EXPECTED_SPATIAL_METRICS:
        assert METRICS[metric_name] == "GEO"


def test_existing_metric_taxonomy_is_preserved() -> None:
    assert METRICS["mAP@0.5"] == "ML"
    assert METRICS["mAP@0.5:0.95"] == "ML"
    assert METRICS["precision"] == "ML"
    assert METRICS["recall"] == "ML"
    assert METRICS["F1"] == "ML"
    assert METRICS["inference latency"] == "SIM"
    assert METRICS["FPS"] == "SIM"
    assert METRICS["tests passed"] == "SW"
    assert METRICS["projection error"] == "GEO"


def test_p19_is_current_and_chat19_is_historical_only() -> None:
    assert "P19" in WORKSTREAMS_CURRENT
    assert "Chat19" not in WORKSTREAMS_CURRENT

    assert WORKSTREAMS_HISTORICAL == {
        "Chat19",
    }

    assert "P19" in WORKSTREAMS_ACCEPTED
    assert "Chat19" in WORKSTREAMS_ACCEPTED


def test_new_p19_experiment_validates() -> None:
    record = p19_experiment()

    assert validate_experiment(
        record,
        protocol(),
    ) is record


def test_historical_chat19_remains_validator_compatible() -> None:
    record = p19_experiment()
    record["workstream"] = "Chat19"

    assert validate_experiment(
        record,
        protocol(),
    ) is record


def test_unknown_new_workstream_still_fails_closed() -> None:
    record = p19_experiment()
    record["workstream"] = "P19-ALIAS"

    with pytest.raises(
        ValueError,
        match="Unknown workstream",
    ):
        validate_experiment(
            record,
            protocol(),
        )


@pytest.mark.parametrize(
    "metric_name",
    sorted(EXPECTED_SPATIAL_METRICS),
)
def test_each_new_geo_metric_passes_pending_registry_validation(
    tmp_path: Path,
    metric_name: str,
) -> None:
    experiment = p19_experiment()
    evidence = pending_evidence(
        experiment
    )

    metric = pending_metric(
        experiment,
        metric_name,
    )

    assert validate_metric(
        metric,
        experiment,
        evidence,
        protocol(),
        tmp_path,
    ) is metric


def test_unknown_metric_still_requires_explicit_taxonomy_extension(
    tmp_path: Path,
) -> None:
    experiment = p19_experiment()
    evidence = pending_evidence(
        experiment
    )

    metric = pending_metric(
        experiment,
        "arbitrary_unreviewed_metric",
    )

    with pytest.raises(
        ValueError,
        match="Unknown metric",
    ):
        validate_metric(
            metric,
            experiment,
            evidence,
            protocol(),
            tmp_path,
        )


def trajectory_metric_fixture() -> tuple[
    TrajectoryMetricResult,
    TrajectoryAssociationResult,
]:
    alignment = RigidAlignment(
        rotation=(
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ),
        translation_m=(
            0.0,
            0.0,
            0.0,
        ),
    )

    ate = AteResult(
        mean_translation_error_m=0.1,
        median_translation_error_m=0.1,
        rmse_translation_error_m=0.2,
        p95_translation_error_m=0.3,
        aligned_sample_count=8,
        per_sample_translation_error_m=(
            0.1,
            0.2,
        ),
    )

    rpe = RpeResult(
        translation_rmse_m=0.4,
        rotation_rmse_deg=2.5,
        evaluated_pair_count=7,
        pairs=(),
    )

    metrics = TrajectoryMetricResult(
        alignment=alignment,
        ate=ate,
        rpe=rpe,
    )

    association = TrajectoryAssociationResult(
        aligned=(),
        estimator_sample_count=10,
        aligned_sample_count=8,
        dropped_sample_count=2,
        timestamp_alignment_coverage=0.8,
        evaluated_duration_s=15.0,
    )

    return metrics, association


def test_trajectory_geo_metric_extraction_is_exact() -> None:
    metrics, association = trajectory_metric_fixture()

    values = trajectory_geo_metric_values(
        metrics,
        association,
    )

    assert values == {
        "vio_ate_translation_rmse_m": 0.2,
        "vio_rpe_translation_rmse_m_1s": 0.4,
        "vio_rpe_rotation_rmse_deg_1s": 2.5,
        "vio_aligned_sample_count": 8,
        "vio_timestamp_alignment_coverage": 0.8,
        "vio_evaluated_duration_s": 15.0,
    }


def test_defect_geo_metric_extraction_is_exact() -> None:
    result = DefectLocalizationResult(
        matches=(),
        matched_count=4,
        unmatched_estimated_count=1,
        unmatched_gt_count=2,
        unmatched_estimated_ids=("est-x",),
        unmatched_gt_ids=("gt-x", "gt-y"),
        mean_euclidean_error_m=0.2,
        median_euclidean_error_m=0.15,
        rmse_euclidean_error_m=0.3,
        p95_euclidean_error_m=0.5,
    )

    values = defect_geo_metric_values(
        result
    )

    assert values == {
        "defect_localization_mean_error_m": 0.2,
        "defect_localization_median_error_m": 0.15,
        "defect_localization_rmse_m": 0.3,
        "defect_localization_p95_error_m": 0.5,
        "defect_localization_matched_count": 4,
        "defect_localization_unmatched_estimated_count": 1,
        "defect_localization_unmatched_gt_count": 2,
    }


def test_defect_empty_match_aggregates_remain_null() -> None:
    result = DefectLocalizationResult(
        matches=(),
        matched_count=0,
        unmatched_estimated_count=1,
        unmatched_gt_count=1,
        unmatched_estimated_ids=("est",),
        unmatched_gt_ids=("gt",),
        mean_euclidean_error_m=None,
        median_euclidean_error_m=None,
        rmse_euclidean_error_m=None,
        p95_euclidean_error_m=None,
    )

    values = defect_geo_metric_values(
        result
    )

    assert values[
        "defect_localization_mean_error_m"
    ] is None

    assert values[
        "defect_localization_median_error_m"
    ] is None

    assert values[
        "defect_localization_rmse_m"
    ] is None

    assert values[
        "defect_localization_p95_error_m"
    ] is None


def test_same_normalized_spatial_object_has_identical_bytes() -> None:
    metrics, association = trajectory_metric_fixture()

    object_a = {
        "trajectory": trajectory_geo_metric_values(
            metrics,
            association,
        ),
        "kind": "synthetic-fixture-only",
    }

    object_b = {
        "kind": "synthetic-fixture-only",
        "trajectory": trajectory_geo_metric_values(
            metrics,
            association,
        ),
    }

    assert canonical_json_bytes(
        object_a
    ) == canonical_json_bytes(
        object_b
    )


def test_serialization_module_has_no_forbidden_runtime_imports() -> None:
    import ast

    path = (
        ROOT
        / "src"
        / "evaluation"
        / "serialization.py"
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