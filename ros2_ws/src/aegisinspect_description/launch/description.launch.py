"""Publish only fixed sensor transforms from the Xacro description."""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import xacro


def generate_launch_description():
    path = Path(get_package_share_directory('aegisinspect_description'))
    robot = xacro.process_file(str(path / 'urdf' / 'drone.urdf.xacro')).toxml()
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        Node(
            package='robot_state_publisher', executable='robot_state_publisher',
            name='robot_state_publisher', namespace='/aegis', output='screen',
            parameters=[{
                'robot_description': robot,
                'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool),
            }],
            remappings=[('tf', '/tf'), ('tf_static', '/tf_static')],
        ),
    ])
