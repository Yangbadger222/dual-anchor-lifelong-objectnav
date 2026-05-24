import math

import pytest

from objectnav_core.mapping.fixtures import build_corridor_grid
from objectnav_core.models import NavigationStatus, Pose2D, make_default_corridor_scene
from objectnav_core.planning.scoring import score_frontier_candidate
from objectnav_core.simulation.navigation import DiscreteStepNavigationClient
from objectnav_core.simulation.observations import ConfigTruthObjectSource


def test_fake_detector_emits_only_inside_camera_sector_and_los() -> None:
    scene = make_default_corridor_scene()
    grid = build_corridor_grid(scene, reveal_all=True)
    source = ConfigTruthObjectSource(scene)

    visible_pose = Pose2D(x=8.0, y=1.45, yaw=-math.pi / 2)
    wrong_yaw_pose = Pose2D(x=8.0, y=1.45, yaw=0.0)
    far_pose = Pose2D(x=1.0, y=1.2, yaw=0.0)

    observations = source.observations_at(visible_pose, grid)

    assert len(observations) == 1
    assert observations[0].class_name == "water_dispenser"
    assert observations[0].anchor_id == scene.anchor.anchor_id
    assert source.observations_at(wrong_yaw_pose, grid) == []
    assert source.observations_at(far_pose, grid) == []


def test_discrete_navigation_reaches_goal_and_accumulates_path_length() -> None:
    navigator = DiscreteStepNavigationClient(
        start_pose=Pose2D(x=1.0, y=1.2, yaw=0.0),
        step_size_m=0.25,
        success_radius_m=0.05,
    )

    navigator.send_goal(Pose2D(x=2.0, y=1.2, yaw=0.0))
    for _ in range(10):
        if navigator.status is NavigationStatus.SUCCEEDED:
            break
        navigator.tick(1.0)

    assert navigator.status is NavigationStatus.SUCCEEDED
    assert navigator.current_pose.x == pytest.approx(2.0)
    assert navigator.current_pose.y == pytest.approx(1.2)
    assert navigator.path_length_m == pytest.approx(1.0)


def test_frontier_score_prefers_information_gain_and_penalizes_revisits() -> None:
    high_info = score_frontier_candidate(
        information_gain=10.0,
        path_cost=2.0,
        revisit_penalty=0.0,
    )
    revisited = score_frontier_candidate(
        information_gain=10.0,
        path_cost=2.0,
        revisit_penalty=5.0,
    )

    assert high_info == pytest.approx(8.0)
    assert revisited == pytest.approx(3.0)
    assert high_info > revisited
