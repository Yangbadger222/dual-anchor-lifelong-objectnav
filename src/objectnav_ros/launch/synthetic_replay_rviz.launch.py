from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    share_dir = Path(get_package_share_directory("objectnav_ros"))
    config_path = share_dir / "config" / "indoor_nav2_adapter.yaml"
    rviz_path = share_dir / "rviz" / "synthetic_replay.rviz"
    return LaunchDescription(
        [
            Node(
                package="objectnav_ros",
                executable="objectnav_adapter",
                name="objectnav_adapter",
                output="screen",
                parameters=[str(config_path)],
            ),
            Node(
                package="objectnav_ros",
                executable="objectnav_synthetic_replay",
                name="objectnav_synthetic_replay",
                output="screen",
                parameters=[
                    {"map_frame": "map"},
                    {"base_frame": "base_link"},
                    {"publish_period_s": 1.0},
                ],
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                name="objectnav_synthetic_replay_rviz",
                output="screen",
                arguments=["-d", str(rviz_path)],
            ),
        ]
    )
