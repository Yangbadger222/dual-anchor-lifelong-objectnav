from __future__ import annotations

from typing import Any, Callable

import numpy as np

from objectnav_core.models import NavigationStatus, Pose2D
from objectnav_core.navigation.backend import (
    ExplorationRequest,
    NavigationBackendStatus,
    NavigationGoal,
)


FollowerFactory = Callable[..., Any]


class HabitatOracleFollowerBackend:
    """Privileged Habitat shortest-path executor for simulation upper bounds."""

    def __init__(
        self,
        env: Any,
        *,
        goal_radius_m: float = 1.0,
        follower_factory: FollowerFactory | None = None,
        backend_id: str = "habitat_oracle_shortest_path",
    ) -> None:
        if goal_radius_m <= 0.0:
            raise ValueError("goal_radius_m must be positive")
        if not str(backend_id).strip():
            raise ValueError("backend_id must be non-empty")
        self.env = env
        self.goal_radius_m = float(goal_radius_m)
        self.backend_id = str(backend_id).strip()
        self._follower_factory = follower_factory or _make_shortest_path_follower
        self._follower: Any | None = None
        self._active_goal_id: str | None = None
        self._goal_position: tuple[float, float, float] | None = None
        self._status = NavigationStatus.IDLE
        self._reason: str | None = None
        self._metadata: dict[str, Any] = {}

    def get_pose(self) -> Pose2D | None:
        position = _sim_agent_position(self.env)
        if position is None:
            return None
        return Pose2D(x=position[0], y=position[2], yaw=0.0)

    def go_to(self, goal: NavigationGoal) -> NavigationBackendStatus:
        self._active_goal_id = goal.goal_id
        self._goal_position = None
        self._reason = None
        self._metadata = _oracle_metadata()

        goal_position, error_reason = _goal_position_from_navigation_goal(
            self.env,
            goal,
        )
        if goal_position is None:
            self._status = NavigationStatus.FAILED
            self._reason = error_reason
            return self.status()

        follower = self._get_follower()
        if follower is None:
            self._status = NavigationStatus.FAILED
            self._reason = "shortest_path_follower_unavailable"
            self._metadata["goal_position"] = list(goal_position)
            return self.status()

        self._goal_position = goal_position
        self._status = NavigationStatus.ACTIVE
        self._metadata["goal_position"] = list(goal_position)
        return self.status()

    def explore(self, request: ExplorationRequest) -> NavigationBackendStatus:
        if request.center is None:
            self._active_goal_id = request.request_id
            self._status = NavigationStatus.FAILED
            self._reason = "explore_requires_center"
            self._metadata = _oracle_metadata()
            return self.status()
        return self.go_to(
            NavigationGoal(
                goal_id=request.request_id,
                pose=request.center,
                frame_id=request.frame_id,
                tolerance_m=request.radius_m or 0.35,
                source=f"explore:{request.strategy}",
                metadata=dict(request.metadata),
            )
        )

    def status(self) -> NavigationBackendStatus:
        return NavigationBackendStatus(
            backend_id=self.backend_id,
            status=self._status,
            pose=self.get_pose(),
            active_goal_id=self._active_goal_id,
            reason=self._reason,
            metadata=dict(self._metadata),
        )

    def cancel(self) -> NavigationBackendStatus:
        self._status = NavigationStatus.CANCELED
        self._reason = "canceled"
        return self.status()

    def next_action(self) -> str:
        if self._status is not NavigationStatus.ACTIVE or self._goal_position is None:
            return "stop"
        follower = self._get_follower()
        if follower is None:
            self._status = NavigationStatus.FAILED
            self._reason = "shortest_path_follower_unavailable"
            return "stop"
        try:
            raw_action = follower.get_next_action(
                np.asarray(self._goal_position, dtype=float)
            )
        except Exception as exc:
            self._status = NavigationStatus.FAILED
            self._reason = "shortest_path_follower_error"
            self._metadata["error"] = str(exc)
            return "stop"
        action = _follower_action_name(raw_action)
        self._metadata["last_action"] = action
        if action == "stop":
            self._status = NavigationStatus.SUCCEEDED
            self._reason = "oracle_follower_stop"
        return action

    def _get_follower(self) -> Any | None:
        if self._follower is not None:
            return self._follower
        try:
            self._follower = self._follower_factory(
                self.env,
                goal_radius_m=self.goal_radius_m,
            )
        except TypeError:
            try:
                self._follower = self._follower_factory(self.env)
            except Exception as exc:
                self._metadata["error"] = str(exc)
                self._follower = None
        except Exception as exc:
            self._metadata["error"] = str(exc)
            self._follower = None
        return self._follower


def _make_shortest_path_follower(env: Any, *, goal_radius_m: float) -> Any | None:
    sim = getattr(env, "sim", None)
    if sim is None:
        return None
    try:
        from habitat.tasks.nav.shortest_path_follower import ShortestPathFollower
    except Exception:
        return None
    try:
        return ShortestPathFollower(
            sim,
            goal_radius=float(goal_radius_m),
            return_one_hot=False,
        )
    except Exception:
        return None


def _goal_position_from_navigation_goal(
    env: Any,
    goal: NavigationGoal,
) -> tuple[tuple[float, float, float] | None, str | None]:
    metadata_goal = goal.metadata.get("habitat_goal_position")
    if metadata_goal is not None:
        goal_position = _tuple3(metadata_goal)
        if goal_position is None:
            return None, "invalid_habitat_goal_position"
        return goal_position, None
    if goal.frame_id == "habitat_world":
        current_position = _sim_agent_position(env)
        y_m = current_position[1] if current_position is not None else 0.0
        return (float(goal.pose.x), float(y_m), float(goal.pose.y)), None
    return None, "habitat_goal_position_required"


def _sim_agent_position(env: Any) -> tuple[float, float, float] | None:
    sim = getattr(env, "sim", None)
    if sim is None:
        return None
    state = None
    if hasattr(sim, "get_agent_state"):
        try:
            state = sim.get_agent_state()
        except Exception:
            state = None
    if state is None and hasattr(sim, "get_agent"):
        try:
            state = sim.get_agent(0).get_state()
        except Exception:
            state = None
    return _tuple3(getattr(state, "position", None))


def _tuple3(values: Any) -> tuple[float, float, float] | None:
    if values is None:
        return None
    try:
        position = tuple(float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if len(position) != 3:
        return None
    if not all(np.isfinite(value) for value in position):
        return None
    return position


def _follower_action_name(action: Any) -> str:
    if action is None:
        return "stop"
    if isinstance(action, str):
        return action
    action_names = {
        0: "stop",
        1: "move_forward",
        2: "turn_left",
        3: "turn_right",
    }
    array = np.asarray(action)
    if array.ndim > 0 and array.size > 1:
        action_id = int(np.argmax(array))
        return action_names.get(action_id, str(action_id))
    if array.size == 1:
        try:
            action_id = int(array.reshape(-1)[0])
        except (TypeError, ValueError):
            return str(action)
        return action_names.get(action_id, str(action_id))
    return str(action)


def _oracle_metadata() -> dict[str, Any]:
    return {
        "backend_kind": "habitat_oracle_shortest_path",
        "benchmark_valid": False,
        "privileged_oracle": True,
    }
