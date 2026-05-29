from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping


Covariance2D = tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True)
class PoseEstimate2D:
    x: float
    y: float
    yaw: float = 0.0
    covariance: Covariance2D = ((0.0, 0.0), (0.0, 0.0))


@dataclass(frozen=True)
class FrameTransform2D:
    dx: float
    dy: float
    dyaw: float = 0.0
    covariance: Covariance2D = ((0.0, 0.0), (0.0, 0.0))


@dataclass(frozen=True)
class InstanceMatch:
    object_id: str | None
    accepted: bool
    reason: str
    best_distance: float | None
    second_best_distance: float | None
    distances: dict[str, float]


def transform_pose_estimate(
    pose: PoseEstimate2D,
    transform: FrameTransform2D,
) -> PoseEstimate2D:
    cos_yaw = math.cos(transform.dyaw)
    sin_yaw = math.sin(transform.dyaw)
    x = transform.dx + cos_yaw * pose.x - sin_yaw * pose.y
    y = transform.dy + sin_yaw * pose.x + cos_yaw * pose.y
    rotated_covariance = _rotate_covariance(pose.covariance, transform.dyaw)
    covariance = _add_covariance(rotated_covariance, transform.covariance)
    return PoseEstimate2D(
        x=round(x, 12),
        y=round(y, 12),
        yaw=_wrap_angle(pose.yaw + transform.dyaw),
        covariance=_round_covariance(covariance),
    )


def mahalanobis_squared(
    predicted: PoseEstimate2D,
    observed: PoseEstimate2D,
) -> float:
    covariance = _add_covariance(predicted.covariance, observed.covariance)
    inverse = _inverse_2x2(covariance)
    dx = observed.x - predicted.x
    dy = observed.y - predicted.y
    value = (
        dx * (inverse[0][0] * dx + inverse[0][1] * dy)
        + dy * (inverse[1][0] * dx + inverse[1][1] * dy)
    )
    return round(float(value), 12)


def match_instance_by_mahalanobis(
    *,
    observed: PoseEstimate2D,
    candidates: Mapping[str, PoseEstimate2D],
    gate_threshold: float,
    ambiguity_margin: float,
) -> InstanceMatch:
    if gate_threshold <= 0.0:
        raise ValueError("gate_threshold must be positive")
    if ambiguity_margin < 0.0:
        raise ValueError("ambiguity_margin must be non-negative")
    distances = {
        object_id: mahalanobis_squared(candidate, observed)
        for object_id, candidate in candidates.items()
    }
    if not distances:
        return InstanceMatch(
            object_id=None,
            accepted=False,
            reason="no_candidates",
            best_distance=None,
            second_best_distance=None,
            distances={},
        )
    ranked = sorted(distances.items(), key=lambda item: item[1])
    best_id, best_distance = ranked[0]
    second_best_distance = ranked[1][1] if len(ranked) > 1 else None
    if best_distance > gate_threshold:
        return InstanceMatch(
            object_id=None,
            accepted=False,
            reason="outside_gate",
            best_distance=best_distance,
            second_best_distance=second_best_distance,
            distances=distances,
        )
    if (
        second_best_distance is not None
        and second_best_distance - best_distance < ambiguity_margin
    ):
        return InstanceMatch(
            object_id=None,
            accepted=False,
            reason="ambiguous",
            best_distance=best_distance,
            second_best_distance=second_best_distance,
            distances=distances,
        )
    return InstanceMatch(
        object_id=best_id,
        accepted=True,
        reason="accepted",
        best_distance=best_distance,
        second_best_distance=second_best_distance,
        distances=distances,
    )


def _rotate_covariance(covariance: Covariance2D, yaw: float) -> Covariance2D:
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    r00 = cos_yaw
    r01 = -sin_yaw
    r10 = sin_yaw
    r11 = cos_yaw
    c00, c01 = covariance[0]
    c10, c11 = covariance[1]
    rc00 = r00 * c00 + r01 * c10
    rc01 = r00 * c01 + r01 * c11
    rc10 = r10 * c00 + r11 * c10
    rc11 = r10 * c01 + r11 * c11
    return (
        (rc00 * r00 + rc01 * r01, rc00 * r10 + rc01 * r11),
        (rc10 * r00 + rc11 * r01, rc10 * r10 + rc11 * r11),
    )


def _add_covariance(first: Covariance2D, second: Covariance2D) -> Covariance2D:
    return (
        (first[0][0] + second[0][0], first[0][1] + second[0][1]),
        (first[1][0] + second[1][0], first[1][1] + second[1][1]),
    )


def _inverse_2x2(matrix: Covariance2D) -> Covariance2D:
    a, b = matrix[0]
    c, d = matrix[1]
    determinant = a * d - b * c
    if abs(determinant) < 1e-12:
        raise ValueError("covariance matrix must be invertible")
    scale = 1.0 / determinant
    return ((d * scale, -b * scale), (-c * scale, a * scale))


def _round_covariance(covariance: Covariance2D) -> Covariance2D:
    return (
        (round(float(covariance[0][0]), 12), round(float(covariance[0][1]), 12)),
        (round(float(covariance[1][0]), 12), round(float(covariance[1][1]), 12)),
    )


def _wrap_angle(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))
