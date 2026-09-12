"""Opt-in Phase 3 camera-only projection; start foundation separately."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='aegisinspect_mapping', executable='camera_projection_node.py',
             parameters=[{'use_sim_time': True}], output='screen'),
    ])
