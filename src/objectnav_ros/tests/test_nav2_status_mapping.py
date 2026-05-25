from types import SimpleNamespace

from action_msgs.msg import GoalStatus

from objectnav_core.models import NavigationStatus, Pose2D
from objectnav_ros.adapters.nav2_navigation_client import (
    Nav2NavigationClient,
    make_navigate_to_pose_goal,
    navigation_status_from_goal_status,
)


def test_nav2_goal_status_maps_to_core_navigation_status() -> None:
    assert navigation_status_from_goal_status(GoalStatus.STATUS_SUCCEEDED) == (
        NavigationStatus.SUCCEEDED,
        "nav2_succeeded",
    )
    assert navigation_status_from_goal_status(GoalStatus.STATUS_CANCELED) == (
        NavigationStatus.CANCELED,
        "nav2_canceled",
    )
    assert navigation_status_from_goal_status(GoalStatus.STATUS_EXECUTING) == (
        NavigationStatus.ACTIVE,
        "nav2_active",
    )
    assert navigation_status_from_goal_status(GoalStatus.STATUS_ABORTED) == (
        NavigationStatus.FAILED,
        "nav2_aborted",
    )


def test_make_navigate_to_pose_goal_uses_core_pose_and_frame() -> None:
    goal = make_navigate_to_pose_goal(
        Pose2D(x=2.0, y=3.0, yaw=1.57),
        frame_id="map",
    )

    assert goal.pose.header.frame_id == "map"
    assert goal.pose.pose.position.x == 2.0
    assert goal.pose.pose.position.y == 3.0
    assert goal.pose.pose.orientation.w != 0.0


def test_nav2_navigation_client_reports_unavailable_server() -> None:
    action_client = FakeActionClient(server_available=False)
    client = Nav2NavigationClient(
        node=None,
        frame_id="map",
        server_timeout_s=1.5,
        action_client=action_client,
    )

    status = client.send_goal(Pose2D(x=2.0, y=3.0, yaw=0.0))

    assert status is NavigationStatus.FAILED
    assert client.result_reason == "action_server_unavailable"
    assert action_client.wait_timeout_s == 1.5
    assert action_client.sent_goal is None


def test_nav2_navigation_client_sends_goal_and_maps_success_result() -> None:
    result_future = ImmediateFuture(
        SimpleNamespace(
            status=GoalStatus.STATUS_SUCCEEDED,
            result=SimpleNamespace(error_code=0, error_msg=""),
        )
    )
    action_client = FakeActionClient(
        goal_handle=FakeGoalHandle(result_future=result_future),
    )
    client = Nav2NavigationClient(
        node=None,
        frame_id="map",
        action_client=action_client,
    )

    status = client.send_goal(Pose2D(x=2.0, y=3.0, yaw=1.57))

    assert status is NavigationStatus.SUCCEEDED
    assert client.status is NavigationStatus.SUCCEEDED
    assert client.result_reason == "nav2_succeeded"
    assert action_client.sent_goal.pose.header.frame_id == "map"
    assert action_client.sent_goal.pose.pose.position.x == 2.0


def test_nav2_navigation_client_marks_rejected_goal_failed() -> None:
    action_client = FakeActionClient(goal_handle=FakeGoalHandle(accepted=False))
    client = Nav2NavigationClient(
        node=None,
        frame_id="map",
        action_client=action_client,
    )

    status = client.send_goal(Pose2D(x=2.0, y=3.0, yaw=1.57))

    assert status is NavigationStatus.FAILED
    assert client.status is NavigationStatus.FAILED
    assert client.result_reason == "goal_rejected"


def test_nav2_navigation_client_includes_nav2_result_detail_on_abort() -> None:
    result_future = ImmediateFuture(
        SimpleNamespace(
            status=GoalStatus.STATUS_ABORTED,
            result=SimpleNamespace(error_code=42, error_msg="planner blocked"),
        )
    )
    action_client = FakeActionClient(
        goal_handle=FakeGoalHandle(result_future=result_future),
    )
    client = Nav2NavigationClient(
        node=None,
        frame_id="map",
        action_client=action_client,
    )

    status = client.send_goal(Pose2D(x=2.0, y=3.0, yaw=1.57))

    assert status is NavigationStatus.FAILED
    assert client.result_reason == "nav2_aborted:planner blocked"


def test_nav2_navigation_client_cancel_request_updates_status() -> None:
    result_future = ManualFuture()
    cancel_future = ImmediateFuture(SimpleNamespace(goals_canceling=[object()]))
    action_client = FakeActionClient(
        goal_handle=FakeGoalHandle(
            result_future=result_future,
            cancel_future=cancel_future,
        ),
    )
    client = Nav2NavigationClient(
        node=None,
        frame_id="map",
        action_client=action_client,
    )

    assert client.send_goal(Pose2D(x=2.0, y=3.0, yaw=1.57)) is NavigationStatus.ACTIVE
    assert client.cancel_goal() is NavigationStatus.CANCELED
    assert client.result_reason == "nav2_cancel_requested"


class ImmediateFuture:
    def __init__(self, result: object) -> None:
        self._result = result

    def result(self) -> object:
        return self._result

    def add_done_callback(self, callback: object) -> None:
        callback(self)


class ManualFuture:
    def __init__(self) -> None:
        self._callbacks: list[object] = []

    def result(self) -> object:
        raise AssertionError("manual future was not completed")

    def add_done_callback(self, callback: object) -> None:
        self._callbacks.append(callback)


class FakeGoalHandle:
    def __init__(
        self,
        *,
        accepted: bool = True,
        result_future: object | None = None,
        cancel_future: object | None = None,
    ) -> None:
        self.accepted = accepted
        self.result_future = result_future or ImmediateFuture(
            SimpleNamespace(
                status=GoalStatus.STATUS_SUCCEEDED,
                result=SimpleNamespace(error_code=0, error_msg=""),
            )
        )
        self.cancel_future = cancel_future or ImmediateFuture(
            SimpleNamespace(goals_canceling=[object()])
        )

    def get_result_async(self) -> object:
        return self.result_future

    def cancel_goal_async(self) -> object:
        return self.cancel_future


class FakeActionClient:
    def __init__(
        self,
        *,
        server_available: bool = True,
        goal_handle: FakeGoalHandle | None = None,
    ) -> None:
        self.server_available = server_available
        self.goal_handle = goal_handle or FakeGoalHandle()
        self.wait_timeout_s: float | None = None
        self.sent_goal: object | None = None
        self.feedback_callback: object | None = None

    def wait_for_server(self, *, timeout_sec: float) -> bool:
        self.wait_timeout_s = timeout_sec
        return self.server_available

    def send_goal_async(
        self,
        goal: object,
        *,
        feedback_callback: object | None = None,
    ) -> ImmediateFuture:
        self.sent_goal = goal
        self.feedback_callback = feedback_callback
        return ImmediateFuture(self.goal_handle)
