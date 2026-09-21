from dataclasses import replace
from pathlib import Path

import pytest

from aegisinspect_p19_eval.contracts import (
    ContractError, GT_ID, TARGET_CLASS, TARGET_LINK, TARGET_MODEL, TARGET_VISUAL,
)
from aegisinspect_p19_eval.batch_certificate import (
    BATCH_RULE, CERTIFICATE_SCHEMA, WINDOW_ANCHOR, WINDOW_CONTINUE,
    WINDOW_REANCHOR, SensorBatchCertificate, certificate_hash,
    classify_certificate_window_step, validate_certificate_sequence,
    validate_sensor_batch_certificate,
)

HASH_A = "a" * 64
HASH_B = "b" * 64
PKG = Path(__file__).resolve().parents[1]


def certificate(**changes):
    values = dict(
        schema=CERTIFICATE_SCHEMA, run_id="run", acquisition_batch_id="run:batch:7",
        batch_sequence=7, consecutive_valid_index=1, applied_update_identity=100,
        applied_sim_time_ns=1_000_000, rgbd_sensor_id="camera:1",
        truth_sensor_id="p19_truth_camera:2", native_rgb_sha256=HASH_A,
        operational_rgb_sha256=HASH_B, native_depth_sha256=HASH_A,
        operational_depth_sha256=HASH_B, truth_label_map_sha256=HASH_A,
        operational_truth_sha256=HASH_B, native_rgb_timestamp_ns=1,
        native_depth_timestamp_ns=2, native_truth_timestamp_ns=3,
        rgb_width=640, rgb_height=480, rgb_step=1920, rgb_encoding="RGB_INT8",
        depth_width=640, depth_height=480, depth_step=2560,
        depth_encoding="R_FLOAT32", truth_width=640, truth_height=480,
        truth_step=1920, truth_encoding="RGB_INT8_LABEL_MAP",
        calibration_sha256=HASH_A, scene_identity_sha256=HASH_B,
        gt_defect_id=GT_ID, target_class=TARGET_CLASS, scene_model=TARGET_MODEL,
        scene_link=TARGET_LINK, scene_visual=TARGET_VISUAL,
        batch_open_provenance="SensorsPrivate::RunOnce:manager-runonce-open",
        batch_close_provenance="SensorsPrivate::RunOnce:manager-runonce-return",
        instrumentation_identity="p19-batch-hooks-v1", binding_rule_version=BATCH_RULE,
    )
    values.update(changes)
    return SensorBatchCertificate(**values)


def test_valid_certificate_and_deterministic_hash():
    item = certificate()
    validate_sensor_batch_certificate(item)
    assert certificate_hash(item) == certificate_hash(item)


@pytest.mark.parametrize("changes", [
    {"schema": "wrong"}, {"run_id": ""}, {"batch_sequence": 0},
    {"consecutive_valid_index": 0}, {"applied_update_identity": 0},
    {"applied_sim_time_ns": 0}, {"acquisition_batch_id": "run:batch:8"},
    {"native_rgb_sha256": "bad"}, {"operational_rgb_sha256": "bad"},
    {"native_depth_sha256": "bad"}, {"operational_depth_sha256": "bad"},
    {"truth_label_map_sha256": "bad"}, {"operational_truth_sha256": "bad"},
    {"calibration_sha256": "bad"}, {"scene_identity_sha256": "bad"},
    {"native_rgb_timestamp_ns": 0}, {"native_depth_timestamp_ns": 0},
    {"native_truth_timestamp_ns": 0}, {"rgb_width": 1}, {"rgb_encoding": "BGR"},
    {"depth_step": 1}, {"truth_encoding": "mono8"},
    {"gt_defect_id": "other"}, {"target_class": "Crack"},
    {"scene_model": "other"}, {"scene_link": "other"},
    {"scene_visual": "other"}, {"batch_open_provenance": "timestamp-open"},
    {"batch_close_provenance": "timestamp-close"},
    {"binding_rule_version": "nearest-time"},
])
def test_malformed_certificate_fails_closed(changes):
    with pytest.raises(ContractError):
        validate_sensor_batch_certificate(certificate(**changes))


def test_different_timestamps_in_one_batch_are_valid():
    validate_sensor_batch_certificate(certificate(
        native_rgb_timestamp_ns=10, native_depth_timestamp_ns=20,
        native_truth_timestamp_ns=30))


def test_identical_timestamps_do_not_override_batch_identity():
    first = certificate(native_rgb_timestamp_ns=1, native_depth_timestamp_ns=1,
                        native_truth_timestamp_ns=1)
    second = replace(first, acquisition_batch_id="run:batch:8", batch_sequence=8,
                     consecutive_valid_index=2)
    validate_certificate_sequence([first, second] + [
        replace(first, acquisition_batch_id=f"run:batch:{index}",
                batch_sequence=index, consecutive_valid_index=index - 6)
        for index in range(9, 27)
    ])


def test_nonconsecutive_valid_index_rejected():
    values = [replace(certificate(), acquisition_batch_id=f"run:batch:{index}",
                      batch_sequence=index, consecutive_valid_index=index - 6)
              for index in range(7, 27)]
    values[10] = replace(values[10], consecutive_valid_index=99)
    with pytest.raises(ContractError):
        validate_certificate_sequence(values)


def certificate_window(first_valid=103, batches=None):
    if batches is None:
        batches = [3348 + index * 31 for index in range(20)]
    return [
        certificate(
            acquisition_batch_id=f"run:batch:{batch}",
            batch_sequence=batch,
            consecutive_valid_index=first_valid + index,
        )
        for index, batch in enumerate(batches)
    ]


def test_historical_first_local_valid_index_103_is_an_anchor():
    item = certificate_window()[0]
    assert classify_certificate_window_step(
        item, expected_run_id="run", previous_batch_sequence=None,
        previous_valid_index=None,
    ) == WINDOW_ANCHOR


@pytest.mark.parametrize("first_valid", [1, 103])
def test_twenty_certificate_window_can_start_at_any_positive_index(first_valid):
    validate_certificate_sequence(certificate_window(first_valid=first_valid))


def test_raw_manager_batch_gaps_are_valid_for_relevant_window():
    values = certificate_window(
        batches=[3348, 3381, 3410] + [3500 + index * 17 for index in range(17)]
    )
    validate_certificate_sequence(values)


def test_exact_valid_progression_continues_local_window():
    first, second = certificate_window()[:2]
    assert classify_certificate_window_step(
        second, expected_run_id="run",
        previous_batch_sequence=first.batch_sequence,
        previous_valid_index=first.consecutive_valid_index,
    ) == WINDOW_CONTINUE


@pytest.mark.parametrize("next_index", [1, 105])
def test_restart_or_forward_gap_reanchors_without_joining_windows(next_index):
    first = certificate_window()[0]
    later = certificate(
        acquisition_batch_id="run:batch:4000", batch_sequence=4000,
        consecutive_valid_index=next_index,
    )
    assert classify_certificate_window_step(
        later, expected_run_id="run",
        previous_batch_sequence=first.batch_sequence,
        previous_valid_index=first.consecutive_valid_index,
    ) == WINDOW_REANCHOR


@pytest.mark.parametrize("next_index", [103, 102])
def test_duplicate_or_decreasing_valid_index_is_rejected(next_index):
    first = certificate_window()[0]
    later = certificate(
        acquisition_batch_id="run:batch:4000", batch_sequence=4000,
        consecutive_valid_index=next_index,
    )
    with pytest.raises(ContractError):
        classify_certificate_window_step(
            later, expected_run_id="run",
            previous_batch_sequence=first.batch_sequence,
            previous_valid_index=first.consecutive_valid_index,
        )


@pytest.mark.parametrize("next_batch", [3348, 3300])
def test_duplicate_or_decreasing_raw_batch_is_rejected(next_batch):
    first = certificate_window()[0]
    later = certificate(
        acquisition_batch_id=f"run:batch:{next_batch}", batch_sequence=next_batch,
        consecutive_valid_index=104,
    )
    with pytest.raises(ContractError):
        classify_certificate_window_step(
            later, expected_run_id="run",
            previous_batch_sequence=first.batch_sequence,
            previous_valid_index=first.consecutive_valid_index,
        )


def test_cross_run_certificate_is_rejected():
    item = certificate(
        run_id="other", acquisition_batch_id="other:batch:3348",
        batch_sequence=3348, consecutive_valid_index=103,
    )
    with pytest.raises(ContractError):
        classify_certificate_window_step(
            item, expected_run_id="run", previous_batch_sequence=None,
            previous_valid_index=None,
        )


@pytest.mark.parametrize("indices", [
    [103, 105] + list(range(106, 124)),
    [103, 103] + list(range(104, 122)),
    [103, 102] + list(range(103, 121)),
])
def test_helper_rejects_broken_relevant_valid_window(indices):
    batches = [3348 + index * 31 for index in range(20)]
    values = [
        certificate(
            acquisition_batch_id=f"run:batch:{batch}", batch_sequence=batch,
            consecutive_valid_index=valid_index,
        )
        for batch, valid_index in zip(batches, indices)
    ]
    with pytest.raises(ContractError):
        validate_certificate_sequence(values)


def test_collector_discards_incomplete_window_before_reanchor():
    source = (PKG / "scripts/readiness_node.py").read_text()
    discard = source[source.index("def discard_incomplete_qualifying_window"):
                     source.index("def try_certificates")]
    qualify = source[source.index("def try_certificates"):
                     source.index("def write_telemetry")]
    assert "self.receipts.clear()" in discard
    assert 'glob("*.json")' in discard and "path.unlink()" in discard
    assert "if disposition == WINDOW_REANCHOR" in qualify
    assert (qualify.index("self.discard_incomplete_qualifying_window()")
            < qualify.index("self.receipts.append(receipt)"))
    assert "self.seen_batches.clear()" not in discard


def test_postrender_has_no_certificate_api_role():
    source = (PKG / "src/sensor_batch_certificate.cpp").read_text()
    assert "PostRender" not in source
    assert "p19_batch_open" in source and "p19_batch_close" in source


def test_no_timestamp_proximity_or_extra_render_logic():
    sources = "\n".join(path.read_text() for path in [
        PKG / "src/sensor_batch_certificate.cpp",
        PKG / "scripts/readiness_node.py",
        PKG / "gazebo_patch/gz-sim-10.5.0-sensor-batch.patch",
        PKG / "gazebo_patch/gz-sensors-10.0.2-generation-membership.patch",
    ]).lower()
    for forbidden in ("approximatetimesynchronizer", "nearest timestamp", "tolerance_ns"):
        assert forbidden not in sources
    patch = (PKG / "gazebo_patch/gz-sim-10.5.0-sensor-batch.patch").read_text()
    # The zero-context provenance diff must not add another manager invocation.
    assert patch.count("+      this->sensorManager.RunOnce") == 0
    assert "+      this->sensorManager.RunOnce" not in patch


def test_generation_hooks_are_after_final_message_data_creation():
    patch = (PKG / "gazebo_patch/gz-sensors-10.0.2-generation-membership.patch").read_text()
    assert "p19_record_rgb" in patch
    assert "p19_record_depth" in patch
    assert "p19_record_truth" in patch
    assert "p19_record_calibration" in patch


def test_twenty_certificate_gate_is_unchanged():
    source = (PKG / "scripts/readiness_node.py").read_text()
    assert "len(self.receipts) >= 20" in source
    assert "len(self.receipts) == 20" in source


def test_timestamp_maps_cannot_qualify_exposure():
    source = (PKG / "scripts/readiness_node.py").read_text()
    body = source[source.index("def try_receipt"):source.index("def try_certificates")]
    assert "del key" in body
    assert "self.receipts.append" not in body
