"""P19 no-START readiness stack. Contains no detector or P15 nodes."""

from pathlib import Path
import shlex

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument, EmitEvent, IncludeLaunchDescription, OpaqueFunction, PrependEnvironmentVariable, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def include(package, filename, arguments=None):
    path = Path(get_package_share_directory(package)) / "launch" / filename
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(path)),
        launch_arguments=(arguments or {}).items(),
    )


def start(context):
    share = Path(get_package_share_directory("aegisinspect_p19_eval"))
    prefix = Path(get_package_prefix("aegisinspect_p19_eval"))
    sim_prefix = Path(get_package_prefix("aegisinspect_sim"))
    instrumented_prefix = Path(LaunchConfiguration("instrumented_gazebo_prefix").perform(context))
    instrumented_plugin = instrumented_prefix / "lib" / "gz-sim-10" / "plugins" / "libgz-sim-sensors-system.so.10.5.0"
    if not instrumented_plugin.is_file():
        raise RuntimeError(f"version-matched instrumented Sensors system absent: {instrumented_plugin}")
    headless = LaunchConfiguration("headless").perform(context).lower() == "true"
    args = ["-r", "-v", "3"]
    if headless:
        args += ["-s", "--headless-rendering"]
    args.append(str(share / "worlds" / "p19_correspondence_readiness_batch_v1.sdf"))
    collector = Node(package="aegisinspect_p19_eval", executable="readiness_node.py",
                     name="readiness_collector", namespace="/aegis/p19_eval", output="screen",
                     parameters=[{"use_sim_time": True,
                                  "output_directory": LaunchConfiguration("output_directory"),
                                  "manifest_path": LaunchConfiguration("manifest_path"),
                                  "manifest_seal_path": LaunchConfiguration("manifest_seal_path")}])
    return [
        AppendEnvironmentVariable("GZ_SIM_RESOURCE_PATH", str(share / "models")),
        PrependEnvironmentVariable("LD_LIBRARY_PATH", str(prefix / "lib")),
        PrependEnvironmentVariable("LD_LIBRARY_PATH", str(instrumented_prefix / "lib")),
        PrependEnvironmentVariable("GZ_SIM_SYSTEM_PLUGIN_PATH", str(instrumented_prefix / "lib" / "gz-sim-10" / "plugins")),
        AppendEnvironmentVariable("GZ_SIM_SYSTEM_PLUGIN_PATH", str(prefix / "lib")),
        AppendEnvironmentVariable("GZ_SIM_SYSTEM_PLUGIN_PATH", str(sim_prefix / "lib")),
        AppendEnvironmentVariable("P19_CERTIFICATE_RUN_ID", "P19-NO-START-READINESS-002"),
        include("ros_gz_sim", "gz_sim.launch.py", {
            "gz_args": shlex.join(args), "on_exit_shutdown": "true"}),
        Node(package="aegisinspect_sim", executable="motion_control_node",
             name="motion_control_node", namespace="/aegis/sim", output="screen",
             parameters=[{"use_sim_time": True}]),
        Node(package="ros_gz_bridge", executable="parameter_bridge",
             name="p19_sensor_bridge", namespace="/aegis/p19_eval", output="screen",
             parameters=[{"config_file": str(share / "config" / "bridge.yaml"),
                          "use_sim_time": True,
                          "override_timestamps_with_wall_time": False}]),
        Node(package="ros_gz_bridge", executable="parameter_bridge",
             name="p19_batch_certificate_bridge", namespace="/aegis/p19_eval", output="screen",
             parameters=[{"config_file": str(share / "config" / "sensor_batch_bridge.yaml"),
                          "use_sim_time": True,
                          "override_timestamps_with_wall_time": False}]),
        include("aegisinspect_description", "description.launch.py", {"use_sim_time": "true"}),
        include("aegisinspect_localization", "rtabmap_icp_fallback.launch.py"),
        include("aegisinspect_mapping", "session_map.launch.py"),
        collector,
        RegisterEventHandler(OnProcessExit(
            target_action=collector,
            on_exit=[EmitEvent(event=Shutdown(reason="bounded readiness collector exited"))],
        )),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("headless", default_value="true", choices=["true", "false"]),
        DeclareLaunchArgument("output_directory"),
        DeclareLaunchArgument("manifest_path"),
        DeclareLaunchArgument("manifest_seal_path"),
        DeclareLaunchArgument("instrumented_gazebo_prefix"),
        OpaqueFunction(function=start),
    ])
