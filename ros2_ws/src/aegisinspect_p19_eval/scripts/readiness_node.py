#!/usr/bin/env python3
"""Collect one fail-closed P19 no-START synchronization readiness sequence."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from typing import Any

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.serialization import serialize_message
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String

from aegisinspect_p19_eval.contracts import (
    BINDING_RULE,
    ExposureReceipt,
    GT_ID,
    TARGET_LABEL,
    TARGET_LINK,
    TARGET_MODEL,
    TARGET_VISUAL,
    canonical_json_bytes,
    parse_update_attestation,
    pose_matrix,
    receipt_as_dict,
    sha256_bytes,
    startup_alignment_evidence,
    summarize_truth_labels,
    validate_manifest,
    validate_receipt,
    verify_detached_seal,
)
from aegisinspect_p19_eval.batch_certificate import (
    WINDOW_REANCHOR, camera_info_hash, certificate_hash,
    classify_certificate_window_step, operational_image_hash,
    parse_sensor_batch_certificate,
)
from aegisinspect_p19_eval.batch_telemetry import (
    parse_batch_telemetry, telemetry_bytes, validate_telemetry_progression,
)
from aegisinspect_p19_eval.telemetry import PassiveJoinTelemetry
from aegisinspect_p19_eval.diagnostic_observability import (
    CollectorDiagnosticState, diagnostic_bytes,
)


def stamp_ns(message: Any) -> int:
    return int(message.header.stamp.sec) * 1_000_000_000 + int(message.header.stamp.nanosec)


def msg_hash(message: Any) -> str:
    return sha256_bytes(bytes(serialize_message(message)))


def pose_parts(pose: Any):
    return (
        (pose.position.x, pose.position.y, pose.position.z),
        (pose.orientation.x, pose.orientation.y, pose.orientation.z, pose.orientation.w),
    )


def labels_from_image(message: Image) -> tuple[int, ...]:
    data = bytes(message.data)
    encoding = message.encoding.lower()
    if encoding in {"mono8", "8uc1"} and message.step == message.width:
        return tuple(data)
    if encoding in {"rgb8", "bgr8", "8uc3"} and message.step == message.width * 3:
        labels = []
        for offset in range(0, len(data), 3):
            pixel = data[offset:offset + 3]
            if len(pixel) != 3 or not (pixel[0] == pixel[1] == pixel[2]):
                raise ValueError("truth label pixel is not an unambiguous scalar label")
            labels.append(pixel[0])
        return tuple(labels)
    raise ValueError(f"unsupported truth encoding/step: {message.encoding}/{message.step}")


class ReadinessCollector(Node):
    def __init__(self) -> None:
        super().__init__("p19_readiness_collector")
        self.declare_parameter("output_directory", "")
        self.declare_parameter("manifest_path", "")
        self.declare_parameter("manifest_seal_path", "")
        self.output = Path(self.get_parameter("output_directory").value).resolve()
        manifest_path = Path(self.get_parameter("manifest_path").value).resolve()
        seal_path = Path(self.get_parameter("manifest_seal_path").value).resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        (self.output / "receipts").mkdir()
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        validate_manifest(manifest)
        verify_detached_seal(manifest_bytes, seal_path.read_text(encoding="utf-8"))
        shutil.copyfile(manifest_path, self.output / "PRE_START_MANIFEST.json")
        shutil.copyfile(seal_path, self.output / "PRE_START_MANIFEST.sha256")
        self.experiment_id = manifest["experiment_id"]
        self.run_id = "P19-NO-START-READINESS-002"
        self.diagnostic = CollectorDiagnosticState(self.run_id)
        self.terminal_classification = "MISSING"
        self.rgb: dict[str, Image] = {}
        self.depth: dict[str, Image] = {}
        self.info: dict[str, CameraInfo] = {}
        self.calibration_hash: str | None = None
        self.calibration_message: CameraInfo | None = None
        self.truth: dict[str, Image] = {}
        self.certificates: dict[str, Any] = {}
        self.updates: dict[int, Any] = {}
        self.gt_pose: dict[int, PoseStamped] = {}
        self.gt_frame_identity: dict[int, dict[str, Any]] = {}
        self.map_pose: dict[int, Odometry] = {}
        self.scene_identity: dict[str, Any] | None = None
        self.receipts: list[ExposureReceipt] = []
        self.seen_batches: set[str] = set()
        self.last_batch_sequence: int | None = None
        self.last_valid_index: int | None = None
        self.alignment: dict[str, Any] | None = None
        self.alignment_candidate_count = 0
        self.batch_telemetry = None
        self.failed = False
        self.telemetry = PassiveJoinTelemetry()
        self.create_subscription(Image, "/aegis/sensors/camera/image_raw", self.on_rgb, qos_profile_sensor_data)
        self.create_subscription(Image, "/aegis/perception/depth/image", self.on_depth, qos_profile_sensor_data)
        self.create_subscription(CameraInfo, "/aegis/sensors/camera/camera_info", self.on_info, qos_profile_sensor_data)
        self.create_subscription(Image, "/aegis/p19_eval/truth/labels", self.on_truth, qos_profile_sensor_data)
        self.create_subscription(String, "/aegis/p19_eval/update_attestation", self.on_update, qos_profile_sensor_data)
        self.create_subscription(String, "/aegis/p19_eval/scene_identity", self.on_scene, qos_profile_sensor_data)
        self.create_subscription(String, "/aegis/p19_eval/sensor_batch_certificate", self.on_certificate, qos_profile_sensor_data)
        self.create_subscription(String, "/aegis/p19_eval/sensor_batch_telemetry", self.on_batch_telemetry, qos_profile_sensor_data)
        self.create_subscription(String, "/aegis/p19_eval/ground_truth_frame_identity", self.on_gt_frame_identity, qos_profile_sensor_data)
        self.create_subscription(PoseStamped, "/aegis/sim/ground_truth/pose", self.on_gt_pose, qos_profile_sensor_data)
        self.create_subscription(Odometry, "/aegis/localization/vio/odom", self.on_map_pose, qos_profile_sensor_data)
        self.get_logger().info("P19 readiness collector armed; no START or inference API exists in this node")

    def trim(self, values: dict[int, Any]) -> None:
        for key in sorted(values)[:-500]:
            values.pop(key, None)

    def store_image(self, stream: str, values: dict[str, Image], message: Image) -> None:
        self.diagnostic.callback(stream)
        self.telemetry.record_seen(stream)
        values[operational_image_hash(message)] = message
        self.trim(values)
        self.try_certificates()

    def on_rgb(self, message): self.store_image("rgb", self.rgb, message)
    def on_depth(self, message): self.store_image("depth", self.depth, message)
    def on_truth(self, message): self.store_image("truth", self.truth, message)

    def on_info(self, message: CameraInfo) -> None:
        self.diagnostic.callback("camera_info")
        self.telemetry.record_seen("camera_info")
        digest = camera_info_hash(message)
        if self.calibration_hash is not None and digest != self.calibration_hash:
            self.fail("camera calibration mutated or sensor was recreated")
            return
        self.calibration_hash = digest
        self.calibration_message = message
        self.info[digest] = message
        self.trim(self.info)
        self.try_certificates()

    def on_certificate(self, message: String) -> None:
        self.diagnostic.callback("certificate")
        try:
            certificate = parse_sensor_batch_certificate(message.data)
            self.diagnostic.latest_certificate_run_id = certificate.run_id
            self.diagnostic.latest_certificate_batch_id = certificate.acquisition_batch_id
            digest = certificate_hash(certificate)
            if digest in self.certificates:
                self.diagnostic.certificate_rejected_count += 1
                self.fail("duplicate authoritative sensor-batch certificate")
                return
            self.certificates[digest] = certificate
            self.diagnostic.certificate_accepted_count += 1
            self.try_certificates()
        except Exception as exc:
            self.diagnostic.certificate_rejected_count += 1
            self.diagnostic.latest_rejection_or_blocking_predicate = str(exc)
            self.fail(f"sensor-batch certificate rejected: {exc}")

    def on_batch_telemetry(self, message: String) -> None:
        self.diagnostic.callback("telemetry")
        try:
            item = parse_batch_telemetry(message.data)
            self.diagnostic.latest_telemetry_run_id = item.run_id
            self.diagnostic.latest_telemetry_batch_id = (
                f"{item.run_id}:batch:{item.last_batch_sequence}")
            progression = [item] if self.batch_telemetry is None else [self.batch_telemetry, item]
            validate_telemetry_progression(progression, self.run_id)
            self.batch_telemetry = item
            self.finish_if_ready()
        except Exception as exc:
            self.diagnostic.latest_rejection_or_blocking_predicate = str(exc)
            self.fail(f"sensor-batch telemetry rejected: {exc}")

    def on_gt_frame_identity(self, message: String) -> None:
        try:
            value = json.loads(message.data)
            if set(value) != {"schema", "timestamp_ns", "pose_name", "source_topic"}:
                raise ValueError("ground-truth frame identity fields mismatch")
            if value["schema"] != "aegisinspect.p19.ground_truth_frame_identity.v1":
                raise ValueError("ground-truth frame identity schema mismatch")
            if (type(value["timestamp_ns"]) is not int or value["timestamp_ns"] <= 0
                    or not isinstance(value["pose_name"], str) or not value["pose_name"]
                    or value["source_topic"] != "/aegis/sim/ground_truth/pose_gz"):
                raise ValueError("invalid ground-truth frame identity")
            self.gt_frame_identity[value["timestamp_ns"]] = value
            self.try_alignment(value["timestamp_ns"])
        except Exception as exc:
            self.fail(f"ground-truth frame identity rejected: {exc}")

    def on_update(self, message: String) -> None:
        try:
            update = parse_update_attestation(message.data)
            self.telemetry.record_seen("attestation")
            self.updates[update.sim_time_ns] = update
            self.trim(self.updates)
            self.try_receipt(update.sim_time_ns)
        except Exception as exc:
            self.fail(f"update attestation rejected: {exc}")

    def on_scene(self, message: String) -> None:
        self.diagnostic.callback("scene_identity")
        try:
            value = json.loads(message.data)
            if value.get("gt_defect_id") != GT_ID:
                raise ValueError("GT ID mismatch")
            if (value.get("model"), value.get("link"), value.get("visual")) != (
                TARGET_MODEL, TARGET_LINK, TARGET_VISUAL):
                raise ValueError("target entity names mismatch")
            for key in ("model_entity", "link_entity", "visual_entity"):
                if type(value.get(key)) is not int or value[key] <= 0:
                    raise ValueError(f"invalid {key}")
            self.scene_identity = value
            self.telemetry.record_scene_identity()
            self.try_certificates()
        except Exception as exc:
            self.fail(f"scene identity rejected: {exc}")

    def on_gt_pose(self, message: PoseStamped) -> None:
        key = stamp_ns(message)
        if key > 0:
            self.gt_pose[key] = message
            self.trim(self.gt_pose)
            self.try_alignment(key)

    def on_map_pose(self, message: Odometry) -> None:
        key = stamp_ns(message)
        if key > 0:
            self.map_pose[key] = message
            self.trim(self.map_pose)
            self.try_alignment(key)

    def try_alignment(self, key: int) -> None:
        if (self.alignment is not None or key not in self.gt_pose
                or key not in self.map_pose or key not in self.gt_frame_identity):
            return
        self.diagnostic.callback("startup_alignment")
        gt = self.gt_pose[key]
        mapped = self.map_pose[key]
        gt_identity = self.gt_frame_identity[key]
        selection_index = self.alignment_candidate_count
        self.alignment_candidate_count += 1
        try:
            if gt.header.frame_id != "world" or mapped.header.frame_id != "odom" or mapped.child_frame_id != "base_link":
                raise ValueError("world/map base-frame contract mismatch")
            world_position, world_quaternion = pose_parts(gt.pose)
            map_position, map_quaternion = pose_parts(mapped.pose.pose)
            world_base = pose_matrix(world_position, world_quaternion)
            # Accepted map->odom is the identity session origin; preserve the source odom message.
            map_base = pose_matrix(map_position, map_quaternion)
            self.alignment = dict(startup_alignment_evidence(
                timestamp_ns=key,
                selection_index=selection_index,
                world_frame=gt.header.frame_id,
                world_base_frame=gt_identity["pose_name"],
                map_frame=mapped.header.frame_id,
                map_base_frame=mapped.child_frame_id,
                world_from_base=world_base,
                map_from_base=map_base,
            ))
            self.alignment.update({
                "ground_truth_frame_identity": gt_identity,
                "world_pose_message_sha256": msg_hash(gt),
                "map_odometry_message_sha256": msg_hash(mapped),
                "map_from_odom_source": "accepted identity session_map_origin",
            })
            (self.output / "startup_alignment.json").write_bytes(canonical_json_bytes(self.alignment) + b"\n")
            self.finish_if_ready()
        except Exception as exc:
            self.fail(f"startup alignment rejected: {exc}")

    def try_receipt(self, key: int) -> None:
        """Retained only for startup-alignment callers; never qualifies exposure."""
        del key

    def discard_incomplete_qualifying_window(self) -> None:
        """Discard local evidence on an authoritative relevant-streak break."""
        self.receipts.clear()
        self.telemetry.receipts_created = 0
        for path in (self.output / "receipts").glob("*.json"):
            path.unlink()

    def try_certificates(self) -> None:
        """Qualify only explicit native batch certificates and bound outputs."""
        if self.failed or len(self.receipts) >= 20 or self.scene_identity is None:
            return
        for digest, certificate in list(self.certificates.items()):
            if certificate.acquisition_batch_id in self.seen_batches:
                continue
            rgb = self.rgb.get(certificate.operational_rgb_sha256)
            depth = self.depth.get(certificate.operational_depth_sha256)
            truth = self.truth.get(certificate.operational_truth_sha256)
            info = self.calibration_message
            if any(value is None for value in (rgb, depth, truth, info)):
                continue
            try:
                if sha256_bytes(canonical_json_bytes(self.scene_identity)) != certificate.scene_identity_sha256:
                    raise ValueError("certificate scene identity mismatch")
                labels = labels_from_image(truth)
                summary = summarize_truth_labels(labels, target_label=TARGET_LABEL)
                token = "P19OBS-" + digest
                receipt = ExposureReceipt(
                    experiment_id=self.experiment_id,
                    run_id=certificate.run_id,
                    observation_token=token,
                    rgb_sensor_identity=certificate.rgbd_sensor_id,
                    truth_sensor_identity=certificate.truth_sensor_id,
                    simulation_iteration=certificate.applied_update_identity,
                    render_identity=certificate.acquisition_batch_id,
                    timestamp_ns=certificate.native_rgb_timestamp_ns,
                    frame_id=rgb.header.frame_id,
                    width=rgb.width,
                    height=rgb.height,
                    encoding=rgb.encoding,
                    step=rgb.step,
                    rgb_message_sha256=certificate.operational_rgb_sha256,
                    rgb_pixel_sha256=sha256_bytes(bytes(rgb.data)),
                    depth_message_sha256=certificate.operational_depth_sha256,
                    camera_info_sha256=self.calibration_hash,
                    truth_label_buffer_sha256=sha256_bytes(bytes(truth.data)),
                    scene_state_sha256=certificate.scene_identity_sha256,
                    gt_defect_id=certificate.gt_defect_id,
                    scene_model=certificate.scene_model,
                    scene_link=certificate.scene_link,
                    scene_visual=certificate.scene_visual,
                    binding_rule_version=certificate.binding_rule_version,
                    truth_summary=summary,
                )
                disposition = classify_certificate_window_step(
                    certificate, expected_run_id=self.run_id,
                    previous_batch_sequence=self.last_batch_sequence,
                    previous_valid_index=self.last_valid_index,
                )
                if disposition == WINDOW_REANCHOR:
                    self.discard_incomplete_qualifying_window()
                self.receipts.append(receipt)
                self.telemetry.record_receipt(certificate.batch_sequence, token)
                self.seen_batches.add(certificate.acquisition_batch_id)
                self.last_batch_sequence = certificate.batch_sequence
                self.last_valid_index = certificate.consecutive_valid_index
                destination = self.output / "receipts" / f"{len(self.receipts):04d}.json"
                destination.write_bytes(canonical_json_bytes({
                    "certificate_sha256": digest,
                    "certificate": certificate.__dict__,
                    "receipt": receipt_as_dict(receipt),
                    "truth_summary": summary.__dict__,
                }) + b"\n")
                self.get_logger().info(
                    f"eligible authoritative batch {len(self.receipts)}/20: "
                    f"{certificate.acquisition_batch_id}")
                self.finish_if_ready()
            except Exception as exc:
                self.diagnostic.latest_rejection_or_blocking_predicate = str(exc)
                self.telemetry.record_rejection(certificate.batch_sequence, str(exc))
                self.fail(f"authoritative batch rejected: {exc}")
                return

    def write_telemetry(self, outcome: str) -> None:
        path = self.output / "passive_telemetry.json"
        path.write_bytes(canonical_json_bytes(self.telemetry.snapshot(outcome)) + b"\n")

    def write_diagnostic_snapshot(self, reason: str) -> None:
        """Persist bounded evidence only; never participate in readiness decisions."""
        try:
            certificates = list(self.certificates.values())
            rgb_match = any(item.operational_rgb_sha256 in self.rgb for item in certificates)
            depth_match = any(item.operational_depth_sha256 in self.depth for item in certificates)
            telemetry = self.batch_telemetry
            snapshot = self.diagnostic.snapshot(
                reason=reason,
                terminal_classification=self.terminal_classification,
                alignment_available=self.alignment is not None,
                scene_available=self.scene_identity is not None,
                camera_info_available=self.calibration_message is not None,
                calibration_available=self.calibration_hash is not None,
                rgb_hash_match_available=rgb_match,
                depth_hash_match_available=depth_match,
                truth_available=bool(self.truth),
                certificate_available=bool(certificates),
                telemetry_available=telemetry is not None,
                persisted_receipt_count=len(self.receipts),
                current_valid_streak=(telemetry.current_consecutive_valid_streak
                                      if telemetry else 0),
                max_valid_streak=(telemetry.max_consecutive_valid_streak
                                  if telemetry else 0),
            )
            destination = self.output / "collector_runtime_diagnostic.json"
            temporary = self.output / "collector_runtime_diagnostic.json.tmp"
            temporary.write_bytes(diagnostic_bytes(snapshot) + b"\n")
            temporary.replace(destination)
        except Exception as exc:
            self.get_logger().warning(f"passive diagnostic snapshot unavailable: {exc}")

    def finish_if_ready(self) -> None:
        if len(self.receipts) == 20 and self.alignment is not None and not self.failed:
            if not self.batch_telemetry:
                return
            telemetry = self.batch_telemetry
            if (self.last_batch_sequence is None
                    or telemetry.last_batch_sequence < self.last_batch_sequence
                    or telemetry.certificate_count < len(self.receipts)
                    or telemetry.max_consecutive_valid_streak < 20):
                return
            (self.output / "authoritative_batch_telemetry.json").write_bytes(
                telemetry_bytes(telemetry) + b"\n")
            self.write_telemetry("PASS")
            result = {
                "status": "PASS",
                "eligible_pair_count": 20,
                "consecutive_valid_pair_count": 20,
                "gt_operational_use": "NO",
                "p13_start_call_count": 0,
                "reset_call_count": 0,
                "detector_inference_count": 0,
                "p15_scientific_observation_count": 0,
                "p16_ingestion_count": 0,
                "scene_identity": self.scene_identity,
            }
            (self.output / "runtime_result.json").write_bytes(canonical_json_bytes(result) + b"\n")
            self.terminal_classification = "PASS"
            self.get_logger().info("P19 no-START readiness collection complete")
            rclpy.shutdown()

    def fail(self, reason: str) -> None:
        if self.failed:
            return
        self.failed = True
        self.terminal_classification = "BLOCKED"
        self.diagnostic.latest_rejection_or_blocking_predicate = reason
        self.write_telemetry("BLOCKED")
        result = {
            "status": "BLOCKED", "reason": reason,
            "eligible_pair_count": len(self.receipts),
            "gt_operational_use": "NO",
            "p13_start_call_count": 0, "reset_call_count": 0,
            "detector_inference_count": 0,
            "p15_scientific_observation_count": 0, "p16_ingestion_count": 0,
        }
        (self.output / "runtime_result.json").write_bytes(canonical_json_bytes(result) + b"\n")
        self.get_logger().error(reason)
        rclpy.shutdown()


def main() -> None:
    rclpy.init()
    node = ReadinessCollector()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.terminal_classification = "INTERRUPTED"
        node.write_telemetry("INTERRUPTED")
        raise
    finally:
        node.write_diagnostic_snapshot("COLLECTOR_FINALIZATION")
        node.destroy_node()


if __name__ == "__main__":
    main()
