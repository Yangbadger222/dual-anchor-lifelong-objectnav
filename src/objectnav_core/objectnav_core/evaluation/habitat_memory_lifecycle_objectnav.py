from __future__ import annotations

import json
from html import escape
from csv import DictWriter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from objectnav_core.evaluation.lifelong_memory_harness import LifelongMemoryHarness
from objectnav_core.memory.usability import MemoryBelief
from objectnav_core.memory.usability import EvidenceType
from objectnav_core.simulation.depth_noise import DepthNoisePipelineD435
from objectnav_core.simulation.depth_noise import DepthNoiseProfile
from objectnav_core.simulation.rgb_noise import AgentMotion
from objectnav_core.simulation.rgb_noise import RgbNoisePipeline
from objectnav_core.simulation.rgb_noise import RgbNoiseProfile


SUPPORTED_LIFECYCLE_MODES: tuple[str, ...] = (
    "memory_guided",
    "naive_count",
    "no_memory",
)
SUPPORTED_LIFECYCLE_DETECTORS: tuple[str, ...] = (
    "grounding_dino",
    "oracle_bbox",
)
TARGET_CATEGORIES: tuple[str, ...] = (
    "bed",
    "chair",
    "plant",
    "sofa",
    "toilet",
    "tv_monitor",
)
DEFAULT_SENSOR_WIDTH = 1280
DEFAULT_SENSOR_HEIGHT = 720
DEFAULT_NAIVE_COUNT_POSITIVES_TO_TRUST = 2
DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS = 2
DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE = 2.0
DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO = 1.2
DEFAULT_MAX_DETECTION_AREA_RATIO = 0.7
DEFAULT_SEARCH_PROXY_WAYPOINTS = 3
DEFAULT_SEARCH_PROXY_SAMPLE_ATTEMPTS = 48
DEFAULT_DETECTOR_PROMPT_MODE = "target"
DATASET_VERSION = "objectnav_hm3d_v1/val_mini"


@dataclass(frozen=True)
class LifecycleVerification:
    evidence_type: EvidenceType
    target_visible: bool
    evidence_strength: float = 1.0
    evidence_reason: str = ""
    oracle_target_pixels: int = 0
    detector_pixels: int = 0
    overlap_pixels: int = 0
    detector_precision: float = 0.0
    oracle_recall: float = 0.0
    detection_count: int = 0
    detection_filtered_count: int = 0

    @property
    def shared_gate_success(self) -> bool:
        return self.evidence_type is EvidenceType.POSITIVE and self.target_visible


@dataclass(frozen=True)
class LifecyclePlanResult:
    mode: str
    success: bool
    total_path_length_m: float
    route: tuple[str, ...]
    memory_attempted: bool
    memory_reused: bool
    fallback_used: bool
    stale_check_count: int
    naive_positive_count: int
    stop_reason: str


@dataclass(frozen=True)
class LifecycleGroup:
    group_id: str
    scene_key: str
    category: str
    instance_id: str
    discovery_episode: Any
    query_episode: Any
    memory_position: tuple[float, float, float]
    memory_rotation: tuple[float, float, float, float]
    fallback_position: tuple[float, float, float]
    fallback_rotation: tuple[float, float, float, float]


def plan_lifecycle_query(
    *,
    mode: str,
    memory_path_cost_m: float | None,
    fallback_path_cost_m: float,
    memory_verification: LifecycleVerification | None,
    fallback_verifications: Sequence[LifecycleVerification],
    naive_prior_positive_count: int = 0,
    naive_positive_to_trust: int = DEFAULT_NAIVE_COUNT_POSITIVES_TO_TRUST,
) -> LifecyclePlanResult:
    """Plan one lifecycle query under shared current-view stop semantics."""

    if mode not in SUPPORTED_LIFECYCLE_MODES:
        raise ValueError(
            "mode must be one of: " + ", ".join(SUPPORTED_LIFECYCLE_MODES)
        )
    if fallback_path_cost_m < 0.0:
        raise ValueError("fallback_path_cost_m must be non-negative")
    if memory_path_cost_m is not None and memory_path_cost_m < 0.0:
        raise ValueError("memory_path_cost_m must be non-negative")
    if naive_prior_positive_count < 0:
        raise ValueError("naive_prior_positive_count must be non-negative")
    if naive_positive_to_trust <= 0:
        raise ValueError("naive_positive_to_trust must be positive")

    if mode == "naive_count":
        return _plan_naive_count_query(
            memory_path_cost_m=memory_path_cost_m,
            memory_verification=memory_verification,
            fallback_path_cost_m=fallback_path_cost_m,
            fallback_verifications=fallback_verifications,
            prior_positive_count=naive_prior_positive_count,
            positives_to_trust=naive_positive_to_trust,
        )

    if mode == "no_memory":
        success = _any_shared_gate_success(fallback_verifications)
        return LifecyclePlanResult(
            mode=mode,
            success=success,
            total_path_length_m=round(float(fallback_path_cost_m), 6),
            route=("fallback",),
            memory_attempted=False,
            memory_reused=False,
            fallback_used=True,
            stale_check_count=0,
            naive_positive_count=0,
            stop_reason="fallback_verified" if success else "fallback_failed",
        )

    memory_attempted = memory_path_cost_m is not None and memory_verification is not None
    if memory_attempted and memory_verification is not None:
        if memory_verification.shared_gate_success:
            return LifecyclePlanResult(
                mode=mode,
                success=True,
                total_path_length_m=round(float(memory_path_cost_m or 0.0), 6),
                route=("memory",),
                memory_attempted=True,
                memory_reused=True,
                fallback_used=False,
                stale_check_count=0,
                naive_positive_count=0,
                stop_reason="memory_verified",
            )
        fallback_success = _any_shared_gate_success(fallback_verifications)
        return LifecyclePlanResult(
            mode=mode,
            success=fallback_success,
            total_path_length_m=round(
                float(memory_path_cost_m or 0.0) + float(fallback_path_cost_m),
                6,
            ),
            route=("memory", "fallback"),
            memory_attempted=True,
            memory_reused=False,
            fallback_used=True,
            stale_check_count=1,
            naive_positive_count=0,
            stop_reason="fallback_verified" if fallback_success else "fallback_failed",
        )

    fallback_success = _any_shared_gate_success(fallback_verifications)
    return LifecyclePlanResult(
        mode=mode,
        success=fallback_success,
        total_path_length_m=round(float(fallback_path_cost_m), 6),
        route=("fallback",),
        memory_attempted=False,
        memory_reused=False,
        fallback_used=True,
        stale_check_count=0,
        naive_positive_count=0,
        stop_reason="fallback_verified" if fallback_success else "fallback_failed",
    )


def plan_lifecycle_sequence(
    *,
    mode: str,
    repeats: int,
    initial_memory_path_cost_m: float,
    repaired_memory_path_cost_m: float,
    fallback_path_cost_m: float,
    initial_memory_verification: LifecycleVerification,
    repaired_memory_verification: LifecycleVerification,
    fallback_verification: LifecycleVerification,
    naive_prior_positive_count: int = 0,
) -> tuple[LifecyclePlanResult, ...]:
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    results: list[LifecyclePlanResult] = []
    repaired = False
    for repeat_index in range(repeats):
        if mode == "memory_guided" and repaired:
            result = plan_lifecycle_query(
                mode=mode,
                memory_path_cost_m=repaired_memory_path_cost_m,
                fallback_path_cost_m=fallback_path_cost_m,
                memory_verification=repaired_memory_verification,
                fallback_verifications=(fallback_verification,),
            )
        else:
            result = plan_lifecycle_query(
                mode=mode,
                memory_path_cost_m=initial_memory_path_cost_m,
                fallback_path_cost_m=fallback_path_cost_m,
                memory_verification=initial_memory_verification,
                fallback_verifications=(fallback_verification,),
                naive_prior_positive_count=naive_prior_positive_count,
            )
        if (
            mode == "memory_guided"
            and repeat_index == 0
            and result.fallback_used
            and fallback_verification.shared_gate_success
        ):
            repaired = True
        results.append(result)
    return tuple(results)


def run_habitat_memory_lifecycle_preflight(
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
    modes: Sequence[str],
    target_categories: Sequence[str] = TARGET_CATEGORIES,
    episodes_per_category: int | None = None,
    seed: int = 313,
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    grounding_dino_text_threshold: float = 0.25,
    grounding_dino_max_image_side: int | None = 384,
    detector_prompt_mode: str = DEFAULT_DETECTOR_PROMPT_MODE,
    min_target_pixels: int = 24,
    min_detector_pixels: int = 20,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _validate_preflight_inputs(
        noise_levels=noise_levels,
        detector=detector,
        detector_conf=detector_conf,
        modes=modes,
        target_categories=target_categories,
        episodes_per_category=episodes_per_category,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
        detector_prompt_mode=detector_prompt_mode,
    )
    summary: dict[str, Any] = {
        "task": "habitat_memory_lifecycle_objectnav_preflight",
        "full_habitat_run": False,
        "dataset_dir": str(dataset_dir),
        "scene_root": str(scene_root),
        "rgb_noise_profile": str(rgb_noise_profile),
        "depth_noise_profile": str(depth_noise_profile),
        "noise_levels": list(noise_levels),
        "detector": detector,
        "detector_weights": detector_weights,
        "detector_conf": float(detector_conf),
        "grounding_dino_text_threshold": float(grounding_dino_text_threshold),
        "grounding_dino_max_image_side": grounding_dino_max_image_side,
        "detector_prompt_mode": detector_prompt_mode,
        "modes": list(modes),
        "target_categories": list(target_categories),
        "episodes_per_category": episodes_per_category,
        "seed": int(seed),
        "sensor_width": int(sensor_width),
        "sensor_height": int(sensor_height),
        "sensor_resolution": f"{sensor_width}x{sensor_height}",
        "min_target_pixels": int(min_target_pixels),
        "min_detector_pixels": int(min_detector_pixels),
        "naive_count_positive_threshold": DEFAULT_NAIVE_COUNT_POSITIVES_TO_TRUST,
        "artifact_files": {
            "summary": "summary.json",
            "trace": "lifecycle_trace.csv",
            "memory": "lifecycle_memory.sqlite",
            "report": "report.html",
        },
        "limits": [
            "Preflight validates configuration and writes artifact metadata only.",
            "This geodesic lifecycle protocol is not official Habitat SPL.",
            "naive_count is positive-only and receives no stale-memory or geometry helpers.",
        ],
    }
    _write_json(output_path / "summary.json", summary)
    return summary


def run_habitat_memory_lifecycle_objectnav(
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
    modes: Sequence[str],
    target_categories: Sequence[str] = TARGET_CATEGORIES,
    episodes_per_category: int | None = None,
    max_groups: int | None = None,
    seed: int = 313,
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    grounding_dino_text_threshold: float = 0.25,
    grounding_dino_max_image_side: int | None = 384,
    detector_prompt_mode: str = DEFAULT_DETECTOR_PROMPT_MODE,
    min_target_pixels: int = 24,
    min_detector_pixels: int = 20,
    structured_min_goal_viewpoints: int = DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS,
    structured_min_geodesic_distance: float = DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE,
    structured_min_path_complexity_ratio: float = DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO,
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
    search_proxy_waypoints: int = DEFAULT_SEARCH_PROXY_WAYPOINTS,
    query_repeats: int = 1,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    config_summary = run_habitat_memory_lifecycle_preflight(
        output_path,
        dataset_dir=dataset_dir,
        scene_root=scene_root,
        rgb_noise_profile=rgb_noise_profile,
        depth_noise_profile=depth_noise_profile,
        noise_levels=noise_levels,
        detector=detector,
        detector_weights=detector_weights,
        detector_conf=detector_conf,
        modes=modes,
        target_categories=target_categories,
        episodes_per_category=episodes_per_category,
        seed=seed,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        grounding_dino_text_threshold=grounding_dino_text_threshold,
        grounding_dino_max_image_side=grounding_dino_max_image_side,
        detector_prompt_mode=detector_prompt_mode,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
    )
    if max_groups is not None and max_groups <= 0:
        raise ValueError("max_groups must be positive when provided")
    if structured_min_goal_viewpoints <= 0:
        raise ValueError("structured_min_goal_viewpoints must be positive")
    if structured_min_geodesic_distance < 0.0:
        raise ValueError("structured_min_geodesic_distance must be non-negative")
    if structured_min_path_complexity_ratio < 0.0:
        raise ValueError("structured_min_path_complexity_ratio must be non-negative")
    if search_proxy_waypoints < 0:
        raise ValueError("search_proxy_waypoints must be non-negative")
    if query_repeats <= 0:
        raise ValueError("query_repeats must be positive")

    from objectnav_core.evaluation.habitat_objectnav_rgb_noise_stress import (
        _accepted_yolo_detection_labels,
        _detector_for_target,
        _detector_mask,
        _first_goal_view_candidate,
        _normalize_yolo_label,
        _select_episodes,
        _shortest_path_points,
        _target_view_metrics,
        _validate_yolo_prompt_mode,
        _yolo_prompt_categories,
    )
    from objectnav_core.evaluation.habitat_objectnav_valmini_semantic_stress import (
        _group_by_scene,
        _load_valmini_episodes,
        _semantic_id_to_category,
        _semantic_ids_for_target_category,
        _write_scene_dataset_config,
    )
    from objectnav_core.evaluation.habitat_semantic_yolo_stress import (
        _classify_semantic_evidence,
        _depth_valid_ratio,
        _load_habitat_sim,
        _make_simulator,
        _mask_metrics,
    )

    _validate_yolo_prompt_mode(detector_prompt_mode)

    dataset_path = Path(dataset_dir).expanduser().resolve()
    scene_root_path = Path(scene_root).expanduser().resolve()
    episodes = _load_valmini_episodes(dataset_path, scene_root=scene_root_path)
    selected_episodes = _select_episodes(
        episodes,
        target_categories=target_categories,
        episodes_per_category=None,
        max_episodes=None,
        episode_selection_strategy="structured_visibility",
        structured_min_goal_viewpoints=structured_min_goal_viewpoints,
        structured_min_geodesic_distance=structured_min_geodesic_distance,
        structured_min_path_complexity_ratio=structured_min_path_complexity_ratio,
    )
    if not selected_episodes:
        raise ValueError("No structured lifecycle ObjectNav episodes were selected")
    groups = _build_lifecycle_groups(selected_episodes)
    if episodes_per_category is not None:
        groups = _limit_groups_per_category(groups, episodes_per_category)
    if max_groups is not None:
        groups = groups[:max_groups]
    if not groups:
        raise ValueError("No lifecycle groups could be built from selected episodes")

    scene_config_path = (
        output_path / "hm3d_lifecycle_annotated_basis.scene_dataset_config.json"
    )
    _write_scene_dataset_config(
        scene_config_path,
        sorted({group.discovery_episode.resolved_scene_path for group in groups}),
    )
    rgb_noise = RgbNoisePipeline(RgbNoiseProfile.from_yaml(rgb_noise_profile), seed=seed)
    depth_noise = DepthNoisePipelineD435(
        DepthNoiseProfile.from_yaml(depth_noise_profile),
        seed=seed,
    )
    detector_cache: dict[tuple[str, tuple[str, ...]], Any] = {}
    habitat_sim = _load_habitat_sim()
    trace_rows: list[dict[str, Any]] = []
    scene_to_groups: dict[Path, list[LifecycleGroup]] = {}
    for group in groups:
        scene_to_groups.setdefault(group.discovery_episode.resolved_scene_path, []).append(group)

    for scene_index, (scene, scene_groups) in enumerate(scene_to_groups.items()):
        sim = _make_simulator(
            habitat_sim=habitat_sim,
            scene=scene,
            scene_dataset_config=scene_config_path,
            sensor_size=(sensor_height, sensor_width),
        )
        try:
            sim.seed(seed + scene_index * 1000)
            semantic_id_to_category = _semantic_id_to_category(sim)
            for group_index, group in enumerate(scene_groups):
                target_semantic_ids = _semantic_ids_for_target_category(
                    semantic_id_to_category,
                    group.category,
                )
                fallback_candidate = _first_goal_view_candidate(
                    sim=sim,
                    agent=sim.initialize_agent(0),
                    episode=group.query_episode,
                    target_semantic_ids=target_semantic_ids,
                )
                memory_path_cost = _path_distance(
                    _shortest_path_points(
                        sim=sim,
                        start=group.query_episode.start_position,
                        end=group.memory_position,
                    )
                )
                oracle_goal_path_cost = _path_distance(
                    _shortest_path_points(
                        sim=sim,
                        start=group.query_episode.start_position,
                        end=fallback_candidate.position,
                    )
                )
                fallback_path_cost, search_proxy_waypoint_count = _search_proxy_path_distance(
                    sim=sim,
                    start=group.query_episode.start_position,
                    goal=fallback_candidate.position,
                    seed=seed + scene_index * 1000 + group_index,
                    waypoint_count=search_proxy_waypoints,
                )
                detector_adapter = _detector_for_target(
                    detector_cache=detector_cache,
                    detector=detector,
                    detector_weights=detector_weights,
                    detector_conf=detector_conf,
                    grounding_dino_text_threshold=grounding_dino_text_threshold,
                    grounding_dino_max_image_side=grounding_dino_max_image_side,
                    target_category=group.category,
                    yolo_prompt_mode=detector_prompt_mode,
                )
                accepted_labels = _accepted_yolo_detection_labels(
                    group.category,
                    detector_prompt_mode,
                )
                helper_bundle = {
                    "detector_mask": _detector_mask,
                    "mask_metrics": _mask_metrics,
                    "target_view_metrics": _target_view_metrics,
                    "classify": _classify_semantic_evidence,
                    "depth_valid_ratio": _depth_valid_ratio,
                }
                prompt_categories = _yolo_prompt_categories(
                    group.category,
                    detector_prompt_mode,
                )
                for noise_index, noise_level in enumerate(noise_levels):
                    base_frame_index = (
                        scene_index * 100000 + group_index * 1000 + noise_index * 10
                    )
                    memory_verification = _verify_lifecycle_view(
                        sim=sim,
                        position=group.memory_position,
                        rotation=group.memory_rotation,
                        target_semantic_ids=target_semantic_ids,
                        target_category=group.category,
                        detector=detector,
                        detector_adapter=detector_adapter,
                        accepted_detection_labels=accepted_labels,
                        noise_level=noise_level,
                        rgb_noise=rgb_noise,
                        depth_noise=depth_noise,
                        frame_index=base_frame_index,
                        min_target_pixels=min_target_pixels,
                        min_detector_pixels=min_detector_pixels,
                        max_detection_area_ratio=max_detection_area_ratio,
                        helpers=helper_bundle,
                    )
                    fallback_verification = _verify_lifecycle_view(
                        sim=sim,
                        position=fallback_candidate.position,
                        rotation=fallback_candidate.rotation,
                        target_semantic_ids=target_semantic_ids,
                        target_category=group.category,
                        detector=detector,
                        detector_adapter=detector_adapter,
                        accepted_detection_labels=accepted_labels,
                        noise_level=noise_level,
                        rgb_noise=rgb_noise,
                        depth_noise=depth_noise,
                        frame_index=base_frame_index + 1,
                        min_target_pixels=min_target_pixels,
                        min_detector_pixels=min_detector_pixels,
                        max_detection_area_ratio=max_detection_area_ratio,
                        helpers=helper_bundle,
                    )
                    for mode in modes:
                        repaired = False
                        for query_repeat_index in range(query_repeats):
                            active_memory_path_cost = memory_path_cost
                            active_memory_verification = memory_verification
                            if mode == "memory_guided" and repaired:
                                active_memory_path_cost = oracle_goal_path_cost
                                active_memory_verification = fallback_verification
                            result = plan_lifecycle_query(
                                mode=mode,
                                memory_path_cost_m=active_memory_path_cost,
                                fallback_path_cost_m=fallback_path_cost,
                                memory_verification=active_memory_verification,
                                fallback_verifications=(fallback_verification,),
                                naive_prior_positive_count=(
                                    1 if mode == "naive_count" else 0
                                ),
                            )
                            if (
                                mode == "memory_guided"
                                and result.fallback_used
                                and fallback_verification.shared_gate_success
                            ):
                                repaired = True
                            trace_rows.append(
                                _lifecycle_row(
                                    group=group,
                                    mode=mode,
                                    noise_level=noise_level,
                                    detector=detector,
                                    detector_prompt_categories=prompt_categories,
                                    memory_path_cost=active_memory_path_cost,
                                    fallback_path_cost=fallback_path_cost,
                                    oracle_goal_path_cost=oracle_goal_path_cost,
                                    search_proxy_waypoint_count=search_proxy_waypoint_count,
                                    memory_verification=active_memory_verification,
                                    fallback_verification=fallback_verification,
                                    result=result,
                                    normalized_category=_normalize_yolo_label(
                                        group.category
                                    ),
                                    query_repeat_index=query_repeat_index,
                                )
                            )
        finally:
            sim.close()

    _write_csv(output_path / "lifecycle_trace.csv", trace_rows)
    summary = dict(config_summary)
    summary.update(
        {
            "task": "habitat_memory_lifecycle_objectnav",
            "full_habitat_run": True,
            "dataset_dir": str(dataset_path),
            "scene_root": str(scene_root_path),
            "scene_dataset_config": str(scene_config_path),
            "structured_min_goal_viewpoints": int(structured_min_goal_viewpoints),
            "structured_min_geodesic_distance": float(structured_min_geodesic_distance),
            "structured_min_path_complexity_ratio": float(
                structured_min_path_complexity_ratio
            ),
            "search_proxy_waypoints": int(search_proxy_waypoints),
            "query_repeats": int(query_repeats),
            "detector_prompt_mode": detector_prompt_mode,
            "max_groups": max_groups,
            "groups_completed": len(groups),
            "episode_selection": {
                "candidate_episode_count": len(selected_episodes),
                "selected_group_count": len(groups),
                "selected_episode_ids": [
                    str(group.query_episode.episode_id) for group in groups
                ],
                "selected_category_counts": _category_counts_from_groups(groups),
            },
            **summarize_lifecycle_results(
                rows=trace_rows,
                selected_episode_ids=[
                    str(group.query_episode.episode_id) for group in groups
                ],
                selected_groups=len(groups),
            ),
            "artifact_files": {
                "summary": "summary.json",
                "trace": "lifecycle_trace.csv",
                "memory": "lifecycle_memory.sqlite",
                "report": "report.html",
                "scene_dataset_config": scene_config_path.name,
            },
            "limits": [
                "This is a Habitat geodesic lifecycle protocol, not official Habitat SPL.",
                "Fallback uses a search_proxy navmesh route, while oracle_goal_path_cost_m is kept only as a shortest-path lower bound.",
                "The agent teleports to verification poses for measurement; action-level closed loop remains next.",
                "naive_count is positive-only and shares the same memory route/fallback gate.",
            ],
        }
    )
    _write_memory_artifact(output_path / "lifecycle_memory.sqlite", groups)
    _write_json(output_path / "summary.json", summary)
    _write_report(output_path / "report.html", summary)
    return summary


def summarize_lifecycle_results(
    *,
    rows: Sequence[dict[str, Any]],
    selected_episode_ids: Sequence[str],
    selected_groups: int,
) -> dict[str, Any]:
    mode_metrics = {
        mode: _mode_metrics(rows, mode)
        for mode in SUPPORTED_LIFECYCLE_MODES
        if any(str(row.get("mode")) == mode for row in rows)
    }
    memory_metrics = mode_metrics.get("memory_guided", {})
    no_memory_metrics = mode_metrics.get("no_memory", {})
    naive_metrics = mode_metrics.get("naive_count", {})
    comparison: dict[str, Any] = {}
    if memory_metrics and no_memory_metrics:
        memory_path = float(memory_metrics.get("total_path_length_m", 0.0))
        no_memory_path = float(no_memory_metrics.get("total_path_length_m", 0.0))
        comparison["memory_guided_vs_no_memory_path_delta_m"] = round(
            no_memory_path - memory_path,
            6,
        )
        comparison["memory_guided_vs_no_memory_path_reduction_ratio"] = round(
            _safe_div(no_memory_path - memory_path, no_memory_path),
            6,
        )
        comparison["memory_guided_vs_no_memory_success_delta"] = int(
            memory_metrics.get("success_episodes", 0)
        ) - int(no_memory_metrics.get("success_episodes", 0))
    if memory_metrics and naive_metrics:
        memory_path = float(memory_metrics.get("total_path_length_m", 0.0))
        naive_path = float(naive_metrics.get("total_path_length_m", 0.0))
        comparison["memory_guided_vs_naive_count_path_delta_m"] = round(
            naive_path - memory_path,
            6,
        )
        comparison["memory_guided_vs_naive_count_path_reduction_ratio"] = round(
            _safe_div(naive_path - memory_path, naive_path),
            6,
        )
        comparison["memory_guided_vs_naive_count_success_delta"] = int(
            memory_metrics.get("success_episodes", 0)
        ) - int(naive_metrics.get("success_episodes", 0))
    return {
        "selected_groups": int(selected_groups),
        "selected_episode_ids": [str(episode_id) for episode_id in selected_episode_ids],
        "trace_rows": len(rows),
        "mode_metrics": mode_metrics,
        "comparison": comparison,
    }


def _build_lifecycle_groups(episodes: Sequence[Any]) -> list[LifecycleGroup]:
    grouped: dict[tuple[str, str, str], list[Any]] = {}
    for episode in episodes:
        key = (
            str(getattr(episode, "original_scene_id")),
            str(getattr(episode, "object_category")),
            _instance_id(episode),
        )
        grouped.setdefault(key, []).append(episode)
    lifecycle_groups: list[LifecycleGroup] = []
    for (scene_key, category, instance_id), candidates in sorted(grouped.items()):
        if len(candidates) < 2:
            continue
        ordered = sorted(
            candidates,
            key=lambda episode: float(getattr(episode, "geodesic_distance", 0.0) or 0.0),
            reverse=True,
        )
        discovery = ordered[0]
        query = ordered[1]
        memory_pose = _first_goal_view_pose(discovery)
        fallback_pose = _first_goal_view_pose(query)
        if memory_pose is None or fallback_pose is None:
            continue
        memory_position, memory_rotation = memory_pose
        fallback_position, fallback_rotation = fallback_pose
        lifecycle_groups.append(
            LifecycleGroup(
                group_id=f"{scene_key}|{category}|{instance_id}",
                scene_key=scene_key,
                category=category,
                instance_id=instance_id,
                discovery_episode=discovery,
                query_episode=query,
                memory_position=memory_position,
                memory_rotation=memory_rotation,
                fallback_position=fallback_position,
                fallback_rotation=fallback_rotation,
            )
        )
    return lifecycle_groups


def _limit_groups_per_category(
    groups: Sequence[LifecycleGroup],
    episodes_per_category: int,
) -> list[LifecycleGroup]:
    counts: dict[str, int] = {}
    selected: list[LifecycleGroup] = []
    for group in groups:
        count = counts.get(group.category, 0)
        if count >= episodes_per_category:
            continue
        selected.append(group)
        counts[group.category] = count + 1
    return selected


def _verify_lifecycle_view(
    *,
    sim: Any,
    position: tuple[float, float, float],
    rotation: tuple[float, float, float, float],
    target_semantic_ids: Sequence[int],
    target_category: str,
    detector: str,
    detector_adapter: Any,
    accepted_detection_labels: set[str],
    noise_level: str,
    rgb_noise: RgbNoisePipeline,
    depth_noise: DepthNoisePipelineD435,
    frame_index: int,
    min_target_pixels: int,
    min_detector_pixels: int,
    max_detection_area_ratio: float | None,
    helpers: dict[str, Any],
) -> LifecycleVerification:
    agent = sim.initialize_agent(0)
    state = agent.get_state()
    state.position = np.asarray(position, dtype=float)
    state.rotation = list(rotation)
    agent.set_state(state)
    observations = sim.get_sensor_observations()
    rgb = _rgb3(np.asarray(observations["rgb"]))
    depth = np.asarray(observations["depth"])
    semantic = np.asarray(observations["semantic"])
    noisy_rgb = rgb_noise.apply(
        rgb,
        agent_motion=AgentMotion(translation_m=0.0, rotation_rad=0.0),
        level=noise_level,
        frame_index=frame_index,
    )
    noisy_depth = depth_noise.apply(depth, level=noise_level, frame_index=frame_index)
    oracle_mask = np.isin(semantic, list(target_semantic_ids))
    detector_mask, detections, detection_filtered_count = helpers["detector_mask"](
        detector=detector,
        detector_adapter=detector_adapter,
        noisy_rgb=noisy_rgb,
        oracle_mask=oracle_mask,
        target_category=target_category,
        accepted_detection_labels=accepted_detection_labels,
        max_detection_area_ratio=max_detection_area_ratio,
    )
    metrics = helpers["mask_metrics"](
        oracle_mask=oracle_mask,
        detector_mask=detector_mask,
    )
    evidence_type, evidence_strength, _quarantined, evidence_reason = helpers["classify"](
        action="teleport_verify",
        collided=False,
        depth_valid_ratio=helpers["depth_valid_ratio"](noisy_depth),
        metrics=metrics,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
    )
    return LifecycleVerification(
        evidence_type=evidence_type,
        target_visible=int(metrics["oracle_target_pixels"]) >= min_target_pixels,
        evidence_strength=float(evidence_strength),
        evidence_reason=str(evidence_reason),
        oracle_target_pixels=int(metrics["oracle_target_pixels"]),
        detector_pixels=int(metrics["detector_pixels"]),
        overlap_pixels=int(metrics["overlap_pixels"]),
        detector_precision=float(metrics["detector_precision"]),
        oracle_recall=float(metrics["oracle_recall"]),
        detection_count=len(detections),
        detection_filtered_count=int(detection_filtered_count),
    )


def _lifecycle_row(
    *,
    group: LifecycleGroup,
    mode: str,
    noise_level: str,
    detector: str,
    detector_prompt_categories: Sequence[str],
    memory_path_cost: float,
    fallback_path_cost: float,
    oracle_goal_path_cost: float,
    search_proxy_waypoint_count: int,
    memory_verification: LifecycleVerification,
    fallback_verification: LifecycleVerification,
    result: LifecyclePlanResult,
    normalized_category: str,
    query_repeat_index: int = 0,
) -> dict[str, Any]:
    detector_miss = (
        fallback_verification.target_visible
        and fallback_verification.evidence_type is not EvidenceType.POSITIVE
    )
    return {
        "group_id": group.group_id,
        "scene_id": group.scene_key,
        "category": group.category,
        "normalized_category": normalized_category,
        "instance_id": group.instance_id,
        "discovery_episode_id": str(group.discovery_episode.episode_id),
        "query_episode_id": str(group.query_episode.episode_id),
        "mode": mode,
        "noise_level": noise_level,
        "query_repeat_index": int(query_repeat_index),
        "detector": detector,
        "detector_prompt_categories": "|".join(detector_prompt_categories),
        "success": result.success,
        "path_length_m": result.total_path_length_m,
        "memory_path_cost_m": round(memory_path_cost, 6),
        "fallback_path_cost_m": round(fallback_path_cost, 6),
        "oracle_goal_path_cost_m": round(oracle_goal_path_cost, 6),
        "search_proxy_waypoint_count": int(search_proxy_waypoint_count),
        "route": "|".join(result.route),
        "memory_attempted": result.memory_attempted,
        "memory_reused": result.memory_reused,
        "fallback_used": result.fallback_used,
        "stale_check_count": result.stale_check_count,
        "naive_positive_count": result.naive_positive_count,
        "stop_reason": result.stop_reason,
        "memory_evidence_type": memory_verification.evidence_type.value,
        "memory_evidence_reason": memory_verification.evidence_reason,
        "memory_target_visible": memory_verification.target_visible,
        "memory_oracle_target_pixels": memory_verification.oracle_target_pixels,
        "memory_detector_pixels": memory_verification.detector_pixels,
        "memory_overlap_pixels": memory_verification.overlap_pixels,
        "memory_detector_precision": memory_verification.detector_precision,
        "memory_oracle_recall": memory_verification.oracle_recall,
        "fallback_evidence_type": fallback_verification.evidence_type.value,
        "fallback_evidence_reason": fallback_verification.evidence_reason,
        "fallback_target_visible": fallback_verification.target_visible,
        "fallback_oracle_target_pixels": fallback_verification.oracle_target_pixels,
        "fallback_detector_pixels": fallback_verification.detector_pixels,
        "fallback_overlap_pixels": fallback_verification.overlap_pixels,
        "fallback_detector_precision": fallback_verification.detector_precision,
        "fallback_oracle_recall": fallback_verification.oracle_recall,
        "detection_count": (
            memory_verification.detection_count + fallback_verification.detection_count
        ),
        "detection_filtered_count": (
            memory_verification.detection_filtered_count
            + fallback_verification.detection_filtered_count
        ),
        "detector_miss": detector_miss,
    }


def _first_goal_view_pose(
    episode: Any,
) -> tuple[tuple[float, float, float], tuple[float, float, float, float]] | None:
    for viewpoint in getattr(episode, "goal_viewpoints", ()) or ():
        agent_state = viewpoint.get("agent_state", {})
        position = _tuple3(agent_state.get("position"))
        rotation = _tuple4(agent_state.get("rotation"))
        if position is not None and rotation is not None:
            return position, rotation
    return None


def _path_distance(points: Sequence[tuple[float, float, float]]) -> float:
    if len(points) <= 1:
        return 0.0
    return round(
        sum(_distance3(first, second) for first, second in zip(points, points[1:])),
        6,
    )


def _search_proxy_path_distance(
    *,
    sim: Any,
    start: tuple[float, float, float],
    goal: tuple[float, float, float],
    seed: int,
    waypoint_count: int,
) -> tuple[float, int]:
    from objectnav_core.evaluation.habitat_objectnav_rgb_noise_stress import (
        _shortest_path_points,
    )

    if waypoint_count <= 0:
        return _path_distance(_shortest_path_points(sim=sim, start=start, end=goal)), 0
    rng = np.random.default_rng(seed)
    waypoints = _sample_search_proxy_waypoints(
        sim=sim,
        rng=rng,
        waypoint_count=waypoint_count,
        attempts=DEFAULT_SEARCH_PROXY_SAMPLE_ATTEMPTS,
    )
    current = start
    total = 0.0
    used = 0
    for waypoint in waypoints:
        try:
            total += _path_distance(
                _shortest_path_points(sim=sim, start=current, end=waypoint)
            )
        except ValueError:
            continue
        current = waypoint
        used += 1
    total += _path_distance(_shortest_path_points(sim=sim, start=current, end=goal))
    return round(total, 6), used


def _sample_search_proxy_waypoints(
    *,
    sim: Any,
    rng: np.random.Generator,
    waypoint_count: int,
    attempts: int,
) -> list[tuple[float, float, float]]:
    waypoints: list[tuple[float, float, float]] = []
    for _ in range(attempts):
        if len(waypoints) >= waypoint_count:
            break
        point = _tuple3(sim.pathfinder.get_random_navigable_point())
        if point is None:
            continue
        if any(_distance3(point, existing) < 1.0 for existing in waypoints):
            continue
        waypoints.append(point)
    return waypoints


def _distance3(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> float:
    return float(np.linalg.norm(np.asarray(first, dtype=float) - np.asarray(second, dtype=float)))


def _instance_id(episode: Any) -> str:
    info = getattr(episode, "info", {}) or {}
    closest_goal_object_id = info.get("closest_goal_object_id")
    if closest_goal_object_id is not None:
        return f"goal_object:{closest_goal_object_id}"
    return f"category:{getattr(episode, 'object_category', 'unknown')}"


def _tuple3(value: Any) -> tuple[float, float, float] | None:
    if value is None:
        return None
    values = tuple(float(part) for part in value)
    return values if len(values) == 3 else None


def _tuple4(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    values = tuple(float(part) for part in value)
    return values if len(values) == 4 else None


def _rgb3(rgb: np.ndarray) -> np.ndarray:
    array = np.asarray(rgb)
    if array.ndim != 3 or array.shape[2] < 3:
        raise ValueError("Habitat RGB observation must have at least 3 channels")
    return np.ascontiguousarray(array[..., :3].astype(np.uint8, copy=False))


def _plan_naive_count_query(
    *,
    memory_path_cost_m: float | None,
    memory_verification: LifecycleVerification | None,
    fallback_path_cost_m: float,
    fallback_verifications: Sequence[LifecycleVerification],
    prior_positive_count: int,
    positives_to_trust: int,
) -> LifecyclePlanResult:
    positive_count = int(prior_positive_count)
    success = False
    route: list[str] = []
    total_path_length = 0.0
    memory_attempted = memory_path_cost_m is not None and memory_verification is not None
    if memory_attempted and memory_verification is not None:
        route.append("memory")
        total_path_length += float(memory_path_cost_m or 0.0)
        if memory_verification.evidence_type is EvidenceType.POSITIVE:
            positive_count += 1
        if positive_count >= positives_to_trust and memory_verification.shared_gate_success:
            success = True
    if not success:
        route.append("fallback")
        total_path_length += float(fallback_path_cost_m)
        for verification in fallback_verifications:
            if verification.evidence_type is EvidenceType.POSITIVE:
                positive_count += 1
            if positive_count >= positives_to_trust and verification.shared_gate_success:
                success = True
                break
    return LifecyclePlanResult(
        mode="naive_count",
        success=success,
        total_path_length_m=round(total_path_length, 6),
        route=tuple(route),
        memory_attempted=memory_attempted,
        memory_reused=bool(success and route == ["memory"]),
        fallback_used="fallback" in route,
        stale_check_count=0,
        naive_positive_count=positive_count,
        stop_reason=(
            "naive_count_trusted"
            if success
            else "naive_count_insufficient_positive_count"
        ),
    )


def _any_shared_gate_success(
    verifications: Sequence[LifecycleVerification],
) -> bool:
    return any(verification.shared_gate_success for verification in verifications)


def _mode_metrics(rows: Sequence[dict[str, Any]], mode: str) -> dict[str, Any]:
    mode_rows = [row for row in rows if str(row.get("mode")) == mode]
    return {
        "episodes": len(mode_rows),
        "success_episodes": sum(int(bool(row.get("success"))) for row in mode_rows),
        "total_path_length_m": round(
            sum(float(row.get("path_length_m", 0.0) or 0.0) for row in mode_rows),
            6,
        ),
        "mean_path_length_m": round(
            _safe_div(
                sum(float(row.get("path_length_m", 0.0) or 0.0) for row in mode_rows),
                len(mode_rows),
            ),
            6,
        ),
        "memory_reuse_episodes": sum(
            int(bool(row.get("memory_reused"))) for row in mode_rows
        ),
        "fallback_count": sum(int(bool(row.get("fallback_used"))) for row in mode_rows),
        "stale_check_count": sum(
            int(row.get("stale_check_count", 0) or 0) for row in mode_rows
        ),
        "detector_miss_count": sum(
            int(bool(row.get("detector_miss"))) for row in mode_rows
        ),
    }


def _category_counts_from_groups(groups: Sequence[LifecycleGroup]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for group in groups:
        counts[group.category] = counts.get(group.category, 0) + 1
    return dict(sorted(counts.items()))


def _write_memory_artifact(path: Path, groups: Sequence[LifecycleGroup]) -> None:
    memory = LifelongMemoryHarness(path)
    for group in groups:
        belief = MemoryBelief(
            p_existence=0.98,
            p_location_valid=0.96,
            p_usable=0.96,
        )
        memory.save_belief(
            scene_id=group.scene_key,
            episode_dataset_version=DATASET_VERSION,
            category=group.category,
            instance_id=group.instance_id,
            belief=belief,
        )
        memory.save_object_instance_anchor(
            scene_id=group.scene_key,
            episode_dataset_version=DATASET_VERSION,
            category=group.category,
            instance_id=group.instance_id,
            anchor_x=group.memory_position[0],
            anchor_z=group.memory_position[2],
        )
    memory.connection.close()


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    path.write_text(_render_report(summary), encoding="utf-8")


def _render_report(summary: dict[str, Any]) -> str:
    mode_rows = "\n".join(
        f"<tr><th>{escape(mode)}</th>"
        f"<td>{metrics.get('success_episodes', 0)} / {metrics.get('episodes', 0)}</td>"
        f"<td>{metrics.get('total_path_length_m', 0.0)}</td>"
        f"<td>{metrics.get('memory_reuse_episodes', 0)}</td>"
        f"<td>{metrics.get('fallback_count', 0)}</td>"
        f"<td>{metrics.get('detector_miss_count', 0)}</td></tr>"
        for mode, metrics in summary.get("mode_metrics", {}).items()
    )
    comparison_rows = "\n".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape(str(value))}</td></tr>"
        for key, value in summary.get("comparison", {}).items()
    )
    limits = "\n".join(
        f"<li>{escape(str(limit))}</li>" for limit in summary.get("limits", [])
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Habitat Memory Lifecycle ObjectNav</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17202a; background: #f6f7f2; line-height: 1.6; }}
    main {{ width: min(1100px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 56px; }}
    h1 {{ margin: 0; font-size: 38px; line-height: 1.15; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 24px; letter-spacing: 0; }}
    section {{ margin-top: 22px; padding: 20px; border: 1px solid #d7ddd0; border-radius: 8px; background: #fff; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e6e9e0; vertical-align: top; }}
    .sub {{ color: #52606a; max-width: 880px; }}
  </style>
</head>
<body>
<main>
  <h1>Habitat Memory Lifecycle ObjectNav</h1>
  <p class="sub">Memory-first geodesic lifecycle evaluation with detector-backed current-view verification. This report is a research artifact, not an official Habitat SPL result.</p>
  <section>
    <h2>Run</h2>
    <table>
      <tr><th>Detector</th><td>{escape(str(summary.get("detector")))}</td></tr>
      <tr><th>Resolution</th><td>{escape(str(summary.get("sensor_resolution")))}</td></tr>
      <tr><th>Groups</th><td>{escape(str(summary.get("selected_groups", 0)))}</td></tr>
      <tr><th>Trace Rows</th><td>{escape(str(summary.get("trace_rows", 0)))}</td></tr>
    </table>
  </section>
  <section>
    <h2>Mode Metrics</h2>
    <table>
      <tr><th>Mode</th><th>Success</th><th>Total Path m</th><th>Memory Reuse</th><th>Fallback</th><th>Detector Miss</th></tr>
      {mode_rows}
    </table>
  </section>
  <section>
    <h2>Comparison</h2>
    <table>{comparison_rows}</table>
  </section>
  <section>
    <h2>Limits</h2>
    <ul>{limits}</ul>
  </section>
</main>
</body>
</html>
"""


def _safe_div(numerator: float, denominator: float) -> float:
    return 0.0 if abs(denominator) < 1e-9 else float(numerator) / float(denominator)


def _validate_preflight_inputs(
    *,
    noise_levels: Sequence[str],
    detector: str,
    detector_conf: float,
    modes: Sequence[str],
    target_categories: Sequence[str],
    episodes_per_category: int | None,
    sensor_width: int,
    sensor_height: int,
    min_target_pixels: int,
    min_detector_pixels: int,
    detector_prompt_mode: str,
) -> None:
    if not noise_levels:
        raise ValueError("At least one noise level is required")
    if detector not in SUPPORTED_LIFECYCLE_DETECTORS:
        raise ValueError(
            "detector must be one of: "
            + ", ".join(SUPPORTED_LIFECYCLE_DETECTORS)
        )
    if detector_conf < 0.0:
        raise ValueError("detector_conf must be non-negative")
    unknown_modes = sorted(set(modes) - set(SUPPORTED_LIFECYCLE_MODES))
    if unknown_modes:
        raise ValueError(f"unknown lifecycle mode(s): {', '.join(unknown_modes)}")
    if not modes:
        raise ValueError("At least one lifecycle mode is required")
    unknown_categories = sorted(set(target_categories) - set(TARGET_CATEGORIES))
    if unknown_categories:
        raise ValueError(f"unknown target category/categories: {', '.join(unknown_categories)}")
    if not target_categories:
        raise ValueError("At least one target category is required")
    if episodes_per_category is not None and episodes_per_category <= 0:
        raise ValueError("episodes_per_category must be positive when provided")
    if sensor_width <= 0 or sensor_height <= 0:
        raise ValueError("sensor dimensions must be positive")
    if min_target_pixels <= 0:
        raise ValueError("min_target_pixels must be positive")
    if min_detector_pixels <= 0:
        raise ValueError("min_detector_pixels must be positive")
    from objectnav_core.evaluation.habitat_objectnav_rgb_noise_stress import (
        _validate_yolo_prompt_mode,
    )

    _validate_yolo_prompt_mode(detector_prompt_mode)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
