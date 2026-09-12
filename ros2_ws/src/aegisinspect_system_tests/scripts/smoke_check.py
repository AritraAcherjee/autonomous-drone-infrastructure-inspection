#!/usr/bin/env python3
"""Read-only runtime acceptance check against an already running foundation."""
import argparse
from collections import deque
import math
import struct
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=30.0)
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    try:
        import rclpy
        from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, qos_profile_sensor_data
        from sensor_msgs.msg import Image, CameraInfo, Imu, PointCloud2
        from rosgraph_msgs.msg import Clock
        from tf2_msgs.msg import TFMessage
    except ImportError as exc:
        print(f'BLOCKED: ROS 2 Python runtime unavailable: {exc}')
        return 2

    rclpy.init(args=[])
    node = rclpy.create_node('foundation_smoke_check', namespace='/aegis/system_tests')
    sensor_types = {
        '/aegis/sensors/camera/image_raw': (Image, 'camera_optical_frame'),
        '/aegis/sensors/camera/camera_info': (CameraInfo, 'camera_optical_frame'),
        '/aegis/sensors/imu/data': (Imu, 'imu_link'),
        '/aegis/sensors/lidar/points': (PointCloud2, 'lidar_link'),
        '/aegis/perception/depth/image': (Image, 'camera_optical_frame'),
    }
    messages = {topic: deque(maxlen=256) for topic in sensor_types}
    clocks = deque(maxlen=256)
    transforms = {}
    dynamic = []
    errors = set()
    counts = {topic: 0 for topic in sensor_types}
    last_stamp = {}

    def stamp(value):
        return value.sec * 1_000_000_000 + value.nanosec

    def receive(topic, message):
        value = stamp(message.header.stamp)
        if topic in last_stamp and value <= last_stamp[topic]:
            errors.add(f'{topic}: timestamps did not strictly advance')
        last_stamp[topic] = value
        if message.header.frame_id != sensor_types[topic][1]:
            errors.add(f'{topic}: wrong frame {message.header.frame_id!r}')
        counts[topic] += 1
        messages[topic].append(message)

    def receive_tf(message):
        for transform in message.transforms:
            transforms[(transform.header.frame_id, transform.child_frame_id)] = transform

    subscriptions = [node.create_subscription(kind, topic, lambda msg, t=topic: receive(t, msg),
                    qos_profile_sensor_data) for topic, (kind, _) in sensor_types.items()]
    subscriptions.append(node.create_subscription(Clock, '/clock', lambda msg: clocks.append(stamp(msg.clock)), qos_profile_sensor_data))
    static_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    subscriptions.append(node.create_subscription(TFMessage, '/tf_static', receive_tf, static_qos))
    subscriptions.append(node.create_subscription(TFMessage, '/tf', lambda msg: dynamic.extend(msg.transforms), qos_profile_sensor_data))
    try:
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        for topic in sensor_types:
            if counts[topic] < 3:
                errors.add(f'{topic}: received {counts[topic]} samples; require >=3')
            if node.count_publishers(topic) != 1:
                errors.add(f'{topic}: expected exactly one publisher')
        if len(clocks) < 3 or clocks[-1] <= clocks[0]:
            errors.add('/clock: no advancing simulation clock')
        if node.count_publishers('/clock') != 1:
            errors.add('/clock: expected exactly one publisher')
        if any(a > b for a, b in zip(clocks, list(clocks)[1:])):
            errors.add('/clock: time moved backwards')
        if clocks:
            for topic, value in last_stamp.items():
                if value <= 0 or abs(value - clocks[-1]) > 2_000_000_000:
                    errors.add(f'{topic}: timestamp not near simulation clock')

        expected_tf = {
            ('base_link', 'camera_link'): (0.25, 0, 0),
            ('camera_link', 'camera_optical_frame'): (0, 0, 0),
            ('base_link', 'imu_link'): (0, 0, 0),
            ('base_link', 'lidar_link'): (0, 0, 0.15),
        }
        if set(transforms) != set(expected_tf):
            errors.add(f'/tf_static: expected {sorted(expected_tf)}, got {sorted(transforms)}')
        for edge, expected in expected_tf.items():
            if edge not in transforms:
                continue
            transform = transforms[edge].transform
            xyz = transform.translation
            if any(abs(a-b) > 1e-6 for a, b in zip((xyz.x, xyz.y, xyz.z), expected)):
                errors.add(f'/tf_static: wrong translation for {edge}')
            q = transform.rotation
            target = (-0.5, 0.5, -0.5, 0.5) if edge[1] == 'camera_optical_frame' else (0, 0, 0, 1)
            actual = (q.x, q.y, q.z, q.w)
            if not any(all(abs(a-sign*b) < 1e-6 for a, b in zip(actual, target)) for sign in (1, -1)):
                errors.add(f'/tf_static: wrong rotation for {edge}')
        if dynamic:
            errors.add('/tf: unexpected dynamic transforms')
        for topic in ['/aegis/localization/vio/odom']:
            if node.count_publishers(topic):
                errors.add(f'{topic}: reserved interface unexpectedly published')

        image_topic = '/aegis/sensors/camera/image_raw'
        info_topic = '/aegis/sensors/camera/camera_info'
        if messages[image_topic] and messages[info_topic]:
            image = messages[image_topic][-1]
            info = messages[info_topic][-1]
            if (image.width, image.height, image.encoding) != (640, 480, 'rgb8'):
                errors.add('camera: expected 640x480 rgb8')
            if image.step < image.width*3 or len(image.data) != image.step*image.height:
                errors.add('camera: invalid pixel payload')
            if (info.width, info.height) != (image.width, image.height) or info.k[0] <= 0 or info.k[4] <= 0:
                errors.add('camera: invalid CameraInfo dimensions/intrinsics')
            image_stamps = {stamp(msg.header.stamp) for msg in messages[image_topic]}
            if not image_stamps.intersection(stamp(msg.header.stamp) for msg in messages[info_topic]):
                errors.add('camera: no matching Image/CameraInfo acquisition timestamps')
        imu_topic = '/aegis/sensors/imu/data'
        if messages[imu_topic]:
            imu = messages[imu_topic][-1]
            values = [getattr(v, axis) for v in (imu.angular_velocity, imu.linear_acceleration) for axis in ('x', 'y', 'z')]
            if not all(math.isfinite(value) for value in values):
                errors.add('imu: non-finite data')
            acceleration = math.sqrt(sum(getattr(imu.linear_acceleration, axis)**2 for axis in ('x', 'y', 'z')))
            if not 9.5 < acceleration < 10.1:
                errors.add(f'imu: stationary specific force should be near 9.81 m/s^2; got {acceleration}')
        cloud_topic = '/aegis/sensors/lidar/points'
        if messages[cloud_topic]:
            cloud = messages[cloud_topic][-1]
            fields = {field.name: field for field in cloud.fields}
            if not {'x', 'y', 'z'} <= fields.keys() or cloud.width*cloud.height != 360*16:
                errors.add('lidar: expected XYZ and 360x16 points')
            elif any(fields[name].datatype != 7 or fields[name].count != 1 for name in ('x', 'y', 'z')):
                errors.add('lidar: expected float32 XYZ')
            elif (len(cloud.data) != cloud.row_step*cloud.height or cloud.row_step < cloud.width*cloud.point_step
                  or any(fields[name].offset+4 > cloud.point_step for name in ('x', 'y', 'z'))):
                errors.add('lidar: invalid point payload layout')
            else:
                finite_z = []
                fmt = '>f' if cloud.is_bigendian else '<f'
                for row in range(cloud.height):
                    for column in range(cloud.width):
                        offset = row*cloud.row_step + column*cloud.point_step
                        xyz = [struct.unpack_from(fmt, cloud.data, offset+fields[name].offset)[0] for name in ('x', 'y', 'z')]
                        if all(math.isfinite(v) for v in xyz):
                            finite_z.append(xyz[2])
                if not finite_z or max(finite_z)-min(finite_z) < 0.1:
                    errors.add('lidar: no finite 3D surface returns')
        for topic, count in counts.items():
            print(f'{topic}: {count} samples')
        for error in sorted(errors):
            print('FAIL:', error)
        if not errors:
            print('PASS: sensor payloads, frames, static TF, timestamps, clock and reserved-interface isolation')
        return 1 if errors else 0
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
