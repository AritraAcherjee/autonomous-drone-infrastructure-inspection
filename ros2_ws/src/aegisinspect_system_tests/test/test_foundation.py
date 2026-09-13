"""Offline contract checks; these do not claim Gazebo or ROS runtime validation."""
import ast
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from catkin_pkg.package import parse_package
import pytest
import xacro
import yaml

SRC = Path(__file__).resolve().parents[2]
PACKAGES = {
    'interfaces', 'description', 'sensors', 'perception', 'localization', 'mapping',
    'safety', 'navigation', 'inspection', 'diagnostics', 'bringup', 'sim', 'system_tests',
}
RESERVED_PACKAGES = {
    'sensors', 'perception', 'localization', 'safety', 'navigation',
    'inspection', 'diagnostics',
}
EXPECTED = {
    '/aegis/sensors/camera/image_raw': ('sensor_msgs/msg/Image', 'camera_optical_frame'),
    '/aegis/sensors/camera/camera_info': ('sensor_msgs/msg/CameraInfo', 'camera_optical_frame'),
    '/aegis/sensors/imu/data': ('sensor_msgs/msg/Imu', 'imu_link'),
    '/aegis/sensors/lidar/points': ('sensor_msgs/msg/PointCloud2', 'lidar_link'),
}
DEPTH_TOPIC = '/aegis/perception/depth/image'
EDGES = {
    ('base_link', 'camera_link'), ('camera_link', 'camera_optical_frame'),
    ('base_link', 'imu_link'), ('base_link', 'lidar_link'),
}


def load_yaml(relative):
    return yaml.safe_load((SRC / relative).read_text(encoding='utf-8'))


@pytest.fixture
def urdf():
    path = SRC / 'aegisinspect_description/urdf/drone.urdf.xacro'
    return ET.fromstring(xacro.process_file(str(path)).toxml())


@pytest.fixture
def model():
    return ET.parse(SRC / 'aegisinspect_sim/models/aegis_drone/model.sdf').getroot().find('model')


def test_exact_package_set():
    assert {p.parent.name for p in SRC.glob('*/package.xml')} == {
        'aegisinspect_' + name for name in PACKAGES}


@pytest.mark.parametrize('suffix', sorted(PACKAGES))
def test_package_manifests_and_install_directories(suffix):
    path = SRC / ('aegisinspect_' + suffix)
    package = parse_package(str(path / 'package.xml'))
    package.validate()
    assert package.name == path.name
    assert package.get_build_type() == 'ament_cmake'
    cmake = (path / 'CMakeLists.txt').read_text()
    assert f'project({path.name})' in cmake
    assert 'ament_package()' in cmake
    for line in cmake.splitlines():
        if line.startswith('install(DIRECTORY '):
            for directory in line.split('DIRECTORY ', 1)[1].split(' DESTINATION')[0].split():
                assert (path / directory).is_dir()
        if line.startswith('install(PROGRAMS '):
            script = line.split()[1]
            assert (path / script).is_file()
    if suffix in RESERVED_PACKAGES:
        assert {p.name for p in path.iterdir()} == {'package.xml', 'CMakeLists.txt'}


def test_all_xml_and_python_parse():
    for path in SRC.rglob('*'):
        if path.suffix in {'.xml', '.sdf', '.xacro', '.config'}:
            ET.parse(path)
        elif path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))


def test_frozen_tf_and_optical_axes(urdf):
    assert {link.attrib['name'] for link in urdf.findall('link')} == {
        'base_link', 'camera_link', 'camera_optical_frame', 'imu_link', 'lidar_link'}
    edges = set()
    for joint in urdf.findall('joint'):
        assert joint.attrib['type'] == 'fixed'
        edges.add((joint.find('parent').attrib['link'], joint.find('child').attrib['link']))
    assert edges == EDGES
    optical = urdf.find("joint[@name='camera_link_to_camera_optical_frame']/origin")
    roll, pitch, yaw = map(float, optical.attrib['rpy'].split())
    # Rz(yaw) Ry(pitch) Rx(roll): optical Z->body X, X->-Y, Y->-Z.
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    rotation = [cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr,
                sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr, -sp, cp*sr, cp*cr]
    assert rotation == pytest.approx([0, 0, 1, -1, 0, 0, 0, -1, 0], abs=1e-12)


def test_sdf_and_urdf_extrinsics_match(urdf, model):
    frames = {frame.attrib['name']: frame for frame in model.findall('frame')}
    assert set(frames) == {child for _, child in EDGES}
    for joint in urdf.findall('joint'):
        frame = frames[joint.find('child').attrib['link']]
        assert frame.attrib['attached_to'] == joint.find('parent').attrib['link']
        assert frame.find('pose').get('relative_to', frame.attrib['attached_to']) == frame.attrib['attached_to']
        origin = joint.find('origin')
        expected = list(map(float, (origin.attrib['xyz'] + ' ' + origin.attrib['rpy']).split()))
        assert list(map(float, frame.findtext('pose').split())) == pytest.approx(expected)


def test_sensor_types_frames_and_3d_lidar(model):
    sensors = {s.attrib['name']: s for s in model.findall('link/sensor')}
    assert {name: s.attrib['type'] for name, s in sensors.items()} == {
        'camera': 'rgbd_camera', 'imu': 'imu', 'lidar': 'gpu_lidar'}
    for name, header, physical in [('camera', 'camera_optical_frame', 'camera_link'),
                                    ('imu', 'imu_link', 'imu_link'), ('lidar', 'lidar_link', 'lidar_link')]:
        sensor = sensors[name]
        assert sensor.findtext('frame_id') == header
        assert sensor.find('pose').attrib['relative_to'] == physical
        assert list(map(float, sensor.findtext('pose').split())) == [0]*6
        assert float(sensor.findtext('update_rate')) > 0
    vertical = sensors['lidar'].find('lidar/scan/vertical')
    assert int(vertical.findtext('samples')) > 1
    assert float(vertical.findtext('min_angle')) < float(vertical.findtext('max_angle'))
    assert sensors['camera'].findtext('camera/image/format') == 'R8G8B8'
    assert model.findtext('static') == 'true'
    assert not model.findall('plugin')


def test_bridge_matches_sensor_outputs_and_frozen_contract(model):
    bridges = load_yaml('aegisinspect_sim/config/bridge.yaml')
    assert len(bridges) == 6
    assert {b['ros_topic_name'] for b in bridges} == set(EXPECTED) | {'/clock', DEPTH_TOPIC}
    sensors = {s.attrib['name']: s for s in model.findall('link/sensor')}
    outputs = {
        sensors['camera'].findtext('topic') + '/image': 'gz.msgs.Image',
        sensors['camera'].findtext('topic') + '/depth_image': 'gz.msgs.Image',
        sensors['camera'].findtext('camera/camera_info_topic'): 'gz.msgs.CameraInfo',
        sensors['imu'].findtext('topic'): 'gz.msgs.IMU',
        sensors['lidar'].findtext('topic') + '/points': 'gz.msgs.PointCloudPacked',
        '/world/inspection_bay/clock': 'gz.msgs.Clock',
    }
    assert len({b['gz_topic_name'] for b in bridges}) == 6
    for bridge in bridges:
        topic = bridge['ros_topic_name']
        assert bridge['direction'] == 'GZ_TO_ROS'
        assert bridge['lazy'] is False
        assert bridge['gz_type_name'] == outputs[bridge['gz_topic_name']]
        expected_type = {**{t: spec[0] for t, spec in EXPECTED.items()},
                         DEPTH_TOPIC: 'sensor_msgs/msg/Image', '/clock': 'rosgraph_msgs/msg/Clock'}
        assert bridge['ros_type_name'] == expected_type[topic]
        assert bridge['qos_profile'] == ('CLOCK' if topic == '/clock' else 'SENSOR_DATA')


def test_reserved_contracts_have_no_publishers_or_custom_messages():
    contract = load_yaml('aegisinspect_interfaces/config/contracts.yaml')
    assert contract['target'] == {'ubuntu': '26.04', 'ros': 'lyrical', 'gazebo': 'jetty', 'integration': 'ros_gz'}
    assert contract['active_sensor_topics'] == {
        topic: {'type': msg, 'frame': frame} for topic, (msg, frame) in EXPECTED.items()}
    assert {tuple(pair) for pair in contract['static_tf']} == EDGES
    assert contract['reserved_dynamic_tf'] == [['map', 'odom'], ['odom', 'base_link']]
    reserved = contract['reserved_topics']
    assert set(reserved) == {'/aegis/localization/vio/odom'}
    assert set(contract['active_perception_topics']) == {DEPTH_TOPIC}
    depth = contract['active_perception_topics'][DEPTH_TOPIC]
    assert (depth['encoding'], depth['units'], depth['quantity']) == ('32FC1', 'meters', 'optical-axis Z')
    assert (depth['type'], depth['frame'], depth['implemented']) == ('sensor_msgs/msg/Image', 'camera_optical_frame', True)
    vio = reserved['/aegis/localization/vio/odom']
    assert (vio['type'], vio['frame'], vio['child_frame'], vio['publishes_tf']) == ('nav_msgs/msg/Odometry', 'odom', 'base_link', False)
    assert all(value['implemented'] is False for value in reserved.values())
    assert contract['ground_truth_namespace'] == '/aegis/sim/ground_truth'
    assert contract['ground_truth_use'] == 'evaluation-only'
    assert not list(SRC.rglob('*.msg'))
    assert {p.relative_to(SRC).as_posix() for p in SRC.rglob('*.srv')} == {
        'aegisinspect_interfaces/srv/ProjectCamera.srv'}
    assert not list(SRC.rglob('*.action'))


def test_world_is_self_contained_and_known_pose():
    world = ET.parse(SRC / 'aegisinspect_sim/worlds/inspection_bay.sdf').getroot().find('world')
    assert world.attrib['name'] == 'inspection_bay'
    assert {m.attrib['name'] for m in world.findall('model')} == {'floor', 'wall', 'column', 'panel_a', 'panel_b'}
    for item in world.findall('include'):
        uri = item.findtext('uri')
        assert uri.startswith('model://')
        folder = SRC / 'aegisinspect_sim/models' / uri.removeprefix('model://')
        config = ET.parse(folder / 'model.config').getroot()
        assert (folder / config.findtext('sdf')).is_file()
        assert item.findtext('pose') == '0 0 1.5 0 0 0'
    assert {p.attrib['name'] for p in world.findall('plugin')} == {
        'gz::sim::systems::Physics', 'gz::sim::systems::UserCommands',
        'gz::sim::systems::SceneBroadcaster', 'gz::sim::systems::Sensors', 'gz::sim::systems::Imu'}


def test_launch_wiring_and_time_policy():
    sim = (SRC / 'aegisinspect_sim/launch/sim.launch.py').read_text()
    assert "'use_sim_time': True" in sim
    assert "'override_timestamps_with_wall_time': False" in sim
    assert "'on_exit_shutdown': 'true'" in sim
    assert 'AppendEnvironmentVariable' in sim
    assert "'--headless-rendering'" in sim
    bringup = (SRC / 'aegisinspect_bringup/launch/foundation.launch.py').read_text()
    assert "'description.launch.py', {'use_sim_time': 'true'}" in bringup
    assert "'sim.launch.py'" in bringup
    for path in SRC.glob('*/launch/*.py'):
        text = path.read_text()
        assert 'static_transform_publisher' not in text
        assert 'ground_truth' not in text
