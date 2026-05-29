from __future__ import annotations

import math

from objectnav_core.geometry.dual_anchor import (
    FrameTransform2D,
    PoseEstimate2D,
    match_instance_by_mahalanobis,
    mahalanobis_squared,
    transform_pose_estimate,
)


def test_frame_transform_maps_session_one_memory_into_session_two_frame() -> None:
    memory = PoseEstimate2D(
        x=2.0,
        y=1.0,
        yaw=0.0,
        covariance=((0.04, 0.0), (0.0, 0.04)),
    )
    transform = FrameTransform2D(
        dx=10.0,
        dy=-2.0,
        dyaw=math.pi / 2.0,
        covariance=((0.01, 0.0), (0.0, 0.09)),
    )

    transformed = transform_pose_estimate(memory, transform)

    assert transformed.x == 9.0
    assert transformed.y == 0.0
    assert transformed.yaw == math.pi / 2.0
    assert transformed.covariance == ((0.05, 0.0), (0.0, 0.13))


def test_mahalanobis_distance_uses_combined_uncertainty() -> None:
    predicted = PoseEstimate2D(
        x=0.0,
        y=0.0,
        covariance=((0.25, 0.0), (0.0, 0.25)),
    )
    observed = PoseEstimate2D(
        x=1.0,
        y=0.0,
        covariance=((0.25, 0.0), (0.0, 0.25)),
    )

    assert mahalanobis_squared(predicted, observed) == 2.0


def test_match_instance_accepts_best_candidate_inside_gate() -> None:
    observed = PoseEstimate2D(x=1.0, y=0.0, covariance=((0.2, 0.0), (0.0, 0.2)))
    candidates = {
        "near": PoseEstimate2D(x=1.2, y=0.0, covariance=((0.2, 0.0), (0.0, 0.2))),
        "far": PoseEstimate2D(x=4.0, y=0.0, covariance=((0.2, 0.0), (0.0, 0.2))),
    }

    match = match_instance_by_mahalanobis(
        observed=observed,
        candidates=candidates,
        gate_threshold=5.991,
        ambiguity_margin=1.0,
    )

    assert match.accepted is True
    assert match.object_id == "near"
    assert match.reason == "accepted"
    assert match.distances["near"] < match.distances["far"]


def test_match_instance_rejects_ambiguous_same_class_candidates() -> None:
    observed = PoseEstimate2D(x=1.0, y=0.0, covariance=((0.2, 0.0), (0.0, 0.2)))
    candidates = {
        "left": PoseEstimate2D(x=0.9, y=0.0, covariance=((0.2, 0.0), (0.0, 0.2))),
        "right": PoseEstimate2D(x=1.1, y=0.0, covariance=((0.2, 0.0), (0.0, 0.2))),
    }

    match = match_instance_by_mahalanobis(
        observed=observed,
        candidates=candidates,
        gate_threshold=5.991,
        ambiguity_margin=0.5,
    )

    assert match.accepted is False
    assert match.object_id is None
    assert match.reason == "ambiguous"
