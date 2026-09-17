"""Public pure-Python P15 defect mapping domain API."""

from .aggregation import (
    AggregationError,
    aggregate_observation,
    create_persistent_defect,
)
from .association import (
    AssociationCandidate,
    eligible_candidates,
    euclidean_distance_m,
    select_candidate,
)
from .config import (
    CLASS_NAMES_BY_ID,
    DEFAULT_ASSOCIATION_DISTANCE_M,
    DEFAULT_MODEL_VERSION,
    MAP_FRAME,
    FusionConfig,
)
from .engine import (
    FusionEngineError,
    create_state,
    ingest_batch,
    ingest_observation,
)
from .identity import (
    PERSISTENT_ID_NAME_PREFIX,
    PERSISTENT_ID_NAMESPACE,
    PERSISTENT_ID_PREFIX,
    canonical_observation_bytes,
    canonical_observation_payload,
    observation_fingerprint,
    persistent_defect_id,
)
from .models import (
    FusionDecision,
    FusionResult,
    FusionState,
    MappedObservation,
    ObservationProvenance,
    PersistentDefect,
    ProcessedObservation,
)
from .replay import (
    ReplayConflictError,
    check_replay,
)
from .serialization import (
    SERIALIZATION_FORMAT,
    SERIALIZATION_VERSION,
    SerializationError,
    export_state,
    import_state,
    state_from_json,
    state_to_json,
)
from .validation import (
    ValidationError,
    validate_config,
    validate_observation,
    validate_persistent_defect,
    validate_provenance,
    validate_state,
)

__all__ = [
    "AggregationError",
    "AssociationCandidate",
    "CLASS_NAMES_BY_ID",
    "DEFAULT_ASSOCIATION_DISTANCE_M",
    "DEFAULT_MODEL_VERSION",
    "MAP_FRAME",
    "PERSISTENT_ID_NAME_PREFIX",
    "PERSISTENT_ID_NAMESPACE",
    "PERSISTENT_ID_PREFIX",
    "SERIALIZATION_FORMAT",
    "SERIALIZATION_VERSION",
    "FusionConfig",
    "FusionDecision",
    "FusionEngineError",
    "FusionResult",
    "FusionState",
    "MappedObservation",
    "ObservationProvenance",
    "PersistentDefect",
    "ProcessedObservation",
    "ReplayConflictError",
    "SerializationError",
    "ValidationError",
    "aggregate_observation",
    "canonical_observation_bytes",
    "canonical_observation_payload",
    "check_replay",
    "create_persistent_defect",
    "create_state",
    "eligible_candidates",
    "euclidean_distance_m",
    "export_state",
    "import_state",
    "ingest_batch",
    "ingest_observation",
    "observation_fingerprint",
    "persistent_defect_id",
    "select_candidate",
    "state_from_json",
    "state_to_json",
    "validate_config",
    "validate_observation",
    "validate_persistent_defect",
    "validate_provenance",
    "validate_state",
]
