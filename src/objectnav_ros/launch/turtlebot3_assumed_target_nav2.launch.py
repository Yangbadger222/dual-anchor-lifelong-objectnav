import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _prepend_existing_env_paths(name: str, paths: list[Path]) -> None:
    existing_values = [value for value in os.environ.get(name, "").split(os.pathsep) if value]
    prepend_values = [str(path) for path in paths if path.exists()]
    merged_values = prepend_values + [
        value for value in existing_values if value not in prepend_values
    ]
    if merged_values:
        os.environ[name] = os.pathsep.join(merged_values)


def generate_launch_description() -> LaunchDescription:
    objectnav_share = Path(get_package_share_directory("objectnav_ros"))
    turtlebot3_gazebo_share = Path(get_package_share_directory("turtlebot3_gazebo"))
    turtlebot3_navigation_share = Path(get_package_share_directory("turtlebot3_navigation2"))
    _prepend_existing_env_paths(
        "GAZEBO_MODEL_PATH",
        [
            turtlebot3_gazebo_share / "models",
            Path("/usr/share/gazebo-11/models"),
        ],
    )
    # Gazebo Classic's online model database can stall before /spawn_entity appears.
    os.environ.setdefault("GAZEBO_MODEL_DATABASE_URI", "")

    turtlebot3_model = LaunchConfiguration("turtlebot3_model")
    use_sim_time = LaunchConfiguration("use_sim_time")
    start_gazebo = LaunchConfiguration("start_gazebo")
    start_nav2 = LaunchConfiguration("start_nav2")
    send_goal_on_start = LaunchConfiguration("send_goal_on_start")
    target_config = LaunchConfiguration("target_config")
    map_path = LaunchConfiguration("map")
    nav2_params_file = LaunchConfiguration("nav2_params_file")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "turtlebot3_model",
                default_value="waffle",
                description="TurtleBot3 model used by turtlebot3_gazebo/navigation2.",
            ),
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="true",
                description="Use Gazebo simulation time.",
            ),
            DeclareLaunchArgument(
                "start_gazebo",
                default_value="true",
                description="Start TurtleBot3 Gazebo world.",
            ),
            DeclareLaunchArgument(
                "start_nav2",
                default_value="true",
                description="Start TurtleBot3 Navigation2.",
            ),
            DeclareLaunchArgument(
                "send_goal_on_start",
                default_value="false",
                description="Send the assumed target to Nav2 as soon as the smoke node starts.",
            ),
            DeclareLaunchArgument(
                "target_config",
                default_value=str(objectnav_share / "config" / "turtlebot3_assumed_targets.yaml"),
                description="Assumed semantic target parameter file.",
            ),
            DeclareLaunchArgument(
                "map",
                default_value=str(turtlebot3_navigation_share / "map" / "map.yaml"),
                description="TurtleBot3 Navigation2 map YAML.",
            ),
            DeclareLaunchArgument(
                "nav2_params_file",
                default_value=str(turtlebot3_navigation_share / "param" / "humble" / "waffle.yaml"),
                description="TurtleBot3 Navigation2 parameter YAML.",
            ),
            SetEnvironmentVariable("TURTLEBOT3_MODEL", turtlebot3_model),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    str(turtlebot3_gazebo_share / "launch" / "turtlebot3_world.launch.py")
                ),
                condition=IfCondition(start_gazebo),
                launch_arguments={"use_sim_time": use_sim_time}.items(),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    str(turtlebot3_navigation_share / "launch" / "navigation2.launch.py")
                ),
                condition=IfCondition(start_nav2),
                launch_arguments={
                    "use_sim_time": use_sim_time,
                    "map": map_path,
                    "params_file": nav2_params_file,
                }.items(),
            ),
            Node(
                package="objectnav_ros",
                executable="assumed_target_nav2_smoke",
                name="assumed_target_nav2_smoke",
                output="screen",
                parameters=[
                    target_config,
                    {
                        "use_sim_time": use_sim_time,
                        "send_goal_on_start": send_goal_on_start,
                    },
                ],
            ),
        ]
    )
