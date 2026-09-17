"""Immutable P15 domain models.

The pure domain intentionally contains no ROS, tf2, database, dashboard,
detector-runtime, or P16 storage imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Literal, Mapping

from .config import FusionConfig


MapFrame = Literal["map"]


class FusionDecision(str, Enum):
    CREATED = "CREATED"
    ASSOCIATED = "ASSOCIATED"
    REPLAY = "REPLAY"


@dataclass(frozen=True, slots=True)
class MappedObservation:
    inspection_id: int
    observation_id: str
    detection_id: str
    track_id: str | None
    class_id: int
    class_name: str
    confidence: float
    x_m: float
    y_m: float
    z_m: float
    coordinate_frame: MapFrame
    timestamp: datetime
    source_frame_id: str
    bbox_xyxy: tuple[float, float, float, float]
    image_width: int
    image_height: int
    model_version: str
    image_path: str | None
    crop_path: str | None


@dataclass(frozen=True, slots=True)
class ObservationProvenance:
    observation_id: str
    detection_id: str
    inspection_id: int
    track_id: str | None
    class_id: int
    class_name: str
    confidence: float
    x_m: float
    y_m: float
    z_m: float
    coordinate_frame: MapFrame
    timestamp: datetime
    source_frame_id: str
    bbox_xyxy: tuple[float, float, float, float]
    image_width: int
    image_height: int
    model_version: str
    image_path: str | None
    crop_path: str | None

    @classmethod
    def from_observation(
        cls,
        observation: MappedObservation,
    ) -> "ObservationProvenance":
        return cls(
            observation_id=observation.observation_id,
            detection_id=observation.detection_id,
            inspection_id=observation.inspection_id,
            track_id=observation.track_id,
            class_id=observation.class_id,
            class_name=observation.class_name,
            confidence=observation.confidence,
            x_m=observation.x_m,
            y_m=observation.y_m,
            z_m=observation.z_m,
            coordinate_frame=observation.coordinate_frame,
            timestamp=observation.timestamp,
            source_frame_id=observation.source_frame_id,
            bbox_xyxy=observation.bbox_xyxy,
            image_width=observation.image_width,
            image_height=observation.image_height,
            model_version=observation.model_version,
            image_path=observation.image_path,
            crop_path=observation.crop_path,
        )


@dataclass(frozen=True, slots=True)
class ProcessedObservation:
    observation_id: str
    fingerprint: str
    defect_id: str


@dataclass(frozen=True, slots=True)
class PersistentDefect:
    defect_id: str
    inspection_id: int
    creator_observation_id: str
    class_id: int
    class_name: str
    confidence: float
    x_m: float
    y_m: float
    z_m: float
    coordinate_frame: MapFrame
    observation_count: int
    first_seen: datetime
    last_seen: datetime
    canonical_track_id: str | None
    track_ids: tuple[str, ...]
    track_observation_counts: tuple[tuple[str, int], ...]
    model_version: str
    observation_ids: tuple[str, ...]
    provenance: tuple[ObservationProvenance, ...]


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(sorted(value.items())))


@dataclass(frozen=True, slots=True)
class FusionState:
    inspection_id: int
    config: FusionConfig
    schema_version: int = 1
    defects: Mapping[str, PersistentDefect] = field(default_factory=dict)
    processed_observations: Mapping[str, ProcessedObservation] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "defects",
            _freeze_mapping(self.defects),
        )
        object.__setattr__(
            self,
            "processed_observations",
            _freeze_mapping(self.processed_observations),
        )


@dataclass(frozen=True, slots=True)
class FusionResult:
    new_state: FusionState
    decision: FusionDecision
    defect_id: str
    observation_id: str
