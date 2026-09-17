"""Phase-6 deterministic state serialization tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json

import pytest

from src.defect_mapping import (
    FusionDecision,
    MappedObservation,
    SerializationError,
    create_state,
    export_state,
    import_state,
    ingest_batch,
    ingest_observation,
    state_from_json,
    state_to_json,
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
    x_m: float,
    *,
    track_id: str | None = None,
) -> MappedObservation:
    return MappedObservation(
        inspection_id=1,
        observation_id=observation_id,
        detection_id=observation_id,
        track_id=track_id,
        class_id=0,
        class_name="Crack",
        confidence=0.9,
        x_m=x_m,
        y_m=1.0,
        z_m=2.0,
        coordinate_frame="map",
        timestamp=T0,
        source_frame_id="camera_optical_frame",
        bbox_xyxy=(10.0, 10.0, 50.0, 50.0),
        image_width=640,
        image_height=480,
        model_version="DET-FINAL-v1",
        image_path=None,
        crop_path=None,
    )


def populated_state():
    state, _ = ingest_batch(
        create_state(1),
        (
            obs("obs-1", 0.0, track_id="track-a"),
            obs("obs-2", 0.1, track_id="track-a"),
            obs("obs-3", 1.0, track_id="track-b"),
        ),
    )
    return state


def test_empty_state_round_trip() -> None:
    original = create_state(1)

    restored = import_state(
        export_state(original)
    )

    assert restored == original


def test_populated_state_round_trip() -> None:
    original = populated_state()

    restored = import_state(
        export_state(original)
    )

    assert restored == original


def test_json_round_trip_preserves_state() -> None:
    original = populated_state()

    text = state_to_json(original)
    restored = state_from_json(text)

    assert restored == original


def test_json_export_is_deterministic_for_same_state() -> None:
    state = populated_state()

    first = state_to_json(state)
    second = state_to_json(state)

    assert first == second


def test_json_is_compact_and_canonical_key_sorted() -> None:
    text = state_to_json(populated_state())

    assert "\n" not in text
    assert ": " not in text
    assert ", " not in text

    parsed = json.loads(text)

    assert parsed["format"] == (
        "aegisinspect.p15.fusion-state"
    )
    assert parsed["serialization_version"] == 1


def test_defects_export_in_lexical_id_order() -> None:
    payload = export_state(populated_state())

    defect_ids = [
        item["defect_id"]
        for item in payload["defects"]
    ]

    assert defect_ids == sorted(defect_ids)


def test_processed_registry_exports_in_observation_id_order() -> None:
    payload = export_state(populated_state())

    observation_ids = [
        item["observation_id"]
        for item in payload["processed_observations"]
    ]

    assert observation_ids == sorted(observation_ids)


def test_provenance_ingestion_order_is_preserved() -> None:
    state, results = ingest_batch(
        create_state(1),
        (
            obs("z", 0.0),
            obs("a", 0.1),
        ),
    )

    defect = state.defects[
        results[0].defect_id
    ]

    assert defect.observation_ids == (
        "z",
        "a",
    )

    restored = state_from_json(
        state_to_json(state)
    )

    restored_defect = restored.defects[
        results[0].defect_id
    ]

    assert restored_defect.observation_ids == (
        "z",
        "a",
    )


def test_persistent_ids_are_stable_across_round_trip() -> None:
    original = populated_state()
    restored = state_from_json(
        state_to_json(original)
    )

    assert set(restored.defects) == set(original.defects)

    for defect_id in original.defects:
        assert restored.defects[defect_id].defect_id == defect_id


def test_replay_after_import_is_idempotent() -> None:
    original = populated_state()
    restored = state_from_json(
        state_to_json(original)
    )

    replay = ingest_observation(
        restored,
        obs("obs-1", 0.0, track_id="track-a"),
    )

    assert replay.decision is FusionDecision.REPLAY
    assert replay.new_state is restored


def test_new_observation_after_import_can_associate() -> None:
    state, results = ingest_batch(
        create_state(1),
        (
            obs("obs-1", 0.0),
            obs("far", 2.0),
        ),
    )

    restored = state_from_json(
        state_to_json(state)
    )

    result = ingest_observation(
        restored,
        obs("obs-2", 0.1),
    )

    assert result.decision is FusionDecision.ASSOCIATED
    assert result.defect_id == results[0].defect_id


@pytest.mark.parametrize(
    "field",
    [
        "format",
        "serialization_version",
        "state_schema_version",
        "inspection_id",
        "config",
        "defects",
        "processed_observations",
    ],
)
def test_missing_top_level_field_fails_closed(
    field: str,
) -> None:
    payload = export_state(populated_state())
    del payload[field]

    with pytest.raises(SerializationError):
        import_state(payload)


def test_extra_top_level_field_fails_closed() -> None:
    payload = export_state(populated_state())
    payload["unexpected"] = True

    with pytest.raises(SerializationError):
        import_state(payload)


def test_wrong_serialization_format_fails_closed() -> None:
    payload = export_state(populated_state())
    payload["format"] = "wrong"

    with pytest.raises(
        SerializationError,
        match="format",
    ):
        import_state(payload)


def test_wrong_serialization_version_fails_closed() -> None:
    payload = export_state(populated_state())
    payload["serialization_version"] = 999

    with pytest.raises(
        SerializationError,
        match="version",
    ):
        import_state(payload)


def test_invalid_state_schema_version_fails_closed() -> None:
    payload = export_state(populated_state())
    payload["state_schema_version"] = 999

    with pytest.raises(SerializationError):
        import_state(payload)


def test_cross_inspection_defect_tampering_fails_closed() -> None:
    payload = export_state(populated_state())
    payload["defects"][0]["inspection_id"] = 2
    payload["defects"][0]["provenance"][0]["inspection_id"] = 2

    with pytest.raises(SerializationError):
        import_state(payload)


def test_non_map_provenance_tampering_fails_closed() -> None:
    payload = export_state(populated_state())
    payload["defects"][0]["provenance"][0][
        "coordinate_frame"
    ] = "odom"

    with pytest.raises(SerializationError):
        import_state(payload)


def test_model_version_tampering_fails_closed() -> None:
    payload = export_state(populated_state())
    payload["defects"][0]["model_version"] = "OTHER"

    with pytest.raises(SerializationError):
        import_state(payload)


def test_processed_unknown_defect_fails_closed() -> None:
    payload = export_state(populated_state())
    payload["processed_observations"][0][
        "defect_id"
    ] = "P15D-missing"

    with pytest.raises(SerializationError):
        import_state(payload)


def test_processed_fingerprint_tampering_fails_closed() -> None:
    payload = export_state(populated_state())
    payload["processed_observations"][0][
        "fingerprint"
    ] = "0" * 64

    with pytest.raises(
        SerializationError,
        match="fingerprint",
    ):
        import_state(payload)


def test_missing_processed_registry_entry_fails_closed() -> None:
    payload = export_state(populated_state())

    del payload["processed_observations"][0]

    with pytest.raises(
        SerializationError,
        match="registry",
    ):
        import_state(payload)


def test_extra_processed_registry_entry_fails_closed() -> None:
    payload = export_state(populated_state())

    extra = deepcopy(
        payload["processed_observations"][0]
    )
    extra["observation_id"] = "invented-observation"

    payload["processed_observations"].append(extra)

    with pytest.raises(SerializationError):
        import_state(payload)


def test_duplicate_defect_id_fails_closed() -> None:
    payload = export_state(populated_state())

    payload["defects"].append(
        deepcopy(payload["defects"][0])
    )

    with pytest.raises(
        SerializationError,
        match="duplicate",
    ):
        import_state(payload)


def test_duplicate_processed_observation_fails_closed() -> None:
    payload = export_state(populated_state())

    payload["processed_observations"].append(
        deepcopy(
            payload["processed_observations"][0]
        )
    )

    with pytest.raises(
        SerializationError,
        match="duplicate",
    ):
        import_state(payload)


def test_timestamp_must_use_canonical_utc_z_form() -> None:
    payload = export_state(populated_state())

    payload["defects"][0]["first_seen"] = (
        "2026-09-16T12:00:00+00:00"
    )

    with pytest.raises(
        SerializationError,
        match="canonical",
    ):
        import_state(payload)


def test_invalid_json_fails_closed() -> None:
    with pytest.raises(
        SerializationError,
        match="invalid",
    ):
        state_from_json("{broken")


def test_export_does_not_mutate_state() -> None:
    state = populated_state()

    before = state_to_json(state)

    export_state(state)

    after = state_to_json(state)

    assert before == after
