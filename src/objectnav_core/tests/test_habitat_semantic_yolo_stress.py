import sys

import numpy as np

from objectnav_core.evaluation import habitat_semantic_yolo_stress as stress
from objectnav_core.memory.usability import EvidenceType


def test_importing_semantic_stress_module_does_not_import_habitat() -> None:
    assert "habitat" not in sys.modules
    assert "habitat_sim" not in sys.modules


def test_yolo_breaker_miss_can_remove_target_mask() -> None:
    mask = np.zeros((12, 12), dtype=bool)
    mask[3:8, 3:8] = True

    result = stress._apply_yolo_breaker(
        mask,
        rng=np.random.default_rng(8),
        mode="miss",
    )

    assert result.miss_applied is True
    assert result.detector_mask.sum() < mask.sum()


def test_yolo_breaker_fly_points_create_fragmented_false_positives() -> None:
    mask = np.zeros((32, 32), dtype=bool)

    result = stress._apply_yolo_breaker(
        mask,
        rng=np.random.default_rng(4),
        mode="fly_point",
    )
    metrics = stress._mask_metrics(
        oracle_mask=mask,
        detector_mask=result.detector_mask,
    )

    assert result.fly_point_pixels > 0
    assert metrics["false_positive_ratio"] == 1.0
    assert metrics["component_count"] >= 2


def test_semantic_evidence_rejects_fragmented_detector_mask() -> None:
    metrics = {
        "detector_pixels": 40,
        "oracle_target_pixels": 0,
        "component_count": 10,
        "largest_component_ratio": 0.1,
        "edge_touch_ratio": 0.0,
    }

    evidence, strength, quarantined, reason = stress._classify_semantic_evidence(
        action="move_forward",
        collided=False,
        depth_valid_ratio=1.0,
        metrics=metrics,
        min_target_pixels=24,
        min_detector_pixels=20,
    )

    assert evidence is EvidenceType.UNKNOWN
    assert strength == 0.85
    assert quarantined is True
    assert reason == "fragmented_detector_mask"


def test_semantic_evidence_marks_missed_visible_target() -> None:
    metrics = {
        "detector_pixels": 0,
        "oracle_target_pixels": 80,
        "component_count": 0,
        "largest_component_ratio": 0.0,
        "edge_touch_ratio": 0.0,
    }

    evidence, strength, quarantined, reason = stress._classify_semantic_evidence(
        action="turn_left",
        collided=False,
        depth_valid_ratio=1.0,
        metrics=metrics,
        min_target_pixels=24,
        min_detector_pixels=20,
    )

    assert evidence is EvidenceType.NON_CONFIRMATION
    assert strength == 1.0
    assert quarantined is False
    assert reason == "missed_visible_oracle_target"


def test_semantic_evidence_treats_out_of_view_absence_as_unknown() -> None:
    metrics = {
        "detector_pixels": 0,
        "oracle_target_pixels": 0,
        "component_count": 0,
        "largest_component_ratio": 0.0,
        "edge_touch_ratio": 0.0,
    }

    evidence, strength, quarantined, reason = stress._classify_semantic_evidence(
        action="move_forward",
        collided=False,
        depth_valid_ratio=1.0,
        metrics=metrics,
        min_target_pixels=24,
        min_detector_pixels=20,
    )

    assert evidence is EvidenceType.UNKNOWN
    assert strength == 0.45
    assert quarantined is False
    assert reason == "target_out_of_current_view"


def test_component_stats_tracks_largest_component() -> None:
    mask = np.zeros((8, 8), dtype=bool)
    mask[1:3, 1:3] = True
    mask[5, 5] = True

    assert stress._component_stats(mask) == (2, 4)


def test_structural_category_matching_handles_compound_names() -> None:
    assert stress._is_structural_category("stairs railing") is True
    assert stress._is_structural_category("wooden_door") is True
    assert stress._is_structural_category("dresser") is False
