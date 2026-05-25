import json

import rclpy
from std_msgs.msg import String

from objectnav_ros.nodes.objectnav_node import ObjectNavAdapterNode
from objectnav_ros.nodes.synthetic_replay_node import (
    make_synthetic_costmap_message,
    make_synthetic_observation_message,
)


def test_objectnav_node_replay_callbacks_publish_visual_outputs() -> None:
    rclpy.init()
    node = ObjectNavAdapterNode()
    try:
        status_publisher = FakePublisher()
        selected_goal_publisher = FakePublisher()
        frontier_marker_publisher = FakePublisher()
        memory_marker_publisher = FakePublisher()
        node._status_publisher = status_publisher
        node._selected_goal_publisher = selected_goal_publisher
        node._frontier_marker_publisher = frontier_marker_publisher
        node._memory_marker_publisher = memory_marker_publisher

        goal = String()
        goal.data = "water_dispenser"
        node._on_goal(goal)
        node._on_costmap(make_synthetic_costmap_message(frame_id="map"))
        node._on_object_observation(make_synthetic_observation_message(timestamp=0.0))

        states = [json.loads(message.data)["state"] for message in status_publisher.messages]
        assert "goal_received" in states
        assert "costmap_received" in states
        assert "selected_goal_published" in states
        assert "observation_received" in states
        assert selected_goal_publisher.messages[-1].header.frame_id == "map"
        assert len(frontier_marker_publisher.messages[-1].markers) > 0
        assert len(memory_marker_publisher.messages[-1].markers) == 2
    finally:
        node.destroy_node()
        rclpy.shutdown()


class FakePublisher:
    def __init__(self) -> None:
        self.messages: list[object] = []

    def publish(self, message: object) -> None:
        self.messages.append(message)
