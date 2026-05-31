from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from objectnav_core.models import NavigationStatus, Pose2D


class NavigationGoal(BaseModel):
    goal_id: str
    pose: Pose2D
    frame_id: str = "map"
    tolerance_m: float = 0.35
    source: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("goal_id", "frame_id")
    @classmethod
    def _non_empty_text(cls, value: str, info: Any) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError(f"{info.field_name} must be non-empty")
        return normalized

    @field_validator("tolerance_m")
    @classmethod
    def _positive_tolerance(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError("tolerance_m must be positive")
        return value


class ExplorationRequest(BaseModel):
    request_id: str
    frame_id: str = "map"
    region_id: str | None = None
    center: Pose2D | None = None
    radius_m: float | None = None
    strategy: str = "frontier"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("request_id", "frame_id", "strategy")
    @classmethod
    def _non_empty_text(cls, value: str, info: Any) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError(f"{info.field_name} must be non-empty")
        return normalized

    @field_validator("radius_m")
    @classmethod
    def _positive_radius(cls, value: float | None) -> float | None:
        if value is not None and value <= 0.0:
            raise ValueError("radius_m must be positive when provided")
        return value


class NavigationBackendStatus(BaseModel):
    backend_id: str
    status: NavigationStatus
    pose: Pose2D | None = None
    active_goal_id: str | None = None
    reason: str | None = None
    path_length_m: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("backend_id")
    @classmethod
    def _backend_id_non_empty(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("backend_id must be non-empty")
        return normalized

    @field_validator("path_length_m")
    @classmethod
    def _non_negative_path_length(cls, value: float | None) -> float | None:
        if value is not None and value < 0.0:
            raise ValueError("path_length_m must be non-negative")
        return value


@runtime_checkable
class NavigationBackend(Protocol):
    backend_id: str

    def get_pose(self) -> Pose2D | None:
        ...

    def go_to(self, goal: NavigationGoal) -> NavigationBackendStatus:
        ...

    def explore(self, request: ExplorationRequest) -> NavigationBackendStatus:
        ...

    def status(self) -> NavigationBackendStatus:
        ...

    def cancel(self) -> NavigationBackendStatus:
        ...


class LegacyNavigationClientBackend:
    """Adapter for existing clients with send_goal/cancel_goal/status fields."""

    def __init__(
        self,
        client: Any,
        *,
        backend_id: str = "legacy_navigation_client",
    ) -> None:
        if not str(backend_id).strip():
            raise ValueError("backend_id must be non-empty")
        self.client = client
        self.backend_id = str(backend_id).strip()
        self._active_goal_id: str | None = None

    def get_pose(self) -> Pose2D | None:
        pose = getattr(self.client, "current_pose", None)
        return pose if isinstance(pose, Pose2D) else None

    def go_to(self, goal: NavigationGoal) -> NavigationBackendStatus:
        self._active_goal_id = goal.goal_id
        result = self.client.send_goal(goal.pose)
        if isinstance(result, NavigationStatus):
            setattr(self.client, "status", result)
        return self.status()

    def explore(self, request: ExplorationRequest) -> NavigationBackendStatus:
        if request.center is None:
            return NavigationBackendStatus(
                backend_id=self.backend_id,
                status=NavigationStatus.FAILED,
                pose=self.get_pose(),
                active_goal_id=request.request_id,
                reason="explore_requires_center",
            )
        metadata = dict(request.metadata)
        if request.region_id is not None:
            metadata["region_id"] = request.region_id
        if request.radius_m is not None:
            metadata["radius_m"] = request.radius_m
        return self.go_to(
            NavigationGoal(
                goal_id=request.request_id,
                pose=request.center,
                frame_id=request.frame_id,
                source=f"explore:{request.strategy}",
                metadata=metadata,
            )
        )

    def status(self) -> NavigationBackendStatus:
        return NavigationBackendStatus(
            backend_id=self.backend_id,
            status=_coerce_navigation_status(
                getattr(self.client, "status", NavigationStatus.IDLE)
            ),
            pose=self.get_pose(),
            active_goal_id=self._active_goal_id,
            reason=_optional_str(getattr(self.client, "result_reason", None)),
            path_length_m=_optional_float(getattr(self.client, "path_length_m", None)),
        )

    def cancel(self) -> NavigationBackendStatus:
        cancel = getattr(self.client, "cancel_goal", None)
        if callable(cancel):
            result = cancel()
            if isinstance(result, NavigationStatus):
                setattr(self.client, "status", result)
        return self.status()


def _coerce_navigation_status(value: Any) -> NavigationStatus:
    if isinstance(value, NavigationStatus):
        return value
    try:
        return NavigationStatus(str(value))
    except ValueError:
        return NavigationStatus.FAILED


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
