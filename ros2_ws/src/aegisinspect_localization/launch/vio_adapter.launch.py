"""Launch the canonical AegisInspect VIO adapter."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="aegisinspect_localization",
            executable="vio_adapter_node.py",
            name="vio_adapter",
            output="screen",
            parameters=[{"use_sim_time": True}],
        ),
    ])
