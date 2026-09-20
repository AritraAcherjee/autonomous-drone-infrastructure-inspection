from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from aegisinspect_p19_eval.batch_telemetry import (
    BatchTelemetryAccumulator, SensorBatchTelemetry, TELEMETRY_SCHEMA,
    parse_batch_telemetry, telemetry_bytes, telemetry_hash,
    validate_batch_telemetry, validate_telemetry_progression,
)
from aegisinspect_p19_eval.contracts import (
    ContractError, STARTUP_ALIGNMENT_EVIDENCE_SCHEMA, canonical_json_bytes,
    pose_matrix, startup_alignment_evidence, validate_rigid_se3,
    validate_startup_alignment_evidence,
)

PKG = Path(__file__).resolve().parents[1]
IDENTITY = pose_matrix((0, 0, 0), (0, 0, 0, 1))
TRANSLATED = pose_matrix((1, 2, 3), (0, 0, 0, 1))


def alignment(**changes):
    values = dict(timestamp_ns=10, selection_index=0, world_frame="world",
                  world_base_frame="base_link", map_frame="odom",
                  map_base_frame="base_link", world_from_base=IDENTITY,
                  map_from_base=TRANSLATED)
    values.update(changes)
    return startup_alignment_evidence(**values)


def test_alignment_actual_frames_and_index_serialize():
    item = alignment()
    assert item["schema"] == STARTUP_ALIGNMENT_EVIDENCE_SCHEMA
    assert (item["world_frame"], item["world_base_frame"]) == ("world", "base_link")
    assert (item["map_frame"], item["map_base_frame"]) == ("odom", "base_link")
    assert item["selection_index"] == 0


def test_alignment_selected_candidate_feeds_transform():
    item = alignment()
    assert item["map_from_world"] == TRANSLATED
    validate_startup_alignment_evidence(item)


def test_alignment_pre_motion_provenance_is_evaluable():
    item = alignment()
    assert item["timestamp_ns"] > 0 and item["selection_index"] == 0
    assert item["selection_rule"] == "first exact positive startup pair after collector readiness"
    assert item["operational_publication"] is False


@pytest.mark.parametrize("changes", [
    {"world_base_frame": "camera_link"}, {"map_base_frame": "camera_link"},
    {"world_frame": "map"}, {"map_frame": "world"},
    {"selection_index": 1}, {"selection_index": -1},
])
def test_alignment_wrong_frame_or_selection_fails(changes):
    with pytest.raises(ContractError): alignment(**changes)


@pytest.mark.parametrize("missing", ["world_base_frame", "map_base_frame", "selection_index"])
def test_alignment_missing_provenance_fails(missing):
    item = dict(alignment()); item.pop(missing)
    with pytest.raises(ContractError): validate_startup_alignment_evidence(item)


def test_alignment_tampered_selected_transform_fails():
    item = dict(alignment()); item["map_from_world"] = IDENTITY
    with pytest.raises(ContractError): validate_startup_alignment_evidence(item)


def test_alignment_serialization_is_deterministic_and_se3_unchanged():
    first = alignment(); second = alignment()
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    validate_rigid_se3(first["world_from_base"])
    validate_rigid_se3(first["map_from_base"])
    validate_rigid_se3(first["map_from_world"])


def acc(): return BatchTelemetryAccumulator("run-1")


def close_valid(value):
    return value.close(rgb_generated=True, depth_generated=True,
                       truth_generated=True, eligibility_valid=True,
                       certificate_emitted=True)


def test_total_and_non_acquisition_increment_once():
    item = acc().close(rgb_generated=False, depth_generated=False,
                       truth_generated=False, eligibility_valid=False,
                       certificate_emitted=False)
    assert item.total_manager_batches == item.non_acquisition_batches == 1
    assert item.relevant_candidate_batches == 0


def test_rgbd_only_classification():
    item = acc().close(rgb_generated=True, depth_generated=True,
                       truth_generated=False, eligibility_valid=False,
                       certificate_emitted=False)
    assert item.last_classification == "RGBD_ONLY" and item.rgbd_only == 1


def test_truth_only_classification():
    item = acc().close(rgb_generated=False, depth_generated=False,
                       truth_generated=True, eligibility_valid=False,
                       certificate_emitted=False)
    assert item.last_classification == "TRUTH_ONLY" and item.truth_only == 1


def test_both_valid_and_certificate_outcome():
    item = close_valid(acc())
    assert item.both_generated_valid == item.certificate_count == 1
    assert item.current_consecutive_valid_streak == 1


@pytest.mark.parametrize("changes", [
    {"depth_generated": False}, {"eligibility_valid": False},
    {"ambiguous_generation": True},
])
def test_both_invalid_classification(changes):
    args = dict(rgb_generated=True, depth_generated=True, truth_generated=True,
                eligibility_valid=True, certificate_emitted=False)
    args.update(changes)
    item = acc().close(**args)
    assert item.last_classification == "BOTH_GENERATED_INVALID"
    assert item.both_generated_invalid == 1 and item.certificate_count == 0


def test_partition_invariants_and_no_double_counting():
    state = acc()
    state.close(rgb_generated=False, depth_generated=False, truth_generated=False,
                eligibility_valid=False, certificate_emitted=False)
    state.close(rgb_generated=True, depth_generated=True, truth_generated=False,
                eligibility_valid=False, certificate_emitted=False)
    state.close(rgb_generated=False, depth_generated=False, truth_generated=True,
                eligibility_valid=False, certificate_emitted=False)
    final = close_valid(state)
    validate_batch_telemetry(final)
    assert final.total_manager_batches == 4
    assert final.relevant_candidate_batches == 3
    assert final.relevant_candidate_batches == sum((final.both_generated_valid,
        final.rgbd_only, final.truth_only, final.both_generated_invalid))


def test_non_acquisition_does_not_reset_streak():
    state=acc(); close_valid(state)
    item=state.close(rgb_generated=False, depth_generated=False, truth_generated=False,
                     eligibility_valid=False, certificate_emitted=False)
    assert item.current_consecutive_valid_streak == 1


@pytest.mark.parametrize("kind", ["rgbd", "truth", "invalid"])
def test_relevant_invalid_classes_reset_streak_without_resetting_totals(kind):
    state=acc(); close_valid(state)
    args={
      "rgbd": dict(rgb_generated=True,depth_generated=True,truth_generated=False),
      "truth": dict(rgb_generated=False,depth_generated=False,truth_generated=True),
      "invalid": dict(rgb_generated=True,depth_generated=True,truth_generated=True),
    }[kind]
    item=state.close(**args, eligibility_valid=False, certificate_emitted=False)
    assert item.current_consecutive_valid_streak == 0
    assert item.total_manager_batches == 2 and item.relevant_candidate_batches >= 1


def test_max_streak_retained_after_reset_and_valid_increments():
    state=acc(); close_valid(state); close_valid(state)
    item=state.close(rgb_generated=True,depth_generated=True,truth_generated=False,
                     eligibility_valid=False,certificate_emitted=False)
    assert item.current_consecutive_valid_streak == 0 and item.max_consecutive_valid_streak == 2


def test_run_initialization_is_zero_and_independent():
    first, second = acc(), acc()
    assert first.counts == second.counts and all(value == 0 for value in first.counts.values())
    close_valid(first)
    assert second.counts["total_manager_batches"] == 0


def test_stale_or_wrong_run_id_rejected():
    first=close_valid(acc())
    with pytest.raises(ContractError): validate_telemetry_progression([first], "other")
    with pytest.raises(ContractError): validate_telemetry_progression([first, first], "run-1")


def test_duplicate_ambiguous_and_invalid_lifecycle_fail_closed():
    item=acc().close(rgb_generated=True,depth_generated=True,truth_generated=True,
                     eligibility_valid=True,certificate_emitted=False,
                     ambiguous_generation=True)
    assert item.last_classification == "BOTH_GENERATED_INVALID"
    with pytest.raises(ContractError):
        acc().close(rgb_generated=False,depth_generated=False,truth_generated=False,
                    eligibility_valid=False,certificate_emitted=False,lifecycle_valid=False)


def test_certificate_count_requires_actual_emission():
    with pytest.raises(ContractError):
        acc().close(rgb_generated=True,depth_generated=True,truth_generated=True,
                    eligibility_valid=False,certificate_emitted=True)


def test_missing_telemetry_prevents_readiness_pass():
    collector=(PKG/"scripts/readiness_node.py").read_text()
    assert "if not self.batch_telemetry:" in collector
    assert "return" in collector[collector.index("if not self.batch_telemetry:"):]


def test_no_timestamp_or_proximity_telemetry_inference():
    sources=(PKG/"aegisinspect_p19_eval/batch_telemetry.py").read_text().lower()
    for forbidden in ("nearest timestamp", "tolerance_ns", "approximatetime"):
        assert forbidden not in sources


def test_deterministic_telemetry_serialization():
    item=close_valid(acc())
    assert telemetry_bytes(item)==telemetry_bytes(item)
    assert telemetry_hash(item)==telemetry_hash(item)
    assert parse_batch_telemetry(telemetry_bytes(item).decode()) == item


@pytest.mark.parametrize("changes", [
    {"schema":"wrong"}, {"run_id":""}, {"total_manager_batches":-1},
    {"relevant_candidate_batches":2}, {"certificate_count":0},
    {"accounting_valid":False}, {"last_classification":"UNKNOWN"},
])
def test_malformed_telemetry_rejected(changes):
    item=replace(close_valid(acc()), **changes)
    with pytest.raises(ContractError): validate_batch_telemetry(item)


def test_native_interface_is_dedicated_and_certificate_v1_unchanged():
    native=(PKG/"src/sensor_batch_certificate.cpp").read_text()
    bridge=(PKG/"config/sensor_batch_bridge.yaml").read_text()
    assert "aegisinspect.p19.sensor_batch_certificate.v1" in native
    assert "aegisinspect.p19.sensor_batch_telemetry.v1" in native
    assert "/aegis/p19_eval/sensor_batch_telemetry" in native and "sensor_batch_telemetry" in bridge


def test_native_run_initializes_once_at_batch_open_and_counts_publish_outcome():
    native=(PKG/"src/sensor_batch_certificate.cpp").read_text()
    open_body=native[native.index('extern "C" void p19_batch_open'):native.index('extern "C" void p19_batch_close')]
    assert "telemetry.initialized" in open_body and "telemetry.runId = run" in open_body
    assert native.count("telemetry.initialized = true") == 1
    assert "certificateEmitted = publisher.Publish(msg)" in native
    assert "++telemetry.certificates" in native


def test_gt_frame_identity_originates_from_native_pose_name():
    attestor=(PKG/"src/update_attestor.cpp").read_text()
    collector=(PKG/"scripts/readiness_node.py").read_text()
    assert "_message.name()" in attestor
    assert 'world_base_frame=gt_identity["pose_name"]' in collector
    assert 'map_base_frame=mapped.child_frame_id' in collector
