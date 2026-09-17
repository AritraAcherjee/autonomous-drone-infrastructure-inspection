"""Phase-4 deterministic persistent-defect aggregation tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from src.defect_mapping import (
    AggregationError,
    DEFAULT_MODEL_VERSION,
    FusionConfig,
    MappedObservation,
    ValidationError,
    aggregate_observation,
    create_persistent_defect,
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


def make_observation(
    observation_id: str = "obs-1",
    **overrides,
) -> MappedObservation:
    values = {
        "inspection_id": 1,
        "observation_id": observation_id,
        "detection_id": observation_id,
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


def test_first_observation_creates_exact_single_observation_aggregate() -> None:
    defect = create_persistent_defect(
        make_observation(),
        defect_id="P15D-test",
        config=FusionConfig(),
        inspection_id=1,
    )

    assert defect.defect_id == "P15D-test"
    assert defect.inspection_id == 1
    assert defect.creator_observation_id == "obs-1"
    assert defect.class_id == 0
    assert defect.class_name == "Crack"
    assert defect.confidence == pytest.approx(0.9)
    assert defect.x_m == pytest.approx(1.0)
    assert defect.y_m == pytest.approx(2.0)
    assert defect.z_m == pytest.approx(3.0)
    assert defect.coordinate_frame == "map"
    assert defect.observation_count == 1
    assert defect.first_seen == T0
    assert defect.last_seen == T0
    assert defect.observation_ids == ("obs-1",)
    assert len(defect.provenance) == 1


def test_arithmetic_xyz_aggregation() -> None:
    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            x_m=1.0,
            y_m=2.0,
            z_m=3.0,
        ),
        defect_id="P15D-test",
        config=FusionConfig(),
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-2",
            x_m=3.0,
            y_m=4.0,
            z_m=5.0,
        ),
        config=FusionConfig(),
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-3",
            x_m=8.0,
            y_m=9.0,
            z_m=10.0,
        ),
        config=FusionConfig(),
    )

    assert defect.x_m == pytest.approx(4.0)
    assert defect.y_m == pytest.approx(5.0)
    assert defect.z_m == pytest.approx(6.0)


def test_arithmetic_confidence_aggregation() -> None:
    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            confidence=0.3,
        ),
        defect_id="P15D-test",
        config=FusionConfig(),
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-2",
            confidence=0.6,
        ),
        config=FusionConfig(),
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-3",
            confidence=0.9,
        ),
        config=FusionConfig(),
    )

    assert defect.confidence == pytest.approx(0.6)


def test_observation_count_counts_unique_accepted_observations() -> None:
    defect = create_persistent_defect(
        make_observation("obs-1"),
        defect_id="P15D-test",
        config=FusionConfig(),
    )

    for index in range(2, 6):
        defect = aggregate_observation(
            defect,
            make_observation(f"obs-{index}"),
            config=FusionConfig(),
        )

    assert defect.observation_count == 5
    assert defect.observation_ids == (
        "obs-1",
        "obs-2",
        "obs-3",
        "obs-4",
        "obs-5",
    )


def test_out_of_order_timestamp_updates_min_and_max() -> None:
    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            timestamp=T0,
        ),
        defect_id="P15D-test",
        config=FusionConfig(),
    )

    later = T0 + timedelta(seconds=10)
    earlier = T0 - timedelta(seconds=10)

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-2",
            timestamp=later,
        ),
        config=FusionConfig(),
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-3",
            timestamp=earlier,
        ),
        config=FusionConfig(),
    )

    assert defect.first_seen == earlier
    assert defect.last_seen == later


def test_equal_timestamps_are_valid() -> None:
    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            timestamp=T0,
        ),
        defect_id="P15D-test",
        config=FusionConfig(),
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-2",
            timestamp=T0,
        ),
        config=FusionConfig(),
    )

    assert defect.first_seen == T0
    assert defect.last_seen == T0
    assert defect.observation_count == 2


def test_every_unique_observation_retains_full_provenance() -> None:
    first = make_observation(
        "obs-1",
        track_id="track-a",
        image_path="frames/1.jpg",
        crop_path="crops/1.jpg",
    )
    second = make_observation(
        "obs-2",
        track_id="track-b",
        image_path="frames/2.jpg",
        crop_path="crops/2.jpg",
        confidence=0.7,
        x_m=1.2,
    )

    defect = create_persistent_defect(
        first,
        defect_id="P15D-test",
        config=FusionConfig(),
    )

    defect = aggregate_observation(
        defect,
        second,
        config=FusionConfig(),
    )

    assert len(defect.provenance) == 2

    assert defect.provenance[0].observation_id == "obs-1"
    assert defect.provenance[0].track_id == "track-a"
    assert defect.provenance[0].image_path == "frames/1.jpg"
    assert defect.provenance[0].crop_path == "crops/1.jpg"

    assert defect.provenance[1].observation_id == "obs-2"
    assert defect.provenance[1].track_id == "track-b"
    assert defect.provenance[1].image_path == "frames/2.jpg"
    assert defect.provenance[1].crop_path == "crops/2.jpg"
    assert defect.provenance[1].confidence == pytest.approx(0.7)
    assert defect.provenance[1].x_m == pytest.approx(1.2)


def test_canonical_track_id_is_most_frequent_non_null_track() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            track_id="track-b",
        ),
        defect_id="P15D-test",
        config=config,
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-2",
            track_id="track-a",
        ),
        config=config,
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-3",
            track_id="track-b",
        ),
        config=config,
    )

    assert defect.canonical_track_id == "track-b"
    assert defect.track_ids == (
        "track-a",
        "track-b",
    )
    assert defect.track_observation_counts == (
        ("track-a", 1),
        ("track-b", 2),
    )


def test_canonical_track_tie_uses_lexical_order() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            track_id="track-z",
        ),
        defect_id="P15D-test",
        config=config,
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-2",
            track_id="track-a",
        ),
        config=config,
    )

    assert defect.canonical_track_id == "track-a"
    assert defect.track_observation_counts == (
        ("track-a", 1),
        ("track-z", 1),
    )


def test_null_tracks_do_not_participate_in_canonical_track_counts() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            track_id=None,
        ),
        defect_id="P15D-test",
        config=config,
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-2",
            track_id=None,
        ),
        config=config,
    )

    assert defect.canonical_track_id is None
    assert defect.track_ids == ()
    assert defect.track_observation_counts == ()


def test_creator_observation_remains_fixed_after_aggregation() -> None:
    defect = create_persistent_defect(
        make_observation("creator"),
        defect_id="P15D-test",
        config=FusionConfig(),
    )

    defect = aggregate_observation(
        defect,
        make_observation("later"),
        config=FusionConfig(),
    )

    assert defect.creator_observation_id == "creator"


def test_aggregation_is_immutable_and_does_not_modify_old_defect() -> None:
    original = create_persistent_defect(
        make_observation(
            "obs-1",
            confidence=0.2,
        ),
        defect_id="P15D-test",
        config=FusionConfig(),
    )

    updated = aggregate_observation(
        original,
        make_observation(
            "obs-2",
            confidence=0.8,
        ),
        config=FusionConfig(),
    )

    assert original.observation_count == 1
    assert original.observation_ids == ("obs-1",)
    assert original.confidence == pytest.approx(0.2)

    assert updated.observation_count == 2
    assert updated.observation_ids == (
        "obs-1",
        "obs-2",
    )
    assert updated.confidence == pytest.approx(0.5)

    with pytest.raises(FrozenInstanceError):
        original.confidence = 0.5


def test_duplicate_observation_id_fails_closed() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation("obs-1"),
        defect_id="P15D-test",
        config=config,
    )

    with pytest.raises(
        AggregationError,
        match="already exists",
    ):
        aggregate_observation(
            defect,
            make_observation("obs-1"),
            config=config,
        )


def test_cross_inspection_aggregation_fails_closed() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            inspection_id=1,
        ),
        defect_id="P15D-test",
        config=config,
    )

    with pytest.raises(
        ValidationError,
        match="cross-inspection",
    ):
        aggregate_observation(
            defect,
            make_observation(
                "obs-2",
                inspection_id=2,
            ),
            config=config,
        )


def test_class_conflict_fails_closed() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            class_id=0,
            class_name="Crack",
        ),
        defect_id="P15D-test",
        config=config,
    )

    with pytest.raises(
        AggregationError,
        match="class conflict",
    ):
        aggregate_observation(
            defect,
            make_observation(
                "obs-2",
                class_id=1,
                class_name="Breakage",
            ),
            config=config,
        )


def test_model_version_conflict_fails_before_aggregation() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation("obs-1"),
        defect_id="P15D-test",
        config=config,
    )

    with pytest.raises(
        ValidationError,
        match="model_version",
    ):
        aggregate_observation(
            defect,
            make_observation(
                "obs-2",
                model_version="DET-FINAL-v2",
            ),
            config=config,
        )


def test_invalid_non_map_observation_fails_before_aggregation() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation("obs-1"),
        defect_id="P15D-test",
        config=config,
    )

    with pytest.raises(
        ValidationError,
        match='exactly "map"',
    ):
        aggregate_observation(
            defect,
            make_observation(
                "obs-2",
                coordinate_frame="odom",
            ),
            config=config,
        )


def test_invalid_existing_defect_fails_closed_without_partial_result() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation("obs-1"),
        defect_id="P15D-test",
        config=config,
    )

    invalid = replace(
        defect,
        observation_count=99,
    )

    with pytest.raises(ValidationError):
        aggregate_observation(
            invalid,
            make_observation("obs-2"),
            config=config,
        )

    assert defect.observation_count == 1
    assert defect.observation_ids == ("obs-1",)


def test_math_fsum_aggregation_is_deterministic_for_given_provenance() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            x_m=1e16,
        ),
        defect_id="P15D-test",
        config=config,
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-2",
            x_m=1.0,
        ),
        config=config,
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-3",
            x_m=-1e16,
        ),
        config=config,
    )

    assert defect.x_m == pytest.approx(1.0 / 3.0)


def test_provenance_order_is_ingestion_order_not_timestamp_order() -> None:
    config = FusionConfig()

    defect = create_persistent_defect(
        make_observation(
            "obs-1",
            timestamp=T0,
        ),
        defect_id="P15D-test",
        config=config,
    )

    defect = aggregate_observation(
        defect,
        make_observation(
            "obs-2",
            timestamp=T0 - timedelta(seconds=30),
        ),
        config=config,
    )

    assert defect.observation_ids == (
        "obs-1",
        "obs-2",
    )

    assert [
        record.observation_id
        for record in defect.provenance
    ] == [
        "obs-1",
        "obs-2",
    ]

    assert defect.first_seen == (
        T0 - timedelta(seconds=30)
    )


def test_different_valid_order_is_not_claimed_to_change_creator() -> None:
    config = FusionConfig()

    first_a = create_persistent_defect(
        make_observation("obs-a"),
        defect_id="P15D-A",
        config=config,
    )

    first_b = create_persistent_defect(
        make_observation("obs-b"),
        defect_id="P15D-B",
        config=config,
    )

    assert first_a.creator_observation_id == "obs-a"
    assert first_b.creator_observation_id == "obs-b"
    assert first_a.defect_id != first_b.defect_id
