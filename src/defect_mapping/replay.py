"""Idempotent replay classification for P15."""

from __future__ import annotations

from .identity import observation_fingerprint
from .models import (
    FusionState,
    MappedObservation,
    ProcessedObservation,
)
from .validation import ValidationError, validate_observation


class ReplayConflictError(ValidationError):
    """Same observation identity arrived with a conflicting payload."""


def check_replay(
    state: FusionState,
    observation: MappedObservation,
) -> tuple[str, ProcessedObservation | None]:
    """Return fingerprint and prior record, or fail on conflicting replay.

    A matching prior fingerprint is an idempotent replay.
    A different fingerprint for the same observation ID fails closed.
    """

    normalized = validate_observation(
        observation,
        config=state.config,
        inspection_id=state.inspection_id,
    )

    fingerprint = observation_fingerprint(
        normalized,
        config=state.config,
        inspection_id=state.inspection_id,
    )

    prior = state.processed_observations.get(
        normalized.observation_id
    )

    if prior is None:
        return fingerprint, None

    if prior.observation_id != normalized.observation_id:
        raise ReplayConflictError(
            "processed observation registry is inconsistent"
        )

    if prior.fingerprint != fingerprint:
        raise ReplayConflictError(
            "same observation_id arrived with conflicting payload"
        )

    return fingerprint, prior
