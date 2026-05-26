import csv
import json
from pathlib import Path

from objectnav_core.evaluation.grid_trace_experiment import (
    generate_grid_trace,
    run_grid_trace_experiment,
)


def test_generate_grid_trace_is_deterministic_and_uses_required_schema() -> None:
    first = generate_grid_trace(seed=17, episodes=9, steps_per_episode=8)
    second = generate_grid_trace(seed=17, episodes=9, steps_per_episode=8)

    assert first == second
    assert len(first) == 72
    assert {event.scenario for event in first} == {
        "stable_visible",
        "removed_or_moved",
        "occluded_then_revealed",
        "blocked_access",
        "ood_depth_failure",
        "nearby_same_class",
        "inflated_corridor_block",
        "stale_path_cost",
        "multi_object_association",
    }

    sample = first[0].to_row()
    assert {
        "episode_id",
        "scenario",
        "step_index",
        "robot_x",
        "robot_y",
        "robot_yaw",
        "target_x",
        "target_y",
        "evidence_type",
        "evidence_strength",
        "path_blocked",
        "association_candidates",
        "d_nav",
        "d_verify",
        "c_search",
        "b_remaining",
        "obstacle_intersects_path",
        "inflation_intersects_path",
        "stale_cost",
        "cached_d_nav",
        "cached_d_verify",
        "fresh_d_nav",
        "fresh_d_verify",
        "costmap_revision",
        "true_memory_id",
        "nearest_memory_id",
        "jpda_memory_id",
        "association_margin",
        "association_entropy",
        "false_positive",
    }.issubset(sample)

    association_events = [event for event in first if event.scenario == "multi_object_association"]
    assert any(event.nearest_memory_id != event.true_memory_id for event in association_events)
    assert any(event.jpda_memory_id == "unassigned" for event in association_events)


def test_grid_trace_experiment_writes_artifacts_and_runs_usability_replay(tmp_path: Path) -> None:
    output_dir = tmp_path / "grid_trace"

    summary = run_grid_trace_experiment(
        output_dir,
        seed=17,
        episodes=12,
        steps_per_episode=8,
    )

    assert summary["seed"] == 17
    assert summary["episodes"] == 12
    assert summary["steps_per_episode"] == 8
    assert summary["total_events"] == 96
    assert summary["artifact_files"] == {
        "summary": "summary.json",
        "events": "events.csv",
        "report": "trace_report.html",
    }
    assert summary["evidence_counts"]["positive"] > 0
    assert summary["evidence_counts"]["non_confirmation"] > 0
    assert summary["evidence_counts"]["unknown"] > 0
    assert summary["decision_counts"]["trust"] > 0
    assert summary["decision_counts"]["search"] > 0
    assert summary["scenario_summaries"]["ood_depth_failure"]["quarantined_events"] > 0
    assert summary["scenario_summaries"]["removed_or_moved"]["final_belief"]["p_usable"] < 0.4
    assert summary["path_cost_metrics"]["inflation_blocked_events"] > 0
    assert summary["path_cost_metrics"]["stale_cost_events"] > 0
    assert summary["path_cost_metrics"]["decision_flip_after_refresh"] > 0
    assert summary["path_cost_metrics"]["stale_cache_error_rate"] > 0.0
    assert summary["path_cost_metrics"]["mean_cached_to_fresh_cost_ratio"] > 1.0
    assert summary["association_metrics"]["association_events"] > 0
    assert summary["association_metrics"]["nearest_wrong_association_events"] > 0
    assert summary["association_metrics"]["jpda_rejected_ambiguous_events"] > 0
    assert summary["association_metrics"]["ghost_positive_writes_prevented"] > 0
    assert summary["scenario_summaries"]["multi_object_association"]["nearest_wrong_association_events"] > 0

    summary_path = output_dir / "summary.json"
    events_path = output_dir / "events.csv"
    report_path = output_dir / "trace_report.html"

    assert summary_path.exists()
    assert events_path.exists()
    assert report_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8")) == summary

    rows = list(csv.DictReader(events_path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 96
    assert {
        "p_existence",
        "p_location_valid",
        "p_usable",
        "p_valid",
        "decision",
        "cost_trust",
        "cost_verify",
        "cost_search",
        "cost_retire",
        "decision_stale",
        "decision_refreshed",
        "decision_flipped_after_refresh",
        "stale_cache_error",
        "true_memory_id",
        "nearest_memory_id",
        "jpda_memory_id",
        "association_margin",
        "association_entropy",
        "nearest_wrong_association",
        "jpda_rejected_ambiguous",
        "ghost_positive_write_prevented",
    }.issubset(rows[0])

    report_html = report_path.read_text(encoding="utf-8")
    assert "2D Grid Trace Experiment" in report_html
    assert "removed_or_moved" in report_html
    assert "Inflation & Stale Cost Metrics" in report_html
    assert "Association Metrics" in report_html
