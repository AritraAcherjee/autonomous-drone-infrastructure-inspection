"""Narrow ownership and exact-time mapping tests; no runtime processes or GT."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from builtin_interfaces.msg import Time
from geometry_msgs.msg import Point, TransformStamped
from std_msgs.msg import Header
from aegisinspect_mapping.spatial_projection import (
    CAMERA_FRAME, MAP_OWNER, ODOM_OWNER, SpatialContractError, TfOwnership, camera_to_map,
    simulation_datetime,
)


def inputs():
    header = Header(stamp=Time(sec=12, nanosec=345000000), frame_id=CAMERA_FRAME)
    response = NS(status=0, header=header, point=Point(x=1.0, y=2.0, z=3.0))
    tf = TransformStamped(header=Header(stamp=header.stamp, frame_id='map'), child_frame_id=CAMERA_FRAME)
    tf.transform.translation.x = 10.0
    tf.transform.rotation.w = 1.0
    owner = TfOwnership()
    owner.observe('map', 'odom', 'map-gid')
    owner.observe('odom', 'base_link', 'adapter-gid')
    gids = {'map-gid': MAP_OWNER, 'adapter-gid': ODOM_OWNER}
    calls = []

    def lookup(target, source, timestamp):
        calls.append((target, source, timestamp.nanoseconds))
        return tf

    return header, response, tf, owner, gids, calls, NS(lookup_transform=lookup)


def test_exact_time_metric_projection_and_frames():
    h, r, tf, owners, gids, calls, buffer = inputs()
    mapped = camera_to_map(buffer, h, r, owners, gids)
    assert calls == [('map', CAMERA_FRAME, 12_345_000_000)]
    assert mapped.map_xyz == (11., 2., 3.)
    assert mapped.frame_id == 'map' and mapped.source_frame == CAMERA_FRAME
    assert mapped.stamp_ns == mapped.transform_stamp_ns == 12_345_000_000


def test_p15_simulation_timestamp_encoding_is_exact_and_explicit():
    assert simulation_datetime(12_345_000_000).isoformat() == '1970-01-01T00:00:12.345000+00:00'


def test_map_coordinates_are_builtin_floats_for_strict_p15_schema():
    h, r, tf, owners, gids, calls, buffer = inputs()
    mapped = camera_to_map(buffer, h, r, owners, gids)
    assert all(type(value) is float for value in mapped.map_xyz)
    assert mapped.map_xyz == (11., 2., 3.)


@pytest.mark.parametrize('stamp', [0, -1000, 12_345_000_001, 12.345])
def test_p15_timestamp_cannot_be_silently_rounded_or_replaced(stamp):
    with pytest.raises(SpatialContractError): simulation_datetime(stamp)


def test_camera_optical_rotation_to_body_axes():
    h, r, tf, owners, gids, calls, buffer = inputs()
    # Optical +Z -> body +X; optical +X -> body -Y; optical +Y -> body -Z.
    q = tf.transform.rotation
    q.x, q.y, q.z, q.w = -0.5, 0.5, -0.5, 0.5
    assert camera_to_map(buffer, h, r, owners, gids).map_xyz == pytest.approx((13., -1., -2.))


def test_unavailable_exact_tf_propagates_without_retry_or_latest():
    h, r, tf, owners, gids, calls, buffer = inputs()

    def unavailable(target, source, timestamp):
        calls.append(timestamp.nanoseconds)
        raise LookupError('exact TF unavailable')

    with pytest.raises(LookupError, match='exact TF unavailable'):
        camera_to_map(NS(lookup_transform=unavailable), h, r, owners, gids)
    assert calls == [12_345_000_000]


@pytest.mark.parametrize('change', ['zero', 'frame', 'failed_response', 'response_stamp', 'returned_stamp', 'returned_frame', 'nonfinite', 'negative_depth', 'invalid_rotation'])
def test_invalid_input_fails_closed(change):
    h, r, tf, owners, gids, calls, buffer = inputs()
    if change == 'zero': h.stamp = Time()
    elif change == 'frame': h.frame_id = 'camera_link'
    elif change == 'failed_response': r.status = 5
    elif change == 'response_stamp': r.header = Header(stamp=Time(sec=99), frame_id=CAMERA_FRAME)
    elif change == 'returned_stamp': tf.header.stamp = Time(sec=99)
    elif change == 'returned_frame': tf.header.frame_id = 'odom'
    elif change == 'nonfinite': r.point.x = float('nan')
    elif change == 'negative_depth': r.point.z = -1.
    elif change == 'invalid_rotation': tf.transform.rotation.w = 0.
    with pytest.raises(SpatialContractError):
        camera_to_map(buffer, h, r, owners, gids)


def test_empty_ownership_cannot_emit_map_point():
    with pytest.raises(SpatialContractError):
        TfOwnership().require_operational({})


@pytest.mark.parametrize('edge,gid,node', [
    (('map', 'odom'), 'other-map-gid', MAP_OWNER),
    (('odom', 'base_link'), 'icp-gid', '/icp_odometry'),
    (('world', 'odom'), 'gt-gid', '/aegis/sim/sensor_bridge'),
    (('map', 'base_link'), 'bad-parent', MAP_OWNER),
])
def test_duplicate_or_conflicting_ownership_is_rejected(edge, gid, node):
    h, r, tf, owners, gids, calls, buffer = inputs()
    owners.observe(*edge, gid)
    gids[gid] = node
    with pytest.raises(SpatialContractError):
        camera_to_map(buffer, h, r, owners, gids)
    assert calls == []


def test_wrong_or_unknown_owner_is_rejected():
    h, r, tf, owners, gids, calls, buffer = inputs()
    for node in ('/icp_odometry', None):
        gids['adapter-gid'] = node
        with pytest.raises(SpatialContractError): owners.require_operational(gids)


def test_no_existing_map_owner_guard():
    owners = TfOwnership()
    owners.observe('odom', 'base_link', 'adapter')
    owners.require_no_map_owner()
    owners.observe('map', 'odom', 'preexisting-map')
    with pytest.raises(SpatialContractError): owners.require_no_map_owner()


def test_gid_required_and_repeat_messages_do_not_create_duplicate_owner():
    h, r, tf, owners, gids, calls, buffer = inputs()
    owners.observe('map', 'odom', 'map-gid')
    owners.require_operational(gids)
    with pytest.raises(SpatialContractError): owners.observe('map', 'odom', '')


def test_session_map_launch_has_one_identity_owner_no_estimator_or_gt():
    root = Path(__file__).resolve().parents[1]
    text = (root/'launch/session_map.launch.py').read_text()
    tree = ast.parse(text)
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'Node']
    assert len(nodes) == 1
    arguments = ast.literal_eval(next(k.value for k in nodes[0].keywords if k.arg == 'arguments'))
    assert dict(zip(arguments[::2], arguments[1::2])) == {
        '--x': '0', '--y': '0', '--z': '0', '--qx': '0', '--qy': '0', '--qz': '0', '--qw': '1',
        '--frame-id': 'map', '--child-frame-id': 'odom'}
    assert 'ground_truth' not in text and 'icp_odometry' not in text
    assert 'session_map_origin' in text


def test_spatial_boundary_has_no_ground_truth_or_sensor_subscription():
    source = (Path(__file__).resolve().parents[1]/'aegisinspect_mapping/spatial_projection.py').read_text()
    assert 'ground_truth' not in source
    assert 'create_subscription' not in source
    tree = ast.parse(source)
    lookups = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute) and n.func.attr == 'lookup_transform']
    assert len(lookups) == 1
    assert ast.literal_eval(lookups[0].args[0]) == 'map'
    assert isinstance(lookups[0].args[2], ast.Name) and lookups[0].args[2].id == 'requested'
