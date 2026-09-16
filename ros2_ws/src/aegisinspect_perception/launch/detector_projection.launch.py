"""Launch DET-FINAL-v1 detector-to-camera-frame projection."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "model_path",
                description=(
                    "Absolute path to frozen "
                    "DET-FINAL-v1 best.pt"
                ),
            ),
            DeclareLaunchArgument(
                "confidence_floor",
                default_value="0.001",
                description=(
                    "Integration collection floor; "
                    "not a deployment threshold."
                ),
            ),
            Node(
                package="aegisinspect_perception",
                executable="detector_projection_node.py",
                namespace="/aegis/perception",
                output="screen",
                parameters=[
                    {
                        "model_path": LaunchConfiguration(
                            "model_path"
                        ),
                        "confidence_floor":
                            LaunchConfiguration(
                                "confidence_floor"
                            ),
                        "imgsz": 640,
                        "device": 0,
                        "max_det": 300,
                    }
                ],
            ),
        ]
    )
