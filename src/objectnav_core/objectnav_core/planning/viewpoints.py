from __future__ import annotations

import math

from objectnav_core.mapping.frontiers import FrontierCluster
from objectnav_core.mapping.grid import OccupancyGrid
from objectnav_core.models import ObjectConfig, Pose2D


def plan_frontier_viewpoint(grid: OccupancyGrid, frontier: FrontierCluster) -> Pose2D:
    frontier_cols = [col for col, _ in frontier.cells]
    known_side_col = max(min(frontier_cols) - 3, 0)
    candidate_rows = range(1, grid.height_cells - 1)
    free_rows = [row for row in candidate_rows if grid.is_free_cell(known_side_col, row)]
    if not free_rows:
        raise ValueError("frontier has no reachable known-side viewpoint")
    row = min(
        free_rows,
        key=lambda free_row: abs(grid.cell_center(known_side_col, free_row)[1] - frontier.centroid.y),
    )
    x, y = grid.cell_center(known_side_col, row)
    yaw = math.atan2(frontier.centroid.y - y, frontier.centroid.x - x)
    return Pose2D(x=x, y=y, yaw=yaw)


def plan_verification_viewpoint(grid: OccupancyGrid, target: ObjectConfig) -> Pose2D:
    object_pose = target.pose_map
    candidates = [
        Pose2D(
            x=object_pose.x,
            y=object_pose.y + target.preferred_standoff_m,
            yaw=-math.pi / 2,
        ),
        Pose2D(
            x=object_pose.x - target.preferred_standoff_m,
            y=object_pose.y,
            yaw=0.0,
        ),
        Pose2D(
            x=object_pose.x + target.preferred_standoff_m,
            y=object_pose.y,
            yaw=math.pi,
        ),
    ]
    for candidate in candidates:
        if grid.is_free_world(candidate.x, candidate.y):
            return candidate
    raise ValueError(f"no reachable verification viewpoint for {target.object_id}")
