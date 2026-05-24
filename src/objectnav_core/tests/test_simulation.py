import math

import pytest

from objectnav_core.mapping.fixtures import build_corridor_grid
from objectnav_core.mapping.frontiers import FrontierCluster
from objectnav_core.mapping.grid import CellState, OccupancyGrid
from objectnav_core.models import NavigationStatus, Pose2D, make_default_corridor_scene
from objectnav_core.planning.frontier_policies import (
    FrontierPolicyName,
    select_frontier_candidate,
)
from objectnav_core.planning.scoring import score_frontier_candidate
from objectnav_core.simulation.navigation import AStarGridNavigationClient, DiscreteStepNavigationClient
from objectnav_core.simulation.observations import ConfigTruthObjectSource


def test_fake_detector_emits_only_inside_camera_sector_and_los() -> None:
    scene = make_default_corridor_scene()
    grid = build_corridor_grid(scene, reveal_all=True)
    source = ConfigTruthObjectSource(scene)

    visible_pose = Pose2D(x=8.0, y=1.45, yaw=-math.pi / 2)
    wrong_yaw_pose = Pose2D(x=8.0, y=1.45, yaw=0.0)
    far_pose = Pose2D(x=1.0, y=1.2, yaw=0.0)

    observations = source.observations_at(visible_pose, grid)

    assert len(observations) == 1
    assert observations[0].class_name == "water_dispenser"
    assert observations[0].anchor_id == scene.anchor.anchor_id
    assert source.observations_at(wrong_yaw_pose, grid) == []
    assert source.observations_at(far_pose, grid) == []


def test_discrete_navigation_reaches_goal_and_accumulates_path_length() -> None:
    navigator = DiscreteStepNavigationClient(
        start_pose=Pose2D(x=1.0, y=1.2, yaw=0.0),
        step_size_m=0.25,
        success_radius_m=0.05,
    )

    navigator.send_goal(Pose2D(x=2.0, y=1.2, yaw=0.0))
    for _ in range(10):
        if navigator.status is NavigationStatus.SUCCEEDED:
            break
        navigator.tick(1.0)

    assert navigator.status is NavigationStatus.SUCCEEDED
    assert navigator.current_pose.x == pytest.approx(2.0)
    assert navigator.current_pose.y == pytest.approx(1.2)
    assert navigator.path_length_m == pytest.approx(1.0)


def test_astar_navigation_detours_around_occupied_cells() -> None:
    grid = _open_test_grid(width_cells=7, height_cells=7, resolution_m=1.0)
    for row in (1, 2, 3, 4):
        grid.set_cell(3, row, CellState.OCCUPIED)
    navigator = AStarGridNavigationClient(
        grid=grid,
        start_pose=Pose2D(x=1.5, y=3.5, yaw=0.0),
        step_size_m=1.0,
        success_radius_m=0.05,
    )

    navigator.send_goal(Pose2D(x=5.5, y=3.5, yaw=0.0))
    for _ in range(20):
        if navigator.status is NavigationStatus.SUCCEEDED:
            break
        navigator.tick(1.0)

    assert navigator.status is NavigationStatus.SUCCEEDED
    assert navigator.result_reason == "goal_reached"
    assert navigator.current_pose.x == pytest.approx(5.5)
    assert navigator.current_pose.y == pytest.approx(3.5)
    assert navigator.path_length_m == pytest.approx(8.0)
    assert all(grid.is_free_world(pose.x, pose.y) for pose in navigator.planned_path)


def test_astar_navigation_fails_when_unknown_gap_blocks_goal() -> None:
    grid = _open_test_grid(width_cells=5, height_cells=3, resolution_m=1.0)
    grid.set_cell(2, 1, CellState.UNKNOWN)
    navigator = AStarGridNavigationClient(
        grid=grid,
        start_pose=Pose2D(x=1.5, y=1.5, yaw=0.0),
    )

    navigator.send_goal(Pose2D(x=3.5, y=1.5, yaw=0.0))

    assert navigator.status is NavigationStatus.FAILED
    assert navigator.result_reason == "no_path"
    assert navigator.planned_path == []


def test_astar_navigation_cancel_goal() -> None:
    grid = _open_test_grid(width_cells=5, height_cells=3, resolution_m=1.0)
    navigator = AStarGridNavigationClient(
        grid=grid,
        start_pose=Pose2D(x=1.5, y=1.5, yaw=0.0),
    )

    navigator.send_goal(Pose2D(x=3.5, y=1.5, yaw=0.0))
    navigator.cancel_goal()

    assert navigator.status is NavigationStatus.CANCELED
    assert navigator.result_reason == "canceled"
    assert navigator.goal_pose is None


def test_frontier_score_prefers_information_gain_and_penalizes_revisits() -> None:
    high_info = score_frontier_candidate(
        information_gain=10.0,
        path_cost=2.0,
        revisit_penalty=0.0,
    )
    revisited = score_frontier_candidate(
        information_gain=10.0,
        path_cost=2.0,
        revisit_penalty=5.0,
    )

    assert high_info == pytest.approx(8.0)
    assert revisited == pytest.approx(3.0)
    assert high_info > revisited


def test_nearest_frontier_policy_uses_lowest_astar_path_cost() -> None:
    grid = _open_test_grid(width_cells=10, height_cells=8, resolution_m=1.0)
    near = _frontier_at_col(col=5, rows=(1, 2), grid=grid)
    far = _frontier_at_col(col=8, rows=(1, 2, 3, 4, 5), grid=grid)

    selected = select_frontier_candidate(
        grid=grid,
        start_pose=Pose2D(x=1.5, y=2.5, yaw=0.0),
        frontiers=[far, near],
        policy=FrontierPolicyName.NEAREST_FRONTIER,
    )

    assert selected.frontier is near
    assert selected.candidate_type == "nearest_frontier"
    assert selected.path_cost_m < 3.0


def test_information_gain_policy_can_select_farther_high_gain_frontier() -> None:
    grid = _open_test_grid(width_cells=12, height_cells=9, resolution_m=1.0)
    near = _frontier_at_col(col=5, rows=(3,), grid=grid)
    far = _frontier_at_col(col=9, rows=(1, 2, 3, 4, 5, 6), grid=grid)

    selected = select_frontier_candidate(
        grid=grid,
        start_pose=Pose2D(x=1.5, y=3.5, yaw=0.0),
        frontiers=[near, far],
        policy="information_gain",
    )

    assert selected.frontier is far
    assert selected.candidate_type == "information_gain_frontier"
    assert selected.information_gain > near.centroid.distance_to(far.centroid)
    assert selected.score > 0


def _open_test_grid(width_cells: int, height_cells: int, resolution_m: float) -> OccupancyGrid:
    grid = OccupancyGrid(
        width_m=width_cells * resolution_m,
        height_m=height_cells * resolution_m,
        resolution_m=resolution_m,
    )
    for row in range(height_cells):
        for col in range(width_cells):
            is_boundary = (
                col == 0
                or row == 0
                or col == width_cells - 1
                or row == height_cells - 1
            )
            grid.set_cell(col, row, CellState.OCCUPIED if is_boundary else CellState.FREE)
    return grid


def _frontier_at_col(
    col: int,
    rows: tuple[int, ...],
    grid: OccupancyGrid,
) -> FrontierCluster:
    cells = tuple((col, row) for row in rows)
    xs, ys = zip(*(grid.cell_center(cell_col, cell_row) for cell_col, cell_row in cells), strict=True)
    return FrontierCluster(
        cells=cells,
        centroid=Pose2D(x=sum(xs) / len(xs), y=sum(ys) / len(ys)),
    )
