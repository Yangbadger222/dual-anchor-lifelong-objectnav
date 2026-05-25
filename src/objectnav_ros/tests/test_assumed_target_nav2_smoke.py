import json
from pathlib import Path

import rclpy
from std_msgs.msg import String
import yaml

from objectnav_core.models import NavigationStatus
from objectnav_ros.nodes.assumed_target_nav2_smoke import (
    AssumedTargetNav2SmokeNode,
    assumed_target_from_values,
    assumed_target_status_payload,
    status_message_from_payload,
    trigger_matches_target,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_assumed_target_from_values_validates_and_normalizes() -> None:
    target = assumed_target_from_values(
        class_name=" water_dispenser ",
        x=1.5,
        y=0.0,
        yaw=0.25,
        frame_id=" map ",
    )

    assert target.class_name == "water_dispenser"
    assert target.frame_id == "map"
    assert target.pose.x == 1.5
    assert target.pose.yaw == 0.25


def test_trigger_matches_target_requires_exact_class() -> None:
    target = assumed_target_from_values(
        class_name="water_dispenser",
        x=1.5,
        y=0.0,
        yaw=0.0,
        frame_id="map",
    )
    message = String()
    message.data = "water_dispenser"
    other = String()
    other.data = "trash_bin"

    assert trigger_matches_target(message, target)
    assert not trigger_matches_target(other, target)


def test_status_message_contains_target_pose_and_navigation_status() -> None:
    target = assumed_target_from_values(
        class_name="water_dispenser",
        x=1.5,
        y=0.0,
        yaw=0.0,
        frame_id="map",
    )

    message = status_message_from_payload(
        assumed_target_status_payload(
            state="assumed_target_goal_sent",
            target=target,
            navigation_status=NavigationStatus.ACTIVE,
            trigger="water_dispenser",
        )
    )
    payload = json.loads(message.data)

    assert payload["state"] == "assumed_target_goal_sent"
    assert payload["target_class"] == "water_dispenser"
    assert payload["navigation_status"] == "ACTIVE"
    assert payload["x"] == 1.5


def test_assumed_target_node_sends_nav2_goal_on_matching_trigger() -> None:
    rclpy.init()
    node = AssumedTargetNav2SmokeNode()
    try:
        status_publisher = FakePublisher()
        selected_goal_publisher = FakePublisher()
        navigation_client = FakeNavigationClient()
        node._status_publisher = status_publisher
        node._selected_goal_publisher = selected_goal_publisher
        node._navigation_client = navigation_client

        message = String()
        message.data = "water_dispenser"
        node._on_goal_trigger(message)

        assert navigation_client.goal_pose == node.target.pose
        assert selected_goal_publisher.messages[-1].header.frame_id == "map"
        payload = json.loads(status_publisher.messages[-1].data)
        assert payload["state"] == "assumed_target_goal_sent"
        assert payload["trigger"] == "water_dispenser"
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def test_assumed_target_config_and_launch_are_installed() -> None:
    config_path = PACKAGE_ROOT / "config" / "turtlebot3_assumed_targets.yaml"
    launch_path = PACKAGE_ROOT / "launch" / "turtlebot3_assumed_target_nav2.launch.py"
    setup_text = (PACKAGE_ROOT / "setup.py").read_text(encoding="utf-8")

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    params = config["assumed_target_nav2_smoke"]["ros__parameters"]

    assert params["target_class"] == "water_dispenser"
    assert params["map_frame"] == "map"
    assert "assumed_target_nav2_smoke" in setup_text
    assert launch_path.exists()
    launch_text = launch_path.read_text(encoding="utf-8")
    assert "turtlebot3_gazebo" in launch_text
    assert "turtlebot3_navigation2" in launch_text
    assert "turtlebot3_assumed_targets.yaml" in launch_text
    assert "GAZEBO_MODEL_DATABASE_URI" in launch_text
    assert "nav2_params_file" in launch_text


class FakePublisher:
    def __init__(self) -> None:
        self.messages: list[object] = []

    def publish(self, message: object) -> None:
        self.messages.append(message)


class FakeNavigationClient:
    def __init__(self) -> None:
        self.status = NavigationStatus.IDLE
        self.result_reason: str | None = None
        self.goal_pose: object | None = None

    def send_goal(self, goal_pose: object, *, stamp: object | None = None) -> NavigationStatus:
        self.goal_pose = goal_pose
        self.status = NavigationStatus.ACTIVE
        self.result_reason = None
        return self.status
