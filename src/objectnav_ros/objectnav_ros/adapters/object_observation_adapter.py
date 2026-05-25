from __future__ import annotations

import json
import time
from typing import Any

from std_msgs.msg import String

from objectnav_core.models import AnchorType, ObjectObservation, Pose2D


class ObservationAdapterError(ValueError):
    pass


class StaleObservationError(ObservationAdapterError):
    pass


def object_observation_from_json_msg(
    message: String,
    *,
    now_s: float | None = None,
    max_age_s: float | None = None,
) -> ObjectObservation:
    try:
        payload = json.loads(message.data)
    except json.JSONDecodeError as exc:
        raise ObservationAdapterError(f"invalid object observation JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ObservationAdapterError("object observation JSON must be an object")
    return object_observation_from_payload(payload, now_s=now_s, max_age_s=max_age_s)


def object_observation_from_payload(
    payload: dict[str, Any],
    *,
    now_s: float | None = None,
    max_age_s: float | None = None,
) -> ObjectObservation:
    timestamp = payload.get("timestamp")
    if timestamp is not None and max_age_s is not None and max_age_s > 0:
        reference_time = time.time() if now_s is None else now_s
        age_s = reference_time - float(timestamp)
        if age_s > max_age_s:
            raise StaleObservationError(
                f"object observation is stale by {age_s:.3f}s with max_age_s={max_age_s}"
            )

    pose_payload = payload.get("pose")
    if not isinstance(pose_payload, dict):
        raise ObservationAdapterError("object observation payload requires a pose object")

    try:
        return ObjectObservation(
            object_id=str(payload["object_id"]),
            class_name=str(payload["class_name"]),
            confidence=float(payload["confidence"]),
            pose=Pose2D(
                x=float(pose_payload["x"]),
                y=float(pose_payload["y"]),
                yaw=float(pose_payload.get("yaw", 0.0)),
            ),
            anchor_id=str(payload["anchor_id"]),
            anchor_type=AnchorType(str(payload["anchor_type"])),
            frame_id=str(payload["frame_id"]),
            detector_name=str(payload["detector_name"]),
            timestamp=float(timestamp) if timestamp is not None else time.time(),
        )
    except KeyError as exc:
        raise ObservationAdapterError(f"missing object observation field: {exc}") from exc
    except ValueError as exc:
        raise ObservationAdapterError(f"invalid object observation field: {exc}") from exc
