"""Pure functional state transitions for P15 fusion."""

from __future__ import annotations

from collections.abc import Iterable

from .aggregation import (
    aggregate_observation,
    create_persistent_defect,
)
from .association import select_candidate
from .config import FusionConfig
from .identity import persistent_defect_id
from .models import (
    FusionDecision,
    FusionResult,
    FusionState,
    MappedObservation,
    ProcessedObservation,
)
from .replay import check_replay
from .validation import (
    ValidationError,
    validate_observation,
    validate_state,
)


class FusionEngineError(ValidationError):
    """Raised when a functional state transition cannot be completed safely."""


def create_state(
    inspection_id: int,
    *,
    config: FusionConfig | None = None,
) -> FusionState:
    """Create one immutable inspection-local P15 state."""

    if type(inspection_id) is not int or inspection_id < 1:
        raise FusionEngineError(
            "inspection_id must be an integer >= 1"
        )

    state = FusionState(
        inspection_id=inspection_id,
        config=config if config is not None else FusionConfig(),
    )

    return validate_state(state)


def _new_state(
    state: FusionState,
    *,
    defects: dict,
    processed_observations: dict,
) -> FusionState:
    candidate = FusionState(
        inspection_id=state.inspection_id,
        config=state.config,
        schema_version=state.schema_version,
        defects=defects,
        processed_observations=processed_observations,
    )

    return validate_state(candidate)


def ingest_observation(
    state: FusionState,
    observation: MappedObservation,
) -> FusionResult:
    """Ingest one observation with immutable/fail-closed semantics."""

    validate_state(state)

    normalized = validate_observation(
        observation,
        config=state.config,
        inspection_id=state.inspection_id,
    )

    fingerprint, prior = check_replay(
        state,
        normalized,
    )

    if prior is not None:
        return FusionResult(
            new_state=state,
            decision=FusionDecision.REPLAY,
            defect_id=prior.defect_id,
            observation_id=normalized.observation_id,
        )

    candidate = select_candidate(
        state,
        normalized,
    )

    defects = dict(state.defects)
    processed = dict(state.processed_observations)

    if candidate is None:
        defect_id = persistent_defect_id(
            state.inspection_id,
            normalized.observation_id,
        )

        if defect_id in defects:
            raise FusionEngineError(
                "generated persistent defect ID already exists"
            )

        defect = create_persistent_defect(
            normalized,
            defect_id=defect_id,
            config=state.config,
            inspection_id=state.inspection_id,
        )

        decision = FusionDecision.CREATED
    else:
        defect_id = candidate.defect_id

        if defect_id not in defects:
            raise FusionEngineError(
                "association selected unknown persistent defect"
            )

        defect = aggregate_observation(
            defects[defect_id],
            normalized,
            config=state.config,
        )

        decision = FusionDecision.ASSOCIATED

    defects[defect_id] = defect

    processed[normalized.observation_id] = ProcessedObservation(
        observation_id=normalized.observation_id,
        fingerprint=fingerprint,
        defect_id=defect_id,
    )

    next_state = _new_state(
        state,
        defects=defects,
        processed_observations=processed,
    )

    return FusionResult(
        new_state=next_state,
        decision=decision,
        defect_id=defect_id,
        observation_id=normalized.observation_id,
    )


def ingest_batch(
    state: FusionState,
    observations: Iterable[MappedObservation],
) -> tuple[FusionState, tuple[FusionResult, ...]]:
    """Apply one ordered batch atomically from the caller's perspective.

    Same initial state + same frozen config + same ordered observation
    sequence produces the same decisions and final state.

    This function deliberately does NOT claim permutation invariance.
    """

    validate_state(state)

    try:
        ordered = tuple(observations)
    except TypeError as exc:
        raise FusionEngineError(
            "observations must be iterable"
        ) from exc

    working_state = state
    results: list[FusionResult] = []

    for observation in ordered:
        result = ingest_observation(
            working_state,
            observation,
        )
        working_state = result.new_state
        results.append(result)

    return working_state, tuple(results)
