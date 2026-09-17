"""Phase-5 functional fusion-engine tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.defect_mapping import (
    DEFAULT_MODEL_VERSION,
    FusionConfig,
    FusionDecision,
    MappedObservation,
    ReplayConflictError,
    ValidationError,
    create_state,
    ingest_batch,
    ingest_observation,
    persistent_defect_id,
)


T0 = datetime(
    2026,
    9,
    16,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)


def obs(
    observation_id: str,
    *,
    x_m: float = 0.0,
    y_m: float = 0.0,
    z_m: float = 0.0,
    track_id: str | None = None,
    class_id: int = 0,
    class_name: str = "Crack",
    confidence: float = 0.9,
    inspection_id: int = 1,
    timestamp: datetime = T0,
    source_frame_id: str = "camera_optical_frame",
    model_version: str = DEFAULT_MODEL_VERSION,
) -> MappedObservation:
    return MappedObservation(
        inspection_id=inspection_id,
        observation_id=observation_id,
        detection_id=observation_id,
        track_id=track_id,
        class_id=class_id,
        class_name=class_name,
        confidence=confidence,
        x_m=x_m,
        y_m=y_m,
        z_m=z_m,
        coordinate_frame="map",
        timestamp=timestamp,
        source_frame_id=source_frame_id,
        bbox_xyxy=(10.0, 10.0, 50.0, 50.0),
        image_width=640,
        image_height=480,
        model_version=model_version,
        image_path=None,
        crop_path=None,
    )


def test_create_state_is_empty_and_inspection_local() -> None:
    state = create_state(1)

    assert state.inspection_id == 1
    assert dict(state.defects) == {}
    assert dict(state.processed_observations) == {}
    assert state.config == FusionConfig()


def test_first_observation_creates_defect_with_frozen_id() -> None:
    state = create_state(1)

    result = ingest_observation(
        state,
        obs("obs-1"),
    )

    expected = persistent_defect_id(
        1,
        "obs-1",
    )

    assert result.decision is FusionDecision.CREATED
    assert result.defect_id == expected
    assert result.observation_id == "obs-1"
    assert expected in result.new_state.defects
    assert (
        result.new_state.defects[expected].observation_count
        == 1
    )


def test_nearby_observation_associates() -> None:
    first = ingest_observation(
        create_state(1),
        obs("obs-1", x_m=0.0),
    )

    second = ingest_observation(
        first.new_state,
        obs("obs-2", x_m=0.10),
    )

    assert second.decision is FusionDecision.ASSOCIATED
    assert second.defect_id == first.defect_id
    assert len(second.new_state.defects) == 1
    assert (
        second.new_state.defects[first.defect_id].observation_count
        == 2
    )


def test_exact_threshold_boundary_associates() -> None:
    first = ingest_observation(
        create_state(1),
        obs("obs-1", x_m=0.0),
    )

    second = ingest_observation(
        first.new_state,
        obs("obs-2", x_m=0.25),
    )

    assert second.decision is FusionDecision.ASSOCIATED
    assert second.defect_id == first.defect_id


def test_outside_threshold_creates_new_defect() -> None:
    first = ingest_observation(
        create_state(1),
        obs("obs-1", x_m=0.0),
    )

    second = ingest_observation(
        first.new_state,
        obs("obs-2", x_m=0.250001),
    )

    assert second.decision is FusionDecision.CREATED
    assert second.defect_id != first.defect_id
    assert len(second.new_state.defects) == 2


def test_strict_class_conflict_creates_separate_defect() -> None:
    first = ingest_observation(
        create_state(1),
        obs(
            "obs-1",
            class_id=0,
            class_name="Crack",
        ),
    )

    second = ingest_observation(
        first.new_state,
        obs(
            "obs-2",
            x_m=0.01,
            class_id=1,
            class_name="Breakage",
        ),
    )

    assert second.decision is FusionDecision.CREATED
    assert second.defect_id != first.defect_id
    assert len(second.new_state.defects) == 2


def test_track_priority_is_used_by_engine() -> None:
    state = create_state(1)

    a = ingest_observation(
        state,
        obs(
            "a",
            x_m=0.0,
            track_id="track-near",
        ),
    )

    b = ingest_observation(
        a.new_state,
        obs(
            "b",
            x_m=0.40,
            track_id="track-7",
        ),
    )

    incoming = ingest_observation(
        b.new_state,
        obs(
            "incoming",
            x_m=0.20,
            track_id="track-7",
        ),
    )

    assert incoming.decision is FusionDecision.ASSOCIATED
    assert incoming.defect_id == b.defect_id


def test_track_match_does_not_bypass_distance_threshold() -> None:
    first = ingest_observation(
        create_state(1),
        obs(
            "obs-1",
            x_m=0.0,
            track_id="track-7",
        ),
    )

    second = ingest_observation(
        first.new_state,
        obs(
            "obs-2",
            x_m=0.30,
            track_id="track-7",
        ),
    )

    assert second.decision is FusionDecision.CREATED
    assert second.defect_id != first.defect_id
    assert len(second.new_state.defects) == 2


def test_one_observation_updates_at_most_one_defect() -> None:
    state = create_state(1)

    first = ingest_observation(
        state,
        obs("a", x_m=-0.10),
    )

    second = ingest_observation(
        first.new_state,
        obs("b", x_m=0.10),
    )

    before_counts = {
        defect_id: defect.observation_count
        for defect_id, defect in second.new_state.defects.items()
    }

    incoming = ingest_observation(
        second.new_state,
        obs("c", x_m=0.0),
    )

    after_counts = {
        defect_id: defect.observation_count
        for defect_id, defect in incoming.new_state.defects.items()
    }

    increments = sum(
        after_counts[key] - before_counts[key]
        for key in before_counts
    )

    assert increments == 1


def test_same_source_frame_multiple_observations_are_independent() -> None:
    state = create_state(1)

    final_state, results = ingest_batch(
        state,
        (
            obs(
                "frame-1-det-0",
                x_m=0.0,
                source_frame_id="frame-1",
            ),
            obs(
                "frame-1-det-1",
                x_m=2.0,
                source_frame_id="frame-1",
            ),
        ),
    )

    assert len(results) == 2
    assert len(final_state.defects) == 2
    assert {
        result.observation_id
        for result in results
    } == {
        "frame-1-det-0",
        "frame-1-det-1",
    }


def test_exact_replay_returns_same_state_and_no_increment() -> None:
    first = ingest_observation(
        create_state(1),
        obs("obs-1"),
    )

    replay = ingest_observation(
        first.new_state,
        obs("obs-1"),
    )

    assert replay.decision is FusionDecision.REPLAY
    assert replay.defect_id == first.defect_id
    assert replay.new_state is first.new_state
    assert (
        replay.new_state.defects[first.defect_id].observation_count
        == 1
    )
    assert len(replay.new_state.processed_observations) == 1


def test_conflicting_replay_fails_closed_and_old_state_unchanged() -> None:
    first = ingest_observation(
        create_state(1),
        obs(
            "obs-1",
            confidence=0.9,
        ),
    )

    old_state = first.new_state

    with pytest.raises(
        ReplayConflictError,
        match="conflicting payload",
    ):
        ingest_observation(
            old_state,
            obs(
                "obs-1",
                confidence=0.8,
            ),
        )

    assert (
        old_state.defects[first.defect_id].observation_count
        == 1
    )
    assert len(old_state.processed_observations) == 1


def test_out_of_order_valid_observations_are_accepted() -> None:
    first = ingest_observation(
        create_state(1),
        obs(
            "obs-1",
            timestamp=T0,
        ),
    )

    earlier = T0 - timedelta(seconds=30)

    second = ingest_observation(
        first.new_state,
        obs(
            "obs-2",
            x_m=0.05,
            timestamp=earlier,
        ),
    )

    defect = second.new_state.defects[first.defect_id]

    assert defect.first_seen == earlier
    assert defect.last_seen == T0


def test_cross_inspection_observation_fails_closed() -> None:
    state = create_state(1)

    with pytest.raises(
        ValidationError,
        match="cross-inspection",
    ):
        ingest_observation(
            state,
            obs(
                "obs-1",
                inspection_id=2,
            ),
        )

    assert dict(state.defects) == {}
    assert dict(state.processed_observations) == {}


def test_model_version_mismatch_fails_closed() -> None:
    state = create_state(1)

    with pytest.raises(
        ValidationError,
        match="model_version",
    ):
        ingest_observation(
            state,
            obs(
                "obs-1",
                model_version="DET-FINAL-v2",
            ),
        )

    assert dict(state.defects) == {}


def test_state_transitions_are_functional_not_in_place() -> None:
    initial = create_state(1)

    first = ingest_observation(
        initial,
        obs("obs-1"),
    )

    assert dict(initial.defects) == {}
    assert dict(initial.processed_observations) == {}

    second = ingest_observation(
        first.new_state,
        obs("obs-2", x_m=0.05),
    )

    assert (
        first.new_state.defects[first.defect_id].observation_count
        == 1
    )
    assert (
        second.new_state.defects[first.defect_id].observation_count
        == 2
    )


def test_processed_registry_tracks_every_unique_observation() -> None:
    final_state, results = ingest_batch(
        create_state(1),
        (
            obs("obs-1", x_m=0.0),
            obs("obs-2", x_m=0.05),
            obs("obs-3", x_m=2.0),
        ),
    )

    assert len(results) == 3
    assert set(final_state.processed_observations) == {
        "obs-1",
        "obs-2",
        "obs-3",
    }

    for result in results:
        processed = final_state.processed_observations[
            result.observation_id
        ]
        assert processed.defect_id == result.defect_id
        assert len(processed.fingerprint) == 64


def test_batch_preserves_exact_input_order_in_results() -> None:
    final_state, results = ingest_batch(
        create_state(1),
        (
            obs("z"),
            obs("a", x_m=1.0),
            obs("m", x_m=2.0),
        ),
    )

    assert [
        result.observation_id
        for result in results
    ] == [
        "z",
        "a",
        "m",
    ]

    assert len(final_state.processed_observations) == 3


def test_same_initial_state_and_same_order_is_deterministic() -> None:
    observations = (
        obs("obs-1", x_m=0.00),
        obs("obs-2", x_m=0.10),
        obs("obs-3", x_m=1.00),
        obs("obs-4", x_m=1.10),
    )

    first_state, first_results = ingest_batch(
        create_state(1),
        observations,
    )

    second_state, second_results = ingest_batch(
        create_state(1),
        observations,
    )

    assert first_state == second_state

    assert [
        (
            result.decision,
            result.defect_id,
            result.observation_id,
        )
        for result in first_results
    ] == [
        (
            result.decision,
            result.defect_id,
            result.observation_id,
        )
        for result in second_results
    ]


def test_batch_atomicity_when_later_observation_is_invalid() -> None:
    initial = create_state(1)

    valid = obs("obs-1")

    invalid = MappedObservation(
        inspection_id=1,
        observation_id="obs-2",
        detection_id="obs-2",
        track_id=None,
        class_id=0,
        class_name="Crack",
        confidence=float("nan"),
        x_m=0.1,
        y_m=0.0,
        z_m=0.0,
        coordinate_frame="map",
        timestamp=T0,
        source_frame_id="camera_optical_frame",
        bbox_xyxy=(10.0, 10.0, 50.0, 50.0),
        image_width=640,
        image_height=480,
        model_version=DEFAULT_MODEL_VERSION,
        image_path=None,
        crop_path=None,
    )

    with pytest.raises(ValidationError):
        ingest_batch(
            initial,
            (
                valid,
                invalid,
            ),
        )

    # Caller retains the exact unchanged initial state.
    assert dict(initial.defects) == {}
    assert dict(initial.processed_observations) == {}


def test_batch_atomicity_when_later_item_conflicts_with_replay() -> None:
    initial = create_state(1)

    with pytest.raises(ReplayConflictError):
        ingest_batch(
            initial,
            (
                obs(
                    "obs-1",
                    confidence=0.9,
                ),
                obs(
                    "obs-1",
                    confidence=0.8,
                ),
            ),
        )

    assert dict(initial.defects) == {}
    assert dict(initial.processed_observations) == {}


def test_order_sensitivity_is_not_hidden() -> None:
    # The frozen contract guarantees deterministic streaming behavior
    # for the same ordered sequence, not permutation invariance.

    order_one, results_one = ingest_batch(
        create_state(1),
        (
            obs("a", x_m=0.00),
            obs("b", x_m=0.24),
            obs("c", x_m=0.48),
        ),
    )

    order_two, results_two = ingest_batch(
        create_state(1),
        (
            obs("b", x_m=0.24),
            obs("a", x_m=0.00),
            obs("c", x_m=0.48),
        ),
    )

    assert results_one[0].defect_id == persistent_defect_id(
        1,
        "a",
    )

    assert results_two[0].defect_id == persistent_defect_id(
        1,
        "b",
    )

    assert results_one[0].defect_id != results_two[0].defect_id

    assert len(order_one.defects) >= 1
    assert len(order_two.defects) >= 1


def test_custom_threshold_flows_through_engine() -> None:
    state = create_state(
        1,
        config=FusionConfig(
            association_distance_m=0.10,
        ),
    )

    first = ingest_observation(
        state,
        obs("obs-1", x_m=0.0),
    )

    second = ingest_observation(
        first.new_state,
        obs("obs-2", x_m=0.11),
    )

    assert second.decision is FusionDecision.CREATED
    assert len(second.new_state.defects) == 2


def test_batch_replay_is_returned_but_not_reaggregated() -> None:
    state, first_results = ingest_batch(
        create_state(1),
        (
            obs("obs-1", x_m=0.0),
            obs("obs-2", x_m=0.05),
        ),
    )

    before_count = state.defects[
        first_results[0].defect_id
    ].observation_count

    replay_state, replay_results = ingest_batch(
        state,
        (
            obs("obs-1", x_m=0.0),
            obs("obs-2", x_m=0.05),
        ),
    )

    assert [
        result.decision
        for result in replay_results
    ] == [
        FusionDecision.REPLAY,
        FusionDecision.REPLAY,
    ]

    assert replay_state is state
    assert (
        replay_state.defects[
            first_results[0].defect_id
        ].observation_count
        == before_count
    )
