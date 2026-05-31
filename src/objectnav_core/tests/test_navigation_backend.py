from __future__ import annotations

from types import SimpleNamespace

import pytest

from objectnav_core.models import NavigationStatus, Pose2D
from objectnav_core.navigation.backend import (
    ExplorationRequest,
    LegacyNavigationClientBackend,
    NavigationBackend,
    NavigationGoal,
)
from objectnav_core.navigation.habitat_oracle import HabitatOracleFollowerBackend
from objectnav_core.simulation.navigation import DiscreteStepNavigationClient


class _FakeHabitatFollower:
    def __init__(self, actions: list[object]) -> None:
        self.actions = list(actions)
        self.requested_goals: list[tuple[float, float, float]] = []

    def get_next_action(self, goal_position: object) -> object:
        self.requested_goals.append(tuple(float(value) for value in goal_position))
        return self.actions.pop(0) if self.actions else None


class _FakeHabitatSim:
    def __init__(self, position: tuple[float, float, float] = (0.0, 1.5, 0.0)) -> None:
        self.state = SimpleNamespace(position=position)

    def get_agent_state(self) -> SimpleNamespace:
        return self.state


class _FakeHabitatEnv:
    def __init__(self, position: tuple[float, float, float] = (0.0, 1.5, 0.0)) -> None:
        self.sim = _FakeHabitatSim(position)


def test_navigation_goal_validates_identity_frame_and_tolerance() -> None:
    with pytest.raises(ValueError, match="goal_id"):
        NavigationGoal(goal_id=" ", pose=Pose2D(x=1.0, y=2.0))
    with pytest.raises(ValueError, match="frame_id"):
        NavigationGoal(goal_id="goal-a", pose=Pose2D(x=1.0, y=2.0), frame_id=" ")
    with pytest.raises(ValueError, match="tolerance_m"):
        NavigationGoal(
            goal_id="goal-a",
            pose=Pose2D(x=1.0, y=2.0),
            tolerance_m=0.0,
        )


def test_legacy_navigation_backend_go_to_wraps_discrete_client() -> None:
    client = DiscreteStepNavigationClient(
        start_pose=Pose2D(x=0.0, y=0.0),
        step_size_m=1.0,
        success_radius_m=0.05,
    )
    backend = LegacyNavigationClientBackend(client, backend_id="sim-discrete")

    result = backend.go_to(
        NavigationGoal(
            goal_id="memory-chair-1",
            pose=Pose2D(x=2.0, y=0.0),
            frame_id="episode",
            source="memory_guided",
        )
    )

    assert isinstance(backend, NavigationBackend)
    assert result.status is NavigationStatus.ACTIVE
    assert result.active_goal_id == "memory-chair-1"
    assert result.pose == Pose2D(x=0.0, y=0.0)
    assert backend.get_pose() == Pose2D(x=0.0, y=0.0)

    client.tick(1.0)
    client.tick(1.0)
    status = backend.status()

    assert status.status is NavigationStatus.SUCCEEDED
    assert status.reason == "goal_reached"
    assert status.pose == Pose2D(x=2.0, y=0.0)
    assert status.path_length_m == pytest.approx(2.0)


def test_legacy_navigation_backend_explore_goes_to_region_center() -> None:
    client = DiscreteStepNavigationClient(start_pose=Pose2D(x=0.0, y=0.0))
    backend = LegacyNavigationClientBackend(client, backend_id="sim-discrete")

    result = backend.explore(
        ExplorationRequest(
            request_id="explore-room-a",
            center=Pose2D(x=1.5, y=0.5),
            radius_m=2.0,
            strategy="frontier",
        )
    )

    assert result.status is NavigationStatus.ACTIVE
    assert result.active_goal_id == "explore-room-a"
    assert client.goal_pose == Pose2D(x=1.5, y=0.5)


def test_legacy_navigation_backend_explore_without_center_fails_clearly() -> None:
    backend = LegacyNavigationClientBackend(
        DiscreteStepNavigationClient(start_pose=Pose2D(x=0.0, y=0.0)),
        backend_id="sim-discrete",
    )

    result = backend.explore(ExplorationRequest(request_id="explore-anywhere"))

    assert result.status is NavigationStatus.FAILED
    assert result.reason == "explore_requires_center"
    assert result.active_goal_id == "explore-anywhere"


def test_legacy_navigation_backend_cancel_maps_client_status() -> None:
    client = DiscreteStepNavigationClient(start_pose=Pose2D(x=0.0, y=0.0))
    backend = LegacyNavigationClientBackend(client, backend_id="sim-discrete")
    backend.go_to(
        NavigationGoal(goal_id="memory-goal", pose=Pose2D(x=1.0, y=0.0))
    )

    result = backend.cancel()

    assert result.status is NavigationStatus.CANCELED
    assert result.reason == "canceled"
    assert result.active_goal_id == "memory-goal"
    assert backend.status().status is NavigationStatus.CANCELED


def test_exploration_request_validates_request_id_and_radius() -> None:
    with pytest.raises(ValueError, match="request_id"):
        ExplorationRequest(request_id=" ")
    with pytest.raises(ValueError, match="radius_m"):
        ExplorationRequest(request_id="explore", radius_m=0.0)


def test_habitat_oracle_follower_backend_uses_metadata_goal_and_emits_actions() -> None:
    env = _FakeHabitatEnv()
    follower = _FakeHabitatFollower([1, "turn_left", None])
    backend = HabitatOracleFollowerBackend(
        env,
        follower_factory=lambda _env, *, goal_radius_m: follower,
        backend_id="oracle-test",
    )

    result = backend.go_to(
        NavigationGoal(
            goal_id="memory-upper-bound-goal",
            pose=Pose2D(x=0.0, y=0.0),
            frame_id="episode",
            source="memory_upper_bound",
            metadata={"habitat_goal_position": [1.0, 0.0, 2.0]},
        )
    )

    assert isinstance(backend, NavigationBackend)
    assert result.status is NavigationStatus.ACTIVE
    assert result.active_goal_id == "memory-upper-bound-goal"
    assert result.metadata["privileged_oracle"] is True
    assert result.metadata["goal_position"] == [1.0, 0.0, 2.0]

    assert backend.next_action() == "move_forward"
    assert backend.next_action() == "turn_left"
    assert backend.next_action() == "stop"
    assert follower.requested_goals == [
        (1.0, 0.0, 2.0),
        (1.0, 0.0, 2.0),
        (1.0, 0.0, 2.0),
    ]
    assert backend.status().status is NavigationStatus.SUCCEEDED
    assert backend.status().reason == "oracle_follower_stop"


def test_habitat_oracle_follower_backend_requires_explicit_goal_for_episode_frame() -> None:
    backend = HabitatOracleFollowerBackend(
        _FakeHabitatEnv(),
        follower_factory=lambda _env, *, goal_radius_m: _FakeHabitatFollower([]),
    )

    result = backend.go_to(
        NavigationGoal(
            goal_id="episode-goal",
            pose=Pose2D(x=1.0, y=2.0),
            frame_id="episode",
        )
    )

    assert result.status is NavigationStatus.FAILED
    assert result.reason == "habitat_goal_position_required"
    assert result.active_goal_id == "episode-goal"


def test_habitat_oracle_follower_backend_uses_habitat_world_pose_fallback() -> None:
    env = _FakeHabitatEnv(position=(0.0, 1.25, 0.0))
    follower = _FakeHabitatFollower(["stop"])
    backend = HabitatOracleFollowerBackend(
        env,
        follower_factory=lambda _env, *, goal_radius_m: follower,
    )

    result = backend.go_to(
        NavigationGoal(
            goal_id="world-goal",
            pose=Pose2D(x=3.0, y=4.0),
            frame_id="habitat_world",
        )
    )

    assert result.status is NavigationStatus.ACTIVE
    assert backend.next_action() == "stop"
    assert follower.requested_goals == [(3.0, 1.25, 4.0)]


def test_habitat_oracle_follower_backend_unavailable_fails_clearly() -> None:
    backend = HabitatOracleFollowerBackend(
        _FakeHabitatEnv(),
        follower_factory=lambda _env, *, goal_radius_m: None,
    )

    result = backend.go_to(
        NavigationGoal(
            goal_id="oracle-goal",
            pose=Pose2D(x=0.0, y=0.0),
            metadata={"habitat_goal_position": [1.0, 0.0, 2.0]},
        )
    )

    assert result.status is NavigationStatus.FAILED
    assert result.reason == "shortest_path_follower_unavailable"


def test_habitat_oracle_follower_backend_factory_exception_fails_status() -> None:
    def broken_factory(_env: object) -> object:
        raise RuntimeError("factory boom")

    backend = HabitatOracleFollowerBackend(
        _FakeHabitatEnv(),
        follower_factory=broken_factory,
    )

    result = backend.go_to(
        NavigationGoal(
            goal_id="oracle-goal",
            pose=Pose2D(x=0.0, y=0.0),
            metadata={"habitat_goal_position": [1.0, 0.0, 2.0]},
        )
    )

    assert result.status is NavigationStatus.FAILED
    assert result.reason == "shortest_path_follower_unavailable"
    assert result.metadata["error"] == "factory boom"


def test_habitat_oracle_follower_backend_cancel_stops_active_goal() -> None:
    backend = HabitatOracleFollowerBackend(
        _FakeHabitatEnv(),
        follower_factory=lambda _env, *, goal_radius_m: _FakeHabitatFollower([1]),
    )
    backend.go_to(
        NavigationGoal(
            goal_id="oracle-goal",
            pose=Pose2D(x=0.0, y=0.0),
            metadata={"habitat_goal_position": [1.0, 0.0, 2.0]},
        )
    )

    result = backend.cancel()

    assert result.status is NavigationStatus.CANCELED
    assert result.reason == "canceled"
    assert result.active_goal_id == "oracle-goal"
    assert backend.next_action() == "stop"
