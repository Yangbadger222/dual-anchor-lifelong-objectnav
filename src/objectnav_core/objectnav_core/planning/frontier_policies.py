from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from objectnav_core.mapping.frontiers import FrontierCluster
from objectnav_core.mapping.grid import OccupancyGrid
from objectnav_core.models import NavigationStatus, Pose2D
from objectnav_core.planning.scoring import score_frontier_candidate
from objectnav_core.planning.viewpoints import plan_frontier_viewpoint
from objectnav_core.simulation.navigation import AStarGridNavigationClient


class FrontierPolicyName(str, Enum):
    FIRST_FRONTIER = "first_frontier"
    NEAREST_FRONTIER = "nearest_frontier"
    INFORMATION_GAIN = "information_gain"


@dataclass(frozen=True)
class FrontierPolicyCandidate:
    policy: FrontierPolicyName
    candidate_type: str
    frontier: FrontierCluster
    viewpoint: Pose2D
    information_gain: float
    path_cost_m: float
    revisit_penalty: float
    score: float


def select_frontier_candidate(
    grid: OccupancyGrid,
    start_pose: Pose2D,
    frontiers: list[FrontierCluster],
    policy: FrontierPolicyName | str = FrontierPolicyName.FIRST_FRONTIER,
    revisited_frontier_cells: set[tuple[int, int]] | None = None,
) -> FrontierPolicyCandidate:
    policy_name = FrontierPolicyName(policy)
    candidates = [
        candidate
        for frontier in frontiers
        if (
            candidate := _evaluate_frontier(
                grid=grid,
                start_pose=start_pose,
                frontier=frontier,
                policy=policy_name,
                revisited_frontier_cells=revisited_frontier_cells or set(),
            )
        )
        is not None
    ]
    if not candidates:
        raise ValueError("no reachable frontier candidates")

    if policy_name is FrontierPolicyName.FIRST_FRONTIER:
        return candidates[0]
    if policy_name is FrontierPolicyName.NEAREST_FRONTIER:
        return min(
            candidates,
            key=lambda candidate: (
                candidate.path_cost_m,
                candidate.frontier.centroid.x,
                candidate.frontier.centroid.y,
            ),
        )
    return max(
        candidates,
        key=lambda candidate: (
            candidate.score,
            -candidate.path_cost_m,
            -candidate.frontier.centroid.x,
            -candidate.frontier.centroid.y,
        ),
    )


def estimate_astar_path_cost_m(
    grid: OccupancyGrid,
    start_pose: Pose2D,
    goal_pose: Pose2D,
) -> float | None:
    navigator = AStarGridNavigationClient(grid=grid, start_pose=start_pose)
    navigator.send_goal(goal_pose)
    if navigator.status is NavigationStatus.FAILED:
        return None
    if navigator.status is NavigationStatus.SUCCEEDED:
        return start_pose.distance_to(goal_pose)
    path = [start_pose, *navigator.planned_path[1:]]
    return sum(first.distance_to(second) for first, second in zip(path, path[1:]))


def _evaluate_frontier(
    grid: OccupancyGrid,
    start_pose: Pose2D,
    frontier: FrontierCluster,
    policy: FrontierPolicyName,
    revisited_frontier_cells: set[tuple[int, int]],
) -> FrontierPolicyCandidate | None:
    try:
        viewpoint = plan_frontier_viewpoint(grid, frontier)
    except ValueError:
        return None
    path_cost = estimate_astar_path_cost_m(grid, start_pose, viewpoint)
    if path_cost is None:
        return None
    information_gain = float(len(frontier.cells))
    revisit_penalty = _revisit_penalty(frontier, revisited_frontier_cells)
    score = score_frontier_candidate(
        information_gain=information_gain,
        path_cost=path_cost,
        revisit_penalty=revisit_penalty,
    )
    return FrontierPolicyCandidate(
        policy=policy,
        candidate_type=_candidate_type(policy),
        frontier=frontier,
        viewpoint=viewpoint,
        information_gain=information_gain,
        path_cost_m=path_cost,
        revisit_penalty=revisit_penalty,
        score=score,
    )


def _revisit_penalty(
    frontier: FrontierCluster,
    revisited_frontier_cells: set[tuple[int, int]],
) -> float:
    if not revisited_frontier_cells:
        return 0.0
    revisited_count = sum(1 for cell in frontier.cells if cell in revisited_frontier_cells)
    if revisited_count == 0:
        return 0.0
    return float(revisited_count) / len(frontier.cells)


def _candidate_type(policy: FrontierPolicyName) -> str:
    if policy is FrontierPolicyName.FIRST_FRONTIER:
        return "frontier"
    if policy is FrontierPolicyName.NEAREST_FRONTIER:
        return "nearest_frontier"
    if policy is FrontierPolicyName.INFORMATION_GAIN:
        return "information_gain_frontier"
    raise ValueError(f"unknown frontier policy: {policy}")
