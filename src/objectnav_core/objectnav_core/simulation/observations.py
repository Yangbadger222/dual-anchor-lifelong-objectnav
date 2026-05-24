from __future__ import annotations

import math

from objectnav_core.mapping.grid import OccupancyGrid
from objectnav_core.models import ObjectObservation, Pose2D, SceneConfig


class ConfigTruthObjectSource:
    def __init__(self, scene: SceneConfig, detector_name: str = "config_truth") -> None:
        self.scene = scene
        self.detector_name = detector_name

    def observations_at(self, robot_pose: Pose2D, grid: OccupancyGrid) -> list[ObjectObservation]:
        observations: list[ObjectObservation] = []
        detector = self.scene.fake_detector
        half_fov = math.radians(detector.horizontal_fov_deg) / 2.0
        for obj in self.scene.objects:
            if not obj.active:
                continue
            distance = robot_pose.distance_to(obj.pose_map)
            if distance < detector.min_range_m or distance > detector.max_range_m:
                continue
            bearing = math.atan2(obj.pose_map.y - robot_pose.y, obj.pose_map.x - robot_pose.x)
            relative = math.atan2(
                math.sin(bearing - robot_pose.yaw),
                math.cos(bearing - robot_pose.yaw),
            )
            if abs(relative) > half_fov:
                continue
            if detector.require_line_of_sight and not grid.has_line_of_sight(robot_pose, obj.pose_map):
                continue
            observations.append(
                ObjectObservation(
                    object_id=obj.object_id,
                    class_name=obj.class_name,
                    confidence=1.0,
                    pose=obj.pose_map,
                    anchor_id=self.scene.anchor.anchor_id,
                    anchor_type=self.scene.anchor.anchor_type,
                    frame_id=self.scene.anchor.frame_id,
                    detector_name=self.detector_name,
                )
            )
        return observations

