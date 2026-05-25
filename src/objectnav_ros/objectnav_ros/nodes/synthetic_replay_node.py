from __future__ import annotations

import json

import rclpy
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import OccupancyGrid as RosOccupancyGrid
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from tf2_ros import TransformBroadcaster
from visualization_msgs.msg import MarkerArray

from objectnav_core.mapping.fixtures import build_corridor_grid
from objectnav_core.mapping.grid import OccupancyGrid
from objectnav_core.models import ObjectObservation, Pose2D, SceneConfig, make_default_corridor_scene
from objectnav_core.simulation.observations import ConfigTruthObjectSource
from objectnav_ros.adapters.costmap_adapter import core_grid_to_occupancy_grid_msg
from objectnav_ros.adapters.pose_adapter import quaternion_z_w_from_yaw
from objectnav_ros.adapters.visualization import replay_debug_marker_array


class SyntheticReplayNode(Node):
    def __init__(self) -> None:
        super().__init__("objectnav_synthetic_replay")
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("goal_topic", "/objectnav/goal")
        self.declare_parameter("costmap_topic", "/global_costmap/costmap")
        self.declare_parameter("object_observation_topic", "/objectnav/object_observations")
        self.declare_parameter("debug_marker_topic", "/objectnav/debug_markers")
        self.declare_parameter("publish_period_s", 1.0)

        self.scene = make_default_corridor_scene()
        costmap_qos = QoSProfile(depth=1)
        costmap_qos.reliability = ReliabilityPolicy.RELIABLE
        costmap_qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
        self._goal_publisher = self.create_publisher(
            String,
            str(self.get_parameter("goal_topic").value),
            10,
        )
        self._costmap_publisher = self.create_publisher(
            RosOccupancyGrid,
            str(self.get_parameter("costmap_topic").value),
            costmap_qos,
        )
        self._observation_publisher = self.create_publisher(
            String,
            str(self.get_parameter("object_observation_topic").value),
            10,
        )
        self._debug_marker_publisher = self.create_publisher(
            MarkerArray,
            str(self.get_parameter("debug_marker_topic").value),
            10,
        )
        self._tf_broadcaster = TransformBroadcaster(self)
        self._sent_goal = False
        self._step_index = 0
        self._timer = self.create_timer(
            float(self.get_parameter("publish_period_s").value),
            self._publish_replay_step,
        )

    def _publish_replay_step(self) -> None:
        stamp = self.get_clock().now().to_msg()
        if not self._sent_goal:
            goal = String()
            goal.data = self.scene.objects[0].class_name
            self._goal_publisher.publish(goal)
            self._sent_goal = True
        self._costmap_publisher.publish(
            make_synthetic_costmap_message(
                self.scene,
                frame_id=str(self.get_parameter("map_frame").value),
                stamp=stamp,
                step_index=self._step_index,
            )
        )
        robot_pose = synthetic_robot_pose_for_step(self._step_index, self.scene)
        grid = make_synthetic_replay_grid(self.scene, step_index=self._step_index)
        observation_message = make_visible_synthetic_observation_message(
            self.scene,
            robot_pose=robot_pose,
            grid=grid,
            timestamp=self.get_clock().now().nanoseconds / 1_000_000_000.0,
        )
        if observation_message is not None:
            self._observation_publisher.publish(observation_message)
        self._debug_marker_publisher.publish(
            replay_debug_marker_array(
                frame_id=str(self.get_parameter("map_frame").value),
                step_index=self._step_index,
                robot_pose=robot_pose,
                stamp=stamp,
            )
        )
        self._tf_broadcaster.sendTransform(
            make_synthetic_base_transform(
                robot_pose=robot_pose,
                frame_id=str(self.get_parameter("map_frame").value),
                child_frame_id=str(self.get_parameter("base_frame").value),
                stamp=stamp,
            )
        )
        self._step_index += 1


def make_synthetic_costmap_message(
    scene: SceneConfig | None = None,
    *,
    frame_id: str = "map",
    stamp: object | None = None,
    step_index: int = 0,
):
    replay_scene = scene or make_default_corridor_scene()
    grid = make_synthetic_replay_grid(replay_scene, step_index=step_index)
    return core_grid_to_occupancy_grid_msg(grid, frame_id=frame_id, stamp=stamp)


def make_synthetic_replay_grid(
    scene: SceneConfig | None = None,
    *,
    step_index: int = 0,
) -> OccupancyGrid:
    replay_scene = scene or make_default_corridor_scene()
    grid = build_corridor_grid(replay_scene)
    for index in range(max(0, step_index) + 1):
        grid.reveal_forward_sector(
            synthetic_robot_pose_for_step(index, replay_scene),
            replay_scene.reveal_model,
        )
    return grid


def synthetic_robot_pose_for_step(
    step_index: int,
    scene: SceneConfig | None = None,
) -> Pose2D:
    replay_scene = scene or make_default_corridor_scene()
    x = min(1.0 + max(0, step_index) * 0.45, replay_scene.objects[0].pose_map.x - 0.8)
    return Pose2D(x=x, y=1.2, yaw=0.0)


def make_synthetic_observation_message(
    scene: SceneConfig | None = None,
    *,
    timestamp: float = 0.0,
) -> String:
    replay_scene = scene or make_default_corridor_scene()
    target = replay_scene.objects[0]
    message = String()
    message.data = json.dumps(
        {
            "object_id": target.object_id,
            "class_name": target.class_name,
            "confidence": 1.0,
            "pose": target.pose_map.model_dump(mode="json"),
            "anchor_id": replay_scene.anchor.anchor_id,
            "anchor_type": replay_scene.anchor.anchor_type.value,
            "frame_id": replay_scene.anchor.frame_id,
            "detector_name": "synthetic_replay",
            "timestamp": timestamp,
        },
        sort_keys=True,
    )
    return message


def make_visible_synthetic_observation_message(
    scene: SceneConfig | None = None,
    *,
    robot_pose: Pose2D,
    grid: OccupancyGrid,
    timestamp: float = 0.0,
) -> String | None:
    replay_scene = scene or make_default_corridor_scene()
    source = ConfigTruthObjectSource(replay_scene, detector_name="synthetic_replay")
    observations = source.observations_at(robot_pose, grid)
    if not observations:
        return None
    return _observation_to_message(observations[0], timestamp=timestamp)


def make_synthetic_base_transform(
    *,
    robot_pose: Pose2D | None = None,
    frame_id: str = "map",
    child_frame_id: str = "base_link",
    stamp: object | None = None,
) -> TransformStamped:
    pose = robot_pose or Pose2D(x=1.0, y=1.2, yaw=0.0)
    transform = TransformStamped()
    transform.header.frame_id = frame_id
    if stamp is not None:
        transform.header.stamp = stamp
    transform.child_frame_id = child_frame_id
    transform.transform.translation.x = pose.x
    transform.transform.translation.y = pose.y
    transform.transform.translation.z = 0.0
    z, w = quaternion_z_w_from_yaw(pose.yaw)
    transform.transform.rotation.z = z
    transform.transform.rotation.w = w
    return transform


def _observation_to_message(
    observation: ObjectObservation,
    *,
    timestamp: float,
) -> String:
    message = String()
    message.data = json.dumps(
        {
            "object_id": observation.object_id,
            "class_name": observation.class_name,
            "confidence": observation.confidence,
            "pose": observation.pose.model_dump(mode="json"),
            "anchor_id": observation.anchor_id,
            "anchor_type": observation.anchor_type.value,
            "frame_id": observation.frame_id,
            "detector_name": observation.detector_name,
            "timestamp": timestamp,
        },
        sort_keys=True,
    )
    return message


def main(args: list[str] | None = None) -> int:
    rclpy.init(args=args)
    node = SyntheticReplayNode()
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
