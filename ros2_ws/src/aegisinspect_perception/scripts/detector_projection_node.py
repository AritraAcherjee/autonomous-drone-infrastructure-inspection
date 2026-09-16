#!/usr/bin/env python3
"""DET-FINAL-v1 ROS image inference followed by existing ProjectCamera ROI projection."""

import math

import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image

from aegisinspect_interfaces.srv import ProjectCamera
from aegisinspect_perception.detector_projection import (
    Detection,
    MODEL_VERSION,
    bbox_to_roi,
    validate_class_map,
)


class DetectorProjectionNode(Node):
    def __init__(self):
        super().__init__(
            "detector_projection",
            namespace="/aegis/perception",
        )

        self.declare_parameter("model_path", "")
        self.declare_parameter("confidence_floor", 0.001)
        self.declare_parameter("imgsz", 640)
        self.declare_parameter("device", 0)
        self.declare_parameter("max_det", 300)

        model_path = str(
            self.get_parameter("model_path").value
        )
        self.confidence_floor = float(
            self.get_parameter("confidence_floor").value
        )
        self.imgsz = int(
            self.get_parameter("imgsz").value
        )
        self.device = int(
            self.get_parameter("device").value
        )
        self.max_det = int(
            self.get_parameter("max_det").value
        )

        if not model_path:
            raise RuntimeError(
                "model_path parameter is required"
            )

        # Keep the ROS package importable without ML dependencies for ordinary
        # colcon tests. The heavy runtime imports occur only when this node runs.
        import torch
        from ultralytics import YOLO

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA is required for the Tuesday detector integration runtime"
            )

        self.get_logger().info(
            f"loading {MODEL_VERSION} model={model_path} "
            f"device={torch.cuda.get_device_name(self.device)}"
        )

        self.model = YOLO(model_path)
        validate_class_map(self.model.names)

        self.bridge = CvBridge()
        self.project_client = self.create_client(
            ProjectCamera,
            "/aegis/mapping/project_camera",
        )

        if not self.project_client.wait_for_service(
            timeout_sec=10.0
        ):
            raise RuntimeError(
                "/aegis/mapping/project_camera unavailable"
            )

        self.subscription = self.create_subscription(
            Image,
            "/aegis/sensors/camera/image_raw",
            self._image_callback,
            qos_profile_sensor_data,
        )

        self.frames_processed = 0
        self.detections_submitted = 0
        self.projection_successes = 0
        self.projection_failures = 0

        self.metrics_timer = self.create_timer(
            30.0,
            self._report_metrics,
        )

        self.get_logger().info(
            f"{MODEL_VERSION} detector projection ready "
            f"confidence_floor={self.confidence_floor} "
            f"imgsz={self.imgsz}"
        )

    def _image_callback(self, msg: Image):
        try:
            image = self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="bgr8",
            )

            results = self.model.predict(
                source=image,
                imgsz=self.imgsz,
                device=self.device,
                conf=self.confidence_floor,
                max_det=self.max_det,
                verbose=False,
            )

            result = results[0]

            if tuple(result.orig_shape) != (
                int(msg.height),
                int(msg.width),
            ):
                self.get_logger().error(
                    "original-image geometry mismatch: "
                    f"result={result.orig_shape} "
                    f"ros=({msg.height}, {msg.width})"
                )
                return

            self.frames_processed += 1

            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                return

            xyxy = boxes.xyxy.detach().cpu().numpy()
            conf = boxes.conf.detach().cpu().numpy()
            cls = (
                boxes.cls.detach()
                .cpu()
                .numpy()
                .astype(int)
            )

            for index, (box, score, class_id) in enumerate(
                zip(xyxy, conf, cls)
            ):
                bbox = tuple(float(v) for v in box)

                detection = Detection(
                    detection_id=(
                        f"{msg.header.stamp.sec}."
                        f"{msg.header.stamp.nanosec:09d}-"
                        f"{index}"
                    ),
                    class_id=int(class_id),
                    class_name=str(
                        self.model.names[int(class_id)]
                    ),
                    confidence=float(score),
                    bbox_xyxy=bbox,
                    image_width=int(msg.width),
                    image_height=int(msg.height),
                    frame_id=str(msg.header.frame_id),
                    stamp_sec=int(msg.header.stamp.sec),
                    stamp_nanosec=int(
                        msg.header.stamp.nanosec
                    ),
                )

                try:
                    roi = bbox_to_roi(
                        detection.bbox_xyxy,
                        detection.image_width,
                        detection.image_height,
                    )
                except ValueError as exc:
                    self.get_logger().warning(
                        f"NOT_PROJECTED "
                        f"id={detection.detection_id} "
                        f"class={detection.class_name} "
                        f"reason=INVALID_ROI detail={exc}"
                    )
                    self.projection_failures += 1
                    continue

                request = ProjectCamera.Request()
                request.header = msg.header
                request.mode = ProjectCamera.Request.ROI
                (
                    request.left,
                    request.top,
                    request.right,
                    request.bottom,
                ) = roi

                future = self.project_client.call_async(
                    request
                )
                future.add_done_callback(
                    lambda completed,
                    det=detection,
                    det_roi=roi: self._projection_done(
                        completed,
                        det,
                        det_roi,
                    )
                )

                self.detections_submitted += 1

        except Exception as exc:
            self.get_logger().error(
                f"detector frame processing failed: "
                f"{type(exc).__name__}: {exc}"
            )

    def _projection_done(
        self,
        future,
        detection: Detection,
        roi: tuple[int, int, int, int],
    ):
        try:
            response = future.result()
        except Exception as exc:
            self.projection_failures += 1
            self.get_logger().error(
                f"NOT_PROJECTED "
                f"id={detection.detection_id} "
                f"class={detection.class_name} "
                f"reason=SERVICE_ERROR detail={exc}"
            )
            return

        if response.status != ProjectCamera.Response.SUCCESS:
            self.projection_failures += 1
            self.get_logger().warning(
                f"NOT_PROJECTED "
                f"id={detection.detection_id} "
                f"class={detection.class_name} "
                f"confidence={detection.confidence:.6f} "
                f"roi={roi} "
                f"status={response.status} "
                f"detail={response.detail}"
            )
            return

        xyz = (
            float(response.point.x),
            float(response.point.y),
            float(response.point.z),
        )

        if not all(math.isfinite(v) for v in xyz):
            self.projection_failures += 1
            self.get_logger().error(
                f"NOT_PROJECTED "
                f"id={detection.detection_id} "
                f"reason=NONFINITE_SUCCESS_RESPONSE"
            )
            return

        self.projection_successes += 1

        self.get_logger().info(
            f"PROJECTED "
            f"id={detection.detection_id} "
            f"class_id={detection.class_id} "
            f"class={detection.class_name} "
            f"confidence={detection.confidence:.6f} "
            f"bbox={[round(v, 2) for v in detection.bbox_xyxy]} "
            f"roi={roi} "
            f"xyz_m={[round(v, 6) for v in xyz]} "
            f"frame={response.header.frame_id} "
            f"stamp="
            f"{response.header.stamp.sec}."
            f"{response.header.stamp.nanosec:09d} "
            f"model={detection.model_version} "
            f"projection_latency_ms="
            f"{response.latency_ms:.3f}"
        )

    def _report_metrics(self):
        self.get_logger().info(
            f"runtime frames={self.frames_processed} "
            f"submitted={self.detections_submitted} "
            f"projected={self.projection_successes} "
            f"failed={self.projection_failures}"
        )


def main():
    rclpy.init()
    node = None

    try:
        node = DetectorProjectionNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
