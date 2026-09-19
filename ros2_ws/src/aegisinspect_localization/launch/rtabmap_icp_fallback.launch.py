"""Launch the Stop-B RTAB-Map LiDAR ICP odometry fallback.

RTAB-Map owns only native odometry estimation. It does not publish
the canonical Aegis dynamic TF. The Aegis localization adapter is the
sole owner of odom -> base_link.
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    icp_odometry = Node(
        package="rtabmap_odom",
        executable="icp_odometry",
        name="icp_odometry",
        output="screen",
        parameters=[
            {
                "use_sim_time": True,
                "frame_id": "base_link",
                "odom_frame_id": "odom",
                "publish_tf": False,
            }
        ],
        remappings=[
            ("scan_cloud", "/aegis/sensors/lidar/points"),
            ("odom", "/odom"),
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
        icp_odometry,
        canonical_adapter,
    ])
