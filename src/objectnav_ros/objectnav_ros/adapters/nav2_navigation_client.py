from __future__ import annotations

from typing import Any

from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient

from objectnav_core.models import NavigationStatus, Pose2D
from objectnav_ros.adapters.pose_adapter import pose_stamped_from_pose2d


class Nav2NavigationClient:
    def __init__(
        self,
        node: Any,
        *,
        action_name: str = "navigate_to_pose",
        frame_id: str = "map",
        server_timeout_s: float = 2.0,
        action_client: Any | None = None,
    ) -> None:
        self.node = node
        self.action_name = action_name
        self.frame_id = frame_id
        self.server_timeout_s = server_timeout_s
        self._action_client = action_client or ActionClient(
            node,
            NavigateToPose,
            action_name,
        )
        self.status = NavigationStatus.IDLE
        self.result_reason: str | None = None
        self.goal_pose: Pose2D | None = None
        self.feedback_messages: list[Any] = []
        self._goal_handle: Any | None = None
        self._send_goal_future: Any | None = None
        self._result_future: Any | None = None
        self._cancel_future: Any | None = None

    def send_goal(
        self,
        goal_pose: Pose2D,
        *,
        stamp: object | None = None,
    ) -> NavigationStatus:
        if self.status is NavigationStatus.ACTIVE:
            raise RuntimeError("Nav2 goal is already active")
        if not self._action_client.wait_for_server(timeout_sec=self.server_timeout_s):
            self.goal_pose = goal_pose
            self.status = NavigationStatus.FAILED
            self.result_reason = "action_server_unavailable"
            return self.status

        goal = make_navigate_to_pose_goal(goal_pose, frame_id=self.frame_id, stamp=stamp)
        self.goal_pose = goal_pose
        self.result_reason = None
        self.feedback_messages = []
        self._goal_handle = None
        self.status = NavigationStatus.ACTIVE
        self._send_goal_future = self._action_client.send_goal_async(
            goal,
            feedback_callback=self._on_feedback,
        )
        self._send_goal_future.add_done_callback(self._on_goal_response)
        return self.status

    def cancel_goal(self) -> NavigationStatus:
        if self.status is not NavigationStatus.ACTIVE:
            return self.status
        if self._goal_handle is None:
            self.status = NavigationStatus.CANCELED
            self.result_reason = "canceled_before_acceptance"
            return self.status

        self.result_reason = "cancel_requested"
        self._cancel_future = self._goal_handle.cancel_goal_async()
        self._cancel_future.add_done_callback(self._on_cancel_response)
        return self.status

    def _on_feedback(self, feedback_message: Any) -> None:
        self.feedback_messages.append(feedback_message)

    def _on_goal_response(self, future: Any) -> None:
        try:
            goal_handle = future.result()
        except Exception as exc:  # pragma: no cover - exact ROS exception type varies.
            self.status = NavigationStatus.FAILED
            self.result_reason = f"goal_response_failed:{exc}"
            return

        self._goal_handle = goal_handle
        if not getattr(goal_handle, "accepted", False):
            self.status = NavigationStatus.FAILED
            self.result_reason = "goal_rejected"
            return

        self._result_future = goal_handle.get_result_async()
        self._result_future.add_done_callback(self._on_result)

    def _on_result(self, future: Any) -> None:
        try:
            result_response = future.result()
        except Exception as exc:  # pragma: no cover - exact ROS exception type varies.
            self.status = NavigationStatus.FAILED
            self.result_reason = f"result_failed:{exc}"
            return

        status_code = int(getattr(result_response, "status", GoalStatus.STATUS_UNKNOWN))
        self.status, self.result_reason = navigation_status_from_goal_status(status_code)
        nav2_detail = _nav2_result_detail(getattr(result_response, "result", None))
        if nav2_detail and self.status is not NavigationStatus.SUCCEEDED:
            self.result_reason = f"{self.result_reason}:{nav2_detail}"

    def _on_cancel_response(self, future: Any) -> None:
        try:
            response = future.result()
        except Exception as exc:  # pragma: no cover - exact ROS exception type varies.
            self.status = NavigationStatus.FAILED
            self.result_reason = f"cancel_failed:{exc}"
            return

        goals_canceling = getattr(response, "goals_canceling", [])
        if goals_canceling:
            self.status = NavigationStatus.CANCELED
            self.result_reason = "nav2_cancel_requested"
        else:
            self.status = NavigationStatus.ACTIVE
            self.result_reason = "nav2_cancel_rejected"


def make_navigate_to_pose_goal(
    pose: Pose2D,
    frame_id: str,
    stamp: object | None = None,
) -> NavigateToPose.Goal:
    goal = NavigateToPose.Goal()
    goal.pose = pose_stamped_from_pose2d(pose, frame_id=frame_id, stamp=stamp)
    return goal


def navigation_status_from_goal_status(status: int) -> tuple[NavigationStatus, str]:
    if status == GoalStatus.STATUS_SUCCEEDED:
        return NavigationStatus.SUCCEEDED, "nav2_succeeded"
    if status == GoalStatus.STATUS_CANCELED:
        return NavigationStatus.CANCELED, "nav2_canceled"
    if status in {
        GoalStatus.STATUS_ACCEPTED,
        GoalStatus.STATUS_EXECUTING,
        GoalStatus.STATUS_CANCELING,
    }:
        return NavigationStatus.ACTIVE, "nav2_active"
    if status == GoalStatus.STATUS_ABORTED:
        return NavigationStatus.FAILED, "nav2_aborted"
    return NavigationStatus.FAILED, f"nav2_status_{status}"


def _nav2_result_detail(result: object | None) -> str | None:
    if result is None:
        return None
    error_msg = getattr(result, "error_msg", "")
    if error_msg:
        return str(error_msg)
    error_code = getattr(result, "error_code", None)
    if error_code not in (None, 0):
        return f"error_code_{error_code}"
    return None
