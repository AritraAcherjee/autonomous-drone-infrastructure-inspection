"""Stop-B sensor foundation only; no estimators, controllers or dynamic TF."""
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def include(package, filename, arguments):
    path = Path(get_package_share_directory(package)) / 'launch' / filename
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(path)), launch_arguments=arguments.items())


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('headless', default_value='false', choices=['true', 'false']),
        include('aegisinspect_description', 'description.launch.py', {'use_sim_time': 'true'}),
        include('aegisinspect_sim', 'sim.launch.py', {'headless': LaunchConfiguration('headless')}),
    ])
