"""Fail-closed Stop-B camera-to-session-map boundary; no estimator or GT input."""
from collections import defaultdict
from dataclasses import dataclass
from math import isfinite


MAP_OWNER = '/aegis/mapping/session_map_origin'
ODOM_OWNER = '/vio_adapter'
CAMERA_FRAME = 'camera_optical_frame'


class SpatialContractError(ValueError):
    """No mapped observation may be emitted for this input/ownership state."""


class TfOwnership:
    """Attribute actual traffic by DDS publisher GID, never endpoint counts alone."""

    def __init__(self):
        self.edges = defaultdict(set)

    def observe(self, parent, child, publisher_gid):
        if child in ('odom', 'base_link'):
            if not publisher_gid:
                raise SpatialContractError('TF_PUBLISHER_GID_MISSING')
            self.edges[(parent, child)].add(publisher_gid)

    def require_no_map_owner(self):
        if any(child == 'odom' for _, child in self.edges):
            raise SpatialContractError('EXISTING_ODOM_PARENT_OWNER')

    def require_operational(self, gid_owners):
        expected = {('map', 'odom'): MAP_OWNER, ('odom', 'base_link'): ODOM_OWNER}
        if set(self.edges) != set(expected):
            raise SpatialContractError('MISSING_OR_CONFLICTING_OPERATIONAL_TF_EDGE')
        for edge, node in expected.items():
            gids = self.edges[edge]
            if len(gids) != 1:
                raise SpatialContractError('DUPLICATE_OPERATIONAL_TF_OWNER')
            if gid_owners.get(next(iter(gids))) != node:
                raise SpatialContractError('UNEXPECTED_OR_UNKNOWN_OPERATIONAL_TF_OWNER')


@dataclass(frozen=True)
class MapPoint:
    stamp_ns: int
    source_frame: str
    frame_id: str
    camera_xyz: tuple[float, float, float]
    map_xyz: tuple[float, float, float]
    translation: tuple[float, float, float]
    quaternion_xyzw: tuple[float, float, float, float]
    transform_stamp_ns: int


def simulation_datetime(stamp_ns):
    """Exact P15 datetime encoding of simulation seconds, never observed UTC."""
    from datetime import datetime, timedelta, timezone
    if type(stamp_ns) is not int or stamp_ns <= 0 or stamp_ns % 1000:
        raise SpatialContractError('P15_TIMESTAMP_NOT_EXACTLY_REPRESENTABLE')
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=stamp_ns // 1000)


def camera_to_map(buffer, observation_header, camera_response, ownership, gid_owners):
    """Use only the successful 08 response and this observation's exact tf2 time.

    Unavailable TF propagates as an error. There is no latest/now fallback.
    tf2 treats zero as latest, so literal zero observations are rejected here
    (08's camera-only service may independently accept zero as a literal stamp).
    """
    from geometry_msgs.msg import PointStamped
    from rclpy.clock import ClockType
    from rclpy.time import Time
    from tf2_geometry_msgs import do_transform_point

    ownership.require_operational(gid_owners)
    s = observation_header.stamp
    if s.sec < 0 or not 0 <= s.nanosec < 1_000_000_000:
        raise SpatialContractError('INVALID_OBSERVATION_TIMESTAMP')
    stamp_ns = s.sec * 1_000_000_000 + s.nanosec
    if stamp_ns == 0:
        raise SpatialContractError('ZERO_TIMESTAMP_WOULD_MEAN_LATEST_TF')
    if observation_header.frame_id != CAMERA_FRAME:
        raise SpatialContractError('OBSERVATION_OPTICAL_FRAME_MISMATCH')
    response_stamp = camera_response.header.stamp
    if (camera_response.status != 0 or camera_response.header.frame_id != CAMERA_FRAME
            or (response_stamp.sec, response_stamp.nanosec) != (s.sec, s.nanosec)):
        raise SpatialContractError('CAMERA_RESPONSE_STATUS_FRAME_OR_STAMP_MISMATCH')
    p = camera_response.point
    xyz = (p.x, p.y, p.z)
    if not all(isfinite(v) for v in xyz) or p.z <= 0:
        raise SpatialContractError('INVALID_METRIC_CAMERA_POINT')
    requested = Time.from_msg(s, clock_type=ClockType.ROS_TIME)
    transform = buffer.lookup_transform('map', CAMERA_FRAME, requested)
    ts = transform.header.stamp
    transform_ns = ts.sec * 1_000_000_000 + ts.nanosec
    if (transform.header.frame_id != 'map' or transform.child_frame_id != CAMERA_FRAME
            or transform_ns != stamp_ns):
        raise SpatialContractError('RETURNED_TRANSFORM_FRAME_OR_STAMP_MISMATCH')
    t, q = transform.transform.translation, transform.transform.rotation
    translation, rotation = (t.x, t.y, t.z), (q.x, q.y, q.z, q.w)
    if (not all(isfinite(v) for v in translation + rotation)
            or abs(sum(v*v for v in rotation) - 1.0) > 1e-6):
        raise SpatialContractError('INVALID_RIGID_TRANSFORM')
    point = PointStamped(header=observation_header, point=p)
    mapped = do_transform_point(point, transform).point
    # tf2_geometry_msgs may return NumPy scalar fields. P15's strict domain
    # accepts built-in numbers only; normalize representation, not coordinates.
    result = tuple(float(v) for v in (mapped.x, mapped.y, mapped.z))
    if not all(isfinite(v) for v in result):
        raise SpatialContractError('NONFINITE_MAP_POINT')
    return MapPoint(stamp_ns, CAMERA_FRAME, 'map', xyz, result,
                    translation, rotation, transform_ns)
