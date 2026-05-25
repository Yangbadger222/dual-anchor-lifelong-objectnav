from __future__ import annotations

from builtin_interfaces.msg import Duration
from geometry_msgs.msg import Point
from std_msgs.msg import ColorRGBA
from visualization_msgs.msg import Marker, MarkerArray

from objectnav_core.mapping.frontiers import FrontierCluster
from objectnav_core.mapping.grid import OccupancyGrid
from objectnav_core.models import ObjectObservation, Pose2D
from objectnav_ros.adapters.pose_adapter import quaternion_z_w_from_yaw


def frontier_marker_array(
    frontiers: list[FrontierCluster],
    grid: OccupancyGrid,
    *,
    frame_id: str,
    stamp: object | None = None,
) -> MarkerArray:
    markers = MarkerArray()
    for marker_id, frontier in enumerate(frontiers):
        marker = Marker()
        marker.header.frame_id = frame_id
        if stamp is not None:
            marker.header.stamp = stamp
        marker.ns = "objectnav_frontiers"
        marker.id = marker_id
        marker.type = Marker.CUBE_LIST
        marker.action = Marker.ADD
        marker.scale.x = grid.resolution_m
        marker.scale.y = grid.resolution_m
        marker.scale.z = 0.05
        marker.color = ColorRGBA(r=0.1, g=0.55, b=1.0, a=0.75)
        marker.lifetime = Duration(sec=2)
        marker.points = [
            _point(x, y, 0.03)
            for col, row in frontier.cells
            for x, y in (grid.cell_center(col, row),)
        ]
        markers.markers.append(marker)
    return markers


def selected_goal_marker(
    pose: Pose2D,
    *,
    frame_id: str,
    stamp: object | None = None,
) -> Marker:
    marker = Marker()
    marker.header.frame_id = frame_id
    if stamp is not None:
        marker.header.stamp = stamp
    marker.ns = "objectnav_selected_goal"
    marker.id = 0
    marker.type = Marker.ARROW
    marker.action = Marker.ADD
    marker.pose.position.x = pose.x
    marker.pose.position.y = pose.y
    marker.pose.position.z = 0.1
    z, w = quaternion_z_w_from_yaw(pose.yaw)
    marker.pose.orientation.z = z
    marker.pose.orientation.w = w
    marker.scale.x = 0.45
    marker.scale.y = 0.08
    marker.scale.z = 0.08
    marker.color = ColorRGBA(r=0.1, g=0.9, b=0.35, a=0.95)
    marker.lifetime = Duration(sec=2)
    return marker


def memory_marker_array(
    observations: list[ObjectObservation],
    *,
    frame_id: str,
    stamp: object | None = None,
) -> MarkerArray:
    markers = MarkerArray()
    for index, observation in enumerate(observations):
        sphere = Marker()
        sphere.header.frame_id = frame_id
        if stamp is not None:
            sphere.header.stamp = stamp
        sphere.ns = "objectnav_memory"
        sphere.id = index * 2
        sphere.type = Marker.SPHERE
        sphere.action = Marker.ADD
        sphere.pose.position.x = observation.pose.x
        sphere.pose.position.y = observation.pose.y
        sphere.pose.position.z = 0.35
        sphere.pose.orientation.w = 1.0
        sphere.scale.x = 0.25
        sphere.scale.y = 0.25
        sphere.scale.z = 0.25
        sphere.color = ColorRGBA(r=1.0, g=0.65, b=0.1, a=0.9)
        sphere.lifetime = Duration(sec=2)
        markers.markers.append(sphere)

        label = Marker()
        label.header.frame_id = frame_id
        if stamp is not None:
            label.header.stamp = stamp
        label.ns = "objectnav_memory_labels"
        label.id = index * 2 + 1
        label.type = Marker.TEXT_VIEW_FACING
        label.action = Marker.ADD
        label.pose.position.x = observation.pose.x
        label.pose.position.y = observation.pose.y
        label.pose.position.z = 0.75
        label.pose.orientation.w = 1.0
        label.scale.z = 0.25
        label.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=0.95)
        label.text = f"{observation.class_name}:{observation.object_id}"
        label.lifetime = Duration(sec=2)
        markers.markers.append(label)
    return markers


def delete_all_markers(*, frame_id: str, stamp: object | None = None) -> MarkerArray:
    marker = Marker()
    marker.header.frame_id = frame_id
    if stamp is not None:
        marker.header.stamp = stamp
    marker.action = Marker.DELETEALL
    return MarkerArray(markers=[marker])


def replay_debug_marker_array(
    *,
    frame_id: str,
    step_index: int,
    robot_pose: Pose2D,
    stamp: object | None = None,
) -> MarkerArray:
    label = Marker()
    label.header.frame_id = frame_id
    if stamp is not None:
        label.header.stamp = stamp
    label.ns = "objectnav_replay_legend"
    label.id = 0
    label.type = Marker.TEXT_VIEW_FACING
    label.action = Marker.ADD
    label.pose.position.x = 1.2
    label.pose.position.y = 3.0
    label.pose.position.z = 0.8
    label.pose.orientation.w = 1.0
    label.scale.z = 0.28
    label.color = ColorRGBA(r=0.95, g=0.95, b=0.95, a=0.95)
    label.text = (
        "Synthetic ObjectNav replay\n"
        f"step: {step_index}  base_link: ({robot_pose.x:.2f}, {robot_pose.y:.2f})\n"
        "green arrow: selected frontier goal\n"
        "blue blocks: known/unknown frontier\n"
        "orange sphere: synthetic object observation"
    )
    label.lifetime = Duration(sec=2)
    return MarkerArray(markers=[label])


def _point(x: float, y: float, z: float) -> Point:
    point = Point()
    point.x = float(x)
    point.y = float(y)
    point.z = float(z)
    return point
