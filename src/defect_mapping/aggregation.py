"""Pure immutable aggregation for P15 persistent defects.

This module operates only after an observation has been accepted as a
unique observation for a particular persistent defect.

It does not perform spatial association, replay registry mutation,
state mutation, serialization, or P16 persistence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import math

from .config import FusionConfig
from .models import (
    MappedObservation,
    ObservationProvenance,
    PersistentDefect,
)
from .validation import (
    ValidationError,
    validate_observation,
    validate_persistent_defect,
)


class AggregationError(ValidationError):
    """Raised when an aggregation operation violates the frozen contract."""


def _track_summary(
    provenance: tuple[ObservationProvenance, ...],
) -> tuple[
    str | None,
    tuple[str, ...],
    tuple[tuple[str, int], ...],
]:
    counts = Counter(
        record.track_id
        for record in provenance
        if record.track_id is not None
    )

    if not counts:
        return None, (), ()

    track_ids = tuple(sorted(counts))
    track_observation_counts = tuple(
        (track_id, counts[track_id])
        for track_id in track_ids
    )

    canonical_track_id = sorted(
        counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )[0][0]

    return (
        canonical_track_id,
        track_ids,
        track_observation_counts,
    )


def _aggregate_numeric(
    provenance: tuple[ObservationProvenance, ...],
    attribute: str,
) -> float:
    values = [
        float(getattr(record, attribute))
        for record in provenance
    ]

    result = math.fsum(values) / len(values)

    if not math.isfinite(result):
        raise AggregationError(
            f"aggregate {attribute} must be finite"
        )

    if result == 0.0:
        return 0.0

    return result


def _build_aggregate(
    *,
    defect_id: str,
    creator_observation_id: str,
    provenance: tuple[ObservationProvenance, ...],
    config: FusionConfig,
) -> PersistentDefect:
    if not provenance:
        raise AggregationError(
            "persistent defect requires at least one observation"
        )

    first = provenance[0]

    observation_ids = tuple(
        record.observation_id
        for record in provenance
    )

    if len(set(observation_ids)) != len(observation_ids):
        raise AggregationError(
            "aggregation requires unique observation IDs"
        )

    if creator_observation_id not in observation_ids:
        raise AggregationError(
            "creator observation must remain in provenance"
        )

    for record in provenance:
        if record.inspection_id != first.inspection_id:
            raise AggregationError(
                "cross-inspection aggregation is forbidden"
            )

        if (
            record.class_id != first.class_id
            or record.class_name != first.class_name
        ):
            raise AggregationError(
                "strict class conflict during aggregation"
            )

        if record.coordinate_frame != "map":
            raise AggregationError(
                'aggregate provenance frame must be exactly "map"'
            )

        if record.model_version != config.expected_model_version:
            raise AggregationError(
                "aggregate provenance model version mismatch"
            )

    (
        canonical_track_id,
        track_ids,
        track_observation_counts,
    ) = _track_summary(provenance)

    defect = PersistentDefect(
        defect_id=defect_id,
        inspection_id=first.inspection_id,
        creator_observation_id=creator_observation_id,
        class_id=first.class_id,
        class_name=first.class_name,
        confidence=_aggregate_numeric(
            provenance,
            "confidence",
        ),
        x_m=_aggregate_numeric(
            provenance,
            "x_m",
        ),
        y_m=_aggregate_numeric(
            provenance,
            "y_m",
        ),
        z_m=_aggregate_numeric(
            provenance,
            "z_m",
        ),
        coordinate_frame="map",
        observation_count=len(provenance),
        first_seen=min(
            record.timestamp
            for record in provenance
        ),
        last_seen=max(
            record.timestamp
            for record in provenance
        ),
        canonical_track_id=canonical_track_id,
        track_ids=track_ids,
        track_observation_counts=track_observation_counts,
        model_version=config.expected_model_version,
        observation_ids=observation_ids,
        provenance=provenance,
    )

    return validate_persistent_defect(
        defect,
        config=config,
        inspection_id=first.inspection_id,
    )


def create_persistent_defect(
    observation: MappedObservation,
    *,
    defect_id: str,
    config: FusionConfig,
    inspection_id: int | None = None,
) -> PersistentDefect:
    """Create one persistent defect from its unique creator observation."""

    normalized = validate_observation(
        observation,
        config=config,
        inspection_id=inspection_id,
    )

    provenance = (
        ObservationProvenance.from_observation(
            normalized
        ),
    )

    return _build_aggregate(
        defect_id=defect_id,
        creator_observation_id=normalized.observation_id,
        provenance=provenance,
        config=config,
    )


def aggregate_observation(
    defect: PersistentDefect,
    observation: MappedObservation,
    *,
    config: FusionConfig,
) -> PersistentDefect:
    """Return a new aggregate containing one additional unique observation.

    The input defect is never mutated.
    Replays are handled by the future ingestion engine before this function.
    Receiving an already-present observation ID here is therefore a
    fail-closed programming/domain error.
    """

    validated_defect = validate_persistent_defect(
        defect,
        config=config,
        inspection_id=defect.inspection_id,
    )

    normalized = validate_observation(
        observation,
        config=config,
        inspection_id=validated_defect.inspection_id,
    )

    if normalized.observation_id in validated_defect.observation_ids:
        raise AggregationError(
            "observation_id already exists in persistent defect"
        )

    if (
        normalized.class_id != validated_defect.class_id
        or normalized.class_name != validated_defect.class_name
    ):
        raise AggregationError(
            "strict class conflict during aggregation"
        )

    new_provenance = (
        validated_defect.provenance
        + (
            ObservationProvenance.from_observation(
                normalized
            ),
        )
    )

    return _build_aggregate(
        defect_id=validated_defect.defect_id,
        creator_observation_id=(
            validated_defect.creator_observation_id
        ),
        provenance=new_provenance,
        config=config,
    )
