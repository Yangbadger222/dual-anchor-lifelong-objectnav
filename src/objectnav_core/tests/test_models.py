import pytest
from pydantic import ValidationError

from objectnav_core.models import (
    AnchorType,
    MemoryState,
    Pose2D,
    SceneConfig,
    make_default_corridor_scene,
)


def test_default_corridor_scene_carries_dual_anchor_ready_metadata() -> None:
    scene = make_default_corridor_scene()

    assert scene.scene_id == "straight_corridor_one_water_dispenser_unknown"
    assert scene.anchor.anchor_id == "indoor_map_corridor_a"
    assert scene.anchor.anchor_type is AnchorType.INDOOR_MAP
    assert scene.anchor.frame_id == "map"
    assert scene.map.resolution_m == pytest.approx(0.1)
    assert scene.map.width_m == pytest.approx(12.0)
    assert scene.map.height_m == pytest.approx(2.4)
    assert scene.objects[0].class_name == "water_dispenser"
    assert scene.objects[0].pose_map.x == pytest.approx(8.0)
    assert scene.fake_detector.horizontal_fov_deg == pytest.approx(70.0)


def test_scene_rejects_non_positive_detector_range() -> None:
    payload = make_default_corridor_scene().model_dump()
    payload["fake_detector"]["max_range_m"] = 0.0

    with pytest.raises(ValidationError):
        SceneConfig.model_validate(payload)


def test_pose_distance_and_memory_states_are_explicit() -> None:
    start = Pose2D(x=1.0, y=1.2, yaw=0.0)
    goal = Pose2D(x=4.0, y=1.2, yaw=0.0)

    assert start.distance_to(goal) == pytest.approx(3.0)
    assert {state.value for state in MemoryState} >= {
        "observed",
        "verified",
        "reusable",
        "stale",
        "suspect_missing",
        "missing",
    }
