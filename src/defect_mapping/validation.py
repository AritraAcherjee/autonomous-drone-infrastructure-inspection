"""Fail-closed validation for the pure P15 domain."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import math
import re
import unicodedata

from .config import (
    CLASS_NAMES_BY_ID,
    MAP_FRAME,
    FusionConfig,
)
from .models import (
    FusionState,
    MappedObservation,
    ObservationProvenance,
    PersistentDefect,
)


class ValidationError(ValueError):
    """Raised when a P15 domain contract is violated."""


def _fail(message: str) -> None:
    raise ValidationError(message)


def _positive_int(name: str, value: object) -> int:
    if type(value) is not int or value < 1:
        _fail(f"{name} must be an integer >= 1")
    return value


def _identifier(name: str, value: object) -> str:
    if not isinstance(value, str):
        _fail(f"{name} must be a string")

    if not value or value.strip() != value:
        _fail(f"{name} must be non-empty with no surrounding whitespace")

    if len(value) > 256:
        _fail(f"{name} must be <= 256 characters")

    if any(unicodedata.category(char) == "Cc" for char in value):
        _fail(f"{name} must not contain control characters")

    return value


def _nonempty_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{name} must be a non-empty string")
    return value


def _optional_path(name: str, value: object) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        _fail(f"{name} must be None or a non-empty string")

    return value


def _finite_number(name: str, value: object) -> float:
    if type(value) not in {int, float}:
        _fail(f"{name} must be numeric")

    value = float(value)

    if not math.isfinite(value):
        _fail(f"{name} must be finite")

    return value


def _confidence(value: object) -> float:
    value = _finite_number("confidence", value)

    if not 0.0 <= value <= 1.0:
        _fail("confidence must be in [0, 1]")

    return value


def _aware_utc(name: str, value: object) -> datetime:
    if not isinstance(value, datetime):
        _fail(f"{name} must be a datetime")

    try:
        offset = value.utcoffset()
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ValidationError(
            f"{name} must be UTC-convertible"
        ) from exc

    if value.tzinfo is None or offset is None:
        _fail(f"{name} must be timezone-aware")

    try:
        return value.astimezone(timezone.utc)
    except Exception as exc:
        raise ValidationError(
            f"{name} must be UTC-convertible"
        ) from exc


def validate_config(config: FusionConfig) -> FusionConfig:
    if not isinstance(config, FusionConfig):
        _fail("config must be a FusionConfig")

    # FusionConfig.__post_init__ already enforces its frozen invariants.
    return config


def validate_observation(
    observation: MappedObservation,
    *,
    config: FusionConfig,
    inspection_id: int | None = None,
) -> MappedObservation:
    """Validate and UTC-normalize one already-map-localized observation."""

    if not isinstance(observation, MappedObservation):
        _fail("observation must be a MappedObservation")

    validate_config(config)

    obs_inspection_id = _positive_int(
        "inspection_id",
        observation.inspection_id,
    )

    if inspection_id is not None:
        expected_inspection_id = _positive_int(
            "expected inspection_id",
            inspection_id,
        )

        if obs_inspection_id != expected_inspection_id:
            _fail(
                "cross-inspection observation rejected: "
                f"{obs_inspection_id} != {expected_inspection_id}"
            )

    observation_id = _identifier(
        "observation_id",
        observation.observation_id,
    )
    detection_id = _identifier(
        "detection_id",
        observation.detection_id,
    )

    if observation_id != detection_id:
        _fail("observation_id must equal detection_id for the P15 MVP")

    if observation.track_id is not None:
        _identifier("track_id", observation.track_id)

    expected_class_name = CLASS_NAMES_BY_ID.get(observation.class_id)

    if expected_class_name is None:
        _fail("class_id is outside the frozen six-class taxonomy")

    if observation.class_name != expected_class_name:
        _fail(
            "class_id/class_name mismatch: "
            f"expected {expected_class_name!r}"
        )

    confidence = _confidence(observation.confidence)
    x_m = _finite_number("x_m", observation.x_m)
    y_m = _finite_number("y_m", observation.y_m)
    z_m = _finite_number("z_m", observation.z_m)

    if observation.coordinate_frame != MAP_FRAME:
        _fail('coordinate_frame must be exactly "map"')

    timestamp = _aware_utc("timestamp", observation.timestamp)

    _nonempty_text(
        "source_frame_id",
        observation.source_frame_id,
    )

    image_width = _positive_int(
        "image_width",
        observation.image_width,
    )
    image_height = _positive_int(
        "image_height",
        observation.image_height,
    )

    bbox = observation.bbox_xyxy

    if not isinstance(bbox, tuple) or len(bbox) != 4:
        _fail("bbox_xyxy must be a 4-tuple")

    x1 = _finite_number("bbox_x1", bbox[0])
    y1 = _finite_number("bbox_y1", bbox[1])
    x2 = _finite_number("bbox_x2", bbox[2])
    y2 = _finite_number("bbox_y2", bbox[3])

    if not (0.0 <= x1 < x2 <= image_width):
        _fail(
            "bbox x coordinates must satisfy "
            "0 <= x1 < x2 <= image_width"
        )

    if not (0.0 <= y1 < y2 <= image_height):
        _fail(
            "bbox y coordinates must satisfy "
            "0 <= y1 < y2 <= image_height"
        )

    model_version = observation.model_version

    if (
        not isinstance(model_version, str)
        or not model_version
        or model_version.strip() != model_version
    ):
        _fail("model_version must be a non-empty trimmed string")

    if model_version != config.expected_model_version:
        _fail(
            "model_version does not match FusionState configuration"
        )

    image_path = _optional_path(
        "image_path",
        observation.image_path,
    )
    crop_path = _optional_path(
        "crop_path",
        observation.crop_path,
    )

    return replace(
        observation,
        confidence=confidence,
        x_m=x_m,
        y_m=y_m,
        z_m=z_m,
        timestamp=timestamp,
        bbox_xyxy=(x1, y1, x2, y2),
        image_path=image_path,
        crop_path=crop_path,
    )


def validate_provenance(
    provenance: ObservationProvenance,
    *,
    config: FusionConfig,
    inspection_id: int | None = None,
) -> ObservationProvenance:
    if not isinstance(provenance, ObservationProvenance):
        _fail("provenance must be ObservationProvenance")

    normalized = validate_observation(
        MappedObservation(
            inspection_id=provenance.inspection_id,
            observation_id=provenance.observation_id,
            detection_id=provenance.detection_id,
            track_id=provenance.track_id,
            class_id=provenance.class_id,
            class_name=provenance.class_name,
            confidence=provenance.confidence,
            x_m=provenance.x_m,
            y_m=provenance.y_m,
            z_m=provenance.z_m,
            coordinate_frame=provenance.coordinate_frame,
            timestamp=provenance.timestamp,
            source_frame_id=provenance.source_frame_id,
            bbox_xyxy=provenance.bbox_xyxy,
            image_width=provenance.image_width,
            image_height=provenance.image_height,
            model_version=provenance.model_version,
            image_path=provenance.image_path,
            crop_path=provenance.crop_path,
        ),
        config=config,
        inspection_id=inspection_id,
    )

    return ObservationProvenance.from_observation(normalized)


def validate_persistent_defect(
    defect: PersistentDefect,
    *,
    config: FusionConfig,
    inspection_id: int | None = None,
) -> PersistentDefect:
    if not isinstance(defect, PersistentDefect):
        _fail("defect must be a PersistentDefect")

    validate_config(config)

    defect_inspection_id = _positive_int(
        "inspection_id",
        defect.inspection_id,
    )

    if (
        inspection_id is not None
        and defect_inspection_id != inspection_id
    ):
        _fail("persistent defect inspection_id does not match state")

    _identifier("defect_id", defect.defect_id)
    _identifier(
        "creator_observation_id",
        defect.creator_observation_id,
    )

    expected_class_name = CLASS_NAMES_BY_ID.get(defect.class_id)

    if expected_class_name is None:
        _fail("persistent defect class_id is invalid")

    if defect.class_name != expected_class_name:
        _fail("persistent defect class_id/class_name mismatch")

    confidence = _confidence(defect.confidence)
    x_m = _finite_number("x_m", defect.x_m)
    y_m = _finite_number("y_m", defect.y_m)
    z_m = _finite_number("z_m", defect.z_m)

    if defect.coordinate_frame != MAP_FRAME:
        _fail('persistent defect coordinate_frame must be exactly "map"')

    observation_count = _positive_int(
        "observation_count",
        defect.observation_count,
    )

    first_seen = _aware_utc("first_seen", defect.first_seen)
    last_seen = _aware_utc("last_seen", defect.last_seen)

    if last_seen < first_seen:
        _fail("last_seen must be >= first_seen")

    if defect.model_version != config.expected_model_version:
        _fail("persistent defect model_version mismatch")

    if defect.canonical_track_id is not None:
        _identifier(
            "canonical_track_id",
            defect.canonical_track_id,
        )

    if len(set(defect.track_ids)) != len(defect.track_ids):
        _fail("track_ids must not contain duplicates")

    for track_id in defect.track_ids:
        _identifier("track_id", track_id)

    track_counts: dict[str, int] = {}

    for item in defect.track_observation_counts:
        if not isinstance(item, tuple) or len(item) != 2:
            _fail(
                "track_observation_counts entries must be "
                "(track_id, count) tuples"
            )

        track_id, count = item
        _identifier("track_id", track_id)
        _positive_int("track observation count", count)

        if track_id in track_counts:
            _fail("track_observation_counts contains duplicate track_id")

        track_counts[track_id] = count

    if set(track_counts) != set(defect.track_ids):
        _fail(
            "track_observation_counts keys must exactly match track_ids"
        )

    if track_counts:
        expected_canonical = sorted(
            track_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[0][0]

        if defect.canonical_track_id != expected_canonical:
            _fail(
                "canonical_track_id must be the most frequent "
                "non-null track ID, with lexical tie-break"
            )
    elif defect.canonical_track_id is not None:
        _fail("canonical_track_id must be None when no track IDs exist")

    if len(defect.observation_ids) != observation_count:
        _fail(
            "observation_ids length must equal observation_count"
        )

    if len(set(defect.observation_ids)) != len(defect.observation_ids):
        _fail("observation_ids must be unique")

    for observation_id in defect.observation_ids:
        _identifier("observation_id", observation_id)

    if defect.creator_observation_id not in defect.observation_ids:
        _fail(
            "creator_observation_id must be one of observation_ids"
        )

    if len(defect.provenance) != observation_count:
        _fail("provenance length must equal observation_count")

    normalized_provenance = tuple(
        validate_provenance(
            record,
            config=config,
            inspection_id=defect_inspection_id,
        )
        for record in defect.provenance
    )

    provenance_ids = tuple(
        record.observation_id
        for record in normalized_provenance
    )

    if provenance_ids != defect.observation_ids:
        _fail(
            "provenance observation ordering must match observation_ids"
        )

    for record in normalized_provenance:
        if (
            record.class_id != defect.class_id
            or record.class_name != defect.class_name
        ):
            _fail(
                "all provenance must match the persistent defect class"
            )

    if min(record.timestamp for record in normalized_provenance) != first_seen:
        _fail("first_seen must equal minimum provenance timestamp")

    if max(record.timestamp for record in normalized_provenance) != last_seen:
        _fail("last_seen must equal maximum provenance timestamp")

    return replace(
        defect,
        confidence=confidence,
        x_m=x_m,
        y_m=y_m,
        z_m=z_m,
        first_seen=first_seen,
        last_seen=last_seen,
        provenance=normalized_provenance,
    )


def validate_state(state: FusionState) -> FusionState:
    if not isinstance(state, FusionState):
        _fail("state must be a FusionState")

    _positive_int("inspection_id", state.inspection_id)
    validate_config(state.config)

    if state.schema_version != 1:
        _fail("unsupported FusionState schema_version")

    for defect_id, defect in state.defects.items():
        if defect_id != defect.defect_id:
            _fail("defects mapping key must equal defect.defect_id")

        validate_persistent_defect(
            defect,
            config=state.config,
            inspection_id=state.inspection_id,
        )

    fingerprint_pattern = re.compile(r"[0-9a-f]{64}")

    for observation_id, processed in state.processed_observations.items():
        if observation_id != processed.observation_id:
            _fail(
                "processed observation mapping key must equal "
                "processed.observation_id"
            )

        _identifier("observation_id", processed.observation_id)
        _identifier("defect_id", processed.defect_id)

        if fingerprint_pattern.fullmatch(processed.fingerprint) is None:
            _fail(
                "processed observation fingerprint must be "
                "64 lowercase hexadecimal characters"
            )

        if processed.defect_id not in state.defects:
            _fail(
                "processed observation references unknown defect_id"
            )

    return state
