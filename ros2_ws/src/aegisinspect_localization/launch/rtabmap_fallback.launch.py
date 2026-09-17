"""Launch the Stop-B RTAB-Map RGB-D odometry fallback.

RTAB-Map owns only native odometry estimation. It does not publish
the canonical Aegis dynamic TF. The Aegis localization adapter is the
sole owner of odom -> base_link.
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    rtab_odometry = Node(
        package="rtabmap_odom",
        executable="rgbd_odometry",
        name="rgbd_odometry",
        output="screen",
        parameters=[
            {
                "use_sim_time": True,
                "frame_id": "base_link",
                "odom_frame_id": "odom",
                "publish_tf": False,
                "wait_imu_to_init": True,
                "approx_sync": True,
            }
        ],
        remappings=[
            (
                "rgb/image",
                "/aegis/sensors/camera/image_raw",
            ),
            (
                "depth/image",
                "/aegis/perception/depth/image",
            ),
            (
                "rgb/camera_info",
                "/aegis/sensors/camera/camera_info",
            ),
            (
                "imu",
                "/aegis/sensors/imu/data",
            ),
        ],
    )

    canonical_adapter = Node(
        package="aegisinspect_localization",
        executable="vio_adapter_node.py",
        name="vio_adapter",
        output="screen",
        parameters=[
            {
                "use_sim_time": True,
                "native_odom_topic": "/odom",
            }
        ],
    )

    return LaunchDescription([
        rtab_odometry,
        canonical_adapter,
    ])
