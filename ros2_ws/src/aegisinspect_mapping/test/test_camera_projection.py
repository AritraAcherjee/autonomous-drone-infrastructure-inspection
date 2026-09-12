"""Deterministic projection and ROS-shaped adapter checks, with no ROS imports."""
from copy import deepcopy
from math import inf, nan, isnan
from pathlib import Path
import struct
from types import SimpleNamespace as NS

import pytest

from aegisinspect_mapping.camera_projection import (
    FRAME, Status, ProjectionCache, decode_depth, fill_response, project,
)

def header(sec=17, nanosec=123456789, frame_id=FRAME):
    return NS(stamp=NS(sec=sec, nanosec=nanosec), frame_id=frame_id)


def inputs(values=None, width=4, height=4):
    values = [2.] * (width * height) if values is None else values
    depth = NS(header=header(), width=width, height=height, step=width * 4,
               encoding='32FC1', is_bigendian=0,
               data=struct.pack('<' + str(len(values)) + 'f', *values))
    info = NS(header=header(), width=width, height=height,
              k=[2., 0., 2., 0., 4., 2., 0., 0., 1.],
              p=[2., 0., 2., 0., 0., 4., 2., 0., 0., 0., 1., 0.],
              r=[1., 0., 0., 0., 1., 0., 0., 0., 1.], d=[],
              distortion_model='plumb_bob', binning_x=0, binning_y=0,
              roi=NS(x_offset=0, y_offset=0, width=0, height=0, do_rectify=False))
    request = NS(header=header(), mode=0, u=2, v=2, left=0, top=0, right=4, bottom=4)
    return request, depth, info


def assert_failure(result, status):
    assert result.status == status
    assert result.xyz is None and result.pixel is None and result.frame_id == ''
    response = NS(header=header(), point=NS(x=0., y=0., z=0.))
    fill_response(result, response, 0.25)
    assert response.status == int(status)
    assert all(isnan(x) for x in (response.point.x, response.point.y, response.point.z,
                                  response.sample_u, response.sample_v))
    assert response.header.frame_id == ''
    assert (response.header.stamp.sec, response.header.stamp.nanosec) == result.stamp


@pytest.mark.parametrize('u,v,xyz', [(2, 2, (0, 0, 2)), (3, 0, (1, -1, 2)),
                                   (0, 3, (-2, .5, 2))])
def test_pixel_and_wire_result(u, v, xyz):
    request, depth, info = inputs()
    request.u, request.v = u, v
    result = project(request, depth, info)
    assert result.status == Status.SUCCESS
    assert result.xyz == pytest.approx(xyz)
    assert result.frame_id == FRAME
    assert result.stamp == (17, 123456789)
    response = NS(header=header(99), point=NS(x=0, y=0, z=0))
    fill_response(result, response, .25)
    assert response.header.stamp.sec == 17
    assert response.header.stamp.nanosec == 123456789
    assert response.header.frame_id == FRAME
    assert (response.point.x, response.point.y, response.point.z) == pytest.approx(xyz)
    assert (response.sample_u, response.sample_v) == (u, v)
    assert response.latency_ms == .25


@pytest.mark.parametrize('value', [nan, inf, -inf, 0., -1.])
def test_invalid_pixel_never_uses_neighbor(value):
    request, depth, info = inputs([value] + [2.] * 15)
    request.u = request.v = 0
    assert_failure(project(request, depth, info), Status.NO_VALID_DEPTH)


@pytest.mark.parametrize('u,v', [(-1, 0), (0, -1), (4, 0), (0, 4)])
def test_pixel_bounds(u, v):
    request, depth, info = inputs()
    request.u, request.v = u, v
    assert_failure(project(request, depth, info), Status.OUT_OF_BOUNDS)


def test_roi_median_filters_border_outlier_and_preserves_stamp():
    request, depth, info = inputs([100, 100, 100, 100, 100, 2, 3, 100,
                                   100, 4, 99, 100, 100, 100, 100, 100])
    request.mode = 1
    result = project(request, depth, info)
    assert result.status == Status.SUCCESS
    assert result.pixel == (1.5, 1.5)
    assert result.xyz == pytest.approx((-.875, -.4375, 3.5))
    assert result.stamp == (17, 123456789)


@pytest.mark.parametrize('central,status', [([0, 0, 0, 0], Status.NO_VALID_DEPTH),
                                            ([2, 0, 0, 0], Status.INSUFFICIENT_DEPTH)])
def test_roi_depth_failure(central, status):
    values = [2.] * 16
    for index, value in zip((5, 6, 9, 10), central):
        values[index] = value
    request, depth, info = inputs(values)
    request.mode = 1
    assert_failure(project(request, depth, info), status)


def test_roi_threshold_equality_and_configuration():
    request, depth, info = inputs([2, 0, 0, 0] * 4)
    request.mode = 1
    result = project(request, depth, info, central_fraction=1, min_valid_fraction=.25)
    assert result.status == Status.SUCCESS and result.xyz[2] == 2
    assert_failure(project(request, depth, info, central_fraction=1, min_valid_fraction=.26),
                   Status.INSUFFICIENT_DEPTH)


@pytest.mark.parametrize('bounds,status', [
    ((0, 0, 0, 4), Status.INVALID_REQUEST), ((3, 0, 2, 4), Status.INVALID_REQUEST),
    ((0, 3, 4, 2), Status.INVALID_REQUEST), ((-1, 0, 4, 4), Status.OUT_OF_BOUNDS),
    ((0, 0, 5, 4), Status.OUT_OF_BOUNDS), ((0, -1, 4, 4), Status.OUT_OF_BOUNDS),
    ((0, 0, 4, 5), Status.OUT_OF_BOUNDS), ((0.5, 0, 4, 4), Status.INVALID_REQUEST),
])
def test_roi_bounds(bounds, status):
    request, depth, info = inputs()
    request.mode = 1
    request.left, request.top, request.right, request.bottom = bounds
    assert_failure(project(request, depth, info), status)


@pytest.mark.parametrize('index,values', [(0, [0, -1, nan, inf, -inf]),
                                         (4, [0, -1, nan, inf, -inf]),
                                         (2, [nan, inf]), (5, [nan, inf])])
def test_invalid_intrinsics(index, values):
    for value in values:
        request, depth, info = inputs()
        info.k[index] = value
        assert_failure(project(request, depth, info), Status.INVALID_CAMERA_MODEL)


@pytest.mark.parametrize('field,value', [
    ('width', 3), ('height', 0), ('k', [1]), ('k', [2, 1, 2, 0, 4, 2, 0, 0, 1]),
    ('d', [.1]), ('d', [nan]), ('distortion_model', 'equidistant'),
    ('binning_x', 2), ('binning_y', 2), ('p', [0]*11), ('r', [nan]*9),
    ('r', [-1, 0, 0, 0, 1, 0, 0, 0, 1]), ('p', [1]*12),
])
def test_camera_geometry_rejected(field, value):
    request, depth, info = inputs()
    setattr(info, field, value)
    assert_failure(project(request, depth, info), Status.INVALID_CAMERA_MODEL)


@pytest.mark.parametrize('field,value', [('x_offset', 1), ('y_offset', 1),
                                         ('do_rectify', True), ('width', 2)])
def test_camera_roi_rejected(field, value):
    request, depth, info = inputs()
    setattr(info.roi, field, value)
    assert_failure(project(request, depth, info), Status.INVALID_CAMERA_MODEL)


@pytest.mark.parametrize('which', [0, 1, 2])
def test_timestamp_mismatch(which):
    data = inputs()
    data[which].header.stamp.nanosec += 1
    assert_failure(project(*data), Status.TIMESTAMP_MISMATCH)


@pytest.mark.parametrize('which', [0, 1, 2])
@pytest.mark.parametrize('frame', ['', 'camera_link', 'base_link', 'odom', 'map'])
def test_frame_mismatch(which, frame):
    data = inputs()
    data[which].header.frame_id = frame
    assert_failure(project(*data), Status.FRAME_MISMATCH)


@pytest.mark.parametrize('field,value', [('encoding', '16UC1'), ('data', b''),
                                         ('step', 1), ('is_bigendian', 2)])
def test_invalid_image(field, value):
    request, depth, info = inputs()
    setattr(depth, field, value)
    assert_failure(project(request, depth, info), Status.INVALID_DEPTH_IMAGE)


@pytest.mark.parametrize('endian', [0, 1])
def test_endian_padding_decode(endian):
    request, depth, info = inputs()
    depth.is_bigendian = endian
    depth.step = 20
    depth.data = (struct.pack(('>' if endian else '<') + '4f', 2, nan, inf, -inf) + b'PAD!') * 4
    rows = decode_depth(depth)
    assert rows[0][0] == 2 and isnan(rows[0][1])
    assert rows[0][2:] == (inf, -inf)
    request.u = request.v = 0
    assert project(request, depth, info).xyz == (-2, -1, 2)


@pytest.mark.parametrize('mode', [2, 255])
def test_unknown_mode(mode):
    request, depth, info = inputs()
    request.mode = mode
    assert_failure(project(request, depth, info), Status.INVALID_REQUEST)


def test_projection_overflow():
    request, depth, info = inputs()
    info.k[0] = 1e-320
    info.p = [0.] * 12
    request.u = 0
    assert_failure(project(request, depth, info), Status.NUMERICAL_ERROR)


def test_exact_cache_arrival_eviction_and_counters():
    request, depth, info = inputs()
    cache = ProjectionCache(capacity=1)
    assert_failure(cache.handle(request), Status.TIMESTAMP_MISMATCH)
    cache.add_info(info)
    assert_failure(cache.handle(request), Status.TIMESTAMP_MISMATCH)
    cache.add_depth(depth)
    assert cache.handle(request).xyz == (0, 0, 2)
    newer = deepcopy(depth)
    newer.header.stamp.sec += 1
    cache.add_depth(newer)
    assert_failure(cache.handle(request), Status.TIMESTAMP_MISMATCH)
    assert len(cache.depth) == 1
    assert cache.counts == {'TIMESTAMP_MISMATCH': 3, 'SUCCESS': 1}
    assert cache.last_latency_ms >= 0


def test_cache_does_not_use_latest_info_or_depth():
    request, depth, info = inputs()
    cache = ProjectionCache()
    cache.add_depth(depth)
    late_info = deepcopy(info)
    late_info.header.stamp.nanosec += 1
    cache.add_info(late_info)
    assert_failure(cache.handle(request), Status.TIMESTAMP_MISMATCH)
    cache.add_info(info)
    request.mode = 1
    assert cache.handle(request).status == Status.SUCCESS


@pytest.mark.parametrize('kwargs', [
    {'capacity': 0}, {'capacity': 1.5}, {'central_fraction': 0},
    {'central_fraction': nan}, {'central_fraction': 1.1},
    {'min_valid_fraction': -.1}, {'min_valid_fraction': inf},
])
def test_configuration_validation(kwargs):
    with pytest.raises(ValueError):
        ProjectionCache(**kwargs)


def test_wire_status_constants_match_core():
    service = (Path(__file__).resolve().parents[2] /
               'aegisinspect_interfaces/srv/ProjectCamera.srv').read_text()
    for status in Status:
        assert f'uint8 {status.name}={status.value}' in service.split('---')[1]


def test_zero_observation_stamp_is_not_latest_or_restamped():
    request, depth, info = inputs()
    for message in (request, depth, info):
        message.header.stamp.sec = message.header.stamp.nanosec = 0
    assert project(request, depth, info).stamp == (0, 0)


def test_bad_direct_sampling_configuration():
    assert_failure(project(*inputs(), central_fraction=0), Status.INVALID_REQUEST)


@pytest.mark.parametrize('case,expected', [
    ('pixel', Status.SUCCESS), ('roi', Status.SUCCESS),
    ('depth', Status.NO_VALID_DEPTH), ('camera', Status.INVALID_CAMERA_MODEL),
    ('bounds', Status.OUT_OF_BOUNDS), ('timestamp', Status.TIMESTAMP_MISMATCH),
    ('frame', Status.FRAME_MISMATCH),
])
def test_actual_node_callback_with_ros_shaped_transport(monkeypatch, case, expected):
    """Exercise production wiring/callback; transport is a test double, not ROS."""
    import importlib.util
    import sys
    import types

    class NodeDouble:
        def __init__(self, *args, **kwargs):
            self.parameters = {}
            self.subscriptions = {}

        def declare_parameter(self, name, value):
            self.parameters[name] = value

        def get_parameter(self, name):
            return NS(value=self.parameters[name])

        def create_subscription(self, kind, topic, callback, qos):
            self.subscriptions[topic] = callback
            return callback

        def create_service(self, kind, name, callback):
            assert name == '/aegis/mapping/project_camera'
            return callback

        def create_timer(self, interval, callback):
            return callback

    for name, attributes in {
        'rclpy': {}, 'rclpy.node': {'Node': NodeDouble},
        'rclpy.qos': {'qos_profile_sensor_data': object()},
        'sensor_msgs': {}, 'sensor_msgs.msg': {'CameraInfo': object, 'Image': object},
        'aegisinspect_interfaces': {},
        'aegisinspect_interfaces.srv': {'ProjectCamera': object},
    }.items():
        module = types.ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    path = Path(__file__).resolve().parents[1] / 'scripts/camera_projection_node.py'
    spec = importlib.util.spec_from_file_location('projection_node_under_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    node = module.CameraProjectionNode()
    request, depth, info = inputs([0.] * 16 if case == 'depth' else None)
    if case == 'roi':
        request.mode = 1
    elif case == 'camera':
        info.k[0] = 0
    elif case == 'bounds':
        request.u = -1
    elif case == 'timestamp':
        request.header.stamp.nanosec += 1
    elif case == 'frame':
        depth.header.frame_id = 'base_link'
    node.subscriptions['/aegis/perception/depth/image'](depth)
    node.subscriptions['/aegis/sensors/camera/camera_info'](info)
    response = NS(header=header(), point=NS(x=0, y=0, z=0))
    assert node.service(request, response) is response
    assert response.status == expected
    assert response.header.stamp.nanosec == request.header.stamp.nanosec
    if expected == Status.SUCCESS:
        assert response.point.z == 2 and response.header.frame_id == FRAME
    else:
        assert isnan(response.point.x) and isnan(response.point.y) and isnan(response.point.z)
        assert response.header.frame_id == ''


def test_node_preserves_inherited_handle():
    """The service callback must not shadow rclpy Node.handle."""
    import ast

    path = Path(__file__).resolve().parents[1] / 'scripts/camera_projection_node.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    node_class = next(node for node in tree.body
                      if isinstance(node, ast.ClassDef) and node.name == 'CameraProjectionNode')
    # Load only the class definition, without importing or constructing rclpy.
    namespace = {'Node': object, '__name__': 'projection_node_contract_test'}
    exec(compile(ast.Module(body=[node_class], type_ignores=[]), str(path), 'exec'), namespace)
    assert 'handle' not in vars(namespace['CameraProjectionNode'])
