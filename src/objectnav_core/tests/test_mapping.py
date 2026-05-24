import math

import pytest

from objectnav_core.mapping.fixtures import build_corridor_grid
from objectnav_core.mapping.frontiers import extract_frontier_clusters
from objectnav_core.models import Pose2D, make_default_corridor_scene
from objectnav_core.planning.viewpoints import (
    plan_frontier_viewpoint,
    plan_verification_viewpoint,
)


def test_corridor_fixture_starts_partially_unknown_with_boundary_walls() -> None:
    scene = make_default_corridor_scene()
    grid = build_corridor_grid(scene)

    assert grid.width_cells == 120
    assert grid.height_cells == 24
    assert grid.is_free_world(1.0, 1.2)
    assert grid.is_unknown_world(6.0, 1.2)
    assert grid.is_occupied_world(1.0, 0.0)
    assert grid.is_occupied_world(11.9, 2.39)


def test_forward_sector_reveals_only_visible_cells_in_front() -> None:
    scene = make_default_corridor_scene()
    grid = build_corridor_grid(scene)
    pose = Pose2D(x=2.8, y=1.2, yaw=0.0)

    changed = grid.reveal_forward_sector(pose, scene.reveal_model)

    assert changed > 0
    assert grid.is_free_world(4.2, 1.2)
    assert grid.is_unknown_world(3.3, 2.2)
    assert grid.is_unknown_world(6.0, 1.2)


def test_frontier_cluster_yields_reachable_known_side_viewpoint() -> None:
    scene = make_default_corridor_scene()
    grid = build_corridor_grid(scene)
    clusters = extract_frontier_clusters(grid)

    assert len(clusters) == 1
    viewpoint = plan_frontier_viewpoint(grid, clusters[0])

    assert grid.is_free_world(viewpoint.x, viewpoint.y)
    assert viewpoint.x < clusters[0].centroid.x
    assert viewpoint.y == pytest.approx(1.2, abs=0.2)
    assert viewpoint.yaw == pytest.approx(0.0, abs=0.2)


def test_verification_viewpoint_stands_off_wall_adjacent_object() -> None:
    scene = make_default_corridor_scene()
    grid = build_corridor_grid(scene, reveal_all=True)
    target = scene.objects[0]

    viewpoint = plan_verification_viewpoint(grid, target)

    assert grid.is_free_world(viewpoint.x, viewpoint.y)
    assert viewpoint.x == pytest.approx(target.pose_map.x, abs=0.15)
    assert viewpoint.y == pytest.approx(target.pose_map.y + target.preferred_standoff_m, abs=0.15)
    assert viewpoint.yaw == pytest.approx(-math.pi / 2, abs=0.15)
