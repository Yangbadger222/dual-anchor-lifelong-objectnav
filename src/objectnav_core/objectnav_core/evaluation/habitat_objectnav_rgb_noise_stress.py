from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_objectnav_valmini_semantic_stress import (
    VALID_START_SOURCES,
    _agent_pose,
    _load_valmini_episodes,
    _quaternion_angle_degrees,
    _resolve_hm3d_scene_path,
    _select_episode_start,
    _semantic_id_to_category,
    _semantic_ids_for_target_category,
    _target_aliases,
    _translation_delta,
    _write_scene_dataset_config,
)
from objectnav_core.evaluation.habitat_semantic_yolo_stress import (
    _classify_semantic_evidence,
    _count_values,
    _decision_context,
    _depth_valid_ratio,
    _load_habitat_sim,
    _make_simulator,
    _mask_metrics,
    _write_csv,
)
from objectnav_core.evaluation.lifelong_memory_harness import LifelongMemoryHarness
from objectnav_core.memory.usability import (
    DecisionType,
    EvidenceEvent,
    EvidenceType,
    MemoryBelief,
    UsabilityDecisionPolicy,
    UsabilityUpdater,
)
from objectnav_core.perception.grounding_dino_adapter import GroundingDinoDetector
from objectnav_core.perception.yolo_world_adapter import Detection, YoloWorldDetector
from objectnav_core.simulation.depth_noise import DepthNoisePipelineD435
from objectnav_core.simulation.depth_noise import DepthNoiseProfile
from objectnav_core.simulation.revisit_controller import OutAndBackController
from objectnav_core.simulation.rgb_noise import AgentMotion, RgbNoisePipeline
from objectnav_core.simulation.rgb_noise import RgbNoiseProfile


TARGET_CATEGORIES: tuple[str, ...] = (
    "bed",
    "chair",
    "plant",
    "sofa",
    "toilet",
    "tv_monitor",
)
SUPPORTED_DETECTORS: tuple[str, ...] = (
    "yolo_world",
    "grounding_dino",
    "oracle_bbox",
)
SUPPORTED_MEMORY_ABLATIONS: tuple[str, ...] = ("on", "naive_count", "off")
SUPPORTED_YOLO_PROMPT_MODES: tuple[str, ...] = (
    "target",
    "all_categories",
    "target_aliases",
)
DEFAULT_SENSOR_SIZE = 320
DEFAULT_SENSOR_WIDTH = 640
DEFAULT_SENSOR_HEIGHT = 480
DEFAULT_YOLO_PROMPT_MODE = "target"
DEFAULT_STOP_ON_TRUST = True
DEFAULT_DEBUG_EXPORT_CATEGORIES: tuple[str, ...] = ("plant", "tv_monitor")
DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY = 256
DEFAULT_MAX_DETECTION_AREA_RATIO = 0.7
DEBUG_PANEL_MAX_WIDTH = 640
DATASET_VERSION = "objectnav_hm3d_v1/val_mini"
INITIAL_BELIEF = MemoryBelief(
    p_existence=0.9,
    p_location_valid=0.85,
    p_usable=0.85,
)
NAIVE_COUNT_TRUST_P_VALID = 0.9
NAIVE_COUNT_POSITIVES_TO_TRUST = 2
YOLO_WORLD_PROMPT_ALIASES: dict[str, tuple[str, ...]] = {
    "plant": ("plant", "potted plant", "houseplant"),
    "sofa": ("sofa", "couch"),
    "toilet": ("toilet", "bathroom toilet", "toilet bowl", "white toilet", "commode"),
    "tv monitor": ("tv monitor", "tv", "television", "monitor"),
}


@dataclass(frozen=True)
class NaiveCountState:
    positive_count: int = 0


def run_habitat_objectnav_rgb_noise_stress(
    output_dir: str | Path,
    *,
    dataset_dir: str | Path,
    scene_root: str | Path,
    rgb_noise_profile: str | Path,
    depth_noise_profile: str | Path,
    noise_levels: Sequence[str],
    detector: str,
    detector_weights: str,
    detector_conf: float,
    memory_ablation: Sequence[str],
    max_episodes: int | None = None,
    start_source: str = "goal_viewpoint",
    seed: int = 313,
    sensor_size: int | None = None,
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    min_target_pixels: int = 24,
    min_detector_pixels: int = 20,
    grounding_dino_text_threshold: float = 0.25,
    grounding_dino_max_image_side: int | None = None,
    yolo_prompt_mode: str = DEFAULT_YOLO_PROMPT_MODE,
    stop_on_trust: bool = DEFAULT_STOP_ON_TRUST,
    target_categories: Sequence[str] = TARGET_CATEGORIES,
    episodes_per_category: int | None = None,
    debug_export_gate_rejections: bool = False,
    debug_export_categories: Sequence[str] = DEFAULT_DEBUG_EXPORT_CATEGORIES,
    debug_export_limit_per_category: int = DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY,
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
) -> dict[str, Any]:
    """Run the v1 RGB/depth-noise ObjectNav memory stress harness."""

    if max_episodes is not None and max_episodes <= 0:
        raise ValueError("max_episodes must be positive when provided")
    sensor_height_resolved, sensor_width_resolved = _resolve_sensor_resolution(
        sensor_size=sensor_size,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
    )
    if start_source not in VALID_START_SOURCES:
        raise ValueError(
            f"start_source must be one of: {', '.join(VALID_START_SOURCES)}"
        )
    if episodes_per_category is not None and episodes_per_category <= 0:
        raise ValueError("episodes_per_category must be positive when provided")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    config_summary = run_rgb_noise_stress_preflight(
        output_path,
        rgb_noise_profile=rgb_noise_profile,
        depth_noise_profile=depth_noise_profile,
        noise_levels=noise_levels,
        detector=detector,
        detector_weights=detector_weights,
        detector_conf=detector_conf,
        grounding_dino_text_threshold=grounding_dino_text_threshold,
        grounding_dino_max_image_side=grounding_dino_max_image_side,
        memory_ablation=memory_ablation,
        seed=seed,
        yolo_prompt_mode=yolo_prompt_mode,
        stop_on_trust=stop_on_trust,
        sensor_size=sensor_size,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        target_categories=target_categories,
        episodes_per_category=episodes_per_category,
        debug_export_gate_rejections=debug_export_gate_rejections,
        debug_export_categories=debug_export_categories,
        debug_export_limit_per_category=debug_export_limit_per_category,
        max_detection_area_ratio=max_detection_area_ratio,
    )
    rgb_profile = RgbNoiseProfile.from_yaml(rgb_noise_profile)
    depth_profile = DepthNoiseProfile.from_yaml(depth_noise_profile)
    rgb_noise = RgbNoisePipeline(rgb_profile, seed=seed)
    depth_noise = DepthNoisePipelineD435(depth_profile, seed=seed)
    controller = OutAndBackController()
    detector_cache: dict[tuple[str, tuple[str, ...]], Any] = {}

    dataset_path = Path(dataset_dir).expanduser().resolve()
    scene_root_path = Path(scene_root).expanduser().resolve()
    episodes = _load_valmini_episodes(dataset_path, scene_root=scene_root_path)
    selected_episodes = _select_episodes(
        episodes,
        target_categories=target_categories,
        episodes_per_category=episodes_per_category,
        max_episodes=max_episodes,
    )
    if not selected_episodes:
        raise ValueError(f"No ObjectNav episodes found under {dataset_path}")
    scene_config_path = output_path / "hm3d_rgb_noise_annotated_basis.scene_dataset_config.json"
    _write_scene_dataset_config(
        scene_config_path,
        sorted({episode.resolved_scene_path for episode in selected_episodes}),
    )

    habitat_sim = _load_habitat_sim()
    memory = LifelongMemoryHarness(output_path / "lifelong_memory.sqlite")
    trace_rows: list[dict[str, Any]] = []
    episode_summaries: list[dict[str, Any]] = []
    debug_categories = _debug_category_filter(debug_export_categories)
    debug_export_dir = (
        output_path / "debug_gate_rejections"
        if debug_export_gate_rejections
        else None
    )
    debug_png_counts: dict[str, int] = {}
    debug_png_skipped_counts: dict[str, int] = {}
    for scene_index, scene in enumerate(
        sorted({episode.resolved_scene_path for episode in selected_episodes})
    ):
        scene_episodes = [
            episode for episode in selected_episodes if episode.resolved_scene_path == scene
        ]
        sim = _make_simulator(
            habitat_sim=habitat_sim,
            scene=scene,
            scene_dataset_config=scene_config_path,
            sensor_size=(sensor_height_resolved, sensor_width_resolved),
        )
        try:
            sim.seed(seed + scene_index * 1000)
            semantic_id_to_category = _semantic_id_to_category(sim)
            for episode in scene_episodes:
                episode_index = selected_episodes.index(episode)
                for level in noise_levels:
                    for memory_mode in memory_ablation:
                        rows, episode_summary = _run_rgb_noise_episode(
                            sim=sim,
                            episode=episode,
                            episode_index=episode_index,
                            level=level,
                            memory_mode=memory_mode,
                            start_source=start_source,
                            controller=controller,
                            rgb_noise=rgb_noise,
                            depth_noise=depth_noise,
                            detector=detector,
                            detector_adapter=_detector_for_target(
                                detector_cache=detector_cache,
                                detector=detector,
                                detector_weights=detector_weights,
                                detector_conf=detector_conf,
                                grounding_dino_text_threshold=grounding_dino_text_threshold,
                                grounding_dino_max_image_side=grounding_dino_max_image_side,
                                target_category=episode.object_category,
                                yolo_prompt_mode=yolo_prompt_mode,
                            ),
                            accepted_detection_labels=_accepted_yolo_detection_labels(
                                episode.object_category,
                                yolo_prompt_mode,
                            ),
                            yolo_prompt_categories=_yolo_prompt_categories(
                                episode.object_category,
                                yolo_prompt_mode,
                            ),
                            semantic_id_to_category=semantic_id_to_category,
                            memory=memory,
                            seed=seed,
                            min_target_pixels=min_target_pixels,
                            min_detector_pixels=min_detector_pixels,
                            stop_on_trust=stop_on_trust,
                            debug_export_gate_rejections=debug_export_gate_rejections,
                            debug_export_categories=debug_categories,
                            debug_export_dir=debug_export_dir,
                            debug_export_counts=debug_png_counts,
                            debug_export_skipped_counts=debug_png_skipped_counts,
                            debug_export_limit_per_category=debug_export_limit_per_category,
                            output_path=output_path,
                            max_detection_area_ratio=max_detection_area_ratio,
                        )
                        trace_rows.extend(rows)
                        episode_summaries.append(episode_summary)
        finally:
            sim.close()

    _write_csv(output_path / "rgb_noise_trace.csv", trace_rows)
    summary = _summarize_rgb_noise_run(
        output_path=output_path,
        config_summary=config_summary,
        dataset_dir=dataset_path,
        scene_root=scene_root_path,
        scene_dataset_config=scene_config_path,
        start_source=start_source,
        sensor_height=sensor_height_resolved,
        sensor_width=sensor_width_resolved,
        max_episodes=max_episodes,
        rows=trace_rows,
        episode_summaries=episode_summaries,
        debug_png_counts=debug_png_counts,
        debug_png_skipped_counts=debug_png_skipped_counts,
    )
    _write_json(output_path / "summary.json", summary)
    return summary


def run_rgb_noise_stress_preflight(
    output_dir: str | Path,
    *,
    rgb_noise_profile: str | Path,
    depth_noise_profile: str | Path,
    noise_levels: Sequence[str],
    detector: str,
    detector_weights: str,
    detector_conf: float,
    memory_ablation: Sequence[str],
    seed: int,
    grounding_dino_text_threshold: float = 0.25,
    grounding_dino_max_image_side: int | None = None,
    yolo_prompt_mode: str = DEFAULT_YOLO_PROMPT_MODE,
    stop_on_trust: bool = DEFAULT_STOP_ON_TRUST,
    sensor_size: int | None = None,
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    target_categories: Sequence[str] = TARGET_CATEGORIES,
    episodes_per_category: int | None = None,
    debug_export_gate_rejections: bool = False,
    debug_export_categories: Sequence[str] = DEFAULT_DEBUG_EXPORT_CATEGORIES,
    debug_export_limit_per_category: int = DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY,
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
) -> dict[str, Any]:
    """Validate the RGB-noise stress configuration without importing Habitat."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    rgb_profile = RgbNoiseProfile.from_yaml(rgb_noise_profile)
    depth_profile = DepthNoiseProfile.from_yaml(depth_noise_profile)
    _validate_noise_levels(noise_levels, rgb_profile, depth_profile)
    _validate_detector(detector, detector_conf)
    _validate_grounding_dino_text_threshold(grounding_dino_text_threshold)
    _validate_grounding_dino_max_image_side(grounding_dino_max_image_side)
    _validate_memory_ablation(memory_ablation)
    _validate_yolo_prompt_mode(yolo_prompt_mode)
    _validate_debug_export_limit(debug_export_limit_per_category)
    _validate_max_detection_area_ratio(max_detection_area_ratio)
    sensor_height_resolved, sensor_width_resolved = _resolve_sensor_resolution(
        sensor_size=sensor_size,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
    )
    if episodes_per_category is not None and episodes_per_category <= 0:
        raise ValueError("episodes_per_category must be positive when provided")
    controller = OutAndBackController()
    actions = controller.actions_for_episode(
        start_pose=(0.0, 0.0, 0.0),
        target_pose=(1.0, 0.0, 0.0),
    )
    summary: dict[str, Any] = {
        "task": "habitat_objectnav_rgb_noise_stress_preflight",
        "full_habitat_run": False,
        "seed": int(seed),
        "rgb_noise_profile": str(rgb_noise_profile),
        "rgb_noise_provenance": rgb_profile.provenance,
        "depth_noise_profile": str(depth_noise_profile),
        "depth_noise_provenance": depth_profile.provenance,
        "target_camera": depth_profile.target_camera,
        "noise_levels": list(noise_levels),
        "detector": detector,
        "detector_weights": detector_weights,
        "detector_conf": detector_conf,
        "grounding_dino_text_threshold": grounding_dino_text_threshold,
        "grounding_dino_max_image_side": grounding_dino_max_image_side,
        "yolo_prompt_mode": yolo_prompt_mode,
        "stop_on_trust": bool(stop_on_trust),
        "sensor_size": sensor_size,
        "sensor_width": sensor_width_resolved,
        "sensor_height": sensor_height_resolved,
        "sensor_resolution": (
            f"{sensor_width_resolved}x{sensor_height_resolved}"
        ),
        "target_categories": list(TARGET_CATEGORIES),
        "category_filter": list(target_categories),
        "episodes_per_category": episodes_per_category,
        "memory_ablation": list(memory_ablation),
        "debug_export_gate_rejections": bool(debug_export_gate_rejections),
        "debug_export_categories": sorted(_debug_category_filter(debug_export_categories)),
        "debug_export_limit_per_category": int(debug_export_limit_per_category),
        "max_detection_area_ratio": max_detection_area_ratio,
        "revisit_strategy": "out_and_back",
        "out_and_back_actions": list(actions),
        "out_and_back_action_count": len(actions),
        "artifact_files": {"summary": "summary.json"},
        "limits": [
            "Preflight validates configuration and lazy import boundaries only.",
            "It does not load Habitat scenes, YOLO-World weights, or HM3D episodes.",
        ],
    }
    _write_json(output_path / "summary.json", summary)
    return summary


def _run_rgb_noise_episode(
    *,
    sim: Any,
    episode: Any,
    episode_index: int,
    level: str,
    memory_mode: str,
    start_source: str,
    controller: OutAndBackController,
    rgb_noise: RgbNoisePipeline,
    depth_noise: DepthNoisePipelineD435,
    detector: str,
    detector_adapter: YoloWorldDetector | GroundingDinoDetector | None,
    accepted_detection_labels: set[str],
    yolo_prompt_categories: Sequence[str],
    semantic_id_to_category: dict[int, str],
    memory: LifelongMemoryHarness,
    seed: int,
    min_target_pixels: int,
    min_detector_pixels: int,
    stop_on_trust: bool,
    debug_export_gate_rejections: bool = False,
    debug_export_categories: set[str] | None = None,
    debug_export_dir: Path | None = None,
    debug_export_counts: dict[str, int] | None = None,
    debug_export_skipped_counts: dict[str, int] | None = None,
    debug_export_limit_per_category: int = DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY,
    output_path: Path | None = None,
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    agent = sim.initialize_agent(0)
    start = _select_episode_start(episode, start_source=start_source)
    state = agent.get_state()
    state.position = np.asarray(start.position, dtype=float)
    state.rotation = list(start.rotation)
    agent.set_state(state)
    observations = sim.get_sensor_observations()
    target_semantic_ids = _semantic_ids_for_target_category(
        semantic_id_to_category,
        episode.object_category,
    )
    actions = controller.actions_for_episode(
        start_pose=start.position,
        target_pose=_first_goal_position(episode),
    )
    updater = UsabilityUpdater()
    policy = UsabilityDecisionPolicy()
    naive_count_state = NaiveCountState()
    if memory_mode == "on":
        belief = memory.load_belief(
            scene_id=episode.original_scene_id,
            episode_dataset_version=DATASET_VERSION,
            category=episode.object_category,
            default=INITIAL_BELIEF,
        )
    else:
        belief = INITIAL_BELIEF
    rows: list[dict[str, Any]] = []
    negative_streak = 0
    previous_pose = _agent_pose(agent)
    for step_index, action in enumerate(("reset", *actions)):
        if action != "reset":
            observations = sim.step(action)
        pose = _agent_pose(agent)
        motion = AgentMotion(
            translation_m=_translation_delta(previous_pose[0], pose[0]),
            rotation_rad=np.deg2rad(
                _quaternion_angle_degrees(previous_pose[1], pose[1])
            ),
        )
        previous_pose = pose
        rgb = _rgb3(np.asarray(observations["rgb"]))
        depth = np.asarray(observations["depth"])
        semantic = np.asarray(observations["semantic"])
        noisy_rgb = rgb_noise.apply(
            rgb,
            agent_motion=motion,
            level=level,
            frame_index=episode_index * 1000 + step_index,
        )
        noisy_depth = depth_noise.apply(
            depth,
            level=level,
            frame_index=episode_index * 1000 + step_index,
        )
        oracle_mask = np.isin(semantic, list(target_semantic_ids))
        detector_mask, detections, detection_filtered_count = _detector_mask(
            detector=detector,
            detector_adapter=detector_adapter,
            noisy_rgb=noisy_rgb,
            oracle_mask=oracle_mask,
            target_category=episode.object_category,
            accepted_detection_labels=accepted_detection_labels,
            max_detection_area_ratio=max_detection_area_ratio,
        )
        metrics = _mask_metrics(oracle_mask=oracle_mask, detector_mask=detector_mask)
        view_metrics = _target_view_metrics(oracle_mask)
        depth_valid_ratio = _depth_valid_ratio(noisy_depth)
        collided = bool(getattr(sim, "previous_step_collided", False))
        evidence_type, evidence_strength, quarantined, evidence_reason = (
            _classify_semantic_evidence(
                action=action,
                collided=collided,
                depth_valid_ratio=depth_valid_ratio,
                metrics=metrics,
                min_target_pixels=min_target_pixels,
                min_detector_pixels=min_detector_pixels,
            )
        )
        if evidence_type is EvidenceType.POSITIVE:
            negative_streak = 0
        elif evidence_type in {
            EvidenceType.FREE,
            EvidenceType.NON_CONFIRMATION,
            EvidenceType.ACCESS_BLOCKED,
            EvidenceType.SCENE_CHANGED,
        }:
            negative_streak += 1
        event = EvidenceEvent(
            evidence_type=evidence_type,
            strength=evidence_strength,
            quarantined=quarantined,
        )
        if memory_mode == "off":
            belief = updater.apply(INITIAL_BELIEF, event)
        elif memory_mode == "naive_count":
            naive_count_state, belief = _naive_count_belief(
                naive_count_state,
                evidence_type,
            )
        else:
            belief = updater.apply(belief, event)
        decision = policy.choose(
            belief,
            _decision_context(
                step_index=step_index,
                total_steps=len(actions) + 1,
                negative_streak=negative_streak,
                metrics=metrics,
            ),
        )
        target_visible = metrics["oracle_target_pixels"] >= min_target_pixels
        gated_decision = _gated_decision(
            decision=decision.decision,
            target_visible=target_visible,
            evidence_type=evidence_type,
        )
        decision_gate_reason = _decision_gate_reason(
            decision=decision.decision,
            gated_decision=gated_decision,
            target_visible=target_visible,
            evidence_type=evidence_type,
        )
        oracle_stop_success = (
            gated_decision is DecisionType.TRUST
            and target_visible
        )
        stopped_on_trust = _should_stop_episode(
            decision=decision.decision,
            gated_decision=gated_decision,
            target_visible=target_visible,
            stop_on_trust=stop_on_trust,
        )
        debug_png = ""
        if (
            debug_export_gate_rejections
            and debug_export_dir is not None
            and debug_export_counts is not None
            and debug_export_skipped_counts is not None
            and _should_export_gate_rejection_debug(
                object_category=episode.object_category,
                decision=decision.decision,
                gated_decision=gated_decision,
                debug_categories=debug_export_categories,
            )
        ):
            debug_key = _debug_category_token(episode.object_category)
            debug_index = debug_export_counts.get(debug_key, 0)
            if debug_index < debug_export_limit_per_category:
                debug_path = _write_gate_rejection_debug_png(
                    output_dir=debug_export_dir,
                    rgb=rgb,
                    noisy_rgb=noisy_rgb,
                    oracle_mask=oracle_mask,
                    detector_mask=detector_mask,
                    detections=detections,
                    metadata={
                        "episode_index": episode_index,
                        "episode_id": episode.episode_id,
                        "original_scene_id": episode.original_scene_id,
                        "object_category": episode.object_category,
                        "noise_level": level,
                        "memory_mode": memory_mode,
                        "detector": detector,
                        "step_index": step_index,
                        "action": action,
                        "target_visible": target_visible,
                        "evidence_type": evidence_type.value,
                        "evidence_reason": evidence_reason,
                        "raw_decision": decision.decision.value,
                        "decision": gated_decision.value,
                        "decision_gate_reason": decision_gate_reason,
                        "naive_positive_count": naive_count_state.positive_count,
                        "p_valid": round(decision.p_valid, 6),
                        "detection_count": len(detections),
                        "detection_filtered_count": detection_filtered_count,
                        "detection_conf_max": round(
                            max((d.confidence for d in detections), default=0.0),
                            6,
                        ),
                        **metrics,
                        **view_metrics,
                    },
                    sequence_id=debug_index,
                )
                debug_export_counts[debug_key] = debug_index + 1
                if output_path is not None:
                    debug_png = str(debug_path.relative_to(output_path))
                else:
                    debug_png = str(debug_path)
            else:
                debug_export_skipped_counts[debug_key] = (
                    debug_export_skipped_counts.get(debug_key, 0) + 1
                )
        rows.append(
            {
                "episode_index": episode_index,
                "episode_id": episode.episode_id,
                "original_scene_id": episode.original_scene_id,
                "object_category": episode.object_category,
                "noise_level": level,
                "memory_mode": memory_mode,
                "detector": detector,
                "detector_prompt_categories": "|".join(yolo_prompt_categories),
                "start_source_requested": start_source,
                "start_source_used": start.source_used,
                "step_index": step_index,
                "action": action,
                "translation_m": round(motion.translation_m, 6),
                "rotation_rad": round(float(motion.rotation_rad), 6),
                "depth_valid_ratio": depth_valid_ratio,
                "previous_step_collided": collided,
                "detection_count": len(detections),
                "detection_filtered_count": detection_filtered_count,
                "detection_conf_max": round(
                    max((d.confidence for d in detections), default=0.0),
                    6,
                ),
                **metrics,
                **view_metrics,
                "target_visible": target_visible,
                "evidence_type": evidence_type.value,
                "evidence_strength": round(evidence_strength, 6),
                "evidence_quarantined": quarantined,
                "evidence_reason": evidence_reason,
                "p_existence": round(belief.p_existence, 6),
                "p_location_valid": round(belief.p_location_valid, 6),
                "p_usable": round(belief.p_usable, 6),
                "p_valid": round(decision.p_valid, 6),
                "raw_decision": decision.decision.value,
                "decision": gated_decision.value,
                "decision_gate_reason": decision_gate_reason,
                "naive_positive_count": naive_count_state.positive_count,
                "debug_png": debug_png,
                "oracle_stop_success": oracle_stop_success,
                "stopped_on_trust": stopped_on_trust,
            }
        )
        if stopped_on_trust:
            break
    if memory_mode == "on":
        memory.save_belief(
            scene_id=episode.original_scene_id,
            episode_dataset_version=DATASET_VERSION,
            category=episode.object_category,
            belief=belief,
        )
    return rows, {
        "episode_index": episode_index,
        "episode_id": episode.episode_id,
        "original_scene_id": episode.original_scene_id,
        "object_category": episode.object_category,
        "noise_level": level,
        "memory_mode": memory_mode,
        "trace_rows": len(rows),
        "target_visible_rows": sum(int(row["target_visible"]) for row in rows),
        "oracle_stop_success_rows": sum(
            int(row["oracle_stop_success"]) for row in rows
        ),
        "final_p_valid": round(belief.p_valid, 6),
    }


def _detector_mask(
    *,
    detector: str,
    detector_adapter: YoloWorldDetector | GroundingDinoDetector | None,
    noisy_rgb: np.ndarray,
    oracle_mask: np.ndarray,
    target_category: str,
    accepted_detection_labels: set[str],
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
) -> tuple[np.ndarray, list[Detection], int]:
    if detector == "oracle_bbox":
        bbox = _mask_bbox(oracle_mask)
        if bbox is None:
            return np.zeros(oracle_mask.shape, dtype=bool), [], 0
        mask = np.zeros(oracle_mask.shape, dtype=bool)
        x1, y1, x2, y2 = bbox
        mask[y1:y2, x1:x2] = True
        return (
            mask,
            [
                Detection(
                    category=target_category,
                    bbox=bbox,
                    confidence=1.0,
                    mask=mask,
                )
            ],
            0,
        )
    if detector_adapter is None:
        raise RuntimeError(f"detector_adapter is required for {detector}")
    label_matched_detections = [
        detection
        for detection in detector_adapter.detect(noisy_rgb)
        if _normalize_yolo_label(detection.category) in accepted_detection_labels
    ]
    detections, filtered_count = _filter_detections_by_area(
        label_matched_detections,
        image_shape=noisy_rgb.shape[:2],
        max_detection_area_ratio=max_detection_area_ratio,
    )
    mask = np.zeros(noisy_rgb.shape[:2], dtype=bool)
    for detection in detections:
        mask |= detection.mask
    if _mask_area_ratio(mask) > (max_detection_area_ratio or 1.0):
        filtered_count += len(detections)
        detections = []
        mask = np.zeros(noisy_rgb.shape[:2], dtype=bool)
    return mask, detections, filtered_count


def _filter_detections_by_area(
    detections: Sequence[Detection],
    *,
    image_shape: tuple[int, int],
    max_detection_area_ratio: float | None,
) -> tuple[list[Detection], int]:
    if max_detection_area_ratio is None:
        return list(detections), 0
    image_height, image_width = image_shape
    image_area = max(1, image_height * image_width)
    kept: list[Detection] = []
    filtered_count = 0
    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        bbox_area = max(0, x2 - x1) * max(0, y2 - y1)
        if bbox_area / image_area > max_detection_area_ratio:
            filtered_count += 1
            continue
        kept.append(detection)
    return kept, filtered_count


def _mask_area_ratio(mask: np.ndarray) -> float:
    mask_bool = np.asarray(mask, dtype=bool)
    return float(mask_bool.sum()) / max(1, mask_bool.size)


def _detector_for_target(
    *,
    detector_cache: dict[tuple[str, tuple[str, ...]], Any],
    detector: str,
    detector_weights: str,
    detector_conf: float,
    grounding_dino_text_threshold: float,
    grounding_dino_max_image_side: int | None,
    target_category: str,
    yolo_prompt_mode: str,
    detector_factory: Any | None = None,
) -> YoloWorldDetector | GroundingDinoDetector | None:
    if detector not in {"yolo_world", "grounding_dino"}:
        return None
    prompt_categories = _yolo_prompt_categories(target_category, yolo_prompt_mode)
    cache_key = (detector, prompt_categories)
    if cache_key not in detector_cache:
        if detector == "yolo_world":
            factory = detector_factory or YoloWorldDetector
            detector_cache[cache_key] = factory(
                weights=detector_weights,
                categories=list(prompt_categories),
                conf=detector_conf,
                device="auto",
            )
        else:
            factory = detector_factory or GroundingDinoDetector
            detector_cache[cache_key] = factory(
                model_id=detector_weights,
                categories=list(prompt_categories),
                conf=detector_conf,
                text_threshold=grounding_dino_text_threshold,
                max_image_side=grounding_dino_max_image_side,
                device="auto",
            )
    return detector_cache[cache_key]


def _yolo_prompt_categories(target_category: str, yolo_prompt_mode: str) -> tuple[str, ...]:
    _validate_yolo_prompt_mode(yolo_prompt_mode)
    if yolo_prompt_mode == "all_categories":
        return tuple(_normalize_yolo_label(category) for category in TARGET_CATEGORIES)
    target_label = _normalize_yolo_label(target_category)
    if yolo_prompt_mode == "target":
        return (target_label,)
    return YOLO_WORLD_PROMPT_ALIASES.get(target_label, (target_label,))


def _accepted_yolo_detection_labels(
    target_category: str,
    yolo_prompt_mode: str,
) -> set[str]:
    _validate_yolo_prompt_mode(yolo_prompt_mode)
    labels = set(_target_aliases(target_category))
    if yolo_prompt_mode == "target_aliases":
        labels.update(
            _normalize_yolo_label(label)
            for label in _yolo_prompt_categories(target_category, yolo_prompt_mode)
        )
    return labels


def _normalize_yolo_label(category: str) -> str:
    return category.strip().lower().replace("_", " ")


def _target_view_metrics(oracle_mask: np.ndarray) -> dict[str, Any]:
    bbox = _mask_bbox(oracle_mask)
    height, width = oracle_mask.shape
    if bbox is None:
        return {
            "oracle_bbox": "",
            "oracle_bbox_area": 0,
            "oracle_bbox_fill_ratio": 0.0,
            "oracle_touches_edge": False,
            "oracle_touches_side_edge": False,
            "oracle_edge_sides": "",
            "oracle_edge_clearance_ratio": 0.0,
        }
    x1, y1, x2, y2 = bbox
    bbox_area = (x2 - x1) * (y2 - y1)
    edge_clearance = min(x1, y1, width - x2, height - y2)
    edge_sides = _edge_sides(
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        width=width,
        height=height,
    )
    return {
        "oracle_bbox": f"{x1},{y1},{x2},{y2}",
        "oracle_bbox_area": bbox_area,
        "oracle_bbox_fill_ratio": round(
            float(np.asarray(oracle_mask).sum()) / bbox_area,
            6,
        ),
        "oracle_touches_edge": edge_clearance == 0,
        "oracle_touches_side_edge": bool({"left", "right"} & set(edge_sides)),
        "oracle_edge_sides": "|".join(edge_sides),
        "oracle_edge_clearance_ratio": round(
            float(edge_clearance) / max(1, min(height, width)),
            6,
        ),
    }


def _edge_sides(
    *,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    width: int,
    height: int,
) -> tuple[str, ...]:
    sides: list[str] = []
    if x1 == 0:
        sides.append("left")
    if x2 == width:
        sides.append("right")
    if y1 == 0:
        sides.append("top")
    if y2 == height:
        sides.append("bottom")
    return tuple(sides)


def _should_stop_episode(
    *,
    decision: DecisionType,
    gated_decision: DecisionType | None = None,
    target_visible: bool,
    stop_on_trust: bool,
) -> bool:
    effective_decision = gated_decision if gated_decision is not None else decision
    return bool(
        stop_on_trust
        and target_visible
        and effective_decision is DecisionType.TRUST
    )


def _gated_decision(
    *,
    decision: DecisionType,
    target_visible: bool,
    evidence_type: EvidenceType,
) -> DecisionType:
    if decision is not DecisionType.TRUST:
        return decision
    if target_visible and evidence_type is EvidenceType.POSITIVE:
        return DecisionType.TRUST
    return DecisionType.VERIFY


def _decision_gate_reason(
    *,
    decision: DecisionType,
    gated_decision: DecisionType,
    target_visible: bool,
    evidence_type: EvidenceType,
) -> str:
    if decision is not DecisionType.TRUST:
        return "not_raw_trust"
    if gated_decision is DecisionType.TRUST:
        return "current_positive_confirmation"
    if not target_visible:
        return "target_not_currently_visible"
    if evidence_type is not EvidenceType.POSITIVE:
        return "missing_current_positive_evidence"
    return "trust_rejected"


def _should_export_gate_rejection_debug(
    *,
    object_category: str,
    decision: DecisionType,
    gated_decision: DecisionType,
    debug_categories: set[str] | None,
) -> bool:
    if decision is not DecisionType.TRUST or gated_decision is DecisionType.TRUST:
        return False
    normalized_categories = {
        _debug_category_token(category) for category in (debug_categories or set())
    }
    return not normalized_categories or (
        _debug_category_token(object_category) in normalized_categories
    )


def _write_gate_rejection_debug_png(
    *,
    output_dir: Path,
    rgb: np.ndarray,
    noisy_rgb: np.ndarray,
    oracle_mask: np.ndarray,
    detector_mask: np.ndarray,
    detections: Sequence[Detection],
    metadata: dict[str, Any],
    sequence_id: int,
) -> Path:
    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Pillow is required for debug PNG export. Install pillow or disable "
            "--debug-export-gate-rejections."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    rgb_image = Image.fromarray(_rgb3(rgb)).convert("RGB")
    noisy_image = Image.fromarray(_rgb3(noisy_rgb)).convert("RGB")
    oracle_bool = np.asarray(oracle_mask, dtype=bool)
    detector_bool = np.asarray(detector_mask, dtype=bool)

    clean_panel = rgb_image.copy()
    oracle_bbox = _mask_bbox(oracle_bool)
    if oracle_bbox is not None:
        _draw_bbox(clean_panel, oracle_bbox, color=(0, 190, 80), label="Habitat GT")

    dino_panel = noisy_image.copy()
    for detection in detections:
        _draw_bbox(
            dino_panel,
            detection.bbox,
            color=(235, 60, 45),
            label=f"{detection.category} {detection.confidence:.2f}",
        )

    detector_panel = _mask_overlay(
        noisy_image,
        detector_bool,
        color=(235, 60, 45),
        alpha=110,
    )
    oracle_panel = _mask_overlay(
        noisy_image,
        oracle_bool,
        color=(0, 190, 80),
        alpha=110,
    )
    overlap_panel = _overlap_overlay(noisy_image, oracle_bool, detector_bool)
    if oracle_bbox is not None:
        _draw_bbox(overlap_panel, oracle_bbox, color=(0, 190, 80), label="GT")
    for detection in detections:
        _draw_bbox(
            overlap_panel,
            detection.bbox,
            color=(235, 60, 45),
            label=f"DINO {detection.confidence:.2f}",
        )

    panels = [
        _fit_debug_panel(clean_panel, "clean RGB + GT bbox"),
        _fit_debug_panel(dino_panel, "noisy RGB + DINO boxes"),
        _fit_debug_panel(oracle_panel, "Habitat GT mask"),
        _fit_debug_panel(detector_panel, "DINO box mask"),
        _fit_debug_panel(overlap_panel, "GT green / DINO red / overlap yellow"),
    ]
    panel_width = max(panel.width for panel in panels)
    panel_height = max(panel.height for panel in panels)
    text_height = 150
    canvas = Image.new(
        "RGB",
        (panel_width * 2, panel_height * 3 + text_height),
        (245, 245, 245),
    )
    positions = [
        (0, 0),
        (panel_width, 0),
        (0, panel_height),
        (panel_width, panel_height),
        (0, panel_height * 2),
    ]
    for panel, position in zip(panels, positions):
        canvas.paste(panel, position)

    draw = ImageDraw.Draw(canvas)
    info_x = panel_width
    info_y = panel_height * 2
    draw.rectangle(
        (info_x, info_y, panel_width * 2, panel_height * 3),
        fill=(255, 255, 255),
    )
    y = info_y + 8
    for line in _debug_metadata_lines(metadata, detections):
        draw.text((info_x + 10, y), line, fill=(20, 20, 20))
        y += 16

    footer_y = panel_height * 3
    draw.rectangle(
        (0, footer_y, panel_width * 2, footer_y + text_height),
        fill=(255, 255, 255),
    )
    y = footer_y + 10
    for line in _debug_interpretation_lines(metadata):
        draw.text((10, y), line, fill=(20, 20, 20))
        y += 18

    path = output_dir / _debug_png_filename(metadata, sequence_id)
    canvas.save(path)
    return path


def _draw_bbox(
    image: Any,
    bbox: tuple[int, int, int, int],
    *,
    color: tuple[int, int, int],
    label: str,
) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(image)
    width = max(2, image.width // 320)
    x1, y1, x2, y2 = bbox
    draw.rectangle((x1, y1, x2, y2), outline=color, width=width)
    text_y = max(0, y1 - 15)
    draw.rectangle((x1, text_y, min(image.width, x1 + 180), text_y + 14), fill=color)
    draw.text((x1 + 3, text_y + 2), label[:28], fill=(255, 255, 255))


def _mask_overlay(
    image: Any,
    mask: np.ndarray,
    *,
    color: tuple[int, int, int],
    alpha: int,
) -> Any:
    from PIL import Image

    base = image.convert("RGBA")
    overlay = np.zeros((image.height, image.width, 4), dtype=np.uint8)
    overlay[np.asarray(mask, dtype=bool)] = (*color, alpha)
    return Image.alpha_composite(base, Image.fromarray(overlay, mode="RGBA")).convert(
        "RGB"
    )


def _overlap_overlay(image: Any, oracle_mask: np.ndarray, detector_mask: np.ndarray) -> Any:
    from PIL import Image

    base = image.convert("RGBA")
    oracle_bool = np.asarray(oracle_mask, dtype=bool)
    detector_bool = np.asarray(detector_mask, dtype=bool)
    overlay = np.zeros((image.height, image.width, 4), dtype=np.uint8)
    overlay[oracle_bool & ~detector_bool] = (0, 190, 80, 115)
    overlay[detector_bool & ~oracle_bool] = (235, 60, 45, 115)
    overlay[oracle_bool & detector_bool] = (255, 210, 0, 145)
    return Image.alpha_composite(base, Image.fromarray(overlay, mode="RGBA")).convert(
        "RGB"
    )


def _fit_debug_panel(image: Any, title: str) -> Any:
    from PIL import ImageDraw

    if image.width > DEBUG_PANEL_MAX_WIDTH:
        ratio = DEBUG_PANEL_MAX_WIDTH / float(image.width)
        image = image.resize(
            (DEBUG_PANEL_MAX_WIDTH, max(1, int(round(image.height * ratio))))
        )
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, image.width, 24), fill=(0, 0, 0))
    draw.text((8, 6), title, fill=(255, 255, 255))
    return image


def _debug_metadata_lines(
    metadata: dict[str, Any],
    detections: Sequence[Detection],
) -> list[str]:
    detector_pixels = metadata.get(
        "detector_pixels",
        metadata.get("detector_target_pixels"),
    )
    detection_text = "; ".join(
        f"{det.category}:{det.confidence:.2f}@{det.bbox}" for det in detections[:4]
    )
    if len(detections) > 4:
        detection_text += f"; +{len(detections) - 4} more"
    return [
        (
            f"category={metadata.get('object_category')} "
            f"memory={metadata.get('memory_mode')} noise={metadata.get('noise_level')}"
        ),
        (
            f"episode={metadata.get('episode_index')} id={metadata.get('episode_id')} "
            f"step={metadata.get('step_index')} action={metadata.get('action')}"
        ),
        (
            f"raw={metadata.get('raw_decision')} gated={metadata.get('decision')} "
            f"reason={metadata.get('decision_gate_reason')}"
        ),
        (
            f"target_visible={metadata.get('target_visible')} "
            f"evidence={metadata.get('evidence_type')} "
            f"p_valid={metadata.get('p_valid')}"
        ),
        (
            f"oracle_px={metadata.get('oracle_target_pixels')} "
            f"detector_px={detector_pixels} "
            f"precision={metadata.get('detector_precision')} "
            f"recall={metadata.get('oracle_recall')}"
        ),
        (
            f"oracle_bbox={metadata.get('oracle_bbox')} "
            f"max_conf={metadata.get('detection_conf_max')} "
            f"detections={metadata.get('detection_count')}"
        ),
        f"boxes={detection_text or 'none'}",
    ]


def _debug_interpretation_lines(metadata: dict[str, Any]) -> list[str]:
    return [
        "How to inspect: red is detector box-mask, green is Habitat semantic GT, yellow is overlap.",
        "If red boxes cover a visually wrong object, blame detector false positives.",
        "If red boxes cover the object but green GT is tiny/missing, blame strict or sparse Habitat GT.",
        (
            f"evidence_reason={metadata.get('evidence_reason')} "
            f"naive_positive_count={metadata.get('naive_positive_count')}"
        ),
        f"scene={metadata.get('original_scene_id')}",
    ]


def _debug_png_filename(metadata: dict[str, Any], sequence_id: int) -> str:
    category = _debug_category_token(str(metadata.get("object_category", "unknown")))
    memory = _sanitize_debug_token(str(metadata.get("memory_mode", "unknown")))
    noise = _sanitize_debug_token(str(metadata.get("noise_level", "unknown")))
    reason = _sanitize_debug_token(
        str(metadata.get("decision_gate_reason", "trust_rejected"))
    )
    episode = _sanitize_debug_token(str(metadata.get("episode_index", "unknown")))
    step = _sanitize_debug_token(str(metadata.get("step_index", "unknown")))
    return (
        f"{sequence_id:03d}_{category}_{memory}_{noise}_"
        f"ep{episode}_step{step}_{reason}.png"
    )


def _debug_category_filter(categories: Sequence[str]) -> set[str]:
    return {_debug_category_token(category) for category in categories}


def _debug_category_token(category: str) -> str:
    return _normalize_yolo_label(category).replace(" ", "_")


def _sanitize_debug_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip())
    return token.strip("-") or "unknown"


def _naive_count_belief(
    state: NaiveCountState,
    evidence_type: EvidenceType,
) -> tuple[NaiveCountState, MemoryBelief]:
    positive_count = state.positive_count
    if evidence_type is EvidenceType.POSITIVE:
        positive_count += 1
    if positive_count >= NAIVE_COUNT_POSITIVES_TO_TRUST:
        belief = MemoryBelief(
            p_existence=0.98,
            p_location_valid=0.98,
            p_usable=0.98,
        )
    elif positive_count > 0:
        belief = MemoryBelief(
            p_existence=0.93,
            p_location_valid=0.88,
            p_usable=0.88,
        )
    else:
        belief = INITIAL_BELIEF
    return NaiveCountState(positive_count=positive_count), belief


def _mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(np.asarray(mask, dtype=bool))
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _rgb3(rgb: np.ndarray) -> np.ndarray:
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError("Habitat RGB observation must have at least 3 channels")
    return np.ascontiguousarray(rgb[:, :, :3].astype(np.uint8, copy=False))


def _first_goal_position(episode: Any) -> tuple[float, float, float] | None:
    if not episode.goal_viewpoints:
        return None
    agent_state = episode.goal_viewpoints[0].get("agent_state", {})
    position = agent_state.get("position")
    if position is None:
        return None
    return tuple(float(value) for value in position)


def _resolve_sensor_resolution(
    *,
    sensor_size: int | None,
    sensor_width: int,
    sensor_height: int,
) -> tuple[int, int]:
    if sensor_size is not None:
        if sensor_size <= 0:
            raise ValueError("sensor_size must be positive")
        return int(sensor_size), int(sensor_size)
    if sensor_width <= 0:
        raise ValueError("sensor_width must be positive")
    if sensor_height <= 0:
        raise ValueError("sensor_height must be positive")
    return int(sensor_height), int(sensor_width)


def _select_episodes(
    episodes: Sequence[Any],
    *,
    target_categories: Sequence[str],
    episodes_per_category: int | None,
    max_episodes: int | None,
) -> list[Any]:
    if not target_categories:
        raise ValueError("At least one target category is required")
    category_filter = {_normalize_yolo_label(category) for category in target_categories}
    filtered = [
        episode
        for episode in episodes
        if _normalize_yolo_label(episode.object_category) in category_filter
    ]
    if episodes_per_category is None:
        selected = filtered
    else:
        counts: dict[str, int] = {}
        selected = []
        for episode in filtered:
            category = _normalize_yolo_label(episode.object_category)
            if counts.get(category, 0) >= episodes_per_category:
                continue
            selected.append(episode)
            counts[category] = counts.get(category, 0) + 1
            if all(counts.get(category, 0) >= episodes_per_category for category in category_filter):
                break
    return selected[:max_episodes] if max_episodes is not None else selected


def _category_counts(episodes: Sequence[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for episode in episodes:
        if isinstance(episode, dict):
            category = str(episode["object_category"])
        else:
            category = str(episode.object_category)
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def _summarize_rgb_noise_run(
    *,
    output_path: Path,
    config_summary: dict[str, Any],
    dataset_dir: Path,
    scene_root: Path,
    scene_dataset_config: Path,
    start_source: str,
    sensor_height: int,
    sensor_width: int,
    max_episodes: int | None,
    rows: Sequence[dict[str, Any]],
    episode_summaries: Sequence[dict[str, Any]],
    debug_png_counts: dict[str, int] | None = None,
    debug_png_skipped_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    artifact_files = {
        "trace": "rgb_noise_trace.csv",
        "summary": "summary.json",
        "memory": "lifelong_memory.sqlite",
        "scene_dataset_config": scene_dataset_config.name,
    }
    if debug_png_counts:
        artifact_files["debug_gate_rejections"] = "debug_gate_rejections/"
    summary = dict(config_summary)
    summary.update(
        {
            "task": "habitat_objectnav_rgb_noise_stress",
            "full_habitat_run": True,
            "dataset_dir": str(dataset_dir),
            "scene_root": str(scene_root),
            "scene_dataset_config": str(scene_dataset_config),
            "start_source": start_source,
            "sensor_size": sensor_width if sensor_width == sensor_height else None,
            "sensor_width": sensor_width,
            "sensor_height": sensor_height,
            "sensor_resolution": f"{sensor_width}x{sensor_height}",
            "max_episodes": max_episodes,
            "episodes_completed": len(episode_summaries),
            "episode_category_counts": _category_counts(episode_summaries),
            "trace_rows": len(rows),
            "evidence_counts": _count_values(rows, "evidence_type"),
            "decision_counts": _count_values(rows, "decision"),
            "raw_decision_counts": _count_values(rows, "raw_decision"),
            "decision_gate_reason_counts": _count_values(
                rows,
                "decision_gate_reason",
            ),
            "oracle_stop_success_rows": sum(
                int(row["oracle_stop_success"]) for row in rows
            ),
            "mean_detector_precision": _mean(rows, "detector_precision"),
            "mean_oracle_recall": _mean(rows, "oracle_recall"),
            "mean_final_p_valid": _mean(episode_summaries, "final_p_valid"),
            "detection_filtered_count": sum(
                int(row.get("detection_filtered_count", 0)) for row in rows
            ),
            "debug_png_counts": dict(sorted((debug_png_counts or {}).items())),
            "debug_png_skipped_counts": dict(
                sorted((debug_png_skipped_counts or {}).items())
            ),
            "episode_summaries": list(episode_summaries),
            "artifact_files": artifact_files,
            "artifact_dir": str(output_path),
            "limits": [
                "V1 reports oracle-stop success rows, not official Habitat SPL.",
                "oracle_bbox detector mode is for Habitat/noise/memory smoke only.",
                "YOLO-World mode depends on ultralytics and local model weights/cache.",
            ],
        }
    )
    return summary


def _mean(rows: Sequence[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return round(float(np.mean(values)), 6)


def _validate_noise_levels(
    noise_levels: Sequence[str],
    rgb_profile: RgbNoiseProfile,
    depth_profile: DepthNoiseProfile,
) -> None:
    if not noise_levels:
        raise ValueError("At least one noise level is required")
    missing_rgb = sorted(set(noise_levels) - set(rgb_profile.levels))
    missing_depth = sorted(set(noise_levels) - set(depth_profile.levels))
    missing = sorted(set(missing_rgb + missing_depth))
    if missing:
        raise ValueError(f"Noise level(s) missing from profiles: {', '.join(missing)}")


def _validate_detector(detector: str, detector_conf: float) -> None:
    if detector not in SUPPORTED_DETECTORS:
        raise ValueError(
            f"detector must be one of: {', '.join(SUPPORTED_DETECTORS)}"
        )
    if not 0.0 <= detector_conf <= 1.0:
        raise ValueError("detector_conf must be in [0, 1]")


def _validate_grounding_dino_text_threshold(text_threshold: float) -> None:
    if not 0.0 <= text_threshold <= 1.0:
        raise ValueError("grounding_dino_text_threshold must be in [0, 1]")


def _validate_grounding_dino_max_image_side(max_image_side: int | None) -> None:
    if max_image_side is not None and max_image_side <= 0:
        raise ValueError("grounding_dino_max_image_side must be positive when provided")


def _validate_memory_ablation(memory_ablation: Sequence[str]) -> None:
    if not memory_ablation:
        raise ValueError("At least one memory ablation is required")
    unknown = sorted(set(memory_ablation) - set(SUPPORTED_MEMORY_ABLATIONS))
    if unknown:
        raise ValueError(
            f"memory_ablation must use {', '.join(SUPPORTED_MEMORY_ABLATIONS)}; "
            f"got {', '.join(unknown)}"
        )


def _validate_yolo_prompt_mode(yolo_prompt_mode: str) -> None:
    if yolo_prompt_mode not in SUPPORTED_YOLO_PROMPT_MODES:
        raise ValueError(
            "yolo_prompt_mode must be one of: "
            f"{', '.join(SUPPORTED_YOLO_PROMPT_MODES)}"
        )


def _validate_debug_export_limit(limit: int) -> None:
    if limit <= 0:
        raise ValueError("debug_export_limit_per_category must be positive")


def _validate_max_detection_area_ratio(max_detection_area_ratio: float | None) -> None:
    if max_detection_area_ratio is None:
        return
    if not 0.0 < max_detection_area_ratio <= 1.0:
        raise ValueError("max_detection_area_ratio must be in (0, 1] or None")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
