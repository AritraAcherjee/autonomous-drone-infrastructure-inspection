"""Start the deterministic inspection bay, motion adapter and one-way bridges."""

from pathlib import Path
import shlex

from ament_index_python.packages import (
    get_package_prefix,
    get_package_share_directory,
)
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
)
from launch.launch_description_sources import (
    PythonLaunchDescriptionSource,
)
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _start(context):
    share = Path(
        get_package_share_directory('aegisinspect_sim')
    )
    prefix = Path(
        get_package_prefix('aegisinspect_sim')
    )

    headless = (
        LaunchConfiguration('headless')
        .perform(context)
        .lower()
        == 'true'
    )

    args = ['-r', '-v', '3']

    if headless:
        args += ['-s', '--headless-rendering']

    args.append(
        str(share / 'worlds' / 'inspection_bay.sdf')
    )

    return [
        AppendEnvironmentVariable(
            'GZ_SIM_RESOURCE_PATH',
            str(share / 'models'),
        ),
        AppendEnvironmentVariable(
            'GZ_SIM_SYSTEM_PLUGIN_PATH',
            str(prefix / 'lib'),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                str(
                    Path(
                        get_package_share_directory(
                            'ros_gz_sim'
                        )
                    )
                    / 'launch'
                    / 'gz_sim.launch.py'
                )
            ),
            launch_arguments={
                'gz_args': shlex.join(args),
                'on_exit_shutdown': 'true',
            }.items(),
        ),
        Node(
            package='aegisinspect_sim',
            executable='motion_control_node',
            name='motion_control_node',
            namespace='/aegis/sim',
            output='screen',
            parameters=[{
                'use_sim_time': True,
            }],
        ),
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='sensor_bridge',
            namespace='/aegis/sim',
            output='screen',
            parameters=[{
                'config_file': str(
                    share / 'config' / 'bridge.yaml'
                ),
                'use_sim_time': True,
                'override_timestamps_with_wall_time': False,
            }],
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'headless',
            default_value='false',
            choices=['true', 'false'],
        ),
        OpaqueFunction(function=_start),
    ])
