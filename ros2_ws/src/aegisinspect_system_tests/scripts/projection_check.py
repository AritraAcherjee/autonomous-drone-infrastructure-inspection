#!/usr/bin/env python3
"""Live Phase 3 service acceptance in the unchanged Phase 2 inspection bay.

Run foundation and camera_projection_node first. No publishers or transforms.
Exit 0 = probe passed; 1 = acceptance failed; 2 = ROS dependencies missing.
"""
import math
import time


def main():
    try:
        import rclpy
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import CameraInfo, Image
        from aegisinspect_interfaces.srv import ProjectCamera
        from aegisinspect_mapping.depth_geometry import pixel_to_camera_xyz
    except ImportError as exc:
        print(f'BLOCKED: {exc}')
        return 2
    rclpy.init(args=[])
    node = rclpy.create_node('projection_acceptance_check', namespace='/aegis/system_tests')
    depths, infos = {}, {}

    def stamp(msg):
        return msg.header.stamp.sec, msg.header.stamp.nanosec

    def receive(cache, msg):
        cache[stamp(msg)] = msg
        while len(cache) > 30:
            del cache[next(iter(cache))]

    subscriptions = [
        node.create_subscription(Image, '/aegis/perception/depth/image',
                                 lambda m: receive(depths, m), qos_profile_sensor_data),
        node.create_subscription(CameraInfo, '/aegis/sensors/camera/camera_info',
                                 lambda m: receive(infos, m), qos_profile_sensor_data),
    ]
    client = node.create_client(ProjectCamera, '/aegis/mapping/project_camera')

    def check(condition, detail):
        if not condition:
            raise ValueError(detail)

    def call(request, retry_missing=False):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            future = client.call_async(request)
            rclpy.spin_until_future_complete(node, future, timeout_sec=1)
            if not future.done():
                client.remove_pending_request(future)
                raise ValueError('service response timeout')
            response = future.result()
            if response.status != response.TIMESTAMP_MISMATCH or not retry_missing:
                return response
            # Retry the exact request after callbacks have delivered its pair.
            rclpy.spin_once(node, timeout_sec=.05)
        raise ValueError('exact observation was not cached within 3 seconds')

    def request_for_pair():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.1)
            common = depths.keys() & infos.keys()
            if common:
                key = max(common)
                info = infos[key]
                request = ProjectCamera.Request()
                request.header = depths[key].header
                return request, info
        raise ValueError('no exact depth/CameraInfo pair received')

    try:
        check(client.wait_for_service(timeout_sec=10), 'projection service unavailable')
        for name in ('principal', 'off_center', 'roi'):
            request, info = request_for_pair()
            request.mode = request.PIXEL
            request.u, request.v = round(info.k[2]), round(info.k[5])
            u, v = float(request.u), float(request.v)
            if name == 'off_center':
                request.u = 64
                u = 64.
            elif name == 'roi':
                request.mode = request.ROI
                request.left, request.top, request.right, request.bottom = 300, 230, 341, 251
                u, v = 320., 240.
            response = call(request, retry_missing=True)
            check(response.status == response.SUCCESS, f'{name}: {response.status} {response.detail}')
            check(response.header == request.header, f'{name}: observation header changed')
            check(response.header.frame_id == 'camera_optical_frame', 'wrong output frame')
            expected = pixel_to_camera_xyz(u, v, 3.65, fx=info.k[0], fy=info.k[4],
                                           cx=info.k[2], cy=info.k[5])
            actual = (response.point.x, response.point.y, response.point.z)
            check(all(math.isfinite(a) and abs(a-b) <= .02 for a, b in zip(actual, expected)),
                  f'{name}: actual {actual}; expected {expected} +/- 0.02 m per axis')
            check((response.sample_u, response.sample_v) == (u, v), 'wrong representative pixel')
            # Independently verify the transmitted point follows the pinhole formula.
            analytic = ((u-info.k[2])*actual[2]/info.k[0],
                        (v-info.k[5])*actual[2]/info.k[4], actual[2])
            check(all(abs(a-b) <= 1e-9 for a, b in zip(actual, analytic)), 'pinhole disagreement')
            print(f'PASS {name}: stamp={stamp(response)} XYZ={actual} expected={expected}')
        request, info = request_for_pair()
        request.u, request.v = -1, 240
        response = call(request, retry_missing=True)
        check(response.status == response.OUT_OF_BOUNDS, 'expected OUT_OF_BOUNDS')
        check(all(math.isnan(x) for x in (response.point.x, response.point.y, response.point.z)),
              'failure fabricated XYZ')
        check(response.header.frame_id == '', 'failure claimed valid frame')
        check(stamp(response) == stamp(request), 'failure lost requested stamp')
        print('PASS out-of-bounds: explicit status, NaN XYZ, requested stamp')
        # A negative observation stamp cannot match this positive-time scene.
        request.header.stamp.sec = -1
        response = call(request)
        check(response.status == response.TIMESTAMP_MISMATCH, 'expected TIMESTAMP_MISMATCH')
        check(all(math.isnan(x) for x in (response.point.x, response.point.y, response.point.z)),
              'mismatch fabricated XYZ')
        print('PASS missing timestamp: no latest-observation fallback')
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f'FAIL: {exc}')
        return 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
