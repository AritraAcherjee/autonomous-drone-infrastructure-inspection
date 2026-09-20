from dataclasses import replace
import json
import math

import pytest

from aegisinspect_p19_eval.contracts import *


HASH = "0" * 64


def target():
    return {
        "gt_defect_id": GT_ID, "target_class": TARGET_CLASS,
        "coordinate_frame": "world", "scene_model": TARGET_MODEL,
        "scene_link": TARGET_LINK, "scene_visual": TARGET_VISUAL,
        "coordinate_convention": "center of authored front target surface",
        "x_m": 3.0, "y_m": 0.0, "z_m": 1.5,
    }


def receipt():
    return ExposureReceipt(
        "exp", "run", "token", "rgb", "truth", 42, "gz-post-render-7-update-42",
        100, "camera_optical_frame", 640, 480, "rgb8", 1920,
        HASH, HASH, HASH, HASH, HASH, HASH, GT_ID, TARGET_MODEL, TARGET_LINK,
        TARGET_VISUAL, BINDING_RULE, TruthSummary(307200, 307200, 0, 0, 0))


def test_frozen_target_and_unique_gt_id():
    validate_target_record(target())
    assert validate_unique_ids([GT_ID], "gt_defect_id") == (GT_ID,)


@pytest.mark.parametrize("field,value", [("target_class", "Crack"), ("x_m", math.nan), ("x_m", 3.1)])
def test_target_mutation_rejected(field, value):
    value_record = target(); value_record[field] = value
    with pytest.raises(ContractError): validate_target_record(value_record)


def test_duplicate_gt_and_estimate_ids_rejected():
    with pytest.raises(ContractError): validate_unique_ids([GT_ID, GT_ID], "gt_defect_id")
    with pytest.raises(ContractError): validate_unique_ids(["P15D-a", "P15D-a"], "estimated_defect_id")


def test_asset_hash_and_detached_manifest_mutation():
    require_sha256(HASH, "asset")
    payload = b'{"frozen":true}\n'; seal = sha256_bytes(payload)
    verify_detached_seal(payload, seal)
    with pytest.raises(ContractError): verify_detached_seal(payload + b" ", seal)


def test_truth_full_frame_and_ambiguities():
    assert summarize_truth_labels([TARGET_LABEL] * 8).target_pixels == 8
    for values in ([TARGET_LABEL, 0], [TARGET_LABEL, 20], []):
        with pytest.raises(ContractError): summarize_truth_labels(values)


def test_update_and_receipt_identity():
    update = UpdateAttestation(42, 100, False, 7, "gz::sim::events::PostRender")
    validate_receipt(receipt(), update)
    for changed in (
        replace(receipt(), simulation_iteration=43),
        replace(receipt(), timestamp_ns=101),
        replace(receipt(), gt_defect_id="other"),
        replace(receipt(), truth_summary=TruthSummary(1, 0, 1, 0, 0)),
    ):
        with pytest.raises(ContractError): validate_receipt(changed, update)


def test_attestation_serialization_is_deterministic_and_fail_closed():
    raw = '{"iteration":42,"paused":false,"render_event":7,"render_event_type":"gz::sim::events::PostRender","sim_time_ns":100}'
    assert parse_update_attestation(raw) == UpdateAttestation(42, 100, False, 7, "gz::sim::events::PostRender")
    assert canonical_json_bytes(json.loads(raw)) == canonical_json_bytes(json.loads(raw))
    for invalid in ('{}', '{"iteration":42,"paused":false,"sim_time_ns":0}',
                    '{"iteration":42,"paused":true,"sim_time_ns":100}',
                    '{"iteration":42,"paused":false,"render_event":7,"render_event_type":"synthetic","sim_time_ns":100}'):
        with pytest.raises(ContractError): parse_update_attestation(invalid)


def test_consecutive_receipts_reject_duplicate_or_short_sequence():
    values = [replace(receipt(), observation_token=f"t{i}", timestamp_ns=100+i,
                      simulation_iteration=42+i,
                      render_identity=f"gz-post-render-7-update-{42+i}")
              for i in range(20)]
    validate_consecutive_receipts(values)
    with pytest.raises(ContractError): validate_consecutive_receipts(values[:19])
    with pytest.raises(ContractError): validate_consecutive_receipts(values[:-1] + [values[-2]])


def test_explicit_correspondence_preserves_identity_only():
    args = dict(p15_defect_id="P15D-a", creator_observation_id="d1",
                detection_id="d1", inference_detection_id="d1",
                inference_observation_token="t1", certificate_observation_token="t1",
                gt_defect_id=GT_ID, estimated_class=TARGET_CLASS, gt_class=TARGET_CLASS,
                detection_count=1, contributing_observation_ids=["d1"])
    assert explicit_correspondence(**args) == {"estimated_defect_id": "P15D-a", "gt_defect_id": GT_ID}
    for key, value in (("detection_count", 0), ("detection_count", 2),
                       ("estimated_class", "Crack"),
                       ("certificate_observation_token", "other"),
                       ("contributing_observation_ids", ["d1", "d2"])):
        changed = dict(args); changed[key] = value
        with pytest.raises(ContractError): explicit_correspondence(**changed)
    with pytest.raises(ContractError): explicit_correspondence(**args, x_m=3.0)


def test_startup_alignment_identity_and_first_pair_rule():
    identity = pose_matrix((0, 0, 0), (0, 0, 0, 1))
    result = startup_alignment(timestamp_ns=1, world_base_frame="base_link",
                               map_base_frame="base_link", world_from_base=identity,
                               map_from_base=identity, selection_index=0)
    validate_rigid_se3(result)
    assert determinant3([row[:3] for row in result[:3]]) == pytest.approx(1.0)
    for changes in ({"timestamp_ns": 0}, {"selection_index": 1}, {"map_base_frame": "camera"}):
        args = dict(timestamp_ns=1, world_base_frame="base_link", map_base_frame="base_link",
                    world_from_base=identity, map_from_base=identity, selection_index=0)
        args.update(changes)
        with pytest.raises(ContractError): startup_alignment(**args)


def test_nonrigid_transforms_rejected():
    invalid = ((2,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1))
    with pytest.raises(ContractError): validate_rigid_se3(invalid)
    reflected = ((-1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1))
    with pytest.raises(ContractError): validate_rigid_se3(reflected)


def test_locked_data_reference_rejected():
    reject_locked_data_references({"asset": "project-authored.png"})
    for value in ({"asset": "GYU-DET-TEST/x.png"}, {"asset": "CODEBRIM/x.jpg"}):
        with pytest.raises(ContractError): reject_locked_data_references(value)
