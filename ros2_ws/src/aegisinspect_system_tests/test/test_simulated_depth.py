"""Configuration invariants and synthetic probe tests; no ROS/Gazebo claims."""
import importlib.util
import math
from pathlib import Path
import struct
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest
import yaml

SRC = Path(__file__).resolve().parents[2]
SIM = SRC / 'aegisinspect_sim'
spec = importlib.util.spec_from_file_location('depth_check', Path(__file__).resolve().parents[1] / 'scripts/depth_check.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_one_rgbd_geometry_drives_both_images_and_info():
    model = ET.parse(SIM / 'models/aegis_drone/model.sdf').getroot()
    cameras = model.findall('.//sensor/camera')
    assert len(cameras) == 1
    camera = cameras[0]
    sensor = model.find(".//sensor[@type='rgbd_camera']")
    assert sensor is not None and sensor.find('camera') is camera
    # Freeze the established RGB geometry; no independent depth calibration/clip override.
    assert (int(camera.findtext('image/width')), int(camera.findtext('image/height'))) == (640, 480)
    assert float(camera.findtext('horizontal_fov')) == pytest.approx(math.pi / 3)
    assert [float(camera.findtext('clip/' + k)) for k in ('near', 'far')] == [0.1, 20]
    assert camera.find('depth_camera') is None
    assert camera.find('lens') is None
    assert camera.find('distortion') is None
    assert camera.find('noise') is None
    assert sensor.find('pose').get('relative_to') == 'camera_link'
    assert list(map(float, sensor.findtext('pose').split())) == [0] * 6
    assert sensor.findtext('frame_id') == 'camera_optical_frame'
    bridges = yaml.safe_load((SIM / 'config/bridge.yaml').read_text())
    by_ros = {b['ros_topic_name']: b for b in bridges}
    prefix = sensor.findtext('topic')
    assert by_ros[probe.RGB]['gz_topic_name'] == prefix + '/image'
    assert by_ros[probe.DEPTH]['gz_topic_name'] == prefix + '/depth_image'
    assert by_ros[probe.INFO]['gz_topic_name'] == camera.findtext('camera_info_topic') == prefix + '/camera_info'
    assert by_ros[probe.DEPTH]['ros_type_name'] == 'sensor_msgs/msg/Image'
    assert by_ros[probe.DEPTH]['gz_type_name'] == 'gz.msgs.Image'


def test_wall_probe_rays_hit_unoccluded_front_face():
    fixture = probe.fixture_geometry(SIM)
    assert fixture['z'] == pytest.approx(3.65)
    world = ET.parse(SIM / 'worlds/inspection_bay.sdf').getroot()
    f = fixture['width'] / (2 * math.tan(fixture['hfov'] / 2))
    for u in (64, 320, 576):
        # Optical (xn, 0, 1) -> world (1, -xn, 0), origin from the fixture.
        origin = (0.25, 0, 1.5)
        direction = (1, -(u - 320) / f, 0)
        hits = []
        for model in world.findall('world/model'):
            pose = list(map(float, model.findtext('pose').split()))
            assert pose[3:] == [0, 0, 0]
            size = list(map(float, model.findtext('link/visual/geometry/box/size').split()))
            low, high = -math.inf, math.inf
            for center, length, start, delta in zip(pose[:3], size, origin, direction):
                if delta == 0:
                    if not center - length/2 <= start <= center + length/2:
                        high = -math.inf
                else:
                    a, b = sorted(((center-length/2-start)/delta, (center+length/2-start)/delta))
                    low, high = max(low, a), min(high, b)
            if high >= max(low, 0):
                hits.append((low, model.get('name')))
        distance, name = min(hits)
        assert name == 'wall'
        assert distance == pytest.approx(fixture['z'])


@pytest.mark.parametrize('bigendian', [False, True])
def test_decode_preserves_invalids_and_honors_padding(bigendian):
    fmt = '>' if bigendian else '<'
    values = (3.65, math.nan, math.inf, -math.inf, 0, -1)
    payload = b''.join(struct.pack(fmt + '3f', *values[i:i+3]) + b'PAD!' for i in (0, 3))
    msg = SimpleNamespace(width=3, height=2, step=16, encoding='32FC1', is_bigendian=bigendian, data=payload)
    rows = probe.decode_depth(msg)
    assert rows[0][0] == pytest.approx(3.65)
    assert math.isnan(rows[0][1])
    assert rows[0][2] == math.inf
    assert rows[1] == (-math.inf, 0, -1)


@pytest.mark.parametrize('override', [{'encoding': '16UC1'}, {'step': 3}, {'data': b''}, {'width': 0}])
def test_reject_malformed_depth(override):
    msg = dict(width=1, height=1, step=4, encoding='32FC1', is_bigendian=False, data=struct.pack('<f', 3.65))
    msg.update(override)
    with pytest.raises(ValueError):
        probe.decode_depth(SimpleNamespace(**msg))


@pytest.mark.parametrize('kind', ['z', 'radial', 'millimeters', 'invalid'])
def test_plane_probe_distinguishes_z_from_range_and_wrong_units(kind):
    f = 640 / (2 * math.tan(math.pi / 6))
    info = SimpleNamespace(width=640, k=[f, 0, 320, 0, f, 240, 0, 0, 1])
    row = [3.65 * math.sqrt(1 + ((u-320)/f)**2) if kind == 'radial'
           else 3650 if kind == 'millimeters' else math.inf if kind == 'invalid' else 3.65
           for u in range(640)]
    rows = [row] * 480
    if kind == 'z':
        result = probe.plane_samples(rows, info, 3.65)
        assert [s['u'] for s in result] == [64, 320, 576]
        assert result[0]['radial_prediction_m'] - result[0]['depth_m'] > 0.3
    else:
        with pytest.raises(ValueError, match='optical-Z plane check failed'):
            probe.plane_samples(rows, info, 3.65)


def test_gazebo_timestamp_parser_handles_zero_fields_and_ignores_data():
    text = 'header { stamp { sec: 12 nsec: 34 } } data: "sec: 999"\n'
    text += 'header { stamp { sec: 13 } }\nheader { stamp { nsec: 50 } }'
    assert probe.gz_stamps(text) == {12_000_000_034, 13_000_000_000, 50}
