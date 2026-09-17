"""Phase-2 deterministic identity, fingerprint, and replay tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from src.defect_mapping import (
    DEFAULT_MODEL_VERSION,
    FusionConfig,
    FusionState,
    MappedObservation,
    ProcessedObservation,
    ReplayConflictError,
    ValidationError,
    canonical_observation_bytes,
    observation_fingerprint,
    persistent_defect_id,
    check_replay,
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


def test_fixed_uuidv5_regression_vector() -> None:
    assert persistent_defect_id(
        1,
        "100.000000001-0",
    ) == (
        "P15D-"
        "14e60c20-09ce-5606-89cf-b81ae9f52cbd"
    )


def test_second_fixed_uuidv5_vector() -> None:
    assert persistent_defect_id(
        42,
        "1700000000.123456789-3",
    ) == (
        "P15D-"
        "be8eb3e2-d4cb-51b8-971b-7a57e5dbe1ce"
    )


def test_persistent_id_prefix_and_uuid_are_lowercase() -> None:
    value = persistent_defect_id(
        1,
        "100.000000001-0",
    )

    assert value.startswith("P15D-")
    assert value[5:] == value[5:].lower()


def test_persistent_id_changes_with_inspection_identity() -> None:
    assert persistent_defect_id(
        1,
        "obs-1",
    ) != persistent_defect_id(
        2,
        "obs-1",
    )


def test_persistent_id_changes_with_observation_identity() -> None:
    assert persistent_defect_id(
        1,
        "obs-1",
    ) != persistent_defect_id(
        1,
        "obs-2",
    )


@pytest.mark.parametrize(
    ("inspection_id", "observation_id"),
    [
        (0, "obs"),
        (-1, "obs"),
        (True, "obs"),
        (1, ""),
        (1, " obs"),
        (1, "obs "),
        (1, "bad\nobs"),
    ],
)
def test_persistent_identity_inputs_fail_closed(
    inspection_id,
    observation_id,
) -> None:
    with pytest.raises(ValidationError):
        persistent_defect_id(
            inspection_id,
            observation_id,
        )


def test_fixed_fingerprint_regression_vector() -> None:
    fingerprint = observation_fingerprint(
        make_observation(),
        config=FusionConfig(),
        inspection_id=1,
    )

    assert fingerprint == (
        "03115caf6de37b36c7fb23f0dc788492"
        "5aea630dbe20c7bcaabd5c57beb0e732"
    )


def test_fingerprint_is_stable_for_repeated_calls() -> None:
    observation = make_observation()

    first = observation_fingerprint(
        observation,
        config=FusionConfig(),
        inspection_id=1,
    )
    second = observation_fingerprint(
        observation,
        config=FusionConfig(),
        inspection_id=1,
    )

    assert first == second


def test_timezone_equivalent_timestamp_has_same_fingerprint() -> None:
    eastern = timezone(timedelta(hours=-4))

    utc_observation = make_observation()

    eastern_observation = make_observation(
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

    assert observation_fingerprint(
        utc_observation,
        config=FusionConfig(),
        inspection_id=1,
    ) == observation_fingerprint(
        eastern_observation,
        config=FusionConfig(),
        inspection_id=1,
    )


def test_negative_zero_is_canonicalized() -> None:
    positive = make_observation(x_m=0.0)
    negative = make_observation(x_m=-0.0)

    assert observation_fingerprint(
        positive,
        config=FusionConfig(),
        inspection_id=1,
    ) == observation_fingerprint(
        negative,
        config=FusionConfig(),
        inspection_id=1,
    )


@pytest.mark.parametrize(
    "changed",
    [
        {"track_id": "track-7"},
        {"class_id": 1, "class_name": "Breakage"},
        {"confidence": 0.8},
        {"x_m": 1.1},
        {"y_m": 2.1},
        {"z_m": 3.1},
        {"timestamp": T0 + timedelta(microseconds=1)},
        {"source_frame_id": "other_camera_frame"},
        {"bbox_xyxy": (11.0, 20.0, 110.0, 120.0)},
        {"image_width": 641},
        {"image_height": 481},
        {"image_path": "frame.jpg"},
        {"crop_path": "crop.jpg"},
    ],
)
def test_valid_payload_change_changes_fingerprint(
    changed,
) -> None:
    baseline = make_observation()
    altered = make_observation(**changed)

    assert observation_fingerprint(
        baseline,
        config=FusionConfig(),
        inspection_id=1,
    ) != observation_fingerprint(
        altered,
        config=FusionConfig(),
        inspection_id=1,
    )


def test_identity_change_changes_fingerprint() -> None:
    baseline = make_observation()

    changed = make_observation(
        observation_id="100.000000001-1",
        detection_id="100.000000001-1",
    )

    assert observation_fingerprint(
        baseline,
        config=FusionConfig(),
        inspection_id=1,
    ) != observation_fingerprint(
        changed,
        config=FusionConfig(),
        inspection_id=1,
    )


def test_inspection_identity_participates_in_fingerprint() -> None:
    first = make_observation(inspection_id=1)
    second = make_observation(inspection_id=2)

    assert observation_fingerprint(
        first,
        config=FusionConfig(),
    ) != observation_fingerprint(
        second,
        config=FusionConfig(),
    )


def test_model_version_is_part_of_payload_and_validated() -> None:
    alternate_config = FusionConfig(
        expected_model_version="DET-FINAL-v2"
    )

    alternate = make_observation(
        model_version="DET-FINAL-v2"
    )

    assert observation_fingerprint(
        make_observation(),
        config=FusionConfig(),
    ) != observation_fingerprint(
        alternate,
        config=alternate_config,
    )


def test_canonical_bytes_are_compact_deterministic_json() -> None:
    canonical = canonical_observation_bytes(
        make_observation(),
        config=FusionConfig(),
        inspection_id=1,
    )

    text = canonical.decode("utf-8")

    assert "\n" not in text
    assert ": " not in text
    assert ", " not in text
    assert '"coordinate_frame":"map"' in text


def test_unseen_observation_returns_fingerprint_and_none() -> None:
    state = FusionState(
        inspection_id=1,
        config=FusionConfig(),
    )
    observation = make_observation()

    fingerprint, prior = check_replay(
        state,
        observation,
    )

    assert fingerprint == observation_fingerprint(
        observation,
        config=state.config,
        inspection_id=1,
    )
    assert prior is None


def test_exact_replay_is_idempotently_recognized() -> None:
    observation = make_observation()

    fingerprint = observation_fingerprint(
        observation,
        config=FusionConfig(),
        inspection_id=1,
    )

    processed = ProcessedObservation(
        observation_id=observation.observation_id,
        fingerprint=fingerprint,
        defect_id="P15D-existing",
    )

    state = FusionState(
        inspection_id=1,
        config=FusionConfig(),
        processed_observations={
            observation.observation_id: processed,
        },
    )

    observed_fingerprint, prior = check_replay(
        state,
        observation,
    )

    assert observed_fingerprint == fingerprint
    assert prior is processed


def test_same_id_conflicting_payload_fails_closed() -> None:
    original = make_observation()

    fingerprint = observation_fingerprint(
        original,
        config=FusionConfig(),
        inspection_id=1,
    )

    state = FusionState(
        inspection_id=1,
        config=FusionConfig(),
        processed_observations={
            original.observation_id: ProcessedObservation(
                observation_id=original.observation_id,
                fingerprint=fingerprint,
                defect_id="P15D-existing",
            )
        },
    )

    conflicting = replace(
        original,
        confidence=0.8,
    )

    with pytest.raises(
        ReplayConflictError,
        match="conflicting payload",
    ):
        check_replay(
            state,
            conflicting,
        )


def test_cross_inspection_replay_check_fails_closed() -> None:
    state = FusionState(
        inspection_id=1,
        config=FusionConfig(),
    )

    with pytest.raises(
        ValidationError,
        match="cross-inspection",
    ):
        check_replay(
            state,
            make_observation(inspection_id=2),
        )


def test_replay_check_does_not_mutate_state() -> None:
    state = FusionState(
        inspection_id=1,
        config=FusionConfig(),
    )

    before_defects = dict(state.defects)
    before_processed = dict(state.processed_observations)

    check_replay(
        state,
        make_observation(),
    )

    assert dict(state.defects) == before_defects
    assert dict(state.processed_observations) == before_processed
