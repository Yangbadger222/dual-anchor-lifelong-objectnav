from __future__ import annotations

import math
from heapq import heappop, heappush

from objectnav_core.mapping.grid import OccupancyGrid
from objectnav_core.models import NavigationStatus, Pose2D


class DiscreteStepNavigationClient:
    def __init__(
        self,
        start_pose: Pose2D,
        step_size_m: float = 0.25,
        success_radius_m: float = 0.05,
    ) -> None:
        self.current_pose = start_pose
        self.step_size_m = step_size_m
        self.success_radius_m = success_radius_m
        self.status = NavigationStatus.IDLE
        self.goal_pose: Pose2D | None = None
        self.path_length_m = 0.0
        self.result_reason: str | None = None

    def send_goal(self, goal_pose: Pose2D) -> None:
        self.goal_pose = goal_pose
        self.status = NavigationStatus.ACTIVE
        self.result_reason = None

    def cancel_goal(self) -> None:
        self.status = NavigationStatus.CANCELED
        self.result_reason = "canceled"
        self.goal_pose = None

    def tick(self, dt: float) -> NavigationStatus:
        if self.status is not NavigationStatus.ACTIVE or self.goal_pose is None:
            return self.status
        distance = self.current_pose.distance_to(self.goal_pose)
        if distance <= self.success_radius_m:
            self.current_pose = self.goal_pose
            self.status = NavigationStatus.SUCCEEDED
            self.result_reason = "goal_reached"
            return self.status

        step = min(self.step_size_m * dt, distance)
        direction = math.atan2(
            self.goal_pose.y - self.current_pose.y,
            self.goal_pose.x - self.current_pose.x,
        )
        next_pose = Pose2D(
            x=self.current_pose.x + math.cos(direction) * step,
            y=self.current_pose.y + math.sin(direction) * step,
            yaw=direction,
        )
        self.current_pose = next_pose
        self.path_length_m += step

        if self.current_pose.distance_to(self.goal_pose) <= self.success_radius_m:
            self.path_length_m += self.current_pose.distance_to(self.goal_pose)
            self.current_pose = self.goal_pose
            self.status = NavigationStatus.SUCCEEDED
            self.result_reason = "goal_reached"
        return self.status


class AStarGridNavigationClient:
    def __init__(
        self,
        grid: OccupancyGrid,
        start_pose: Pose2D,
        step_size_m: float = 0.25,
        success_radius_m: float = 0.05,
    ) -> None:
        self.grid = grid
        self.current_pose = start_pose
        self.step_size_m = step_size_m
        self.success_radius_m = success_radius_m
        self.status = NavigationStatus.IDLE
        self.goal_pose: Pose2D | None = None
        self.path_length_m = 0.0
        self.result_reason: str | None = None
        self.planned_path: list[Pose2D] = []
        self._waypoints: list[Pose2D] = []

    def send_goal(self, goal_pose: Pose2D) -> None:
        self.goal_pose = goal_pose
        self.result_reason = None
        self.path_length_m = 0.0
        self.planned_path = []
        self._waypoints = []

        start_cell = self.grid.world_to_cell(self.current_pose.x, self.current_pose.y)
        goal_cell = self.grid.world_to_cell(goal_pose.x, goal_pose.y)
        if not self.grid.is_free_cell(*start_cell):
            self.status = NavigationStatus.FAILED
            self.result_reason = "start_not_free"
            return
        if not self.grid.is_free_cell(*goal_cell):
            self.status = NavigationStatus.FAILED
            self.result_reason = "goal_not_free"
            return

        path_cells = self._find_path(start_cell, goal_cell)
        if path_cells is None:
            self.status = NavigationStatus.FAILED
            self.result_reason = "no_path"
            return

        self.planned_path = [self._pose_for_cell(col, row) for col, row in path_cells]
        self._waypoints = self.planned_path[1:]
        if not self._waypoints:
            self.current_pose = goal_pose
            self.status = NavigationStatus.SUCCEEDED
            self.result_reason = "goal_reached"
            return
        self._waypoints[-1] = goal_pose
        self.planned_path[-1] = goal_pose
        self.status = NavigationStatus.ACTIVE

    def cancel_goal(self) -> None:
        self.status = NavigationStatus.CANCELED
        self.result_reason = "canceled"
        self.goal_pose = None
        self._waypoints = []

    def tick(self, dt: float) -> NavigationStatus:
        if self.status is not NavigationStatus.ACTIVE:
            return self.status
        step_remaining = max(0.0, self.step_size_m * dt)
        while step_remaining > 0 and self._waypoints:
            target = self._waypoints[0]
            distance = self.current_pose.distance_to(target)
            if distance <= self.success_radius_m:
                self.current_pose = target
                self._waypoints.pop(0)
                continue
            step = min(step_remaining, distance)
            yaw = math.atan2(target.y - self.current_pose.y, target.x - self.current_pose.x)
            self.current_pose = Pose2D(
                x=self.current_pose.x + math.cos(yaw) * step,
                y=self.current_pose.y + math.sin(yaw) * step,
                yaw=yaw,
            )
            self.path_length_m += step
            step_remaining -= step
            if self.current_pose.distance_to(target) <= self.success_radius_m:
                remaining = self.current_pose.distance_to(target)
                self.path_length_m += remaining
                self.current_pose = target
                self._waypoints.pop(0)
        if not self._waypoints:
            if self.goal_pose is not None:
                self.current_pose = self.goal_pose
            self.status = NavigationStatus.SUCCEEDED
            self.result_reason = "goal_reached"
        return self.status

    def _find_path(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
    ) -> list[tuple[int, int]] | None:
        open_set: list[tuple[float, tuple[int, int]]] = []
        heappush(open_set, (0.0, start))
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        g_score = {start: 0.0}

        while open_set:
            _, current = heappop(open_set)
            if current == goal:
                return self._reconstruct_path(came_from, current)
            for neighbor in self._free_neighbors(current):
                tentative = g_score[current] + 1.0
                if tentative >= g_score.get(neighbor, math.inf):
                    continue
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                priority = tentative + self._manhattan(neighbor, goal)
                heappush(open_set, (priority, neighbor))
        return None

    def _free_neighbors(self, cell: tuple[int, int]) -> list[tuple[int, int]]:
        col, row = cell
        candidates = ((col + 1, row), (col, row + 1), (col, row - 1), (col - 1, row))
        return [
            (candidate_col, candidate_row)
            for candidate_col, candidate_row in candidates
            if self.grid.is_free_cell(candidate_col, candidate_row)
        ]

    def _pose_for_cell(self, col: int, row: int) -> Pose2D:
        x, y = self.grid.cell_center(col, row)
        return Pose2D(x=x, y=y, yaw=0.0)

    def _reconstruct_path(
        self,
        came_from: dict[tuple[int, int], tuple[int, int]],
        current: tuple[int, int],
    ) -> list[tuple[int, int]]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        return list(reversed(path))

    def _manhattan(self, first: tuple[int, int], second: tuple[int, int]) -> float:
        return abs(first[0] - second[0]) + abs(first[1] - second[1])
