from __future__ import annotations

import math
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AnchorType(str, Enum):
    INDOOR_MAP = "indoor_map"
    OUTDOOR_MAP = "outdoor_map"
    GPS_RTK = "gps_rtk"


class MemoryState(str, Enum):
    OBSERVED = "observed"
    VERIFIED = "verified"
    REUSABLE = "reusable"
    STALE = "stale"
    SUSPECT_MISSING = "suspect_missing"
    MISSING = "missing"


class NavigationStatus(str, Enum):
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class Pose2D(BaseModel):
    x: float
    y: float
    yaw: float = 0.0

    def distance_to(self, other: "Pose2D") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


class AnchorConfig(BaseModel):
    anchor_id: str
    anchor_type: AnchorType
    frame_id: str


class Bounds2D(BaseModel):
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @field_validator("x_max")
    @classmethod
    def _x_max_exceeds_min(cls, value: float, info: Any) -> float:
        x_min = info.data.get("x_min")
        if x_min is not None and value <= x_min:
            raise ValueError("x_max must be greater than x_min")
        return value

    @field_validator("y_max")
    @classmethod
    def _y_max_exceeds_min(cls, value: float, info: Any) -> float:
        y_min = info.data.get("y_min")
        if y_min is not None and value <= y_min:
            raise ValueError("y_max must be greater than y_min")
        return value


class MapConfig(BaseModel):
    width_m: float
    height_m: float
    resolution_m: float
    known_at_start: Bounds2D

    @field_validator("width_m", "height_m", "resolution_m")
    @classmethod
    def _positive_dimensions(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("map dimensions and resolution must be positive")
        return value


class RevealModelConfig(BaseModel):
    max_range_m: float
    horizontal_fov_deg: float
    raycast_step_m: float = 0.05

    @field_validator("max_range_m", "horizontal_fov_deg", "raycast_step_m")
    @classmethod
    def _positive_values(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("reveal model values must be positive")
        return value


class FakeDetectorConfig(BaseModel):
    min_range_m: float = 0.05
    max_range_m: float
    horizontal_fov_deg: float
    require_line_of_sight: bool = True

    @field_validator("min_range_m", "max_range_m", "horizontal_fov_deg")
    @classmethod
    def _positive_values(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("detector range and fov values must be positive")
        return value

    @field_validator("max_range_m")
    @classmethod
    def _max_exceeds_min(cls, value: float, info: Any) -> float:
        min_range_m = info.data.get("min_range_m")
        if min_range_m is not None and value <= min_range_m:
            raise ValueError("detector max_range_m must exceed min_range_m")
        return value


class ObjectConfig(BaseModel):
    object_id: str
    class_name: str
    pose_map: Pose2D
    active: bool = True
    preferred_standoff_m: float = 1.2

    @field_validator("preferred_standoff_m")
    @classmethod
    def _positive_standoff(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("preferred_standoff_m must be positive")
        return value


class SceneConfig(BaseModel):
    scene_id: str
    anchor: AnchorConfig
    map: MapConfig
    objects: list[ObjectConfig]
    reveal_model: RevealModelConfig
    fake_detector: FakeDetectorConfig

    @field_validator("objects")
    @classmethod
    def _requires_objects(cls, value: list[ObjectConfig]) -> list[ObjectConfig]:
        if not value:
            raise ValueError("scene must contain at least one object")
        return value


class ObjectObservation(BaseModel):
    object_id: str
    class_name: str
    confidence: float
    pose: Pose2D
    anchor_id: str
    anchor_type: AnchorType
    frame_id: str
    detector_name: str
    timestamp: float = Field(default_factory=time.time)

    @field_validator("confidence")
    @classmethod
    def _confidence_is_probability(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        return value


class MemoryObject(BaseModel):
    object_id: str
    class_name: str
    state: MemoryState
    pose: Pose2D
    anchor_id: str
    anchor_type: AnchorType
    frame_id: str
    confidence: float
    detector_name: str
    verification_viewpoint: Pose2D | None = None


class ObjectRelation(BaseModel):
    source_object_id: str
    target_object_id: str
    relation_type: str


class TrialEvent(BaseModel):
    trial_id: str
    event_type: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class TrialMetrics(BaseModel):
    success: bool = False
    failure_reason: str | None = None
    final_state: str = "unknown"
    path_length_m: float = 0.0
    elapsed_time_s: float = 0.0
    num_nav_goals: int = 0
    num_nav_failures: int = 0
    num_replans: int = 0
    frontier_count_total: int = 0
    frontier_selected_count: int = 0
    time_to_first_observation_s: float | None = None
    time_to_verify_s: float | None = None
    observation_count: int = 0
    verification_attempt_count: int = 0
    failed_viewpoint_count: int = 0
    memory_reused: bool = False
    memory_query_count: int = 0
    memory_hit_count: int = 0
    memory_state_transition_count: int = 0
    stale_recheck_count: int = 0
    missing_detection_success: bool = False
    relocation_recorded: bool = False
    map_coverage_at_success: float = 0.0
    unknown_area_reduction: float = 0.0
    repeated_exploration_ratio: float = 0.0
    selected_candidate_types: list[str] = Field(default_factory=list)
    final_candidate_score: float | None = None


class TrialResult(BaseModel):
    trial_id: str
    metrics: TrialMetrics
    events: list[TrialEvent] = Field(default_factory=list)


def make_default_corridor_scene() -> SceneConfig:
    return SceneConfig(
        scene_id="straight_corridor_one_water_dispenser_unknown",
        anchor=AnchorConfig(
            anchor_id="indoor_map_corridor_a",
            anchor_type=AnchorType.INDOOR_MAP,
            frame_id="map",
        ),
        map=MapConfig(
            width_m=12.0,
            height_m=2.4,
            resolution_m=0.1,
            known_at_start=Bounds2D(x_min=0.0, x_max=3.2, y_min=0.0, y_max=2.4),
        ),
        objects=[
            ObjectConfig(
                object_id="water_dispenser_001",
                class_name="water_dispenser",
                pose_map=Pose2D(x=8.0, y=0.25, yaw=1.5708),
                preferred_standoff_m=1.2,
            )
        ],
        reveal_model=RevealModelConfig(
            max_range_m=2.5,
            horizontal_fov_deg=70.0,
            raycast_step_m=0.05,
        ),
        fake_detector=FakeDetectorConfig(
            min_range_m=0.2,
            max_range_m=3.0,
            horizontal_fov_deg=70.0,
            require_line_of_sight=True,
        ),
    )
