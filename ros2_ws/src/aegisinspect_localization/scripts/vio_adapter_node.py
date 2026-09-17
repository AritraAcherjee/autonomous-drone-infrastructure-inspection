#!/usr/bin/env python3
"""AegisInspect OpenVINS-to-canonical-odometry adapter."""

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster

from aegisinspect_localization.vio_adapter import (
    CANONICAL_ODOM_TOPIC,
    NATIVE_ODOM_TOPIC,
    canonicalize_odometry,
    transform_from_odometry,
)


class VioAdapterNode(Node):

    def __init__(self):
        super().__init__("vio_adapter")

        self._publisher = self.create_publisher(
            Odometry,
            CANONICAL_ODOM_TOPIC,
            10,
        )

        self._tf_broadcaster = TransformBroadcaster(self)

        self.declare_parameter(
            "native_odom_topic",
            NATIVE_ODOM_TOPIC,
        )
        native_odom_topic = self.get_parameter(
            "native_odom_topic"
        ).value

        if (
            not isinstance(native_odom_topic, str)
            or not native_odom_topic.strip()
        ):
            raise ValueError(
                "native_odom_topic must be a non-empty string"
            )

        self._subscription = self.create_subscription(
            Odometry,
            native_odom_topic,
            self._on_native_odometry,
            2,
        )

    def _on_native_odometry(self, native):
        canonical = canonicalize_odometry(native)

        if canonical is None:
            self.get_logger().warning(
                "Rejected invalid OpenVINS odometry sample; "
                "no canonical odometry or TF published."
            )
            return

        transform = transform_from_odometry(canonical)

        self._publisher.publish(canonical)
        self._tf_broadcaster.sendTransform(transform)


def main(args=None):
    rclpy.init(args=args)

    node = VioAdapterNode()

    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
