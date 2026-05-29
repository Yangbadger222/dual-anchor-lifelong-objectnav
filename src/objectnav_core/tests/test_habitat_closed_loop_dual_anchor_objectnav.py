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
    assert summary["memory_valid_prior"] == 0.5
    assert summary["artifact_files"]["summary"] == "summary.json"
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == summary


def test_habitat_closed_loop_preflight_records_grounding_dino_detector_config(
    tmp_path,
) -> None:
    summary = run_habitat_closed_loop_dual_anchor_preflight(
        tmp_path,
        dataset_dir="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_categories=("plant", "toilet"),
        max_groups=2,
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        grounding_dino_text_threshold=0.2,
        grounding_dino_max_image_side=384,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_level="mild",
        min_target_pixels=24,
        min_detector_pixels=20,
        max_detection_area_ratio=0.7,
        detector_prompt_mode="target",
    )

    assert summary["detector"] == "grounding_dino"
    assert summary["detector_weights"] == "IDEA-Research/grounding-dino-tiny"
    assert summary["detector_conf"] == 0.25
    assert summary["grounding_dino_text_threshold"] == 0.2
    assert summary["grounding_dino_max_image_side"] == 384
    assert summary["rgb_noise_profile"] == "configs/noise/rgb_published_v1.yaml"
    assert summary["depth_noise_profile"] == "configs/noise/depth_realsense_d435_v1.yaml"
    assert summary["noise_level"] == "mild"
    assert summary["min_target_pixels"] == 24
    assert summary["min_detector_pixels"] == 20
    assert summary["max_detection_area_ratio"] == 0.7
    assert summary["detector_prompt_mode"] == "target"


def test_habitat_closed_loop_preflight_records_navmesh_frontier_config(tmp_path) -> None:
    summary = run_habitat_closed_loop_dual_anchor_preflight(
        tmp_path,
        dataset_dir="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_categories=("plant", "toilet"),
        max_groups=2,
        frontier_mode="navmesh_frontier",
        frontier_probe_count=5,
        frontier_probe_heading_count=8,
    )

    assert summary["frontier_mode"] == "navmesh_frontier"
    assert summary["frontier_probe_count"] == 5
    assert summary["frontier_probe_heading_count"] == 8


def test_select_balanced_groups_prefers_category_coverage_before_duplicates() -> None:
    from types import SimpleNamespace

    groups = [
        SimpleNamespace(category="chair", group_id="chair-1"),
        SimpleNamespace(category="chair", group_id="chair-2"),
        SimpleNamespace(category="plant", group_id="plant-1"),
        SimpleNamespace(category="sofa", group_id="sofa-1"),
    ]

    selected = closed_loop._select_balanced_groups(groups, max_groups=3)

    assert [group.group_id for group in selected] == [
        "chair-1",
        "plant-1",
        "sofa-1",
    ]


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


def test_habitat_option_row_defers_memory_when_expected_utility_prefers_frontier() -> None:
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
            matching_reason="expected_utility_frontier",
            memory_verified=False,
            fallback_verified=True,
            memory_decision="frontier_first",
            memory_valid_prior=0.5,
            expected_memory_first_action_count=21.0,
            expected_frontier_first_action_count=30.0,
        )
    )

    assert row["success"] is True
    assert row["selected_candidate_types"] == ["frontier"]
    assert row["memory_reused"] is False
    assert row["action_count"] == 30
    assert row["memory_decision"] == "frontier_first"
    assert row["memory_valid_prior"] == 0.5
    assert row["expected_memory_first_action_count"] == 21.0


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


def test_accepted_repaired_memory_records_memory_first_decision() -> None:
    assert (
        closed_loop._memory_decision_for_row(
            policy="memory_guided",
            matching_reason="accepted",
            raw_memory_decision="frontier_first",
        )
        == "memory_first"
    )
    assert (
        closed_loop._memory_decision_for_row(
            policy="memory_guided",
            matching_reason="expected_utility_frontier",
            raw_memory_decision="frontier_first",
        )
        == "frontier_first"
    )


def test_expected_utility_skips_memory_when_stale_probe_is_not_worth_it() -> None:
    assert closed_loop._expected_memory_first_action_count(
        memory_action_count=139,
        fallback_from_memory_action_count=408,
        memory_valid_prior=0.5,
    ) == 343.0
    assert (
        closed_loop._memory_first_decision(
            memory_action_count=139,
            fallback_from_memory_action_count=408,
            fallback_action_count=202,
            memory_valid_prior=0.5,
        )
        == "frontier_first"
    )
    assert (
        closed_loop._memory_first_decision(
            memory_action_count=69,
            fallback_from_memory_action_count=371,
            fallback_action_count=355,
            memory_valid_prior=0.5,
        )
        == "memory_first"
    )


def test_shared_detector_gate_controls_memory_verification_for_all_memory_policies() -> None:
    positive = closed_loop._OracleVisible(target_visible=True)
    missed = closed_loop._OracleVisible(target_visible=False)

    assert closed_loop._memory_verified_by_shared_gate(
        policy="memory_guided",
        matching_reason="accepted",
        active_memory_verification=positive,
    )
    assert closed_loop._memory_verified_by_shared_gate(
        policy="naive_count",
        matching_reason="accepted",
        active_memory_verification=positive,
    )
    assert not closed_loop._memory_verified_by_shared_gate(
        policy="frontier_only",
        matching_reason="accepted",
        active_memory_verification=positive,
    )
    assert not closed_loop._memory_verified_by_shared_gate(
        policy="memory_guided",
        matching_reason="accepted",
        active_memory_verification=missed,
    )
    assert not closed_loop._memory_verified_by_shared_gate(
        policy="naive_count",
        matching_reason="ambiguous",
        active_memory_verification=positive,
    )


def test_stale_proxy_forces_initial_memory_verification_to_non_confirmation() -> None:
    positive = closed_loop._OracleVisible(target_visible=True, oracle_target_pixels=100)

    stale = closed_loop._stale_proxy_initial_memory_verification(positive)

    assert stale.shared_gate_success is False
    assert stale.target_visible is False
    assert stale.evidence_reason == "stale_proxy_memory_absent"
    assert closed_loop._verification_payload(stale)["evidence_type"] == "non_confirmation"
    assert closed_loop._verification_payload(stale)["oracle_target_pixels"] == 100


def test_navmesh_frontier_probe_goals_are_seeded_and_target_agnostic() -> None:
    class PathFinder:
        def __init__(self) -> None:
            self.points = [
                (0.0, 0.0, 0.0),
                (5.0, 0.0, 0.0),
                (1.0, 0.0, 0.0),
                (7.0, 0.0, 0.0),
                (2.0, 0.0, 0.0),
                (9.0, 0.0, 0.0),
            ]
            self.index = 0

        def get_random_navigable_point(self):
            point = self.points[self.index % len(self.points)]
            self.index += 1
            return point

        def is_navigable(self, point) -> bool:
            return True

    class Sim:
        def __init__(self) -> None:
            self.pathfinder = PathFinder()

    sim_a = Sim()
    sim_b = Sim()
    goals_a = closed_loop._navmesh_frontier_probe_goals(
        sim=sim_a,
        start=(0.0, 0.0, 0.0),
        seed=313,
        probe_count=3,
        min_distance_m=1.5,
        sample_attempts=6,
    )
    goals_b = closed_loop._navmesh_frontier_probe_goals(
        sim=sim_b,
        start=(0.0, 0.0, 0.0),
        seed=313,
        probe_count=3,
        min_distance_m=1.5,
        sample_attempts=6,
    )

    assert goals_a == goals_b
    assert goals_a == ((5.0, 0.0, 0.0), (7.0, 0.0, 0.0), (2.0, 0.0, 0.0))


def test_navmesh_frontier_route_stops_at_first_positive_probe() -> None:
    from types import SimpleNamespace

    visited_sources: list[str] = []

    def route_segment(*, start_position, start_rotation, goal_position):
        del start_position, start_rotation
        return SimpleNamespace(
            actions=(f"move_to_{goal_position[0]}",),
            action_count=1,
            reached_stop=True,
            final_position=goal_position,
            final_rotation=(0.0, 0.0, 0.0, 1.0),
            executed_distance_m=float(goal_position[0]),
        )

    def verify_probe(*, source, position, rotation, probe_index):
        del position, rotation, probe_index
        visited_sources.append(source)
        return closed_loop._OracleVisible(
            target_visible=source == "navmesh_frontier_probe:1:heading:0"
        )

    result = closed_loop._run_navmesh_frontier_probe_route(
        start_position=(0.0, 0.0, 0.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        probe_goals=((1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0)),
        route_segment=route_segment,
        verify_probe=verify_probe,
        probe_heading_count=1,
    )

    assert visited_sources == [
        "navmesh_frontier_probe:0:heading:0",
        "navmesh_frontier_probe:1:heading:0",
    ]
    assert result.selected_probe_source == "navmesh_frontier_probe:1:heading:0"
    assert result.selected_probe_position == (2.0, 0.0, 0.0)
    assert result.selected_verification.shared_gate_success is True
    assert result.route.action_count == 2
    assert result.route.executed_distance_m == 3.0


def test_navmesh_frontier_route_skips_unreachable_probe_segment() -> None:
    from types import SimpleNamespace

    visited_sources: list[str] = []

    def route_segment(*, start_position, start_rotation, goal_position):
        del start_position, start_rotation
        if goal_position == (1.0, 0.0, 0.0):
            raise RuntimeError("unreachable probe")
        return SimpleNamespace(
            actions=(f"move_to_{goal_position[0]}",),
            action_count=1,
            reached_stop=True,
            final_position=goal_position,
            final_rotation=(0.0, 0.0, 0.0, 1.0),
            executed_distance_m=float(goal_position[0]),
        )

    def verify_probe(*, source, position, rotation, probe_index):
        del position, rotation, probe_index
        visited_sources.append(source)
        return closed_loop._OracleVisible(target_visible=True)

    result = closed_loop._run_navmesh_frontier_probe_route(
        start_position=(0.0, 0.0, 0.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        probe_goals=((1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        route_segment=route_segment,
        verify_probe=verify_probe,
        route_error_types=(RuntimeError,),
        probe_heading_count=1,
    )

    assert visited_sources == ["navmesh_frontier_probe:1:heading:0"]
    assert result.selected_probe_source == "navmesh_frontier_probe:1:heading:0"
    assert result.route.action_count == 1


def test_navmesh_frontier_probe_scans_headings_before_next_probe() -> None:
    from types import SimpleNamespace

    visited: list[tuple[str, int]] = []
    visited_rotations: list[tuple[float, float, float, float]] = []

    def route_segment(*, start_position, start_rotation, goal_position):
        del start_position, start_rotation
        return SimpleNamespace(
            actions=(f"move_to_{goal_position[0]}",),
            reached_stop=True,
            final_position=goal_position,
            final_rotation=(0.0, 1.0, 0.0, 0.0),
            executed_distance_m=float(goal_position[0]),
        )

    def verify_probe(*, source, position, rotation, probe_index):
        del position
        visited.append((source, probe_index))
        visited_rotations.append(rotation)
        return closed_loop._OracleVisible(
            target_visible=source == "navmesh_frontier_probe:0:heading:2"
        )

    result = closed_loop._run_navmesh_frontier_probe_route(
        start_position=(0.0, 0.0, 0.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        probe_goals=((1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        route_segment=route_segment,
        verify_probe=verify_probe,
        probe_heading_count=4,
    )

    assert visited == [
        ("navmesh_frontier_probe:0:heading:0", 0),
        ("navmesh_frontier_probe:0:heading:1", 0),
        ("navmesh_frontier_probe:0:heading:2", 0),
    ]
    assert visited_rotations[0] == (0.0, 1.0, 0.0, 0.0)
    assert result.selected_probe_source == "navmesh_frontier_probe:0:heading:2"
    assert result.selected_verification.shared_gate_success is True
    assert result.route.actions == (
        "move_to_1.0",
        "scan_heading:0:1",
        "scan_heading:0:2",
    )
    assert result.route.action_count == 3


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
