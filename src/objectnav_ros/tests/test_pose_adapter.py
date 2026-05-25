import math

import pytest
from geometry_msgs.msg import TransformStamped

from objectnav_core.models import Pose2D
from objectnav_ros.adapters.pose_adapter import (
    pose2d_from_pose_stamped,
    pose2d_from_transform_stamped,
    pose_stamped_from_pose2d,
    quaternion_z_w_from_yaw,
)


def test_pose_stamped_round_trip_preserves_xy_yaw_and_frame() -> None:
    pose = Pose2D(x=1.5, y=2.5, yaw=math.pi / 2)

    message = pose_stamped_from_pose2d(pose, frame_id="map")
    restored = pose2d_from_pose_stamped(message)

    assert message.header.frame_id == "map"
    assert restored.x == pytest.approx(1.5)
    assert restored.y == pytest.approx(2.5)
    assert restored.yaw == pytest.approx(math.pi / 2)


def test_transform_stamped_converts_to_pose2d() -> None:
    message = TransformStamped()
    message.header.frame_id = "map"
    message.child_frame_id = "base_link"
    message.transform.translation.x = 3.0
    message.transform.translation.y = 4.0
    z, w = quaternion_z_w_from_yaw(-math.pi / 2)
    message.transform.rotation.z = z
    message.transform.rotation.w = w

    pose = pose2d_from_transform_stamped(message)

    assert pose.x == pytest.approx(3.0)
    assert pose.y == pytest.approx(4.0)
    assert pose.yaw == pytest.approx(-math.pi / 2)
