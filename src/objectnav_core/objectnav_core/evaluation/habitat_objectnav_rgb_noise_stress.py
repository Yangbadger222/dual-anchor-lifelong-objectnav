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
SUPPORTED_EPISODE_SELECTION_STRATEGIES: tuple[str, ...] = (
    "category_balanced",
    "structured_visibility",
)
SUPPORTED_REPLAY_PROTOCOLS: tuple[str, ...] = (
    "out_and_back",
    "visibility_challenge",
    "geodesic_path",
    "expected_empty_challenge",
)
REPLAY_PHASES: tuple[str, ...] = (
    "approach",
    "confirm",
    "depart",
    "expected_empty",
    "non_confirm",
    "revisit",
)
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
DEFAULT_DEBUG_EXPORT_REPLAY_PHASES: tuple[str, ...] = ()
DEFAULT_DEBUG_EXPORT_EVIDENCE_TYPES: tuple[str, ...] = ()
DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY = 256
DEFAULT_MAX_DETECTION_AREA_RATIO = 0.7
DEFAULT_MEMORY_GEOMETRY_GATE_RADIUS_M: float | None = None
DEFAULT_EPISODE_SELECTION_STRATEGY = "category_balanced"
DEFAULT_REPLAY_PROTOCOL = "out_and_back"
DEFAULT_GEODESIC_PATH_MAX_STEPS = 24
GEODESIC_PATH_CONFIRM_FRAMES = 3
DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS = 2
DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE = 2.0
DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO = 1.2
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


@dataclass(frozen=True)
class ReplayViewCandidate:
    source: str
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    target_pixels: int


@dataclass(frozen=True)
class ReplayStep:
    phase: str
    action: str
    source: str = ""
    position: tuple[float, float, float] | None = None
    rotation: tuple[float, float, float, float] | None = None
    target_pixels: int | None = None
    expected_target_absent: bool = False


@dataclass(frozen=True)
class MemoryGeometryState:
    anchor_x: float | None = None
    anchor_z: float | None = None


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
    debug_export_replay_phases: Sequence[str] = DEFAULT_DEBUG_EXPORT_REPLAY_PHASES,
    debug_export_evidence_types: Sequence[str] = DEFAULT_DEBUG_EXPORT_EVIDENCE_TYPES,
    debug_export_limit_per_category: int = DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY,
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
    memory_geometry_gate_radius_m: float | None = DEFAULT_MEMORY_GEOMETRY_GATE_RADIUS_M,
    episode_selection_strategy: str = DEFAULT_EPISODE_SELECTION_STRATEGY,
    replay_protocol: str = DEFAULT_REPLAY_PROTOCOL,
    geodesic_path_max_steps: int = DEFAULT_GEODESIC_PATH_MAX_STEPS,
    structured_min_goal_viewpoints: int = DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS,
    structured_min_geodesic_distance: float = DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE,
    structured_min_path_complexity_ratio: float = DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO,
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
        debug_export_replay_phases=debug_export_replay_phases,
        debug_export_evidence_types=debug_export_evidence_types,
        debug_export_limit_per_category=debug_export_limit_per_category,
        max_detection_area_ratio=max_detection_area_ratio,
        memory_geometry_gate_radius_m=memory_geometry_gate_radius_m,
        episode_selection_strategy=episode_selection_strategy,
        replay_protocol=replay_protocol,
        geodesic_path_max_steps=geodesic_path_max_steps,
        structured_min_goal_viewpoints=structured_min_goal_viewpoints,
        structured_min_geodesic_distance=structured_min_geodesic_distance,
        structured_min_path_complexity_ratio=structured_min_path_complexity_ratio,
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
        episode_selection_strategy=episode_selection_strategy,
        structured_min_goal_viewpoints=structured_min_goal_viewpoints,
        structured_min_geodesic_distance=structured_min_geodesic_distance,
        structured_min_path_complexity_ratio=structured_min_path_complexity_ratio,
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
    debug_replay_phases = _debug_replay_phase_filter(debug_export_replay_phases)
    debug_evidence_types = _debug_evidence_type_filter(debug_export_evidence_types)
    debug_export_dir_name = _debug_export_directory_name(
        debug_export_gate_rejections=debug_export_gate_rejections,
        debug_export_replay_phases=debug_replay_phases,
        debug_export_evidence_types=debug_evidence_types,
    )
    debug_export_dir = (
        output_path / debug_export_dir_name if debug_export_dir_name else None
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
                            debug_export_replay_phases=debug_replay_phases,
                            debug_export_evidence_types=debug_evidence_types,
                            debug_export_dir=debug_export_dir,
                            debug_export_counts=debug_png_counts,
                            debug_export_skipped_counts=debug_png_skipped_counts,
                            debug_export_limit_per_category=debug_export_limit_per_category,
                            output_path=output_path,
                            max_detection_area_ratio=max_detection_area_ratio,
                            memory_geometry_gate_radius_m=memory_geometry_gate_radius_m,
                            replay_protocol=replay_protocol,
                            geodesic_path_max_steps=geodesic_path_max_steps,
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
        all_episodes=episodes,
        selected_episodes=selected_episodes,
        target_categories=target_categories,
        episode_selection_strategy=episode_selection_strategy,
        replay_protocol=replay_protocol,
        geodesic_path_max_steps=geodesic_path_max_steps,
        structured_min_goal_viewpoints=structured_min_goal_viewpoints,
        structured_min_geodesic_distance=structured_min_geodesic_distance,
        structured_min_path_complexity_ratio=structured_min_path_complexity_ratio,
        rows=trace_rows,
        episode_summaries=episode_summaries,
        debug_png_counts=debug_png_counts,
        debug_png_skipped_counts=debug_png_skipped_counts,
        debug_export_dir_name=debug_export_dir_name,
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
    debug_export_replay_phases: Sequence[str] = DEFAULT_DEBUG_EXPORT_REPLAY_PHASES,
    debug_export_evidence_types: Sequence[str] = DEFAULT_DEBUG_EXPORT_EVIDENCE_TYPES,
    debug_export_limit_per_category: int = DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY,
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
    memory_geometry_gate_radius_m: float | None = DEFAULT_MEMORY_GEOMETRY_GATE_RADIUS_M,
    episode_selection_strategy: str = DEFAULT_EPISODE_SELECTION_STRATEGY,
    replay_protocol: str = DEFAULT_REPLAY_PROTOCOL,
    geodesic_path_max_steps: int = DEFAULT_GEODESIC_PATH_MAX_STEPS,
    structured_min_goal_viewpoints: int = DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS,
    structured_min_geodesic_distance: float = DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE,
    structured_min_path_complexity_ratio: float = DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO,
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
    _validate_debug_export_replay_phases(debug_export_replay_phases)
    _validate_debug_export_evidence_types(debug_export_evidence_types)
    _validate_max_detection_area_ratio(max_detection_area_ratio)
    _validate_memory_geometry_gate_radius(memory_geometry_gate_radius_m)
    _validate_replay_protocol(replay_protocol)
    _validate_geodesic_path_max_steps(geodesic_path_max_steps)
    _validate_episode_selection(
        episode_selection_strategy=episode_selection_strategy,
        structured_min_goal_viewpoints=structured_min_goal_viewpoints,
        structured_min_geodesic_distance=structured_min_geodesic_distance,
        structured_min_path_complexity_ratio=structured_min_path_complexity_ratio,
    )
    sensor_height_resolved, sensor_width_resolved = _resolve_sensor_resolution(
        sensor_size=sensor_size,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
    )
    if episodes_per_category is not None and episodes_per_category <= 0:
        raise ValueError("episodes_per_category must be positive when provided")
    debug_replay_phases = _debug_replay_phase_filter(debug_export_replay_phases)
    debug_evidence_types = _debug_evidence_type_filter(debug_export_evidence_types)
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
        "episode_selection_strategy": episode_selection_strategy,
        "structured_min_goal_viewpoints": int(structured_min_goal_viewpoints),
        "structured_min_geodesic_distance": float(structured_min_geodesic_distance),
        "structured_min_path_complexity_ratio": float(
            structured_min_path_complexity_ratio
        ),
        "memory_ablation": list(memory_ablation),
        "debug_export_gate_rejections": bool(debug_export_gate_rejections),
        "debug_export_categories": sorted(_debug_category_filter(debug_export_categories)),
        "debug_export_replay_phases": _ordered_debug_replay_phases(
            debug_replay_phases
        ),
        "debug_export_evidence_types": _ordered_debug_evidence_types(
            debug_evidence_types
        ),
        "debug_export_directory": _debug_export_directory_name(
            debug_export_gate_rejections=debug_export_gate_rejections,
            debug_export_replay_phases=debug_replay_phases,
            debug_export_evidence_types=debug_evidence_types,
        ),
        "debug_export_limit_per_category": int(debug_export_limit_per_category),
        "max_detection_area_ratio": max_detection_area_ratio,
        "memory_geometry_gate_radius_m": memory_geometry_gate_radius_m,
        "replay_protocol": replay_protocol,
        "revisit_strategy": replay_protocol,
        "geodesic_path_max_steps": int(geodesic_path_max_steps),
        "replay_phases": list(REPLAY_PHASES),
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
    debug_export_replay_phases: set[str] | None = None,
    debug_export_evidence_types: set[str] | None = None,
    debug_export_dir: Path | None = None,
    debug_export_counts: dict[str, int] | None = None,
    debug_export_skipped_counts: dict[str, int] | None = None,
    debug_export_limit_per_category: int = DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY,
    output_path: Path | None = None,
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
    memory_geometry_gate_radius_m: float | None = DEFAULT_MEMORY_GEOMETRY_GATE_RADIUS_M,
    replay_protocol: str = DEFAULT_REPLAY_PROTOCOL,
    geodesic_path_max_steps: int = DEFAULT_GEODESIC_PATH_MAX_STEPS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _validate_replay_protocol(replay_protocol)
    _validate_geodesic_path_max_steps(geodesic_path_max_steps)
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
    if replay_protocol == "visibility_challenge":
        replay_steps = _build_visibility_challenge_replay_steps(
            sim=sim,
            agent=agent,
            episode=episode,
            target_semantic_ids=target_semantic_ids,
            min_target_pixels=min_target_pixels,
        )
    elif replay_protocol == "expected_empty_challenge":
        replay_steps = _build_expected_empty_challenge_replay_steps(
            sim=sim,
            agent=agent,
            episode=episode,
            target_semantic_ids=target_semantic_ids,
            min_target_pixels=min_target_pixels,
        )
    elif replay_protocol == "geodesic_path":
        replay_steps = _build_geodesic_path_replay_steps(
            sim=sim,
            agent=agent,
            episode=episode,
            start=start,
            target_semantic_ids=target_semantic_ids,
            max_steps=geodesic_path_max_steps,
        )
    else:
        replay_steps = _out_and_back_replay_steps(actions)
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
        candidate_born = belief != INITIAL_BELIEF
    else:
        belief = INITIAL_BELIEF
        candidate_born = False
    rows: list[dict[str, Any]] = []
    negative_streak = 0
    memory_geometry_state = MemoryGeometryState()
    previous_pose = _initial_replay_pose_from_steps(replay_steps) or _agent_pose(agent)
    total_steps = len(replay_steps)
    for step_index, replay_step in enumerate(replay_steps):
        action = replay_step.action
        replay_phase = replay_step.phase
        if replay_step.position is not None and replay_step.rotation is not None:
            state = agent.get_state()
            state.position = np.asarray(replay_step.position, dtype=float)
            state.rotation = list(replay_step.rotation)
            agent.set_state(state)
            observations = sim.get_sensor_observations()
        elif action != "reset":
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
        detection_anchor_xz = _estimate_detection_anchor_xz(
            detector_mask=detector_mask,
            depth=noisy_depth,
            agent_pose=pose,
        )
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
        evidence_type, evidence_strength, quarantined, evidence_reason = (
            _apply_expected_empty_context(
                evidence_type=evidence_type,
                evidence_strength=evidence_strength,
                quarantined=quarantined,
                evidence_reason=evidence_reason,
                expected_target_absent=replay_step.expected_target_absent,
                detector_positive=metrics["detector_pixels"] >= min_detector_pixels,
                target_visible=metrics["oracle_target_pixels"] >= min_target_pixels,
            )
        )
        memory_geometry_distance_m: float | None = None
        memory_geometry_gate_reason = ""
        (
            memory_geometry_state,
            evidence_type,
            evidence_strength,
            quarantined,
            evidence_reason,
            memory_geometry_distance_m,
        ) = _apply_memory_geometry_gate(
            state=memory_geometry_state,
            memory_mode=memory_mode,
            evidence_type=evidence_type,
            evidence_strength=evidence_strength,
            quarantined=quarantined,
            evidence_reason=evidence_reason,
            observation_anchor_xz=detection_anchor_xz,
            gate_radius_m=memory_geometry_gate_radius_m,
            agent_pose=pose,
        )
        if evidence_reason == "geometry_inconsistent_positive":
            memory_geometry_gate_reason = evidence_reason
        elif evidence_reason == "geometry_anchor_out_of_view_positive":
            memory_geometry_gate_reason = evidence_reason
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
            candidate_born, belief = _memory_on_belief_update(
                candidate_born=candidate_born,
                belief=belief,
                event=event,
                updater=updater,
            )
        decision = policy.choose(
            belief,
            _decision_context(
                step_index=step_index,
                total_steps=total_steps,
                negative_streak=negative_streak,
                metrics=metrics,
                current_positive_evidence=evidence_type is EvidenceType.POSITIVE,
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
            debug_export_dir is not None
            and debug_export_counts is not None
            and debug_export_skipped_counts is not None
            and _should_export_debug_png(
                object_category=episode.object_category,
                decision=decision.decision,
                gated_decision=gated_decision,
                replay_phase=replay_phase,
                evidence_type=evidence_type,
                debug_categories=debug_export_categories,
                debug_export_gate_rejections=debug_export_gate_rejections,
                debug_export_replay_phases=debug_export_replay_phases,
                debug_export_evidence_types=debug_export_evidence_types,
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
                        "replay_phase": replay_phase,
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
                        "memory_anchor_x": _round_optional(
                            memory_geometry_state.anchor_x
                        ),
                        "memory_anchor_z": _round_optional(
                            memory_geometry_state.anchor_z
                        ),
                        "memory_observation_anchor_x": _round_optional(
                            detection_anchor_xz[0] if detection_anchor_xz else None
                        ),
                        "memory_observation_anchor_z": _round_optional(
                            detection_anchor_xz[1] if detection_anchor_xz else None
                        ),
                        "memory_geometry_distance_m": _round_optional(
                            memory_geometry_distance_m
                        ),
                        "memory_geometry_gate_reason": memory_geometry_gate_reason,
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
                "replay_protocol": replay_protocol,
                "start_source_requested": start_source,
                "start_source_used": start.source_used,
                "replay_source": replay_step.source,
                "replay_source_target_pixels": replay_step.target_pixels,
                "expected_target_absent": replay_step.expected_target_absent,
                "step_index": step_index,
                "action": action,
                "replay_phase": replay_phase,
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
                "memory_anchor_x": _round_optional(memory_geometry_state.anchor_x),
                "memory_anchor_z": _round_optional(memory_geometry_state.anchor_z),
                "memory_observation_anchor_x": _round_optional(
                    detection_anchor_xz[0] if detection_anchor_xz else None
                ),
                "memory_observation_anchor_z": _round_optional(
                    detection_anchor_xz[1] if detection_anchor_xz else None
                ),
                "memory_geometry_distance_m": _round_optional(
                    memory_geometry_distance_m
                ),
                "memory_geometry_gate_reason": memory_geometry_gate_reason,
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
        "replay_protocol": replay_protocol,
        "replay_phase_counts": _count_values(rows, "replay_phase"),
        "trace_rows": len(rows),
        "path_translation_m": round(
            sum(float(row["translation_m"]) for row in rows),
            6,
        ),
        "episode_geodesic_distance": getattr(episode, "geodesic_distance", None),
        "episode_euclidean_distance": getattr(episode, "euclidean_distance", None),
        "target_visible_rows": sum(int(row["target_visible"]) for row in rows),
        "oracle_stop_success_rows": sum(
            int(row["oracle_stop_success"]) for row in rows
        ),
        "final_p_valid": round(belief.p_valid, 6),
        **_episode_timing_metrics(rows),
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


def _round_optional(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


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
    return _should_export_debug_png(
        object_category=object_category,
        decision=decision,
        gated_decision=gated_decision,
        replay_phase="",
        evidence_type=EvidenceType.UNKNOWN,
        debug_categories=debug_categories,
        debug_export_gate_rejections=True,
        debug_export_replay_phases=set(),
        debug_export_evidence_types=set(),
    )


def _should_export_debug_png(
    *,
    object_category: str,
    decision: DecisionType,
    gated_decision: DecisionType,
    replay_phase: str,
    evidence_type: EvidenceType,
    debug_categories: set[str] | None,
    debug_export_gate_rejections: bool,
    debug_export_replay_phases: set[str] | None,
    debug_export_evidence_types: set[str] | None,
) -> bool:
    if not _debug_category_matches(object_category, debug_categories):
        return False
    if (
        debug_export_gate_rejections
        and decision is DecisionType.TRUST
        and gated_decision is not DecisionType.TRUST
    ):
        return True
    return _debug_trace_filter_matches(
        replay_phase=replay_phase,
        evidence_type=evidence_type,
        debug_export_replay_phases=debug_export_replay_phases,
        debug_export_evidence_types=debug_export_evidence_types,
    )


def _debug_category_matches(
    object_category: str,
    debug_categories: set[str] | None,
) -> bool:
    normalized_categories = {
        _debug_category_token(category) for category in (debug_categories or set())
    }
    return not normalized_categories or (
        _debug_category_token(object_category) in normalized_categories
    )


def _debug_trace_filter_matches(
    *,
    replay_phase: str,
    evidence_type: EvidenceType,
    debug_export_replay_phases: set[str] | None,
    debug_export_evidence_types: set[str] | None,
) -> bool:
    phase_filter = debug_export_replay_phases or set()
    evidence_filter = debug_export_evidence_types or set()
    if not phase_filter and not evidence_filter:
        return False
    if phase_filter and replay_phase not in phase_filter:
        return False
    if evidence_filter and evidence_type.value not in evidence_filter:
        return False
    return True


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
            "debug PNG export."
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
            f"step={metadata.get('step_index')} phase={metadata.get('replay_phase')} "
            f"action={metadata.get('action')}"
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
    phase = _sanitize_debug_token(str(metadata.get("replay_phase", "unknown")))
    evidence = _sanitize_debug_token(str(metadata.get("evidence_type", "unknown")))
    reason = _sanitize_debug_token(
        str(metadata.get("decision_gate_reason", "trust_rejected"))
    )
    episode = _sanitize_debug_token(str(metadata.get("episode_index", "unknown")))
    step = _sanitize_debug_token(str(metadata.get("step_index", "unknown")))
    return (
        f"{sequence_id:03d}_{category}_{memory}_{noise}_"
        f"ep{episode}_step{step}_{phase}_{evidence}_{reason}.png"
    )


def _debug_category_filter(categories: Sequence[str]) -> set[str]:
    return {_debug_category_token(category) for category in categories}


def _debug_replay_phase_filter(phases: Sequence[str]) -> set[str]:
    return {phase.strip().lower() for phase in phases if phase.strip()}


def _debug_evidence_type_filter(evidence_types: Sequence[str]) -> set[str]:
    return {
        evidence_type.strip().lower()
        for evidence_type in evidence_types
        if evidence_type.strip()
    }


def _ordered_debug_replay_phases(phases: set[str]) -> list[str]:
    return [phase for phase in REPLAY_PHASES if phase in phases]


def _ordered_debug_evidence_types(evidence_types: set[str]) -> list[str]:
    return [
        evidence.value for evidence in EvidenceType if evidence.value in evidence_types
    ]


def _debug_export_directory_name(
    *,
    debug_export_gate_rejections: bool,
    debug_export_replay_phases: set[str],
    debug_export_evidence_types: set[str],
) -> str | None:
    if not (
        debug_export_gate_rejections
        or debug_export_replay_phases
        or debug_export_evidence_types
    ):
        return None
    if debug_export_gate_rejections and not (
        debug_export_replay_phases or debug_export_evidence_types
    ):
        return "debug_gate_rejections"
    return "debug_rows"


def _debug_category_token(category: str) -> str:
    return _normalize_yolo_label(category).replace(" ", "_")


def _sanitize_debug_token(value: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip())
    return token.strip("-") or "unknown"


def _out_and_back_replay_steps(actions: Sequence[str]) -> tuple[ReplayStep, ...]:
    total_steps = len(actions) + 1
    return tuple(
        ReplayStep(
            phase=_replay_phase(step_index, total_steps=total_steps),
            action=action,
        )
        for step_index, action in enumerate(("reset", *actions))
    )


def _initial_replay_pose_from_steps(
    replay_steps: Sequence[ReplayStep],
) -> tuple[tuple[float, float, float], tuple[float, float, float, float]] | None:
    if not replay_steps:
        return None
    first = replay_steps[0]
    if first.position is None or first.rotation is None:
        return None
    return first.position, first.rotation


def _visibility_challenge_replay_steps(
    candidates: Sequence[ReplayViewCandidate],
    *,
    min_target_pixels: int,
) -> tuple[ReplayStep, ...]:
    visible_candidates = [
        candidate
        for candidate in candidates
        if candidate.target_pixels >= min_target_pixels
    ]
    hidden_candidates = [
        candidate
        for candidate in candidates
        if candidate.target_pixels < min_target_pixels
    ]
    if not visible_candidates:
        raise ValueError("visibility_challenge requires a target-visible view")
    if not hidden_candidates:
        raise ValueError("visibility_challenge requires a target-hidden view")
    visible = max(visible_candidates, key=lambda candidate: candidate.target_pixels)
    hidden = min(hidden_candidates, key=lambda candidate: candidate.target_pixels)
    plan = (
        ("confirm", visible, 3),
        ("depart", hidden, 2),
        ("non_confirm", hidden, 4),
        ("revisit", visible, 4),
    )
    steps: list[ReplayStep] = []
    for phase, candidate, count in plan:
        for index in range(count):
            steps.append(
                ReplayStep(
                    phase=phase,
                    action="reset" if not steps else f"teleport_{phase}",
                    source=candidate.source,
                    position=candidate.position,
                    rotation=candidate.rotation,
                    target_pixels=candidate.target_pixels,
                )
            )
    return tuple(steps)


def _expected_empty_challenge_replay_steps(
    candidates: Sequence[ReplayViewCandidate],
    *,
    min_target_pixels: int,
) -> tuple[ReplayStep, ...]:
    visible_candidates = [
        candidate
        for candidate in candidates
        if candidate.target_pixels >= min_target_pixels
    ]
    hidden_candidates = [
        candidate
        for candidate in candidates
        if candidate.target_pixels < min_target_pixels
    ]
    if not visible_candidates:
        raise ValueError("expected_empty_challenge requires a target-visible view")
    if not hidden_candidates:
        raise ValueError("expected_empty_challenge requires a target-hidden view")
    visible = max(visible_candidates, key=lambda candidate: candidate.target_pixels)
    hidden = min(hidden_candidates, key=lambda candidate: candidate.target_pixels)
    plan = (
        ("confirm", visible, 3, False),
        ("expected_empty", hidden, 4, True),
        ("revisit", visible, 4, False),
    )
    steps: list[ReplayStep] = []
    for phase, candidate, count, expected_absent in plan:
        for _ in range(count):
            steps.append(
                ReplayStep(
                    phase=phase,
                    action="reset" if not steps else f"teleport_{phase}",
                    source=candidate.source,
                    position=candidate.position,
                    rotation=candidate.rotation,
                    target_pixels=candidate.target_pixels,
                    expected_target_absent=expected_absent,
                )
            )
    return tuple(steps)


def _geodesic_path_replay_steps(
    *,
    waypoints: Sequence[ReplayViewCandidate],
    goal: ReplayViewCandidate,
    confirm_frames: int = GEODESIC_PATH_CONFIRM_FRAMES,
) -> tuple[ReplayStep, ...]:
    steps: list[ReplayStep] = []
    for waypoint in waypoints:
        steps.append(
            ReplayStep(
                phase="approach",
                action="reset" if not steps else "teleport_approach",
                source=waypoint.source,
                position=waypoint.position,
                rotation=waypoint.rotation,
                target_pixels=waypoint.target_pixels,
            )
        )
    for _ in range(confirm_frames):
        steps.append(
            ReplayStep(
                phase="confirm",
                action="reset" if not steps else "teleport_confirm",
                source=goal.source,
                position=goal.position,
                rotation=goal.rotation,
                target_pixels=goal.target_pixels,
            )
        )
    return tuple(steps)


def _resample_path_positions(
    points: Sequence[tuple[float, float, float]],
    *,
    max_points: int,
) -> tuple[tuple[float, float, float], ...]:
    if max_points <= 0:
        raise ValueError("max_points must be positive")
    if len(points) <= max_points:
        return tuple(points)
    if max_points == 1:
        return (tuple(points[-1]),)
    indices = np.linspace(0, len(points) - 1, num=max_points)
    return tuple(tuple(points[int(round(index))]) for index in indices)


def _build_geodesic_path_replay_steps(
    *,
    sim: Any,
    agent: Any,
    episode: Any,
    start: Any,
    target_semantic_ids: Sequence[int],
    max_steps: int,
) -> tuple[ReplayStep, ...]:
    goal = _first_goal_view_candidate(
        sim=sim,
        agent=agent,
        episode=episode,
        target_semantic_ids=target_semantic_ids,
    )
    path_points = _shortest_path_points(
        sim=sim,
        start=start.position,
        end=goal.position,
    )
    sampled_points = _resample_path_positions(
        path_points[:-1] if len(path_points) > 1 else path_points,
        max_points=max(1, max_steps),
    )
    waypoints: list[ReplayViewCandidate] = []
    for index, position in enumerate(sampled_points):
        next_position = (
            sampled_points[index + 1]
            if index + 1 < len(sampled_points)
            else goal.position
        )
        rotation = _look_at_quaternion_xyzw(position, next_position)
        waypoints.append(
            _measure_replay_view_candidate(
                sim=sim,
                agent=agent,
                source=f"geodesic_path:waypoint:{index}",
                position=position,
                rotation=rotation,
                target_semantic_ids=target_semantic_ids,
            )
        )
    return _geodesic_path_replay_steps(waypoints=waypoints, goal=goal)


def _build_visibility_challenge_replay_steps(
    *,
    sim: Any,
    agent: Any,
    episode: Any,
    target_semantic_ids: Sequence[int],
    min_target_pixels: int,
) -> tuple[ReplayStep, ...]:
    candidates = _sample_replay_view_candidates(
        sim=sim,
        agent=agent,
        episode=episode,
        target_semantic_ids=target_semantic_ids,
    )
    return _visibility_challenge_replay_steps(
        candidates,
        min_target_pixels=min_target_pixels,
    )


def _build_expected_empty_challenge_replay_steps(
    *,
    sim: Any,
    agent: Any,
    episode: Any,
    target_semantic_ids: Sequence[int],
    min_target_pixels: int,
) -> tuple[ReplayStep, ...]:
    candidates = _sample_replay_view_candidates(
        sim=sim,
        agent=agent,
        episode=episode,
        target_semantic_ids=target_semantic_ids,
    )
    return _expected_empty_challenge_replay_steps(
        candidates,
        min_target_pixels=min_target_pixels,
    )


def _sample_replay_view_candidates(
    *,
    sim: Any,
    agent: Any,
    episode: Any,
    target_semantic_ids: Sequence[int],
) -> tuple[ReplayViewCandidate, ...]:
    candidates: list[ReplayViewCandidate] = []
    for index, viewpoint in enumerate(getattr(episode, "goal_viewpoints", ()) or ()):
        agent_state = viewpoint.get("agent_state", {})
        position = _tuple3_from_any(agent_state.get("position"))
        rotation = _tuple4_from_any(agent_state.get("rotation"))
        if position is None or rotation is None:
            continue
        candidates.append(
            _measure_replay_view_candidate(
                sim=sim,
                agent=agent,
                source=f"goal_viewpoint:{index}",
                position=position,
                rotation=rotation,
                target_semantic_ids=target_semantic_ids,
            )
        )
        candidates.append(
            _measure_replay_view_candidate(
                sim=sim,
                agent=agent,
                source=f"goal_viewpoint:{index}_turn_around",
                position=position,
                rotation=_yaw_180_quaternion_xyzw(rotation),
                target_semantic_ids=target_semantic_ids,
            )
        )
    if not candidates:
        start = _select_episode_start(episode, start_source="episode_start")
        candidates.append(
            _measure_replay_view_candidate(
                sim=sim,
                agent=agent,
                source="episode_start",
                position=start.position,
                rotation=start.rotation,
                target_semantic_ids=target_semantic_ids,
            )
        )
    return tuple(candidates)


def _first_goal_view_candidate(
    *,
    sim: Any,
    agent: Any,
    episode: Any,
    target_semantic_ids: Sequence[int],
) -> ReplayViewCandidate:
    for index, viewpoint in enumerate(getattr(episode, "goal_viewpoints", ()) or ()):
        agent_state = viewpoint.get("agent_state", {})
        position = _tuple3_from_any(agent_state.get("position"))
        rotation = _tuple4_from_any(agent_state.get("rotation"))
        if position is None or rotation is None:
            continue
        return _measure_replay_view_candidate(
            sim=sim,
            agent=agent,
            source=f"goal_viewpoint:{index}",
            position=position,
            rotation=rotation,
            target_semantic_ids=target_semantic_ids,
        )
    goal_position = _first_goal_position(episode)
    if goal_position is None:
        raise ValueError("geodesic_path requires an episode goal viewpoint")
    return _measure_replay_view_candidate(
        sim=sim,
        agent=agent,
        source="goal_position",
        position=goal_position,
        rotation=(0.0, 0.0, 0.0, 1.0),
        target_semantic_ids=target_semantic_ids,
    )


def _shortest_path_points(
    *,
    sim: Any,
    start: tuple[float, float, float],
    end: tuple[float, float, float],
) -> tuple[tuple[float, float, float], ...]:
    if not sim.pathfinder.is_loaded:
        raise RuntimeError("geodesic_path requires a loaded Habitat navmesh")
    try:
        import habitat_sim
    except ModuleNotFoundError as exc:
        raise RuntimeError("Habitat-Sim is required for geodesic_path replay") from exc
    path = habitat_sim.ShortestPath()
    path.requested_start = np.asarray(start, dtype=float)
    path.requested_end = np.asarray(end, dtype=float)
    found_path = bool(sim.pathfinder.find_path(path))
    points = getattr(path, "points", None)
    if not found_path or points is None or len(points) == 0:
        raise ValueError("geodesic_path could not find a navmesh path to the goal")
    return tuple(
        _tuple3_from_any(point) or tuple(float(value) for value in point)
        for point in points
    )


def _measure_replay_view_candidate(
    *,
    sim: Any,
    agent: Any,
    source: str,
    position: tuple[float, float, float],
    rotation: tuple[float, float, float, float],
    target_semantic_ids: Sequence[int],
) -> ReplayViewCandidate:
    state = agent.get_state()
    state.position = np.asarray(position, dtype=float)
    state.rotation = list(rotation)
    agent.set_state(state)
    observations = sim.get_sensor_observations()
    semantic = np.asarray(observations["semantic"])
    target_pixels = int(np.isin(semantic, list(target_semantic_ids)).sum())
    return ReplayViewCandidate(
        source=source,
        position=position,
        rotation=rotation,
        target_pixels=target_pixels,
    )


def _tuple3_from_any(value: Any) -> tuple[float, float, float] | None:
    if value is None:
        return None
    values = tuple(float(part) for part in value)
    if len(values) != 3:
        return None
    return values


def _tuple4_from_any(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    values = tuple(float(part) for part in value)
    if len(values) != 4:
        return None
    return values


def _yaw_180_quaternion_xyzw(
    rotation: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    x, y, z, w = rotation
    return _normalize_quaternion_xyzw((z, w, -x, -y))


def _look_at_quaternion_xyzw(
    position: tuple[float, float, float],
    target: tuple[float, float, float],
) -> tuple[float, float, float, float]:
    dx = float(target[0] - position[0])
    dz = float(target[2] - position[2])
    if abs(dx) + abs(dz) < 1e-6:
        return (0.0, 0.0, 0.0, 1.0)
    yaw = float(np.arctan2(-dx, -dz))
    half_yaw = yaw / 2.0
    return _normalize_quaternion_xyzw(
        (0.0, float(np.sin(half_yaw)), 0.0, float(np.cos(half_yaw)))
    )


def _normalize_quaternion_xyzw(
    rotation: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    norm = float(np.sqrt(sum(value * value for value in rotation)))
    if norm == 0.0:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(float(value / norm) for value in rotation)  # type: ignore[return-value]


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


def _memory_on_belief_update(
    *,
    candidate_born: bool,
    belief: MemoryBelief,
    event: EvidenceEvent,
    updater: UsabilityUpdater,
) -> tuple[bool, MemoryBelief]:
    if not candidate_born and event.evidence_type is not EvidenceType.POSITIVE:
        return False, belief
    return True, updater.apply(belief, event)


def _apply_memory_geometry_gate(
    *,
    state: MemoryGeometryState,
    memory_mode: str,
    evidence_type: EvidenceType,
    evidence_strength: float,
    quarantined: bool,
    evidence_reason: str,
    observation_anchor_xz: tuple[float, float] | None,
    gate_radius_m: float | None,
    agent_pose: (
        tuple[tuple[float, float, float], tuple[float, float, float, float]] | None
    ) = None,
    hfov_degrees: float = 79.0,
) -> tuple[MemoryGeometryState, EvidenceType, float, bool, str, float | None]:
    if (
        memory_mode != "on"
        or gate_radius_m is None
        or evidence_type is not EvidenceType.POSITIVE
        or observation_anchor_xz is None
    ):
        return (
            state,
            evidence_type,
            evidence_strength,
            quarantined,
            evidence_reason,
            None,
        )
    obs_x, obs_z = observation_anchor_xz
    if state.anchor_x is None or state.anchor_z is None:
        return (
            MemoryGeometryState(anchor_x=obs_x, anchor_z=obs_z),
            evidence_type,
            evidence_strength,
            quarantined,
            evidence_reason,
            None,
        )
    distance_m = float(np.hypot(obs_x - state.anchor_x, obs_z - state.anchor_z))
    if agent_pose is not None and not _anchor_in_camera_fov(
        anchor_xz=(state.anchor_x, state.anchor_z),
        agent_pose=agent_pose,
        hfov_degrees=hfov_degrees,
    ):
        return (
            state,
            EvidenceType.UNKNOWN,
            0.35,
            True,
            "geometry_anchor_out_of_view_positive",
            round(distance_m, 6),
        )
    if distance_m > gate_radius_m:
        return (
            state,
            EvidenceType.UNKNOWN,
            0.35,
            True,
            "geometry_inconsistent_positive",
            round(distance_m, 6),
        )
    return (
        state,
        evidence_type,
        evidence_strength,
        quarantined,
        evidence_reason,
        round(distance_m, 6),
    )


def _anchor_in_camera_fov(
    *,
    anchor_xz: tuple[float, float],
    agent_pose: tuple[tuple[float, float, float], tuple[float, float, float, float]],
    hfov_degrees: float = 79.0,
) -> bool:
    position, rotation = agent_pose
    dx = anchor_xz[0] - position[0]
    dz = anchor_xz[1] - position[2]
    if abs(dx) + abs(dz) < 1e-6:
        return True
    target_bearing = float(np.arctan2(-dx, -dz))
    delta = _wrap_angle_rad(target_bearing - _yaw_from_quaternion_xyzw(rotation))
    return abs(delta) <= np.deg2rad(hfov_degrees) / 2.0


def _wrap_angle_rad(value: float) -> float:
    return float((value + np.pi) % (2.0 * np.pi) - np.pi)


def _estimate_detection_anchor_xz(
    *,
    detector_mask: np.ndarray,
    depth: np.ndarray,
    agent_pose: tuple[tuple[float, float, float], tuple[float, float, float, float]],
    hfov_degrees: float = 79.0,
) -> tuple[float, float] | None:
    bbox = _mask_bbox(detector_mask)
    if bbox is None:
        return None
    x1, y1, x2, y2 = bbox
    center_x = (x1 + x2 - 1) / 2.0
    center_y = (y1 + y2 - 1) / 2.0
    depth_arr = np.asarray(depth, dtype=float)
    height, width = depth_arr.shape[:2]
    if height <= 0 or width <= 0:
        return None
    patch = depth_arr[max(0, y1):min(height, y2), max(0, x1):min(width, x2)]
    finite = patch[np.isfinite(patch) & (patch > 0.0)]
    if finite.size == 0:
        return None
    distance = float(np.median(finite))
    horizontal_offset = (center_x - (width - 1) / 2.0) / max(1.0, (width - 1) / 2.0)
    bearing = horizontal_offset * np.deg2rad(hfov_degrees) / 2.0
    yaw = _yaw_from_quaternion_xyzw(agent_pose[1])
    world_angle = yaw + bearing
    position = agent_pose[0]
    return (
        round(float(position[0] - distance * np.sin(world_angle)), 6),
        round(float(position[2] - distance * np.cos(world_angle)), 6),
    )


def _yaw_from_quaternion_xyzw(
    rotation: tuple[float, float, float, float],
) -> float:
    x, y, z, w = rotation
    siny_cosp = 2.0 * (w * y + x * z)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return float(np.arctan2(siny_cosp, cosy_cosp))


def _apply_expected_empty_context(
    *,
    evidence_type: EvidenceType,
    evidence_strength: float,
    quarantined: bool,
    evidence_reason: str,
    expected_target_absent: bool,
    detector_positive: bool,
    target_visible: bool,
) -> tuple[EvidenceType, float, bool, str]:
    if (
        expected_target_absent
        and not detector_positive
        and not target_visible
        and evidence_type is not EvidenceType.POSITIVE
    ):
        return (
            EvidenceType.NON_CONFIRMATION,
            1.0,
            False,
            "expected_location_empty",
        )
    return evidence_type, evidence_strength, quarantined, evidence_reason


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
    episode_selection_strategy: str = DEFAULT_EPISODE_SELECTION_STRATEGY,
    structured_min_goal_viewpoints: int = DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS,
    structured_min_geodesic_distance: float = DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE,
    structured_min_path_complexity_ratio: float = DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO,
) -> list[Any]:
    if not target_categories:
        raise ValueError("At least one target category is required")
    _validate_episode_selection(
        episode_selection_strategy=episode_selection_strategy,
        structured_min_goal_viewpoints=structured_min_goal_viewpoints,
        structured_min_geodesic_distance=structured_min_geodesic_distance,
        structured_min_path_complexity_ratio=structured_min_path_complexity_ratio,
    )
    category_filter = {_normalize_yolo_label(category) for category in target_categories}
    filtered = [
        episode
        for episode in episodes
        if _normalize_yolo_label(episode.object_category) in category_filter
    ]
    if episode_selection_strategy == "structured_visibility":
        filtered = [
            episode
            for episode in filtered
            if _is_structured_episode_candidate(
                episode,
                min_goal_viewpoints=structured_min_goal_viewpoints,
                min_geodesic_distance=structured_min_geodesic_distance,
                min_path_complexity_ratio=structured_min_path_complexity_ratio,
            )
        ]
        filtered = sorted(
            filtered,
            key=_structured_episode_sort_key,
            reverse=True,
        )
    if (
        episode_selection_strategy == "structured_visibility"
        and episodes_per_category is not None
    ):
        selected = []
        for category in target_categories:
            normalized_category = _normalize_yolo_label(category)
            category_candidates = [
                episode
                for episode in filtered
                if _normalize_yolo_label(episode.object_category) == normalized_category
            ]
            selected.extend(category_candidates[:episodes_per_category])
    elif episodes_per_category is None:
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


def _is_structured_episode_candidate(
    episode: Any,
    *,
    min_goal_viewpoints: int,
    min_geodesic_distance: float,
    min_path_complexity_ratio: float,
) -> bool:
    if len(getattr(episode, "goal_viewpoints", ()) or ()) < min_goal_viewpoints:
        return False
    geodesic_distance = getattr(episode, "geodesic_distance", None)
    if geodesic_distance is None or float(geodesic_distance) < min_geodesic_distance:
        return False
    return _episode_path_complexity_ratio(episode) >= min_path_complexity_ratio


def _structured_episode_sort_key(episode: Any) -> tuple[float, float, int]:
    return (
        _episode_path_complexity_ratio(episode),
        float(getattr(episode, "geodesic_distance", 0.0) or 0.0),
        len(getattr(episode, "goal_viewpoints", ()) or ()),
    )


def _episode_path_complexity_ratio(episode: Any) -> float:
    geodesic_distance = getattr(episode, "geodesic_distance", None)
    euclidean_distance = getattr(episode, "euclidean_distance", None)
    if geodesic_distance is None or euclidean_distance is None:
        return 0.0
    euclidean = max(float(euclidean_distance), 1e-6)
    return float(geodesic_distance) / euclidean


def _replay_phase(step_index: int, *, total_steps: int) -> str:
    if total_steps <= 1:
        return "confirm"
    confirm_end = max(1, total_steps // 5)
    depart_end = max(confirm_end + 1, total_steps // 2)
    non_confirm_end = max(depart_end + 1, (total_steps * 3) // 4)
    if step_index < confirm_end:
        return "confirm"
    if step_index < depart_end:
        return "depart"
    if step_index < non_confirm_end:
        return "non_confirm"
    return "revisit"


def _episode_selection_summary(
    *,
    all_episodes: Sequence[Any],
    selected_episodes: Sequence[Any],
    target_categories: Sequence[str],
    episode_selection_strategy: str,
    structured_min_goal_viewpoints: int,
    structured_min_geodesic_distance: float,
    structured_min_path_complexity_ratio: float,
) -> dict[str, Any]:
    category_order = [
        (str(category), _normalize_yolo_label(category))
        for category in target_categories
    ]
    category_filter = {normalized for _, normalized in category_order}
    category_candidates = [
        episode
        for episode in all_episodes
        if _normalize_yolo_label(episode.object_category) in category_filter
    ]
    structured_candidates = [
        episode
        for episode in category_candidates
        if _is_structured_episode_candidate(
            episode,
            min_goal_viewpoints=structured_min_goal_viewpoints,
            min_geodesic_distance=structured_min_geodesic_distance,
            min_path_complexity_ratio=structured_min_path_complexity_ratio,
        )
    ]
    candidate_count = (
        len(structured_candidates)
        if episode_selection_strategy == "structured_visibility"
        else len(category_candidates)
    )
    category_audit: dict[str, Any] = {}
    zero_structured_categories: list[str] = []
    for category_key, category in category_order:
        category_all = [
            episode
            for episode in category_candidates
            if _normalize_yolo_label(episode.object_category) == category
        ]
        category_structured = [
            episode
            for episode in structured_candidates
            if _normalize_yolo_label(episode.object_category) == category
        ]
        category_selected = [
            episode
            for episode in selected_episodes
            if _normalize_yolo_label(episode.object_category) == category
        ]
        if episode_selection_strategy == "structured_visibility":
            category_candidate_count = len(category_structured)
            dropped_count = max(0, len(category_all) - len(category_structured))
            if not category_all:
                selection_status = "no_category_candidates"
                zero_structured_categories.append(category_key)
            elif not category_structured:
                selection_status = "no_structured_candidates"
                zero_structured_categories.append(category_key)
            elif category_selected:
                selection_status = "selected"
            else:
                selection_status = "structured_candidates_not_selected"
        else:
            category_candidate_count = len(category_all)
            dropped_count = 0
            if not category_all:
                selection_status = "no_category_candidates"
            elif category_selected:
                selection_status = "selected"
            else:
                selection_status = "category_candidates_not_selected"
        category_audit[category_key] = {
            "category_candidate_episode_count": len(category_all),
            "structured_candidate_episode_count": len(category_structured),
            "candidate_episode_count": category_candidate_count,
            "selected_episode_count": len(category_selected),
            "selected_episode_ids": [
                str(getattr(episode, "episode_id")) for episode in category_selected
            ],
            "dropped_by_structured_filter_count": dropped_count,
            "selection_status": selection_status,
        }
    return {
        "episode_selection_strategy": episode_selection_strategy,
        "category_candidate_episode_count": len(category_candidates),
        "candidate_episode_count": candidate_count,
        "selected_episode_count": len(selected_episodes),
        "dropped_by_structured_filter_count": max(
            0,
            len(category_candidates) - len(structured_candidates),
        )
        if episode_selection_strategy == "structured_visibility"
        else 0,
        "structured_min_goal_viewpoints": int(structured_min_goal_viewpoints),
        "structured_min_geodesic_distance": float(structured_min_geodesic_distance),
        "structured_min_path_complexity_ratio": float(
            structured_min_path_complexity_ratio
        ),
        "selected_episode_ids": [
            str(getattr(episode, "episode_id")) for episode in selected_episodes
        ],
        "selected_category_counts": _category_counts(selected_episodes),
        "zero_structured_candidate_categories": zero_structured_categories,
        "category_audit": category_audit,
    }


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
    all_episodes: Sequence[Any] = (),
    selected_episodes: Sequence[Any] = (),
    target_categories: Sequence[str] = TARGET_CATEGORIES,
    episode_selection_strategy: str = DEFAULT_EPISODE_SELECTION_STRATEGY,
    replay_protocol: str = DEFAULT_REPLAY_PROTOCOL,
    geodesic_path_max_steps: int = DEFAULT_GEODESIC_PATH_MAX_STEPS,
    structured_min_goal_viewpoints: int = DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS,
    structured_min_geodesic_distance: float = DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE,
    structured_min_path_complexity_ratio: float = DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO,
    rows: Sequence[dict[str, Any]],
    episode_summaries: Sequence[dict[str, Any]],
    debug_png_counts: dict[str, int] | None = None,
    debug_png_skipped_counts: dict[str, int] | None = None,
    debug_export_dir_name: str | None = None,
) -> dict[str, Any]:
    artifact_files = {
        "trace": "rgb_noise_trace.csv",
        "summary": "summary.json",
        "memory": "lifelong_memory.sqlite",
        "scene_dataset_config": scene_dataset_config.name,
    }
    if debug_png_counts and debug_export_dir_name is not None:
        artifact_key = (
            "debug_gate_rejections"
            if debug_export_dir_name == "debug_gate_rejections"
            else "debug_rows"
        )
        artifact_files[artifact_key] = f"{debug_export_dir_name}/"
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
            "replay_protocol": replay_protocol,
            "revisit_strategy": replay_protocol,
            "episode_selection": _episode_selection_summary(
                all_episodes=all_episodes,
                selected_episodes=selected_episodes,
                target_categories=target_categories,
                episode_selection_strategy=episode_selection_strategy,
                structured_min_goal_viewpoints=structured_min_goal_viewpoints,
                structured_min_geodesic_distance=structured_min_geodesic_distance,
                structured_min_path_complexity_ratio=structured_min_path_complexity_ratio,
            ),
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
            "replay_phase_counts": _count_values(rows, "replay_phase"),
            "replay_phase_evidence_counts": _nested_count_values(
                rows,
                "replay_phase",
                "evidence_type",
            ),
            "replay_phase_decision_counts": _nested_count_values(
                rows,
                "replay_phase",
                "decision",
            ),
            "replay_phase_raw_decision_counts": _nested_count_values(
                rows,
                "replay_phase",
                "raw_decision",
            ),
            "oracle_stop_success_rows": sum(
                int(row["oracle_stop_success"]) for row in rows
            ),
            "mean_detector_precision": _mean(rows, "detector_precision"),
            "mean_oracle_recall": _mean(rows, "oracle_recall"),
            "mean_final_p_valid": _mean(episode_summaries, "final_p_valid"),
            "memory_mode_metrics": _memory_mode_metrics(
                rows=rows,
                episode_summaries=episode_summaries,
            ),
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


def _episode_timing_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    first_positive = _first_row(rows, lambda row: row.get("evidence_type") == "positive")
    first_raw_trust = _first_row(rows, lambda row: row.get("raw_decision") == "trust")
    first_gated_trust = _first_row(rows, lambda row: row.get("decision") == "trust")
    first_success = _first_row(rows, lambda row: bool(row.get("oracle_stop_success")))
    return {
        "first_positive_step": _row_step(first_positive),
        "first_positive_phase": _row_phase(first_positive),
        "first_raw_trust_step": _row_step(first_raw_trust),
        "first_raw_trust_phase": _row_phase(first_raw_trust),
        "first_gated_trust_step": _row_step(first_gated_trust),
        "first_gated_trust_phase": _row_phase(first_gated_trust),
        "first_oracle_stop_success_step": _row_step(first_success),
        "first_oracle_stop_success_phase": _row_phase(first_success),
        "path_translation_to_first_success_m": _path_translation_to_row(
            rows,
            first_success,
        ),
        "successful_replay": first_success is not None,
    }


def _memory_mode_metrics(
    *,
    rows: Sequence[dict[str, Any]],
    episode_summaries: Sequence[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    memory_modes = sorted(
        {
            str(row["memory_mode"])
            for row in rows
            if row.get("memory_mode") is not None
        }
        | {
            str(summary["memory_mode"])
            for summary in episode_summaries
            if summary.get("memory_mode") is not None
        }
    )
    metrics: dict[str, dict[str, Any]] = {}
    for memory_mode in memory_modes:
        mode_rows = [row for row in rows if row.get("memory_mode") == memory_mode]
        mode_summaries = [
            summary
            for summary in episode_summaries
            if summary.get("memory_mode") == memory_mode
        ]
        metrics[memory_mode] = {
            "episodes": len(mode_summaries),
            "success_episodes": sum(
                int(_episode_summary_successful(summary))
                for summary in mode_summaries
            ),
            "success_rows": sum(
                int(row.get("oracle_stop_success", False)) for row in mode_rows
            ),
            "raw_trust_rows": sum(
                int(row.get("raw_decision") == "trust") for row in mode_rows
            ),
            "gate_rejection_rows": sum(
                int(
                    row.get("decision_gate_reason")
                    in {
                        "target_not_currently_visible",
                        "missing_current_positive_evidence",
                    }
                )
                for row in mode_rows
            ),
            "mean_first_success_step": _mean(
                mode_summaries,
                "first_oracle_stop_success_step",
            ),
            "mean_path_translation_to_first_success_m": _mean(
                mode_summaries,
                "path_translation_to_first_success_m",
            ),
            "mean_final_p_valid": _mean(mode_summaries, "final_p_valid"),
        }
    return metrics


def _episode_summary_successful(summary: dict[str, Any]) -> bool:
    if summary.get("successful_replay") is not None:
        return bool(summary["successful_replay"])
    if summary.get("first_oracle_stop_success_step") is not None:
        return True
    return int(summary.get("oracle_stop_success_rows", 0)) > 0


def _first_row(
    rows: Sequence[dict[str, Any]],
    predicate: Any,
) -> dict[str, Any] | None:
    for row in rows:
        if predicate(row):
            return row
    return None


def _row_step(row: dict[str, Any] | None) -> int | None:
    if row is None or row.get("step_index") is None:
        return None
    return int(row["step_index"])


def _row_phase(row: dict[str, Any] | None) -> str | None:
    if row is None or row.get("replay_phase") is None:
        return None
    return str(row["replay_phase"])


def _path_translation_to_row(
    rows: Sequence[dict[str, Any]],
    target_row: dict[str, Any] | None,
) -> float | None:
    if target_row is None:
        return None
    target_step = _row_step(target_row)
    if target_step is None:
        return None
    return round(
        sum(
            float(row.get("translation_m", 0.0))
            for row in rows
            if int(row.get("step_index", -1)) <= target_step
        ),
        6,
    )


def _nested_count_values(
    rows: Sequence[dict[str, Any]],
    outer_key: str,
    inner_key: str,
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        outer_value = row.get(outer_key)
        inner_value = row.get(inner_key)
        if outer_value is None or inner_value is None:
            continue
        outer = str(outer_value)
        inner = str(inner_value)
        if outer not in counts:
            counts[outer] = {}
        counts[outer][inner] = counts[outer].get(inner, 0) + 1
    return {
        outer: dict(sorted(inner_counts.items()))
        for outer, inner_counts in sorted(counts.items())
    }


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


def _validate_debug_export_replay_phases(phases: Sequence[str]) -> None:
    unknown = sorted(_debug_replay_phase_filter(phases) - set(REPLAY_PHASES))
    if unknown:
        raise ValueError(
            f"debug_export_replay_phases must use {', '.join(REPLAY_PHASES)}; "
            f"got {', '.join(unknown)}"
        )


def _validate_debug_export_evidence_types(evidence_types: Sequence[str]) -> None:
    supported = {evidence.value for evidence in EvidenceType}
    unknown = sorted(_debug_evidence_type_filter(evidence_types) - supported)
    if unknown:
        raise ValueError(
            "debug_export_evidence_types must use "
            f"{', '.join(sorted(supported))}; got {', '.join(unknown)}"
        )


def _validate_max_detection_area_ratio(max_detection_area_ratio: float | None) -> None:
    if max_detection_area_ratio is None:
        return
    if not 0.0 < max_detection_area_ratio <= 1.0:
        raise ValueError("max_detection_area_ratio must be in (0, 1] or None")


def _validate_memory_geometry_gate_radius(radius_m: float | None) -> None:
    if radius_m is None:
        return
    if radius_m <= 0.0:
        raise ValueError("memory_geometry_gate_radius_m must be positive or None")


def _validate_replay_protocol(replay_protocol: str) -> None:
    if replay_protocol not in SUPPORTED_REPLAY_PROTOCOLS:
        raise ValueError(
            "replay_protocol must be one of: "
            f"{', '.join(SUPPORTED_REPLAY_PROTOCOLS)}"
        )


def _validate_geodesic_path_max_steps(max_steps: int) -> None:
    if max_steps <= 0:
        raise ValueError("geodesic_path_max_steps must be positive")


def _validate_episode_selection(
    *,
    episode_selection_strategy: str,
    structured_min_goal_viewpoints: int,
    structured_min_geodesic_distance: float,
    structured_min_path_complexity_ratio: float,
) -> None:
    if episode_selection_strategy not in SUPPORTED_EPISODE_SELECTION_STRATEGIES:
        raise ValueError(
            "episode_selection_strategy must be one of: "
            f"{', '.join(SUPPORTED_EPISODE_SELECTION_STRATEGIES)}"
        )
    if structured_min_goal_viewpoints <= 0:
        raise ValueError("structured_min_goal_viewpoints must be positive")
    if structured_min_geodesic_distance < 0.0:
        raise ValueError("structured_min_geodesic_distance must be non-negative")
    if structured_min_path_complexity_ratio < 1.0:
        raise ValueError("structured_min_path_complexity_ratio must be at least 1.0")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
