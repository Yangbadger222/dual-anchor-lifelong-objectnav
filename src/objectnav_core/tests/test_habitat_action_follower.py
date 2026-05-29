from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from objectnav_core.evaluation.habitat_action_follower import (
    HabitatActionRoute,
    follow_greedy_geodesic_route,
)


class _FakeAgent:
    def __init__(self) -> None:
        self.state = SimpleNamespace(
            position=np.asarray([0.0, 0.0, 0.0], dtype=float),
            rotation=[0.0, 0.0, 0.0, 1.0],
        )

    def get_state(self) -> SimpleNamespace:
        return self.state

    def set_state(self, state: SimpleNamespace) -> None:
        self.state = state


class _FakeFollower:
    def __init__(self, actions: tuple[str, ...]) -> None:
        self.actions = list(actions)

    def next_action_along(self, _goal: np.ndarray) -> str:
        return self.actions.pop(0)


class _FakeNav:
    class GreedyGeodesicFollower:
        def __init__(self, _pathfinder, _agent, **_kwargs) -> None:
            self.impl = _FakeFollower(("move_forward", "turn_left", "stop"))

        def next_action_along(self, goal: np.ndarray) -> str:
            return self.impl.next_action_along(goal)


class _FakeHabitatSim:
    nav = _FakeNav()


class _FakeSim:
    pathfinder = object()

    def __init__(self) -> None:
        self.agent = _FakeAgent()
        self.stepped_actions: list[str] = []

    def initialize_agent(self, _agent_id: int) -> _FakeAgent:
        return self.agent

    def step(self, action: str) -> None:
        self.stepped_actions.append(action)
        state = self.agent.get_state()
        state.position = state.position + np.asarray([0.25, 0.0, 0.0])
        self.agent.set_state(state)


def test_follow_greedy_geodesic_route_steps_until_stop() -> None:
    sim = _FakeSim()

    route = follow_greedy_geodesic_route(
        habitat_sim=_FakeHabitatSim(),
        sim=sim,
        start_position=(1.0, 0.0, 2.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        goal_position=(2.0, 0.0, 2.0),
        max_steps=10,
        goal_radius=0.2,
    )

    assert isinstance(route, HabitatActionRoute)
    assert route.reached_stop is True
    assert route.actions == ("move_forward", "turn_left")
    assert route.action_count == 2
    assert route.executed_distance_m == 0.5
    assert sim.stepped_actions == ["move_forward", "turn_left"]
