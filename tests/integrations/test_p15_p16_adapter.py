"""Phase-7 tests for the isolated P15 -> P16 DTO adapter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sys

import pytest

from src.defect_mapping import (
    FusionDecision,
    FusionResult,
    MappedObservation,
    create_state,
    ingest_observation,
)
from src.integrations.p15_p16_adapter import (
    P15P16AdapterError,
    fusion_result_to_p16,
    persistent_defect_to_p16_record,
    provenance_to_p16_evidence,
)
from src.storage.models import (
    EvidenceCreate,
    MappedDefectRecord,
)


T0 = datetime(
    2026,
    9,
    16,
    12,
    0,
    0,
    tzinfo=timezone.utc,
)


def obs(
    observation_id: str,
    *,
    x_m: float = 1.0,
    y_m: float = 2.0,
    z_m: float = 3.0,
    confidence: float = 0.9,
    track_id: str | None = None,
    timestamp: datetime = T0,
    image_path: str | None = None,
    crop_path: str | None = None,
) -> MappedObservation:
    return MappedObservation(
        inspection_id=1,
        observation_id=observation_id,
        detection_id=observation_id,
        track_id=track_id,
        class_id=0,
        class_name="Crack",
        confidence=confidence,
        x_m=x_m,
        y_m=y_m,
        z_m=z_m,
        coordinate_frame="map",
        timestamp=timestamp,
        source_frame_id="camera_optical_frame",
        bbox_xyxy=(10.0, 20.0, 110.0, 120.0),
        image_width=640,
        image_height=480,
        model_version="DET-FINAL-v1",
        image_path=image_path,
        crop_path=crop_path,
    )


def test_persistent_defect_maps_to_real_p16_record() -> None:
    result = ingest_observation(
        create_state(1),
        obs(
            "obs-1",
            track_id="track-7",
        ),
    )

    defect = result.new_state.defects[
        result.defect_id
    ]

    record = persistent_defect_to_p16_record(
        defect
    )

    assert isinstance(record, MappedDefectRecord)
    assert record.defect_id == defect.defect_id
    assert record.inspection_id == 1
    assert record.track_id == "track-7"
    assert record.class_name == "Crack"
    assert record.confidence == pytest.approx(0.9)
    assert record.x_m == pytest.approx(1.0)
    assert record.y_m == pytest.approx(2.0)
    assert record.z_m == pytest.approx(3.0)
    assert record.coordinate_frame == "map"
    assert record.observation_count == 1
    assert record.first_seen == T0
    assert record.last_seen == T0
    assert record.model_version == "DET-FINAL-v1"


def test_aggregated_record_uses_current_p15_aggregate() -> None:
    first = ingest_observation(
        create_state(1),
        obs(
            "obs-1",
            confidence=0.6,
            x_m=1.0,
            track_id="track-b",
            timestamp=T0,
        ),
    )

    second = ingest_observation(
        first.new_state,
        obs(
            "obs-2",
            confidence=1.0,
            x_m=1.2,
            track_id="track-b",
            timestamp=T0 + timedelta(seconds=10),
        ),
    )

    adapted = fusion_result_to_p16(second)
    record = adapted.defect_record

    assert record.defect_id == first.defect_id
    assert record.track_id == "track-b"
    assert record.confidence == pytest.approx(0.8)
    assert record.x_m == pytest.approx(1.1)
    assert record.observation_count == 2
    assert record.first_seen == T0
    assert record.last_seen == T0 + timedelta(seconds=10)


def test_provenance_maps_to_real_p16_evidence() -> None:
    result = ingest_observation(
        create_state(1),
        obs(
            "obs-1",
            confidence=0.75,
            image_path="frames/f1.jpg",
            crop_path="crops/f1.jpg",
        ),
    )

    defect = result.new_state.defects[
        result.defect_id
    ]

    evidence = provenance_to_p16_evidence(
        defect.defect_id,
        defect.provenance[0],
    )

    assert isinstance(evidence, EvidenceCreate)
    assert evidence.defect_id == defect.defect_id
    assert evidence.frame_id == "camera_optical_frame"
    assert evidence.timestamp == T0
    assert evidence.image_path == "frames/f1.jpg"
    assert evidence.crop_path == "crops/f1.jpg"
    assert evidence.confidence == pytest.approx(0.75)
    assert evidence.bbox_x1 == pytest.approx(10.0)
    assert evidence.bbox_y1 == pytest.approx(20.0)
    assert evidence.bbox_x2 == pytest.approx(110.0)
    assert evidence.bbox_y2 == pytest.approx(120.0)


def test_created_result_emits_exactly_one_new_evidence() -> None:
    result = ingest_observation(
        create_state(1),
        obs("obs-1"),
    )

    adapted = fusion_result_to_p16(result)

    assert result.decision is FusionDecision.CREATED
    assert len(adapted.evidence) == 1
    assert (
        adapted.evidence[0].defect_id
        == result.defect_id
    )


def test_associated_result_emits_only_new_observation_evidence() -> None:
    first = ingest_observation(
        create_state(1),
        obs("obs-1", x_m=0.0),
    )

    second = ingest_observation(
        first.new_state,
        obs(
            "obs-2",
            x_m=0.1,
            image_path="frames/obs-2.jpg",
        ),
    )

    adapted = fusion_result_to_p16(second)

    assert second.decision is FusionDecision.ASSOCIATED
    assert len(adapted.evidence) == 1

    evidence = adapted.evidence[0]

    assert evidence.image_path == "frames/obs-2.jpg"
    assert evidence.timestamp == T0
    assert evidence.defect_id == first.defect_id


def test_replay_emits_no_new_p16_evidence() -> None:
    first = ingest_observation(
        create_state(1),
        obs("obs-1"),
    )

    replay = ingest_observation(
        first.new_state,
        obs("obs-1"),
    )

    adapted = fusion_result_to_p16(replay)

    assert replay.decision is FusionDecision.REPLAY
    assert adapted.evidence == ()
    assert (
        adapted.defect_record.observation_count
        == 1
    )


def test_canonical_track_maps_to_p16_track_id() -> None:
    first = ingest_observation(
        create_state(1),
        obs(
            "obs-1",
            x_m=0.0,
            track_id="track-z",
        ),
    )

    second = ingest_observation(
        first.new_state,
        obs(
            "obs-2",
            x_m=0.05,
            track_id="track-a",
        ),
    )

    # One observation each -> frozen lexical tie-break.
    assert (
        second.new_state.defects[
            first.defect_id
        ].canonical_track_id
        == "track-a"
    )

    adapted = fusion_result_to_p16(second)

    assert adapted.defect_record.track_id == "track-a"


def test_coordinate_frame_is_exact_map() -> None:
    result = ingest_observation(
        create_state(1),
        obs("obs-1"),
    )

    adapted = fusion_result_to_p16(result)

    assert adapted.defect_record.coordinate_frame == "map"


def test_no_human_review_field_is_added_by_p15_adapter() -> None:
    result = ingest_observation(
        create_state(1),
        obs("obs-1"),
    )

    adapted = fusion_result_to_p16(result)

    assert not hasattr(
        adapted.defect_record,
        "review_status",
    )
    assert not hasattr(
        adapted.defect_record,
        "human_review",
    )


def test_adapter_rejects_unknown_result_defect() -> None:
    result = ingest_observation(
        create_state(1),
        obs("obs-1"),
    )

    invalid = replace(
        result,
        defect_id="P15D-missing",
    )

    with pytest.raises(
        P15P16AdapterError,
        match="unknown defect",
    ):
        fusion_result_to_p16(invalid)


def test_adapter_rejects_wrong_observation_for_accepted_result() -> None:
    result = ingest_observation(
        create_state(1),
        obs("obs-1"),
    )

    invalid = replace(
        result,
        observation_id="obs-missing",
    )

    with pytest.raises(P15P16AdapterError):
        fusion_result_to_p16(invalid)


def test_adapter_source_uses_only_p16_dto_boundary() -> None:
    from pathlib import Path

    source = Path(
        "src/integrations/p15_p16_adapter.py"
    ).read_text(encoding="utf-8-sig")

    assert "from src.storage.models import" in source

    forbidden_direct_dependencies = (
        "src.storage.repository",
        "src.storage.service",
        "src.storage.schema",
        "src.storage.validation",
        "sqlite3",
        "streamlit",
        "rclpy",
        "tf2_ros",
        "gazebo",
        "ultralytics",
        "torch",
    )

    for forbidden in forbidden_direct_dependencies:
        assert forbidden not in source
