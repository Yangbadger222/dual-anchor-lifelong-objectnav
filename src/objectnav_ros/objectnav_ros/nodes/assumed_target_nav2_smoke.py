from __future__ import annotations

from dataclasses import dataclass
import json
import math

from geometry_msgs.msg import PoseStamped
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String

from objectnav_core.models import NavigationStatus, Pose2D
from objectnav_ros.adapters.nav2_navigation_client import Nav2NavigationClient
from objectnav_ros.adapters.pose_adapter import pose_stamped_from_pose2d


@dataclass(frozen=True)
class AssumedTarget:
    class_name: str
    pose: Pose2D
    frame_id: str


def assumed_target_from_values(
    *,
    class_name: str,
    x: float,
    y: float,
    yaw: float,
    frame_id: str,
) -> AssumedTarget:
    normalized_class = class_name.strip()
    normalized_frame = frame_id.strip()
    if not normalized_class:
        raise ValueError("target_class must not be empty")
    if not normalized_frame:
        raise ValueError("map_frame must not be empty")
    if not all(math.isfinite(value) for value in (x, y, yaw)):
        raise ValueError("target pose values must be finite")
    return AssumedTarget(
        class_name=normalized_class,
        pose=Pose2D(x=float(x), y=float(y), yaw=float(yaw)),
        frame_id=normalized_frame,
    )


def trigger_matches_target(message: String, target: AssumedTarget) -> bool:
    return message.data.strip() == target.class_name


def assumed_target_status_payload(
    *,
    state: str,
    target: AssumedTarget,
    navigation_status: NavigationStatus | None = None,
    result_reason: str | None = None,
    trigger: str | None = None,
    message: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "state": state,
        "target_class": target.class_name,
        "frame_id": target.frame_id,
        "x": target.pose.x,
        "y": target.pose.y,
        "yaw": target.pose.yaw,
    }
    if navigation_status is not None:
        payload["navigation_status"] = navigation_status.value
    if result_reason:
        payload["result_reason"] = result_reason
    if trigger:
        payload["trigger"] = trigger
    if message:
        payload["message"] = message
    return payload


def status_message_from_payload(payload: dict[str, object]) -> String:
    message = String()
    message.data = json.dumps(payload, sort_keys=True)
    return message


class AssumedTargetNav2SmokeNode(Node):
    def __init__(self) -> None:
        super().__init__("assumed_target_nav2_smoke")

        self.declare_parameter("map_frame", "map")
        self.declare_parameter("target_class", "water_dispenser")
        self.declare_parameter("target_x", 1.5)
        self.declare_parameter("target_y", 0.0)
        self.declare_parameter("target_yaw", 0.0)
        self.declare_parameter("status_topic", "/objectnav/status")
        self.declare_parameter("selected_goal_topic", "/objectnav/selected_goal")
        self.declare_parameter("trigger_topic", "/objectnav/goal")
        self.declare_parameter("navigate_to_pose_action", "navigate_to_pose")
        self.declare_parameter("navigation_timeout_s", 30.0)
        self.declare_parameter("status_period_s", 1.0)
        self.declare_parameter("send_goal_on_start", False)
        self.declare_parameter("exit_on_result", False)

        self.target = assumed_target_from_values(
            class_name=str(self.get_parameter("target_class").value),
            x=float(self.get_parameter("target_x").value),
            y=float(self.get_parameter("target_y").value),
            yaw=float(self.get_parameter("target_yaw").value),
            frame_id=str(self.get_parameter("map_frame").value),
        )
        self._status_publisher = self.create_publisher(
            String,
            str(self.get_parameter("status_topic").value),
            10,
        )
        self._selected_goal_publisher = self.create_publisher(
            PoseStamped,
            str(self.get_parameter("selected_goal_topic").value),
            10,
        )
        self.create_subscription(
            String,
            str(self.get_parameter("trigger_topic").value),
            self._on_goal_trigger,
            10,
        )
        self._navigation_client = Nav2NavigationClient(
            self,
            action_name=str(self.get_parameter("navigate_to_pose_action").value),
            frame_id=self.target.frame_id,
            server_timeout_s=float(self.get_parameter("navigation_timeout_s").value),
        )
        self._goal_sent = False
        self._terminal_status_reported = False
        self._last_status_key: tuple[str, str, str | None] | None = None
        self._publish_selected_goal()
        self._publish_status(
            state="assumed_target_ready",
            navigation_status=self._navigation_client.status,
            message="publish the target class on the trigger topic to send the Nav2 goal",
        )
        self._timer = self.create_timer(
            float(self.get_parameter("status_period_s").value),
            self._on_timer,
        )

    def _on_goal_trigger(self, message: String) -> None:
        if not trigger_matches_target(message, self.target):
            self._publish_status(
                state="assumed_target_ignored",
                navigation_status=self._navigation_client.status,
                trigger=message.data.strip(),
                message="trigger did not match configured target_class",
                force=True,
            )
            return
        self._send_nav2_goal(trigger=message.data.strip())

    def _on_timer(self) -> None:
        self._publish_selected_goal()
        if bool(self.get_parameter("send_goal_on_start").value) and not self._goal_sent:
            self._send_nav2_goal(trigger="send_goal_on_start")
            return
        self._publish_navigation_status()
        if self._should_exit_after_result():
            rclpy.shutdown()

    def _send_nav2_goal(self, *, trigger: str) -> None:
        if self._goal_sent:
            self._publish_status(
                state="assumed_target_goal_already_sent",
                navigation_status=self._navigation_client.status,
                result_reason=self._navigation_client.result_reason,
                trigger=trigger,
                force=True,
            )
            return
        self._publish_selected_goal()
        status = self._navigation_client.send_goal(
            self.target.pose,
            stamp=self.get_clock().now().to_msg(),
        )
        self._goal_sent = True
        self._publish_status(
            state="assumed_target_goal_sent"
            if status is NavigationStatus.ACTIVE
            else "assumed_target_goal_failed",
            navigation_status=status,
            result_reason=self._navigation_client.result_reason,
            trigger=trigger,
            force=True,
        )

    def _publish_selected_goal(self) -> None:
        self._selected_goal_publisher.publish(
            pose_stamped_from_pose2d(
                self.target.pose,
                frame_id=self.target.frame_id,
                stamp=self.get_clock().now().to_msg(),
            )
        )

    def _publish_navigation_status(self) -> None:
        status = self._navigation_client.status
        state = "assumed_target_navigation_active"
        if status is NavigationStatus.IDLE:
            state = "assumed_target_waiting_for_trigger"
        elif status in {
            NavigationStatus.SUCCEEDED,
            NavigationStatus.FAILED,
            NavigationStatus.CANCELED,
        }:
            state = "assumed_target_navigation_result"
            self._terminal_status_reported = True
        self._publish_status(
            state=state,
            navigation_status=status,
            result_reason=self._navigation_client.result_reason,
            force=True,
        )

    def _publish_status(
        self,
        *,
        state: str,
        navigation_status: NavigationStatus | None = None,
        result_reason: str | None = None,
        trigger: str | None = None,
        message: str | None = None,
        force: bool = False,
    ) -> None:
        status_value = navigation_status.value if navigation_status is not None else ""
        key = (state, status_value, result_reason)
        if not force and key == self._last_status_key:
            return
        self._last_status_key = key
        self._status_publisher.publish(
            status_message_from_payload(
                assumed_target_status_payload(
                    state=state,
                    target=self.target,
                    navigation_status=navigation_status,
                    result_reason=result_reason,
                    trigger=trigger,
                    message=message,
                )
            )
        )

    def _should_exit_after_result(self) -> bool:
        return bool(self.get_parameter("exit_on_result").value) and self._terminal_status_reported


def main(args: list[str] | None = None) -> int:
    rclpy.init(args=args)
    node = AssumedTargetNav2SmokeNode()
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
