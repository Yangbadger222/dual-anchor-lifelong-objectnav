from __future__ import annotations

import json

from nav_msgs.msg import OccupancyGrid as RosOccupancyGrid
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String
from visualization_msgs.msg import MarkerArray

from objectnav_core.mapping.frontiers import FrontierCluster, extract_frontier_clusters
from objectnav_core.mapping.grid import OccupancyGrid
from objectnav_core.models import ObjectObservation, Pose2D
from objectnav_core.planning.viewpoints import plan_frontier_viewpoint
from objectnav_ros.adapters.costmap_adapter import (
    CostmapConversionConfig,
    occupancy_grid_to_core_grid,
)
from objectnav_ros.adapters.object_observation_adapter import (
    ObservationAdapterError,
    object_observation_from_json_msg,
)
from objectnav_ros.adapters.nav2_navigation_client import Nav2NavigationClient
from objectnav_ros.adapters.pose_adapter import pose_stamped_from_pose2d
from objectnav_ros.adapters.visualization import (
    frontier_marker_array,
    memory_marker_array,
)


class ObjectNavAdapterNode(Node):
    def __init__(self) -> None:
        super().__init__("objectnav_adapter")

        self.declare_parameter("map_frame", "map")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("goal_topic", "/objectnav/goal")
        self.declare_parameter("status_topic", "/objectnav/status")
        self.declare_parameter("selected_goal_topic", "/objectnav/selected_goal")
        self.declare_parameter("frontier_marker_topic", "/objectnav/frontier_markers")
        self.declare_parameter("memory_marker_topic", "/objectnav/memory_markers")
        self.declare_parameter("object_observation_topic", "/objectnav/object_observations")
        self.declare_parameter("costmap_topic", "/global_costmap/costmap")
        self.declare_parameter("navigate_to_pose_action", "navigate_to_pose")
        self.declare_parameter("target_anchor_id", "indoor_map_corridor_a")
        self.declare_parameter("memory_db_path", "objectnav_memory.sqlite")
        self.declare_parameter("free_threshold", 25)
        self.declare_parameter("occupied_threshold", 65)
        self.declare_parameter("unknown_value", -1)
        self.declare_parameter("publish_markers", True)
        self.declare_parameter("navigation_timeout_s", 120.0)
        self.declare_parameter("max_observation_age_s", 0.0)

        goal_topic = self.get_parameter("goal_topic").value
        status_topic = self.get_parameter("status_topic").value
        selected_goal_topic = self.get_parameter("selected_goal_topic").value
        frontier_marker_topic = self.get_parameter("frontier_marker_topic").value
        memory_marker_topic = self.get_parameter("memory_marker_topic").value
        object_observation_topic = self.get_parameter("object_observation_topic").value
        costmap_topic = self.get_parameter("costmap_topic").value

        self._status_publisher = self.create_publisher(String, status_topic, 10)
        self._selected_goal_publisher = self.create_publisher(
            type(pose_stamped_from_pose2d(Pose2D(x=0.0, y=0.0), frame_id="map")),
            selected_goal_topic,
            10,
        )
        self._frontier_marker_publisher = self.create_publisher(
            MarkerArray,
            frontier_marker_topic,
            10,
        )
        self._memory_marker_publisher = self.create_publisher(
            MarkerArray,
            memory_marker_topic,
            10,
        )
        self.create_subscription(String, goal_topic, self._on_goal, 10)
        self.create_subscription(String, object_observation_topic, self._on_object_observation, 10)
        self.create_subscription(RosOccupancyGrid, costmap_topic, self._on_costmap, 10)
        self._navigation_client = Nav2NavigationClient(
            self,
            action_name=str(self.get_parameter("navigate_to_pose_action").value),
            frame_id=str(self.get_parameter("map_frame").value),
            server_timeout_s=float(self.get_parameter("navigation_timeout_s").value),
        )
        self._active_target_class: str | None = None
        self._latest_grid: OccupancyGrid | None = None
        self._latest_frontiers: list[FrontierCluster] = []
        self._latest_frame_id = str(self.get_parameter("map_frame").value)
        self._latest_observations: list[ObjectObservation] = []

        self._publish_status(
            state="ready",
            message="objectnav_ros adapter skeleton started",
        )

    def _on_goal(self, message: String) -> None:
        target_class = message.data.strip()
        self._active_target_class = target_class or None
        self._publish_status(
            state="goal_received" if self._active_target_class else "goal_rejected",
            target_class=self._active_target_class,
            message="received ObjectNav target class"
            if self._active_target_class
            else "empty ObjectNav target class",
        )
        if self._active_target_class and self._latest_grid is not None:
            self._publish_selected_frontier_goal()

    def _on_costmap(self, message: RosOccupancyGrid) -> None:
        try:
            grid = occupancy_grid_to_core_grid(
                message,
                CostmapConversionConfig(
                    free_threshold=int(self.get_parameter("free_threshold").value),
                    occupied_threshold=int(self.get_parameter("occupied_threshold").value),
                    unknown_value=int(self.get_parameter("unknown_value").value),
                ),
            )
        except ValueError as exc:
            self._publish_status(state="costmap_rejected", message=str(exc))
            return

        self._latest_grid = grid
        self._latest_frontiers = extract_frontier_clusters(grid)
        frame_id = str(message.header.frame_id or self.get_parameter("map_frame").value)
        self._latest_frame_id = frame_id
        if bool(self.get_parameter("publish_markers").value):
            self._frontier_marker_publisher.publish(
                frontier_marker_array(
                    self._latest_frontiers,
                    grid,
                    frame_id=frame_id,
                    stamp=message.header.stamp,
                )
            )
        self._publish_status(
            state="costmap_received",
            frame_id=frame_id,
            frontier_count=len(self._latest_frontiers),
        )
        if self._active_target_class:
            self._publish_selected_frontier_goal(stamp=message.header.stamp)

    def _on_object_observation(self, message: String) -> None:
        max_age_s = float(self.get_parameter("max_observation_age_s").value)
        try:
            observation = object_observation_from_json_msg(
                message,
                now_s=self.get_clock().now().nanoseconds / 1_000_000_000.0,
                max_age_s=max_age_s if max_age_s > 0 else None,
            )
        except ObservationAdapterError as exc:
            self._publish_status(state="observation_rejected", message=str(exc))
            return
        self._latest_observations.append(observation)
        if bool(self.get_parameter("publish_markers").value):
            self._memory_marker_publisher.publish(
                memory_marker_array(
                    self._latest_observations,
                    frame_id=observation.frame_id or str(self.get_parameter("map_frame").value),
                    stamp=self.get_clock().now().to_msg(),
                )
            )
        self._publish_status(
            state="observation_received",
            object_id=observation.object_id,
            class_name=observation.class_name,
            anchor_id=observation.anchor_id,
            detector_name=observation.detector_name,
        )

    def _publish_selected_frontier_goal(self, stamp: object | None = None) -> None:
        if self._latest_grid is None:
            self._publish_status(state="waiting_for_map")
            return
        goal_pose = select_replay_frontier_goal(self._latest_grid, self._latest_frontiers)
        if goal_pose is None:
            self._publish_status(
                state="selected_goal_unavailable",
                frontier_count=len(self._latest_frontiers),
            )
            return
        self._selected_goal_publisher.publish(
            pose_stamped_from_pose2d(goal_pose, frame_id=self._latest_frame_id, stamp=stamp)
        )
        self._publish_status(
            state="selected_goal_published",
            target_class=self._active_target_class,
            x=goal_pose.x,
            y=goal_pose.y,
            yaw=goal_pose.yaw,
        )

    def _publish_status(self, **payload: object) -> None:
        message = String()
        message.data = json.dumps(payload, sort_keys=True)
        self._status_publisher.publish(message)


def select_replay_frontier_goal(
    grid: OccupancyGrid,
    frontiers: list[FrontierCluster],
) -> Pose2D | None:
    for frontier in frontiers:
        try:
            return plan_frontier_viewpoint(grid, frontier)
        except ValueError:
            continue
    return None


def main(args: list[str] | None = None) -> int:
    rclpy.init(args=args)
    node = ObjectNavAdapterNode()
    try:
        rclpy.spin(node)
    except ExternalShutdownException:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
