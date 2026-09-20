"""Fail-closed authoritative Gazebo sensor-batch certificate contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Mapping, Sequence

from .contracts import (
    ContractError, GT_ID, TARGET_CLASS, TARGET_LINK, TARGET_MODEL, TARGET_VISUAL,
    canonical_json_bytes, require_sha256, require_text, sha256_bytes,
)

CERTIFICATE_SCHEMA = "aegisinspect.p19.sensor_batch_certificate.v1"
BATCH_RULE = "gz-sim-10.5.0-sensors-manager-runonce-membership-v1"


@dataclass(frozen=True)
class SensorBatchCertificate:
    schema: str
    run_id: str
    acquisition_batch_id: str
    batch_sequence: int
    consecutive_valid_index: int
    applied_update_identity: int
    applied_sim_time_ns: int
    rgbd_sensor_id: str
    truth_sensor_id: str
    native_rgb_sha256: str
    operational_rgb_sha256: str
    native_depth_sha256: str
    operational_depth_sha256: str
    truth_label_map_sha256: str
    operational_truth_sha256: str
    native_rgb_timestamp_ns: int
    native_depth_timestamp_ns: int
    native_truth_timestamp_ns: int
    rgb_width: int
    rgb_height: int
    rgb_step: int
    rgb_encoding: str
    depth_width: int
    depth_height: int
    depth_step: int
    depth_encoding: str
    truth_width: int
    truth_height: int
    truth_step: int
    truth_encoding: str
    calibration_sha256: str
    scene_identity_sha256: str
    gt_defect_id: str
    target_class: str
    scene_model: str
    scene_link: str
    scene_visual: str
    batch_open_provenance: str
    batch_close_provenance: str
    instrumentation_identity: str
    binding_rule_version: str


def parse_sensor_batch_certificate(text: str) -> SensorBatchCertificate:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContractError("invalid sensor-batch certificate JSON") from exc
    if set(value) != set(SensorBatchCertificate.__dataclass_fields__):
        raise ContractError("sensor-batch certificate fields mismatch")
    certificate = SensorBatchCertificate(**value)
    validate_sensor_batch_certificate(certificate)
    return certificate


def validate_sensor_batch_certificate(certificate: SensorBatchCertificate) -> None:
    if certificate.schema != CERTIFICATE_SCHEMA:
        raise ContractError("sensor-batch certificate schema mismatch")
    for name in (
        "run_id", "acquisition_batch_id", "rgbd_sensor_id", "truth_sensor_id",
        "rgb_encoding", "depth_encoding", "truth_encoding",
        "batch_open_provenance", "batch_close_provenance",
        "instrumentation_identity", "binding_rule_version",
    ):
        require_text(getattr(certificate, name), name)
    if type(certificate.batch_sequence) is not int or certificate.batch_sequence < 1:
        raise ContractError("invalid batch sequence")
    if type(certificate.consecutive_valid_index) is not int or certificate.consecutive_valid_index < 1:
        raise ContractError("invalid consecutive valid index")
    if type(certificate.applied_update_identity) is not int or certificate.applied_update_identity < 1:
        raise ContractError("invalid applied update identity")
    if type(certificate.applied_sim_time_ns) is not int or certificate.applied_sim_time_ns <= 0:
        raise ContractError("invalid applied simulation time")
    if certificate.acquisition_batch_id != f"{certificate.run_id}:batch:{certificate.batch_sequence}":
        raise ContractError("batch identifier is not owned by its run sequence")
    for name in (
        "native_rgb_sha256", "operational_rgb_sha256", "native_depth_sha256",
        "operational_depth_sha256", "truth_label_map_sha256",
        "operational_truth_sha256", "calibration_sha256", "scene_identity_sha256",
    ):
        require_sha256(getattr(certificate, name), name)
    for name in ("native_rgb_timestamp_ns", "native_depth_timestamp_ns", "native_truth_timestamp_ns"):
        if type(getattr(certificate, name)) is not int or getattr(certificate, name) <= 0:
            raise ContractError(f"invalid {name}")
    if (certificate.rgb_width, certificate.rgb_height, certificate.rgb_step,
            certificate.rgb_encoding) != (640, 480, 1920, "RGB_INT8"):
        raise ContractError("unexpected certified RGB layout")
    if (certificate.depth_width, certificate.depth_height, certificate.depth_step,
            certificate.depth_encoding) != (640, 480, 2560, "R_FLOAT32"):
        raise ContractError("unexpected certified depth layout")
    if (certificate.truth_width, certificate.truth_height, certificate.truth_step,
            certificate.truth_encoding) != (640, 480, 1920, "RGB_INT8_LABEL_MAP"):
        raise ContractError("unexpected certified truth layout")
    if certificate.gt_defect_id != GT_ID or certificate.target_class != TARGET_CLASS:
        raise ContractError("certificate GT identity mismatch")
    if (certificate.scene_model, certificate.scene_link, certificate.scene_visual) != (
            TARGET_MODEL, TARGET_LINK, TARGET_VISUAL):
        raise ContractError("certificate scene identity mismatch")
    if certificate.binding_rule_version != BATCH_RULE:
        raise ContractError("certificate binding rule mismatch")
    if "manager-runonce-open" not in certificate.batch_open_provenance:
        raise ContractError("batch open provenance is not authoritative")
    if "manager-runonce-return" not in certificate.batch_close_provenance:
        raise ContractError("batch close provenance is not authoritative")


def certificate_hash(certificate: SensorBatchCertificate) -> str:
    validate_sensor_batch_certificate(certificate)
    return sha256_bytes(canonical_json_bytes(asdict(certificate)))


def camera_info_provenance(message: Any) -> Mapping[str, Any]:
    return {
        "sensor_identity": "aegis_drone::base_link::camera",
        "frame_id": str(message.header.frame_id), "width": int(message.width),
        "height": int(message.height), "distortion_model": str(message.distortion_model),
        "d": [float(v) for v in message.d], "k": [float(v) for v in message.k],
        "r": [float(v) for v in message.r], "p": [float(v) for v in message.p],
        "binning_x": int(message.binning_x), "binning_y": int(message.binning_y),
        "roi": {"x_offset": int(message.roi.x_offset), "y_offset": int(message.roi.y_offset),
                "height": int(message.roi.height), "width": int(message.roi.width),
                "do_rectify": bool(message.roi.do_rectify)},
    }


def camera_info_hash(message: Any) -> str:
    return sha256_bytes(canonical_json_bytes(camera_info_provenance(message)))


def operational_image_hash(message: Any) -> str:
    record = {
        "stamp_ns": int(message.header.stamp.sec) * 1_000_000_000 + int(message.header.stamp.nanosec),
        "frame_id": str(message.header.frame_id), "width": int(message.width),
        "height": int(message.height), "encoding": str(message.encoding),
        "is_bigendian": int(message.is_bigendian), "step": int(message.step),
        "data_sha256": sha256_bytes(bytes(message.data)),
    }
    return sha256_bytes(canonical_json_bytes(record))


def validate_certificate_sequence(certificates: Sequence[SensorBatchCertificate]) -> None:
    if len(certificates) < 20:
        raise ContractError("fewer than 20 authoritative sensor-batch certificates")
    previous_batch = previous_valid = 0
    run_id = certificates[0].run_id
    for certificate in certificates:
        validate_sensor_batch_certificate(certificate)
        if (certificate.run_id != run_id or certificate.batch_sequence <= previous_batch
                or certificate.consecutive_valid_index != previous_valid + 1):
            raise ContractError("certified batches are not consecutive")
        previous_batch = certificate.batch_sequence
        previous_valid = certificate.consecutive_valid_index
