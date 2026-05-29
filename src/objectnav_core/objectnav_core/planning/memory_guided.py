from __future__ import annotations

from dataclasses import dataclass

from objectnav_core.mapping.frontiers import FrontierCluster
from objectnav_core.mapping.grid import OccupancyGrid
from objectnav_core.models import MemoryObject, Pose2D
from objectnav_core.planning.frontier_policies import estimate_astar_path_cost_m
from objectnav_core.planning.viewpoints import plan_frontier_viewpoint


MEMORY_MISS_SEARCH_COST_M = 28.0


@dataclass(frozen=True)
class NavigationCandidate:
    candidate_type: str
    goal_pose: Pose2D
    object_id: str | None
    class_name: str
    expected_success: float
    information_gain: float
    path_cost_m: float
    verification_cost_m: float
    stale_penalty: float
    score: float
    frontier_cells: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True)
class MemoryMatchEvidence:
    accepted: bool
    reason: str
    mahalanobis_distance: float | None = None


def select_memory_guided_candidate(
    *,
    grid: OccupancyGrid,
    start_pose: Pose2D,
    target_class: str,
    memories: list[MemoryObject],
    frontiers: list[FrontierCluster],
    visited_frontier_cells: set[tuple[int, int]] | None = None,
    memory_grid: OccupancyGrid | None = None,
    memory_match_evidence: dict[str, MemoryMatchEvidence] | None = None,
) -> NavigationCandidate:
    visited = visited_frontier_cells or set()
    memory_reachability_grid = memory_grid or grid
    candidates: list[NavigationCandidate] = []
    candidates.extend(
        _memory_candidate(
            memory_reachability_grid,
            start_pose,
            memory,
            match_evidence=(
                memory_match_evidence or {}
            ).get(memory.object_id),
        )
        for memory in memories
        if memory.class_name == target_class and memory.verification_viewpoint is not None
    )
    candidates.extend(
        candidate
        for frontier in frontiers
        if (
            candidate := _frontier_candidate(
                grid=grid,
                start_pose=start_pose,
                target_class=target_class,
                frontier=frontier,
                visited_frontier_cells=visited,
            )
        )
        is not None
    )
    reachable_candidates = [
        candidate for candidate in candidates if candidate.path_cost_m != float("inf")
    ]
    if not reachable_candidates:
        raise ValueError("no reachable memory or frontier candidates")
    return max(
        reachable_candidates,
        key=lambda candidate: (
            candidate.score,
            candidate.candidate_type == "memory",
            -candidate.path_cost_m,
            candidate.object_id or "",
        ),
    )


def _memory_candidate(
    grid: OccupancyGrid,
    start_pose: Pose2D,
    memory: MemoryObject,
    *,
    match_evidence: MemoryMatchEvidence | None = None,
) -> NavigationCandidate:
    assert memory.verification_viewpoint is not None
    path_cost = estimate_astar_path_cost_m(
        grid=grid,
        start_pose=start_pose,
        goal_pose=memory.verification_viewpoint,
    )
    expected_success = _memory_expected_success(memory, match_evidence=match_evidence)
    verification_cost = 1.0
    stale_penalty = 1.5 if memory.state.value == "suspect_missing" else 0.0
    if match_evidence is not None and not match_evidence.accepted:
        stale_penalty += 6.0
    if path_cost is None:
        path_cost = float("inf")
    score = (
        expected_success * MEMORY_MISS_SEARCH_COST_M
        - path_cost
        - verification_cost
        - stale_penalty
    )
    return NavigationCandidate(
        candidate_type="memory",
        goal_pose=memory.verification_viewpoint,
        object_id=memory.object_id,
        class_name=memory.class_name,
        expected_success=expected_success,
        information_gain=0.0,
        path_cost_m=path_cost,
        verification_cost_m=verification_cost,
        stale_penalty=stale_penalty,
        score=score,
    )


def _frontier_candidate(
    *,
    grid: OccupancyGrid,
    start_pose: Pose2D,
    target_class: str,
    frontier: FrontierCluster,
    visited_frontier_cells: set[tuple[int, int]],
) -> NavigationCandidate | None:
    new_cells = tuple(cell for cell in frontier.cells if cell not in visited_frontier_cells)
    if not new_cells:
        return None
    try:
        viewpoint = plan_frontier_viewpoint(grid, frontier)
    except ValueError:
        return None
    path_cost = estimate_astar_path_cost_m(
        grid=grid,
        start_pose=start_pose,
        goal_pose=viewpoint,
    )
    if path_cost is None:
        return None
    if path_cost <= 0.05:
        return None
    information_gain = float(len(new_cells))
    score = information_gain * 0.35 - path_cost
    return NavigationCandidate(
        candidate_type="frontier",
        goal_pose=viewpoint,
        object_id=None,
        class_name=target_class,
        expected_success=0.0,
        information_gain=information_gain,
        path_cost_m=path_cost,
        verification_cost_m=0.0,
        stale_penalty=0.0,
        score=score,
        frontier_cells=tuple(frontier.cells),
    )


def _memory_expected_success(
    memory: MemoryObject,
    *,
    match_evidence: MemoryMatchEvidence | None = None,
) -> float:
    if match_evidence is not None and not match_evidence.accepted:
        return 0.05
    if memory.state.value == "reusable":
        return max(0.2, min(0.98, memory.confidence))
    if memory.state.value == "verified":
        return max(0.1, min(0.9, memory.confidence * 0.9))
    if memory.state.value == "suspect_missing":
        return max(0.05, min(0.35, memory.confidence * 0.35))
    return 0.0
