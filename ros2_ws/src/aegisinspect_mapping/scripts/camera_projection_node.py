#!/usr/bin/env python3
"""Synchronous camera-frame service, explicitly spun with one executor thread."""
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
from aegisinspect_interfaces.srv import ProjectCamera
from aegisinspect_mapping.camera_projection import ProjectionCache, fill_response


class CameraProjectionNode(Node):
    def __init__(self):
        super().__init__('camera_projection', namespace='/aegis/mapping')
        self.declare_parameter('cache_size', 30)
        self.declare_parameter('central_fraction', 0.5)
        self.declare_parameter('min_valid_fraction', 0.5)
        self.cache = ProjectionCache(
            self.get_parameter('cache_size').value,
            self.get_parameter('central_fraction').value,
            self.get_parameter('min_valid_fraction').value)
        self.depth_sub = self.create_subscription(
            Image, '/aegis/perception/depth/image', self.cache.add_depth, qos_profile_sensor_data)
        self.info_sub = self.create_subscription(
            CameraInfo, '/aegis/sensors/camera/camera_info', self.cache.add_info, qos_profile_sensor_data)
        self.service = self.create_service(
            ProjectCamera, '/aegis/mapping/project_camera', self.handle)
        self.metrics_timer = self.create_timer(30.0, self.report_metrics)

    def handle(self, request, response):
        result = self.cache.handle(request)
        return fill_response(result, response, self.cache.last_latency_ms)

    def report_metrics(self):
        counts = dict(self.cache.counts)
        success = counts.get('SUCCESS', 0)
        self.get_logger().info(
            f'projection success={success} failure={sum(counts.values()) - success} '
            f'counts={counts} last_latency_ms={self.cache.last_latency_ms:.3f}')


def main():
    rclpy.init()
    node = None
    try:
        node = CameraProjectionNode()
        rclpy.spin(node)
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
