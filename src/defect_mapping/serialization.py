"""Deterministic export/import for immutable P15 FusionState."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
from typing import Any

from .config import FusionConfig
from .identity import observation_fingerprint
from .models import (
    FusionState,
    MappedObservation,
    ObservationProvenance,
    PersistentDefect,
    ProcessedObservation,
)
from .validation import ValidationError, validate_state


SERIALIZATION_FORMAT = "aegisinspect.p15.fusion-state"
SERIALIZATION_VERSION = 1


class SerializationError(ValidationError):
    """Raised when P15 serialized state is malformed or inconsistent."""


def _fail(message: str) -> None:
    raise SerializationError(message)


def _exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    *,
    name: str,
) -> None:
    actual = set(value)

    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        _fail(
            f"{name} keys mismatch; "
            f"missing={missing}, extra={extra}"
        )


def _timestamp_to_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        _fail("serialized timestamps must be timezone-aware")

    utc = value.astimezone(timezone.utc)

    return (
        utc.isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _timestamp_from_text(value: object) -> datetime:
    if not isinstance(value, str):
        _fail("serialized timestamp must be a string")

    if not value.endswith("Z"):
        _fail("serialized timestamp must use canonical UTC Z form")

    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00"
        )
    except ValueError as exc:
        raise SerializationError(
            "serialized timestamp is invalid"
        ) from exc

    parsed = parsed.astimezone(timezone.utc)

    if _timestamp_to_text(parsed) != value:
        _fail("serialized timestamp is not canonical")

    return parsed


def _provenance_to_dict(
    record: ObservationProvenance,
) -> dict[str, Any]:
    return {
        "observation_id": record.observation_id,
        "detection_id": record.detection_id,
        "inspection_id": record.inspection_id,
        "track_id": record.track_id,
        "class_id": record.class_id,
        "class_name": record.class_name,
        "confidence": record.confidence,
        "x_m": record.x_m,
        "y_m": record.y_m,
        "z_m": record.z_m,
        "coordinate_frame": record.coordinate_frame,
        "timestamp": _timestamp_to_text(record.timestamp),
        "source_frame_id": record.source_frame_id,
        "bbox_xyxy": list(record.bbox_xyxy),
        "image_width": record.image_width,
        "image_height": record.image_height,
        "model_version": record.model_version,
        "image_path": record.image_path,
        "crop_path": record.crop_path,
    }


def _provenance_from_dict(
    value: object,
) -> ObservationProvenance:
    if not isinstance(value, Mapping):
        _fail("provenance entry must be an object")

    _exact_keys(
        value,
        {
            "observation_id",
            "detection_id",
            "inspection_id",
            "track_id",
            "class_id",
            "class_name",
            "confidence",
            "x_m",
            "y_m",
            "z_m",
            "coordinate_frame",
            "timestamp",
            "source_frame_id",
            "bbox_xyxy",
            "image_width",
            "image_height",
            "model_version",
            "image_path",
            "crop_path",
        },
        name="provenance",
    )

    bbox = value["bbox_xyxy"]

    if not isinstance(bbox, list) or len(bbox) != 4:
        _fail("serialized bbox_xyxy must be a four-element list")

    return ObservationProvenance(
        observation_id=value["observation_id"],
        detection_id=value["detection_id"],
        inspection_id=value["inspection_id"],
        track_id=value["track_id"],
        class_id=value["class_id"],
        class_name=value["class_name"],
        confidence=value["confidence"],
        x_m=value["x_m"],
        y_m=value["y_m"],
        z_m=value["z_m"],
        coordinate_frame=value["coordinate_frame"],
        timestamp=_timestamp_from_text(value["timestamp"]),
        source_frame_id=value["source_frame_id"],
        bbox_xyxy=tuple(bbox),
        image_width=value["image_width"],
        image_height=value["image_height"],
        model_version=value["model_version"],
        image_path=value["image_path"],
        crop_path=value["crop_path"],
    )


def _defect_to_dict(
    defect: PersistentDefect,
) -> dict[str, Any]:
    return {
        "defect_id": defect.defect_id,
        "inspection_id": defect.inspection_id,
        "creator_observation_id": defect.creator_observation_id,
        "class_id": defect.class_id,
        "class_name": defect.class_name,
        "confidence": defect.confidence,
        "x_m": defect.x_m,
        "y_m": defect.y_m,
        "z_m": defect.z_m,
        "coordinate_frame": defect.coordinate_frame,
        "observation_count": defect.observation_count,
        "first_seen": _timestamp_to_text(defect.first_seen),
        "last_seen": _timestamp_to_text(defect.last_seen),
        "canonical_track_id": defect.canonical_track_id,
        "track_ids": list(defect.track_ids),
        "track_observation_counts": [
            [track_id, count]
            for track_id, count in defect.track_observation_counts
        ],
        "model_version": defect.model_version,
        "observation_ids": list(defect.observation_ids),
        "provenance": [
            _provenance_to_dict(record)
            for record in defect.provenance
        ],
    }


def _defect_from_dict(
    value: object,
) -> PersistentDefect:
    if not isinstance(value, Mapping):
        _fail("defect entry must be an object")

    _exact_keys(
        value,
        {
            "defect_id",
            "inspection_id",
            "creator_observation_id",
            "class_id",
            "class_name",
            "confidence",
            "x_m",
            "y_m",
            "z_m",
            "coordinate_frame",
            "observation_count",
            "first_seen",
            "last_seen",
            "canonical_track_id",
            "track_ids",
            "track_observation_counts",
            "model_version",
            "observation_ids",
            "provenance",
        },
        name="defect",
    )

    track_ids = value["track_ids"]
    counts = value["track_observation_counts"]
    observation_ids = value["observation_ids"]
    provenance = value["provenance"]

    if not isinstance(track_ids, list):
        _fail("track_ids must be a list")

    if not isinstance(counts, list):
        _fail("track_observation_counts must be a list")

    count_tuples: list[tuple[str, int]] = []

    for item in counts:
        if not isinstance(item, list) or len(item) != 2:
            _fail(
                "track_observation_counts entries must be two-element lists"
            )
        count_tuples.append((item[0], item[1]))

    if not isinstance(observation_ids, list):
        _fail("observation_ids must be a list")

    if not isinstance(provenance, list):
        _fail("provenance must be a list")

    return PersistentDefect(
        defect_id=value["defect_id"],
        inspection_id=value["inspection_id"],
        creator_observation_id=value["creator_observation_id"],
        class_id=value["class_id"],
        class_name=value["class_name"],
        confidence=value["confidence"],
        x_m=value["x_m"],
        y_m=value["y_m"],
        z_m=value["z_m"],
        coordinate_frame=value["coordinate_frame"],
        observation_count=value["observation_count"],
        first_seen=_timestamp_from_text(value["first_seen"]),
        last_seen=_timestamp_from_text(value["last_seen"]),
        canonical_track_id=value["canonical_track_id"],
        track_ids=tuple(track_ids),
        track_observation_counts=tuple(count_tuples),
        model_version=value["model_version"],
        observation_ids=tuple(observation_ids),
        provenance=tuple(
            _provenance_from_dict(record)
            for record in provenance
        ),
    )


def export_state(
    state: FusionState,
) -> dict[str, Any]:
    """Export a validated state to deterministic JSON-compatible data."""

    validate_state(state)

    return {
        "format": SERIALIZATION_FORMAT,
        "serialization_version": SERIALIZATION_VERSION,
        "state_schema_version": state.schema_version,
        "inspection_id": state.inspection_id,
        "config": {
            "association_distance_m": (
                state.config.association_distance_m
            ),
            "expected_model_version": (
                state.config.expected_model_version
            ),
        },
        "defects": [
            _defect_to_dict(state.defects[defect_id])
            for defect_id in sorted(state.defects)
        ],
        "processed_observations": [
            {
                "observation_id": record.observation_id,
                "fingerprint": record.fingerprint,
                "defect_id": record.defect_id,
            }
            for _, record in sorted(
                state.processed_observations.items()
            )
        ],
    }


def state_to_json(
    state: FusionState,
) -> str:
    """Return canonical compact UTF-8-safe JSON text."""

    return json.dumps(
        export_state(state),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _provenance_as_observation(
    record: ObservationProvenance,
) -> MappedObservation:
    return MappedObservation(
        inspection_id=record.inspection_id,
        observation_id=record.observation_id,
        detection_id=record.detection_id,
        track_id=record.track_id,
        class_id=record.class_id,
        class_name=record.class_name,
        confidence=record.confidence,
        x_m=record.x_m,
        y_m=record.y_m,
        z_m=record.z_m,
        coordinate_frame=record.coordinate_frame,
        timestamp=record.timestamp,
        source_frame_id=record.source_frame_id,
        bbox_xyxy=record.bbox_xyxy,
        image_width=record.image_width,
        image_height=record.image_height,
        model_version=record.model_version,
        image_path=record.image_path,
        crop_path=record.crop_path,
    )


def _validate_registry_consistency(
    state: FusionState,
) -> None:
    provenance_index: dict[
        str,
        tuple[str, ObservationProvenance],
    ] = {}

    for defect_id, defect in state.defects.items():
        for record in defect.provenance:
            if record.observation_id in provenance_index:
                _fail(
                    "observation appears in multiple persistent defects"
                )

            provenance_index[record.observation_id] = (
                defect_id,
                record,
            )

    if set(provenance_index) != set(
        state.processed_observations
    ):
        _fail(
            "processed observation registry must exactly match "
            "persistent-defect provenance"
        )

    for observation_id, processed in (
        state.processed_observations.items()
    ):
        defect_id, record = provenance_index[
            observation_id
        ]

        if processed.defect_id != defect_id:
            _fail(
                "processed observation defect_id does not match provenance"
            )

        expected_fingerprint = observation_fingerprint(
            _provenance_as_observation(record),
            config=state.config,
            inspection_id=state.inspection_id,
        )

        if processed.fingerprint != expected_fingerprint:
            _fail(
                "processed observation fingerprint does not match provenance"
            )


def import_state(
    value: object,
) -> FusionState:
    """Import serialized state and fail closed on any inconsistency."""

    if not isinstance(value, Mapping):
        _fail("serialized state must be an object")

    _exact_keys(
        value,
        {
            "format",
            "serialization_version",
            "state_schema_version",
            "inspection_id",
            "config",
            "defects",
            "processed_observations",
        },
        name="serialized state",
    )

    if value["format"] != SERIALIZATION_FORMAT:
        _fail("unsupported serialization format")

    if value["serialization_version"] != SERIALIZATION_VERSION:
        _fail("unsupported serialization version")

    config_value = value["config"]

    if not isinstance(config_value, Mapping):
        _fail("serialized config must be an object")

    _exact_keys(
        config_value,
        {
            "association_distance_m",
            "expected_model_version",
        },
        name="config",
    )

    try:
        config = FusionConfig(
            association_distance_m=(
                config_value["association_distance_m"]
            ),
            expected_model_version=(
                config_value["expected_model_version"]
            ),
        )
    except (TypeError, ValueError) as exc:
        raise SerializationError(
            "serialized config is invalid"
        ) from exc

    defects_value = value["defects"]

    if not isinstance(defects_value, list):
        _fail("defects must be a list")

    defects: dict[str, PersistentDefect] = {}

    for item in defects_value:
        defect = _defect_from_dict(item)

        if defect.defect_id in defects:
            _fail("duplicate serialized defect_id")

        defects[defect.defect_id] = defect

    processed_value = value["processed_observations"]

    if not isinstance(processed_value, list):
        _fail("processed_observations must be a list")

    processed: dict[str, ProcessedObservation] = {}

    for item in processed_value:
        if not isinstance(item, Mapping):
            _fail("processed observation entry must be an object")

        _exact_keys(
            item,
            {
                "observation_id",
                "fingerprint",
                "defect_id",
            },
            name="processed observation",
        )

        record = ProcessedObservation(
            observation_id=item["observation_id"],
            fingerprint=item["fingerprint"],
            defect_id=item["defect_id"],
        )

        if record.observation_id in processed:
            _fail("duplicate processed observation_id")

        processed[record.observation_id] = record

    state = FusionState(
        inspection_id=value["inspection_id"],
        config=config,
        schema_version=value["state_schema_version"],
        defects=defects,
        processed_observations=processed,
    )

    try:
        validate_state(state)
    except ValidationError as exc:
        raise SerializationError(
            "serialized state violates P15 domain invariants"
        ) from exc

    _validate_registry_consistency(state)

    return state


def state_from_json(
    text: str,
) -> FusionState:
    if not isinstance(text, str):
        _fail("serialized JSON must be a string")

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SerializationError(
            "serialized JSON is invalid"
        ) from exc

    return import_state(value)
