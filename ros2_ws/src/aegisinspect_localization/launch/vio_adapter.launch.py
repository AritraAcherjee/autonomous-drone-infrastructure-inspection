"""Launch the canonical AegisInspect localization adapter."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    native_odom_topic = LaunchConfiguration(
        "native_odom_topic"
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            "native_odom_topic",
            default_value="/odomimu",
            description=(
                "Native localization Odometry topic consumed by "
                "the canonical Aegis adapter."
            ),
        ),
        Node(
            package="aegisinspect_localization",
            executable="vio_adapter_node.py",
            name="vio_adapter",
            output="screen",
            parameters=[
                {
                    "use_sim_time": True,
                    "native_odom_topic": native_odom_topic,
                }
            ],
        ),
    ])
