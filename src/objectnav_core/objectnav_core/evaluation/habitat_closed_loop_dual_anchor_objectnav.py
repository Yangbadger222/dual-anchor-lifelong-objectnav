from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from objectnav_core.geometry.dual_anchor import FrameTransform2D


POLICIES: tuple[str, ...] = ("memory_guided", "frontier_only", "naive_count")
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
DEFAULT_MAX_GROUPS = 1
DEFAULT_GATE_THRESHOLD = 5.991
DEFAULT_AMBIGUITY_MARGIN = 0.5
DEFAULT_FRONTIER_PROXY_WAYPOINTS = 2
SUPPORTED_FRONTIER_MODES: tuple[str, ...] = ("search_proxy", "navmesh_frontier")
DEFAULT_FRONTIER_MODE = "search_proxy"
DEFAULT_FRONTIER_PROBE_COUNT = 8
DEFAULT_NAVMESH_FRONTIER_SAMPLE_ATTEMPTS = 64
DEFAULT_NAVMESH_FRONTIER_MIN_DISTANCE_M = 1.5
DEFAULT_QUERY_REPEATS = 1
DEFAULT_MEMORY_VALID_PRIOR = 0.5
SUPPORTED_CHALLENGES: tuple[str, ...] = ("stable", "ambiguous", "stale_proxy")
DEFAULT_CHALLENGE = "stable"
SUPPORTED_DETECTORS: tuple[str, ...] = (
    "oracle_semantic_visibility",
    "grounding_dino",
)
DEFAULT_DETECTOR = "oracle_semantic_visibility"
DEFAULT_DETECTOR_WEIGHTS = "IDEA-Research/grounding-dino-tiny"
DEFAULT_DETECTOR_CONF = 0.25
DEFAULT_GROUNDING_DINO_TEXT_THRESHOLD = 0.25
DEFAULT_GROUNDING_DINO_MAX_IMAGE_SIDE = 384
DEFAULT_RGB_NOISE_PROFILE = "configs/noise/rgb_published_v1.yaml"
DEFAULT_DEPTH_NOISE_PROFILE = "configs/noise/depth_realsense_d435_v1.yaml"
SUPPORTED_NOISE_LEVELS: tuple[str, ...] = ("clean", "mild", "heavy")
DEFAULT_NOISE_LEVEL = "clean"
SUPPORTED_DETECTOR_PROMPT_MODES: tuple[str, ...] = (
    "target",
    "all_categories",
    "target_aliases",
)
DEFAULT_DETECTOR_PROMPT_MODE = "target"
DEFAULT_MIN_TARGET_PIXELS = 24
DEFAULT_MIN_DETECTOR_PIXELS = 20
DEFAULT_MAX_DETECTION_AREA_RATIO = 0.7


@dataclass(frozen=True)
class HabitatClosedLoopOptionPlan:
    group_id: str
    category: str
    policy: str
    memory_action_count: int
    memory_executed_distance_m: float
    fallback_action_count: int
    fallback_executed_distance_m: float
    fallback_from_memory_action_count: int
    fallback_from_memory_executed_distance_m: float
    matching_reason: str
    memory_verified: bool
    fallback_verified: bool
    fallback_from_memory_verified: bool | None = None
    stale_repair: bool = False
    query_repeat_index: int = 0
    memory_decision: str = "memory_first"
    memory_valid_prior: float = DEFAULT_MEMORY_VALID_PRIOR
    expected_memory_first_action_count: float | None = None
    expected_frontier_first_action_count: float | None = None
    memory_anchor_source: str = ""
    fallback_anchor_source: str = ""
    fallback_from_memory_anchor_source: str = ""
    memory_evidence: dict[str, Any] | None = None
    fallback_evidence: dict[str, Any] | None = None
    fallback_from_memory_evidence: dict[str, Any] | None = None


@dataclass(frozen=True)
class NavmeshFrontierRouteResult:
    route: Any
    selected_probe_source: str
    selected_probe_position: tuple[float, float, float] | None
    selected_verification: Any
    verification_count: int


def run_habitat_closed_loop_dual_anchor_preflight(
    output_dir: str | Path,
    *,
    dataset_dir: str | Path,
    scene_root: str | Path,
    target_categories: Sequence[str] = TARGET_CATEGORIES,
    policies: Sequence[str] = POLICIES,
    max_groups: int | None = DEFAULT_MAX_GROUPS,
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    gate_threshold: float = DEFAULT_GATE_THRESHOLD,
    ambiguity_margin: float = DEFAULT_AMBIGUITY_MARGIN,
    frontier_proxy_waypoints: int = DEFAULT_FRONTIER_PROXY_WAYPOINTS,
    frontier_mode: str = DEFAULT_FRONTIER_MODE,
    frontier_probe_count: int = DEFAULT_FRONTIER_PROBE_COUNT,
    challenge: str = DEFAULT_CHALLENGE,
    query_repeats: int = DEFAULT_QUERY_REPEATS,
    memory_valid_prior: float = DEFAULT_MEMORY_VALID_PRIOR,
    detector: str = DEFAULT_DETECTOR,
    detector_weights: str = DEFAULT_DETECTOR_WEIGHTS,
    detector_conf: float = DEFAULT_DETECTOR_CONF,
    grounding_dino_text_threshold: float = DEFAULT_GROUNDING_DINO_TEXT_THRESHOLD,
    grounding_dino_max_image_side: int | None = DEFAULT_GROUNDING_DINO_MAX_IMAGE_SIDE,
    rgb_noise_profile: str | Path = DEFAULT_RGB_NOISE_PROFILE,
    depth_noise_profile: str | Path = DEFAULT_DEPTH_NOISE_PROFILE,
    noise_level: str = DEFAULT_NOISE_LEVEL,
    min_target_pixels: int = DEFAULT_MIN_TARGET_PIXELS,
    min_detector_pixels: int = DEFAULT_MIN_DETECTOR_PIXELS,
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
    detector_prompt_mode: str = DEFAULT_DETECTOR_PROMPT_MODE,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _validate_common(
        target_categories=target_categories,
        policies=policies,
        max_groups=max_groups,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        frontier_mode=frontier_mode,
        frontier_probe_count=frontier_probe_count,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
        detector=detector,
        detector_conf=detector_conf,
        grounding_dino_text_threshold=grounding_dino_text_threshold,
        grounding_dino_max_image_side=grounding_dino_max_image_side,
        noise_level=noise_level,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
        max_detection_area_ratio=max_detection_area_ratio,
        detector_prompt_mode=detector_prompt_mode,
    )
    summary = _base_summary(
        task="habitat_closed_loop_dual_anchor_objectnav_preflight",
        full_habitat_run=False,
        dataset_dir=dataset_dir,
        scene_root=scene_root,
        target_categories=target_categories,
        policies=policies,
        max_groups=max_groups,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        frontier_mode=frontier_mode,
        frontier_probe_count=frontier_probe_count,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
        detector=detector,
        detector_weights=detector_weights,
        detector_conf=detector_conf,
        grounding_dino_text_threshold=grounding_dino_text_threshold,
        grounding_dino_max_image_side=grounding_dino_max_image_side,
        rgb_noise_profile=rgb_noise_profile,
        depth_noise_profile=depth_noise_profile,
        noise_level=noise_level,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
        max_detection_area_ratio=max_detection_area_ratio,
        detector_prompt_mode=detector_prompt_mode,
    )
    _write_json(output_path / "summary.json", summary)
    return summary


def run_habitat_closed_loop_dual_anchor_objectnav(
    output_dir: str | Path,
    *,
    dataset_dir: str | Path,
    scene_root: str | Path,
    target_categories: Sequence[str] = TARGET_CATEGORIES,
    policies: Sequence[str] = POLICIES,
    max_groups: int | None = DEFAULT_MAX_GROUPS,
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    gate_threshold: float = DEFAULT_GATE_THRESHOLD,
    ambiguity_margin: float = DEFAULT_AMBIGUITY_MARGIN,
    frontier_proxy_waypoints: int = DEFAULT_FRONTIER_PROXY_WAYPOINTS,
    frontier_mode: str = DEFAULT_FRONTIER_MODE,
    frontier_probe_count: int = DEFAULT_FRONTIER_PROBE_COUNT,
    challenge: str = DEFAULT_CHALLENGE,
    query_repeats: int = DEFAULT_QUERY_REPEATS,
    memory_valid_prior: float = DEFAULT_MEMORY_VALID_PRIOR,
    detector: str = DEFAULT_DETECTOR,
    detector_weights: str = DEFAULT_DETECTOR_WEIGHTS,
    detector_conf: float = DEFAULT_DETECTOR_CONF,
    grounding_dino_text_threshold: float = DEFAULT_GROUNDING_DINO_TEXT_THRESHOLD,
    grounding_dino_max_image_side: int | None = DEFAULT_GROUNDING_DINO_MAX_IMAGE_SIDE,
    rgb_noise_profile: str | Path = DEFAULT_RGB_NOISE_PROFILE,
    depth_noise_profile: str | Path = DEFAULT_DEPTH_NOISE_PROFILE,
    noise_level: str = DEFAULT_NOISE_LEVEL,
    min_target_pixels: int = DEFAULT_MIN_TARGET_PIXELS,
    min_detector_pixels: int = DEFAULT_MIN_DETECTOR_PIXELS,
    max_detection_area_ratio: float | None = DEFAULT_MAX_DETECTION_AREA_RATIO,
    detector_prompt_mode: str = DEFAULT_DETECTOR_PROMPT_MODE,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _validate_common(
        target_categories=target_categories,
        policies=policies,
        max_groups=max_groups,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        frontier_mode=frontier_mode,
        frontier_probe_count=frontier_probe_count,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
        detector=detector,
        detector_conf=detector_conf,
        grounding_dino_text_threshold=grounding_dino_text_threshold,
        grounding_dino_max_image_side=grounding_dino_max_image_side,
        noise_level=noise_level,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
        max_detection_area_ratio=max_detection_area_ratio,
        detector_prompt_mode=detector_prompt_mode,
    )

    from objectnav_core.evaluation.habitat_memory_lifecycle_objectnav import (
        _verify_lifecycle_view,
        _build_lifecycle_groups,
        _cached_action_route_sequence,
        _search_proxy_route_goals,
        _choose_lifecycle_anchor_candidate,
        _choose_lifecycle_fallback_candidate,
        _episode_selection_key,
        _rank_lifecycle_anchor_candidates,
    )
    from objectnav_core.evaluation.habitat_objectnav_rgb_noise_stress import (
        _accepted_yolo_detection_labels,
        _detector_for_target,
        _detector_mask,
        _select_episodes,
        _sample_replay_view_candidates,
        _target_view_metrics,
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
    from objectnav_core.simulation.depth_noise import DepthNoisePipelineD435
    from objectnav_core.simulation.depth_noise import DepthNoiseProfile
    from objectnav_core.simulation.rgb_noise import RgbNoisePipeline
    from objectnav_core.simulation.rgb_noise import RgbNoiseProfile

    dataset_path = Path(dataset_dir).expanduser().resolve()
    scene_root_path = Path(scene_root).expanduser().resolve()
    episodes = _load_valmini_episodes(dataset_path, scene_root=scene_root_path)
    selected_episodes = _select_episodes(
        episodes,
        target_categories=target_categories,
        episodes_per_category=None,
        max_episodes=None,
        episode_selection_strategy="structured_visibility",
    )
    groups = _build_lifecycle_groups(selected_episodes)
    if max_groups is not None:
        groups = _select_balanced_groups(groups, max_groups=max_groups)
    if not groups:
        raise ValueError("No lifecycle groups could be built from selected episodes")

    scene_config_path = (
        output_path / "hm3d_closed_loop_dual_anchor_basis.scene_dataset_config.json"
    )
    _write_scene_dataset_config(
        scene_config_path,
        sorted({group.discovery_episode.resolved_scene_path for group in groups}),
    )
    habitat_sim = _load_habitat_sim()
    action_route_cache: dict[Any, Any] = {}
    detector_cache: dict[tuple[str, tuple[str, ...]], Any] = {}
    rgb_noise = RgbNoisePipeline(RgbNoiseProfile.from_yaml(rgb_noise_profile), seed=313)
    depth_noise = DepthNoisePipelineD435(
        DepthNoiseProfile.from_yaml(depth_noise_profile),
        seed=313,
    )
    helper_bundle = {
        "detector_mask": _detector_mask,
        "mask_metrics": _mask_metrics,
        "target_view_metrics": _target_view_metrics,
        "classify": _classify_semantic_evidence,
        "depth_valid_ratio": _depth_valid_ratio,
    }
    rows: list[dict[str, Any]] = []
    scene_to_groups: dict[Path, list[Any]] = {}
    for group in groups:
        scene_to_groups.setdefault(group.discovery_episode.resolved_scene_path, []).append(group)

    for scene, scene_groups in _group_by_scene(
        [group.discovery_episode for group in groups]
    ).items():
        selected_scene_groups = [
            group for group in scene_to_groups.get(scene, []) if group.discovery_episode.resolved_scene_path == scene
        ]
        if not selected_scene_groups:
            continue
        sim = _make_simulator(
            habitat_sim=habitat_sim,
            scene=scene,
            scene_dataset_config=scene_config_path,
            sensor_size=(sensor_height, sensor_width),
        )
        try:
            semantic_id_to_category = _semantic_id_to_category(sim)
            agent = sim.initialize_agent(0)
            for group in selected_scene_groups:
                target_semantic_ids = _semantic_ids_for_target_category(
                    semantic_id_to_category,
                    group.category,
                )
                detector_adapter = _detector_for_target(
                    detector_cache=detector_cache,
                    detector=(
                        "grounding_dino"
                        if detector == "grounding_dino"
                        else "oracle_semantic_visibility"
                    ),
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
                memory_candidates = _rank_lifecycle_anchor_candidates(
                    _sample_replay_view_candidates(
                        sim=sim,
                        agent=agent,
                        episode=group.discovery_episode,
                        target_semantic_ids=target_semantic_ids,
                    ),
                    limit=4,
                )
                fallback_candidates = _rank_lifecycle_anchor_candidates(
                    _sample_replay_view_candidates(
                        sim=sim,
                        agent=agent,
                        episode=group.query_episode,
                        target_semantic_ids=target_semantic_ids,
                    ),
                    limit=4,
                )
                base_frame_index = len(rows) * 100
                memory_verifications = _verify_candidate_views(
                    detector=detector,
                    verify_view=_verify_lifecycle_view,
                    sim=sim,
                    candidates=memory_candidates,
                    target_semantic_ids=target_semantic_ids,
                    target_category=group.category,
                    detector_adapter=detector_adapter,
                    accepted_detection_labels=accepted_labels,
                    noise_level=noise_level,
                    rgb_noise=rgb_noise,
                    depth_noise=depth_noise,
                    frame_index_base=base_frame_index + 100,
                    min_target_pixels=min_target_pixels,
                    min_detector_pixels=min_detector_pixels,
                    max_detection_area_ratio=max_detection_area_ratio,
                    helpers=helper_bundle,
                )
                fallback_verifications = _verify_candidate_views(
                    detector=detector,
                    verify_view=_verify_lifecycle_view,
                    sim=sim,
                    candidates=fallback_candidates,
                    target_semantic_ids=target_semantic_ids,
                    target_category=group.category,
                    detector_adapter=detector_adapter,
                    accepted_detection_labels=accepted_labels,
                    noise_level=noise_level,
                    rgb_noise=rgb_noise,
                    depth_noise=depth_noise,
                    frame_index_base=base_frame_index + 200,
                    min_target_pixels=min_target_pixels,
                    min_detector_pixels=min_detector_pixels,
                    max_detection_area_ratio=max_detection_area_ratio,
                    helpers=helper_bundle,
                )
                anchor_strategy = (
                    "detector_positive"
                    if detector == "grounding_dino"
                    else "most_visible"
                )
                memory_candidate = _choose_lifecycle_anchor_candidate(
                    candidates=memory_candidates,
                    verifications=memory_verifications,
                    strategy=anchor_strategy,
                    min_target_pixels=min_target_pixels,
                )
                fallback_candidate = _choose_lifecycle_fallback_candidate(
                    candidates=fallback_candidates,
                    verifications=fallback_verifications,
                    min_target_pixels=min_target_pixels,
                )
                initial_memory_verification = memory_verifications[
                    memory_candidate.source
                ]
                if challenge == "stale_proxy":
                    initial_memory_verification = _stale_proxy_initial_memory_verification(
                        initial_memory_verification
                    )
                fallback_verification = fallback_verifications[
                    fallback_candidate.source
                ]
                memory_route = _cached_action_route_sequence(
                    cache=action_route_cache,
                    habitat_sim=habitat_sim,
                    sim=sim,
                    start_position=group.query_episode.start_position,
                    start_rotation=group.query_episode.start_rotation,
                    route_goals=(memory_candidate.position,),
                )
                repaired_memory_route = _cached_action_route_sequence(
                    cache=action_route_cache,
                    habitat_sim=habitat_sim,
                    sim=sim,
                    start_position=group.query_episode.start_position,
                    start_rotation=group.query_episode.start_rotation,
                    route_goals=(fallback_candidate.position,),
                )
                fallback_from_memory_verification = fallback_verification
                fallback_from_memory_anchor_source = fallback_candidate.source
                fallback_from_memory_evidence_source = fallback_verification
                if frontier_mode == "search_proxy":
                    fallback_route = _cached_action_route_sequence(
                        cache=action_route_cache,
                        habitat_sim=habitat_sim,
                        sim=sim,
                        start_position=group.query_episode.start_position,
                        start_rotation=group.query_episode.start_rotation,
                        route_goals=_search_proxy_route_goals(
                            sim=sim,
                            start=group.query_episode.start_position,
                            goal=fallback_candidate.position,
                            seed=313 + len(rows),
                            waypoint_count=frontier_proxy_waypoints,
                        )[0],
                    )
                    fallback_from_memory_route = _cached_action_route_sequence(
                        cache=action_route_cache,
                        habitat_sim=habitat_sim,
                        sim=sim,
                        start_position=memory_candidate.position,
                        start_rotation=memory_candidate.rotation,
                        route_goals=_search_proxy_route_goals(
                            sim=sim,
                            start=memory_candidate.position,
                            goal=fallback_candidate.position,
                            seed=313 + len(rows) + 500000,
                            waypoint_count=(
                                frontier_proxy_waypoints
                                if challenge == "stale_proxy"
                                else 0
                            ),
                        )[0],
                    )
                else:
                    fallback_result = _navmesh_frontier_result(
                        habitat_sim=habitat_sim,
                        sim=sim,
                        target_semantic_ids=target_semantic_ids,
                        target_category=group.category,
                        detector=detector,
                        detector_adapter=detector_adapter,
                        accepted_detection_labels=accepted_labels,
                        noise_level=noise_level,
                        rgb_noise=rgb_noise,
                        depth_noise=depth_noise,
                        min_target_pixels=min_target_pixels,
                        min_detector_pixels=min_detector_pixels,
                        max_detection_area_ratio=max_detection_area_ratio,
                        helpers=helper_bundle,
                        start_position=group.query_episode.start_position,
                        start_rotation=group.query_episode.start_rotation,
                        seed=313 + len(rows),
                        probe_count=frontier_probe_count,
                        frame_index_base=base_frame_index + 300,
                    )
                    fallback_route = fallback_result.route
                    fallback_verification = fallback_result.selected_verification
                    fallback_candidate = _replace_candidate_pose(
                        fallback_candidate,
                        source=fallback_result.selected_probe_source,
                        position=(
                            fallback_result.selected_probe_position
                            or fallback_candidate.position
                        ),
                        rotation=tuple(fallback_route.final_rotation),
                    )
                    fallback_from_memory_result = _navmesh_frontier_result(
                        habitat_sim=habitat_sim,
                        sim=sim,
                        target_semantic_ids=target_semantic_ids,
                        target_category=group.category,
                        detector=detector,
                        detector_adapter=detector_adapter,
                        accepted_detection_labels=accepted_labels,
                        noise_level=noise_level,
                        rgb_noise=rgb_noise,
                        depth_noise=depth_noise,
                        min_target_pixels=min_target_pixels,
                        min_detector_pixels=min_detector_pixels,
                        max_detection_area_ratio=max_detection_area_ratio,
                        helpers=helper_bundle,
                        start_position=memory_candidate.position,
                        start_rotation=memory_candidate.rotation,
                        seed=313 + len(rows) + 500000,
                        probe_count=frontier_probe_count,
                        frame_index_base=base_frame_index + 400,
                    )
                    fallback_from_memory_route = fallback_from_memory_result.route
                    fallback_from_memory_verification = (
                        fallback_from_memory_result.selected_verification
                    )
                    fallback_from_memory_anchor_source = (
                        fallback_from_memory_result.selected_probe_source
                    )
                    fallback_from_memory_evidence_source = (
                        fallback_from_memory_result.selected_verification
                    )
                    if fallback_from_memory_result.selected_probe_position is not None:
                        repaired_memory_route = _cached_action_route_sequence(
                            cache=action_route_cache,
                            habitat_sim=habitat_sim,
                            sim=sim,
                            start_position=group.query_episode.start_position,
                            start_rotation=group.query_episode.start_rotation,
                            route_goals=(
                                fallback_from_memory_result.selected_probe_position,
                            ),
                        )
                for policy in policies:
                    for repeat_index in range(query_repeats):
                        matching_reason = _matching_reason_for_repeat(
                            challenge=challenge,
                            policy=policy,
                            repeat_index=repeat_index,
                        )
                        repair_succeeded = bool(
                            fallback_from_memory_verification.shared_gate_success
                        )
                        if (
                            challenge == "stale_proxy"
                            and policy == "memory_guided"
                            and repeat_index > 0
                            and not repair_succeeded
                        ):
                            matching_reason = "no_current_observation"
                        active_memory_route = _active_memory_route_for_repeat(
                            challenge=challenge,
                            policy=policy,
                            repeat_index=repeat_index,
                            initial_memory_route=memory_route,
                            repaired_memory_route=(
                                repaired_memory_route
                                if repair_succeeded
                                else memory_route
                            ),
                            fallback_route=fallback_route,
                        )
                        expected_memory_first = _expected_memory_first_action_count(
                            memory_action_count=active_memory_route.action_count,
                            fallback_from_memory_action_count=(
                                fallback_from_memory_route.action_count
                            ),
                            memory_valid_prior=memory_valid_prior,
                        )
                        expected_frontier_first = float(fallback_route.action_count)
                        memory_decision = _memory_first_decision(
                            memory_action_count=active_memory_route.action_count,
                            fallback_from_memory_action_count=(
                                fallback_from_memory_route.action_count
                            ),
                            fallback_action_count=fallback_route.action_count,
                            memory_valid_prior=memory_valid_prior,
                        )
                        if (
                            policy == "memory_guided"
                            and matching_reason == "no_current_observation"
                            and memory_decision == "frontier_first"
                        ):
                            matching_reason = "expected_utility_frontier"
                        active_memory_verification = _active_memory_verification_for_repeat(
                            challenge=challenge,
                            policy=policy,
                            repeat_index=repeat_index,
                            initial_memory_verification=initial_memory_verification,
                            repaired_memory_verification=(
                                fallback_from_memory_verification
                                if repair_succeeded
                                else initial_memory_verification
                            ),
                        )
                        rows.append(
                            make_habitat_closed_loop_option_row(
                                HabitatClosedLoopOptionPlan(
                                    group_id=group.group_id,
                                    category=group.category,
                                    policy=policy,
                                    memory_action_count=active_memory_route.action_count,
                                    memory_executed_distance_m=(
                                        active_memory_route.executed_distance_m
                                    ),
                                    fallback_action_count=fallback_route.action_count,
                                    fallback_executed_distance_m=(
                                        fallback_route.executed_distance_m
                                    ),
                                    fallback_from_memory_action_count=(
                                        fallback_from_memory_route.action_count
                                    ),
                                    fallback_from_memory_executed_distance_m=(
                                        fallback_from_memory_route.executed_distance_m
                                    ),
                                    matching_reason=matching_reason,
                                    memory_verified=_memory_verified_by_shared_gate(
                                        policy=policy,
                                        matching_reason=matching_reason,
                                        active_memory_verification=(
                                            active_memory_verification
                                        ),
                                    ),
                                    fallback_verified=(
                                        fallback_verification.shared_gate_success
                                    ),
                                    fallback_from_memory_verified=(
                                        fallback_from_memory_verification.shared_gate_success
                                    ),
                                    stale_repair=(
                                        policy != "frontier_only"
                                        and matching_reason == "no_current_observation"
                                    ),
                                    query_repeat_index=repeat_index,
                                    memory_decision=_memory_decision_for_row(
                                        policy=policy,
                                        matching_reason=matching_reason,
                                        raw_memory_decision=memory_decision,
                                    ),
                                    memory_valid_prior=memory_valid_prior,
                                    expected_memory_first_action_count=(
                                        expected_memory_first
                                    ),
                                    expected_frontier_first_action_count=(
                                        expected_frontier_first
                                    ),
                                    memory_anchor_source=memory_candidate.source,
                                    fallback_anchor_source=fallback_candidate.source,
                                    fallback_from_memory_anchor_source=(
                                        fallback_from_memory_anchor_source
                                    ),
                                    memory_evidence=_verification_payload(
                                        active_memory_verification
                                    ),
                                    fallback_evidence=_verification_payload(
                                        fallback_verification
                                    ),
                                    fallback_from_memory_evidence=_verification_payload(
                                        fallback_from_memory_evidence_source
                                    ),
                                )
                            )
                        )
        finally:
            sim.close()

    summary = _base_summary(
        task="habitat_closed_loop_dual_anchor_objectnav",
        full_habitat_run=True,
        dataset_dir=dataset_path,
        scene_root=scene_root_path,
        target_categories=target_categories,
        policies=policies,
        max_groups=max_groups,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        frontier_mode=frontier_mode,
        frontier_probe_count=frontier_probe_count,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
        detector=detector,
        detector_weights=detector_weights,
        detector_conf=detector_conf,
        grounding_dino_text_threshold=grounding_dino_text_threshold,
        grounding_dino_max_image_side=grounding_dino_max_image_side,
        rgb_noise_profile=rgb_noise_profile,
        depth_noise_profile=depth_noise_profile,
        noise_level=noise_level,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
        max_detection_area_ratio=max_detection_area_ratio,
        detector_prompt_mode=detector_prompt_mode,
    )
    summary.update(
        {
            "selected_groups": len(groups),
            "episode_selection": {
                "candidate_episode_count": len(selected_episodes),
                "selected_group_count": len(groups),
                "selected_group_ids": [group.group_id for group in groups],
                "selected_episode_ids": [
                    _episode_selection_key(group.query_episode) for group in groups
                ],
            },
            "policy_summaries": _summarize_rows_by_policy(rows),
            "comparison": _compare_policy_summaries(_summarize_rows_by_policy(rows)),
            "rows": rows,
            "artifact_files": {
                "summary": "summary.json",
                "scene_dataset_config": scene_config_path.name,
            },
        }
    )
    _write_json(output_path / "summary.json", summary)
    return summary


def make_habitat_closed_loop_option_row(
    plan: HabitatClosedLoopOptionPlan,
    *,
    frame_transform: FrameTransform2D | None = None,
) -> dict[str, Any]:
    if plan.policy not in POLICIES:
        raise ValueError(f"unknown policy: {plan.policy}")
    transform = frame_transform or _session_restart_transform()
    if plan.policy == "frontier_only":
        selected = ["frontier"]
        action_count = plan.fallback_action_count
        distance = plan.fallback_executed_distance_m
        success = plan.fallback_verified
        memory_reused = False
    elif plan.matching_reason in {"ambiguous", "expected_utility_frontier"}:
        selected = ["frontier"]
        action_count = plan.fallback_action_count
        distance = plan.fallback_executed_distance_m
        success = plan.fallback_verified
        memory_reused = False
    elif plan.memory_verified:
        selected = ["memory"]
        action_count = plan.memory_action_count
        distance = plan.memory_executed_distance_m
        success = True
        memory_reused = True
    elif (
        plan.fallback_from_memory_verified
        if plan.fallback_from_memory_verified is not None
        else plan.fallback_verified
    ):
        selected = ["memory", "frontier"]
        action_count = plan.memory_action_count + plan.fallback_from_memory_action_count
        distance = (
            plan.memory_executed_distance_m
            + plan.fallback_from_memory_executed_distance_m
        )
        success = True
        memory_reused = False
    else:
        selected = ["memory"]
        action_count = plan.memory_action_count
        distance = plan.memory_executed_distance_m
        success = False
        memory_reused = False
    return {
        "group_id": plan.group_id,
        "category": plan.category,
        "policy": plan.policy,
        "query_repeat_index": int(plan.query_repeat_index),
        "success": bool(success),
        "selected_candidate_types": selected,
        "matching_reason": plan.matching_reason,
        "memory_reused": memory_reused,
        "stale_repair_recorded": bool(plan.stale_repair),
        "action_count": int(action_count),
        "executed_distance_m": round(float(distance), 6),
        "frame_transform": _transform_payload(transform),
        "memory_action_count": int(plan.memory_action_count),
        "fallback_action_count": int(plan.fallback_action_count),
        "fallback_from_memory_action_count": int(
            plan.fallback_from_memory_action_count
        ),
        "memory_executed_distance_m": round(float(plan.memory_executed_distance_m), 6),
        "fallback_executed_distance_m": round(
            float(plan.fallback_executed_distance_m),
            6,
        ),
        "fallback_from_memory_executed_distance_m": round(
            float(plan.fallback_from_memory_executed_distance_m),
            6,
        ),
        "memory_anchor_source": plan.memory_anchor_source,
        "fallback_anchor_source": plan.fallback_anchor_source,
        "fallback_from_memory_anchor_source": plan.fallback_from_memory_anchor_source,
        "memory_evidence": plan.memory_evidence,
        "fallback_evidence": plan.fallback_evidence,
        "fallback_from_memory_evidence": plan.fallback_from_memory_evidence,
        "memory_decision": plan.memory_decision,
        "memory_valid_prior": round(float(plan.memory_valid_prior), 6),
        "expected_memory_first_action_count": (
            None
            if plan.expected_memory_first_action_count is None
            else round(float(plan.expected_memory_first_action_count), 6)
        ),
        "expected_frontier_first_action_count": (
            None
            if plan.expected_frontier_first_action_count is None
            else round(float(plan.expected_frontier_first_action_count), 6)
        ),
    }


def _base_summary(
    *,
    task: str,
    full_habitat_run: bool,
    dataset_dir: str | Path,
    scene_root: str | Path,
    target_categories: Sequence[str],
    policies: Sequence[str],
    max_groups: int | None,
    sensor_width: int,
    sensor_height: int,
    gate_threshold: float,
    ambiguity_margin: float,
    frontier_proxy_waypoints: int,
    frontier_mode: str,
    frontier_probe_count: int,
    challenge: str,
    query_repeats: int,
    memory_valid_prior: float,
    detector: str,
    detector_weights: str,
    detector_conf: float,
    grounding_dino_text_threshold: float,
    grounding_dino_max_image_side: int | None,
    rgb_noise_profile: str | Path,
    depth_noise_profile: str | Path,
    noise_level: str,
    min_target_pixels: int,
    min_detector_pixels: int,
    max_detection_area_ratio: float | None,
    detector_prompt_mode: str,
) -> dict[str, Any]:
    return {
        "task": task,
        "full_habitat_run": bool(full_habitat_run),
        "dataset_dir": str(dataset_dir),
        "scene_root": str(scene_root),
        "target_categories": list(target_categories),
        "policies": list(policies),
        "max_groups": max_groups,
        "sensor_resolution": {"width": int(sensor_width), "height": int(sensor_height)},
        "gate_threshold": float(gate_threshold),
        "ambiguity_margin": float(ambiguity_margin),
        "frontier_proxy_waypoints": int(frontier_proxy_waypoints),
        "frontier_mode": frontier_mode,
        "frontier_probe_count": int(frontier_probe_count),
        "challenge": challenge,
        "query_repeats": int(query_repeats),
        "memory_valid_prior": round(float(memory_valid_prior), 6),
        "detector": detector,
        "detector_weights": detector_weights,
        "detector_conf": round(float(detector_conf), 6),
        "grounding_dino_text_threshold": round(
            float(grounding_dino_text_threshold),
            6,
        ),
        "grounding_dino_max_image_side": grounding_dino_max_image_side,
        "rgb_noise_profile": str(rgb_noise_profile),
        "depth_noise_profile": str(depth_noise_profile),
        "noise_level": noise_level,
        "min_target_pixels": int(min_target_pixels),
        "min_detector_pixels": int(min_detector_pixels),
        "max_detection_area_ratio": (
            None
            if max_detection_area_ratio is None
            else round(float(max_detection_area_ratio), 6)
        ),
        "detector_prompt_mode": detector_prompt_mode,
        "session_restart": {
            "memory_frame_id": "map_session_1",
            "runtime_frame_id": "map_session_2",
            "frame_transform": _transform_payload(_session_restart_transform()),
        },
        "artifact_files": {"summary": "summary.json"},
        "limits": [
            "Preflight does not import Habitat or detector weights.",
            "Current Habitat slice is option-level action smoke, not official SPL.",
            "Grounding-DINO is applied at selected memory/fallback candidate views, not every action step yet.",
            "navmesh_frontier samples deterministic navmesh probes but is not an occupancy-grid frontier.",
        ],
    }


def _validate_common(
    *,
    target_categories: Sequence[str],
    policies: Sequence[str],
    max_groups: int | None,
    sensor_width: int,
    sensor_height: int,
    gate_threshold: float,
    ambiguity_margin: float,
    frontier_proxy_waypoints: int,
    frontier_mode: str,
    frontier_probe_count: int,
    challenge: str,
    query_repeats: int,
    memory_valid_prior: float,
    detector: str,
    detector_conf: float,
    grounding_dino_text_threshold: float,
    grounding_dino_max_image_side: int | None,
    noise_level: str,
    min_target_pixels: int,
    min_detector_pixels: int,
    max_detection_area_ratio: float | None,
    detector_prompt_mode: str,
) -> None:
    unknown_policies = sorted(set(policies) - set(POLICIES))
    if unknown_policies:
        raise ValueError(f"unknown policy/policies: {', '.join(unknown_policies)}")
    unknown_categories = sorted(set(target_categories) - set(TARGET_CATEGORIES))
    if unknown_categories:
        raise ValueError(f"unknown target category/categories: {', '.join(unknown_categories)}")
    if max_groups is not None and max_groups <= 0:
        raise ValueError("max_groups must be positive when provided")
    if sensor_width <= 0 or sensor_height <= 0:
        raise ValueError("sensor dimensions must be positive")
    if gate_threshold <= 0.0:
        raise ValueError("gate_threshold must be positive")
    if ambiguity_margin < 0.0:
        raise ValueError("ambiguity_margin must be non-negative")
    if frontier_proxy_waypoints < 0:
        raise ValueError("frontier_proxy_waypoints must be non-negative")
    if frontier_mode not in SUPPORTED_FRONTIER_MODES:
        raise ValueError(
            "frontier_mode must be one of: " + ", ".join(SUPPORTED_FRONTIER_MODES)
        )
    if frontier_probe_count <= 0:
        raise ValueError("frontier_probe_count must be positive")
    if challenge not in SUPPORTED_CHALLENGES:
        raise ValueError(
            "challenge must be one of: " + ", ".join(SUPPORTED_CHALLENGES)
        )
    if query_repeats <= 0:
        raise ValueError("query_repeats must be positive")
    if not 0.0 <= memory_valid_prior <= 1.0:
        raise ValueError("memory_valid_prior must be in [0, 1]")
    if detector not in SUPPORTED_DETECTORS:
        raise ValueError(
            "detector must be one of: " + ", ".join(SUPPORTED_DETECTORS)
        )
    if not 0.0 <= detector_conf <= 1.0:
        raise ValueError("detector_conf must be in [0, 1]")
    if not 0.0 <= grounding_dino_text_threshold <= 1.0:
        raise ValueError("grounding_dino_text_threshold must be in [0, 1]")
    if (
        grounding_dino_max_image_side is not None
        and grounding_dino_max_image_side <= 0
    ):
        raise ValueError("grounding_dino_max_image_side must be positive when provided")
    if noise_level not in SUPPORTED_NOISE_LEVELS:
        raise ValueError(
            "noise_level must be one of: " + ", ".join(SUPPORTED_NOISE_LEVELS)
        )
    if min_target_pixels <= 0:
        raise ValueError("min_target_pixels must be positive")
    if min_detector_pixels <= 0:
        raise ValueError("min_detector_pixels must be positive")
    if (
        max_detection_area_ratio is not None
        and not 0.0 < max_detection_area_ratio <= 1.0
    ):
        raise ValueError("max_detection_area_ratio must be in (0, 1] when provided")
    if detector_prompt_mode not in SUPPORTED_DETECTOR_PROMPT_MODES:
        raise ValueError(
            "detector_prompt_mode must be one of: "
            + ", ".join(SUPPORTED_DETECTOR_PROMPT_MODES)
        )


def _session_restart_transform() -> FrameTransform2D:
    return FrameTransform2D(
        dx=0.2,
        dy=-0.15,
        dyaw=0.0,
        covariance=((0.05, 0.0), (0.0, 0.05)),
    )


def _select_balanced_groups(groups: Sequence[Any], *, max_groups: int) -> list[Any]:
    if max_groups <= 0:
        raise ValueError("max_groups must be positive")
    selected: list[Any] = []
    selected_ids: set[int] = set()
    seen_categories: set[str] = set()
    for group in groups:
        category = str(getattr(group, "category"))
        if category in seen_categories:
            continue
        selected.append(group)
        selected_ids.add(id(group))
        seen_categories.add(category)
        if len(selected) >= max_groups:
            return selected
    for group in groups:
        if id(group) in selected_ids:
            continue
        selected.append(group)
        if len(selected) >= max_groups:
            return selected
    return selected


def _matching_reason_for_challenge(challenge: str) -> str:
    if challenge == "stable":
        return "accepted"
    if challenge == "ambiguous":
        return "ambiguous"
    if challenge == "stale_proxy":
        return "no_current_observation"
    raise ValueError(
        "challenge must be one of: " + ", ".join(SUPPORTED_CHALLENGES)
    )


def _matching_reason_for_repeat(
    *,
    challenge: str,
    policy: str,
    repeat_index: int,
) -> str:
    if challenge == "stale_proxy" and policy == "memory_guided" and repeat_index > 0:
        return "accepted"
    return _matching_reason_for_challenge(challenge)


def _active_memory_route_for_repeat(
    *,
    challenge: str,
    policy: str,
    repeat_index: int,
    initial_memory_route: Any,
    repaired_memory_route: Any,
    fallback_route: Any,
) -> Any:
    if challenge == "stale_proxy" and policy == "memory_guided" and repeat_index > 0:
        return repaired_memory_route
    return initial_memory_route


def _active_memory_verification_for_repeat(
    *,
    challenge: str,
    policy: str,
    repeat_index: int,
    initial_memory_verification: Any,
    repaired_memory_verification: Any,
) -> Any:
    if challenge == "stale_proxy" and policy == "memory_guided" and repeat_index > 0:
        return repaired_memory_verification
    return initial_memory_verification


def _stale_proxy_initial_memory_verification(verification: Any) -> Any:
    return _StaleProxyVerification(
        oracle_target_pixels=int(getattr(verification, "oracle_target_pixels", 0) or 0),
        detector_pixels=int(getattr(verification, "detector_pixels", 0) or 0),
        overlap_pixels=int(getattr(verification, "overlap_pixels", 0) or 0),
        detector_precision=float(
            getattr(verification, "detector_precision", 0.0) or 0.0
        ),
        oracle_recall=float(getattr(verification, "oracle_recall", 0.0) or 0.0),
        detection_count=int(getattr(verification, "detection_count", 0) or 0),
        detection_filtered_count=int(
            getattr(verification, "detection_filtered_count", 0) or 0
        ),
    )


def _expected_memory_first_action_count(
    *,
    memory_action_count: int,
    fallback_from_memory_action_count: int,
    memory_valid_prior: float,
) -> float:
    if not 0.0 <= memory_valid_prior <= 1.0:
        raise ValueError("memory_valid_prior must be in [0, 1]")
    return round(
        float(memory_action_count)
        + (1.0 - float(memory_valid_prior)) * float(fallback_from_memory_action_count),
        6,
    )


def _memory_first_decision(
    *,
    memory_action_count: int,
    fallback_from_memory_action_count: int,
    fallback_action_count: int,
    memory_valid_prior: float,
) -> str:
    expected_memory = _expected_memory_first_action_count(
        memory_action_count=memory_action_count,
        fallback_from_memory_action_count=fallback_from_memory_action_count,
        memory_valid_prior=memory_valid_prior,
    )
    if expected_memory <= float(fallback_action_count):
        return "memory_first"
    return "frontier_first"


def _memory_decision_for_row(
    *,
    policy: str,
    matching_reason: str,
    raw_memory_decision: str,
) -> str:
    if policy != "memory_guided":
        return "memory_first"
    if matching_reason == "accepted":
        return "memory_first"
    return raw_memory_decision


def _memory_verified_by_shared_gate(
    *,
    policy: str,
    matching_reason: str,
    active_memory_verification: Any,
) -> bool:
    return (
        policy != "frontier_only"
        and matching_reason == "accepted"
        and bool(active_memory_verification.shared_gate_success)
    )


def _verify_candidate_views(
    *,
    detector: str,
    verify_view: Any,
    sim: Any,
    candidates: Sequence[Any],
    target_semantic_ids: Sequence[int],
    target_category: str,
    detector_adapter: Any,
    accepted_detection_labels: set[str],
    noise_level: str,
    rgb_noise: Any,
    depth_noise: Any,
    frame_index_base: int,
    min_target_pixels: int,
    min_detector_pixels: int,
    max_detection_area_ratio: float | None,
    helpers: dict[str, Any],
) -> dict[str, Any]:
    if detector == "oracle_semantic_visibility":
        return {
            candidate.source: _OracleVisible(
                target_visible=int(getattr(candidate, "target_pixels", 0) or 0)
                >= min_target_pixels,
                oracle_target_pixels=int(getattr(candidate, "target_pixels", 0) or 0),
            )
            for candidate in candidates
        }
    return {
        candidate.source: verify_view(
            sim=sim,
            position=candidate.position,
            rotation=candidate.rotation,
            target_semantic_ids=target_semantic_ids,
            target_category=target_category,
            detector=detector,
            detector_adapter=detector_adapter,
            accepted_detection_labels=accepted_detection_labels,
            noise_level=noise_level,
            rgb_noise=rgb_noise,
            depth_noise=depth_noise,
            frame_index=frame_index_base + candidate_index,
            min_target_pixels=min_target_pixels,
            min_detector_pixels=min_detector_pixels,
            max_detection_area_ratio=max_detection_area_ratio,
            helpers=helpers,
        )
        for candidate_index, candidate in enumerate(candidates)
    }


def _navmesh_frontier_probe_goals(
    *,
    sim: Any,
    start: Sequence[float],
    seed: int,
    probe_count: int,
    min_distance_m: float = DEFAULT_NAVMESH_FRONTIER_MIN_DISTANCE_M,
    sample_attempts: int = DEFAULT_NAVMESH_FRONTIER_SAMPLE_ATTEMPTS,
) -> tuple[tuple[float, float, float], ...]:
    if probe_count <= 0:
        raise ValueError("probe_count must be positive")
    if min_distance_m < 0.0:
        raise ValueError("min_distance_m must be non-negative")
    if sample_attempts <= 0:
        raise ValueError("sample_attempts must be positive")
    start_tuple = _tuple3(start)
    if start_tuple is None:
        raise ValueError("start must be a 3D position")

    pathfinder = sim.pathfinder
    if hasattr(sim, "seed"):
        sim.seed(seed)
    elif hasattr(pathfinder, "seed"):
        pathfinder.seed(seed)
    goals: list[tuple[float, float, float]] = []
    for _ in range(sample_attempts):
        if len(goals) >= probe_count:
            break
        point = _tuple3(pathfinder.get_random_navigable_point())
        if point is None:
            continue
        if not bool(pathfinder.is_navigable(point)):
            continue
        if _distance3(start_tuple, point) < min_distance_m:
            continue
        if any(_distance3(point, existing) < min_distance_m for existing in goals):
            continue
        goals.append(point)
    return tuple(goals)


def _run_navmesh_frontier_probe_route(
    *,
    start_position: Sequence[float],
    start_rotation: Sequence[float],
    probe_goals: Sequence[Sequence[float]],
    route_segment: Any,
    verify_probe: Any,
    route_error_types: tuple[type[BaseException], ...] = (),
) -> NavmeshFrontierRouteResult:
    current_position = _tuple3(start_position)
    current_rotation = _tuple4(start_rotation)
    if current_position is None or current_rotation is None:
        raise ValueError("start position and rotation must be valid")

    actions: list[str] = []
    executed_distance_m = 0.0
    reached_stop = bool(probe_goals)
    selected_verification: Any | None = None
    selected_source = "navmesh_frontier_probe:none"
    selected_position: tuple[float, float, float] | None = None
    verification_count = 0

    for probe_index, raw_goal in enumerate(probe_goals):
        goal = _tuple3(raw_goal)
        if goal is None:
            raise ValueError("probe_goals must contain valid 3D positions")
        try:
            segment = route_segment(
                start_position=current_position,
                start_rotation=current_rotation,
                goal_position=goal,
            )
        except route_error_types:
            continue
        actions.extend(str(action) for action in getattr(segment, "actions", ()))
        executed_distance_m += float(getattr(segment, "executed_distance_m", 0.0) or 0.0)
        reached_stop = reached_stop and bool(getattr(segment, "reached_stop", False))
        current_position = _tuple3(getattr(segment, "final_position", None)) or goal
        current_rotation = (
            _tuple4(getattr(segment, "final_rotation", None)) or current_rotation
        )
        selected_source = f"navmesh_frontier_probe:{probe_index}"
        verification_count += 1
        selected_verification = verify_probe(
            source=selected_source,
            position=current_position,
            rotation=current_rotation,
            probe_index=probe_index,
        )
        selected_position = current_position
        if bool(selected_verification.shared_gate_success):
            break

    if selected_verification is None:
        selected_verification = _OracleVisible(target_visible=False)
    return NavmeshFrontierRouteResult(
        route=_RouteAggregate(
            actions=tuple(actions),
            reached_stop=reached_stop,
            final_position=current_position,
            final_rotation=current_rotation,
            executed_distance_m=round(executed_distance_m, 6),
        ),
        selected_probe_source=selected_source,
        selected_probe_position=selected_position,
        selected_verification=selected_verification,
        verification_count=verification_count,
    )


def _navmesh_frontier_result(
    *,
    habitat_sim: Any,
    sim: Any,
    target_semantic_ids: Sequence[int],
    target_category: str,
    detector: str,
    detector_adapter: Any,
    accepted_detection_labels: set[str],
    noise_level: str,
    rgb_noise: Any,
    depth_noise: Any,
    min_target_pixels: int,
    min_detector_pixels: int,
    max_detection_area_ratio: float | None,
    helpers: dict[str, Any],
    start_position: Sequence[float],
    start_rotation: Sequence[float],
    seed: int,
    probe_count: int,
    frame_index_base: int,
) -> NavmeshFrontierRouteResult:
    from objectnav_core.evaluation.habitat_action_follower import (
        follow_greedy_geodesic_route,
    )
    from objectnav_core.evaluation.habitat_memory_lifecycle_objectnav import (
        DEFAULT_ACTION_MAX_STEPS_PER_GOAL,
        _verify_lifecycle_view,
    )
    try:
        from habitat_sim.errors import GreedyFollowerError
    except ModuleNotFoundError:
        GreedyFollowerError = RuntimeError

    probe_goals = _navmesh_frontier_probe_goals(
        sim=sim,
        start=start_position,
        seed=seed,
        probe_count=probe_count,
    )

    def route_segment(
        *,
        start_position: Sequence[float],
        start_rotation: Sequence[float],
        goal_position: Sequence[float],
    ) -> Any:
        return follow_greedy_geodesic_route(
            habitat_sim=habitat_sim,
            sim=sim,
            start_position=start_position,
            start_rotation=start_rotation,
            goal_position=goal_position,
            max_steps=DEFAULT_ACTION_MAX_STEPS_PER_GOAL,
            goal_radius=0.2,
        )

    def verify_probe(
        *,
        source: str,
        position: tuple[float, float, float],
        rotation: tuple[float, float, float, float],
        probe_index: int,
    ) -> Any:
        del source
        if detector == "oracle_semantic_visibility":
            return _verify_oracle_pose(
                sim=sim,
                position=position,
                rotation=rotation,
                target_semantic_ids=target_semantic_ids,
                min_target_pixels=min_target_pixels,
            )
        return _verify_lifecycle_view(
            sim=sim,
            position=position,
            rotation=rotation,
            target_semantic_ids=target_semantic_ids,
            target_category=target_category,
            detector=detector,
            detector_adapter=detector_adapter,
            accepted_detection_labels=accepted_detection_labels,
            noise_level=noise_level,
            rgb_noise=rgb_noise,
            depth_noise=depth_noise,
            frame_index=frame_index_base + probe_index,
            min_target_pixels=min_target_pixels,
            min_detector_pixels=min_detector_pixels,
            max_detection_area_ratio=max_detection_area_ratio,
            helpers=helpers,
        )

    return _run_navmesh_frontier_probe_route(
        start_position=start_position,
        start_rotation=start_rotation,
        probe_goals=probe_goals,
        route_segment=route_segment,
        verify_probe=verify_probe,
        route_error_types=(GreedyFollowerError,),
    )


def _verify_oracle_pose(
    *,
    sim: Any,
    position: tuple[float, float, float],
    rotation: tuple[float, float, float, float],
    target_semantic_ids: Sequence[int],
    min_target_pixels: int,
) -> _OracleVisible:
    agent = sim.initialize_agent(0)
    state = agent.get_state()
    state.position = np.asarray(position, dtype=float)
    state.rotation = list(rotation)
    agent.set_state(state)
    observations = sim.get_sensor_observations()
    semantic = np.asarray(observations["semantic"])
    target_pixels = int(np.isin(semantic, list(target_semantic_ids)).sum())
    return _OracleVisible(
        target_visible=target_pixels >= min_target_pixels,
        oracle_target_pixels=target_pixels,
    )


def _replace_candidate_pose(
    candidate: Any,
    *,
    source: str,
    position: tuple[float, float, float],
    rotation: tuple[float, float, float, float],
) -> Any:
    try:
        return replace(candidate, source=source, position=position, rotation=rotation)
    except TypeError:
        return candidate


def _verification_payload(verification: Any) -> dict[str, Any]:
    evidence_type = getattr(verification, "evidence_type", None)
    if evidence_type is None:
        evidence_type_value = "positive" if verification.shared_gate_success else "unknown"
    else:
        evidence_type_value = str(getattr(evidence_type, "value", evidence_type))
    return {
        "shared_gate_success": bool(verification.shared_gate_success),
        "evidence_type": evidence_type_value,
        "target_visible": bool(getattr(verification, "target_visible", False)),
        "evidence_reason": str(getattr(verification, "evidence_reason", "")),
        "oracle_target_pixels": int(
            getattr(verification, "oracle_target_pixels", 0) or 0
        ),
        "detector_pixels": int(getattr(verification, "detector_pixels", 0) or 0),
        "overlap_pixels": int(getattr(verification, "overlap_pixels", 0) or 0),
        "detector_precision": round(
            float(getattr(verification, "detector_precision", 0.0) or 0.0),
            6,
        ),
        "oracle_recall": round(
            float(getattr(verification, "oracle_recall", 0.0) or 0.0),
            6,
        ),
        "detection_count": int(getattr(verification, "detection_count", 0) or 0),
        "detection_filtered_count": int(
            getattr(verification, "detection_filtered_count", 0) or 0
        ),
    }


def summarize_habitat_closed_loop_rows(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    policy_summaries = _summarize_rows_by_policy(rows)
    return {
        "policy_summaries": policy_summaries,
        "comparison": _compare_policy_summaries(policy_summaries),
    }


def _transform_payload(transform: FrameTransform2D) -> dict[str, Any]:
    return {
        "dx": float(transform.dx),
        "dy": float(transform.dy),
        "dyaw": float(transform.dyaw),
        "covariance": [
            [float(transform.covariance[0][0]), float(transform.covariance[0][1])],
            [float(transform.covariance[1][0]), float(transform.covariance[1][1])],
        ],
    }


def _tuple3(value: Any) -> tuple[float, float, float] | None:
    if value is None:
        return None
    try:
        values = tuple(float(part) for part in value)
    except TypeError:
        return None
    return values if len(values) == 3 else None


def _tuple4(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    try:
        values = tuple(float(part) for part in value)
    except TypeError:
        return None
    return values if len(values) == 4 else None


def _distance3(
    first: Sequence[float],
    second: Sequence[float],
) -> float:
    return float(np.linalg.norm(np.asarray(first, dtype=float) - np.asarray(second, dtype=float)))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class _OracleVisible:
    target_visible: bool
    oracle_target_pixels: int = 0

    @property
    def shared_gate_success(self) -> bool:
        return bool(self.target_visible)


class _EvidenceLabel(str, Enum):
    NON_CONFIRMATION = "non_confirmation"


@dataclass(frozen=True)
class _StaleProxyVerification:
    target_visible: bool = False
    evidence_type: _EvidenceLabel = _EvidenceLabel.NON_CONFIRMATION
    evidence_reason: str = "stale_proxy_memory_absent"
    oracle_target_pixels: int = 0
    detector_pixels: int = 0
    overlap_pixels: int = 0
    detector_precision: float = 0.0
    oracle_recall: float = 0.0
    detection_count: int = 0
    detection_filtered_count: int = 0

    @property
    def shared_gate_success(self) -> bool:
        return False


@dataclass(frozen=True)
class _RouteAggregate:
    actions: tuple[str, ...]
    reached_stop: bool
    final_position: tuple[float, float, float]
    final_rotation: tuple[float, float, float, float]
    executed_distance_m: float

    @property
    def action_count(self) -> int:
        return len(self.actions)


def _summarize_rows_by_policy(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for policy in POLICIES:
        policy_rows = [row for row in rows if row["policy"] == policy]
        if not policy_rows:
            continue
        summaries[policy] = {
            "episodes": len(policy_rows),
            "success_episodes": sum(int(row["success"]) for row in policy_rows),
            "total_action_count": sum(int(row["action_count"]) for row in policy_rows),
            "total_executed_distance_m": round(
                sum(float(row["executed_distance_m"]) for row in policy_rows),
                6,
            ),
            "memory_reuse_episodes": sum(int(row["memory_reused"]) for row in policy_rows),
            "frontier_selected_count": sum(
                row["selected_candidate_types"].count("frontier")
                for row in policy_rows
            ),
        }
    return summaries


def _compare_policy_summaries(summaries: dict[str, Any]) -> dict[str, Any]:
    memory = summaries.get("memory_guided")
    frontier = summaries.get("frontier_only")
    naive = summaries.get("naive_count")
    comparison: dict[str, Any] = {}
    if memory and frontier:
        frontier_actions = int(frontier["total_action_count"])
        memory_actions = int(memory["total_action_count"])
        frontier_distance = float(frontier["total_executed_distance_m"])
        memory_distance = float(memory["total_executed_distance_m"])
        comparison.update(
            {
                "memory_guided_action_delta": frontier_actions - memory_actions,
                "memory_guided_distance_delta_m": round(
                    frontier_distance - memory_distance,
                    6,
                ),
            }
        )
    if memory and naive:
        comparison.update(
            {
                "memory_guided_vs_naive_count_action_delta": int(
                    naive["total_action_count"]
                )
                - int(memory["total_action_count"]),
                "memory_guided_vs_naive_count_distance_delta_m": round(
                    float(naive["total_executed_distance_m"])
                    - float(memory["total_executed_distance_m"]),
                    6,
                ),
            }
        )
    return comparison
