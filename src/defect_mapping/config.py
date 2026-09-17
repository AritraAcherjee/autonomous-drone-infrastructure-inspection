"""Frozen configuration and taxonomy for P15 defect-to-map fusion."""

from __future__ import annotations

from dataclasses import dataclass
import math


MAP_FRAME = "map"
DEFAULT_ASSOCIATION_DISTANCE_M = 0.25
DEFAULT_MODEL_VERSION = "DET-FINAL-v1"

CLASS_NAMES_BY_ID = {
    0: "Crack",
    1: "Breakage",
    2: "Honeycombing",
    3: "Hole",
    4: "Exposed Reinforcement",
    5: "Seepage",
}


@dataclass(frozen=True, slots=True)
class FusionConfig:
    """Immutable configuration for one P15 fusion state."""

    association_distance_m: float = DEFAULT_ASSOCIATION_DISTANCE_M
    expected_model_version: str = DEFAULT_MODEL_VERSION

    def __post_init__(self) -> None:
        value = self.association_distance_m

        if type(value) not in {int, float}:
            raise ValueError("association_distance_m must be numeric")

        value = float(value)

        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(
                "association_distance_m must be finite and > 0"
            )

        model_version = self.expected_model_version

        if (
            not isinstance(model_version, str)
            or not model_version
            or model_version.strip() != model_version
        ):
            raise ValueError(
                "expected_model_version must be a non-empty trimmed string"
            )

        object.__setattr__(self, "association_distance_m", value)
