from copy import deepcopy
import math
from pathlib import Path

import pytest
from nav_msgs.msg import Odometry

from aegisinspect_localization.vio_adapter import (
    BASE_FRAME,
    CANONICAL_ODOM_TOPIC,
    NATIVE_ODOM_TOPIC,
    ODOM_FRAME,
    canonicalize_odometry,
    odometry_is_valid,
    transform_from_odometry,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_native():
    msg = Odometry()

    msg.header.stamp.sec = 12
    msg.header.stamp.nanosec = 345678901
    msg.header.frame_id = "global"
    msg.child_frame_id = "imu"

    msg.pose.pose.position.x = 1.25
    msg.pose.pose.position.y = -2.5
    msg.pose.pose.position.z = 3.75

    msg.pose.pose.orientation.x = 0.0
    msg.pose.pose.orientation.y = 0.0
    msg.pose.pose.orientation.z = 0.0
    msg.pose.pose.orientation.w = 1.0

    msg.twist.twist.linear.x = 0.5
    msg.twist.twist.linear.y = -0.25
    msg.twist.twist.linear.z = 0.125

    msg.twist.twist.angular.x = 0.01
    msg.twist.twist.angular.y = -0.02
    msg.twist.twist.angular.z = 0.03

    msg.pose.covariance = [float(index) + 0.125 for index in range(36)]
    msg.twist.covariance = [float(index) + 100.125 for index in range(36)]

    return msg


def set_nested(obj, path, value):
    fields = path.split(".")
    target = obj

    for field in fields[:-1]:
        target = getattr(target, field)

    setattr(target, fields[-1], value)


def test_topics_are_frozen():
    assert NATIVE_ODOM_TOPIC == "/odomimu"
    assert CANONICAL_ODOM_TOPIC == "/aegis/localization/vio/odom"


def test_valid_native_odom_becomes_canonical_without_state_mutation():
    native = valid_native()
    original = deepcopy(native)

    canonical = canonicalize_odometry(native)

    assert canonical is not None
    assert canonical.header.frame_id == ODOM_FRAME == "odom"
    assert canonical.child_frame_id == BASE_FRAME == "base_link"

    assert canonical.header.stamp.sec == original.header.stamp.sec
    assert canonical.header.stamp.nanosec == original.header.stamp.nanosec

    assert canonical.pose.pose == original.pose.pose
    assert canonical.twist.twist == original.twist.twist

    assert list(canonical.pose.covariance) == list(original.pose.covariance)
    assert list(canonical.twist.covariance) == list(original.twist.covariance)

    # Input message itself must not be rewritten.
    assert native.header.frame_id == "global"
    assert native.child_frame_id == "imu"


def test_tf_uses_exact_same_pose_and_timestamp():
    canonical = canonicalize_odometry(valid_native())
    transform = transform_from_odometry(canonical)

    assert transform.header.frame_id == "odom"
    assert transform.child_frame_id == "base_link"

    assert transform.header.stamp.sec == canonical.header.stamp.sec
    assert transform.header.stamp.nanosec == canonical.header.stamp.nanosec

    assert transform.transform.translation.x == canonical.pose.pose.position.x
    assert transform.transform.translation.y == canonical.pose.pose.position.y
    assert transform.transform.translation.z == canonical.pose.pose.position.z

    assert transform.transform.rotation.x == canonical.pose.pose.orientation.x
    assert transform.transform.rotation.y == canonical.pose.pose.orientation.y
    assert transform.transform.rotation.z == canonical.pose.pose.orientation.z
    assert transform.transform.rotation.w == canonical.pose.pose.orientation.w


@pytest.mark.parametrize(
    "field",
    [
        "pose.pose.position.x",
        "pose.pose.position.y",
        "pose.pose.position.z",
        "pose.pose.orientation.x",
        "pose.pose.orientation.y",
        "pose.pose.orientation.z",
        "pose.pose.orientation.w",
        "twist.twist.linear.x",
        "twist.twist.linear.y",
        "twist.twist.linear.z",
        "twist.twist.angular.x",
        "twist.twist.angular.y",
        "twist.twist.angular.z",
    ],
)
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_nonfinite_state_is_rejected(field, bad_value):
    msg = valid_native()
    set_nested(msg, field, bad_value)

    assert not odometry_is_valid(msg)
    assert canonicalize_odometry(msg) is None


@pytest.mark.parametrize("which", ["pose", "twist"])
@pytest.mark.parametrize("bad_value", [float("nan"), float("inf")])
def test_nonfinite_covariance_is_rejected(which, bad_value):
    msg = valid_native()

    covariance = getattr(msg, which).covariance
    covariance[17] = bad_value

    assert not odometry_is_valid(msg)
    assert canonicalize_odometry(msg) is None


def test_zero_norm_quaternion_is_rejected():
    msg = valid_native()

    msg.pose.pose.orientation.x = 0.0
    msg.pose.pose.orientation.y = 0.0
    msg.pose.pose.orientation.z = 0.0
    msg.pose.pose.orientation.w = 0.0

    assert not odometry_is_valid(msg)
    assert canonicalize_odometry(msg) is None


def test_negative_timestamp_is_rejected():
    msg = valid_native()
    msg.header.stamp.sec = -1

    assert not odometry_is_valid(msg)
    assert canonicalize_odometry(msg) is None


def test_openvins_native_tf_is_disabled_and_sim_time_enabled():
    text = (
        ROOT
        / "config"
        / "openvins"
        / "aegis_mvp"
        / "openvins_ros_params.yaml"
    ).read_text(encoding="utf-8")

    assert "use_sim_time: true" in text
    assert "publish_global_to_imu_tf: false" in text
    assert "publish_calibration_tf: false" in text
    assert 'path_gt: ""' in text


def test_launch_keeps_sim_time_and_has_no_ground_truth_dependency():
    text = (ROOT / "launch" / "vio_adapter.launch.py").read_text(
        encoding="utf-8"
    )

    assert 'package="aegisinspect_localization"' in text
    assert 'executable="vio_adapter_node.py"' in text
    assert '"use_sim_time": True' in text
    assert "ground_truth" not in text


def test_adapter_source_has_only_odom_to_base_link_tf_contract():
    text = (
        ROOT
        / "aegisinspect_localization"
        / "vio_adapter.py"
    ).read_text(encoding="utf-8")

    assert 'ODOM_FRAME = "odom"' in text
    assert 'BASE_FRAME = "base_link"' in text
    assert "ground_truth" not in text
    assert '"map"' not in text


def test_package_activation_files_exist():
    assert (ROOT / "package.xml").is_file()
    assert (ROOT / "CMakeLists.txt").is_file()
    assert (ROOT / "scripts" / "vio_adapter_node.py").is_file()
    assert (ROOT / "launch" / "vio_adapter.launch.py").is_file()
