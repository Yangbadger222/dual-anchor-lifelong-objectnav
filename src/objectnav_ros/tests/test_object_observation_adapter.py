import json

import pytest
from std_msgs.msg import String

from objectnav_core.models import AnchorType
from objectnav_ros.adapters.object_observation_adapter import (
    ObservationAdapterError,
    StaleObservationError,
    object_observation_from_json_msg,
)


def test_json_string_object_observation_converts_to_core_model() -> None:
    message = String()
    message.data = json.dumps(
        {
            "object_id": "water_dispenser_001",
            "class_name": "water_dispenser",
            "confidence": 0.92,
            "pose": {"x": 8.0, "y": 0.25, "yaw": 1.57},
            "anchor_id": "indoor_map_corridor_a",
            "anchor_type": "indoor_map",
            "frame_id": "map",
            "detector_name": "projected_detector",
            "timestamp": 100.0,
        }
    )

    observation = object_observation_from_json_msg(message, now_s=101.0, max_age_s=5.0)

    assert observation.object_id == "water_dispenser_001"
    assert observation.class_name == "water_dispenser"
    assert observation.confidence == pytest.approx(0.92)
    assert observation.pose.x == pytest.approx(8.0)
    assert observation.anchor_type is AnchorType.INDOOR_MAP
    assert observation.frame_id == "map"
    assert observation.timestamp == pytest.approx(100.0)


def test_json_string_object_observation_rejects_stale_timestamps() -> None:
    message = String()
    message.data = json.dumps(
        {
            "object_id": "water_dispenser_001",
            "class_name": "water_dispenser",
            "confidence": 0.92,
            "pose": {"x": 8.0, "y": 0.25},
            "anchor_id": "indoor_map_corridor_a",
            "anchor_type": "indoor_map",
            "frame_id": "map",
            "detector_name": "projected_detector",
            "timestamp": 10.0,
        }
    )

    with pytest.raises(StaleObservationError):
        object_observation_from_json_msg(message, now_s=20.0, max_age_s=5.0)


def test_json_string_object_observation_rejects_invalid_payload() -> None:
    message = String()
    message.data = "[]"

    with pytest.raises(ObservationAdapterError, match="must be an object"):
        object_observation_from_json_msg(message)
