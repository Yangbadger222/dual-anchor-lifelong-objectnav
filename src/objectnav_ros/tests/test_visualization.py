from visualization_msgs.msg import Marker

from objectnav_core.mapping.fixtures import build_corridor_grid
from objectnav_core.mapping.frontiers import extract_frontier_clusters
from objectnav_core.models import (
    AnchorType,
    ObjectObservation,
    Pose2D,
    make_default_corridor_scene,
)
from objectnav_ros.adapters.visualization import (
    frontier_marker_array,
    memory_marker_array,
    replay_debug_marker_array,
    selected_goal_marker,
)


def test_frontier_marker_array_uses_map_frame_and_frontier_cells() -> None:
    scene = make_default_corridor_scene()
    grid = build_corridor_grid(scene)
    frontiers = extract_frontier_clusters(grid)

    markers = frontier_marker_array(frontiers, grid, frame_id="map")

    assert len(markers.markers) == len(frontiers)
    assert markers.markers[0].header.frame_id == "map"
    assert markers.markers[0].ns == "objectnav_frontiers"
    assert markers.markers[0].type == Marker.CUBE_LIST
    assert len(markers.markers[0].points) == len(frontiers[0].cells)


def test_selected_goal_marker_is_arrow_in_map_frame() -> None:
    marker = selected_goal_marker(Pose2D(x=2.0, y=3.0, yaw=1.0), frame_id="map")

    assert marker.header.frame_id == "map"
    assert marker.ns == "objectnav_selected_goal"
    assert marker.type == Marker.ARROW
    assert marker.pose.position.x == 2.0
    assert marker.pose.orientation.w != 0.0


def test_memory_marker_array_adds_sphere_and_label() -> None:
    observation = ObjectObservation(
        object_id="water_dispenser_001",
        class_name="water_dispenser",
        confidence=1.0,
        pose=Pose2D(x=8.0, y=0.25, yaw=1.57),
        anchor_id="indoor_map_corridor_a",
        anchor_type=AnchorType.INDOOR_MAP,
        frame_id="map",
        detector_name="test",
        timestamp=123.0,
    )

    markers = memory_marker_array([observation], frame_id="map")

    assert len(markers.markers) == 2
    assert markers.markers[0].type == Marker.SPHERE
    assert markers.markers[1].type == Marker.TEXT_VIEW_FACING
    assert markers.markers[1].text == "water_dispenser:water_dispenser_001"


def test_replay_debug_marker_array_describes_current_step() -> None:
    markers = replay_debug_marker_array(
        frame_id="map",
        step_index=7,
        robot_pose=Pose2D(x=4.15, y=1.2, yaw=0.0),
    )

    assert len(markers.markers) == 1
    assert markers.markers[0].header.frame_id == "map"
    assert markers.markers[0].ns == "objectnav_replay_legend"
    assert markers.markers[0].type == Marker.TEXT_VIEW_FACING
    assert "step: 7" in markers.markers[0].text
    assert "base_link: (4.15, 1.20)" in markers.markers[0].text
