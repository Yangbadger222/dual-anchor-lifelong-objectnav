from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import numpy as np

from objectnav_core.evaluation.habitat_closed_loop_dual_anchor_objectnav import (
    HabitatClosedLoopOptionPlan,
    make_habitat_closed_loop_option_row,
    run_habitat_closed_loop_dual_anchor_preflight,
    summarize_habitat_closed_loop_rows,
)
from objectnav_core.evaluation import habitat_closed_loop_dual_anchor_objectnav as closed_loop
from objectnav_core.evaluation.habitat_memory_lifecycle_objectnav import LifecycleGroup


@dataclass(frozen=True)
class DetectorVerification:
    target_visible: bool
    oracle_target_pixels: int
    detector_pixels: int
    evidence_reason: str = "detector_positive_mask"

    @property
    def shared_gate_success(self) -> bool:
        return self.target_visible and self.detector_pixels > 0


def _lifecycle_group(
    *,
    scene_key: str,
    category: str,
    instance_id: str,
    memory_position: tuple[float, float, float] = (1.0, 0.0, 0.0),
    fallback_position: tuple[float, float, float] = (2.0, 0.0, 0.0),
) -> LifecycleGroup:
    return LifecycleGroup(
        group_id=f"{scene_key}|{category}|{instance_id}",
        scene_key=scene_key,
        category=category,
        instance_id=instance_id,
        discovery_episode=SimpleNamespace(name=f"discover:{instance_id}"),
        query_episode=SimpleNamespace(name=f"query:{instance_id}"),
        memory_position=memory_position,
        memory_rotation=(0.0, 0.0, 0.0, 1.0),
        fallback_position=fallback_position,
        fallback_rotation=(0.0, 0.0, 0.0, 1.0),
    )


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


def test_habitat_closed_loop_preflight_records_memory_local_search_config(
    tmp_path,
) -> None:
    summary = run_habitat_closed_loop_dual_anchor_preflight(
        tmp_path,
        dataset_dir="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_categories=("plant", "toilet"),
        max_groups=2,
        post_memory_search_mode="memory_local_active",
        local_search_radii_m=(1.0, 2.0, 4.0),
        local_search_probe_count=6,
        local_search_heading_count=8,
        local_search_score_mode="belief_gain",
    )

    assert summary["post_memory_search_mode"] == "memory_local_active"
    assert summary["local_search_radii_m"] == [1.0, 2.0, 4.0]
    assert summary["local_search_probe_count"] == 6
    assert summary["local_search_heading_count"] == 8
    assert summary["local_search_score_mode"] == "belief_gain"


def test_habitat_closed_loop_preflight_records_memory_reliability_mode(
    tmp_path,
) -> None:
    summary = run_habitat_closed_loop_dual_anchor_preflight(
        tmp_path,
        dataset_dir="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_categories=("plant", "toilet"),
        max_groups=2,
        memory_reliability_mode="evidence",
    )

    assert summary["memory_reliability_mode"] == "evidence"


def test_post_memory_search_mode_defaults_to_frontier_mode() -> None:
    assert (
        closed_loop._effective_post_memory_search_mode(
            frontier_mode="search_proxy",
            post_memory_search_mode="frontier_mode",
        )
        == "search_proxy"
    )
    assert (
        closed_loop._effective_post_memory_search_mode(
            frontier_mode="navmesh_frontier",
            post_memory_search_mode="memory_local_active",
        )
        == "memory_local_active"
    )


def test_habitat_closed_loop_preflight_records_route_observation_mode(
    tmp_path,
) -> None:
    summary = run_habitat_closed_loop_dual_anchor_preflight(
        tmp_path,
        dataset_dir="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_categories=("plant", "toilet"),
        max_groups=2,
        route_observation_mode="per_action",
    )

    assert summary["route_observation_mode"] == "per_action"


def test_habitat_closed_loop_preflight_records_detector_confirmation_config(
    tmp_path,
) -> None:
    summary = run_habitat_closed_loop_dual_anchor_preflight(
        tmp_path,
        dataset_dir="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        target_categories=("plant", "toilet"),
        max_groups=2,
        detector_confirmation_mode="multiview",
        detector_confirmation_frames=2,
        detector_confirmation_min_translation=0.05,
        detector_confirmation_min_rotation_deg=5.0,
        detector_confirmation_min_mask_iou=0.05,
    )

    assert summary["detector_confirmation_mode"] == "multiview"
    assert summary["detector_confirmation"] == {
        "frames": 2,
        "min_translation_m": 0.05,
        "min_rotation_deg": 5.0,
        "min_mask_iou": 0.05,
    }


def test_select_balanced_groups_prefers_category_coverage_before_duplicates() -> None:
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


def test_select_closed_loop_groups_preserves_explicit_order() -> None:
    groups = [
        SimpleNamespace(category="chair", group_id="chair-1"),
        SimpleNamespace(category="plant", group_id="plant-1"),
        SimpleNamespace(category="sofa", group_id="sofa-1"),
    ]

    selected = closed_loop._select_closed_loop_groups(
        groups,
        max_groups=1,
        selected_group_ids=("sofa-1", "chair-1"),
    )

    assert [group.group_id for group in selected] == ["sofa-1", "chair-1"]


def test_select_closed_loop_groups_rejects_missing_explicit_group_ids() -> None:
    groups = [
        SimpleNamespace(category="chair", group_id="chair-1"),
        SimpleNamespace(category="plant", group_id="plant-1"),
    ]

    with pytest.raises(ValueError, match="missing"):
        closed_loop._select_closed_loop_groups(
            groups,
            max_groups=1,
            selected_group_ids=("chair-1", "sofa-9"),
        )


def test_build_goal_object_relocation_groups_pairs_same_scene_category_instances() -> None:
    old_group = _lifecycle_group(
        scene_key="scene-a.glb",
        category="chair",
        instance_id="goal_object:1",
    )
    new_group = _lifecycle_group(
        scene_key="scene-a.glb",
        category="chair",
        instance_id="goal_object:2",
    )
    other_scene_group = _lifecycle_group(
        scene_key="scene-b.glb",
        category="chair",
        instance_id="goal_object:3",
    )

    relocated = closed_loop._build_goal_object_relocation_groups(
        [old_group, new_group, other_scene_group]
    )

    assert [group.group_id for group in relocated] == [
        "scene-a.glb|chair|relocated:goal_object:1->goal_object:2",
        "scene-a.glb|chair|relocated:goal_object:2->goal_object:1",
    ]
    assert relocated[0].discovery_episode is old_group.discovery_episode
    assert relocated[0].query_episode is new_group.query_episode
    assert relocated[0].memory_instance_id == "goal_object:1"
    assert relocated[0].target_instance_id == "goal_object:2"


def test_build_goal_object_relocation_groups_ranks_pairs_by_spatial_separation() -> None:
    near_group = _lifecycle_group(
        scene_key="scene-a.glb",
        category="chair",
        instance_id="goal_object:1",
        memory_position=(0.0, 0.0, 0.0),
        fallback_position=(0.0, 0.0, 0.0),
    )
    middle_group = _lifecycle_group(
        scene_key="scene-a.glb",
        category="chair",
        instance_id="goal_object:2",
        memory_position=(1.0, 0.0, 0.0),
        fallback_position=(1.0, 0.0, 0.0),
    )
    far_group = _lifecycle_group(
        scene_key="scene-a.glb",
        category="chair",
        instance_id="goal_object:3",
        memory_position=(8.0, 0.0, 0.0),
        fallback_position=(8.0, 0.0, 0.0),
    )

    relocated = closed_loop._build_goal_object_relocation_groups(
        [near_group, middle_group, far_group]
    )

    assert relocated[0].group_id == (
        "scene-a.glb|chair|relocated:goal_object:1->goal_object:3"
    )
    assert relocated[0].relocation_pair_distance_m == 8.0
    assert relocated[1].group_id == (
        "scene-a.glb|chair|relocated:goal_object:3->goal_object:1"
    )
    assert relocated[1].relocation_pair_distance_m == 8.0


def test_goal_object_relocation_uses_old_memory_and_new_query_semantic_ids() -> None:
    old_group = _lifecycle_group(
        scene_key="scene-a.glb",
        category="chair",
        instance_id="goal_object:1",
    )
    new_group = _lifecycle_group(
        scene_key="scene-a.glb",
        category="chair",
        instance_id="goal_object:2",
    )
    relocated = closed_loop._build_goal_object_relocation_groups(
        [old_group, new_group]
    )[0]

    memory_ids, query_ids = closed_loop._semantic_ids_for_closed_loop_group(
        semantic_id_to_category={1: "chair", 2: "chair", 3: "plant"},
        group=relocated,
        challenge="goal_object_relocation",
    )

    assert memory_ids == (1,)
    assert query_ids == (2,)


def test_stable_challenge_keeps_category_semantic_scope() -> None:
    group = _lifecycle_group(
        scene_key="scene-a.glb",
        category="chair",
        instance_id="goal_object:1",
    )

    memory_ids, query_ids = closed_loop._semantic_ids_for_closed_loop_group(
        semantic_id_to_category={1: "chair", 2: "chair", 3: "plant"},
        group=group,
        challenge="stable",
    )

    assert memory_ids == (1, 2)
    assert query_ids == (1, 2)


def test_goal_object_relocation_verifies_memory_candidates_against_old_instance() -> None:
    assert closed_loop._candidate_verification_semantic_ids(
        challenge="goal_object_relocation",
        candidate_role="memory_anchor",
        memory_target_semantic_ids=(1,),
        target_semantic_ids=(2,),
    ) == (1,)
    assert closed_loop._candidate_verification_semantic_ids(
        challenge="goal_object_relocation",
        candidate_role="query_task",
        memory_target_semantic_ids=(1,),
        target_semantic_ids=(2,),
    ) == (2,)


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
    assert row["memory_decision_bucket"] == "memory_missed_then_frontier_repaired"


def test_habitat_option_row_records_goal_object_scope_metadata() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="scene|chair|relocated:goal_object:1->goal_object:2",
            category="chair",
            policy="memory_guided",
            memory_action_count=12,
            memory_executed_distance_m=3.5,
            fallback_action_count=30,
            fallback_executed_distance_m=9.0,
            fallback_from_memory_action_count=18,
            fallback_from_memory_executed_distance_m=5.0,
            matching_reason="accepted",
            memory_verified=False,
            fallback_verified=True,
            memory_instance_id="goal_object:1",
            target_instance_id="goal_object:2",
            relocation_pair_distance_m=8.25,
        )
    )

    assert row["memory_instance_id"] == "goal_object:1"
    assert row["target_instance_id"] == "goal_object:2"
    assert row["relocation_pair_distance_m"] == 8.25


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
    assert row["memory_decision_bucket"] == "frontier_shorter_selected"


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


def test_summary_counts_memory_decision_buckets() -> None:
    rows = [
        {"policy": "memory_guided", "success": True, "action_count": 69, "executed_distance_m": 8.0, "memory_reused": True, "selected_candidate_types": ["memory"], "memory_decision_bucket": "memory_shorter_reused", "hindsight_action_regret": 0, "hindsight_distance_regret_m": 0.0},
        {"policy": "memory_guided", "success": True, "action_count": 125, "executed_distance_m": 19.8, "memory_reused": False, "selected_candidate_types": ["frontier"], "memory_decision_bucket": "frontier_shorter_selected", "hindsight_action_regret": 0, "hindsight_distance_regret_m": 0.0},
        {"policy": "memory_guided", "success": True, "action_count": 179, "executed_distance_m": 26.9, "memory_reused": True, "selected_candidate_types": ["memory"], "memory_decision_bucket": "memory_rescued_frontier_failure", "hindsight_action_regret": 0, "hindsight_distance_regret_m": 0.0},
        {"policy": "frontier_only", "success": True, "action_count": 125, "executed_distance_m": 19.8, "memory_reused": False, "selected_candidate_types": ["frontier"], "memory_decision_bucket": "frontier_only", "hindsight_action_regret": 3, "hindsight_distance_regret_m": 1.5},
    ]

    summary = summarize_habitat_closed_loop_rows(rows)

    assert summary["policy_summaries"]["memory_guided"]["memory_decision_buckets"] == {
        "frontier_shorter_selected": 1,
        "memory_rescued_frontier_failure": 1,
        "memory_shorter_reused": 1,
    }


def test_summary_records_hindsight_regret_totals() -> None:
    rows = [
        {"policy": "memory_guided", "success": True, "action_count": 115, "executed_distance_m": 16.5, "memory_reused": False, "selected_candidate_types": ["frontier"], "memory_decision_bucket": "valid_memory_wrongly_deferred", "hindsight_action_regret": 46, "hindsight_distance_regret_m": 8.5},
        {"policy": "memory_guided", "success": True, "action_count": 125, "executed_distance_m": 19.84, "memory_reused": False, "selected_candidate_types": ["frontier"], "memory_decision_bucket": "frontier_shorter_selected", "hindsight_action_regret": 0, "hindsight_distance_regret_m": 0.0},
    ]

    summary = summarize_habitat_closed_loop_rows(rows)

    metrics = summary["policy_summaries"]["memory_guided"]
    assert metrics["total_hindsight_action_regret"] == 46
    assert metrics["mean_hindsight_action_regret"] == 23.0
    assert metrics["total_hindsight_distance_regret_m"] == 8.5


def test_memory_guided_accepted_memory_keeps_expected_utility_frontier_decision() -> None:
    assert (
        closed_loop._memory_decision_for_row(
            policy="memory_guided",
            matching_reason="accepted",
            raw_memory_decision="frontier_first",
        )
        == "frontier_first"
    )
    assert (
        closed_loop._memory_decision_for_row(
            policy="memory_guided",
            matching_reason="expected_utility_frontier",
            raw_memory_decision="frontier_first",
        )
        == "frontier_first"
    )


def test_naive_count_accepted_memory_ignores_expected_utility_frontier_decision() -> None:
    assert (
        closed_loop._memory_decision_for_row(
            policy="naive_count",
            matching_reason="accepted",
            raw_memory_decision="frontier_first",
        )
        == "memory_first"
    )


def test_memory_guided_row_selects_frontier_when_expected_utility_prefers_it() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="g1",
            category="plant",
            policy="memory_guided",
            memory_action_count=139,
            memory_executed_distance_m=22.45,
            fallback_action_count=124,
            fallback_executed_distance_m=20.22,
            fallback_from_memory_action_count=400,
            fallback_from_memory_executed_distance_m=60.0,
            matching_reason="accepted",
            memory_verified=True,
            fallback_verified=True,
            fallback_from_memory_verified=False,
            memory_decision="frontier_first",
            expected_memory_first_action_count=339.0,
            expected_frontier_first_action_count=124.0,
        )
    )

    assert row["selected_candidate_types"] == ["frontier"]
    assert row["memory_reused"] is False
    assert row["action_count"] == 124
    assert row["success"] is True
    assert row["memory_decision_bucket"] == "frontier_shorter_selected"


def test_option_row_records_memory_reliability_trace() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="g1",
            category="plant",
            policy="memory_guided",
            memory_action_count=100,
            memory_executed_distance_m=12.0,
            fallback_action_count=140,
            fallback_executed_distance_m=20.0,
            fallback_from_memory_action_count=50,
            fallback_from_memory_executed_distance_m=6.0,
            matching_reason="accepted",
            memory_verified=True,
            fallback_verified=True,
            memory_valid_prior=0.91,
            memory_reliability_mode="evidence",
            memory_reliability={
                "mode": "evidence",
                "value": 0.91,
                "components": {"current_evidence": 0.98},
                "reason": "evidence_weighted",
            },
        )
    )

    assert row["memory_valid_prior"] == 0.91
    assert row["memory_reliability_mode"] == "evidence"
    assert row["memory_reliability"]["components"]["current_evidence"] == 0.98


def test_option_row_records_route_observation_trace() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="g1",
            category="plant",
            policy="memory_guided",
            memory_action_count=12,
            memory_executed_distance_m=3.0,
            fallback_action_count=30,
            fallback_executed_distance_m=9.0,
            fallback_from_memory_action_count=5,
            fallback_from_memory_executed_distance_m=1.2,
            matching_reason="accepted",
            memory_verified=True,
            fallback_verified=True,
            route_observation_mode="per_action",
            memory_route_observation_source="memory:step:3",
            memory_route_observation_step_index=3,
            memory_route_observation_count=4,
            fallback_route_observation_source="frontier:step:6",
            fallback_route_observation_step_index=6,
            fallback_route_observation_count=7,
            fallback_from_memory_route_observation_source="repair:step:0",
            fallback_from_memory_route_observation_step_index=0,
            fallback_from_memory_route_observation_count=1,
        )
    )

    assert row["route_observation_mode"] == "per_action"
    assert row["memory_route_observation"] == {
        "source": "memory:step:3",
        "step_index": 3,
        "observation_count": 4,
    }
    assert row["fallback_route_observation"] == {
        "source": "frontier:step:6",
        "step_index": 6,
        "observation_count": 7,
    }
    assert row["fallback_from_memory_route_observation"] == {
        "source": "repair:step:0",
        "step_index": 0,
        "observation_count": 1,
    }


def test_option_row_flags_detector_false_confirmation_audit() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="g1",
            category="plant",
            policy="memory_guided",
            memory_action_count=12,
            memory_executed_distance_m=3.0,
            fallback_action_count=30,
            fallback_executed_distance_m=9.0,
            fallback_from_memory_action_count=5,
            fallback_from_memory_executed_distance_m=1.2,
            matching_reason="accepted",
            memory_verified=True,
            fallback_verified=True,
            memory_evidence={
                "shared_gate_success": True,
                "evidence_reason": "detector_positive_mask",
                "detector_pixels": 8150,
                "overlap_pixels": 0,
                "detector_precision": 0.0,
                "oracle_recall": 0.0,
            },
            fallback_evidence={
                "shared_gate_success": True,
                "evidence_reason": "detector_positive_mask",
                "detector_pixels": 2067,
                "overlap_pixels": 1400,
                "detector_precision": 0.67731,
                "oracle_recall": 0.725013,
            },
        )
    )

    assert row["memory_evidence"]["detector_false_confirmation"] is True
    assert row["memory_evidence"]["detector_overlap_success"] is False
    assert row["fallback_evidence"]["detector_false_confirmation"] is False
    assert row["fallback_evidence"]["detector_overlap_success"] is True


def test_policy_summary_counts_detector_false_confirmations() -> None:
    rows = [
        {
            "policy": "memory_guided",
            "success": True,
            "action_count": 12,
            "executed_distance_m": 3.0,
            "memory_reused": True,
            "selected_candidate_types": ["memory"],
            "memory_decision_bucket": "memory_shorter_reused",
            "hindsight_action_regret": 0,
            "hindsight_distance_regret_m": 0.0,
            "memory_evidence": {"detector_false_confirmation": True},
            "fallback_evidence": {"detector_false_confirmation": False},
            "fallback_from_memory_evidence": {"detector_false_confirmation": False},
        },
        {
            "policy": "memory_guided",
            "success": True,
            "action_count": 15,
            "executed_distance_m": 4.0,
            "memory_reused": True,
            "selected_candidate_types": ["memory"],
            "memory_decision_bucket": "memory_shorter_reused",
            "hindsight_action_regret": 0,
            "hindsight_distance_regret_m": 0.0,
            "memory_evidence": {"detector_false_confirmation": False},
            "fallback_evidence": {"detector_false_confirmation": True},
            "fallback_from_memory_evidence": {"detector_false_confirmation": True},
        },
    ]

    summary = summarize_habitat_closed_loop_rows(rows)

    assert summary["policy_summaries"]["memory_guided"][
        "detector_false_confirmation_counts"
    ] == {
        "fallback": 1,
        "fallback_from_memory": 1,
        "memory": 1,
    }


def test_policy_summary_counts_detector_confirmation_outcomes() -> None:
    rows = [
        {
            "policy": "memory_guided",
            "success": True,
            "action_count": 12,
            "executed_distance_m": 3.0,
            "memory_reused": True,
            "selected_candidate_types": ["memory"],
            "memory_decision_bucket": "memory_shorter_reused",
            "hindsight_action_regret": 0,
            "hindsight_distance_regret_m": 0.0,
            "memory_evidence": {
                "detector_confirmation": {
                    "mode": "multiview",
                    "candidate_reason": "detector_positive_mask",
                    "confirmed": False,
                }
            },
            "fallback_evidence": {
                "detector_confirmation": {
                    "mode": "multiview",
                    "candidate_reason": "detector_positive_mask",
                    "confirmed": True,
                }
            },
            "fallback_from_memory_evidence": {},
        },
        {
            "policy": "memory_guided",
            "success": True,
            "action_count": 15,
            "executed_distance_m": 4.0,
            "memory_reused": False,
            "selected_candidate_types": ["frontier"],
            "memory_decision_bucket": "frontier_shorter_selected",
            "hindsight_action_regret": 0,
            "hindsight_distance_regret_m": 0.0,
            "memory_evidence": {},
            "fallback_evidence": {},
            "fallback_from_memory_evidence": {
                "detector_confirmation": {
                    "mode": "multiview",
                    "candidate_reason": "detector_positive_mask",
                    "confirmed": False,
                }
            },
        },
    ]

    summary = summarize_habitat_closed_loop_rows(rows)

    assert summary["policy_summaries"]["memory_guided"][
        "detector_confirmation_counts"
    ] == {
        "confirmed": 1,
        "suppressed": 2,
    }


def test_summary_counts_runtime_detector_confirmation_events() -> None:
    rows = [
        {
            "policy": "memory_guided",
            "success": True,
            "action_count": 12,
            "executed_distance_m": 3.0,
            "memory_reused": True,
            "selected_candidate_types": ["memory"],
            "memory_decision_bucket": "memory_shorter_reused",
            "hindsight_action_regret": 0,
            "hindsight_distance_regret_m": 0.0,
            "memory_evidence": {},
            "fallback_evidence": {},
            "fallback_from_memory_evidence": {},
            "detector_confirmation_events": [
                {"context": "memory", "outcome": "suppressed"},
                {"context": "memory", "outcome": "confirmed"},
                {"context": "fallback", "outcome": "suppressed"},
            ],
        },
        {
            "policy": "memory_guided",
            "success": False,
            "action_count": 15,
            "executed_distance_m": 4.0,
            "memory_reused": False,
            "selected_candidate_types": ["memory"],
            "memory_decision_bucket": "memory_attempt_failed",
            "hindsight_action_regret": 0,
            "hindsight_distance_regret_m": 0.0,
            "memory_evidence": {},
            "fallback_evidence": {},
            "fallback_from_memory_evidence": {},
            "detector_confirmation_events": [
                {"context": "fallback_from_memory", "outcome": "suppressed"},
            ],
        },
    ]

    summary = summarize_habitat_closed_loop_rows(rows)

    policy_summary = summary["policy_summaries"]["memory_guided"]
    assert policy_summary["detector_confirmation_event_counts"] == {
        "confirmed": 1,
        "suppressed": 3,
    }
    assert policy_summary["detector_confirmation_event_counts_by_context"] == {
        "fallback": {"suppressed": 1},
        "fallback_from_memory": {"suppressed": 1},
        "memory": {"confirmed": 1, "suppressed": 1},
    }


def test_naive_count_row_reuses_accepted_memory_even_when_frontier_is_cheaper() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="g1",
            category="plant",
            policy="naive_count",
            memory_action_count=139,
            memory_executed_distance_m=22.45,
            fallback_action_count=124,
            fallback_executed_distance_m=20.22,
            fallback_from_memory_action_count=400,
            fallback_from_memory_executed_distance_m=60.0,
            matching_reason="accepted",
            memory_verified=True,
            fallback_verified=True,
            fallback_from_memory_verified=False,
            memory_decision="memory_first",
            expected_memory_first_action_count=339.0,
            expected_frontier_first_action_count=124.0,
        )
    )

    assert row["selected_candidate_types"] == ["memory"]
    assert row["memory_reused"] is True
    assert row["action_count"] == 139
    assert row["memory_decision_bucket"] == "naive_memory_reuse"


def test_memory_guided_bucket_records_memory_rescue_when_frontier_fails() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="g1",
            category="toilet",
            policy="memory_guided",
            memory_action_count=179,
            memory_executed_distance_m=26.9,
            fallback_action_count=468,
            fallback_executed_distance_m=69.4,
            fallback_from_memory_action_count=400,
            fallback_from_memory_executed_distance_m=60.0,
            matching_reason="accepted",
            memory_verified=True,
            fallback_verified=False,
            fallback_from_memory_verified=False,
            memory_decision="memory_first",
        )
    )

    assert row["selected_candidate_types"] == ["memory"]
    assert row["memory_decision_bucket"] == "memory_rescued_frontier_failure"


def test_memory_guided_failed_post_memory_repair_counts_search_cost() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="scene|sofa|relocated",
            category="sofa",
            policy="memory_guided",
            memory_action_count=49,
            memory_executed_distance_m=7.0,
            fallback_action_count=246,
            fallback_executed_distance_m=40.0,
            fallback_from_memory_action_count=100,
            fallback_from_memory_executed_distance_m=18.0,
            matching_reason="no_current_observation",
            memory_verified=False,
            fallback_verified=False,
            fallback_from_memory_verified=False,
            memory_decision="memory_first",
        )
    )

    assert row["selected_candidate_types"] == ["memory", "frontier"]
    assert row["success"] is False
    assert row["action_count"] == 149
    assert row["executed_distance_m"] == 25.0
    assert row["memory_decision_bucket"] == "memory_then_frontier_failed"


def test_memory_guided_bucket_records_valid_memory_wrongly_deferred() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="g1",
            category="chair",
            policy="memory_guided",
            memory_action_count=69,
            memory_executed_distance_m=8.0,
            fallback_action_count=115,
            fallback_executed_distance_m=16.5,
            fallback_from_memory_action_count=125,
            fallback_from_memory_executed_distance_m=18.0,
            matching_reason="accepted",
            memory_verified=True,
            fallback_verified=True,
            fallback_from_memory_verified=True,
            memory_decision="frontier_first",
        )
    )

    assert row["selected_candidate_types"] == ["frontier"]
    assert row["memory_decision_bucket"] == "valid_memory_wrongly_deferred"
    assert row["hindsight_best_candidate_type"] == "memory"
    assert row["hindsight_action_regret"] == 46
    assert row["hindsight_distance_regret_m"] == 8.5


def test_memory_guided_hindsight_best_is_frontier_when_frontier_is_shorter() -> None:
    row = make_habitat_closed_loop_option_row(
        HabitatClosedLoopOptionPlan(
            group_id="g1",
            category="plant",
            policy="memory_guided",
            memory_action_count=139,
            memory_executed_distance_m=22.45,
            fallback_action_count=125,
            fallback_executed_distance_m=19.84,
            fallback_from_memory_action_count=200,
            fallback_from_memory_executed_distance_m=30.0,
            matching_reason="accepted",
            memory_verified=True,
            fallback_verified=True,
            fallback_from_memory_verified=True,
            memory_decision="memory_first",
        )
    )

    assert row["selected_candidate_types"] == ["memory"]
    assert row["hindsight_best_candidate_type"] == "frontier"
    assert row["hindsight_action_regret"] == 14
    assert row["hindsight_distance_regret_m"] == 2.61


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


def test_expected_utility_ignores_unavailable_frontier_option() -> None:
    assert (
        closed_loop._memory_first_decision(
            memory_action_count=32,
            fallback_from_memory_action_count=2,
            fallback_action_count=0,
            memory_valid_prior=0.589418,
            fallback_available=False,
        )
        == "memory_first"
    )


def test_calibrated_memory_decision_keeps_strong_shorter_memory() -> None:
    estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="accepted",
        verification=closed_loop._OracleVisible(
            target_visible=True,
            oracle_target_pixels=411114,
        ),
        category="sofa",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )

    assert (
        closed_loop._memory_first_decision(
            memory_action_count=98,
            fallback_from_memory_action_count=87,
            fallback_action_count=102,
            memory_valid_prior=estimate.value,
        )
        == "memory_first"
    )


def test_expected_utility_ignores_unavailable_post_memory_repair() -> None:
    assert (
        closed_loop._memory_first_decision(
            memory_action_count=40,
            fallback_from_memory_action_count=0,
            fallback_action_count=120,
            memory_valid_prior=0.25,
            fallback_available=True,
            fallback_from_memory_available=False,
        )
        == "frontier_first"
    )
    assert (
        closed_loop._memory_first_decision(
            memory_action_count=40,
            fallback_from_memory_action_count=0,
            fallback_action_count=120,
            memory_valid_prior=0.25,
            fallback_available=False,
            fallback_from_memory_available=False,
        )
        == "memory_first"
    )


def test_calibrated_memory_decision_still_uses_frontier_when_frontier_is_shorter() -> None:
    estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="accepted",
        verification=closed_loop._OracleVisible(
            target_visible=True,
            oracle_target_pixels=74268,
        ),
        category="plant",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )

    assert (
        closed_loop._memory_first_decision(
            memory_action_count=139,
            fallback_from_memory_action_count=166,
            fallback_action_count=125,
            memory_valid_prior=estimate.value,
        )
        == "frontier_first"
    )


def test_evidence_reliability_boosts_strong_current_positive_memory() -> None:
    estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="accepted",
        verification=closed_loop._OracleVisible(
            target_visible=True,
            oracle_target_pixels=74268,
        ),
        category="chair",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )

    assert estimate.value > 0.85
    assert estimate.components["current_evidence"] > 0.9
    assert estimate.components["matching"] == 1.0


def test_evidence_reliability_rejects_nonpositive_or_ambiguous_memory() -> None:
    missed = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="accepted",
        verification=closed_loop._OracleVisible(target_visible=False),
        category="chair",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )
    ambiguous = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="ambiguous",
        verification=closed_loop._OracleVisible(
            target_visible=True,
            oracle_target_pixels=74268,
        ),
        category="chair",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )

    assert missed.value < 0.35
    assert ambiguous.value < 0.35
    assert ambiguous.components["matching"] < 0.5


def test_detector_reliability_uses_detector_pixels_not_oracle_pixels() -> None:
    estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="accepted",
        verification=DetectorVerification(
            target_visible=True,
            oracle_target_pixels=500_000,
            detector_pixels=30,
        ),
        category="chair",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )

    assert estimate.components["current_evidence"] == 0.72
    assert estimate.reason == "evidence_weighted"
    assert estimate.value < 0.9


def _detector_confirmation_event(
    *,
    outcome: str,
    context: str = "memory",
    detector_pixels: int = 1024,
    mask_iou: float = 0.5,
    pending_count: int = 2,
    translation_m: float = 0.1,
    rotation_deg: float = 8.0,
    overlap_pixels: int = 0,
    oracle_recall: float = 0.0,
) -> dict[str, object]:
    return {
        "outcome": outcome,
        "context": context,
        "candidate_reason": "detector_positive_mask",
        "detector_pixels": detector_pixels,
        "mask_iou": mask_iou,
        "pending_count": pending_count,
        "translation_m": translation_m,
        "rotation_deg": rotation_deg,
        "overlap_pixels": overlap_pixels,
        "oracle_recall": oracle_recall,
    }


def test_event_posterior_reliability_boosts_confirmed_memory_events() -> None:
    verification = DetectorVerification(
        target_visible=True,
        oracle_target_pixels=500_000,
        detector_pixels=1024,
    )
    evidence = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="accepted",
        verification=verification,
        category="plant",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )

    estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="event_posterior",
        matching_reason="accepted",
        verification=verification,
        category="plant",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
        detector_confirmation_events=[
            _detector_confirmation_event(outcome="confirmed", detector_pixels=2048),
            _detector_confirmation_event(outcome="confirmed", detector_pixels=4096),
        ],
        detector_confirmation_context="memory",
    )

    assert estimate.reason == "event_posterior_weighted"
    assert estimate.value > evidence.value
    assert estimate.components["detector_event_count"] == 2
    assert estimate.components["detector_event_confirmed_weight"] > 0
    assert estimate.components["detector_event_suppressed_weight"] == 0
    assert estimate.components["detector_event_posterior"] > 0.75


def test_event_posterior_reliability_reduces_suppressed_dominant_memory() -> None:
    verification = DetectorVerification(
        target_visible=True,
        oracle_target_pixels=500_000,
        detector_pixels=8192,
    )
    evidence = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="accepted",
        verification=verification,
        category="plant",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )

    estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="event_posterior",
        matching_reason="accepted",
        verification=verification,
        category="plant",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
        detector_confirmation_events=[
            _detector_confirmation_event(outcome="suppressed", detector_pixels=8192),
            _detector_confirmation_event(outcome="suppressed", detector_pixels=4096),
            _detector_confirmation_event(outcome="suppressed", detector_pixels=2048),
        ],
        detector_confirmation_context="memory",
    )

    assert evidence.reason == "strong_current_evidence_floor"
    assert estimate.value < evidence.value
    assert estimate.components["detector_event_suppressed_weight"] > (
        estimate.components["detector_event_confirmed_weight"]
    )
    assert (
        closed_loop._memory_first_decision(
            memory_action_count=100,
            fallback_from_memory_action_count=200,
            fallback_action_count=150,
            memory_valid_prior=estimate.value,
        )
        == "frontier_first"
    )


def test_learned_memory_validity_model_overrides_base_reliability() -> None:
    verification = DetectorVerification(
        target_visible=False,
        oracle_target_pixels=0,
        detector_pixels=112_000,
    )
    base_estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="event_posterior",
        matching_reason="accepted",
        verification=verification,
        category="sofa",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )

    learned_estimate = closed_loop._apply_learned_memory_validity_model(
        model={"feature_names": (), "weights": (), "bias": -10.0},
        base_estimate=base_estimate,
        memory_action_count=49,
        fallback_action_count=246,
        fallback_from_memory_action_count=211,
        memory_valid_prior=0.5,
        relocation_pair_distance_m=6.69003,
        memory_evidence=closed_loop._verification_payload(verification),
    )

    assert learned_estimate.mode == "learned_model"
    assert learned_estimate.reason == "learned_memory_validity_model"
    assert learned_estimate.value < 0.001
    assert learned_estimate.components["base_reliability_value"] == base_estimate.value
    assert learned_estimate.components["model_feature_count"] == 0
    assert (
        closed_loop._memory_first_decision(
            memory_action_count=49,
            fallback_from_memory_action_count=211,
            fallback_action_count=246,
            memory_valid_prior=learned_estimate.value,
        )
        == "frontier_first"
    )


def test_learned_memory_validity_features_use_exporter_event_names() -> None:
    estimate = closed_loop.MemoryReliabilityEstimate(
        mode="event_posterior",
        value=0.2875,
        components={
            "base_prior": 0.5,
            "current_evidence": 0.15,
            "detector_event_count": 2.0,
            "detector_event_confirmed_weight": 1.5,
            "detector_event_suppressed_weight": 3.0,
            "detector_event_posterior": 0.33,
        },
        reason="event_posterior_weighted",
    )

    features = closed_loop._learned_memory_validity_features(
        base_estimate=estimate,
        memory_action_count=49,
        fallback_action_count=246,
        fallback_from_memory_action_count=211,
        memory_valid_prior=0.5,
        relocation_pair_distance_m=None,
        memory_evidence={"detector_precision": 0.0},
    )

    assert features["memory_reliability_current_evidence"] == 0.15
    assert features["memory_detector_event_count"] == 2.0
    assert features["memory_detector_event_confirmed_weight"] == 1.5
    assert features["memory_detector_event_suppressed_weight"] == 3.0
    assert features["memory_detector_event_posterior"] == 0.33
    assert "memory_reliability_detector_event_count" not in features


def test_event_posterior_filters_events_by_active_memory_context() -> None:
    verification = DetectorVerification(
        target_visible=True,
        oracle_target_pixels=500_000,
        detector_pixels=2048,
    )

    memory_estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="event_posterior",
        matching_reason="accepted",
        verification=verification,
        category="plant",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
        detector_confirmation_events=[
            _detector_confirmation_event(outcome="suppressed", context="memory"),
            _detector_confirmation_event(
                outcome="confirmed",
                context="fallback_from_memory",
                detector_pixels=4096,
            ),
        ],
        detector_confirmation_context="memory",
    )
    repaired_estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="event_posterior",
        matching_reason="accepted",
        verification=verification,
        category="plant",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
        detector_confirmation_events=[
            _detector_confirmation_event(outcome="suppressed", context="memory"),
            _detector_confirmation_event(
                outcome="confirmed",
                context="fallback_from_memory",
                detector_pixels=4096,
            ),
        ],
        detector_confirmation_context="fallback_from_memory",
    )

    assert memory_estimate.components["detector_event_count"] == 1
    assert repaired_estimate.components["detector_event_count"] == 1
    assert repaired_estimate.value > memory_estimate.value


def test_event_posterior_ignores_oracle_audit_fields() -> None:
    verification = DetectorVerification(
        target_visible=True,
        oracle_target_pixels=500_000,
        detector_pixels=2048,
    )
    common_kwargs = {
        "base_prior": 0.5,
        "mode": "event_posterior",
        "matching_reason": "accepted",
        "verification": verification,
        "category": "plant",
        "transform": closed_loop._session_restart_transform(),
        "repeat_index": 0,
        "detector_confirmation_context": "memory",
    }

    no_overlap = closed_loop._estimate_memory_valid_prior(
        **common_kwargs,
        detector_confirmation_events=[
            _detector_confirmation_event(
                outcome="confirmed",
                overlap_pixels=0,
                oracle_recall=0.0,
            )
        ],
    )
    high_overlap = closed_loop._estimate_memory_valid_prior(
        **common_kwargs,
        detector_confirmation_events=[
            _detector_confirmation_event(
                outcome="confirmed",
                overlap_pixels=999_999,
                oracle_recall=1.0,
            )
        ],
    )

    assert high_overlap.value == no_overlap.value
    assert high_overlap.components == no_overlap.components


def test_multiview_confirmation_suppresses_single_frame_detector_positive() -> None:
    positive = DetectorVerification(
        target_visible=True,
        oracle_target_pixels=3495,
        detector_pixels=8150,
    )
    state = closed_loop.DetectorConfirmationState()
    mask = np.ones((4, 4), dtype=bool)

    confirmed = closed_loop._apply_detector_confirmation(
        verification=positive,
        state=state,
        mode="multiview",
        pose=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=mask,
        config=closed_loop.DetectorConfirmationConfig(
            frames=2,
            min_translation_m=0.05,
            min_rotation_deg=5.0,
            min_mask_iou=0.05,
        ),
    )

    assert confirmed.shared_gate_success is False
    assert confirmed.target_visible is False
    assert confirmed.evidence_reason == "pending_detector_confirmation"
    assert confirmed.detector_confirmation["candidate_reason"] == "detector_positive_mask"
    assert confirmed.detector_confirmation["pending_count"] == 1
    assert confirmed.detector_confirmation["confirmed"] is False


def test_multiview_confirmation_records_suppressed_positive_event() -> None:
    positive = DetectorVerification(
        target_visible=True,
        oracle_target_pixels=3495,
        detector_pixels=8150,
    )
    state = closed_loop.DetectorConfirmationState()
    events: list[dict[str, object]] = []

    confirmed = closed_loop._apply_detector_confirmation(
        verification=positive,
        state=state,
        mode="multiview",
        pose=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=np.ones((4, 4), dtype=bool),
        config=closed_loop.DetectorConfirmationConfig(frames=2),
        events=events,
        source="memory_candidate:0",
        context="memory",
    )

    assert confirmed.shared_gate_success is False
    assert events == [
        {
            "context": "memory",
            "source": "memory_candidate:0",
            "candidate_reason": "detector_positive_mask",
            "outcome": "suppressed",
            "pending_count": 1,
            "translation_m": 0.0,
            "rotation_deg": 0.0,
            "mask_iou": 1.0,
            "detector_pixels": 8150,
            "overlap_pixels": 0,
            "detector_precision": 0.0,
            "oracle_recall": 0.0,
        }
    ]


def test_multiview_confirmation_accepts_repeated_positive_after_view_change() -> None:
    state = closed_loop.DetectorConfirmationState()
    config = closed_loop.DetectorConfirmationConfig(
        frames=2,
        min_translation_m=0.05,
        min_rotation_deg=5.0,
        min_mask_iou=0.05,
    )
    mask = np.zeros((4, 4), dtype=bool)
    mask[1:3, 1:3] = True
    positive = DetectorVerification(
        target_visible=True,
        oracle_target_pixels=3495,
        detector_pixels=8150,
    )

    closed_loop._apply_detector_confirmation(
        verification=positive,
        state=state,
        mode="multiview",
        pose=((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=mask,
        config=config,
    )
    confirmed = closed_loop._apply_detector_confirmation(
        verification=positive,
        state=state,
        mode="multiview",
        pose=((0.1, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
        detector_mask=mask,
        config=config,
    )

    assert confirmed.shared_gate_success is True
    assert confirmed.evidence_reason == "confirmed_detector_positive_mask"
    assert confirmed.detector_confirmation["pending_count"] == 2
    assert confirmed.detector_confirmation["translation_m"] == 0.1
    assert confirmed.detector_confirmation["confirmed"] is True


def test_pending_detector_confirmation_is_weak_current_evidence() -> None:
    pending = closed_loop.DetectorConfirmedVerification(
        source=DetectorVerification(
            target_visible=True,
            oracle_target_pixels=3495,
            detector_pixels=8150,
        ),
        evidence_type_value="unknown",
        target_visible=False,
        evidence_strength=0.35,
        evidence_reason="pending_detector_confirmation",
        detector_confirmation={
            "mode": "multiview",
            "confirmed": False,
            "candidate_reason": "detector_positive_mask",
            "pending_count": 1,
        },
    )

    estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="accepted",
        verification=pending,
        category="plant",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )

    assert estimate.components["current_evidence"] < 0.5
    assert estimate.reason == "weak_current_evidence"
    assert estimate.value < 0.34


def test_confirmed_detector_reason_still_uses_detector_pixels_and_audit() -> None:
    confirmed = closed_loop.DetectorConfirmedVerification(
        source=DetectorVerification(
            target_visible=True,
            oracle_target_pixels=500_000,
            detector_pixels=30,
        ),
        evidence_type_value="positive",
        target_visible=True,
        evidence_strength=1.2,
        evidence_reason="confirmed_detector_positive_mask",
        detector_confirmation={"mode": "multiview", "confirmed": True},
    )

    estimate = closed_loop._estimate_memory_valid_prior(
        base_prior=0.5,
        mode="evidence",
        matching_reason="accepted",
        verification=confirmed,
        category="chair",
        transform=closed_loop._session_restart_transform(),
        repeat_index=0,
    )
    payload = closed_loop._audit_evidence_payload(
        closed_loop._verification_payload(confirmed)
    )

    assert estimate.components["current_evidence"] == 0.72
    assert payload["detector_false_confirmation"] is True


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


def test_replay_control_values_are_stable_for_group_not_row_order() -> None:
    group_id = (
        "hm3d/val/00813-svBbv1Pavdk/svBbv1Pavdk.basis.glb"
        "|tv_monitor|goal_object:287"
    )

    fallback_seed = closed_loop._stable_replay_seed(
        group_id=group_id,
        context="fallback",
    )
    fallback_seed_again = closed_loop._stable_replay_seed(
        group_id=group_id,
        context="fallback",
    )
    repair_seed = closed_loop._stable_replay_seed(
        group_id=group_id,
        context="fallback_from_memory",
    )
    other_group_seed = closed_loop._stable_replay_seed(
        group_id=(
            "hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb"
            "|sofa|goal_object:275"
        ),
        context="fallback",
    )

    assert fallback_seed == fallback_seed_again
    assert fallback_seed != repair_seed
    assert fallback_seed != other_group_seed
    assert (
        closed_loop._stable_replay_frame_index_base(group_id=group_id)
        == closed_loop._stable_replay_frame_index_base(group_id=group_id)
    )
    assert closed_loop._stable_replay_frame_index_base(group_id=group_id) % 100 == 0


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


def test_memory_local_probe_goals_expand_around_memory_anchor() -> None:
    class PathFinder:
        def snap_point(self, point):
            return point

        def is_navigable(self, point) -> bool:
            return True

    class Sim:
        pathfinder = PathFinder()

    goals = closed_loop._memory_local_probe_goals(
        sim=Sim(),
        memory_anchor=(10.0, 0.0, 20.0),
        start=(10.0, 0.0, 20.0),
        seed=313,
        radii_m=(1.0, 2.0),
        probe_count=4,
        angle_count=4,
        score_mode="distance_prior",
        min_separation_m=0.1,
    )

    assert [goal.position for goal in goals] == [
        (11.0, 0.0, 20.0),
        (10.0, 0.0, 21.0),
        (9.0, 0.0, 20.0),
        (10.0, 0.0, 19.0),
    ]
    assert [goal.source for goal in goals] == [
        "memory_local_active_probe:0",
        "memory_local_active_probe:1",
        "memory_local_active_probe:2",
        "memory_local_active_probe:3",
    ]


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


def test_probe_route_uses_custom_source_prefix() -> None:
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
        return closed_loop._OracleVisible(target_visible=True)

    result = closed_loop._run_navmesh_frontier_probe_route(
        start_position=(0.0, 0.0, 0.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        probe_goals=((1.0, 0.0, 0.0),),
        route_segment=route_segment,
        verify_probe=verify_probe,
        probe_heading_count=1,
        source_prefix="memory_local_active_probe",
    )

    assert visited_sources == ["memory_local_active_probe:0:heading:0"]
    assert result.selected_probe_source == "memory_local_active_probe:0:heading:0"


def test_memory_local_active_result_stops_at_first_positive_probe() -> None:
    from types import SimpleNamespace

    class PathFinder:
        def snap_point(self, point):
            return point

        def is_navigable(self, point) -> bool:
            return True

    class Sim:
        pathfinder = PathFinder()

    visited_sources: list[str] = []

    def route_segment(*, start_position, start_rotation, goal_position):
        del start_position, start_rotation
        return SimpleNamespace(
            actions=(f"move_to_{goal_position[0]}_{goal_position[2]}",),
            action_count=1,
            reached_stop=True,
            final_position=goal_position,
            final_rotation=(0.0, 0.0, 0.0, 1.0),
            executed_distance_m=1.0,
        )

    def verify_probe(*, source, position, rotation, probe_index):
        del position, rotation, probe_index
        visited_sources.append(source)
        return closed_loop._OracleVisible(
            target_visible=source == "memory_local_active_probe:1:heading:0"
        )

    result = closed_loop._memory_local_active_result(
        sim=Sim(),
        start_position=(10.0, 0.0, 20.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        memory_anchor=(10.0, 0.0, 20.0),
        seed=313,
        radii_m=(1.0,),
        probe_count=2,
        angle_count=4,
        score_mode="distance_prior",
        route_segment=route_segment,
        verify_probe=verify_probe,
        probe_heading_count=1,
    )

    assert visited_sources == [
        "memory_local_active_probe:0:heading:0",
        "memory_local_active_probe:1:heading:0",
    ]
    assert result.selected_probe_source == "memory_local_active_probe:1:heading:0"
    assert result.selected_probe_position == (10.0, 0.0, 21.0)
    assert result.selected_verification.shared_gate_success is True
    assert result.route.action_count == 2


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


def test_per_action_route_observation_truncates_at_first_positive_step() -> None:
    from types import SimpleNamespace

    route = SimpleNamespace(
        actions=("move_forward", "turn_left", "move_forward"),
        action_count=3,
        reached_stop=True,
        final_position=(3.0, 0.0, 0.0),
        final_rotation=(0.0, 0.0, 0.0, 1.0),
        executed_distance_m=3.0,
        observations=(
            SimpleNamespace(
                action_index=0,
                action="move_forward",
                position=(1.0, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0, 1.0),
                cumulative_distance_m=1.0,
            ),
            SimpleNamespace(
                action_index=1,
                action="turn_left",
                position=(2.0, 0.0, 0.0),
                rotation=(0.0, 0.1, 0.0, 0.99),
                cumulative_distance_m=2.0,
            ),
            SimpleNamespace(
                action_index=2,
                action="move_forward",
                position=(3.0, 0.0, 0.0),
                rotation=(0.0, 0.1, 0.0, 0.99),
                cumulative_distance_m=3.0,
            ),
        ),
    )
    visited_sources: list[str] = []

    def verify_observation(*, source, position, rotation, step_index, action):
        del position, rotation, action
        visited_sources.append(source)
        return closed_loop._OracleVisible(target_visible=step_index == 1)

    result = closed_loop._observe_route_until_positive(
        route=route,
        route_source="memory",
        mode="per_action",
        verify_observation=verify_observation,
    )

    assert visited_sources == ["memory:step:0", "memory:step:1"]
    assert result.selected_source == "memory:step:1"
    assert result.selected_step_index == 1
    assert result.observation_count == 2
    assert result.selected_verification.shared_gate_success is True
    assert result.route.actions == ("move_forward", "turn_left")
    assert result.route.action_count == 2
    assert result.route.executed_distance_m == 2.0
    assert result.route.final_position == (2.0, 0.0, 0.0)


def test_route_observation_result_exposes_row_payload() -> None:
    result = closed_loop.RouteObservationResult(
        route=object(),
        selected_source="memory:step:2",
        selected_verification=closed_loop._OracleVisible(target_visible=True),
        selected_step_index=2,
        observation_count=3,
    )

    assert closed_loop._route_observation_result_payload(result) == {
        "source": "memory:step:2",
        "step_index": 2,
        "observation_count": 3,
    }


def test_navmesh_route_result_exposes_route_observation_result() -> None:
    route = object()
    verification = closed_loop._OracleVisible(target_visible=True)
    result = closed_loop.NavmeshFrontierRouteResult(
        route=route,
        selected_probe_source="navmesh_frontier_probe:3:step:6",
        selected_probe_position=(1.0, 0.0, 2.0),
        selected_verification=verification,
        verification_count=9,
    )

    observation = closed_loop._route_observation_from_navmesh_result(result)

    assert observation.route is route
    assert observation.selected_source == "navmesh_frontier_probe:3:step:6"
    assert observation.selected_verification is verification
    assert observation.selected_step_index == 6
    assert observation.observation_count == 9


def test_stale_proxy_initial_memory_route_is_not_truncated_by_per_action_positive() -> None:
    from types import SimpleNamespace

    route = SimpleNamespace(
        actions=("move_forward", "turn_left", "move_forward"),
        action_count=3,
        reached_stop=True,
        final_position=(3.0, 0.0, 0.0),
        final_rotation=(0.0, 0.0, 0.0, 1.0),
        executed_distance_m=3.0,
        observations=(
            SimpleNamespace(
                action_index=0,
                action="move_forward",
                position=(1.0, 0.0, 0.0),
                rotation=(0.0, 0.0, 0.0, 1.0),
                cumulative_distance_m=1.0,
            ),
        ),
    )
    verification_calls: list[str] = []

    def verify_observation(*, source, position, rotation, step_index, action):
        del position, rotation, step_index, action
        verification_calls.append(source)
        return closed_loop._OracleVisible(target_visible=True)

    result = closed_loop._observe_initial_memory_route(
        route=route,
        route_source="memory_candidate:route",
        challenge="stale_proxy",
        mode="per_action",
        initial_memory_verification=closed_loop._OracleVisible(
            target_visible=True,
            oracle_target_pixels=128,
        ),
        verify_observation=verify_observation,
    )

    assert verification_calls == []
    assert result.route is route
    assert result.route.action_count == 3
    assert result.route.executed_distance_m == 3.0
    assert result.selected_source == "memory_candidate:route:stale_proxy_absent"
    assert result.selected_verification.shared_gate_success is False
    assert result.observation_count == 0


def test_navmesh_frontier_route_checks_per_action_observations_before_probe_heading() -> None:
    from types import SimpleNamespace

    visited_sources: list[str] = []

    def route_segment(*, start_position, start_rotation, goal_position):
        del start_position, start_rotation
        return SimpleNamespace(
            actions=("move_forward", "move_forward", "move_forward"),
            reached_stop=True,
            final_position=goal_position,
            final_rotation=(0.0, 0.0, 0.0, 1.0),
            executed_distance_m=3.0,
            observations=(
                SimpleNamespace(
                    action_index=0,
                    action="move_forward",
                    position=(1.0, 0.0, 0.0),
                    rotation=(0.0, 0.0, 0.0, 1.0),
                    cumulative_distance_m=1.0,
                ),
                SimpleNamespace(
                    action_index=1,
                    action="move_forward",
                    position=(2.0, 0.0, 0.0),
                    rotation=(0.0, 0.0, 0.0, 1.0),
                    cumulative_distance_m=2.0,
                ),
            ),
        )

    def verify_probe(*, source, position, rotation, probe_index):
        del position, rotation, probe_index
        visited_sources.append(source)
        return closed_loop._OracleVisible(
            target_visible=source == "navmesh_frontier_probe:0:step:1"
        )

    result = closed_loop._run_navmesh_frontier_probe_route(
        start_position=(0.0, 0.0, 0.0),
        start_rotation=(0.0, 0.0, 0.0, 1.0),
        probe_goals=((3.0, 0.0, 0.0),),
        route_segment=route_segment,
        verify_probe=verify_probe,
        route_observation_mode="per_action",
    )

    assert visited_sources == [
        "navmesh_frontier_probe:0:step:0",
        "navmesh_frontier_probe:0:step:1",
    ]
    assert result.selected_probe_source == "navmesh_frontier_probe:0:step:1"
    assert result.route.actions == ("move_forward", "move_forward")
    assert result.route.action_count == 2
    assert result.route.executed_distance_m == 2.0


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
