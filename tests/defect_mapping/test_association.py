"""Phase-3 deterministic association tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.defect_mapping import (
    DEFAULT_MODEL_VERSION,
    FusionConfig,
    FusionState,
    MappedObservation,
    ObservationProvenance,
    PersistentDefect,
    ValidationError,
    eligible_candidates,
    euclidean_distance_m,
    select_candidate,
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


def make_observation(**overrides) -> MappedObservation:
    values = {
        "inspection_id": 1,
        "observation_id": "200.000000001-0",
        "detection_id": "200.000000001-0",
        "track_id": None,
        "class_id": 0,
        "class_name": "Crack",
        "confidence": 0.9,
        "x_m": 0.0,
        "y_m": 0.0,
        "z_m": 0.0,
        "coordinate_frame": "map",
        "timestamp": T0,
        "source_frame_id": "camera_optical_frame",
        "bbox_xyxy": (10.0, 10.0, 50.0, 50.0),
        "image_width": 640,
        "image_height": 480,
        "model_version": DEFAULT_MODEL_VERSION,
        "image_path": None,
        "crop_path": None,
    }
    values.update(overrides)
    return MappedObservation(**values)


def make_defect(
    defect_id: str,
    *,
    x_m: float,
    y_m: float = 0.0,
    z_m: float = 0.0,
    track_id: str | None = None,
    class_id: int = 0,
    class_name: str = "Crack",
    inspection_id: int = 1,
) -> PersistentDefect:
    observation_id = f"creator-{defect_id}"

    provenance = ObservationProvenance(
        observation_id=observation_id,
        detection_id=observation_id,
        inspection_id=inspection_id,
        track_id=track_id,
        class_id=class_id,
        class_name=class_name,
        confidence=0.8,
        x_m=x_m,
        y_m=y_m,
        z_m=z_m,
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

    if track_id is None:
        track_ids = ()
        track_counts = ()
    else:
        track_ids = (track_id,)
        track_counts = ((track_id, 1),)

    return PersistentDefect(
        defect_id=defect_id,
        inspection_id=inspection_id,
        creator_observation_id=observation_id,
        class_id=class_id,
        class_name=class_name,
        confidence=0.8,
        x_m=x_m,
        y_m=y_m,
        z_m=z_m,
        coordinate_frame="map",
        observation_count=1,
        first_seen=T0,
        last_seen=T0,
        canonical_track_id=track_id,
        track_ids=track_ids,
        track_observation_counts=track_counts,
        model_version=DEFAULT_MODEL_VERSION,
        observation_ids=(observation_id,),
        provenance=(provenance,),
    )


def make_state(*defects: PersistentDefect) -> FusionState:
    return FusionState(
        inspection_id=1,
        config=FusionConfig(),
        defects={
            defect.defect_id: defect
            for defect in defects
        },
    )


def test_euclidean_distance_is_3d() -> None:
    observation = make_observation(
        x_m=0.0,
        y_m=0.0,
        z_m=0.0,
    )
    defect = make_defect(
        "P15D-a",
        x_m=0.1,
        y_m=0.2,
        z_m=0.2,
    )

    assert euclidean_distance_m(
        observation,
        defect,
    ) == pytest.approx(0.3)


def test_nearby_same_class_candidate_is_eligible() -> None:
    state = make_state(
        make_defect(
            "P15D-a",
            x_m=0.1,
        )
    )

    selected = select_candidate(
        state,
        make_observation(),
    )

    assert selected is not None
    assert selected.defect_id == "P15D-a"
    assert selected.distance_m == pytest.approx(0.1)


def test_exact_025_m_boundary_associates() -> None:
    state = make_state(
        make_defect(
            "P15D-boundary",
            x_m=0.25,
        )
    )

    selected = select_candidate(
        state,
        make_observation(),
    )

    assert selected is not None
    assert selected.defect_id == "P15D-boundary"
    assert selected.distance_m == pytest.approx(0.25)


def test_just_outside_threshold_is_not_eligible() -> None:
    state = make_state(
        make_defect(
            "P15D-outside",
            x_m=0.250001,
        )
    )

    assert select_candidate(
        state,
        make_observation(),
    ) is None


def test_strict_class_conflict_is_ineligible() -> None:
    state = make_state(
        make_defect(
            "P15D-breakage",
            x_m=0.05,
            class_id=1,
            class_name="Breakage",
        )
    )

    assert select_candidate(
        state,
        make_observation(
            class_id=0,
            class_name="Crack",
        ),
    ) is None


def test_track_match_has_priority_over_nearer_nontrack_candidate() -> None:
    state = make_state(
        make_defect(
            "P15D-near",
            x_m=0.05,
            track_id="other-track",
        ),
        make_defect(
            "P15D-track",
            x_m=0.20,
            track_id="track-7",
        ),
    )

    selected = select_candidate(
        state,
        make_observation(
            track_id="track-7",
        ),
    )

    assert selected is not None
    assert selected.defect_id == "P15D-track"
    assert selected.track_match is True
    assert selected.distance_m == pytest.approx(0.20)


def test_track_match_never_bypasses_spatial_threshold() -> None:
    state = make_state(
        make_defect(
            "P15D-track-far",
            x_m=0.30,
            track_id="track-7",
        )
    )

    assert select_candidate(
        state,
        make_observation(
            track_id="track-7",
        ),
    ) is None


def test_track_match_never_bypasses_class_gate() -> None:
    state = make_state(
        make_defect(
            "P15D-track-wrong-class",
            x_m=0.05,
            track_id="track-7",
            class_id=1,
            class_name="Breakage",
        )
    )

    assert select_candidate(
        state,
        make_observation(
            track_id="track-7",
            class_id=0,
            class_name="Crack",
        ),
    ) is None


def test_without_track_match_nearest_candidate_wins() -> None:
    state = make_state(
        make_defect(
            "P15D-farther",
            x_m=0.20,
        ),
        make_defect(
            "P15D-nearer",
            x_m=0.10,
        ),
    )

    selected = select_candidate(
        state,
        make_observation(),
    )

    assert selected is not None
    assert selected.defect_id == "P15D-nearer"


def test_equal_distance_uses_lexical_defect_id_tiebreak() -> None:
    state = make_state(
        make_defect(
            "P15D-zeta",
            x_m=0.10,
        ),
        make_defect(
            "P15D-alpha",
            x_m=-0.10,
        ),
    )

    selected = select_candidate(
        state,
        make_observation(),
    )

    assert selected is not None
    assert selected.defect_id == "P15D-alpha"


def test_equal_distance_track_matches_use_lexical_tiebreak() -> None:
    state = make_state(
        make_defect(
            "P15D-zeta",
            x_m=0.10,
            track_id="track-7",
        ),
        make_defect(
            "P15D-alpha",
            x_m=-0.10,
            track_id="track-7",
        ),
    )

    selected = select_candidate(
        state,
        make_observation(
            track_id="track-7",
        ),
    )

    assert selected is not None
    assert selected.defect_id == "P15D-alpha"


def test_candidate_list_is_returned_in_exact_frozen_rank_order() -> None:
    state = make_state(
        make_defect(
            "P15D-c",
            x_m=0.05,
        ),
        make_defect(
            "P15D-b",
            x_m=0.20,
            track_id="track-7",
        ),
        make_defect(
            "P15D-a",
            x_m=0.20,
            track_id="track-7",
        ),
        make_defect(
            "P15D-d",
            x_m=0.10,
        ),
    )

    candidates = eligible_candidates(
        state,
        make_observation(
            track_id="track-7",
        ),
    )

    assert [
        candidate.defect_id
        for candidate in candidates
    ] == [
        "P15D-a",
        "P15D-b",
        "P15D-c",
        "P15D-d",
    ]


def test_at_most_one_candidate_is_selected() -> None:
    state = make_state(
        make_defect(
            "P15D-a",
            x_m=0.05,
        ),
        make_defect(
            "P15D-b",
            x_m=0.10,
        ),
        make_defect(
            "P15D-c",
            x_m=0.15,
        ),
    )

    selected = select_candidate(
        state,
        make_observation(),
    )

    assert selected is not None
    assert selected.defect_id == "P15D-a"


def test_mapping_insertion_order_does_not_change_candidate_ranking() -> None:
    alpha = make_defect(
        "P15D-alpha",
        x_m=-0.10,
    )
    zeta = make_defect(
        "P15D-zeta",
        x_m=0.10,
    )

    state_one = FusionState(
        inspection_id=1,
        config=FusionConfig(),
        defects={
            zeta.defect_id: zeta,
            alpha.defect_id: alpha,
        },
    )

    state_two = FusionState(
        inspection_id=1,
        config=FusionConfig(),
        defects={
            alpha.defect_id: alpha,
            zeta.defect_id: zeta,
        },
    )

    first = select_candidate(
        state_one,
        make_observation(),
    )
    second = select_candidate(
        state_two,
        make_observation(),
    )

    assert first is not None
    assert second is not None
    assert first.defect_id == "P15D-alpha"
    assert second.defect_id == "P15D-alpha"


def test_custom_threshold_is_respected() -> None:
    state = FusionState(
        inspection_id=1,
        config=FusionConfig(
            association_distance_m=0.10,
        ),
        defects={
            "P15D-a": make_defect(
                "P15D-a",
                x_m=0.11,
            )
        },
    )

    assert select_candidate(
        state,
        make_observation(),
    ) is None


def test_cross_inspection_observation_fails_closed() -> None:
    state = make_state(
        make_defect(
            "P15D-a",
            x_m=0.05,
        )
    )

    with pytest.raises(
        ValidationError,
        match="cross-inspection",
    ):
        select_candidate(
            state,
            make_observation(
                inspection_id=2,
            ),
        )


def test_invalid_non_map_observation_fails_closed() -> None:
    state = make_state(
        make_defect(
            "P15D-a",
            x_m=0.05,
        )
    )

    with pytest.raises(
        ValidationError,
        match='exactly "map"',
    ):
        select_candidate(
            state,
            make_observation(
                coordinate_frame="odom",
            ),
        )


def test_invalid_state_defect_fails_closed() -> None:
    bad = make_defect(
        "P15D-bad",
        x_m=0.05,
    )

    # Bypass normal construction semantics only to prove the
    # association boundary validates state before using it.
    object.__setattr__(
        bad,
        "confidence",
        float("nan"),
    )

    state = FusionState(
        inspection_id=1,
        config=FusionConfig(),
        defects={
            bad.defect_id: bad,
        },
    )

    with pytest.raises(ValidationError):
        select_candidate(
            state,
            make_observation(),
        )
