from __future__ import annotations

import json
from pathlib import Path

from objectnav_core.evaluation.habitat_memory_lifecycle_objectnav import (
    LifecycleVerification,
    plan_lifecycle_query,
    run_habitat_memory_lifecycle_preflight,
    summarize_lifecycle_results,
)
from objectnav_core.memory.usability import EvidenceType


def _verification(
    evidence_type: EvidenceType,
    *,
    target_visible: bool,
) -> LifecycleVerification:
    return LifecycleVerification(
        evidence_type=evidence_type,
        target_visible=target_visible,
        evidence_strength=1.0,
        evidence_reason=evidence_type.value,
    )


def test_memory_guided_stops_after_successful_memory_verification() -> None:
    result = plan_lifecycle_query(
        mode="memory_guided",
        memory_path_cost_m=4.25,
        fallback_path_cost_m=18.0,
        memory_verification=_verification(EvidenceType.POSITIVE, target_visible=True),
        fallback_verifications=(
            _verification(EvidenceType.POSITIVE, target_visible=True),
        ),
    )

    assert result.success is True
    assert result.total_path_length_m == 4.25
    assert result.route == ("memory",)
    assert result.memory_attempted is True
    assert result.memory_reused is True
    assert result.fallback_used is False
    assert result.stop_reason == "memory_verified"


def test_memory_guided_falls_back_after_failed_memory_verification() -> None:
    result = plan_lifecycle_query(
        mode="memory_guided",
        memory_path_cost_m=3.0,
        fallback_path_cost_m=11.5,
        memory_verification=_verification(
            EvidenceType.NON_CONFIRMATION,
            target_visible=False,
        ),
        fallback_verifications=(
            _verification(EvidenceType.POSITIVE, target_visible=True),
        ),
    )

    assert result.success is True
    assert result.total_path_length_m == 14.5
    assert result.route == ("memory", "fallback")
    assert result.memory_attempted is True
    assert result.memory_reused is False
    assert result.fallback_used is True
    assert result.stale_check_count == 1
    assert result.stop_reason == "fallback_verified"


def test_no_memory_skips_memory_pose_even_if_memory_would_verify() -> None:
    result = plan_lifecycle_query(
        mode="no_memory",
        memory_path_cost_m=2.0,
        fallback_path_cost_m=12.0,
        memory_verification=_verification(EvidenceType.POSITIVE, target_visible=True),
        fallback_verifications=(
            _verification(EvidenceType.POSITIVE, target_visible=True),
        ),
    )

    assert result.success is True
    assert result.total_path_length_m == 12.0
    assert result.route == ("fallback",)
    assert result.memory_attempted is False
    assert result.memory_reused is False
    assert result.fallback_used is True


def test_naive_count_needs_two_positive_observations_and_ignores_non_confirmation() -> None:
    first_only = plan_lifecycle_query(
        mode="naive_count",
        memory_path_cost_m=2.0,
        fallback_path_cost_m=12.0,
        memory_verification=_verification(EvidenceType.POSITIVE, target_visible=True),
        fallback_verifications=(),
        naive_prior_positive_count=0,
    )

    assert first_only.success is False
    assert first_only.naive_positive_count == 1
    assert first_only.stop_reason == "naive_count_insufficient_positive_count"
    assert first_only.memory_attempted is True

    second_positive_after_non_confirmation = plan_lifecycle_query(
        mode="naive_count",
        memory_path_cost_m=2.0,
        fallback_path_cost_m=12.0,
        memory_verification=_verification(EvidenceType.NON_CONFIRMATION, target_visible=False),
        fallback_verifications=(
            _verification(EvidenceType.NON_CONFIRMATION, target_visible=False),
            _verification(EvidenceType.POSITIVE, target_visible=True),
        ),
        naive_prior_positive_count=1,
    )

    assert second_positive_after_non_confirmation.success is True
    assert second_positive_after_non_confirmation.naive_positive_count == 2
    assert second_positive_after_non_confirmation.route == ("memory", "fallback")
    assert second_positive_after_non_confirmation.total_path_length_m == 14.0


def test_lifecycle_preflight_writes_summary(tmp_path: Path) -> None:
    summary = run_habitat_memory_lifecycle_preflight(
        output_dir=tmp_path,
        dataset_dir="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean", "mild"),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        modes=("memory_guided", "naive_count", "no_memory"),
        target_categories=("bed", "toilet"),
        episodes_per_category=2,
        seed=313,
    )

    assert summary["task"] == "habitat_memory_lifecycle_objectnav_preflight"
    assert summary["full_habitat_run"] is False
    assert summary["detector"] == "grounding_dino"
    assert summary["modes"] == ["memory_guided", "naive_count", "no_memory"]
    assert summary["noise_levels"] == ["clean", "mild"]
    assert summary["target_categories"] == ["bed", "toilet"]
    assert summary["artifact_files"]["summary"] == "summary.json"
    assert any("not official Habitat SPL" in limit for limit in summary["limits"])
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == summary


def test_summarize_lifecycle_results_reports_mode_comparison() -> None:
    rows = [
        {
            "mode": "memory_guided",
            "success": True,
            "path_length_m": 4.0,
            "memory_reused": True,
            "fallback_used": False,
            "stale_check_count": 0,
            "detector_miss": False,
        },
        {
            "mode": "memory_guided",
            "success": True,
            "path_length_m": 13.0,
            "memory_reused": False,
            "fallback_used": True,
            "stale_check_count": 1,
            "detector_miss": True,
        },
        {
            "mode": "naive_count",
            "success": True,
            "path_length_m": 18.0,
            "memory_reused": False,
            "fallback_used": True,
            "stale_check_count": 0,
            "detector_miss": False,
        },
        {
            "mode": "no_memory",
            "success": True,
            "path_length_m": 24.0,
            "memory_reused": False,
            "fallback_used": True,
            "stale_check_count": 0,
            "detector_miss": False,
        },
    ]

    summary = summarize_lifecycle_results(
        rows=rows,
        selected_episode_ids=("3", "33"),
        selected_groups=2,
    )

    assert summary["selected_groups"] == 2
    assert summary["mode_metrics"]["memory_guided"]["success_episodes"] == 2
    assert summary["mode_metrics"]["memory_guided"]["total_path_length_m"] == 17.0
    assert summary["mode_metrics"]["memory_guided"]["memory_reuse_episodes"] == 1
    assert summary["mode_metrics"]["memory_guided"]["fallback_count"] == 1
    assert summary["mode_metrics"]["memory_guided"]["stale_check_count"] == 1
    assert summary["mode_metrics"]["memory_guided"]["detector_miss_count"] == 1
    assert summary["comparison"]["memory_guided_vs_no_memory_path_reduction_ratio"] > 0.2
