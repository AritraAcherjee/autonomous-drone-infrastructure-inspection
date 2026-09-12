#!/usr/bin/env python3
"""Read-only depth acceptance probe; run against the installed inspection bay.

No publishers, canonicalization, registration or operational transforms.
Exit 0 means this probe passed, 1 failed, 2 runtime/dependency blocked.
Run smoke_check.py separately for all existing sensors and TF.
"""
import argparse
from collections import Counter
import math
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

DEPTH = '/aegis/perception/depth/image'
RGB = '/aegis/sensors/camera/image_raw'
INFO = '/aegis/sensors/camera/camera_info'
GZ_DEPTH = '/aegis/sim/sensors/camera/depth_image'


def fixture_geometry(share):
    """Read evaluation-only geometry; never publish it as a transform."""
    model = ET.parse(Path(share) / 'models/aegis_drone/model.sdf').getroot()
    world = ET.parse(Path(share) / 'worlds/inspection_bay.sdf').getroot()
    camera = model.find(".//sensor[@name='camera']/camera")
    rig = list(map(float, world.findtext(".//include[name='aegis_drone']/pose").split()))
    origin = list(map(float, model.findtext(".//frame[@name='camera_link']/pose").split()))
    wall = world.find(".//model[@name='wall']")
    wall_pose = list(map(float, wall.findtext('pose').split()))
    if any(rig[3:] + origin[3:] + wall_pose[3:]):
        raise ValueError('fixture requires the original axis-aligned rig and wall')
    wall_thickness = float(wall.findtext('link/visual/geometry/box/size').split()[0])
    return {
        'width': int(camera.findtext('image/width')),
        'height': int(camera.findtext('image/height')),
        'hfov': float(camera.findtext('horizontal_fov')),
        'z': wall_pose[0] - wall_thickness / 2 - rig[0] - origin[0],
    }


def decode_depth(message):
    """Respect byte order and row padding, without changing any samples."""
    if message.encoding != '32FC1':
        raise ValueError(f'expected 32FC1, got {message.encoding}')
    if (message.width <= 0 or message.height <= 0 or message.step < message.width * 4
            or len(message.data) != message.step * message.height):
        raise ValueError('invalid depth payload layout')
    fmt = ('>' if message.is_bigendian else '<') + str(message.width) + 'f'
    return [struct.unpack_from(fmt, message.data, row * message.step)
            for row in range(message.height)]


def plane_samples(rows, info, expected_z, tolerance=0.02):
    """Sample the wall clear of panels; radial range must fail this check."""
    v = round(info.k[5])
    locations = [('left', round(info.width * 0.1)), ('center', round(info.k[2])),
                 ('right', round(info.width * 0.9))]
    results = []
    for name, u in locations:
        if not (0 <= v < len(rows) and 0 <= u < len(rows[v])):
            raise ValueError('principal row or probe pixel outside image')
        z = rows[v][u]
        radial = expected_z * math.sqrt(1 + ((u - info.k[2]) / info.k[0])**2
                                       + ((v - info.k[5]) / info.k[4])**2)
        results.append({'region': name, 'u': u, 'v': v, 'depth_m': z,
                        'radial_prediction_m': radial})
    if any(not math.isfinite(s['depth_m']) or abs(s['depth_m'] - expected_z) > tolerance
           for s in results):
        raise ValueError(f'optical-Z plane check failed: expected {expected_z} +/- {tolerance} m; {results}')
    return results


def gz_stamps(text):
    """Extract protobuf text stamps, including omitted zero-valued fields."""
    stamps = set()
    for block in re.findall(r'header\s*\{\s*stamp\s*\{([^}]*)\}', text):
        sec = re.search(r'\bsec:\s*(\d+)', block)
        nsec = re.search(r'\bnsec:\s*(\d+)', block)
        stamps.add((int(sec[1]) if sec else 0) * 1_000_000_000 + (int(nsec[1]) if nsec else 0))
    return stamps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--expect-no-return', action='store_true',
                        help='only after removing the five bay geometry models; restart afterward')
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be finite and positive')
    try:
        import rclpy
        from rclpy.qos import qos_profile_sensor_data
        from sensor_msgs.msg import Image, CameraInfo
        from rosgraph_msgs.msg import Clock
        from ament_index_python.packages import get_package_share_directory
    except ImportError as exc:
        print(f'BLOCKED: {exc}')
        return 2
    fixture = fixture_geometry(get_package_share_directory('aegisinspect_sim'))
    rclpy.init(args=[])
    node = rclpy.create_node('depth_acceptance_check', namespace='/aegis/system_tests')
    latest, stamps, errors = {}, {t: set() for t in (DEPTH, RGB, INFO)}, set()
    counts, clocks = Counter(), []

    def stamp(value):
        return value.sec * 1_000_000_000 + value.nanosec

    def receive(topic, msg):
        value = stamp(msg.header.stamp)
        if topic in latest and value <= stamp(latest[topic].header.stamp):
            errors.add(f'{topic}: non-advancing timestamp')
        if msg.header.frame_id != 'camera_optical_frame':
            errors.add(f'{topic}: wrong optical frame')
        latest[topic] = msg
        stamps[topic].add(value)
        counts[topic] += 1

    subscriptions = [node.create_subscription(kind, topic, lambda m, t=topic: receive(t, m),
                      qos_profile_sensor_data) for topic, kind in [(DEPTH, Image), (RGB, Image), (INFO, CameraInfo)]]
    subscriptions.append(node.create_subscription(Clock, '/clock', lambda m: clocks.append(stamp(m.clock)),
                                                 qos_profile_sensor_data))
    capture = None
    try:
        with tempfile.TemporaryFile(mode='w+') as output, tempfile.TemporaryFile(mode='w+') as stderr:
            deadline = time.monotonic() + args.timeout
            while time.monotonic() < deadline:
                rclpy.spin_once(node, timeout_sec=0.05)
                if capture is None and counts[DEPTH] >= 3:
                    # Start after ROS discovery; retain ROS stamps across this exact acquisition interval.
                    capture = subprocess.Popen(['gz', 'topic', '-e', '-t', GZ_DEPTH, '-n', '3'],
                                               stdout=output, stderr=stderr)
            if capture is None:
                errors.add('no depth messages; Gazebo timestamp capture not started')
            elif capture.poll() is None:
                capture.terminate()
                capture.wait(timeout=5)
                errors.add('Gazebo transport capture timed out')
            elif capture.returncode != 0:
                stderr.seek(0)
                errors.add('Gazebo transport capture failed: ' + stderr.read())
            output.seek(0)
            original_stamps = gz_stamps(output.read())
            matched = original_stamps & stamps[DEPTH]
            print('Gazebo observation stamps (ns):', sorted(original_stamps))
            print('Exact ROS depth stamp matches (ns):', sorted(matched))
            if len(original_stamps) < 3 or matched != original_stamps:
                errors.add('require three exact Gazebo -> ROS observation timestamp matches')

        for topic in stamps:
            if counts[topic] < 3 or node.count_publishers(topic) != 1:
                errors.add(f'{topic}: require >=3 messages and exactly one publisher')
        if len(clocks) < 3 or clocks[-1] <= clocks[0] or any(a > b for a, b in zip(clocks, clocks[1:])):
            errors.add('simulation clock not advancing monotonically')
        if not set.intersection(*stamps.values()):
            errors.add('no shared RGB/depth/CameraInfo observation timestamp')
        if all(topic in latest for topic in stamps):
            depth, rgb, info = (latest[t] for t in (DEPTH, RGB, INFO))
            print('Depth metadata:', depth.header, depth.encoding, depth.width, depth.height, depth.step)
            print('RGB:', rgb.encoding, rgb.width, rgb.height)
            print('CameraInfo K:', list(info.k), 'P:', list(info.p), 'D:', list(info.d))
            sizes = {(m.width, m.height) for m in (depth, rgb, info)}
            if sizes != {(fixture['width'], fixture['height'])} or rgb.encoding != 'rgb8':
                errors.add('RGB/depth/CameraInfo resolution or RGB encoding mismatch')
            f = fixture['width'] / (2 * math.tan(fixture['hfov'] / 2))
            target = [f, 0, info.width / 2, 0, f, info.height / 2, 0, 0, 1]
            if any(not math.isfinite(a) or abs(a-b) > 0.01 for a, b in zip(info.k, target)):
                errors.add('CameraInfo K does not match configured pinhole projection')
            if any(not math.isfinite(d) or abs(d) > 1e-9 for d in info.d):
                errors.add('unexpected camera distortion')
            expected_p = [info.k[0], 0, info.k[2], 0, 0, info.k[4], info.k[5], 0, 0, 0, 1, 0]
            if any(not math.isfinite(a) or abs(a-b) > 0.01 for a, b in zip(info.p, expected_p)):
                errors.add('CameraInfo P and K disagree')
            if clocks and any(not 0 < stamp(m.header.stamp) <= clocks[-1] + 1_000_000_000
                              or abs(stamp(m.header.stamp) - clocks[-1]) > 2_000_000_000
                              for m in (depth, rgb, info)):
                errors.add('sensor stamps inconsistent with simulation clock')
            try:
                rows = decode_depth(depth)
                invalid = Counter('nan' if math.isnan(z) else '+inf' if z == math.inf else '-inf'
                                  if z == -math.inf else 'nonpositive' if z <= 0 else 'positive_finite'
                                  for row in rows for z in row)
                print('Depth value counts:', dict(invalid))
                if args.expect_no_return:
                    if invalid['positive_finite']:
                        errors.add('empty-scene test contains fabricated or unexpected finite returns')
                elif not errors:
                    print('Optical-Z samples:', plane_samples(rows, info, fixture['z']))
            except ValueError as exc:
                errors.add(str(exc))
        for error in sorted(errors):
            print('FAIL:', error)
        if not errors:
            print('PASS:', 'empty-scene invalid depth' if args.expect_no_return else 'metric optical-Z plane',
                  'and depth metadata/calibration/observation timestamps')
        return 1 if errors else 0
    except (OSError, subprocess.SubprocessError) as exc:
        print(f'BLOCKED: {exc}')
        return 2
    finally:
        if capture is not None and capture.poll() is None:
            capture.terminate()
            capture.wait(timeout=5)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
