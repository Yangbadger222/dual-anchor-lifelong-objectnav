from __future__ import annotations

import math
from enum import IntEnum

import numpy as np

from objectnav_core.models import Pose2D, RevealModelConfig


class CellState(IntEnum):
    UNKNOWN = -1
    FREE = 0
    OCCUPIED = 1


class OccupancyGrid:
    def __init__(self, width_m: float, height_m: float, resolution_m: float) -> None:
        self.width_m = width_m
        self.height_m = height_m
        self.resolution_m = resolution_m
        self.width_cells = int(round(width_m / resolution_m))
        self.height_cells = int(round(height_m / resolution_m))
        self.data = np.full(
            (self.height_cells, self.width_cells),
            CellState.UNKNOWN,
            dtype=np.int8,
        )

    def in_bounds_cell(self, col: int, row: int) -> bool:
        return 0 <= col < self.width_cells and 0 <= row < self.height_cells

    def world_to_cell(self, x: float, y: float) -> tuple[int, int]:
        col = int(math.floor(x / self.resolution_m))
        row = int(math.floor(y / self.resolution_m))
        col = min(max(col, 0), self.width_cells - 1)
        row = min(max(row, 0), self.height_cells - 1)
        return col, row

    def cell_center(self, col: int, row: int) -> tuple[float, float]:
        return (
            (col + 0.5) * self.resolution_m,
            (row + 0.5) * self.resolution_m,
        )

    def get_cell(self, col: int, row: int) -> CellState:
        if not self.in_bounds_cell(col, row):
            return CellState.OCCUPIED
        return CellState(int(self.data[row, col]))

    def set_cell(self, col: int, row: int, state: CellState) -> None:
        if self.in_bounds_cell(col, row):
            self.data[row, col] = state

    def get_world(self, x: float, y: float) -> CellState:
        return self.get_cell(*self.world_to_cell(x, y))

    def is_free_cell(self, col: int, row: int) -> bool:
        return self.get_cell(col, row) == CellState.FREE

    def is_unknown_cell(self, col: int, row: int) -> bool:
        return self.get_cell(col, row) == CellState.UNKNOWN

    def is_occupied_cell(self, col: int, row: int) -> bool:
        return self.get_cell(col, row) == CellState.OCCUPIED

    def is_free_world(self, x: float, y: float) -> bool:
        return self.get_world(x, y) == CellState.FREE

    def is_unknown_world(self, x: float, y: float) -> bool:
        return self.get_world(x, y) == CellState.UNKNOWN

    def is_occupied_world(self, x: float, y: float) -> bool:
        return self.get_world(x, y) == CellState.OCCUPIED

    def has_line_of_sight(self, start: Pose2D, end: Pose2D, step_m: float = 0.05) -> bool:
        distance = start.distance_to(end)
        steps = max(1, int(math.ceil(distance / step_m)))
        for index in range(1, steps + 1):
            ratio = index / steps
            x = start.x + (end.x - start.x) * ratio
            y = start.y + (end.y - start.y) * ratio
            if self.is_occupied_world(x, y):
                return False
        return True

    def reveal_forward_sector(self, pose: Pose2D, config: RevealModelConfig) -> int:
        changed = 0
        half_fov = math.radians(config.horizontal_fov_deg) / 2.0
        max_cells = int(math.ceil(config.max_range_m / self.resolution_m))
        origin_col, origin_row = self.world_to_cell(pose.x, pose.y)

        for row in range(origin_row - max_cells, origin_row + max_cells + 1):
            for col in range(origin_col - max_cells, origin_col + max_cells + 1):
                if not self.in_bounds_cell(col, row):
                    continue
                if not self.is_unknown_cell(col, row):
                    continue
                x, y = self.cell_center(col, row)
                dx = x - pose.x
                dy = y - pose.y
                distance = math.hypot(dx, dy)
                if distance > config.max_range_m:
                    continue
                angle = math.atan2(math.sin(math.atan2(dy, dx) - pose.yaw), math.cos(math.atan2(dy, dx) - pose.yaw))
                if abs(angle) > half_fov:
                    continue
                if not self.has_line_of_sight(pose, Pose2D(x=x, y=y), config.raycast_step_m):
                    continue
                self.set_cell(col, row, CellState.FREE)
                changed += 1
        return changed

