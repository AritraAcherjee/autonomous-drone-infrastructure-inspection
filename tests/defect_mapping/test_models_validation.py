"""Phase-1 synthetic tests for frozen P15 models and validation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from src.defect_mapping import (
    CLASS_NAMES_BY_ID,
    DEFAULT_ASSOCIATION_DISTANCE_M,
    DEFAULT_MODEL_VERSION,
    FusionConfig,
    FusionDecision,
    FusionState,
    MappedObservation,
    ObservationProvenance,
    ValidationError,
    validate_observation,
)


T0 = datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc)


def make_observation(**overrides) -> MappedObservation:
    values = {
        "inspection_id": 1,
        "observation_id": "100.000000001-0",
        "detection_id": "100.000000001-0",
        "track_id": None,
        "class_id": 0,
        "class_name": "Crack",
        "confidence": 0.9,
        "x_m": 1.0,
        "y_m": 2.0,
        "z_m": 3.0,
        "coordinate_frame": "map",
        "timestamp": T0,
        "source_frame_id": "camera_optical_frame",
        "bbox_xyxy": (10.0, 20.0, 110.0, 120.0),
        "image_width": 640,
        "image_height": 480,
        "model_version": DEFAULT_MODEL_VERSION,
        "image_path": None,
        "crop_path": None,
    }
    values.update(overrides)
    return MappedObservation(**values)


def test_fusion_config_defaults_are_frozen_contract() -> None:
    config = FusionConfig()

    assert config.association_distance_m == DEFAULT_ASSOCIATION_DISTANCE_M
    assert config.association_distance_m == 0.25
    assert config.expected_model_version == "DET-FINAL-v1"

    with pytest.raises(FrozenInstanceError):
        config.association_distance_m = 1.0


@pytest.mark.parametrize(
    "value",
    [
        0,
        -0.1,
        float("nan"),
        float("inf"),
        True,
        "0.25",
    ],
)
def test_config_rejects_invalid_association_distance(value) -> None:
    with pytest.raises(ValueError):
        FusionConfig(association_distance_m=value)


def test_valid_observation_is_accepted_and_utc_normalized() -> None:
    eastern = timezone(timedelta(hours=-4))

    observation = make_observation(
        timestamp=datetime(
            2026,
            9,
            16,
            8,
            0,
            0,
            tzinfo=eastern,
        )
    )

    normalized = validate_observation(
        observation,
        config=FusionConfig(),
        inspection_id=1,
    )

    assert normalized.timestamp == T0
    assert normalized.timestamp.tzinfo == timezone.utc


def test_observation_is_immutable() -> None:
    observation = make_observation()

    with pytest.raises(FrozenInstanceError):
        observation.confidence = 0.1


def test_observation_id_must_equal_detection_id() -> None:
    observation = make_observation(
        detection_id="different-detection"
    )

    with pytest.raises(
        ValidationError,
        match="observation_id must equal detection_id",
    ):
        validate_observation(
            observation,
            config=FusionConfig(),
        )


@pytest.mark.parametrize(
    "bad_id",
    [
        "",
        " leading",
        "trailing ",
        "line\nbreak",
        "x" * 257,
    ],
)
def test_observation_identity_is_fail_closed(bad_id: str) -> None:
    observation = make_observation(
        observation_id=bad_id,
        detection_id=bad_id,
    )

    with pytest.raises(ValidationError):
        validate_observation(
            observation,
            config=FusionConfig(),
        )


@pytest.mark.parametrize(
    ("class_id", "class_name"),
    sorted(CLASS_NAMES_BY_ID.items()),
)
def test_exact_six_class_taxonomy_is_accepted(
    class_id: int,
    class_name: str,
) -> None:
    normalized = validate_observation(
        make_observation(
            class_id=class_id,
            class_name=class_name,
        ),
        config=FusionConfig(),
    )

    assert normalized.class_id == class_id
    assert normalized.class_name == class_name


def test_class_id_name_mismatch_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="class_id/class_name mismatch",
    ):
        validate_observation(
            make_observation(
                class_id=0,
                class_name="Breakage",
            ),
            config=FusionConfig(),
        )


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("x_m", float("nan")),
        ("y_m", float("inf")),
        ("z_m", float("-inf")),
        ("x_m", True),
    ],
)
def test_nonfinite_or_boolean_xyz_is_rejected(
    field_name: str,
    bad_value,
) -> None:
    with pytest.raises(ValidationError):
        validate_observation(
            make_observation(
                **{field_name: bad_value}
            ),
            config=FusionConfig(),
        )


@pytest.mark.parametrize(
    "bad_confidence",
    [
        -0.01,
        1.01,
        float("nan"),
        float("inf"),
        True,
        "0.5",
    ],
)
def test_invalid_confidence_is_rejected(
    bad_confidence,
) -> None:
    with pytest.raises(ValidationError):
        validate_observation(
            make_observation(
                confidence=bad_confidence
            ),
            config=FusionConfig(),
        )


def test_exact_map_frame_is_required() -> None:
    for frame in [
        "Map",
        "MAP",
        "odom",
        "camera_optical_frame",
        " map",
        "map ",
    ]:
        with pytest.raises(
            ValidationError,
            match='exactly "map"',
        ):
            validate_observation(
                make_observation(
                    coordinate_frame=frame
                ),
                config=FusionConfig(),
            )


def test_cross_inspection_observation_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="cross-inspection",
    ):
        validate_observation(
            make_observation(inspection_id=2),
            config=FusionConfig(),
            inspection_id=1,
        )


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        validate_observation(
            make_observation(
                timestamp=datetime(
                    2026,
                    9,
                    16,
                    12,
                    0,
                    0,
                )
            ),
            config=FusionConfig(),
        )


@pytest.mark.parametrize(
    ("width", "height"),
    [
        (0, 480),
        (640, 0),
        (True, 480),
        (640, False),
    ],
)
def test_invalid_image_dimensions_are_rejected(
    width,
    height,
) -> None:
    with pytest.raises(ValidationError):
        validate_observation(
            make_observation(
                image_width=width,
                image_height=height,
            ),
            config=FusionConfig(),
        )


@pytest.mark.parametrize(
    "bbox",
    [
        (-1.0, 0.0, 10.0, 10.0),
        (0.0, -1.0, 10.0, 10.0),
        (10.0, 0.0, 10.0, 10.0),
        (0.0, 10.0, 10.0, 10.0),
        (0.0, 0.0, 641.0, 10.0),
        (0.0, 0.0, 10.0, 481.0),
        (0.0, 0.0, float("nan"), 10.0),
    ],
)
def test_bbox_must_be_finite_ordered_and_inside_image(
    bbox,
) -> None:
    with pytest.raises(ValidationError):
        validate_observation(
            make_observation(bbox_xyxy=bbox),
            config=FusionConfig(),
        )


def test_model_version_must_match_state_configuration() -> None:
    with pytest.raises(
        ValidationError,
        match="model_version",
    ):
        validate_observation(
            make_observation(
                model_version="different-model"
            ),
            config=FusionConfig(),
        )


@pytest.mark.parametrize(
    "track_id",
    [
        "",
        " track",
        "track ",
        "bad\ntrack",
        "x" * 257,
    ],
)
def test_non_null_track_id_uses_frozen_identifier_rules(
    track_id: str,
) -> None:
    with pytest.raises(ValidationError):
        validate_observation(
            make_observation(track_id=track_id),
            config=FusionConfig(),
        )


def test_optional_paths_may_be_none_or_nonempty_strings() -> None:
    normalized = validate_observation(
        make_observation(
            image_path="evidence/frame.jpg",
            crop_path="evidence/crop.jpg",
        ),
        config=FusionConfig(),
    )

    assert normalized.image_path == "evidence/frame.jpg"
    assert normalized.crop_path == "evidence/crop.jpg"

    for field_name in ("image_path", "crop_path"):
        with pytest.raises(ValidationError):
            validate_observation(
                make_observation(
                    **{field_name: "   "}
                ),
                config=FusionConfig(),
            )


def test_provenance_copies_exact_normalized_observation() -> None:
    normalized = validate_observation(
        make_observation(track_id="track-7"),
        config=FusionConfig(),
    )

    provenance = ObservationProvenance.from_observation(
        normalized
    )

    assert provenance.observation_id == normalized.observation_id
    assert provenance.detection_id == normalized.detection_id
    assert provenance.track_id == "track-7"
    assert provenance.x_m == normalized.x_m
    assert provenance.timestamp == normalized.timestamp


def test_empty_fusion_state_has_immutable_mappings() -> None:
    state = FusionState(
        inspection_id=1,
        config=FusionConfig(),
    )

    assert state.schema_version == 1
    assert dict(state.defects) == {}
    assert dict(state.processed_observations) == {}

    with pytest.raises(TypeError):
        state.defects["P15D-test"] = object()


def test_fusion_decision_values_are_frozen() -> None:
    assert FusionDecision.CREATED.value == "CREATED"
    assert FusionDecision.ASSOCIATED.value == "ASSOCIATED"
    assert FusionDecision.REPLAY.value == "REPLAY"
