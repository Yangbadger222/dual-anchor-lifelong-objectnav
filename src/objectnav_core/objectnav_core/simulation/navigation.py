from __future__ import annotations

import math

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
