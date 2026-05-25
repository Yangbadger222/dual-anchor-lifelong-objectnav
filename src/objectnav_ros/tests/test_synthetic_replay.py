import json

from objectnav_core.mapping.fixtures import build_corridor_grid
from objectnav_core.mapping.frontiers import extract_frontier_clusters
from objectnav_core.mapping.grid import CellState
from objectnav_core.models import make_default_corridor_scene
from objectnav_ros.adapters.object_observation_adapter import object_observation_from_json_msg
from objectnav_ros.nodes.objectnav_node import select_replay_frontier_goal
from objectnav_ros.nodes.synthetic_replay_node import (
    make_synthetic_base_transform,
    make_synthetic_costmap_message,
    make_synthetic_observation_message,
    make_synthetic_replay_grid,
    make_visible_synthetic_observation_message,
    synthetic_robot_pose_for_step,
)


def test_synthetic_costmap_message_matches_phase1a_scene() -> None:
    scene = make_default_corridor_scene()

    message = make_synthetic_costmap_message(scene, frame_id="map")

    assert message.header.frame_id == "map"
    assert message.info.width == 120
    assert message.info.height == 24
    assert message.info.resolution == scene.map.resolution_m
    assert len(message.data) == message.info.width * message.info.height
    assert -1 in message.data
    assert 100 in message.data


def test_synthetic_replay_grid_progressively_reveals_corridor() -> None:
    scene = make_default_corridor_scene()

    step_0 = make_synthetic_replay_grid(scene, step_index=0)
    step_5 = make_synthetic_replay_grid(scene, step_index=5)

    assert (step_5.data == CellState.UNKNOWN).sum() < (step_0.data == CellState.UNKNOWN).sum()
    assert step_5.is_free_world(4.2, 1.2)


def test_synthetic_observation_message_uses_adapter_schema() -> None:
    scene = make_default_corridor_scene()

    message = make_synthetic_observation_message(scene, timestamp=123.0)
    payload = json.loads(message.data)
    observation = object_observation_from_json_msg(message, now_s=124.0, max_age_s=5.0)

    assert payload["detector_name"] == "synthetic_replay"
    assert observation.object_id == scene.objects[0].object_id
    assert observation.anchor_id == scene.anchor.anchor_id
    assert observation.timestamp == 123.0


def test_visible_synthetic_observation_waits_for_line_of_sight() -> None:
    scene = make_default_corridor_scene()
    early_pose = synthetic_robot_pose_for_step(0, scene)
    visible_pose = synthetic_robot_pose_for_step(10, scene)

    early_message = make_visible_synthetic_observation_message(
        scene,
        robot_pose=early_pose,
        grid=make_synthetic_replay_grid(scene, step_index=0),
        timestamp=10.0,
    )
    visible_message = make_visible_synthetic_observation_message(
        scene,
        robot_pose=visible_pose,
        grid=make_synthetic_replay_grid(scene, step_index=10),
        timestamp=11.0,
    )

    assert early_message is None
    assert visible_message is not None
    observation = object_observation_from_json_msg(visible_message, now_s=11.0, max_age_s=1.0)
    assert observation.object_id == scene.objects[0].object_id
    assert observation.detector_name == "synthetic_replay"


def test_synthetic_base_transform_uses_configured_frames() -> None:
    transform = make_synthetic_base_transform(frame_id="map", child_frame_id="base_link")

    assert transform.header.frame_id == "map"
    assert transform.child_frame_id == "base_link"
    assert transform.transform.translation.x == 1.0
    assert transform.transform.rotation.w == 1.0


def test_synthetic_base_transform_tracks_replay_pose() -> None:
    pose = synthetic_robot_pose_for_step(4)

    transform = make_synthetic_base_transform(robot_pose=pose)

    assert transform.transform.translation.x == pose.x
    assert transform.transform.translation.y == pose.y


def test_replay_frontier_goal_selects_known_side_viewpoint() -> None:
    scene = make_default_corridor_scene()
    grid = build_corridor_grid(scene)
    frontiers = extract_frontier_clusters(grid)

    goal = select_replay_frontier_goal(grid, frontiers)

    assert goal is not None
    assert grid.is_free_world(goal.x, goal.y)
    assert goal.x < frontiers[0].centroid.x
