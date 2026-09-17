"""Deterministic identity and replay fingerprint primitives for P15."""

from __future__ import annotations

from datetime import timezone
import hashlib
import json
import math
import unicodedata
import uuid
from typing import Any

from .config import FusionConfig
from .models import MappedObservation
from .validation import ValidationError, validate_observation


PERSISTENT_ID_PREFIX = "P15D-"
PERSISTENT_ID_NAME_PREFIX = "urn:aegisinspect:p15:defect:v1"
PERSISTENT_ID_NAMESPACE = uuid.NAMESPACE_URL


def _validate_identity_component(
    *,
    inspection_id: object,
    observation_id: object,
) -> tuple[int, str]:
    if type(inspection_id) is not int or inspection_id < 1:
        raise ValidationError(
            "inspection_id must be an integer >= 1"
        )

    if not isinstance(observation_id, str):
        raise ValidationError("observation_id must be a string")

    if (
        not observation_id
        or observation_id.strip() != observation_id
        or len(observation_id) > 256
        or any(
            unicodedata.category(char) == "Cc"
            for char in observation_id
        )
    ):
        raise ValidationError(
            "observation_id is invalid for persistent identity"
        )

    return inspection_id, observation_id


def persistent_defect_id(
    inspection_id: int,
    observation_id: str,
) -> str:
    """Return the frozen deterministic P15 persistent defect ID.

    The identity is deterministic only under the frozen Aegis inputs.
    It does not claim universal uniqueness across independently recreated
    databases/deployments that reuse the same inspection/observation IDs.
    """

    inspection_id, observation_id = _validate_identity_component(
        inspection_id=inspection_id,
        observation_id=observation_id,
    )

    name = (
        f"{PERSISTENT_ID_NAME_PREFIX}:"
        f"{inspection_id}:"
        f"{observation_id}"
    )

    identifier = uuid.uuid5(
        PERSISTENT_ID_NAMESPACE,
        name,
    )

    return f"{PERSISTENT_ID_PREFIX}{str(identifier)}"


def _canonical_float(value: float) -> float:
    value = float(value)

    if not math.isfinite(value):
        raise ValidationError(
            "canonical fingerprint values must be finite"
        )

    # Normalize IEEE negative zero so semantically equal validated
    # numeric observations do not receive different fingerprints.
    if value == 0.0:
        return 0.0

    return value


def canonical_observation_payload(
    observation: MappedObservation,
    *,
    config: FusionConfig,
    inspection_id: int | None = None,
) -> dict[str, Any]:
    """Return the canonical normalized representation of all DTO fields."""

    normalized = validate_observation(
        observation,
        config=config,
        inspection_id=inspection_id,
    )

    timestamp = normalized.timestamp.astimezone(timezone.utc)
    timestamp_text = (
        timestamp.isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )

    return {
        "inspection_id": normalized.inspection_id,
        "observation_id": normalized.observation_id,
        "detection_id": normalized.detection_id,
        "track_id": normalized.track_id,
        "class_id": normalized.class_id,
        "class_name": normalized.class_name,
        "confidence": _canonical_float(
            normalized.confidence
        ),
        "x_m": _canonical_float(normalized.x_m),
        "y_m": _canonical_float(normalized.y_m),
        "z_m": _canonical_float(normalized.z_m),
        "coordinate_frame": normalized.coordinate_frame,
        "timestamp": timestamp_text,
        "source_frame_id": normalized.source_frame_id,
        "bbox_xyxy": [
            _canonical_float(value)
            for value in normalized.bbox_xyxy
        ],
        "image_width": normalized.image_width,
        "image_height": normalized.image_height,
        "model_version": normalized.model_version,
        "image_path": normalized.image_path,
        "crop_path": normalized.crop_path,
    }


def canonical_observation_bytes(
    observation: MappedObservation,
    *,
    config: FusionConfig,
    inspection_id: int | None = None,
) -> bytes:
    payload = canonical_observation_payload(
        observation,
        config=config,
        inspection_id=inspection_id,
    )

    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )

    return text.encode("utf-8")


def observation_fingerprint(
    observation: MappedObservation,
    *,
    config: FusionConfig,
    inspection_id: int | None = None,
) -> str:
    """SHA-256 of the canonical normalized full observation payload."""

    canonical = canonical_observation_bytes(
        observation,
        config=config,
        inspection_id=inspection_id,
    )

    return hashlib.sha256(canonical).hexdigest()
