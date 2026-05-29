from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class HabitatActionRoute:
    actions: tuple[str, ...]
    reached_stop: bool
    final_position: tuple[float, float, float]
    executed_distance_m: float

    @property
    def action_count(self) -> int:
        return len(self.actions)


def follow_greedy_geodesic_route(
    *,
    habitat_sim: Any,
    sim: Any,
    start_position: Sequence[float],
    start_rotation: Sequence[float],
    goal_position: Sequence[float],
    max_steps: int,
    goal_radius: float,
    agent_id: int = 0,
) -> HabitatActionRoute:
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    if goal_radius <= 0.0:
        raise ValueError("goal_radius must be positive")

    agent = sim.initialize_agent(agent_id)
    _set_agent_pose(agent, start_position=start_position, start_rotation=start_rotation)
    follower = habitat_sim.nav.GreedyGeodesicFollower(
        sim.pathfinder,
        agent,
        goal_radius=goal_radius,
        stop_key="stop",
        forward_key="move_forward",
        left_key="turn_left",
        right_key="turn_right",
    )
    actions: list[str] = []
    reached_stop = False
    previous_position = _agent_position(agent)
    executed_distance = 0.0
    goal = np.asarray(goal_position, dtype=float)

    for _ in range(max_steps):
        action = follower.next_action_along(goal)
        if action is None or str(action) == "stop":
            reached_stop = True
            break
        action_name = str(action)
        actions.append(action_name)
        sim.step(action_name)
        current_position = _agent_position(agent)
        executed_distance += _distance3(previous_position, current_position)
        previous_position = current_position

    return HabitatActionRoute(
        actions=tuple(actions),
        reached_stop=reached_stop,
        final_position=tuple(float(value) for value in previous_position),
        executed_distance_m=round(executed_distance, 6),
    )


def _set_agent_pose(
    agent: Any,
    *,
    start_position: Sequence[float],
    start_rotation: Sequence[float],
) -> None:
    state = agent.get_state()
    state.position = np.asarray(start_position, dtype=float)
    state.rotation = list(start_rotation)
    agent.set_state(state)


def _agent_position(agent: Any) -> np.ndarray:
    return np.asarray(agent.get_state().position, dtype=float)


def _distance3(first: np.ndarray, second: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(first, dtype=float) - np.asarray(second, dtype=float)))
