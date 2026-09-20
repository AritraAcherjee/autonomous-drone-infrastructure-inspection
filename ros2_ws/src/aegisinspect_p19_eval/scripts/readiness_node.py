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
    startup_alignment,
    summarize_truth_labels,
    validate_manifest,
    validate_receipt,
    verify_detached_seal,
)
from aegisinspect_p19_eval.telemetry import PassiveJoinTelemetry


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
        self.run_id = "P19-NO-START-READINESS-001"
        self.rgb: dict[int, Image] = {}
        self.depth: dict[int, Image] = {}
        self.info: dict[int, CameraInfo] = {}
        self.truth: dict[int, Image] = {}
        self.updates: dict[int, Any] = {}
        self.gt_pose: dict[int, PoseStamped] = {}
        self.map_pose: dict[int, Odometry] = {}
        self.scene_identity: dict[str, Any] | None = None
        self.receipts: list[ExposureReceipt] = []
        self.seen_stamps: set[int] = set()
        self.alignment: dict[str, Any] | None = None
        self.failed = False
        self.telemetry = PassiveJoinTelemetry()
        self.create_subscription(Image, "/aegis/sensors/camera/image_raw", self.on_rgb, qos_profile_sensor_data)
        self.create_subscription(Image, "/aegis/perception/depth/image", self.on_depth, qos_profile_sensor_data)
        self.create_subscription(CameraInfo, "/aegis/sensors/camera/camera_info", self.on_info, qos_profile_sensor_data)
        self.create_subscription(Image, "/aegis/p19_eval/truth/labels", self.on_truth, qos_profile_sensor_data)
        self.create_subscription(String, "/aegis/p19_eval/update_attestation", self.on_update, qos_profile_sensor_data)
        self.create_subscription(String, "/aegis/p19_eval/scene_identity", self.on_scene, qos_profile_sensor_data)
        self.create_subscription(PoseStamped, "/aegis/sim/ground_truth/pose", self.on_gt_pose, qos_profile_sensor_data)
        self.create_subscription(Odometry, "/aegis/localization/vio/odom", self.on_map_pose, qos_profile_sensor_data)
        self.get_logger().info("P19 readiness collector armed; no START or inference API exists in this node")

    def trim(self, values: dict[int, Any]) -> None:
        for key in sorted(values)[:-500]:
            values.pop(key, None)

    def store(self, stream: str, values: dict[int, Any], message: Any) -> None:
        key = stamp_ns(message)
        if key > 0:
            self.telemetry.record_seen(stream)
            values[key] = message
            self.trim(values)
            self.try_receipt(key)

    def on_rgb(self, message): self.store("rgb", self.rgb, message)
    def on_depth(self, message): self.store("depth", self.depth, message)
    def on_info(self, message): self.store("camera_info", self.info, message)
    def on_truth(self, message): self.store("truth", self.truth, message)

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
        if self.alignment is not None or key not in self.gt_pose or key not in self.map_pose:
            return
        gt = self.gt_pose[key]
        mapped = self.map_pose[key]
        try:
            if gt.header.frame_id != "world" or mapped.header.frame_id != "odom" or mapped.child_frame_id != "base_link":
                raise ValueError("world/map base-frame contract mismatch")
            world_position, world_quaternion = pose_parts(gt.pose)
            map_position, map_quaternion = pose_parts(mapped.pose.pose)
            world_base = pose_matrix(world_position, world_quaternion)
            # Accepted map->odom is the identity session origin; preserve the source odom message.
            map_base = pose_matrix(map_position, map_quaternion)
            transform = startup_alignment(
                timestamp_ns=key,
                world_base_frame="base_link",
                map_base_frame="base_link",
                world_from_base=world_base,
                map_from_base=map_base,
                selection_index=0,
            )
            self.alignment = {
                "selection_rule": "first exact positive startup pair after collector readiness",
                "timestamp_ns": key,
                "world_from_base": world_base,
                "map_from_base": map_base,
                "map_from_world": transform,
                "world_pose_message_sha256": msg_hash(gt),
                "map_odometry_message_sha256": msg_hash(mapped),
                "map_from_odom_source": "accepted identity session_map_origin",
                "operational_publication": False,
            }
            (self.output / "startup_alignment.json").write_bytes(canonical_json_bytes(self.alignment) + b"\n")
            self.finish_if_ready()
        except Exception as exc:
            self.fail(f"startup alignment rejected: {exc}")

    def try_receipt(self, key: int) -> None:
        if self.failed or key in self.seen_stamps or len(self.receipts) >= 20:
            return
        if self.scene_identity is None:
            self.telemetry.record_join(key, {
                "rgb": key in self.rgb, "depth": key in self.depth,
                "camera_info": key in self.info, "truth": key in self.truth,
                "attestation": key in self.updates,
            }, False)
            return
        required = (self.rgb, self.depth, self.info, self.truth, self.updates)
        presence = {
            "rgb": key in self.rgb, "depth": key in self.depth,
            "camera_info": key in self.info, "truth": key in self.truth,
            "attestation": key in self.updates,
        }
        self.telemetry.record_join(key, presence, True)
        if any(key not in values for values in required):
            return
        try:
            rgb, depth, info, truth, update = (
                self.rgb[key], self.depth[key], self.info[key], self.truth[key], self.updates[key])
            if not (rgb.header.frame_id == depth.header.frame_id == info.header.frame_id == truth.header.frame_id == "camera_optical_frame"):
                raise ValueError("camera frame identity mismatch")
            if (rgb.width, rgb.height) != (640, 480) or (truth.width, truth.height) != (640, 480):
                raise ValueError("camera dimensions mismatch")
            labels = labels_from_image(truth)
            summary = summarize_truth_labels(labels, target_label=TARGET_LABEL)
            rgb_serialized = bytes(serialize_message(rgb))
            token_payload = {
                "experiment_id": self.experiment_id,
                "run_id": self.run_id,
                "timestamp_ns": key,
                "simulation_iteration": update.iteration,
                "rgb_message_sha256": sha256_bytes(rgb_serialized),
                "rgb_sensor_identity": "/aegis/sim/sensors/camera/image",
            }
            token = "P19OBS-" + sha256_bytes(canonical_json_bytes(token_payload))
            scene_hash = sha256_bytes(canonical_json_bytes(self.scene_identity))
            receipt = ExposureReceipt(
                experiment_id=self.experiment_id,
                run_id=self.run_id,
                observation_token=token,
                rgb_sensor_identity="/aegis/sim/sensors/camera/image",
                truth_sensor_identity="/aegis/p19_eval/truth/labels_map",
                simulation_iteration=update.iteration,
                render_identity=f"gz-post-render-{update.render_event}-update-{update.iteration}",
                timestamp_ns=key,
                frame_id=rgb.header.frame_id,
                width=rgb.width,
                height=rgb.height,
                encoding=rgb.encoding,
                step=rgb.step,
                rgb_message_sha256=sha256_bytes(rgb_serialized),
                rgb_pixel_sha256=sha256_bytes(bytes(rgb.data)),
                depth_message_sha256=msg_hash(depth),
                camera_info_sha256=msg_hash(info),
                truth_label_buffer_sha256=sha256_bytes(bytes(truth.data)),
                scene_state_sha256=scene_hash,
                gt_defect_id=GT_ID,
                scene_model=TARGET_MODEL,
                scene_link=TARGET_LINK,
                scene_visual=TARGET_VISUAL,
                binding_rule_version=BINDING_RULE,
                truth_summary=summary,
            )
            validate_receipt(receipt, update)
            if self.receipts and (key <= self.receipts[-1].timestamp_ns or
                                  update.iteration <= self.receipts[-1].simulation_iteration):
                raise ValueError("duplicate/restarted timestamp or iteration")
            self.receipts.append(receipt)
            self.telemetry.record_receipt(key, token)
            self.seen_stamps.add(key)
            destination = self.output / "receipts" / f"{len(self.receipts):04d}.json"
            destination.write_bytes(canonical_json_bytes(receipt_as_dict(receipt)) + b"\n")
            self.get_logger().info(f"eligible paired receipt {len(self.receipts)}/20 at {key}")
            self.finish_if_ready()
        except Exception as exc:
            self.telemetry.record_rejection(key, str(exc))
            self.fail(f"paired exposure rejected at {key}: {exc}")

    def write_telemetry(self, outcome: str) -> None:
        path = self.output / "passive_telemetry.json"
        path.write_bytes(canonical_json_bytes(self.telemetry.snapshot(outcome)) + b"\n")

    def finish_if_ready(self) -> None:
        if len(self.receipts) == 20 and self.alignment is not None and not self.failed:
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
            self.get_logger().info("P19 no-START readiness collection complete")
            rclpy.shutdown()

    def fail(self, reason: str) -> None:
        if self.failed:
            return
        self.failed = True
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
        node.write_telemetry("INTERRUPTED")
        raise
    finally:
        node.destroy_node()


if __name__ == "__main__":
    main()
