from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    OfficialMemoryAnchor,
    _depth_frame_2d,
    _depth_value_to_meters,
    _observation_heading,
    _observation_xz,
)


def estimate_episode_robot_viewpoint_anchor(
    observation: Mapping[str, Any],
    *,
    object_category: str,
    confidence: float = 1.0,
    source: str = "detector_viewpoint",
    scene_id: str | None = None,
    episode_id: str | None = None,
) -> OfficialMemoryAnchor:
    """Store the robot viewpoint that produced detector evidence."""

    if not object_category:
        raise ValueError("object_category must be non-empty")
    if not np.isfinite(confidence):
        raise ValueError("confidence must be finite")
    current_x, current_z = _observation_xz(observation)
    return OfficialMemoryAnchor(
        object_category=object_category,
        x_m=round(float(current_x), 6),
        z_m=round(float(current_z), 6),
        scene_id=scene_id,
        episode_id=episode_id,
        confidence=float(confidence),
        source=str(source),
        coordinate_frame="episode_start_relative",
    )


def estimate_episode_detection_anchor(
    observation: Mapping[str, Any],
    *,
    bbox_xyxy: Sequence[float],
    object_category: str,
    confidence: float = 1.0,
    source: str = "detector",
    scene_id: str | None = None,
    episode_id: str | None = None,
    hfov_deg: float = 79.0,
    min_depth_m: float = 0.5,
    max_depth_m: float = 5.0,
) -> OfficialMemoryAnchor | None:
    """Project a detector bbox into the official episode-relative memory frame."""

    if not object_category:
        raise ValueError("object_category must be non-empty")
    if not np.isfinite(confidence):
        raise ValueError("confidence must be finite")
    if hfov_deg <= 0.0:
        raise ValueError("hfov_deg must be positive")
    if min_depth_m <= 0.0 or max_depth_m <= min_depth_m:
        raise ValueError("depth range must satisfy 0 < min_depth_m < max_depth_m")

    depth = _depth_frame_2d(observation.get("depth"))
    if depth is None:
        return None
    bbox = _clip_bbox_xyxy(bbox_xyxy, width=depth.shape[1], height=depth.shape[0])
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    patch = depth[y1:y2, x1:x2]
    finite = patch[np.isfinite(patch) & (patch > 0.0)]
    if finite.size == 0:
        return None

    finite_depth = depth[np.isfinite(depth)]
    normalized = bool(finite_depth.size and float(np.nanmax(finite_depth)) <= 1.0)
    depth_m = _depth_value_to_meters(
        float(np.median(finite)),
        normalized=normalized,
        min_depth_m=min_depth_m,
        max_depth_m=max_depth_m,
    )
    center_x = (x1 + x2 - 1) / 2.0
    horizontal_offset = (
        (center_x - (depth.shape[1] - 1) / 2.0)
        / max(1.0, (depth.shape[1] - 1) / 2.0)
    )
    bearing = horizontal_offset * np.deg2rad(hfov_deg) / 2.0
    current_x, current_z = _observation_xz(observation)
    heading = _observation_heading(observation)
    episode_angle = heading + bearing
    return OfficialMemoryAnchor(
        object_category=object_category,
        x_m=round(float(current_x + depth_m * np.sin(episode_angle)), 6),
        z_m=round(float(current_z + depth_m * np.cos(episode_angle)), 6),
        scene_id=scene_id,
        episode_id=episode_id,
        confidence=float(confidence),
        source=str(source),
        coordinate_frame="episode_start_relative",
    )


def make_official_memory_prior_payload(
    anchors: Sequence[OfficialMemoryAnchor],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "anchors": [_anchor_to_payload(anchor) for anchor in anchors],
        "metadata": {
            "source": "official_episode_detection_memory",
            "coordinate_frame": "episode_start_relative",
            "anchor_count": len(anchors),
        },
    }
    if metadata:
        payload["metadata"].update(dict(metadata))
    return payload


def _clip_bbox_xyxy(
    bbox_xyxy: Sequence[float],
    *,
    width: int,
    height: int,
) -> tuple[int, int, int, int] | None:
    if len(bbox_xyxy) != 4:
        raise ValueError("bbox_xyxy must contain four values")
    try:
        x1_raw, y1_raw, x2_raw, y2_raw = (float(value) for value in bbox_xyxy)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox_xyxy must contain numeric values") from exc
    if not all(np.isfinite(value) for value in (x1_raw, y1_raw, x2_raw, y2_raw)):
        raise ValueError("bbox_xyxy values must be finite")
    x1 = max(0, min(width, int(np.floor(x1_raw))))
    y1 = max(0, min(height, int(np.floor(y1_raw))))
    x2 = max(0, min(width, int(np.ceil(x2_raw))))
    y2 = max(0, min(height, int(np.ceil(y2_raw))))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _anchor_to_payload(anchor: OfficialMemoryAnchor) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "object_category": anchor.object_category,
        "x_m": anchor.x_m,
        "z_m": anchor.z_m,
        "confidence": anchor.confidence,
        "source": anchor.source,
        "coordinate_frame": anchor.coordinate_frame,
    }
    if anchor.scene_id is not None:
        payload["scene_id"] = anchor.scene_id
    if anchor.episode_id is not None:
        payload["episode_id"] = anchor.episode_id
    if anchor.y_m is not None:
        payload["y_m"] = anchor.y_m
    return payload
