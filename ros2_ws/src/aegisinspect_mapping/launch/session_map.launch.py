"""Opt-in session-local map coincident with odometry origin; no global correction.

Start only after inspecting live TF for an existing odom parent. Consumers must
validate actual map/odom TF publisher ownership before emitting mapped records.
This does not launch localization, motion, sensors, P15, or full integration.
"""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(package='tf2_ros', executable='static_transform_publisher',
             name='session_map_origin', namespace='/aegis/mapping',
             arguments=['--x', '0', '--y', '0', '--z', '0',
                        '--qx', '0', '--qy', '0', '--qz', '0', '--qw', '1',
                        '--frame-id', 'map', '--child-frame-id', 'odom'],
             parameters=[{'use_sim_time': True}], output='screen'),
    ])
