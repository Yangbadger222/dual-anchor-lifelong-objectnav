from __future__ import annotations

import json

from objectnav_core.evaluation.habitat_closed_loop_dual_anchor_objectnav import (
    HabitatClosedLoopOptionPlan,
    make_habitat_closed_loop_option_row,
    run_habitat_closed_loop_dual_anchor_preflight,
    summarize_habitat_closed_loop_rows,
)
from objectnav_core.evaluation import habitat_closed_loop_dual_anchor_objectnav as closed_loop


def test_habitat_closed_loop_dual_anchor_preflight_writes_summary(tmp_path) -> None:
    summary = run_habitat_closed_loop_dual_anchor_preflight(
        tmp_path,
        dataset_dir="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_categories=("plant", "toilet"),
        max_groups=2,
        sensor_width=1280,
        sensor_height=720,
    )

    assert summary["task"] == "habitat_closed_loop_dual_anchor_objectnav_preflight"
    assert summary["full_habitat_run"] is False
    assert summary["policies"] == ["memory_guided", "frontier_only", "naive_count"]
    assert summary["session_restart"]["frame_transform"]["dx"] != 0.0
    assert summary["session_restart"]["frame_transform"]["dy"] != 0.0
    assert summary["frontier_proxy_waypoints"] == 2
    assert summary["challenge"] == "stable"
    assert summary["query_repeats"] == 1
    assert summary["artifact_files"]["summary"] == "summary.json"
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == summary


def test_habitat_option_row_records_closed_loop_action_decision() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="scene|plant|1",
            category="plant",
            policy="memory_guided",
            memory_action_count=12,
            memory_executed_distance_m=3.5,
            fallback_action_count=30,
            fallback_executed_distance_m=9.0,
            fallback_from_memory_action_count=18,
            fallback_from_memory_executed_distance_m=5.0,
            matching_reason="no_current_observation",
            memory_verified=False,
            fallback_verified=True,
            stale_repair=True,
        )
    )

    assert row["success"] is True
    assert row["selected_candidate_types"] == ["memory", "frontier"]
    assert row["matching_reason"] == "no_current_observation"
    assert row["stale_repair_recorded"] is True
    assert row["action_count"] == 30
    assert row["executed_distance_m"] == 8.5
    assert row["frame_transform"]["dx"] != 0.0


def test_habitat_option_row_defers_memory_under_ambiguous_match() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="scene|plant|1",
            category="plant",
            policy="memory_guided",
            memory_action_count=12,
            memory_executed_distance_m=3.5,
            fallback_action_count=30,
            fallback_executed_distance_m=9.0,
            fallback_from_memory_action_count=18,
            fallback_from_memory_executed_distance_m=5.0,
            matching_reason="ambiguous",
            memory_verified=True,
            fallback_verified=True,
            stale_repair=False,
        )
    )

    assert row["success"] is True
    assert row["selected_candidate_types"] == ["frontier"]
    assert row["memory_reused"] is False
    assert row["action_count"] == 30


def test_habitat_option_row_charges_post_memory_fallback_for_stale_repair() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="scene|plant|1",
            category="plant",
            policy="memory_guided",
            memory_action_count=12,
            memory_executed_distance_m=3.5,
            fallback_action_count=30,
            fallback_executed_distance_m=9.0,
            fallback_from_memory_action_count=18,
            fallback_from_memory_executed_distance_m=5.0,
            matching_reason="no_current_observation",
            memory_verified=False,
            fallback_verified=True,
            stale_repair=True,
        )
    )

    assert row["selected_candidate_types"] == ["memory", "frontier"]
    assert row["action_count"] == 30
    assert row["executed_distance_m"] == 8.5
    assert row["stale_repair_recorded"] is True


def test_habitat_repeated_stale_summary_rewards_repaired_memory_over_naive_count() -> None:
    rows = [
        make_habitat_closed_loop_option_row(
            HabitatClosedLoopOptionPlan(
                group_id="scene|plant|1",
                category="plant",
                policy="memory_guided",
                memory_action_count=12,
                memory_executed_distance_m=3.5,
                fallback_action_count=30,
                fallback_executed_distance_m=9.0,
                fallback_from_memory_action_count=18,
                fallback_from_memory_executed_distance_m=5.0,
                matching_reason="no_current_observation",
                memory_verified=False,
                fallback_verified=True,
                stale_repair=True,
                query_repeat_index=0,
            )
        ),
        make_habitat_closed_loop_option_row(
            HabitatClosedLoopOptionPlan(
                group_id="scene|plant|1",
                category="plant",
                policy="memory_guided",
                memory_action_count=8,
                memory_executed_distance_m=2.0,
                fallback_action_count=30,
                fallback_executed_distance_m=9.0,
                fallback_from_memory_action_count=18,
                fallback_from_memory_executed_distance_m=5.0,
                matching_reason="accepted",
                memory_verified=True,
                fallback_verified=True,
                stale_repair=False,
                query_repeat_index=1,
            )
        ),
        make_habitat_closed_loop_option_row(
            HabitatClosedLoopOptionPlan(
                group_id="scene|plant|1",
                category="plant",
                policy="naive_count",
                memory_action_count=12,
                memory_executed_distance_m=3.5,
                fallback_action_count=30,
                fallback_executed_distance_m=9.0,
                fallback_from_memory_action_count=18,
                fallback_from_memory_executed_distance_m=5.0,
                matching_reason="no_current_observation",
                memory_verified=False,
                fallback_verified=True,
                stale_repair=True,
                query_repeat_index=0,
            )
        ),
        make_habitat_closed_loop_option_row(
            HabitatClosedLoopOptionPlan(
                group_id="scene|plant|1",
                category="plant",
                policy="naive_count",
                memory_action_count=12,
                memory_executed_distance_m=3.5,
                fallback_action_count=30,
                fallback_executed_distance_m=9.0,
                fallback_from_memory_action_count=18,
                fallback_from_memory_executed_distance_m=5.0,
                matching_reason="no_current_observation",
                memory_verified=False,
                fallback_verified=True,
                stale_repair=True,
                query_repeat_index=1,
            )
        ),
    ]

    summary = summarize_habitat_closed_loop_rows(rows)

    assert summary["policy_summaries"]["memory_guided"]["total_action_count"] == 38
    assert summary["policy_summaries"]["naive_count"]["total_action_count"] == 60
    assert summary["comparison"]["memory_guided_vs_naive_count_action_delta"] == 22


def test_repeated_stale_uses_direct_repaired_memory_route_not_frontier_proxy() -> None:
    initial_route = object()
    repaired_route = object()
    fallback_route = object()

    assert (
        closed_loop._active_memory_route_for_repeat(
            challenge="stale_proxy",
            policy="memory_guided",
            repeat_index=1,
            initial_memory_route=initial_route,
            repaired_memory_route=repaired_route,
            fallback_route=fallback_route,
        )
        is repaired_route
    )
    assert (
        closed_loop._active_memory_route_for_repeat(
            challenge="stale_proxy",
            policy="memory_guided",
            repeat_index=0,
            initial_memory_route=initial_route,
            repaired_memory_route=repaired_route,
            fallback_route=fallback_route,
        )
        is initial_route
    )
    assert (
        closed_loop._active_memory_route_for_repeat(
            challenge="stale_proxy",
            policy="naive_count",
            repeat_index=1,
            initial_memory_route=initial_route,
            repaired_memory_route=repaired_route,
            fallback_route=fallback_route,
        )
        is initial_route
    )
