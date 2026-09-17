"""Isolated adapter from P15 pure-domain output to P16 storage DTOs.

Boundary rule:
- P15 pure-domain modules do not import P16 storage models.
- This adapter is the only P15 implementation layer that imports them.
- No repository writes, SQLite behavior, Streamlit, or human-review logic
  belong here.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.defect_mapping.models import (
    FusionDecision,
    FusionResult,
    ObservationProvenance,
    PersistentDefect,
)
from src.defect_mapping.validation import (
    ValidationError,
    validate_persistent_defect,
    validate_state,
)
from src.storage.models import (
    EvidenceCreate,
    MappedDefectRecord,
)


class P15P16AdapterError(ValidationError):
    """Raised when a P15 result cannot be safely represented for P16."""


@dataclass(frozen=True, slots=True)
class P16AdaptedResult:
    """DTO bundle produced from one P15 FusionResult."""

    defect_record: MappedDefectRecord
    evidence: tuple[EvidenceCreate, ...]


def persistent_defect_to_p16_record(
    defect: PersistentDefect,
) -> MappedDefectRecord:
    """Map one validated P15 persistent defect to the real P16 DTO."""

    if not isinstance(defect, PersistentDefect):
        raise P15P16AdapterError(
            "defect must be a PersistentDefect"
        )

    # Validate against the defect's own model version without importing
    # storage behavior into the pure domain.
    from src.defect_mapping.config import FusionConfig

    config = FusionConfig(
        expected_model_version=defect.model_version
    )

    validated = validate_persistent_defect(
        defect,
        config=config,
        inspection_id=defect.inspection_id,
    )

    return MappedDefectRecord(
        defect_id=validated.defect_id,
        inspection_id=validated.inspection_id,
        track_id=validated.canonical_track_id,
        class_name=validated.class_name,
        confidence=validated.confidence,
        x_m=validated.x_m,
        y_m=validated.y_m,
        z_m=validated.z_m,
        coordinate_frame="map",
        observation_count=validated.observation_count,
        first_seen=validated.first_seen,
        last_seen=validated.last_seen,
        model_version=validated.model_version,
    )


def provenance_to_p16_evidence(
    defect_id: str,
    provenance: ObservationProvenance,
) -> EvidenceCreate:
    """Map exactly one accepted P15 observation to one P16 evidence DTO."""

    if not isinstance(defect_id, str) or not defect_id:
        raise P15P16AdapterError(
            "defect_id must be a non-empty string"
        )

    if not isinstance(provenance, ObservationProvenance):
        raise P15P16AdapterError(
            "provenance must be ObservationProvenance"
        )

    x1, y1, x2, y2 = provenance.bbox_xyxy

    return EvidenceCreate(
        defect_id=defect_id,
        frame_id=provenance.source_frame_id,
        timestamp=provenance.timestamp,
        image_path=provenance.image_path,
        crop_path=provenance.crop_path,
        confidence=provenance.confidence,
        bbox_x1=x1,
        bbox_y1=y1,
        bbox_x2=x2,
        bbox_y2=y2,
    )


def _find_result_provenance(
    result: FusionResult,
    defect: PersistentDefect,
) -> ObservationProvenance:
    matches = tuple(
        record
        for record in defect.provenance
        if record.observation_id == result.observation_id
    )

    if len(matches) != 1:
        raise P15P16AdapterError(
            "FusionResult observation must map to exactly one "
            "persistent-defect provenance record"
        )

    return matches[0]


def fusion_result_to_p16(
    result: FusionResult,
) -> P16AdaptedResult:
    """Convert one P15 result to P16 DTOs.

    CREATED / ASSOCIATED:
        one current MappedDefectRecord
        plus exactly one EvidenceCreate for the newly accepted observation.

    REPLAY:
        one current MappedDefectRecord
        plus zero new EvidenceCreate objects.
    """

    if not isinstance(result, FusionResult):
        raise P15P16AdapterError(
            "result must be a FusionResult"
        )

    state = result.new_state
    validate_state(state)

    if result.defect_id not in state.defects:
        raise P15P16AdapterError(
            "FusionResult references unknown defect_id"
        )

    defect = state.defects[result.defect_id]

    if defect.inspection_id != state.inspection_id:
        raise P15P16AdapterError(
            "P15/P16 adapter rejects cross-inspection defect"
        )

    defect_record = persistent_defect_to_p16_record(
        defect
    )

    if result.decision is FusionDecision.REPLAY:
        if result.observation_id not in state.processed_observations:
            raise P15P16AdapterError(
                "replay result references unknown processed observation"
            )

        processed = state.processed_observations[
            result.observation_id
        ]

        if processed.defect_id != result.defect_id:
            raise P15P16AdapterError(
                "replay result defect_id conflicts with processed registry"
            )

        return P16AdaptedResult(
            defect_record=defect_record,
            evidence=(),
        )

    if result.decision not in {
        FusionDecision.CREATED,
        FusionDecision.ASSOCIATED,
    }:
        raise P15P16AdapterError(
            "unsupported FusionDecision"
        )

    processed = state.processed_observations.get(
        result.observation_id
    )

    if processed is None:
        raise P15P16AdapterError(
            "accepted result is missing processed-observation registry entry"
        )

    if processed.defect_id != result.defect_id:
        raise P15P16AdapterError(
            "accepted result defect_id conflicts with processed registry"
        )

    provenance = _find_result_provenance(
        result,
        defect,
    )

    evidence = provenance_to_p16_evidence(
        defect.defect_id,
        provenance,
    )

    return P16AdaptedResult(
        defect_record=defect_record,
        evidence=(evidence,),
    )
