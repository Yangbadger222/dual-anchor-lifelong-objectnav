from __future__ import annotations

import json
import random
from types import SimpleNamespace

import numpy as np
import pytest

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    OFFICIAL_OBJECTNAV_MEASURE_KEYS,
    OCCUPANCY_FREE,
    OCCUPANCY_OCCUPIED,
    OCCUPANCY_UNKNOWN,
    OfficialMemoryAnchor,
    OfficialObjectNavRunConfig,
    OfficialPathfinderSuffixController,
    OfficialPolicyState,
    SUPPORTED_OFFICIAL_POLICIES,
    create_occupancy_frontier_map,
    load_official_memory_prior,
    load_official_memory_prior_from_payload,
    make_protocol_manifest,
    occupancy_frontier_counts,
    run_habitat_official_objectnav_eval,
    run_habitat_official_objectnav_preflight,
    run_official_objectnav_episode_loop,
    select_official_memory_anchor,
    summarize_official_objectnav_metrics,
    update_occupancy_frontier_map,
    _episode_goal_positions,
    _follower_action_name,
    _memory_anchor_oracle_goal_position,
    _select_memory_active_perception_frontier,
    _select_memory_active_perception_frontier_fallback,
    _select_memory_belief_frontier,
    _select_targetnav_fmm_action,
    _select_targetnav_occupancy_action,
    _smooth_targetnav_goal,
    _targetnav_pointgoal_with_gps_compass,
    _targetnav_goal_from_detector_match,
)
from objectnav_core.navigation import HabitatOracleFollowerBackend
from objectnav_core.perception.yolo_world_adapter import Detection


def test_summarize_official_objectnav_metrics_uses_habitat_metric_keys() -> None:
    rows = [
        {
            "episode_id": "0",
            "habitat_official": {
                "success": 1.0,
                "spl": 0.5,
                "soft_spl": 0.7,
                "distance_to_goal": 0.0,
            },
            "policy_debug": {"success": 99.0},
        },
        {
            "episode_id": "1",
            "habitat_official": {
                "success": 0.0,
                "spl": 0.0,
                "soft_spl": 0.2,
                "distance_to_goal": 2.0,
            },
            "policy_debug": {"success": 99.0},
        },
    ]

    summary = summarize_official_objectnav_metrics(rows)

    assert summary["episodes"] == 2
    assert summary["measure_source"] == "habitat.Env.get_metrics"
    assert summary["success_rate"] == 0.5
    assert summary["spl"] == 0.25
    assert summary["soft_spl"] == pytest.approx(0.45)
    assert summary["distance_to_goal"] == 1.0
    assert summary["required_measures_present"] is True


def test_make_protocol_manifest_records_official_boundary() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
        dataset_data_path="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="noop",
        max_episodes=1,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert manifest["metric_source"] == "habitat.Env.get_metrics"
    assert manifest["official_measure_keys"] == list(OFFICIAL_OBJECTNAV_MEASURE_KEYS)
    assert manifest["policy"] == "noop"
    assert manifest["habitat"]["version"] == "0.3.3"
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "preflight_or_trivial_policy_only"
    )


def test_make_protocol_manifest_records_frontier_baseline_boundary() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="frontier_only",
        max_episodes=3,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert "frontier_only" in SUPPORTED_OFFICIAL_POLICIES
    assert manifest["policy"] == "frontier_only"
    assert manifest["policy_kind"] == "target_agnostic_depth_frontier_baseline"
    assert manifest["invalid_for_benchmark_claim_reason"] is None


def test_make_protocol_manifest_records_occupancy_frontier_boundary() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="occupancy_frontier",
        max_episodes=3,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert "occupancy_frontier" in SUPPORTED_OFFICIAL_POLICIES
    assert manifest["policy_kind"] == "target_agnostic_occupancy_frontier_baseline"
    assert manifest["invalid_for_benchmark_claim_reason"] is None


def test_candidate_viewpoint_ranker_model_loader_validates_task(tmp_path) -> None:
    from objectnav_core.evaluation.habitat_official_objectnav_eval import (
        load_official_candidate_viewpoint_ranker_model,
    )

    model_path = tmp_path / "ranker.json"
    model_path.write_text(
        json.dumps(
            {
                "task": "habitat_official_candidate_viewpoint_ranker_model",
                "feature_names": ["candidate_rank"],
                "weights": [1.0],
                "bias": 0.0,
                "preprocessing": {
                    "feature_means": {"candidate_rank": 0.0},
                    "feature_scales": {"candidate_rank": 1.0},
                },
            }
        ),
        encoding="utf-8",
    )
    wrong_path = tmp_path / "wrong.json"
    wrong_path.write_text(
        json.dumps({"task": "habitat_official_local_action_logistic_model"}),
        encoding="utf-8",
    )

    model = load_official_candidate_viewpoint_ranker_model(model_path)

    assert model["feature_names"] == ["candidate_rank"]
    with pytest.raises(ValueError, match="candidate viewpoint ranker"):
        load_official_candidate_viewpoint_ranker_model(wrong_path)


def test_make_protocol_manifest_records_memory_prior_boundary(tmp_path) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_guided_frontier",
        max_episodes=3,
        memory_prior_path=str(memory_path),
        memory_stop_radius_m=0.35,
        memory_bearing_tolerance_deg=20.0,
        memory_min_confidence=0.5,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert "memory_guided_frontier" in SUPPORTED_OFFICIAL_POLICIES
    assert manifest["policy_kind"] == "memory_guided_occupancy_frontier"
    assert manifest["memory_prior"]["path"] == str(memory_path)
    assert manifest["memory_prior"]["anchor_count"] == 0
    assert manifest["memory_prior"]["stop_radius_m"] == 0.35
    assert manifest["memory_prior"]["bearing_tolerance_deg"] == 20.0
    assert manifest["memory_prior"]["min_confidence"] == 0.5
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "memory_prior_source_not_benchmark_validated"
    )


def test_memory_belief_frontier_policy_is_registered_with_memory_boundary(tmp_path) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_belief_frontier",
        max_episodes=3,
        memory_prior_path=str(memory_path),
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})
    summary = run_habitat_official_objectnav_preflight(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_belief_frontier",
        max_episodes=1,
        memory_prior_path=memory_path,
        validate_habitat=False,
    )

    assert "memory_belief_frontier" in SUPPORTED_OFFICIAL_POLICIES
    assert manifest["policy_kind"] == "memory_belief_frontier_active_search"
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "memory_prior_source_not_benchmark_validated"
    )
    assert summary["policy"] == "memory_belief_frontier"


def test_memory_evidence_frontier_policy_is_registered_with_memory_boundary(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_evidence_frontier",
        max_episodes=3,
        memory_prior_path=str(memory_path),
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})
    summary = run_habitat_official_objectnav_preflight(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_evidence_frontier",
        max_episodes=1,
        memory_prior_path=memory_path,
        validate_habitat=False,
    )

    assert "memory_evidence_frontier" in SUPPORTED_OFFICIAL_POLICIES
    assert manifest["policy_kind"] == "memory_evidence_frontier_active_search"
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "memory_prior_source_not_benchmark_validated"
    )
    assert summary["policy"] == "memory_evidence_frontier"


def test_memory_active_perception_frontier_policy_is_registered_with_memory_boundary(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    summary = run_habitat_official_objectnav_preflight(
        tmp_path / "preflight",
        config_path="third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
        dataset_data_path="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        policy="memory_active_perception_frontier",
        memory_prior_path=memory_path,
        max_episodes=2,
    )
    manifest = summary["protocol_manifest"]

    assert "memory_active_perception_frontier" in SUPPORTED_OFFICIAL_POLICIES
    assert manifest["policy_kind"] == (
        "memory_active_perception_frontier_active_search"
    )
    assert manifest["memory_prior"]["path"] == str(memory_path)
    assert summary["policy"] == "memory_active_perception_frontier"


def test_memory_active_perception_pathfinder_suffix_policy_is_diagnostic() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_active_perception_frontier_pathfinder_suffix",
        max_episodes=3,
        pathfinder_suffix_goal_radius_m=1.0,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert "memory_active_perception_frontier_pathfinder_suffix" in (
        SUPPORTED_OFFICIAL_POLICIES
    )
    assert manifest["policy_kind"] == (
        "memory_active_perception_frontier_pathfinder_suffix_diagnostic"
    )
    assert manifest["pathfinder_suffix"] == {
        "enabled": True,
        "goal_radius_m": 1.0,
        "source_validity": "oracle_diagnostic_only",
    }
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "pathfinder_suffix_oracle_diagnostic"
    )


def test_memory_active_perception_targetnav_policy_records_interface_boundary() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_active_perception_frontier_targetnav",
        max_episodes=3,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert "memory_active_perception_frontier_targetnav" in SUPPORTED_OFFICIAL_POLICIES
    assert manifest["policy_kind"] == "memory_active_perception_frontier_targetnav"
    assert manifest["targetnav"] == {
        "enabled": True,
        "target_estimator": "bbox_depth",
        "backend": "occupancy_grid",
        "source_validity": "sensor_depth_local_planner",
    }
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "memory_prior_source_not_benchmark_validated"
    )


def test_memory_active_perception_targetnav_policy_records_oracle_backend_selector() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_active_perception_frontier_targetnav",
        targetnav_backend="oracle_follower",
        max_episodes=3,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert manifest["policy_kind"] == "memory_active_perception_frontier_targetnav"
    assert manifest["targetnav"] == {
        "enabled": True,
        "target_estimator": "bbox_depth",
        "backend": "oracle_follower",
        "source_validity": "oracle_diagnostic_only",
    }
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "targetnav_oracle_backend_diagnostic"
    )


def test_memory_active_perception_targetnav_policy_records_fmm_backend_selector() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_active_perception_frontier_targetnav",
        targetnav_backend="fmm_grid",
        max_episodes=3,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert manifest["policy_kind"] == "memory_active_perception_frontier_targetnav"
    assert manifest["targetnav"] == {
        "enabled": True,
        "target_estimator": "bbox_depth",
        "backend": "fmm_grid",
        "source_validity": "sensor_depth_local_planner",
    }
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "memory_prior_source_not_benchmark_validated"
    )


def test_memory_active_perception_targetnav_policy_records_ddppo_backend_selector() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_active_perception_frontier_targetnav",
        targetnav_backend="ddppo_pointnav",
        targetnav_ddppo_checkpoint_path="models/habitat/ddppo/hm3d-depth/ckpt.60.pth",
        targetnav_ddppo_device="cuda",
        max_episodes=3,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert manifest["policy_kind"] == "memory_active_perception_frontier_targetnav"
    assert manifest["targetnav"] == {
        "enabled": True,
        "target_estimator": "bbox_depth",
        "backend": "ddppo_pointnav",
        "checkpoint_path": "models/habitat/ddppo/hm3d-depth/ckpt.60.pth",
        "device": "cuda",
        "source_validity": "sensor_depth_learned_pointnav_policy",
    }
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "memory_prior_source_not_benchmark_validated"
    )


def test_memory_active_perception_targetnav_fmm_policy_records_backend_boundary() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_active_perception_frontier_targetnav_fmm",
        max_episodes=3,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert "memory_active_perception_frontier_targetnav_fmm" in (
        SUPPORTED_OFFICIAL_POLICIES
    )
    assert manifest["policy_kind"] == "memory_active_perception_frontier_targetnav_fmm"
    assert manifest["targetnav"] == {
        "enabled": True,
        "target_estimator": "bbox_depth",
        "backend": "fmm_grid",
        "source_validity": "sensor_depth_local_planner",
    }
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "memory_prior_source_not_benchmark_validated"
    )


def test_memory_active_perception_targetnav_ddppo_policy_records_backend_boundary() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_active_perception_frontier_targetnav_ddppo",
        max_episodes=3,
        targetnav_ddppo_checkpoint_path="models/habitat/ddppo/hm3d-depth/ckpt.60.pth",
        targetnav_ddppo_device="cuda",
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert "memory_active_perception_frontier_targetnav_ddppo" in (
        SUPPORTED_OFFICIAL_POLICIES
    )
    assert manifest["policy_kind"] == "memory_active_perception_frontier_targetnav_ddppo"
    assert manifest["targetnav"] == {
        "enabled": True,
        "target_estimator": "bbox_depth",
        "backend": "ddppo_pointnav",
        "checkpoint_path": "models/habitat/ddppo/hm3d-depth/ckpt.60.pth",
        "device": "cuda",
        "source_validity": "sensor_depth_learned_pointnav_policy",
    }
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "memory_prior_source_not_benchmark_validated"
    )


def test_targetnav_ddppo_policy_requires_explicit_checkpoint_path(tmp_path) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="targetnav DDPPO checkpoint"):
        run_habitat_official_objectnav_preflight(
            tmp_path / "out",
            config_path="official.yaml",
            dataset_data_path="val_mini.json.gz",
            scene_root="datasets/habitat/scene_datasets/hm3d",
            policy="memory_active_perception_frontier_targetnav_ddppo",
            memory_prior_path=memory_path,
            validate_habitat=False,
        )


def test_memory_learned_local_frontier_policy_records_model_boundary(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")
    model_path = _write_local_action_model(tmp_path / "local_model.json")

    summary = run_habitat_official_objectnav_preflight(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_learned_local_frontier",
        max_episodes=1,
        validate_habitat=False,
        memory_prior_path=memory_path,
        local_action_model_path=model_path,
    )

    manifest = json.loads(
        (tmp_path / "out" / "protocol_manifest.json").read_text(encoding="utf-8")
    )

    assert "memory_learned_local_frontier" in SUPPORTED_OFFICIAL_POLICIES
    assert summary["policy"] == "memory_learned_local_frontier"
    assert manifest["policy_kind"] == "memory_learned_local_frontier_active_search"
    assert manifest["local_action_model"]["path"] == str(model_path)
    assert manifest["local_action_model"]["task"] == (
        "habitat_official_local_action_logistic_model"
    )
    assert manifest["local_action_model"]["label_name"] == "next_target_visible"

    with pytest.raises(ValueError, match="requires local_action_model_path"):
        run_habitat_official_objectnav_preflight(
            tmp_path / "missing_model",
            config_path="official.yaml",
            dataset_data_path="val_mini.json.gz",
            scene_root="datasets/habitat/scene_datasets/hm3d",
            split="val_mini",
            policy="memory_learned_local_frontier",
            max_episodes=1,
            validate_habitat=False,
            memory_prior_path=memory_path,
        )


def test_memory_prior_parser_loads_anchor_records(tmp_path) -> None:
    path = tmp_path / "memory_prior.json"
    path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "scene-a",
                        "x_m": 1.25,
                        "z_m": -0.5,
                        "confidence": 0.8,
                        "source": "detector_positive:previous_session",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    anchors = load_official_memory_prior(path)

    assert len(anchors) == 1
    assert anchors[0].object_category == "chair"
    assert anchors[0].scene_id == "scene-a"
    assert anchors[0].x_m == 1.25
    assert anchors[0].z_m == -0.5
    assert anchors[0].confidence == 0.8
    assert anchors[0].source == "detector_positive:previous_session"
    assert anchors[0].coordinate_frame == "episode_start_relative"


def test_memory_prior_parser_rejects_malformed_records(tmp_path) -> None:
    path = tmp_path / "memory_prior.json"
    path.write_text(
        json.dumps({"anchors": [{"object_category": "chair", "x_m": 1.0}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="z_m"):
        load_official_memory_prior(path)


def test_select_official_memory_anchor_matches_category_scene_and_confidence() -> None:
    path_payload = {
        "anchors": [
            {
                "object_category": "chair",
                "scene_id": "scene-a",
                "x_m": 1.0,
                "z_m": 0.0,
                "confidence": 0.4,
                "source": "low",
            },
            {
                "object_category": "chair",
                "scene_id": "scene-a",
                "x_m": 2.0,
                "z_m": 0.0,
                "confidence": 0.9,
                "source": "high",
            },
            {
                "object_category": "chair",
                "scene_id": "scene-b",
                "x_m": 3.0,
                "z_m": 0.0,
                "confidence": 0.95,
                "source": "wrong-scene",
            },
        ]
    }
    anchors = [
        anchor
        for anchor in load_official_memory_prior_from_payload(path_payload)
    ]

    selected = select_official_memory_anchor(
        anchors,
        object_category="chair",
        scene_id="scene-a",
        min_confidence=0.5,
    )

    assert selected is not None
    assert selected.source == "high"


def test_select_official_memory_anchor_matches_compact_scene_key() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "00802-wcojb4TFT35",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "compact-scene",
                }
            ]
        }
    )

    selected = select_official_memory_anchor(
        anchors,
        object_category="chair",
        scene_id="datasets/habitat/scene_datasets/hm3d/val/00802-wcojb4TFT35/wcojb4TFT35.basis.glb",
    )

    assert selected is not None
    assert selected.source == "compact-scene"


def test_select_official_memory_anchor_rejects_unsupported_coordinate_frame() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "scene-a",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "world-frame",
                    "coordinate_frame": "habitat_world",
                }
            ]
        }
    )

    selected = select_official_memory_anchor(
        anchors,
        object_category="chair",
        scene_id="scene-a",
    )

    assert selected is None


def test_select_official_memory_anchor_prefers_exact_episode_anchor() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "scene-a",
                    "x_m": 10.0,
                    "z_m": 0.0,
                    "confidence": 1.0,
                    "source": "generic",
                },
                {
                    "object_category": "chair",
                    "scene_id": "scene-a",
                    "episode_id": "episode-2",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.8,
                    "source": "oracle-specific",
                },
                {
                    "object_category": "chair",
                    "scene_id": "scene-a",
                    "episode_id": "episode-1",
                    "x_m": -2.0,
                    "z_m": 0.0,
                    "confidence": 0.99,
                    "source": "wrong-episode",
                },
            ]
        }
    )

    selected = select_official_memory_anchor(
        anchors,
        object_category="chair",
        scene_id="scene-a",
        episode_id="episode-2",
    )

    assert selected is not None
    assert selected.source == "oracle-specific"


def test_protocol_manifest_marks_oracle_memory_prior_diagnostic(tmp_path) -> None:
    memory_path = tmp_path / "oracle_memory_prior.json"
    memory_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "scene-a",
                        "episode_id": "episode-1",
                        "x_m": 1.0,
                        "z_m": 2.0,
                        "confidence": 1.0,
                        "source": "habitat_oracle_goal:episode-1",
                    }
                ],
                "metadata": {
                    "source": "habitat_official_oracle_memory_prior",
                    "source_validity": "oracle_diagnostic_only",
                },
            }
        ),
        encoding="utf-8",
    )
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_active_perception_frontier_targetnav",
        targetnav_backend="fmm_grid",
        max_episodes=3,
        memory_prior_path=str(memory_path),
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert manifest["memory_prior"]["metadata_source"] == (
        "habitat_official_oracle_memory_prior"
    )
    assert manifest["memory_prior"]["source_validity"] == "oracle_diagnostic_only"
    assert manifest["invalid_for_benchmark_claim_reason"] == (
        "oracle_memory_prior_diagnostic"
    )


def test_official_objectnav_preflight_writes_manifest_and_summary(tmp_path) -> None:
    summary = run_habitat_official_objectnav_preflight(
        tmp_path,
        config_path="third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
        dataset_data_path="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="noop",
        max_episodes=1,
        validate_habitat=False,
    )

    manifest = json.loads(
        (tmp_path / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    saved_summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert summary == saved_summary
    assert summary["task"] == "habitat_official_objectnav_preflight"
    assert summary["full_habitat_run"] is False
    assert summary["official_metrics"] is None
    assert summary["artifact_files"]["protocol_manifest"] == "protocol_manifest.json"
    assert manifest["split"] == "val_mini"
    assert manifest["official_measure_keys"] == list(OFFICIAL_OBJECTNAV_MEASURE_KEYS)


def test_official_objectnav_preflight_validates_memory_prior(tmp_path) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(json.dumps({"anchors": []}), encoding="utf-8")

    summary = run_habitat_official_objectnav_preflight(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_guided_frontier",
        max_episodes=1,
        memory_prior_path=str(memory_path),
        memory_min_confidence=0.5,
        validate_habitat=False,
    )

    manifest = summary["protocol_manifest"]

    assert summary["official_metrics"] is None
    assert manifest["memory_prior"]["path"] == str(memory_path)
    assert manifest["memory_prior"]["anchor_count"] == 0


def test_official_eval_writes_detector_trace_artifact(tmp_path) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "depth-scene",
                        "x_m": 2.0,
                        "z_m": 0.0,
                        "confidence": 0.9,
                        "source": "east-memory",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )

    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                    "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                }
            ]
        )

    summary = run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=5,
        validate_habitat=False,
        memory_prior_path=memory_path,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        env_factory=env_factory,
    )

    trace_path = tmp_path / "out" / "detector_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    assert summary["artifact_files"]["detector_trace"] == "detector_trace.json"
    assert summary["detector_trace"]["call_count"] == 1
    assert summary["detector_trace"]["target_match_call_count"] == 1
    assert summary["detector_trace"]["target_match_detection_count"] == 1
    assert trace["call_count"] == 1
    assert trace["calls"][0]["episode_id"] == "depth-episode"
    assert trace["calls"][0]["target_category"] == "chair"
    assert trace["calls"][0]["detection_count"] == 1
    assert trace["calls"][0]["target_match_count"] == 1
    assert trace["calls"][0]["detections"][0]["matches_target"] is True
    assert trace["calls"][0]["detections"][0]["bbox"] == [1, 1, 3, 3]


def test_official_eval_detector_trace_records_nonmatching_detections(tmp_path) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "depth-scene",
                        "x_m": 2.0,
                        "z_m": 0.0,
                        "confidence": 0.9,
                        "source": "east-memory",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    detector = _StaticDetector(
        [
            Detection(
                category="sofa",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            ),
            Detection(
                category="chair",
                bbox=(0, 0, 2, 2),
                confidence=0.2,
                mask=np.ones((4, 4), dtype=bool),
            ),
        ]
    )

    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                    "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                },
                {
                    "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                    "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                },
            ]
        )

    summary = run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=2,
        validate_habitat=False,
        memory_prior_path=memory_path,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        env_factory=env_factory,
    )

    trace = json.loads(
        (tmp_path / "out" / "detector_trace.json").read_text(encoding="utf-8")
    )

    assert summary["detector_trace"]["call_count"] == 1
    assert summary["detector_trace"]["detection_count"] == 2
    assert summary["detector_trace"]["target_match_call_count"] == 0
    assert summary["detector_trace"]["target_match_detection_count"] == 0
    assert trace["calls"][0]["detection_count"] == 2
    assert [detection["category"] for detection in trace["calls"][0]["detections"]] == [
        "sofa",
        "chair",
    ]
    assert [
        detection["matches_target"] for detection in trace["calls"][0]["detections"]
    ] == [False, False]


def test_official_eval_skips_detector_trace_without_detector(tmp_path) -> None:
    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                }
            ]
        )

    summary = run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="occupancy_frontier",
        max_episodes=1,
        max_steps=1,
        validate_habitat=False,
        env_factory=env_factory,
    )

    assert "detector_trace" not in summary
    assert "detector_trace" not in summary["artifact_files"]
    assert not (tmp_path / "out" / "detector_trace.json").exists()


def test_official_eval_writes_policy_step_trace_artifact(tmp_path) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "depth-scene",
                        "x_m": 2.0,
                        "z_m": 0.0,
                        "confidence": 0.9,
                        "source": "east-memory",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )

    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                    "depth": [[[0.9], [0.9], [0.9], [0.9]]] * 4,
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                }
            ]
        )

    summary = run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_belief_frontier",
        max_episodes=1,
        max_steps=2,
        validate_habitat=False,
        memory_prior_path=memory_path,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        env_factory=env_factory,
    )

    trace_path = tmp_path / "out" / "policy_trace.json"
    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    assert summary["artifact_files"]["policy_trace"] == "policy_trace.json"
    assert summary["policy_trace"]["step_count"] == 2
    assert summary["policy_trace"]["action_counts"] == {
        "move_forward": 1,
        "stop": 1,
    }
    assert trace["step_count"] == 2
    assert trace["steps"][0]["action"] == "move_forward"
    assert trace["steps"][0]["memory_prior"]["decision"] == (
        "approach_detector_target"
    )
    assert trace["steps"][0]["x_m"] == pytest.approx(0.0)
    assert trace["steps"][0]["z_m"] == pytest.approx(0.0)
    assert trace["steps"][1]["action"] == "stop"
    assert trace["steps"][1]["memory_prior"]["decision"] == "budget_stop"


def test_official_eval_skips_policy_step_trace_when_disabled(tmp_path) -> None:
    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                }
            ]
        )

    summary = run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="occupancy_frontier",
        max_episodes=1,
        max_steps=1,
        validate_habitat=False,
        env_factory=env_factory,
        write_policy_trace=False,
    )

    assert "policy_trace" not in summary
    assert "policy_trace" not in summary["artifact_files"]
    assert not (tmp_path / "out" / "policy_trace.json").exists()


def test_episode_loop_reads_official_metrics_from_env_get_metrics() -> None:
    env = _FakeOfficialObjectNavEnv(
        [
            {"success": 1.0, "spl": 0.4, "soft_spl": 0.8, "distance_to_goal": 0.0},
            {"success": 0.0, "spl": 0.0, "soft_spl": 0.1, "distance_to_goal": 3.0},
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="noop",
        max_episodes=2,
        max_steps=5,
    )

    assert [row["episode_id"] for row in rows] == ["episode-0", "episode-1"]
    assert rows[0]["habitat_official"]["success"] == 1.0
    assert rows[1]["habitat_official"]["distance_to_goal"] == 3.0
    assert rows[0]["policy_debug"]["actions"] == ["stop"]
    assert env.get_metrics_calls == 2


def test_frontier_only_moves_forward_when_center_depth_is_clear() -> None:
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {"depth": [[2.0, 2.0, 2.0], [2.0, 2.0, 2.0], [2.0, 2.0, 2.0]]},
            {"depth": [[2.0, 2.0, 2.0], [2.0, 2.0, 2.0], [2.0, 2.0, 2.0]]},
            {"depth": [[2.0, 2.0, 2.0], [2.0, 2.0, 2.0], [2.0, 2.0, 2.0]]},
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="frontier_only",
        max_episodes=1,
        max_steps=3,
    )

    assert env.actions == ["move_forward", "move_forward", "stop"]
    assert rows[0]["policy_debug"]["policy_kind"] == (
        "target_agnostic_depth_frontier_baseline"
    )
    assert rows[0]["policy_debug"]["actions"] == env.actions


def test_frontier_only_treats_normalized_habitat_depth_as_clear() -> None:
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {"depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]]},
            {"depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]]},
        ]
    )

    run_official_objectnav_episode_loop(
        env,
        policy="frontier_only",
        max_episodes=1,
        max_steps=2,
    )

    assert env.actions == ["move_forward", "stop"]


def test_frontier_only_keeps_turning_when_center_depth_is_blocked() -> None:
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {"depth": [[0.2, 0.2, 0.2], [0.2, 0.2, 0.2], [0.2, 0.2, 0.2]]},
            {"depth": [[0.2, 0.2, 0.2], [0.2, 0.2, 0.2], [0.2, 0.2, 0.2]]},
            {"depth": [[0.2, 0.2, 0.2], [0.2, 0.2, 0.2], [0.2, 0.2, 0.2]]},
        ]
    )

    run_official_objectnav_episode_loop(
        env,
        policy="frontier_only",
        max_episodes=1,
        max_steps=3,
    )

    assert env.actions == ["turn_left", "turn_left", "stop"]


def test_occupancy_frontier_map_marks_free_and_occupied_cells() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=21, cell_size_m=0.5)

    update_occupancy_frontier_map(
        frontier_map,
        {
            "depth": [[[0.2], [0.2], [0.2]]],
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        hfov_deg=60.0,
        min_depth_m=0.5,
        max_depth_m=5.0,
    )

    counts = occupancy_frontier_counts(frontier_map)

    assert counts["free"] > 0
    assert counts["occupied"] > 0
    assert frontier_map.grid[frontier_map.origin_cell] == OCCUPANCY_FREE
    assert OCCUPANCY_OCCUPIED in set(frontier_map.grid.ravel())


def test_occupancy_frontier_policy_records_map_debug_fields() -> None:
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="occupancy_frontier",
        max_episodes=1,
        max_steps=2,
    )

    assert env.actions == ["move_forward", "stop"]
    assert rows[0]["policy_debug"]["policy_kind"] == (
        "target_agnostic_occupancy_frontier_baseline"
    )
    assert rows[0]["policy_debug"]["occupancy_frontier"]["free"] > 0


def test_occupancy_frontier_turns_consistently_when_blocked() -> None:
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.2], [0.2], [0.2]], [[0.2], [0.2], [0.2]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.2], [0.2], [0.2]], [[0.2], [0.2], [0.2]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.2], [0.2], [0.2]], [[0.2], [0.2], [0.2]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="occupancy_frontier",
        max_episodes=1,
        max_steps=3,
    )

    assert env.actions[0] in {"turn_left", "turn_right"}
    assert env.actions == [env.actions[0], env.actions[0], "stop"]
    assert (
        rows[0]["policy_debug"]["occupancy_frontier"]["selected_bearing_rad"]
        is not None
    )


def test_occupancy_frontier_keeps_turn_direction_as_compass_changes() -> None:
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.2], [0.2], [0.2]], [[0.2], [0.2], [0.2]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.2], [0.2], [0.2]], [[0.2], [0.2], [0.2]]],
                "gps": [0.0, 0.0],
                "compass": [-0.52],
            },
            {
                "depth": [[[0.2], [0.2], [0.2]], [[0.2], [0.2], [0.2]]],
                "gps": [0.0, 0.0],
                "compass": [-1.04],
            },
            {
                "depth": [[[0.2], [0.2], [0.2]], [[0.2], [0.2], [0.2]]],
                "gps": [0.0, 0.0],
                "compass": [-1.56],
            },
        ]
    )

    run_official_objectnav_episode_loop(
        env,
        policy="occupancy_frontier",
        max_episodes=1,
        max_steps=4,
    )

    assert env.actions[0] in {"turn_left", "turn_right"}
    assert env.actions == [env.actions[0], env.actions[0], env.actions[0], "stop"]


def test_memory_belief_frontier_prefers_frontier_near_memory_anchor() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=11, cell_size_m=1.0)
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row, origin_col + 1] = OCCUPANCY_FREE
    frontier_map.grid[origin_row, origin_col + 2] = OCCUPANCY_FREE
    anchor = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 3.0,
                    "z_m": 0.0,
                    "confidence": 1.0,
                    "source": "east-memory",
                }
            ]
        }
    )[0]

    selected = _select_memory_belief_frontier(
        frontier_map,
        {
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        anchor,
        belief_sigma_m=2.0,
        travel_distance_weight=0.05,
    )

    assert selected is not None
    assert selected["frontier_cell"] == [origin_row, origin_col + 3]
    assert selected["belief_mass"] > 0.9
    assert selected["travel_distance_m"] == pytest.approx(3.0)


def test_active_perception_frontier_prefers_viewpoint_with_expected_evidence() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=11, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 1, origin_col] = OCCUPANCY_FREE
    standoff_viewpoint = (origin_row - 2, origin_col)
    standoff_frontier = (origin_row - 3, origin_col)
    frontier_map.grid[standoff_viewpoint] = OCCUPANCY_FREE
    frontier_map.grid[standoff_frontier] = OCCUPANCY_UNKNOWN
    frontier_map.grid[origin_row - 2, origin_col + 1] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 3, origin_col + 1] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 4, origin_col + 1] = OCCUPANCY_FREE
    anchor_frontier = (origin_row - 4, origin_col)
    frontier_map.grid[anchor_frontier] = OCCUPANCY_UNKNOWN
    anchor = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 4.0,
                    "confidence": 1.0,
                    "source": "forward-memory",
                }
            ]
        }
    )[0]

    selected = _select_memory_active_perception_frontier(
        frontier_map,
        {
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        anchor,
        preferred_view_distance_m=2.0,
        view_distance_sigma_m=0.5,
        travel_distance_weight=0.0,
    )

    assert selected is not None
    assert selected["viewpoint_cell"] == [
        standoff_viewpoint[0],
        standoff_viewpoint[1],
    ]
    assert selected["frontier_cell"] == [standoff_frontier[0], standoff_frontier[1]]
    assert selected["expected_evidence"] > 0.5
    assert selected["view_distance_quality"] == pytest.approx(1.0)
    assert selected["candidate_count"] >= 2
    assert selected["top_candidates"][0]["frontier_cell"] == [
        standoff_frontier[0],
        standoff_frontier[1],
    ]


def test_active_perception_frontier_keeps_side_viewpoint_evidence_positive() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=11, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 1, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 2, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 3, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 4, origin_col] = OCCUPANCY_FREE
    side_viewpoint = (origin_row - 4, origin_col + 1)
    frontier_map.grid[side_viewpoint] = OCCUPANCY_FREE
    side_frontier = (origin_row - 4, origin_col + 2)
    frontier_map.grid[side_frontier] = OCCUPANCY_UNKNOWN
    anchor = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 4.0,
                    "confidence": 1.0,
                    "source": "forward-memory",
                }
            ]
        }
    )[0]

    selected = _select_memory_active_perception_frontier(
        frontier_map,
        {
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        anchor,
        preferred_view_distance_m=2.0,
        view_distance_sigma_m=0.5,
        travel_distance_weight=0.0,
    )

    assert selected is not None
    assert selected["viewpoint_cell"] == [side_viewpoint[0], side_viewpoint[1]]
    assert selected["frontier_cell"] == [side_frontier[0], side_frontier[1]]
    assert selected["view_bearing_quality"] == pytest.approx(1.0)
    assert selected["expected_evidence"] > 0.0


def test_active_perception_frontier_scores_reachable_free_viewpoint() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=11, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    viewpoint = (origin_row - 1, origin_col)
    frontier = (origin_row - 2, origin_col)
    frontier_map.grid[viewpoint] = OCCUPANCY_FREE
    frontier_map.grid[frontier] = OCCUPANCY_UNKNOWN
    anchor = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 3.0,
                    "confidence": 1.0,
                    "source": "forward-memory",
                }
            ]
        }
    )[0]

    selected = _select_memory_active_perception_frontier(
        frontier_map,
        {
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        anchor,
        preferred_view_distance_m=2.0,
        view_distance_sigma_m=0.5,
        travel_distance_weight=0.0,
    )

    assert selected is not None
    assert selected["viewpoint_cell"] == [viewpoint[0], viewpoint[1]]
    assert selected["frontier_cell"] == [frontier[0], frontier[1]]
    assert selected["distance_to_anchor_m"] == pytest.approx(2.0)
    assert selected["path_distance_m"] == pytest.approx(1.0)
    assert selected["expected_evidence"] > 0.5


def test_active_perception_frontier_uses_free_space_path_distance() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=11, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE

    blocked_viewpoint = (origin_row, origin_col + 2)
    blocked_frontier = (origin_row, origin_col + 3)
    frontier_map.grid[origin_row, origin_col + 1] = OCCUPANCY_OCCUPIED
    frontier_map.grid[blocked_viewpoint] = OCCUPANCY_FREE
    frontier_map.grid[blocked_frontier] = OCCUPANCY_UNKNOWN

    reachable_viewpoint = (origin_row - 2, origin_col)
    reachable_frontier = (origin_row - 3, origin_col)
    frontier_map.grid[origin_row - 1, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[reachable_viewpoint] = OCCUPANCY_FREE
    frontier_map.grid[reachable_frontier] = OCCUPANCY_UNKNOWN

    anchor = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 1.0,
                    "source": "side-memory",
                }
            ]
        }
    )[0]

    selected = _select_memory_active_perception_frontier(
        frontier_map,
        {
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        anchor,
        preferred_view_distance_m=1.0,
        view_distance_sigma_m=1.0,
        travel_distance_weight=0.0,
    )

    assert selected is not None
    assert selected["viewpoint_cell"] == [
        reachable_viewpoint[0],
        reachable_viewpoint[1],
    ]
    assert selected["frontier_cell"] == [reachable_frontier[0], reachable_frontier[1]]
    assert selected["path_distance_m"] == pytest.approx(2.0)
    assert all(
        candidate["viewpoint_cell"] != [blocked_viewpoint[0], blocked_viewpoint[1]]
        for candidate in selected["top_candidates"]
    )


def test_memory_guided_frontier_stops_within_memory_radius() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.2,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "detector_positive:previous_session",
                }
            ]
        }
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=5,
        memory_anchors=anchors,
        memory_stop_radius_m=0.35,
    )

    assert env.actions == ["stop"]
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == "stop_at_memory"
    assert rows[0]["policy_debug"]["memory_prior"]["selected_source"] == (
        "detector_positive:previous_session"
    )


def test_memory_guided_frontier_turns_toward_memory_bearing() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "east-memory",
                }
            ]
        }
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
        memory_bearing_tolerance_deg=20.0,
    )

    assert env.actions == ["turn_right", "stop"]
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == (
        "turn_toward_memory"
    )


def test_memory_belief_frontier_records_selected_frontier_debug() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 2.0,
                    "confidence": 0.9,
                    "source": "forward-memory",
                }
            ]
        }
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_belief_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
    )
    debug = rows[0]["policy_debug"]["memory_prior"]

    assert all(action in {"move_forward", "turn_left", "turn_right", "stop"} for action in env.actions)
    assert debug["decision"] in {
        "move_toward_memory_belief_frontier",
        "turn_toward_memory_belief_frontier",
    }
    assert debug["selected_source"] == "forward-memory"
    assert debug["selected_frontier_cell"] is not None
    assert debug["belief_mass"] > 0.0
    assert debug["score"] == pytest.approx(
        debug["belief_mass"] - 0.05 * debug["travel_distance_m"]
    )


def test_memory_active_perception_frontier_records_expected_evidence_debug() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 4.0,
                    "confidence": 0.9,
                    "source": "forward-memory",
                }
            ]
        }
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
    )
    debug = rows[0]["policy_debug"]["memory_prior"]

    assert all(action in {"move_forward", "turn_left", "turn_right", "stop"} for action in env.actions)
    assert debug["decision"] in {
        "move_toward_memory_active_perception_frontier",
        "turn_toward_memory_active_perception_frontier",
    }
    assert debug["selected_source"] == "forward-memory"
    assert debug["selected_frontier_cell"] is not None
    assert debug["expected_evidence"] > 0.0
    assert debug["view_quality"] >= 0.0
    assert debug["top_candidates"]


def test_memory_active_perception_frontier_ranker_can_choose_lower_hand_score_candidate() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=7, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row, origin_col - 1] = OCCUPANCY_FREE
    frontier_map.grid[origin_row, origin_col + 1] = OCCUPANCY_FREE
    frontier_map.grid[origin_row, origin_col - 2] = OCCUPANCY_UNKNOWN
    frontier_map.grid[origin_row, origin_col + 2] = OCCUPANCY_UNKNOWN
    anchor = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 1.0,
                    "source": "right-memory",
                }
            ]
        }
    )[0]
    model = {
        "task": "habitat_official_candidate_viewpoint_ranker_model",
        "feature_names": ["candidate_rank"],
        "weights": [10.0],
        "bias": -5.0,
        "preprocessing": {
            "feature_means": {"candidate_rank": 0.0},
            "feature_scales": {"candidate_rank": 1.0},
        },
    }

    baseline = _select_memory_active_perception_frontier(
        frontier_map,
        {"gps": [0.0, 0.0], "compass": [0.0]},
        anchor,
        travel_distance_weight=0.0,
    )
    selected = _select_memory_active_perception_frontier(
        frontier_map,
        {"gps": [0.0, 0.0], "compass": [0.0]},
        anchor,
        travel_distance_weight=0.0,
        candidate_viewpoint_ranker_model=model,
    )

    assert baseline is not None
    assert selected is not None
    assert baseline["candidate_rank"] == 0
    assert selected["candidate_rank"] == 1
    assert selected["ranker_selected_candidate_rank"] == 1
    assert selected["ranker_prediction"] > selected["top_candidates"][1]["ranker_prediction"]
    assert selected["candidate_viewpoint_ranker_model"]["feature_count"] == 1


def test_memory_active_perception_frontier_ranker_only_reranks_top_k_candidates() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=9, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    for col in range(origin_col - 3, origin_col + 4):
        frontier_map.grid[origin_row, col] = OCCUPANCY_FREE
        frontier_map.grid[origin_row - 1, col] = OCCUPANCY_UNKNOWN
    anchor = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 3.0,
                    "z_m": 0.0,
                    "confidence": 1.0,
                    "source": "right-memory",
                }
            ]
        }
    )[0]
    model = {
        "task": "habitat_official_candidate_viewpoint_ranker_model",
        "feature_names": ["candidate_rank"],
        "weights": [10.0],
        "bias": -5.0,
        "preprocessing": {
            "feature_means": {"candidate_rank": 0.0},
            "feature_scales": {"candidate_rank": 1.0},
        },
    }

    selected = _select_memory_active_perception_frontier(
        frontier_map,
        {"gps": [0.0, 0.0], "compass": [0.0]},
        anchor,
        travel_distance_weight=0.0,
        candidate_viewpoint_ranker_model=model,
        top_k=2,
    )

    assert selected is not None
    assert selected["candidate_rank"] <= 1
    assert all(candidate["candidate_rank"] <= 1 for candidate in selected["top_candidates"])


def test_memory_active_perception_frontier_episode_loop_records_ranker_debug() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "right-memory",
                }
            ]
        }
    )
    model = {
        "task": "habitat_official_candidate_viewpoint_ranker_model",
        "feature_names": ["candidate_rank"],
        "weights": [10.0],
        "bias": -5.0,
        "preprocessing": {
            "feature_means": {"candidate_rank": 0.0},
            "feature_scales": {"candidate_rank": 1.0},
        },
    }
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
        candidate_viewpoint_ranker_model=model,
    )
    debug = rows[0]["policy_debug"]["memory_prior"]

    assert debug["candidate_viewpoint_ranker_model"]["feature_count"] == 1
    assert debug["ranker_prediction"] > 0.0
    assert debug["ranker_selected_candidate_rank"] >= 0


def test_memory_active_perception_frontier_commits_to_selected_viewpoint() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 1.0,
                    "source": "right-memory",
                }
            ]
        }
    )
    frontier_map = create_occupancy_frontier_map(size_cells=7, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row, origin_col - 1] = OCCUPANCY_FREE
    frontier_map.grid[origin_row, origin_col + 1] = OCCUPANCY_FREE
    frontier_map.grid[origin_row, origin_col - 2] = OCCUPANCY_UNKNOWN
    frontier_map.grid[origin_row, origin_col + 2] = OCCUPANCY_UNKNOWN
    state = OfficialPolicyState(
        rng=random.Random(7),
        object_category="chair",
        scene_id="depth-scene",
        memory_anchors=anchors,
        occupancy_map=frontier_map,
        candidate_viewpoint_ranker_model={
            "task": "habitat_official_candidate_viewpoint_ranker_model",
            "feature_names": ["candidate_rank"],
            "weights": [10.0],
            "bias": -5.0,
            "preprocessing": {
                "feature_means": {"candidate_rank": 0.0},
                "feature_scales": {"candidate_rank": 1.0},
            },
        },
    )
    observation = {
        "depth": None,
        "gps": [0.0, 0.0],
        "compass": [0.0],
    }

    _select_memory_active_perception_frontier_fallback(
        observation,
        state,
        step_index=3,
    )
    first_viewpoint = state.memory_debug["selected_viewpoint_cell"]
    assert first_viewpoint is not None

    state.candidate_viewpoint_ranker_model = {
        "task": "habitat_official_candidate_viewpoint_ranker_model",
        "feature_names": ["candidate_rank"],
        "weights": [-10.0],
        "bias": 5.0,
        "preprocessing": {
            "feature_means": {"candidate_rank": 0.0},
            "feature_scales": {"candidate_rank": 1.0},
        },
    }
    _select_memory_active_perception_frontier_fallback(
        observation,
        state,
        step_index=4,
    )

    assert state.memory_debug["selected_viewpoint_cell"] == first_viewpoint
    assert state.memory_debug["active_perception_commitment"] == "continued"


def test_memory_active_perception_frontier_scans_before_blocked_fallback() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 2.0,
                    "confidence": 1.0,
                    "source": "forward-memory",
                }
            ]
        }
    )
    frontier_map = create_occupancy_frontier_map(size_cells=7, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 1, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 2, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 3, origin_col] = OCCUPANCY_UNKNOWN
    state = OfficialPolicyState(
        rng=random.Random(7),
        object_category="chair",
        scene_id="depth-scene",
        memory_anchors=anchors,
        occupancy_map=frontier_map,
    )

    action = _select_memory_active_perception_frontier_fallback(
        {
            "depth": None,
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        state,
        step_index=3,
    )

    assert action == "turn_left"
    assert state.memory_debug["decision"] == "scan_blocked_active_perception_target"
    assert state.memory_debug["active_perception_phase"] == "blocked_scan_anchor"
    assert "fallback_reason" not in state.memory_debug


def test_memory_active_perception_frontier_orients_to_anchor_from_reached_viewpoint() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "right-memory",
                }
            ]
        }
    )
    frontier_map = create_occupancy_frontier_map(size_cells=7, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 1, origin_col] = OCCUPANCY_UNKNOWN
    state = OfficialPolicyState(
        rng=random.Random(7),
        object_category="chair",
        scene_id="depth-scene",
        memory_anchors=anchors,
        occupancy_map=frontier_map,
        memory_bearing_tolerance_rad=float(np.deg2rad(20.0)),
    )

    action = _select_memory_active_perception_frontier_fallback(
        {
            "depth": None,
            "gps": [0.0, 0.0],
            "compass": [0.0],
        },
        state,
    )

    assert action == "turn_right"
    assert state.memory_debug is not None
    assert state.memory_debug["decision"] == "orient_memory_anchor_from_active_viewpoint"
    assert state.memory_debug["active_perception_phase"] == "orient_anchor"
    assert state.memory_debug["selected_viewpoint_cell"] == [origin_row, origin_col]
    assert state.memory_debug["path_distance_m"] == pytest.approx(0.0)
    assert state.memory_debug["anchor_bearing_error_rad"] > 0.0


def test_pathfinder_suffix_activates_after_target_detection() -> None:
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    suffix = _FakePathfinderSuffixController(
        actions=["move_forward", "stop"],
        goal_position=(1.0, 0.0, 2.0),
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 0.9, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 0.9, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_pathfinder_suffix",
        max_episodes=1,
        max_steps=5,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        pathfinder_suffix_controller_factory=lambda _env: suffix,
    )

    debug = rows[0]["policy_debug"]
    assert env.actions == ["move_forward", "stop"]
    assert detector.call_count == 1
    assert suffix.next_action_calls == 2
    assert debug["pathfinder_suffix"]["active"] is True
    assert debug["pathfinder_suffix"]["activation_step"] == 0
    assert debug["pathfinder_suffix"]["goal_position"] == [1.0, 0.0, 2.0]
    assert debug["pathfinder_suffix"]["last_action"] == "stop"
    assert debug["memory_prior"]["decision"] == "follow_pathfinder_suffix"


def test_follower_action_name_maps_habitat_actions() -> None:
    assert _follower_action_name(None) == "stop"
    assert _follower_action_name("move_forward") == "move_forward"
    assert _follower_action_name(0) == "stop"
    assert _follower_action_name(1) == "move_forward"
    assert _follower_action_name(2) == "turn_left"
    assert _follower_action_name(3) == "turn_right"
    assert _follower_action_name(np.asarray([0, 0, 1, 0])) == "turn_left"


def test_episode_goal_positions_prefers_viewpoints_before_object_centers() -> None:
    episode = SimpleNamespace(
        goals=[
            SimpleNamespace(
                position=[9.0, 0.0, 9.0],
                view_points=[
                    SimpleNamespace(
                        agent_state=SimpleNamespace(position=[1.0, 0.0, 2.0])
                    ),
                    SimpleNamespace(
                        agent_state=SimpleNamespace(position=[3.0, 0.0, 4.0])
                    ),
                ],
            )
        ]
    )

    assert _episode_goal_positions(episode) == (
        (1.0, 0.0, 2.0),
        (3.0, 0.0, 4.0),
        (9.0, 0.0, 9.0),
    )


def test_official_pathfinder_suffix_controller_uses_oracle_backend_boundary() -> None:
    follower = _FakeHabitatFollower([1, None])
    env = SimpleNamespace(
        sim=_FakeHabitatSim(position=(0.0, 0.4, 0.0)),
        current_episode=SimpleNamespace(
            goals=[
                SimpleNamespace(
                    position=[9.0, 0.0, 9.0],
                    view_points=[
                        SimpleNamespace(
                            agent_state=SimpleNamespace(position=[2.0, 0.0, 0.0])
                        )
                    ],
                )
            ]
        ),
    )

    def backend_factory(
        episode_env: object,
        *,
        goal_radius_m: float,
    ) -> HabitatOracleFollowerBackend:
        return HabitatOracleFollowerBackend(
            episode_env,
            goal_radius_m=goal_radius_m,
            follower_factory=lambda _env, *, goal_radius_m: follower,
            backend_id="test-pathfinder-suffix",
        )

    controller = OfficialPathfinderSuffixController(
        env,
        goal_radius_m=0.7,
        backend_factory=backend_factory,
    )

    goal_position = controller.select_goal_position()

    assert goal_position == (2.0, 0.0, 0.0)
    assert controller.next_action(goal_position) == "move_forward"
    assert controller.next_action(goal_position) == "stop"
    assert follower.requested_goals == [
        (2.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
    ]
    status = controller.backend_status()
    assert status is not None
    assert status.active_goal_id == "pathfinder_suffix_goal"
    assert status.metadata["privileged_oracle"] is True
    assert status.metadata["benchmark_valid"] is False


def test_pathfinder_suffix_missing_goal_falls_back_to_detector_action() -> None:
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    suffix = _FakePathfinderSuffixController(actions=[], goal_position=None)
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 0.9, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 0.9, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_pathfinder_suffix",
        max_episodes=1,
        max_steps=2,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        pathfinder_suffix_controller_factory=lambda _env: suffix,
    )

    assert env.actions == ["move_forward", "stop"]
    assert suffix.next_action_calls == 0
    assert rows[0]["policy_debug"]["pathfinder_suffix"]["fallback_reason"] == (
        "no_pathfinder_goal"
    )
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == (
        "approach_detector_target"
    )


def test_targetnav_goal_from_detector_match_projects_bbox_depth() -> None:
    state = OfficialPolicyState(
        rng=random.Random(7),
        object_category="chair",
        scene_id="depth-scene",
    )
    observation = {
        "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
        "depth": np.full((4, 4), 2.0, dtype=float),
        "gps": [0.0, 0.0],
        "compass": [0.0],
    }
    detector_match = {
        "detector_bbox": [1, 1, 3, 3],
        "detector_category": "chair",
        "detector_confidence": 0.91,
    }

    goal = _targetnav_goal_from_detector_match(
        observation,
        state,
        detector_match,
    )

    assert goal is not None
    assert goal["x_m"] == pytest.approx(0.0)
    assert goal["z_m"] == pytest.approx(2.0)
    assert goal["depth_m"] == pytest.approx(2.0)
    assert goal["targetnav_estimator"] == "bbox_depth"
    assert goal["detector_confidence"] == 0.91
    assert goal["targetnav_measurement_variance_m2"] > 0.0
    assert goal["depth_at_max_range"] is False


def test_targetnav_goal_smoothing_updates_episode_target_belief() -> None:
    previous = {
        "targetnav_estimator": "bbox_depth",
        "x_m": 0.0,
        "z_m": 2.0,
        "depth_m": 2.0,
        "bearing_rad": 0.0,
        "detector_confidence": 0.8,
        "smoothing_sample_count": 1,
    }
    current = {
        "targetnav_estimator": "bbox_depth",
        "x_m": 2.0,
        "z_m": 4.0,
        "depth_m": 3.0,
        "bearing_rad": 0.2,
        "detector_confidence": 0.9,
    }

    smoothed = _smooth_targetnav_goal(previous, current, alpha=0.5)

    assert smoothed["x_m"] == pytest.approx(1.0)
    assert smoothed["z_m"] == pytest.approx(3.0)
    assert smoothed["depth_m"] == pytest.approx(2.5)
    assert smoothed["bearing_rad"] == pytest.approx(0.1)
    assert smoothed["detector_confidence"] == 0.9
    assert smoothed["smoothing_sample_count"] == 2
    assert smoothed["targetnav_estimator"] == "bbox_depth_smoothed"


def test_targetnav_goal_smoothing_downweights_uncertain_max_depth_jump() -> None:
    previous = {
        "targetnav_estimator": "bbox_depth_smoothed",
        "x_m": -2.0,
        "z_m": 0.0,
        "depth_m": 1.2,
        "bearing_rad": 0.1,
        "detector_confidence": 0.8,
        "smoothing_sample_count": 8,
        "targetnav_position_variance_m2": 0.25,
    }
    current = {
        "targetnav_estimator": "bbox_depth",
        "x_m": -7.0,
        "z_m": -0.5,
        "depth_m": 5.0,
        "bearing_rad": -0.3,
        "detector_confidence": 0.92,
        "depth_at_max_range": True,
        "targetnav_measurement_variance_m2": 36.0,
    }

    smoothed = _smooth_targetnav_goal(previous, current)

    assert smoothed["x_m"] == pytest.approx(-2.034, abs=0.01)
    assert smoothed["z_m"] == pytest.approx(-0.003, abs=0.01)
    assert smoothed["targetnav_update_gain"] < 0.01
    assert smoothed["targetnav_estimator"] == "bbox_depth_robust_smoothed"
    assert smoothed["raw_target_goal"] == current


def test_targetnav_goal_smoothing_uses_probabilistic_gain_for_consistent_goal() -> None:
    previous = {
        "targetnav_estimator": "bbox_depth_smoothed",
        "x_m": 0.0,
        "z_m": 2.0,
        "depth_m": 2.0,
        "bearing_rad": 0.0,
        "detector_confidence": 0.8,
        "smoothing_sample_count": 3,
        "targetnav_position_variance_m2": 1.0,
    }
    current = {
        "targetnav_estimator": "bbox_depth",
        "x_m": 1.0,
        "z_m": 3.0,
        "depth_m": 2.2,
        "bearing_rad": 0.1,
        "detector_confidence": 0.9,
        "targetnav_measurement_variance_m2": 1.0,
    }

    smoothed = _smooth_targetnav_goal(previous, current)

    assert smoothed["x_m"] == pytest.approx(0.5)
    assert smoothed["z_m"] == pytest.approx(2.5)
    assert smoothed["targetnav_update_gain"] == pytest.approx(0.5)
    assert smoothed["targetnav_position_variance_m2"] == pytest.approx(0.5)


def test_targetnav_pointgoal_adapter_matches_habitat_polar_convention() -> None:
    observation = {"gps": [0.0, 0.0], "compass": [0.0]}

    ahead = _targetnav_pointgoal_with_gps_compass(
        observation,
        {"x_m": 0.0, "z_m": 2.0},
    )
    right = _targetnav_pointgoal_with_gps_compass(
        observation,
        {"x_m": 2.0, "z_m": 0.0},
    )
    left = _targetnav_pointgoal_with_gps_compass(
        observation,
        {"x_m": -2.0, "z_m": 0.0},
    )

    assert ahead == pytest.approx([2.0, 0.0])
    assert right == pytest.approx([2.0, -np.pi / 2.0])
    assert left == pytest.approx([2.0, np.pi / 2.0])


def test_targetnav_pointgoal_adapter_accounts_for_current_pose() -> None:
    observation = {
        # Habitat GPS is [forward, right], so this is x=1, z=1 internally.
        "gps": [1.0, 1.0],
        # Habitat compass decreases on right turns; internal heading is +right.
        "compass": [-np.pi / 2.0],
    }

    pointgoal = _targetnav_pointgoal_with_gps_compass(
        observation,
        {"x_m": 2.0, "z_m": 1.0},
    )

    assert pointgoal == pytest.approx([1.0, 0.0])


def test_targetnav_fmm_action_moves_toward_clear_distance_field_cell() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=7, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 1, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 2, origin_col] = OCCUPANCY_FREE
    state = OfficialPolicyState(
        rng=random.Random(7),
        object_category="chair",
        scene_id="depth-scene",
        occupancy_map=frontier_map,
    )
    observation = {
        "depth": None,
        "gps": [0.0, 0.0],
        "compass": [0.0],
    }

    action = _select_targetnav_fmm_action(
        observation,
        state,
        {"targetnav_estimator": "bbox_depth", "x_m": 0.0, "z_m": 2.0},
        step_index=4,
    )

    assert action == "move_forward"
    assert state.targetnav_debug is not None
    assert state.targetnav_debug["backend"] == "fmm_grid"
    assert state.targetnav_debug["selected_next_cell"] == [
        origin_row - 1,
        origin_col,
    ]
    assert state.memory_debug["decision"] == "targetnav_fmm_move"


def test_targetnav_fmm_action_replans_around_blocked_forward_cell() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=7, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    for cell in (
        (origin_row, origin_col),
        (origin_row, origin_col - 1),
        (origin_row, origin_col - 2),
        (origin_row, origin_col - 3),
        (origin_row - 1, origin_col),
        (origin_row - 1, origin_col - 1),
        (origin_row - 1, origin_col - 2),
        (origin_row - 1, origin_col - 3),
    ):
        frontier_map.grid[cell] = OCCUPANCY_FREE
    state = OfficialPolicyState(
        rng=random.Random(7),
        object_category="chair",
        scene_id="depth-scene",
        occupancy_map=frontier_map,
        blocked_turn_action="turn_left",
    )
    observation = {
        "depth": np.full((6, 6), np.nan, dtype=float),
        "gps": [0.0, 0.0],
        # Habitat compass decreases on right turns; internal heading is left.
        "compass": [np.pi / 2.0],
    }

    action = _select_targetnav_fmm_action(
        observation,
        state,
        {"targetnav_estimator": "bbox_depth", "x_m": -3.0, "z_m": 0.0},
        step_index=5,
    )

    assert action == "turn_right"
    assert state.targetnav_debug is not None
    assert state.targetnav_debug["backend"] == "fmm_grid"
    assert state.targetnav_debug["blocked_forward_cell"] == [
        origin_row,
        origin_col - 1,
    ]
    assert state.occupancy_map.grid[origin_row, origin_col - 1] == OCCUPANCY_OCCUPIED
    assert state.targetnav_debug["replanned_after_blocked_forward"] is True
    assert state.targetnav_debug["selected_next_cell"] == [
        origin_row - 1,
        origin_col,
    ]
    assert state.memory_debug["decision"] == "targetnav_fmm_turn"


def test_targetnav_fmm_does_not_stop_when_only_current_cell_is_reachable() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=7, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    state = OfficialPolicyState(
        rng=random.Random(7),
        object_category="chair",
        scene_id="depth-scene",
        occupancy_map=frontier_map,
    )
    observation = {
        "depth": None,
        "gps": [0.0, 0.0],
        "compass": [0.0],
    }

    action = _select_targetnav_fmm_action(
        observation,
        state,
        {"targetnav_estimator": "bbox_depth", "x_m": -2.0, "z_m": 0.0},
        step_index=6,
    )

    assert action is None
    assert state.targetnav_debug is not None
    assert state.targetnav_debug["fallback_reason"] == (
        "selected_current_cell_far_from_target"
    )
    assert state.targetnav_debug["pointgoal_with_gps_compass"] == pytest.approx(
        [2.0, np.pi / 2.0]
    )


def test_targetnav_occupancy_action_moves_toward_free_target_cell() -> None:
    frontier_map = create_occupancy_frontier_map(size_cells=7, cell_size_m=1.0)
    frontier_map.grid[:, :] = OCCUPANCY_OCCUPIED
    origin_row, origin_col = frontier_map.origin_cell
    frontier_map.grid[origin_row, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 1, origin_col] = OCCUPANCY_FREE
    frontier_map.grid[origin_row - 2, origin_col] = OCCUPANCY_FREE
    state = OfficialPolicyState(
        rng=random.Random(7),
        object_category="chair",
        scene_id="depth-scene",
        occupancy_map=frontier_map,
    )
    observation = {
        "depth": None,
        "gps": [0.0, 0.0],
        "compass": [0.0],
    }
    target_goal = {
        "x_m": 0.0,
        "z_m": 2.0,
        "targetnav_estimator": "bbox_depth",
    }

    action = _select_targetnav_occupancy_action(
        observation,
        state,
        target_goal,
        step_index=3,
    )

    assert action == "move_forward"
    assert state.targetnav_debug is not None
    assert state.targetnav_debug["backend"] == "occupancy_grid"
    assert state.targetnav_debug["selected_target_cell"] == [
        origin_row - 2,
        origin_col,
    ]
    assert state.memory_debug["decision"] == "targetnav_occupancy_move"


def test_targetnav_policy_uses_detector_depth_occupancy_backend() -> None:
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_targetnav",
        max_episodes=1,
        max_steps=2,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
    )

    debug = rows[0]["policy_debug"]
    assert env.actions == ["move_forward", "stop"]
    assert detector.call_count == 1
    assert debug["targetnav"]["backend"] == "occupancy_grid"
    assert debug["targetnav"]["target_goal"]["targetnav_estimator"] == "bbox_depth"
    assert debug["memory_prior"]["decision"] == "targetnav_occupancy_move"


def test_targetnav_policy_can_use_oracle_follower_backend_selector() -> None:
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    suffix = _FakePathfinderSuffixController(
        actions=["move_forward", "stop"],
        goal_position=(1.0, 0.0, 2.0),
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_targetnav",
        max_episodes=1,
        max_steps=5,
        targetnav_backend="oracle_follower",
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        pathfinder_suffix_controller_factory=lambda _env: suffix,
    )

    debug = rows[0]["policy_debug"]
    assert env.actions == ["move_forward", "stop"]
    assert suffix.next_action_calls == 2
    assert debug["targetnav"]["backend"] == "oracle_follower"
    assert debug["targetnav"]["source_validity"] == "oracle_diagnostic_only"
    assert debug["pathfinder_suffix"]["active"] is True
    assert debug["memory_prior"]["decision"] == "follow_pathfinder_suffix"


def test_no_memory_targetnav_uses_detector_but_not_memory_anchor() -> None:
    anchor = OfficialMemoryAnchor(
        object_category="chair",
        scene_id="depth-scene",
        x_m=2.0,
        z_m=3.0,
        confidence=0.99,
        source="memory_should_be_ignored",
    )
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    suffix = _FakePathfinderSuffixController(
        actions=["move_forward", "stop"],
        goal_position=(1.0, 0.0, 2.0),
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="no_memory_targetnav",
        targetnav_backend="oracle_follower",
        max_episodes=1,
        max_steps=5,
        memory_anchors=(anchor,),
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        pathfinder_suffix_controller_factory=lambda _env: suffix,
    )

    debug = rows[0]["policy_debug"]
    assert env.actions == ["move_forward", "stop"]
    assert suffix.next_action_calls == 2
    assert debug["targetnav"]["backend"] == "oracle_follower"
    assert "memory_anchor" not in debug["targetnav"]
    assert debug["pathfinder_suffix"]["goal_position"] == [1.0, 0.0, 2.0]


def test_naive_count_targetnav_executes_matching_memory_anchor() -> None:
    anchor = OfficialMemoryAnchor(
        object_category="chair",
        scene_id="depth-scene",
        x_m=2.0,
        z_m=3.0,
        confidence=0.91,
        source="naive_count_memory",
    )
    suffix = _FakePathfinderSuffixController(
        actions=["move_forward", "stop"],
        goal_position=None,
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )
    env.current_episode.start_position = (10.0, 0.0, 20.0)
    env.current_episode.start_rotation = (0.0, 0.0, 0.0, 1.0)

    rows = run_official_objectnav_episode_loop(
        env,
        policy="naive_count_targetnav",
        targetnav_backend="oracle_follower",
        max_episodes=1,
        max_steps=5,
        memory_anchors=(anchor,),
        pathfinder_suffix_controller_factory=lambda _env: suffix,
    )

    debug = rows[0]["policy_debug"]
    assert env.actions == ["move_forward", "stop"]
    assert suffix.requested_goal_positions[0] == pytest.approx((12.0, 0.0, 17.0))
    assert debug["targetnav"]["backend"] == "oracle_follower"
    assert debug["targetnav"]["memory_anchor"]["source"] == "naive_count_memory"
    assert debug["memory_prior"]["decision"] == "follow_pathfinder_suffix"


def test_targetnav_fmm_backend_executes_matching_memory_anchor() -> None:
    anchor = OfficialMemoryAnchor(
        object_category="chair",
        scene_id="depth-scene",
        x_m=0.0,
        z_m=2.0,
        confidence=0.88,
        source="unit_memory",
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_targetnav",
        targetnav_backend="fmm_grid",
        max_episodes=1,
        max_steps=2,
        memory_anchors=(anchor,),
    )

    debug = rows[0]["policy_debug"]
    assert env.actions == ["move_forward", "stop"]
    assert debug["targetnav"]["backend"] == "fmm_grid"
    assert debug["targetnav"]["target_goal"]["targetnav_estimator"] == (
        "memory_anchor"
    )
    assert debug["targetnav"]["target_goal"]["source"] == "unit_memory"
    assert debug["memory_prior"]["decision"] == "targetnav_fmm_move"


def test_targetnav_oracle_backend_executes_matching_memory_anchor() -> None:
    anchor = OfficialMemoryAnchor(
        object_category="chair",
        scene_id="depth-scene",
        x_m=2.0,
        z_m=3.0,
        confidence=0.91,
        source="unit_memory",
    )
    suffix = _FakePathfinderSuffixController(
        actions=["move_forward", "stop"],
        goal_position=None,
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )
    env.current_episode.start_position = (10.0, 0.0, 20.0)
    env.current_episode.start_rotation = (0.0, 0.0, 0.0, 1.0)

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_targetnav",
        targetnav_backend="oracle_follower",
        max_episodes=1,
        max_steps=5,
        memory_anchors=(anchor,),
        pathfinder_suffix_controller_factory=lambda _env: suffix,
    )

    debug = rows[0]["policy_debug"]
    assert env.actions == ["move_forward", "stop"]
    assert suffix.next_action_calls == 2
    assert suffix.requested_goal_positions[0] == pytest.approx((12.0, 0.0, 17.0))
    assert debug["targetnav"]["backend"] == "oracle_follower"
    assert debug["targetnav"]["source_validity"] == "oracle_diagnostic_only"
    assert debug["targetnav"]["memory_anchor"]["source"] == "unit_memory"
    assert debug["targetnav"]["oracle_follower"]["goal_position"] == pytest.approx(
        [12.0, 0.0, 17.0]
    )
    assert debug["memory_prior"]["decision"] == "follow_pathfinder_suffix"


def test_targetnav_oracle_memory_anchor_missing_start_pose_falls_back() -> None:
    anchor = OfficialMemoryAnchor(
        object_category="chair",
        scene_id="depth-scene",
        x_m=2.0,
        z_m=3.0,
        confidence=0.91,
        source="unit_memory",
    )
    suffix = _FakePathfinderSuffixController(
        actions=["move_forward"],
        goal_position=None,
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_targetnav",
        targetnav_backend="oracle_follower",
        max_episodes=1,
        max_steps=2,
        memory_anchors=(anchor,),
        pathfinder_suffix_controller_factory=lambda _env: suffix,
    )

    debug = rows[0]["policy_debug"]
    assert suffix.next_action_calls == 0
    assert debug["targetnav"]["backend"] == "oracle_follower"
    assert debug["targetnav"]["fallback_reason"] == (
        "missing_episode_start_pose_for_memory_anchor"
    )


def test_memory_anchor_oracle_goal_position_uses_anchor_vertical_offset() -> None:
    state = OfficialPolicyState(
        rng=random.Random(313),
        episode_start_position=(10.0, 2.5, 20.0),
        episode_start_rotation=(0.0, 0.0, 0.0, 1.0),
    )
    anchor = OfficialMemoryAnchor(
        object_category="chair",
        x_m=2.0,
        y_m=-2.25,
        z_m=3.0,
    )

    goal_position = _memory_anchor_oracle_goal_position(state, anchor)

    assert goal_position == pytest.approx((12.0, 0.25, 17.0))


def test_memory_anchor_oracle_goal_position_without_vertical_offset_uses_start_height() -> None:
    state = OfficialPolicyState(
        rng=random.Random(313),
        episode_start_position=(10.0, 2.5, 20.0),
        episode_start_rotation=(0.0, 0.0, 0.0, 1.0),
    )
    anchor = OfficialMemoryAnchor(
        object_category="chair",
        x_m=2.0,
        z_m=3.0,
    )

    goal_position = _memory_anchor_oracle_goal_position(state, anchor)

    assert goal_position == pytest.approx((12.0, 2.5, 17.0))


def test_targetnav_fmm_policy_uses_detector_depth_fmm_backend() -> None:
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_targetnav_fmm",
        max_episodes=1,
        max_steps=2,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
    )

    debug = rows[0]["policy_debug"]
    assert env.actions == ["move_forward", "stop"]
    assert detector.call_count == 1
    assert debug["targetnav"]["backend"] == "fmm_grid"
    assert debug["targetnav"]["target_goal"]["targetnav_estimator"] == "bbox_depth"
    assert debug["targetnav"]["pointgoal_with_gps_compass"] == pytest.approx(
        [2.0, 0.0]
    )
    assert debug["memory_prior"]["decision"] == "targetnav_fmm_move"


def test_targetnav_ddppo_policy_sends_depth_and_pointgoal_to_backend() -> None:
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    backend = _FakeDDPPOBackend(action_ids=[1])
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_targetnav_ddppo",
        max_episodes=1,
        max_steps=2,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        targetnav_ddppo_backend=backend,
    )

    debug = rows[0]["policy_debug"]
    assert env.actions == ["move_forward", "stop"]
    assert detector.call_count == 1
    assert len(backend.calls) == 1
    assert backend.calls[0]["pointgoal_with_gps_compass"] == pytest.approx(
        [2.0, 0.0]
    )
    assert backend.calls[0]["depth"].shape == (4, 4)
    assert debug["targetnav"]["backend"] == "ddppo_pointnav"
    assert debug["targetnav"]["pointgoal_with_gps_compass"] == pytest.approx(
        [2.0, 0.0]
    )
    assert debug["memory_prior"]["decision"] == "targetnav_ddppo_move"


def test_targetnav_ddppo_backend_resets_for_each_episode() -> None:
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    backend = _FakeDDPPOBackend(action_ids=[0, 0])
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ]
    )

    run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_targetnav_ddppo",
        max_episodes=2,
        max_steps=2,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        targetnav_ddppo_backend=backend,
    )

    assert backend.reset_count == 2


def test_targetnav_policy_refreshes_detector_goal_while_following() -> None:
    detector = _SequenceDetector(
        [
            [
                Detection(
                    category="chair",
                    bbox=(1, 1, 3, 3),
                    confidence=0.8,
                    mask=np.ones((4, 4), dtype=bool),
                )
            ],
            [
                Detection(
                    category="chair",
                    bbox=(2, 1, 4, 3),
                    confidence=0.9,
                    mask=np.ones((4, 4), dtype=bool),
                )
            ],
        ]
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": np.full((4, 4), 2.0, dtype=float),
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_active_perception_frontier_targetnav",
        max_episodes=1,
        max_steps=3,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
    )

    target_goal = rows[0]["policy_debug"]["targetnav"]["target_goal"]
    assert detector.call_count >= 2
    assert target_goal["targetnav_estimator"] == "bbox_depth_robust_smoothed"
    assert target_goal["smoothing_sample_count"] >= 2
    assert 0.0 < target_goal["x_m"] < 2.0


def test_memory_belief_frontier_centers_off_axis_detector_target_before_stop() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "east-memory",
                }
            ]
        }
    )
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(2, 1, 4, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_belief_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
    )

    debug = rows[0]["policy_debug"]["memory_prior"]
    assert env.actions == ["turn_right", "stop"]
    assert debug["decision"] == "center_detector_target"
    assert debug["detector_center_offset_fraction"] > 0.0
    assert "selected_frontier_cell" not in debug


def test_memory_belief_frontier_can_invert_detector_center_direction() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "east-memory",
                }
            ]
        }
    )
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(2, 1, 4, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_belief_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        detector_center_direction_sign=-1,
    )

    debug = rows[0]["policy_debug"]["memory_prior"]
    assert env.actions == ["turn_left", "stop"]
    assert debug["decision"] == "center_detector_target"
    assert debug["detector_center_offset_fraction"] > 0.0
    assert debug["detector_center_direction_sign"] == -1


def test_memory_belief_frontier_approaches_centered_far_detector_target_before_stop() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "east-memory",
                }
            ]
        }
    )
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": [[[0.9], [0.9], [0.9], [0.9]]] * 4,
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_belief_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
    )

    debug = rows[0]["policy_debug"]["memory_prior"]
    assert env.actions == ["move_forward", "stop"]
    assert debug["decision"] == "approach_detector_target"
    assert debug["detector_depth_median"] == pytest.approx(0.9)
    assert debug["detector_depth_is_normalized"] is True
    assert "selected_frontier_cell" not in debug


def test_memory_belief_frontier_stops_only_when_detector_depth_is_close() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "east-memory",
                }
            ]
        }
    )
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": [[[0.12], [0.12], [0.12], [0.12]]] * 4,
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_belief_frontier",
        max_episodes=1,
        max_steps=5,
        memory_anchors=anchors,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
    )

    debug = rows[0]["policy_debug"]["memory_prior"]
    assert env.actions == ["stop"]
    assert debug["decision"] == "stop_on_detector_range_confirmed"
    assert debug["detector_depth_median"] == pytest.approx(0.12)
    assert debug["detector_bbox_area_fraction"] == pytest.approx(0.25)


def test_memory_belief_frontier_flips_detector_center_direction_after_immediate_target_loss(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "depth-scene",
                        "x_m": 2.0,
                        "z_m": 0.0,
                        "confidence": 0.9,
                        "source": "east-memory",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    right_edge_target = Detection(
        category="chair",
        bbox=(2, 1, 4, 3),
        confidence=0.91,
        mask=np.ones((4, 4), dtype=bool),
    )
    detector = _SequenceDetector(
        [
            [right_edge_target],
            [],
            [right_edge_target],
        ]
    )

    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                    "depth": [[[0.9], [0.9], [0.9], [0.9]]] * 4,
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                }
            ]
        )

    run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_belief_frontier",
        max_episodes=1,
        max_steps=4,
        validate_habitat=False,
        memory_prior_path=memory_path,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        env_factory=env_factory,
    )

    trace = json.loads(
        (tmp_path / "out" / "policy_trace.json").read_text(encoding="utf-8")
    )

    assert [step["action"] for step in trace["steps"]] == [
        "turn_right",
        "turn_left",
        "turn_left",
        "stop",
    ]
    assert trace["steps"][1]["memory_prior"]["decision"] == (
        "reacquire_detector_target"
    )
    assert trace["steps"][1]["memory_prior"]["detector_center_direction_sign"] == -1
    assert trace["steps"][2]["memory_prior"]["decision"] == "center_detector_target"
    assert trace["steps"][2]["memory_prior"]["detector_center_direction_sign"] == -1


def test_memory_evidence_frontier_approaches_after_center_action_loses_target(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "depth-scene",
                        "x_m": 2.0,
                        "z_m": 0.0,
                        "confidence": 0.9,
                        "source": "east-memory",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    right_edge_target = Detection(
        category="chair",
        bbox=(2, 1, 4, 3),
        confidence=0.91,
        mask=np.ones((4, 4), dtype=bool),
    )
    detector = _SequenceDetector(
        [
            [right_edge_target],
            [],
            [right_edge_target],
        ]
    )

    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                    "depth": [[[0.9], [0.9], [0.9], [0.9]]] * 4,
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                }
            ]
        )

    run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_evidence_frontier",
        max_episodes=1,
        max_steps=4,
        validate_habitat=False,
        memory_prior_path=memory_path,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        env_factory=env_factory,
    )

    trace = json.loads(
        (tmp_path / "out" / "policy_trace.json").read_text(encoding="utf-8")
    )

    assert [step["action"] for step in trace["steps"]] == [
        "turn_right",
        "turn_left",
        "move_forward",
        "stop",
    ]
    assert trace["steps"][1]["memory_prior"]["decision"] == (
        "reacquire_detector_target"
    )
    assert trace["steps"][2]["memory_prior"]["decision"] == (
        "approach_detector_target_after_center_loss"
    )
    assert trace["steps"][2]["memory_prior"]["suppressed_detector_center_action"] == (
        "turn_right"
    )
    assert trace["steps"][2]["memory_prior"]["detector_center_offset_sign"] == 1


def test_memory_learned_local_frontier_scores_action_after_center_loss(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "depth-scene",
                        "x_m": 2.0,
                        "z_m": 0.0,
                        "confidence": 0.9,
                        "source": "east-memory",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    model_path = _write_local_action_model(tmp_path / "local_model.json")
    right_edge_target = Detection(
        category="chair",
        bbox=(2, 1, 4, 3),
        confidence=0.91,
        mask=np.ones((4, 4), dtype=bool),
    )
    detector = _SequenceDetector(
        [
            [right_edge_target],
            [],
            [right_edge_target],
        ]
    )

    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                    "depth": [[[0.9], [0.9], [0.9], [0.9]]] * 4,
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                }
            ]
        )

    run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_learned_local_frontier",
        max_episodes=1,
        max_steps=4,
        validate_habitat=False,
        memory_prior_path=memory_path,
        local_action_model_path=model_path,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        env_factory=env_factory,
    )

    trace = json.loads(
        (tmp_path / "out" / "policy_trace.json").read_text(encoding="utf-8")
    )

    assert [step["action"] for step in trace["steps"]] == [
        "turn_right",
        "turn_left",
        "turn_left",
        "stop",
    ]
    assert trace["steps"][2]["memory_prior"]["decision"] == (
        "learned_local_action_score"
    )
    assert trace["steps"][2]["memory_prior"]["learned_local_action"] == "turn_left"
    assert trace["steps"][2]["memory_prior"]["learned_local_candidate_scores"][
        "turn_left"
    ] > trace["steps"][2]["memory_prior"]["learned_local_candidate_scores"][
        "move_forward"
    ]


def test_memory_learned_local_frontier_scores_with_online_temporal_history(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "depth-scene",
                        "x_m": 2.0,
                        "z_m": 0.0,
                        "confidence": 0.9,
                        "source": "east-memory",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    model_path = _write_temporal_local_action_model(
        tmp_path / "temporal_local_model.json"
    )
    right_edge_target = Detection(
        category="chair",
        bbox=(2, 1, 4, 3),
        confidence=0.91,
        mask=np.ones((4, 4), dtype=bool),
    )
    detector = _SequenceDetector(
        [
            [right_edge_target],
            [],
            [right_edge_target],
        ]
    )

    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                    "depth": [[[0.9], [0.9], [0.9], [0.9]]] * 4,
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                }
            ]
        )

    run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_learned_local_frontier",
        max_episodes=1,
        max_steps=4,
        validate_habitat=False,
        memory_prior_path=memory_path,
        local_action_model_path=model_path,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        env_factory=env_factory,
    )

    trace = json.loads(
        (tmp_path / "out" / "policy_trace.json").read_text(encoding="utf-8")
    )

    learned_debug = trace["steps"][2]["memory_prior"]
    assert [step["action"] for step in trace["steps"]] == [
        "turn_right",
        "turn_left",
        "turn_left",
        "stop",
    ]
    assert learned_debug["decision"] == "learned_local_action_score"
    assert learned_debug["learned_local_action"] == "turn_left"
    assert learned_debug["learned_local_temporal_features"][
        "history_observed_step_count"
    ] == 2
    assert learned_debug["learned_local_temporal_features"][
        "recent_target_visible_count"
    ] == 2
    assert learned_debug["learned_local_temporal_features"][
        "previous_target_visible"
    ] is False
    assert learned_debug["learned_local_candidate_scores"]["turn_left"] > (
        learned_debug["learned_local_candidate_scores"]["move_forward"]
    )


def test_memory_learned_local_frontier_suppresses_failed_turn_candidates(
    tmp_path,
) -> None:
    memory_path = tmp_path / "memory_prior.json"
    memory_path.write_text(
        json.dumps(
            {
                "anchors": [
                    {
                        "object_category": "chair",
                        "scene_id": "depth-scene",
                        "x_m": 2.0,
                        "z_m": 0.0,
                        "confidence": 0.9,
                        "source": "east-memory",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    model_path = _write_local_action_model(tmp_path / "local_model.json")
    right_edge_target = Detection(
        category="chair",
        bbox=(2, 1, 4, 3),
        confidence=0.91,
        mask=np.ones((4, 4), dtype=bool),
    )
    detector = _SequenceDetector(
        [
            [right_edge_target],
            [],
            [right_edge_target],
            [],
            [right_edge_target],
        ]
    )

    def env_factory(_config: OfficialObjectNavRunConfig) -> _FakeDepthOfficialObjectNavEnv:
        return _FakeDepthOfficialObjectNavEnv(
            observations=[
                {
                    "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                    "depth": [[[0.9], [0.9], [0.9], [0.9]]] * 4,
                    "gps": [0.0, 0.0],
                    "compass": [0.0],
                }
            ]
        )

    run_habitat_official_objectnav_eval(
        tmp_path / "out",
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_learned_local_frontier",
        max_episodes=1,
        max_steps=6,
        validate_habitat=False,
        memory_prior_path=memory_path,
        local_action_model_path=model_path,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
        env_factory=env_factory,
    )

    trace = json.loads(
        (tmp_path / "out" / "policy_trace.json").read_text(encoding="utf-8")
    )

    assert [step["action"] for step in trace["steps"][:5]] == [
        "turn_right",
        "turn_left",
        "turn_left",
        "turn_right",
        "move_forward",
    ]
    assert trace["steps"][4]["memory_prior"]["decision"] == (
        "learned_local_action_score"
    )
    assert trace["steps"][4]["memory_prior"]["learned_local_action"] == (
        "move_forward"
    )
    assert trace["steps"][4]["memory_prior"]["suppressed_detector_center_actions"] == [
        "turn_left",
        "turn_right",
    ]
    assert set(
        trace["steps"][4]["memory_prior"]["learned_local_candidate_scores"]
    ) == {"move_forward"}


def test_memory_guided_frontier_stops_on_detector_confirmed_target() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "east-memory",
                }
            ]
        }
    )
    detector = _StaticDetector(
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ]
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            }
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=5,
        memory_anchors=anchors,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
    )

    assert env.actions == ["stop"]
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == "stop_on_detector"
    assert rows[0]["policy_debug"]["memory_prior"]["detector_category"] == "chair"
    assert rows[0]["policy_debug"]["memory_prior"]["detector_confidence"] == 0.91
    assert detector.call_count == 1


@pytest.mark.parametrize(
    "detections",
    [
        [
            Detection(
                category="sofa",
                bbox=(1, 1, 3, 3),
                confidence=0.91,
                mask=np.ones((4, 4), dtype=bool),
            )
        ],
        [
            Detection(
                category="chair",
                bbox=(1, 1, 3, 3),
                confidence=0.2,
                mask=np.ones((4, 4), dtype=bool),
            )
        ],
    ],
)
def test_memory_guided_frontier_ignores_wrong_or_low_confidence_detector_stop(
    detections: list[Detection],
) -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 2.0,
                    "z_m": 0.0,
                    "confidence": 0.9,
                    "source": "east-memory",
                }
            ]
        }
    )
    detector = _StaticDetector(detections)
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "rgb": np.zeros((4, 4, 3), dtype=np.uint8),
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
        memory_bearing_tolerance_deg=20.0,
        target_detector_adapter=detector,
        target_detector_min_confidence=0.5,
    )

    assert env.actions == ["turn_right", "stop"]
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == (
        "turn_toward_memory"
    )
    assert detector.call_count == 1


def test_memory_guided_frontier_moves_when_aligned_and_clear() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 2.0,
                    "confidence": 0.9,
                    "source": "forward-memory",
                }
            ]
        }
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
    )

    assert env.actions == ["move_forward", "stop"]
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == (
        "move_toward_memory"
    )


def test_memory_guided_frontier_interprets_habitat_gps_forward_right_order() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 2.0,
                    "confidence": 0.9,
                    "source": "forward-memory",
                }
            ]
        }
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [1.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [1.25, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
    )

    assert env.actions == ["move_forward", "stop"]
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == (
        "move_toward_memory"
    )


def test_memory_guided_frontier_inverts_habitat_compass_heading_sign() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "chair",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 2.0,
                    "confidence": 0.9,
                    "source": "forward-memory",
                }
            ]
        }
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [-0.5235987756],
            },
            {
                "depth": [[[0.9], [0.9], [0.9]], [[0.9], [0.9], [0.9]]],
                "gps": [0.0, 0.0],
                "compass": [-0.5235987756],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
    )

    assert env.actions == ["turn_left", "stop"]
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == (
        "turn_toward_memory"
    )


def test_memory_guided_frontier_falls_back_without_matching_anchor() -> None:
    anchors = load_official_memory_prior_from_payload(
        {
            "anchors": [
                {
                    "object_category": "sofa",
                    "scene_id": "depth-scene",
                    "x_m": 0.0,
                    "z_m": 2.0,
                    "confidence": 0.9,
                    "source": "wrong-category",
                }
            ]
        }
    )
    env = _FakeDepthOfficialObjectNavEnv(
        observations=[
            {
                "depth": [[[0.2], [0.2], [0.2]], [[0.2], [0.2], [0.2]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
            {
                "depth": [[[0.2], [0.2], [0.2]], [[0.2], [0.2], [0.2]]],
                "gps": [0.0, 0.0],
                "compass": [0.0],
            },
        ]
    )

    rows = run_official_objectnav_episode_loop(
        env,
        policy="memory_guided_frontier",
        max_episodes=1,
        max_steps=2,
        memory_anchors=anchors,
    )

    assert env.actions[0] in {"turn_left", "turn_right"}
    assert rows[0]["policy_debug"]["memory_prior"]["decision"] == (
        "fallback_occupancy_frontier"
    )
    assert rows[0]["policy_debug"]["memory_prior"]["fallback_reason"] == (
        "no_matching_memory"
    )


class _FakeOfficialObjectNavEnv:
    def __init__(self, metrics_by_episode: list[dict[str, float]]) -> None:
        self.metrics_by_episode = metrics_by_episode
        self.episode_index = -1
        self.episode_over = False
        self.current_episode = SimpleNamespace(episode_id="")
        self.get_metrics_calls = 0

    def reset(self) -> dict[str, object]:
        self.episode_index += 1
        self.episode_over = False
        self.current_episode = SimpleNamespace(
            episode_id=f"episode-{self.episode_index}",
            scene_id=f"scene-{self.episode_index}",
            object_category="chair",
        )
        return {"objectgoal": 0}

    def step(self, action: str) -> dict[str, object]:
        if action == "stop":
            self.episode_over = True
        return {"objectgoal": 0}

    def get_metrics(self) -> dict[str, float]:
        self.get_metrics_calls += 1
        return self.metrics_by_episode[self.episode_index]


class _FakeDepthOfficialObjectNavEnv:
    def __init__(self, observations: list[dict[str, object]]) -> None:
        self.observations = observations
        self.episode_over = False
        self.current_episode = SimpleNamespace(
            episode_id="depth-episode",
            scene_id="depth-scene",
            object_category="chair",
        )
        self.actions: list[str] = []
        self.step_index = 0

    def reset(self) -> dict[str, object]:
        self.episode_over = False
        self.actions = []
        self.step_index = 0
        return self.observations[0]

    def step(self, action: str) -> dict[str, object]:
        self.actions.append(action)
        if action == "stop":
            self.episode_over = True
        self.step_index += 1
        return self.observations[min(self.step_index, len(self.observations) - 1)]

    def get_metrics(self) -> dict[str, float]:
        return {
            "success": 0.0,
            "spl": 0.0,
            "soft_spl": 0.0,
            "distance_to_goal": 1.0,
        }


class _FakeHabitatFollower:
    def __init__(self, actions: list[object]) -> None:
        self.actions = list(actions)
        self.requested_goals: list[tuple[float, float, float]] = []

    def get_next_action(self, goal_position: object) -> object:
        self.requested_goals.append(tuple(float(value) for value in goal_position))
        return self.actions.pop(0) if self.actions else None


class _FakeHabitatSim:
    def __init__(self, position: tuple[float, float, float]) -> None:
        self.state = SimpleNamespace(position=position)

    def get_agent_state(self) -> SimpleNamespace:
        return self.state


class _FakePathfinderSuffixController:
    def __init__(
        self,
        *,
        actions: list[str],
        goal_position: tuple[float, float, float] | None,
    ) -> None:
        self.actions = list(actions)
        self.goal_position = goal_position
        self.next_action_calls = 0
        self.requested_goal_positions: list[tuple[float, float, float]] = []

    def select_goal_position(self) -> tuple[float, float, float] | None:
        return self.goal_position

    def next_action(self, goal_position: tuple[float, float, float]) -> str | None:
        self.next_action_calls += 1
        self.requested_goal_positions.append(
            tuple(float(value) for value in goal_position)
        )
        if not self.actions:
            return "stop"
        return self.actions.pop(0)


class _FakeDDPPOBackend:
    def __init__(self, *, action_ids: list[int]) -> None:
        self.action_ids = list(action_ids)
        self.calls: list[dict[str, object]] = []
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def act(self, *, depth: object, pointgoal_with_gps_compass: object) -> int:
        self.calls.append(
            {
                "depth": np.asarray(depth),
                "pointgoal_with_gps_compass": list(pointgoal_with_gps_compass),
            }
        )
        if not self.action_ids:
            return 0
        return self.action_ids.pop(0)


class _StaticDetector:
    def __init__(self, detections: list[Detection]) -> None:
        self.detections = detections
        self.call_count = 0

    def detect(self, rgb: np.ndarray) -> list[Detection]:
        self.call_count += 1
        assert rgb.dtype == np.uint8
        return list(self.detections)


class _SequenceDetector:
    def __init__(self, detections_by_call: list[list[Detection]]) -> None:
        self.detections_by_call = detections_by_call
        self.call_count = 0

    def detect(self, rgb: np.ndarray) -> list[Detection]:
        assert rgb.dtype == np.uint8
        index = min(self.call_count, len(self.detections_by_call) - 1)
        self.call_count += 1
        return list(self.detections_by_call[index])


def _write_local_action_model(path) -> object:
    payload = {
        "task": "habitat_official_local_action_logistic_model",
        "model_type": "logistic_regression",
        "label_name": "next_target_visible",
        "feature_names": [
            "action_turn_left",
            "action_move_forward",
            "action_turn_right",
        ],
        "weights": [5.0, 0.0, -5.0],
        "bias": 0.0,
        "preprocessing": {
            "feature_means": {
                "action_turn_left": 0.0,
                "action_move_forward": 0.0,
                "action_turn_right": 0.0,
            },
            "feature_scales": {
                "action_turn_left": 1.0,
                "action_move_forward": 1.0,
                "action_turn_right": 1.0,
            },
            "missing_value_count": 0,
            "warnings": [],
        },
        "dataset": {
            "example_count": 3,
            "positive_count": 1,
            "negative_count": 2,
        },
        "metrics": {
            "accuracy": 1.0,
            "example_count": 3,
            "positive_count": 1,
            "negative_count": 2,
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_temporal_local_action_model(path) -> object:
    feature_names = [
        "action_move_forward",
        "action_turn_left__recent_target_visible_count",
        "action_move_forward__recent_target_visible_count",
    ]
    payload = {
        "task": "habitat_official_local_action_logistic_model",
        "model_type": "logistic_regression",
        "label_name": "next_target_visible",
        "feature_names": feature_names,
        "weights": [1.0, 1.0, -1.0],
        "bias": 0.0,
        "preprocessing": {
            "feature_means": {name: 0.0 for name in feature_names},
            "feature_scales": {name: 1.0 for name in feature_names},
            "missing_value_count": 0,
            "warnings": [],
        },
        "dataset": {
            "example_count": 3,
            "positive_count": 1,
            "negative_count": 2,
        },
        "metrics": {
            "accuracy": 1.0,
            "example_count": 3,
            "positive_count": 1,
            "negative_count": 2,
        },
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path
