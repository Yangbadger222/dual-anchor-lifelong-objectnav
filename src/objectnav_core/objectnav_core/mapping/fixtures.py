from __future__ import annotations

from objectnav_core.mapping.grid import CellState, OccupancyGrid
from objectnav_core.models import SceneConfig


def build_corridor_grid(scene: SceneConfig, reveal_all: bool = False) -> OccupancyGrid:
    grid = OccupancyGrid(
        width_m=scene.map.width_m,
        height_m=scene.map.height_m,
        resolution_m=scene.map.resolution_m,
    )

    for row in range(grid.height_cells):
        for col in range(grid.width_cells):
            x, y = grid.cell_center(col, row)
            is_wall = (
                col == 0
                or row == 0
                or col == grid.width_cells - 1
                or row == grid.height_cells - 1
            )
            if is_wall:
                grid.set_cell(col, row, CellState.OCCUPIED)
            elif reveal_all or (
                scene.map.known_at_start.x_min <= x <= scene.map.known_at_start.x_max
                and scene.map.known_at_start.y_min <= y <= scene.map.known_at_start.y_max
            ):
                grid.set_cell(col, row, CellState.FREE)
            else:
                grid.set_cell(col, row, CellState.UNKNOWN)
    return grid


def build_multiroom_grid(scene: SceneConfig, reveal_all: bool = False) -> OccupancyGrid:
    grid = OccupancyGrid(
        width_m=scene.map.width_m,
        height_m=scene.map.height_m,
        resolution_m=scene.map.resolution_m,
    )

    for row in range(grid.height_cells):
        for col in range(grid.width_cells):
            x, y = grid.cell_center(col, row)
            if _is_multiroom_wall(x, y, scene):
                grid.set_cell(col, row, CellState.OCCUPIED)
            elif reveal_all or (
                scene.map.known_at_start.x_min <= x <= scene.map.known_at_start.x_max
                and scene.map.known_at_start.y_min <= y <= scene.map.known_at_start.y_max
            ):
                grid.set_cell(col, row, CellState.FREE)
            else:
                grid.set_cell(col, row, CellState.UNKNOWN)
    return grid


def _is_multiroom_wall(x: float, y: float, scene: SceneConfig) -> bool:
    if (
        x <= scene.map.resolution_m
        or y <= scene.map.resolution_m
        or x >= scene.map.width_m - scene.map.resolution_m
        or y >= scene.map.height_m - scene.map.resolution_m
    ):
        return True

    if 3.8 <= x <= 4.05 and not (4.3 <= y <= 5.7):
        return True
    if 8.0 <= x <= 8.25 and not (4.3 <= y <= 5.7) and not (7.2 <= y <= 8.8):
        return True
    if (
        4.0 <= x <= 13.7
        and (3.7 <= y <= 4.0 or 6.0 <= y <= 6.3)
        and not (10.7 <= x <= 11.8)
    ):
        return True
    return False
