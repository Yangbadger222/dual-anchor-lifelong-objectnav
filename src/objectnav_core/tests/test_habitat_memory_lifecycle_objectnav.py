from __future__ import annotations

import json
from pathlib import Path

from types import SimpleNamespace

from objectnav_core.evaluation.habitat_memory_lifecycle_objectnav import (
    LifecycleVerification,
    _cached_action_route_sequence,
    _choose_lifecycle_anchor_candidate,
    _choose_lifecycle_fallback_candidate,
    _rank_lifecycle_anchor_candidates,
    _stale_memory_verification,
    _lifecycle_row,
    plan_lifecycle_query,
    plan_lifecycle_sequence,
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


def test_memory_guided_charges_fallback_from_failed_memory_pose() -> None:
    result = plan_lifecycle_query(
        mode="memory_guided",
        memory_path_cost_m=3.0,
        fallback_path_cost_m=20.0,
        fallback_from_memory_path_cost_m=5.5,
        memory_verification=_verification(
            EvidenceType.NON_CONFIRMATION,
            target_visible=False,
        ),
        fallback_verifications=(
            _verification(EvidenceType.POSITIVE, target_visible=True),
        ),
    )

    assert result.success is True
    assert result.route == ("memory", "fallback")
    assert result.total_path_length_m == 8.5


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
        detector_prompt_mode="target_aliases",
        seed=313,
    )

    assert summary["task"] == "habitat_memory_lifecycle_objectnav_preflight"
    assert summary["full_habitat_run"] is False
    assert summary["detector"] == "grounding_dino"
    assert summary["modes"] == ["memory_guided", "naive_count", "no_memory"]
    assert summary["noise_levels"] == ["clean", "mild"]
    assert summary["target_categories"] == ["bed", "toilet"]
    assert summary["detector_prompt_mode"] == "target_aliases"
    assert summary["action_metrics"] is False
    assert summary["artifact_files"]["summary"] == "summary.json"
    assert any("not official Habitat SPL" in limit for limit in summary["limits"])
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == summary


def test_lifecycle_trace_rows_record_evidence_reasons() -> None:
    group = SimpleNamespace(
        group_id="scene|chair|goal_object:1",
        scene_key="scene",
        category="chair",
        instance_id="goal_object:1",
        discovery_episode=SimpleNamespace(episode_id="discover"),
        query_episode=SimpleNamespace(episode_id="query"),
    )
    memory_verification = LifecycleVerification(
        evidence_type=EvidenceType.UNKNOWN,
        target_visible=True,
        evidence_reason="edge_touch_breakthrough",
    )
    fallback_verification = LifecycleVerification(
        evidence_type=EvidenceType.POSITIVE,
        target_visible=True,
        evidence_reason="detector_positive_mask",
    )
    result = plan_lifecycle_query(
        mode="memory_guided",
        memory_path_cost_m=3.0,
        fallback_path_cost_m=7.0,
        memory_verification=memory_verification,
        fallback_verifications=(fallback_verification,),
    )

    row = _lifecycle_row(
        group=group,
        mode="memory_guided",
        noise_level="clean",
        detector="grounding_dino",
        detector_prompt_categories=("chair",),
        memory_anchor_source="goal_viewpoint:0",
        memory_path_cost=3.0,
        fallback_path_cost=7.0,
        fallback_from_memory_path_cost=4.5,
        oracle_goal_path_cost=2.0,
        search_proxy_waypoint_count=1,
        fallback_from_memory_waypoint_count=2,
        fallback_anchor_source="goal_viewpoint:1",
        fallback_strategy="detector_positive",
        memory_verification=memory_verification,
        fallback_verification=fallback_verification,
        result=result,
        normalized_category="chair",
    )

    assert row["memory_evidence_reason"] == "edge_touch_breakthrough"
    assert row["fallback_evidence_reason"] == "detector_positive_mask"
    assert row["fallback_from_memory_path_cost_m"] == 4.5
    assert row["fallback_from_memory_waypoint_count"] == 2
    assert row["fallback_anchor_source"] == "goal_viewpoint:1"
    assert row["fallback_strategy"] == "detector_positive"


def test_detector_qualified_anchor_prefers_positive_over_first_viewpoint() -> None:
    first = SimpleNamespace(source="goal_viewpoint:0", target_pixels=500)
    better_visible = SimpleNamespace(source="goal_viewpoint:1", target_pixels=1200)
    qualified = SimpleNamespace(source="goal_viewpoint:2", target_pixels=900)
    verifications = {
        "goal_viewpoint:0": _verification(EvidenceType.NON_CONFIRMATION, target_visible=True),
        "goal_viewpoint:1": _verification(EvidenceType.UNKNOWN, target_visible=True),
        "goal_viewpoint:2": _verification(EvidenceType.POSITIVE, target_visible=True),
    }

    selected = _choose_lifecycle_anchor_candidate(
        candidates=(first, better_visible, qualified),
        verifications=verifications,
        strategy="detector_positive",
        min_target_pixels=24,
    )

    assert selected is qualified


def test_detector_qualified_anchor_falls_back_to_most_visible_viewpoint() -> None:
    first = SimpleNamespace(source="goal_viewpoint:0", target_pixels=500)
    better_visible = SimpleNamespace(source="goal_viewpoint:1", target_pixels=1200)
    verifications = {
        "goal_viewpoint:0": _verification(EvidenceType.NON_CONFIRMATION, target_visible=True),
        "goal_viewpoint:1": _verification(EvidenceType.UNKNOWN, target_visible=True),
    }

    selected = _choose_lifecycle_anchor_candidate(
        candidates=(first, better_visible),
        verifications=verifications,
        strategy="most_visible",
        min_target_pixels=24,
    )

    assert selected is better_visible


def test_detector_qualified_fallback_prefers_positive_over_first_viewpoint() -> None:
    first = SimpleNamespace(source="goal_viewpoint:0", target_pixels=1800)
    qualified = SimpleNamespace(source="goal_viewpoint:1", target_pixels=900)
    verifications = {
        "goal_viewpoint:0": _verification(EvidenceType.NON_CONFIRMATION, target_visible=True),
        "goal_viewpoint:1": _verification(EvidenceType.POSITIVE, target_visible=True),
    }

    selected = _choose_lifecycle_fallback_candidate(
        candidates=(first, qualified),
        verifications=verifications,
        min_target_pixels=24,
    )

    assert selected is qualified


def test_anchor_candidate_ranking_keeps_top_visible_candidates() -> None:
    low = SimpleNamespace(source="goal_viewpoint:0", target_pixels=10)
    high = SimpleNamespace(source="goal_viewpoint:1", target_pixels=1200)
    middle = SimpleNamespace(source="goal_viewpoint:2", target_pixels=500)

    selected = _rank_lifecycle_anchor_candidates(
        candidates=(low, high, middle),
        limit=2,
    )

    assert selected == (high, middle)


def test_synthetic_stale_memory_verification_preserves_diagnostic_pixels() -> None:
    original = LifecycleVerification(
        evidence_type=EvidenceType.POSITIVE,
        target_visible=True,
        evidence_reason="detector_positive_mask",
        oracle_target_pixels=123,
        detector_pixels=99,
        overlap_pixels=88,
        detector_precision=0.8,
        oracle_recall=0.7,
        detection_count=1,
    )

    stale = _stale_memory_verification(original)

    assert stale.evidence_type is EvidenceType.NON_CONFIRMATION
    assert stale.target_visible is False
    assert stale.evidence_reason == "synthetic_stale_relocation"
    assert stale.oracle_target_pixels == 123
    assert stale.detector_pixels == 99


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


def test_summary_counts_detector_miss_only_when_attempted_route_misses() -> None:
    rows = [
        {
            "mode": "memory_guided",
            "success": True,
            "path_length_m": 4.0,
            "memory_reused": True,
            "fallback_used": False,
            "stale_check_count": 0,
            "detector_miss": True,
            "attempted_detector_miss": False,
        },
        {
            "mode": "no_memory",
            "success": False,
            "path_length_m": 18.0,
            "memory_reused": False,
            "fallback_used": True,
            "stale_check_count": 0,
            "detector_miss": True,
            "attempted_detector_miss": True,
        },
    ]

    summary = summarize_lifecycle_results(
        rows=rows,
        selected_episode_ids=("1",),
        selected_groups=1,
    )

    assert summary["mode_metrics"]["memory_guided"]["detector_miss_count"] == 0
    assert summary["mode_metrics"]["no_memory"]["detector_miss_count"] == 1


def test_summary_aggregates_optional_action_metrics() -> None:
    rows = [
        {
            "mode": "memory_guided",
            "success": True,
            "path_length_m": 4.0,
            "memory_reused": True,
            "fallback_used": False,
            "stale_check_count": 0,
            "attempted_detector_miss": False,
            "action_count": 12,
            "executed_distance_m": 3.0,
        },
        {
            "mode": "memory_guided",
            "success": True,
            "path_length_m": 10.0,
            "memory_reused": False,
            "fallback_used": True,
            "stale_check_count": 1,
            "attempted_detector_miss": False,
            "action_count": 30,
            "executed_distance_m": 7.5,
        },
    ]

    summary = summarize_lifecycle_results(
        rows=rows,
        selected_episode_ids=("1",),
        selected_groups=1,
    )

    assert summary["mode_metrics"]["memory_guided"]["total_action_count"] == 42
    assert summary["mode_metrics"]["memory_guided"]["mean_action_count"] == 21.0
    assert summary["mode_metrics"]["memory_guided"]["total_executed_distance_m"] == 10.5


def test_cached_action_route_sequence_preserves_all_route_goals(monkeypatch) -> None:
    calls: list[tuple[tuple[float, float, float], ...]] = []

    def fake_follow_sequence(**kwargs):
        calls.append(tuple(kwargs["goal_positions"]))
        return SimpleNamespace(
            action_count=7,
            executed_distance_m=3.5,
            reached_stop=True,
        )

    from objectnav_core.evaluation import habitat_action_follower

    monkeypatch.setattr(
        habitat_action_follower,
        "follow_greedy_geodesic_route_sequence",
        fake_follow_sequence,
    )
    cache = {}

    route = _cached_action_route_sequence(
        cache=cache,
        habitat_sim=object(),
        sim=SimpleNamespace(),
        start_position=(0.0, 0.0, 0.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        route_goals=((1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
    )
    cached_route = _cached_action_route_sequence(
        cache=cache,
        habitat_sim=object(),
        sim=SimpleNamespace(),
        start_position=(0.0, 0.0, 0.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        route_goals=((1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
    )

    assert route is cached_route
    assert route.action_count == 7
    assert calls == [((1.0, 0.0, 0.0), (2.0, 0.0, 0.0))]


def test_search_proxy_rows_keep_oracle_goal_lower_bound() -> None:
    result = plan_lifecycle_query(
        mode="no_memory",
        memory_path_cost_m=5.0,
        fallback_path_cost_m=21.0,
        memory_verification=_verification(EvidenceType.POSITIVE, target_visible=True),
        fallback_verifications=(
            _verification(EvidenceType.POSITIVE, target_visible=True),
        ),
    )

    assert result.total_path_length_m == 21.0
    assert result.route == ("fallback",)
    assert result.total_path_length_m > 5.0


def test_memory_guided_repairs_stale_anchor_across_repeated_queries() -> None:
    stale_memory = _verification(EvidenceType.NON_CONFIRMATION, target_visible=False)
    repaired_memory = _verification(EvidenceType.POSITIVE, target_visible=True)
    fallback = _verification(EvidenceType.POSITIVE, target_visible=True)

    memory_results = plan_lifecycle_sequence(
        mode="memory_guided",
        repeats=2,
        initial_memory_path_cost_m=6.0,
        repaired_memory_path_cost_m=2.0,
        fallback_path_cost_m=11.0,
        fallback_from_memory_path_cost_m=4.0,
        initial_memory_verification=stale_memory,
        repaired_memory_verification=repaired_memory,
        fallback_verification=fallback,
    )
    naive_results = plan_lifecycle_sequence(
        mode="naive_count",
        repeats=2,
        initial_memory_path_cost_m=6.0,
        repaired_memory_path_cost_m=2.0,
        fallback_path_cost_m=11.0,
        fallback_from_memory_path_cost_m=4.0,
        initial_memory_verification=stale_memory,
        repaired_memory_verification=repaired_memory,
        fallback_verification=fallback,
        naive_prior_positive_count=1,
    )

    assert [result.route for result in memory_results] == [
        ("memory", "fallback"),
        ("memory",),
    ]
    assert [result.total_path_length_m for result in memory_results] == [10.0, 2.0]
    assert [result.route for result in naive_results] == [
        ("memory", "fallback"),
        ("memory", "fallback"),
    ]
    assert [result.total_path_length_m for result in naive_results] == [10.0, 10.0]
