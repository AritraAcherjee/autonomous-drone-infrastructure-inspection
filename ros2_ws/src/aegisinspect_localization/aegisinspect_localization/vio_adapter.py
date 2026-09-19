"""Fail-closed OpenVINS odometry canonicalization for AegisInspect."""

from copy import deepcopy
import math

from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry


NATIVE_ODOM_TOPIC = "/odomimu"
CANONICAL_ODOM_TOPIC = "/aegis/localization/vio/odom"

ODOM_FRAME = "odom"
BASE_FRAME = "base_link"


def _finite(values):
    return all(math.isfinite(float(value)) for value in values)


def _stamp_is_usable(stamp):
    sec = int(stamp.sec)
    nanosec = int(stamp.nanosec)
    return sec >= 0 and 0 <= nanosec < 1_000_000_000


def odometry_is_valid(msg):
    """Return True only for a usable finite native OpenVINS sample."""
    if not _stamp_is_usable(msg.header.stamp):
        return False

    position = msg.pose.pose.position
    orientation = msg.pose.pose.orientation
    linear = msg.twist.twist.linear
    angular = msg.twist.twist.angular

    if not _finite((position.x, position.y, position.z)):
        return False

    quaternion = (
        orientation.x,
        orientation.y,
        orientation.z,
        orientation.w,
    )
    if not _finite(quaternion):
        return False

    # Reject a degenerate quaternion, but do not normalize or otherwise
    # modify an estimator-provided valid quaternion.
    norm_sq = sum(float(value) * float(value) for value in quaternion)
    if norm_sq <= 1.0e-12:
        return False

    if not _finite((linear.x, linear.y, linear.z)):
        return False

    if not _finite((angular.x, angular.y, angular.z)):
        return False

    if not _finite(msg.pose.covariance):
        return False

    if not _finite(msg.twist.covariance):
        return False

    return True


def canonicalize_odometry(native):
    """Return canonical Aegis odometry, or None for an invalid sample.

    base_link -> imu_link is identity for the frozen MVP, so estimator
    pose, velocity and covariance are preserved exactly. Only the frame
    identifiers are canonicalized.
    """
    if not odometry_is_valid(native):
        return None

    canonical = deepcopy(native)
    canonical.header.frame_id = ODOM_FRAME
    canonical.child_frame_id = BASE_FRAME
    return canonical


def transform_from_odometry(canonical):
    """Create odom -> base_link TF using the exact odometry timestamp."""
    transform = TransformStamped()

    transform.header.stamp.sec = canonical.header.stamp.sec
    transform.header.stamp.nanosec = canonical.header.stamp.nanosec
    transform.header.frame_id = ODOM_FRAME
    transform.child_frame_id = BASE_FRAME

    transform.transform.translation.x = canonical.pose.pose.position.x
    transform.transform.translation.y = canonical.pose.pose.position.y
    transform.transform.translation.z = canonical.pose.pose.position.z

    transform.transform.rotation.x = canonical.pose.pose.orientation.x
    transform.transform.rotation.y = canonical.pose.pose.orientation.y
    transform.transform.rotation.z = canonical.pose.pose.orientation.z
    transform.transform.rotation.w = canonical.pose.pose.orientation.w

    return transform
