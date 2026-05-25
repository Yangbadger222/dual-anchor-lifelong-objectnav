from __future__ import annotations

import math

from geometry_msgs.msg import PoseStamped, TransformStamped

from objectnav_core.models import Pose2D


def pose2d_from_pose_stamped(message: PoseStamped) -> Pose2D:
    orientation = message.pose.orientation
    yaw = yaw_from_quaternion(
        x=orientation.x,
        y=orientation.y,
        z=orientation.z,
        w=orientation.w,
    )
    return Pose2D(
        x=float(message.pose.position.x),
        y=float(message.pose.position.y),
        yaw=yaw,
    )


def pose2d_from_transform_stamped(message: TransformStamped) -> Pose2D:
    rotation = message.transform.rotation
    yaw = yaw_from_quaternion(
        x=rotation.x,
        y=rotation.y,
        z=rotation.z,
        w=rotation.w,
    )
    return Pose2D(
        x=float(message.transform.translation.x),
        y=float(message.transform.translation.y),
        yaw=yaw,
    )


def pose_stamped_from_pose2d(
    pose: Pose2D,
    frame_id: str,
    stamp: object | None = None,
) -> PoseStamped:
    message = PoseStamped()
    message.header.frame_id = frame_id
    if stamp is not None:
        message.header.stamp = stamp
    message.pose.position.x = float(pose.x)
    message.pose.position.y = float(pose.y)
    message.pose.position.z = 0.0
    z, w = quaternion_z_w_from_yaw(pose.yaw)
    message.pose.orientation.x = 0.0
    message.pose.orientation.y = 0.0
    message.pose.orientation.z = z
    message.pose.orientation.w = w
    return message


def quaternion_z_w_from_yaw(yaw: float) -> tuple[float, float]:
    half_yaw = yaw / 2.0
    return math.sin(half_yaw), math.cos(half_yaw)


def yaw_from_quaternion(x: float, y: float, z: float, w: float) -> float:
    sin_yaw = 2.0 * (w * z + x * y)
    cos_yaw = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(sin_yaw, cos_yaw)
