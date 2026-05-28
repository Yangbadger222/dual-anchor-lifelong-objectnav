from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from objectnav_core.evaluation import habitat_objectnav_rgb_noise_stress as stress
from objectnav_core.memory.usability import EvidenceType
from objectnav_core.memory.usability import DecisionType
from objectnav_core.perception.yolo_world_adapter import Detection


def test_importing_rgb_noise_stress_does_not_import_habitat_or_ultralytics() -> None:
    assert "habitat" not in sys.modules
    assert "habitat_sim" not in sys.modules
    assert "ultralytics" not in sys.modules
    assert "transformers" not in sys.modules


def test_preflight_writes_summary_for_rgb_noise_stress(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean", "mild"),
        detector="yolo_world",
        detector_weights="yolov8s-worldv2.pt",
        detector_conf=0.25,
        memory_ablation=("on", "off"),
        seed=313,
    )

    assert summary["task"] == "habitat_objectnav_rgb_noise_stress_preflight"
    assert summary["detector"] == "yolo_world"
    assert summary["yolo_prompt_mode"] == "target"
    assert summary["stop_on_trust"] is True
    assert summary["sensor_width"] == 640
    assert summary["sensor_height"] == 480
    assert summary["sensor_resolution"] == "640x480"
    assert summary["episodes_per_category"] is None
    assert summary["category_filter"] == [
        "bed",
        "chair",
        "plant",
        "sofa",
        "toilet",
        "tv_monitor",
    ]
    assert summary["target_categories"] == [
        "bed",
        "chair",
        "plant",
        "sofa",
        "toilet",
        "tv_monitor",
    ]
    assert summary["noise_levels"] == ["clean", "mild"]
    assert summary["memory_ablation"] == ["on", "off"]
    assert summary["out_and_back_action_count"] > 6
    assert (tmp_path / "summary.json").exists()
    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == summary


def test_preflight_accepts_naive_count_memory_baseline(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="oracle_bbox",
        detector_weights="unused",
        detector_conf=0.25,
        memory_ablation=("naive_count",),
        seed=313,
    )

    assert "naive_count" in stress.SUPPORTED_MEMORY_ABLATIONS
    assert summary["memory_ablation"] == ["naive_count"]


def test_preflight_records_gate_rejection_debug_export_config(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on", "naive_count"),
        seed=313,
        debug_export_gate_rejections=True,
        debug_export_categories=("plant", "tv_monitor"),
        debug_export_limit_per_category=12,
    )

    assert summary["debug_export_gate_rejections"] is True
    assert summary["debug_export_categories"] == ["plant", "tv_monitor"]
    assert summary["debug_export_limit_per_category"] == 12


def test_preflight_records_trace_filtered_debug_export_config(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on",),
        seed=313,
        debug_export_categories=("bed",),
        debug_export_replay_phases=("depart", "non_confirm"),
        debug_export_evidence_types=("positive",),
    )

    assert summary["debug_export_replay_phases"] == ["depart", "non_confirm"]
    assert summary["debug_export_evidence_types"] == ["positive"]


def test_preflight_records_structured_episode_selection_config(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on", "naive_count"),
        seed=313,
        episode_selection_strategy="structured_visibility",
        structured_min_goal_viewpoints=3,
        structured_min_geodesic_distance=2.0,
        structured_min_path_complexity_ratio=1.25,
    )

    assert summary["episode_selection_strategy"] == "structured_visibility"
    assert summary["structured_min_goal_viewpoints"] == 3
    assert summary["structured_min_geodesic_distance"] == 2.0
    assert summary["structured_min_path_complexity_ratio"] == 1.25


def test_preflight_records_visibility_challenge_replay_protocol(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on", "naive_count"),
        seed=313,
        replay_protocol="visibility_challenge",
    )

    assert "visibility_challenge" in stress.SUPPORTED_REPLAY_PROTOCOLS
    assert summary["replay_protocol"] == "visibility_challenge"
    assert summary["revisit_strategy"] == "visibility_challenge"


def test_preflight_records_geodesic_path_replay_protocol(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on", "naive_count"),
        seed=313,
        replay_protocol="geodesic_path",
        geodesic_path_max_steps=12,
    )

    assert "geodesic_path" in stress.SUPPORTED_REPLAY_PROTOCOLS
    assert summary["replay_protocol"] == "geodesic_path"
    assert summary["geodesic_path_max_steps"] == 12
    assert "approach" in summary["replay_phases"]


def test_preflight_records_expected_empty_challenge_replay_protocol(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on", "naive_count"),
        seed=313,
        replay_protocol="expected_empty_challenge",
    )

    assert "expected_empty_challenge" in stress.SUPPORTED_REPLAY_PROTOCOLS
    assert summary["replay_protocol"] == "expected_empty_challenge"
    assert "expected_empty" in summary["replay_phases"]


def test_preflight_records_geodesic_expected_empty_replay_protocol(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on", "naive_count"),
        seed=313,
        replay_protocol="geodesic_expected_empty_challenge",
        geodesic_path_max_steps=12,
    )

    assert "geodesic_expected_empty_challenge" in stress.SUPPORTED_REPLAY_PROTOCOLS
    assert summary["replay_protocol"] == "geodesic_expected_empty_challenge"
    assert summary["geodesic_path_max_steps"] == 12
    assert "approach" in summary["replay_phases"]
    assert "expected_empty" in summary["replay_phases"]


def test_preflight_records_memory_geometry_gate_radius(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on", "naive_count"),
        seed=313,
        memory_geometry_gate_radius_m=1.5,
    )

    assert summary["memory_geometry_gate_radius_m"] == 1.5


def test_gate_rejection_debug_export_condition_is_category_scoped() -> None:
    categories = {"plant", "tv_monitor"}

    assert stress._should_export_gate_rejection_debug(
        object_category="tv_monitor",
        decision=DecisionType.TRUST,
        gated_decision=DecisionType.VERIFY,
        debug_categories=categories,
    )
    assert not stress._should_export_gate_rejection_debug(
        object_category="toilet",
        decision=DecisionType.TRUST,
        gated_decision=DecisionType.VERIFY,
        debug_categories=categories,
    )
    assert not stress._should_export_gate_rejection_debug(
        object_category="plant",
        decision=DecisionType.VERIFY,
        gated_decision=DecisionType.VERIFY,
        debug_categories=categories,
    )


def test_trace_filtered_debug_export_condition_matches_hidden_positive_rows() -> None:
    categories = {"bed"}
    replay_phases = {"depart", "non_confirm"}
    evidence_types = {"positive"}

    assert stress._should_export_debug_png(
        object_category="bed",
        decision=DecisionType.VERIFY,
        gated_decision=DecisionType.VERIFY,
        replay_phase="non_confirm",
        evidence_type=EvidenceType.POSITIVE,
        debug_categories=categories,
        debug_export_gate_rejections=False,
        debug_export_replay_phases=replay_phases,
        debug_export_evidence_types=evidence_types,
    )
    assert not stress._should_export_debug_png(
        object_category="bed",
        decision=DecisionType.VERIFY,
        gated_decision=DecisionType.VERIFY,
        replay_phase="confirm",
        evidence_type=EvidenceType.POSITIVE,
        debug_categories=categories,
        debug_export_gate_rejections=False,
        debug_export_replay_phases=replay_phases,
        debug_export_evidence_types=evidence_types,
    )
    assert not stress._should_export_debug_png(
        object_category="bed",
        decision=DecisionType.VERIFY,
        gated_decision=DecisionType.VERIFY,
        replay_phase="non_confirm",
        evidence_type=EvidenceType.UNKNOWN,
        debug_categories=categories,
        debug_export_gate_rejections=False,
        debug_export_replay_phases=replay_phases,
        debug_export_evidence_types=evidence_types,
    )
    assert not stress._should_export_debug_png(
        object_category="plant",
        decision=DecisionType.VERIFY,
        gated_decision=DecisionType.VERIFY,
        replay_phase="non_confirm",
        evidence_type=EvidenceType.POSITIVE,
        debug_categories=categories,
        debug_export_gate_rejections=False,
        debug_export_replay_phases=replay_phases,
        debug_export_evidence_types=evidence_types,
    )


def test_debug_export_condition_preserves_gate_rejection_mode() -> None:
    assert stress._should_export_debug_png(
        object_category="tv_monitor",
        decision=DecisionType.TRUST,
        gated_decision=DecisionType.VERIFY,
        replay_phase="confirm",
        evidence_type=EvidenceType.UNKNOWN,
        debug_categories={"tv_monitor"},
        debug_export_gate_rejections=True,
        debug_export_replay_phases=set(),
        debug_export_evidence_types=set(),
    )


def test_write_gate_rejection_debug_png_creates_visual_artifact(tmp_path: Path) -> None:
    rgb = np.zeros((24, 32, 3), dtype=np.uint8)
    rgb[:, :, 1] = 120
    noisy_rgb = rgb.copy()
    oracle_mask = np.zeros((24, 32), dtype=bool)
    oracle_mask[6:16, 4:14] = True
    detector_mask = np.zeros((24, 32), dtype=bool)
    detector_mask[5:18, 12:28] = True
    detection = Detection(
        category="plant",
        bbox=(12, 5, 28, 18),
        confidence=0.77,
        mask=detector_mask,
    )

    png_path = stress._write_gate_rejection_debug_png(
        output_dir=tmp_path,
        rgb=rgb,
        noisy_rgb=noisy_rgb,
        oracle_mask=oracle_mask,
        detector_mask=detector_mask,
        detections=[detection],
        metadata={
            "object_category": "plant",
            "memory_mode": "on",
            "noise_level": "clean",
            "episode_index": 3,
            "episode_id": "episode-3",
            "step_index": 4,
            "action": "turn_left",
            "decision_gate_reason": "target_not_currently_visible",
            "raw_decision": "trust",
            "decision": "verify",
            "target_visible": False,
            "evidence_type": "unknown",
            "oracle_target_pixels": 100,
            "detector_target_pixels": 208,
            "detector_precision": 0.1,
            "oracle_recall": 0.2,
            "oracle_bbox": "4,6,14,16",
            "detection_conf_max": 0.77,
        },
        sequence_id=0,
    )

    assert png_path.exists()
    assert png_path.suffix == ".png"
    assert png_path.stat().st_size > 0


def test_detector_mask_filters_over_broad_detector_boxes() -> None:
    large_mask = np.ones((20, 30), dtype=bool)
    small_mask = np.zeros((20, 30), dtype=bool)
    small_mask[3:9, 4:12] = True
    detections = [
        Detection("tv monitor", (0, 0, 30, 20), 0.42, large_mask),
        Detection("tv monitor", (4, 3, 12, 9), 0.61, small_mask),
    ]
    adapter = _StaticDetector(detections)

    mask, kept, filtered_count = stress._detector_mask(
        detector="grounding_dino",
        detector_adapter=adapter,
        noisy_rgb=np.zeros((20, 30, 3), dtype=np.uint8),
        oracle_mask=np.zeros((20, 30), dtype=bool),
        target_category="tv_monitor",
        accepted_detection_labels={"tv monitor"},
        max_detection_area_ratio=0.7,
    )

    assert kept == [detections[1]]
    assert filtered_count == 1
    assert np.array_equal(mask, small_mask)


def test_detector_mask_keeps_over_broad_boxes_when_filter_disabled() -> None:
    large_mask = np.ones((20, 30), dtype=bool)
    detection = Detection("tv monitor", (0, 0, 30, 20), 0.42, large_mask)
    adapter = _StaticDetector([detection])

    mask, kept, filtered_count = stress._detector_mask(
        detector="grounding_dino",
        detector_adapter=adapter,
        noisy_rgb=np.zeros((20, 30, 3), dtype=np.uint8),
        oracle_mask=np.zeros((20, 30), dtype=bool),
        target_category="tv_monitor",
        accepted_detection_labels={"tv monitor"},
        max_detection_area_ratio=None,
    )

    assert kept == [detection]
    assert filtered_count == 0
    assert np.array_equal(mask, large_mask)


def test_detector_mask_drops_frame_when_union_area_is_over_broad() -> None:
    upper_mask = np.zeros((20, 30), dtype=bool)
    upper_mask[:12, :] = True
    lower_mask = np.zeros((20, 30), dtype=bool)
    lower_mask[8:, :] = True
    detections = [
        Detection("tv monitor", (0, 0, 30, 12), 0.42, upper_mask),
        Detection("tv monitor", (0, 8, 30, 20), 0.39, lower_mask),
    ]
    adapter = _StaticDetector(detections)

    mask, kept, filtered_count = stress._detector_mask(
        detector="grounding_dino",
        detector_adapter=adapter,
        noisy_rgb=np.zeros((20, 30, 3), dtype=np.uint8),
        oracle_mask=np.zeros((20, 30), dtype=bool),
        target_category="tv_monitor",
        accepted_detection_labels={"tv monitor"},
        max_detection_area_ratio=0.7,
    )

    assert kept == []
    assert filtered_count == 2
    assert not mask.any()


def test_detection_anchor_projection_uses_depth_and_agent_yaw() -> None:
    detector_mask = np.zeros((4, 4), dtype=bool)
    detector_mask[1:3, 1:3] = True
    depth = np.full((4, 4), 2.0, dtype=np.float32)

    anchor = stress._estimate_detection_anchor_xz(
        detector_mask=detector_mask,
        depth=depth,
        agent_pose=((1.0, 0.0, 3.0), (0.0, 0.0, 0.0, 1.0)),
        hfov_degrees=90.0,
    )

    assert anchor is not None
    assert anchor[0] == 1.0
    assert anchor[1] == 1.0


def test_memory_geometry_gate_quarantines_far_positive_after_anchor_birth() -> None:
    state = stress.MemoryGeometryState(anchor_x=0.0, anchor_z=0.0)

    updated_state, evidence_type, strength, quarantined, reason, distance = (
        stress._apply_memory_geometry_gate(
            state=state,
            memory_mode="on",
            evidence_type=EvidenceType.POSITIVE,
            evidence_strength=1.0,
            quarantined=False,
            evidence_reason="detector_positive_mask",
            observation_anchor_xz=(3.0, 0.0),
            gate_radius_m=1.5,
        )
    )

    assert updated_state == state
    assert evidence_type is EvidenceType.UNKNOWN
    assert strength == 0.35
    assert quarantined is True
    assert reason == "geometry_inconsistent_positive"
    assert distance == 3.0


def test_memory_geometry_gate_quarantines_positive_when_anchor_is_behind_camera() -> None:
    state = stress.MemoryGeometryState(anchor_x=0.0, anchor_z=-2.0)

    updated_state, evidence_type, strength, quarantined, reason, distance = (
        stress._apply_memory_geometry_gate(
            state=state,
            memory_mode="on",
            evidence_type=EvidenceType.POSITIVE,
            evidence_strength=1.0,
            quarantined=False,
            evidence_reason="detector_positive_mask",
            observation_anchor_xz=(0.1, -1.8),
            gate_radius_m=1.5,
            agent_pose=((0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0)),
            hfov_degrees=90.0,
        )
    )

    assert updated_state == state
    assert evidence_type is EvidenceType.UNKNOWN
    assert strength == 0.35
    assert quarantined is True
    assert reason == "geometry_anchor_out_of_view_positive"
    assert distance is not None


def test_memory_geometry_gate_can_run_fov_without_distance_radius() -> None:
    state = stress.MemoryGeometryState(anchor_x=0.0, anchor_z=-2.0)

    _, evidence_type, _, quarantined, reason, distance = (
        stress._apply_memory_geometry_gate(
            state=state,
            memory_mode="on",
            evidence_type=EvidenceType.POSITIVE,
            evidence_strength=1.0,
            quarantined=False,
            evidence_reason="detector_positive_mask",
            observation_anchor_xz=(0.1, -1.8),
            gate_radius_m=None,
            gate_fov=True,
            agent_pose=((0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0)),
            hfov_degrees=90.0,
        )
    )

    assert evidence_type is EvidenceType.UNKNOWN
    assert quarantined is True
    assert reason == "geometry_anchor_out_of_view_positive"
    assert distance is not None


def test_memory_geometry_gate_can_defer_fov_during_anchor_acquisition() -> None:
    state = stress.MemoryGeometryState(anchor_x=0.0, anchor_z=-2.0)

    _, evidence_type, strength, quarantined, reason, distance = (
        stress._apply_memory_geometry_gate(
            state=state,
            memory_mode="on",
            evidence_type=EvidenceType.POSITIVE,
            evidence_strength=1.0,
            quarantined=False,
            evidence_reason="detector_positive_mask",
            observation_anchor_xz=(0.1, -1.8),
            gate_radius_m=None,
            gate_fov=True,
            fov_gate_active=False,
            agent_pose=((0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0)),
            hfov_degrees=90.0,
        )
    )

    assert evidence_type is EvidenceType.POSITIVE
    assert strength == 1.0
    assert quarantined is False
    assert reason == "detector_positive_mask"
    assert distance is not None


def test_memory_geometry_gate_can_turn_expected_empty_out_of_fov_positive_negative() -> None:
    state = stress.MemoryGeometryState(anchor_x=0.0, anchor_z=-2.0)

    _, evidence_type, strength, quarantined, reason, distance = (
        stress._apply_memory_geometry_gate(
            state=state,
            memory_mode="on",
            evidence_type=EvidenceType.POSITIVE,
            evidence_strength=1.0,
            quarantined=False,
            evidence_reason="detector_positive_mask",
            observation_anchor_xz=(0.1, -1.8),
            gate_radius_m=None,
            gate_fov=True,
            fov_rejection_evidence_type=EvidenceType.NON_CONFIRMATION,
            agent_pose=((0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0)),
            hfov_degrees=90.0,
        )
    )

    assert evidence_type is EvidenceType.NON_CONFIRMATION
    assert strength == 1.0
    assert quarantined is False
    assert reason == "geometry_anchor_out_of_view_positive"
    assert distance is not None


def test_anchor_in_camera_fov_uses_agent_yaw_and_hfov() -> None:
    pose = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))

    assert stress._anchor_in_camera_fov(
        anchor_xz=(0.0, -2.0),
        agent_pose=pose,
        hfov_degrees=90.0,
    )
    assert not stress._anchor_in_camera_fov(
        anchor_xz=(0.0, 2.0),
        agent_pose=pose,
        hfov_degrees=90.0,
    )


def test_memory_geometry_gate_does_not_change_naive_count_or_disabled_runs() -> None:
    state = stress.MemoryGeometryState(anchor_x=0.0, anchor_z=0.0)

    for memory_mode, gate_radius, gate_fov in (
        ("naive_count", 1.5, True),
        ("on", None, False),
    ):
        _, evidence_type, strength, quarantined, reason, distance = (
            stress._apply_memory_geometry_gate(
                state=state,
                memory_mode=memory_mode,
                evidence_type=EvidenceType.POSITIVE,
                evidence_strength=1.0,
                quarantined=False,
                evidence_reason="detector_positive_mask",
                observation_anchor_xz=(3.0, 0.0),
                gate_radius_m=gate_radius,
                gate_fov=gate_fov,
            )
        )

        assert evidence_type is EvidenceType.POSITIVE
        assert strength == 1.0
        assert quarantined is False
        assert reason == "detector_positive_mask"
        assert distance is None


def test_memory_object_instance_key_prefers_closest_goal_object_id() -> None:
    episode = _Episode("39", "toilet")
    episode.info = {"closest_goal_object_id": 51}

    assert (
        stress._memory_object_instance_id(episode)
        == "goal_object:51"
    )


def test_memory_object_instance_key_falls_back_to_episode_id() -> None:
    episode = _Episode("synthetic-episode", "plant")
    episode.info = {}

    assert (
        stress._memory_object_instance_id(episode)
        == "episode:synthetic-episode"
    )


def test_memory_geometry_state_loads_and_saves_only_for_memory_on(tmp_path: Path) -> None:
    memory = stress.LifelongMemoryHarness(tmp_path / "memory.sqlite")
    episode = _Episode("39", "toilet")
    episode.original_scene_id = "scene-a"
    episode.info = {"closest_goal_object_id": 51}

    memory.save_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version=stress.DATASET_VERSION,
        category="toilet",
        instance_id="goal_object:51",
        anchor_x=0.5,
        anchor_z=-1.5,
    )

    assert stress._load_memory_geometry_state(
        memory=memory,
        episode=episode,
        memory_mode="on",
    ) == stress.MemoryGeometryState(anchor_x=0.5, anchor_z=-1.5)
    assert stress._load_memory_geometry_state(
        memory=memory,
        episode=episode,
        memory_mode="naive_count",
    ) == stress.MemoryGeometryState()

    updated = stress.MemoryGeometryState(anchor_x=2.0, anchor_z=-3.0)
    stress._save_memory_geometry_state(
        memory=memory,
        episode=episode,
        memory_mode="naive_count",
        state=updated,
    )
    assert memory.load_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version=stress.DATASET_VERSION,
        category="toilet",
        instance_id="goal_object:51",
    ) == (0.5, -1.5)

    stress._save_memory_geometry_state(
        memory=memory,
        episode=episode,
        memory_mode="on",
        state=updated,
    )
    assert memory.load_object_instance_anchor(
        scene_id="scene-a",
        episode_dataset_version=stress.DATASET_VERSION,
        category="toilet",
        instance_id="goal_object:51",
    ) == (2.0, -3.0)


def test_naive_count_baseline_only_accumulates_positive_evidence() -> None:
    state = stress.NaiveCountState()

    state, belief = stress._naive_count_belief(state, EvidenceType.POSITIVE)
    assert state.positive_count == 1
    assert belief.p_valid < stress.NAIVE_COUNT_TRUST_P_VALID
    first_positive_p_valid = belief.p_valid

    state, belief = stress._naive_count_belief(state, EvidenceType.UNKNOWN)
    assert state.positive_count == 1
    assert belief.p_valid == first_positive_p_valid

    state, belief = stress._naive_count_belief(state, EvidenceType.NON_CONFIRMATION)
    assert state.positive_count == 1
    assert belief.p_valid == first_positive_p_valid

    state, belief = stress._naive_count_belief(state, EvidenceType.POSITIVE)
    assert state.positive_count == 2
    assert belief.p_valid >= stress.NAIVE_COUNT_TRUST_P_VALID
    assert belief.p_valid >= first_positive_p_valid


def test_memory_on_delays_birth_until_first_positive_evidence() -> None:
    updater = stress.UsabilityUpdater()
    belief = stress.INITIAL_BELIEF
    candidate_born = False

    for evidence_type in (
        EvidenceType.UNKNOWN,
        EvidenceType.NON_CONFIRMATION,
        EvidenceType.FREE,
    ):
        candidate_born, belief = stress._memory_on_belief_update(
            candidate_born=candidate_born,
            belief=belief,
            event=stress.EvidenceEvent(evidence_type),
            updater=updater,
        )

    assert candidate_born is False
    assert belief == stress.INITIAL_BELIEF

    candidate_born, belief = stress._memory_on_belief_update(
        candidate_born=candidate_born,
        belief=belief,
        event=stress.EvidenceEvent(EvidenceType.POSITIVE),
        updater=updater,
    )

    assert candidate_born is True
    assert belief.p_valid > stress.INITIAL_BELIEF.p_valid


def test_memory_on_applies_negative_evidence_after_birth() -> None:
    updater = stress.UsabilityUpdater()
    belief = stress.MemoryBelief(
        p_existence=0.98,
        p_location_valid=0.95,
        p_usable=0.95,
    )

    candidate_born, updated = stress._memory_on_belief_update(
        candidate_born=True,
        belief=belief,
        event=stress.EvidenceEvent(EvidenceType.NON_CONFIRMATION),
        updater=updater,
    )

    assert candidate_born is True
    assert updated.p_existence == belief.p_existence
    assert updated.p_location_valid < belief.p_location_valid
    assert updated.p_usable < belief.p_usable


def test_preflight_accepts_grounding_dino_detector(tmp_path: Path) -> None:
    summary = stress.run_rgb_noise_stress_preflight(
        output_dir=tmp_path,
        rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
        depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
        noise_levels=("clean",),
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        memory_ablation=("on",),
        seed=313,
        grounding_dino_text_threshold=0.2,
        grounding_dino_max_image_side=640,
    )

    assert "grounding_dino" in stress.SUPPORTED_DETECTORS
    assert summary["detector"] == "grounding_dino"
    assert summary["detector_weights"] == "IDEA-Research/grounding-dino-tiny"
    assert summary["grounding_dino_text_threshold"] == 0.2
    assert summary["grounding_dino_max_image_side"] == 640


def test_default_yolo_prompting_is_target_conditioned() -> None:
    assert stress.DEFAULT_SENSOR_WIDTH == 640
    assert stress.DEFAULT_SENSOR_HEIGHT == 480
    assert stress.DEFAULT_YOLO_PROMPT_MODE == "target"
    assert stress.DEFAULT_STOP_ON_TRUST is True
    assert stress._yolo_prompt_categories("toilet", "target") == ("toilet",)
    assert stress._yolo_prompt_categories("tv_monitor", "target") == ("tv monitor",)
    assert stress._yolo_prompt_categories("toilet", "all_categories") == (
        "bed",
        "chair",
        "plant",
        "sofa",
        "toilet",
        "tv monitor",
    )
    assert "white toilet" in stress._accepted_yolo_detection_labels(
        "toilet",
        "target_aliases",
    )


def test_detector_adapter_cache_supports_grounding_dino() -> None:
    cache: dict[tuple[str, tuple[str, ...]], object] = {}

    adapter = stress._detector_for_target(
        detector_cache=cache,
        detector="grounding_dino",
        detector_weights="IDEA-Research/grounding-dino-tiny",
        detector_conf=0.25,
        grounding_dino_text_threshold=0.2,
        grounding_dino_max_image_side=640,
        target_category="tv_monitor",
        yolo_prompt_mode="target",
        detector_factory=lambda **kwargs: kwargs,
    )

    assert adapter == {
        "model_id": "IDEA-Research/grounding-dino-tiny",
        "categories": ["tv monitor"],
        "conf": 0.25,
        "text_threshold": 0.2,
        "max_image_side": 640,
        "device": "auto",
    }
    assert list(cache) == [("grounding_dino", ("tv monitor",))]


def test_sensor_resolution_prefers_explicit_rectangular_dimensions() -> None:
    assert stress._resolve_sensor_resolution(
        sensor_size=None,
        sensor_width=1280,
        sensor_height=720,
    ) == (720, 1280)
    assert stress._resolve_sensor_resolution(
        sensor_size=320,
        sensor_width=1280,
        sensor_height=720,
    ) == (320, 320)


def test_select_episodes_balances_by_category() -> None:
    episodes = [
        _Episode("p1", "plant"),
        _Episode("t1", "toilet"),
        _Episode("p2", "plant"),
        _Episode("c1", "chair"),
        _Episode("t2", "toilet"),
        _Episode("c2", "chair"),
    ]

    selected = stress._select_episodes(
        episodes,
        target_categories=("toilet", "plant"),
        episodes_per_category=1,
        max_episodes=None,
    )

    assert [episode.episode_id for episode in selected] == ["p1", "t1"]
    assert stress._category_counts(selected) == {"plant": 1, "toilet": 1}


def test_structured_episode_selection_prefers_multiview_complex_paths() -> None:
    episodes = [
        _Episode(
            "p-flat",
            "plant",
            goal_viewpoints=1,
            geodesic_distance=1.0,
            euclidean_distance=1.0,
        ),
        _Episode(
            "p-structured",
            "plant",
            goal_viewpoints=4,
            geodesic_distance=6.0,
            euclidean_distance=2.0,
        ),
        _Episode(
            "t-flat",
            "toilet",
            goal_viewpoints=2,
            geodesic_distance=1.5,
            euclidean_distance=1.5,
        ),
        _Episode(
            "t-structured",
            "toilet",
            goal_viewpoints=3,
            geodesic_distance=5.0,
            euclidean_distance=2.0,
        ),
    ]

    selected = stress._select_episodes(
        episodes,
        target_categories=("toilet", "plant"),
        episodes_per_category=1,
        max_episodes=None,
        episode_selection_strategy="structured_visibility",
        structured_min_goal_viewpoints=2,
        structured_min_geodesic_distance=2.0,
        structured_min_path_complexity_ratio=1.2,
    )

    assert [episode.episode_id for episode in selected] == [
        "t-structured",
        "p-structured",
    ]
    report = stress._episode_selection_summary(
        all_episodes=episodes,
        selected_episodes=selected,
        target_categories=("toilet", "plant"),
        episode_selection_strategy="structured_visibility",
        structured_min_goal_viewpoints=2,
        structured_min_geodesic_distance=2.0,
        structured_min_path_complexity_ratio=1.2,
    )
    assert report["candidate_episode_count"] == 2
    assert report["dropped_by_structured_filter_count"] == 2
    assert report["selected_episode_ids"] == ["t-structured", "p-structured"]


def test_episode_selection_summary_reports_zero_structured_categories() -> None:
    episodes = [
        _Episode(
            "sofa-flat",
            "sofa",
            goal_viewpoints=2,
            geodesic_distance=2.0,
            euclidean_distance=2.0,
        ),
        _Episode(
            "plant-structured",
            "plant",
            goal_viewpoints=3,
            geodesic_distance=5.0,
            euclidean_distance=2.0,
        ),
    ]

    report = stress._episode_selection_summary(
        all_episodes=episodes,
        selected_episodes=[episodes[1]],
        target_categories=("sofa", "plant", "tv_monitor"),
        episode_selection_strategy="structured_visibility",
        structured_min_goal_viewpoints=2,
        structured_min_geodesic_distance=2.0,
        structured_min_path_complexity_ratio=1.2,
    )

    assert report["zero_structured_candidate_categories"] == ["sofa", "tv_monitor"]
    assert report["category_audit"]["sofa"] == {
        "category_candidate_episode_count": 1,
        "structured_candidate_episode_count": 0,
        "candidate_episode_count": 0,
        "selected_episode_count": 0,
        "selected_episode_ids": [],
        "dropped_by_structured_filter_count": 1,
        "selection_status": "no_structured_candidates",
    }
    assert report["category_audit"]["plant"]["selection_status"] == "selected"
    assert report["category_audit"]["tv_monitor"]["selection_status"] == (
        "no_category_candidates"
    )


def test_replay_phase_partitions_out_and_back_trace() -> None:
    phases = [stress._replay_phase(step_index, total_steps=15) for step_index in range(15)]

    assert phases == (
        ["confirm"] * 3
        + ["depart"] * 4
        + ["non_confirm"] * 4
        + ["revisit"] * 4
    )
    assert stress._replay_phase(0, total_steps=1) == "confirm"


def test_visibility_challenge_replay_steps_use_visible_and_hidden_views() -> None:
    visible = stress.ReplayViewCandidate(
        source="goal_viewpoint:0",
        position=(1.0, 0.0, 1.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        target_pixels=240,
    )
    hidden = stress.ReplayViewCandidate(
        source="goal_viewpoint:0_turn_around",
        position=(1.0, 0.0, 1.0),
        rotation=(0.0, 1.0, 0.0, 0.0),
        target_pixels=0,
    )

    steps = stress._visibility_challenge_replay_steps(
        (hidden, visible),
        min_target_pixels=24,
    )

    assert [step.phase for step in steps] == (
        ["confirm"] * 3
        + ["depart"] * 2
        + ["non_confirm"] * 4
        + ["revisit"] * 4
    )
    assert all(step.target_pixels >= 24 for step in steps if step.phase in {"confirm", "revisit"})
    assert all(step.target_pixels < 24 for step in steps if step.phase in {"depart", "non_confirm"})
    assert {step.source for step in steps if step.phase == "confirm"} == {
        "goal_viewpoint:0"
    }
    assert {step.source for step in steps if step.phase == "non_confirm"} == {
        "goal_viewpoint:0_turn_around"
    }


def test_visibility_challenge_replay_steps_require_hidden_view() -> None:
    visible = stress.ReplayViewCandidate(
        source="goal_viewpoint:0",
        position=(1.0, 0.0, 1.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        target_pixels=240,
    )

    try:
        stress._visibility_challenge_replay_steps(
            (visible,),
            min_target_pixels=24,
        )
    except ValueError as exc:
        assert "target-hidden" in str(exc)
    else:
        raise AssertionError("visibility_challenge should require a target-hidden view")


def test_expected_empty_challenge_replay_steps_mark_expected_empty_context() -> None:
    visible = stress.ReplayViewCandidate(
        source="goal_viewpoint:0",
        position=(1.0, 0.0, 1.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        target_pixels=240,
    )
    hidden = stress.ReplayViewCandidate(
        source="goal_viewpoint:0_turn_around",
        position=(1.0, 0.0, 1.0),
        rotation=(0.0, 1.0, 0.0, 0.0),
        target_pixels=0,
    )

    steps = stress._expected_empty_challenge_replay_steps(
        (hidden, visible),
        min_target_pixels=24,
    )

    assert [step.phase for step in steps] == (
        ["confirm"] * 3
        + ["expected_empty"] * 4
        + ["revisit"] * 4
    )
    assert all(not step.expected_target_absent for step in steps if step.phase == "confirm")
    assert all(step.expected_target_absent for step in steps if step.phase == "expected_empty")
    assert all(not step.expected_target_absent for step in steps if step.phase == "revisit")
    assert {step.source for step in steps if step.phase == "expected_empty"} == {
        "goal_viewpoint:0_turn_around"
    }


def test_expected_empty_context_turns_empty_positive_miss_into_non_confirmation() -> None:
    evidence_type, strength, quarantined, reason = stress._apply_expected_empty_context(
        evidence_type=EvidenceType.UNKNOWN,
        evidence_strength=0.45,
        quarantined=False,
        evidence_reason="target_out_of_current_view",
        expected_target_absent=True,
        detector_positive=False,
        target_visible=False,
    )

    assert evidence_type is EvidenceType.NON_CONFIRMATION
    assert strength == 1.0
    assert quarantined is False
    assert reason == "expected_location_empty"


def test_expected_empty_context_preserves_detector_positive_evidence() -> None:
    evidence_type, strength, quarantined, reason = stress._apply_expected_empty_context(
        evidence_type=EvidenceType.POSITIVE,
        evidence_strength=1.2,
        quarantined=False,
        evidence_reason="detector_positive_mask",
        expected_target_absent=True,
        detector_positive=True,
        target_visible=False,
    )

    assert evidence_type is EvidenceType.POSITIVE
    assert strength == 1.2
    assert quarantined is False
    assert reason == "detector_positive_mask"


def test_resample_path_positions_keeps_endpoints_and_respects_limit() -> None:
    points = tuple((float(index), 0.0, 0.0) for index in range(10))

    sampled = stress._resample_path_positions(points, max_points=4)

    assert sampled[0] == points[0]
    assert sampled[-1] == points[-1]
    assert len(sampled) == 4


def test_geodesic_path_replay_steps_use_approach_then_goal_confirm() -> None:
    waypoints = (
        stress.ReplayViewCandidate(
            source="geodesic_path:waypoint:0",
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
            target_pixels=0,
        ),
        stress.ReplayViewCandidate(
            source="geodesic_path:waypoint:1",
            position=(1.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
            target_pixels=0,
        ),
    )
    goal = stress.ReplayViewCandidate(
        source="goal_viewpoint:0",
        position=(2.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        target_pixels=240,
    )

    steps = stress._geodesic_path_replay_steps(
        waypoints=waypoints,
        goal=goal,
        confirm_frames=3,
    )

    assert [step.phase for step in steps] == ["approach", "approach", "confirm", "confirm", "confirm"]
    assert [step.source for step in steps[-3:]] == ["goal_viewpoint:0"] * 3
    assert steps[0].action == "reset"
    assert steps[1].action == "teleport_approach"
    assert steps[-1].target_pixels == 240


def test_geodesic_expected_empty_replay_steps_add_hidden_then_revisit() -> None:
    waypoints = (
        stress.ReplayViewCandidate(
            source="geodesic_path:waypoint:0",
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
            target_pixels=0,
        ),
        stress.ReplayViewCandidate(
            source="geodesic_path:waypoint:1",
            position=(1.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
            target_pixels=12,
        ),
    )
    goal = stress.ReplayViewCandidate(
        source="goal_viewpoint:0",
        position=(2.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        target_pixels=240,
    )
    hidden = stress.ReplayViewCandidate(
        source="goal_viewpoint:0_turn_around",
        position=(2.0, 0.0, 0.0),
        rotation=(0.0, 1.0, 0.0, 0.0),
        target_pixels=0,
    )

    steps = stress._geodesic_expected_empty_challenge_replay_steps(
        waypoints=waypoints,
        goal=goal,
        hidden=hidden,
        confirm_frames=3,
        expected_empty_frames=4,
        revisit_frames=4,
    )

    assert [step.phase for step in steps] == (
        ["approach"] * 2
        + ["confirm"] * 3
        + ["expected_empty"] * 4
        + ["revisit"] * 4
    )
    assert steps[0].action == "reset"
    assert all(
        step.source == "goal_viewpoint:0"
        for step in steps
        if step.phase in {"confirm", "revisit"}
    )
    assert all(
        step.source == "goal_viewpoint:0_turn_around"
        for step in steps
        if step.phase == "expected_empty"
    )
    assert all(
        step.expected_target_absent
        for step in steps
        if step.phase == "expected_empty"
    )
    assert not any(
        step.expected_target_absent
        for step in steps
        if step.phase != "expected_empty"
    )


def test_initial_replay_pose_uses_first_teleport_step() -> None:
    step = stress.ReplayStep(
        phase="approach",
        action="reset",
        source="geodesic_path:waypoint:0",
        position=(1.0, 0.0, 2.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        target_pixels=0,
    )

    assert stress._initial_replay_pose_from_steps((step,)) == (
        (1.0, 0.0, 2.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def test_target_view_metrics_marks_edge_clipped_views() -> None:
    centered = stress._target_view_metrics(_mask_with_box((10, 12, 30, 36), (48, 48)))
    clipped = stress._target_view_metrics(_mask_with_box((31, 40, 48, 48), (48, 48)))
    floor_clipped = stress._target_view_metrics(_mask_with_box((10, 20, 30, 48), (48, 48)))

    assert centered["oracle_bbox"] == "10,12,30,36"
    assert centered["oracle_touches_edge"] is False
    assert centered["oracle_edge_sides"] == ""
    assert centered["oracle_touches_side_edge"] is False
    assert centered["oracle_bbox_fill_ratio"] == 1.0
    assert clipped["oracle_touches_edge"] is True
    assert clipped["oracle_edge_sides"] == "right|bottom"
    assert clipped["oracle_touches_side_edge"] is True
    assert clipped["oracle_edge_clearance_ratio"] == 0.0
    assert floor_clipped["oracle_edge_sides"] == "bottom"
    assert floor_clipped["oracle_touches_side_edge"] is False


def test_stop_on_trust_uses_objectnav_stop_semantics() -> None:
    assert (
        stress._should_stop_episode(
            decision=DecisionType.TRUST,
            target_visible=True,
            stop_on_trust=True,
        )
        is True
    )
    assert (
        stress._should_stop_episode(
            decision=DecisionType.TRUST,
            target_visible=False,
            stop_on_trust=True,
        )
        is False
    )
    assert (
        stress._should_stop_episode(
            decision=DecisionType.TRUST,
            target_visible=True,
            stop_on_trust=False,
        )
        is False
    )


def test_shared_decision_gate_requires_current_positive_confirmation() -> None:
    assert (
        stress._gated_decision(
            decision=DecisionType.TRUST,
            target_visible=True,
            evidence_type=EvidenceType.POSITIVE,
        )
        is DecisionType.TRUST
    )
    assert (
        stress._gated_decision(
            decision=DecisionType.TRUST,
            target_visible=True,
            evidence_type=EvidenceType.UNKNOWN,
        )
        is DecisionType.VERIFY
    )
    assert (
        stress._gated_decision(
            decision=DecisionType.TRUST,
            target_visible=False,
            evidence_type=EvidenceType.POSITIVE,
        )
        is DecisionType.VERIFY
    )
    assert (
        stress._should_stop_episode(
            decision=DecisionType.TRUST,
            gated_decision=DecisionType.VERIFY,
            target_visible=True,
            stop_on_trust=True,
        )
        is False
    )
    assert (
        stress._should_stop_episode(
            decision=DecisionType.VERIFY,
            target_visible=True,
            stop_on_trust=True,
        )
        is False
    )


def test_run_summary_reports_raw_and_gated_decision_counts(tmp_path: Path) -> None:
    summary = stress._summarize_rgb_noise_run(
        output_path=tmp_path,
        config_summary={"detector": "oracle_bbox"},
        dataset_dir=Path("dataset"),
        scene_root=Path("scenes"),
        scene_dataset_config=Path("scene_config.json"),
        start_source="goal_viewpoint",
        sensor_height=720,
        sensor_width=1280,
        max_episodes=None,
        rows=[
            {
                "evidence_type": "positive",
                "decision": "trust",
                "raw_decision": "trust",
                "decision_gate_reason": "current_positive_confirmation",
                "replay_phase": "confirm",
                "oracle_stop_success": True,
                "memory_mode": "on",
                "translation_m": 1.0,
                "detector_precision": 1.0,
                "oracle_recall": 1.0,
            },
            {
                "evidence_type": "positive",
                "decision": "verify",
                "raw_decision": "trust",
                "decision_gate_reason": "target_not_currently_visible",
                "replay_phase": "non_confirm",
                "oracle_stop_success": False,
                "memory_mode": "on",
                "translation_m": 1.0,
                "detector_precision": 0.0,
                "oracle_recall": 0.0,
            },
        ],
        episode_summaries=[
            {
                "object_category": "tv_monitor",
                "memory_mode": "on",
                "final_p_valid": 0.95,
                "oracle_stop_success_rows": 1,
                "first_oracle_stop_success_step": 0,
                "path_translation_to_first_success_m": 1.0,
            }
        ],
    )

    assert summary["decision_counts"]["trust"] == 1
    assert summary["decision_counts"]["verify"] == 1
    assert summary["raw_decision_counts"] == {"trust": 2}
    assert summary["decision_gate_reason_counts"] == {
        "current_positive_confirmation": 1,
        "target_not_currently_visible": 1,
    }
    assert summary["replay_phase_counts"] == {"confirm": 1, "non_confirm": 1}
    assert summary["replay_phase_evidence_counts"] == {
        "confirm": {"positive": 1},
        "non_confirm": {"positive": 1},
    }
    assert summary["replay_phase_decision_counts"] == {
        "confirm": {"trust": 1},
        "non_confirm": {"verify": 1},
    }
    assert summary["replay_phase_raw_decision_counts"] == {
        "confirm": {"trust": 1},
        "non_confirm": {"trust": 1},
    }
    assert summary["memory_mode_metrics"]["on"] == {
        "episodes": 1,
        "success_episodes": 1,
        "success_rows": 1,
        "raw_trust_rows": 2,
        "gate_rejection_rows": 1,
        "mean_first_success_step": 0.0,
        "mean_path_translation_to_first_success_m": 1.0,
        "mean_final_p_valid": 0.95,
    }


def test_episode_timing_metrics_record_first_success_and_path_distance() -> None:
    rows = [
        {
            "step_index": 0,
            "replay_phase": "approach",
            "evidence_type": "unknown",
            "raw_decision": "verify",
            "decision": "verify",
            "oracle_stop_success": False,
            "translation_m": 0.0,
        },
        {
            "step_index": 1,
            "replay_phase": "approach",
            "evidence_type": "positive",
            "raw_decision": "trust",
            "decision": "verify",
            "oracle_stop_success": False,
            "translation_m": 2.0,
        },
        {
            "step_index": 2,
            "replay_phase": "confirm",
            "evidence_type": "positive",
            "raw_decision": "trust",
            "decision": "trust",
            "oracle_stop_success": True,
            "translation_m": 3.0,
        },
    ]

    metrics = stress._episode_timing_metrics(rows)

    assert metrics == {
        "first_positive_step": 1,
        "first_positive_phase": "approach",
        "first_raw_trust_step": 1,
        "first_raw_trust_phase": "approach",
        "first_gated_trust_step": 2,
        "first_gated_trust_phase": "confirm",
        "first_oracle_stop_success_step": 2,
        "first_oracle_stop_success_phase": "confirm",
        "path_translation_to_first_success_m": 5.0,
        "successful_replay": True,
    }


def test_preflight_rejects_unknown_yolo_prompt_mode(tmp_path: Path) -> None:
    try:
        stress.run_rgb_noise_stress_preflight(
            output_dir=tmp_path,
            rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
            depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
            noise_levels=("clean",),
            detector="yolo_world",
            detector_weights="yolov8s-worldv2.pt",
            detector_conf=0.25,
            memory_ablation=("on",),
            seed=313,
            yolo_prompt_mode="everything",
        )
    except ValueError as exc:
        assert "yolo_prompt_mode" in str(exc)
    else:
        raise AssertionError("unknown yolo prompt modes should fail preflight")


def test_preflight_rejects_bad_grounding_dino_text_threshold(tmp_path: Path) -> None:
    try:
        stress.run_rgb_noise_stress_preflight(
            output_dir=tmp_path,
            rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
            depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
            noise_levels=("clean",),
            detector="grounding_dino",
            detector_weights="IDEA-Research/grounding-dino-tiny",
            detector_conf=0.25,
            grounding_dino_text_threshold=1.1,
            memory_ablation=("on",),
            seed=313,
        )
    except ValueError as exc:
        assert "grounding_dino_text_threshold" in str(exc)
    else:
        raise AssertionError("bad Grounding-DINO text thresholds should fail preflight")


def test_preflight_rejects_noise_level_missing_from_profile(tmp_path: Path) -> None:
    try:
        stress.run_rgb_noise_stress_preflight(
            output_dir=tmp_path,
            rgb_noise_profile="configs/noise/rgb_published_v1.yaml",
            depth_noise_profile="configs/noise/depth_realsense_d435_v1.yaml",
            noise_levels=("clean", "extreme"),
            detector="yolo_world",
            detector_weights="yolov8s-worldv2.pt",
            detector_conf=0.25,
            memory_ablation=("on",),
            seed=313,
        )
    except ValueError as exc:
        assert "extreme" in str(exc)
    else:
        raise AssertionError("unknown noise levels should fail preflight")


def _mask_with_box(
    bbox: tuple[int, int, int, int],
    shape: tuple[int, int],
) -> object:
    import numpy as np

    mask = np.zeros(shape, dtype=bool)
    x1, y1, x2, y2 = bbox
    mask[y1:y2, x1:x2] = True
    return mask


class _Episode:
    def __init__(
        self,
        episode_id: str,
        object_category: str,
        *,
        goal_viewpoints: int = 0,
        geodesic_distance: float | None = None,
        euclidean_distance: float | None = None,
    ) -> None:
        self.episode_id = episode_id
        self.object_category = object_category
        self.goal_viewpoints = tuple({} for _ in range(goal_viewpoints))
        self.geodesic_distance = geodesic_distance
        self.euclidean_distance = euclidean_distance


class _StaticDetector:
    def __init__(self, detections: list[Detection]) -> None:
        self._detections = detections

    def detect(self, rgb: object) -> list[Detection]:
        return self._detections
