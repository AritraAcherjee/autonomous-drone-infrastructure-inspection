"""Deterministic spatial association for P15.

Association is streaming and inspection-local.

Eligibility:
- exact inspection match
- strict frozen class match
- 3D Euclidean distance <= configured threshold

Ranking among eligible defects:
1. observation track_id already belongs to the persistent defect
2. smaller Euclidean distance
3. lexical persistent defect_id

Track identity is only a priority hint. It never bypasses the spatial
threshold or strict class gating.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .models import (
    FusionState,
    MappedObservation,
    PersistentDefect,
)
from .validation import (
    ValidationError,
    validate_observation,
    validate_persistent_defect,
    validate_state,
)


@dataclass(frozen=True, slots=True)
class AssociationCandidate:
    defect_id: str
    distance_m: float
    track_match: bool


def euclidean_distance_m(
    observation: MappedObservation,
    defect: PersistentDefect,
) -> float:
    """Return finite 3D Euclidean distance in metres."""

    dx = observation.x_m - defect.x_m
    dy = observation.y_m - defect.y_m
    dz = observation.z_m - defect.z_m

    distance = math.sqrt(
        dx * dx
        + dy * dy
        + dz * dz
    )

    if not math.isfinite(distance):
        raise ValidationError(
            "association distance must be finite"
        )

    return distance


def _strict_class_match(
    observation: MappedObservation,
    defect: PersistentDefect,
) -> bool:
    return (
        observation.class_id == defect.class_id
        and observation.class_name == defect.class_name
    )


def _track_match(
    observation: MappedObservation,
    defect: PersistentDefect,
) -> bool:
    if observation.track_id is None:
        return False

    return observation.track_id in defect.track_ids


def eligible_candidates(
    state: FusionState,
    observation: MappedObservation,
) -> tuple[AssociationCandidate, ...]:
    """Return all eligible candidates in frozen deterministic rank order."""

    validate_state(state)

    normalized = validate_observation(
        observation,
        config=state.config,
        inspection_id=state.inspection_id,
    )

    candidates: list[AssociationCandidate] = []

    # Do not rely on mapping/insertion order for outcome semantics.
    for defect_id in sorted(state.defects):
        defect = state.defects[defect_id]

        validate_persistent_defect(
            defect,
            config=state.config,
            inspection_id=state.inspection_id,
        )

        if defect.inspection_id != normalized.inspection_id:
            raise ValidationError(
                "cross-inspection persistent defect rejected"
            )

        if not _strict_class_match(normalized, defect):
            continue

        distance = euclidean_distance_m(
            normalized,
            defect,
        )

        if distance > state.config.association_distance_m:
            continue

        candidates.append(
            AssociationCandidate(
                defect_id=defect.defect_id,
                distance_m=distance,
                track_match=_track_match(
                    normalized,
                    defect,
                ),
            )
        )

    candidates.sort(
        key=lambda candidate: (
            not candidate.track_match,
            candidate.distance_m,
            candidate.defect_id,
        )
    )

    return tuple(candidates)


def select_candidate(
    state: FusionState,
    observation: MappedObservation,
) -> AssociationCandidate | None:
    """Select at most one persistent defect for an observation."""

    candidates = eligible_candidates(
        state,
        observation,
    )

    if not candidates:
        return None

    return candidates[0]
