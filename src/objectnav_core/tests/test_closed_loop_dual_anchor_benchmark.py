from __future__ import annotations

from objectnav_core.evaluation.closed_loop_dual_anchor_benchmark import (
    run_closed_loop_dual_anchor_benchmark,
)


def _episode(summary: dict[str, object], policy: str, episode_id: str) -> dict[str, object]:
    episodes = summary["policy_summaries"][policy]["episodes"]
    return next(episode for episode in episodes if episode["episode_id"] == episode_id)


def test_closed_loop_dual_anchor_benchmark_exercises_reuse_ambiguity_and_stale_repair(
    tmp_path,
) -> None:
    summary = run_closed_loop_dual_anchor_benchmark(tmp_path)

    assert summary["task"] == "closed_loop_dual_anchor_grid_benchmark"
    assert summary["policies"] == ["memory_guided", "frontier_only", "naive_count"]

    memory_reuse = _episode(summary, "memory_guided", "session_2_reuse")
    frontier_reuse = _episode(summary, "frontier_only", "session_2_reuse")
    ambiguous = _episode(summary, "memory_guided", "session_2_ambiguous")
    naive_ambiguous = _episode(summary, "naive_count", "session_2_ambiguous")
    stale = _episode(summary, "memory_guided", "session_2_stale_repair")

    assert memory_reuse["success"] is True
    assert memory_reuse["selected_candidate_types"][0] == "memory"
    assert memory_reuse["matching_reason"] == "accepted"
    assert memory_reuse["memory_frame_id"] == "map_session_1"
    assert memory_reuse["runtime_frame_id"] == "map_session_2"
    assert memory_reuse["frame_transform"]["dx"] != 0.0
    assert memory_reuse["frame_transform"]["dy"] != 0.0
    assert memory_reuse["path_length_m"] < frontier_reuse["path_length_m"]

    assert ambiguous["success"] is True
    assert ambiguous["matching_reason"] == "ambiguous"
    assert ambiguous["selected_candidate_types"][0] == "frontier"
    assert ambiguous["memory_reused"] is False
    assert naive_ambiguous["selected_candidate_types"][0] == "frontier"

    assert stale["success"] is True
    assert stale["selected_candidate_types"][0] == "memory"
    assert stale["matching_reason"] == "no_current_observation"
    assert stale["stale_repair_recorded"] is True
    assert stale["relocation_recorded"] is True
    assert stale["verified_object_id"] == "plant_002"

    comparison = summary["comparison"]
    assert comparison["memory_guided_path_delta_m"] > 0.0
    assert comparison["memory_guided_frontier_reduction"] > 0
