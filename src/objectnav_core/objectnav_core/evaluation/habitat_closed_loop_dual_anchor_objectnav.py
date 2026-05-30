from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence as SequenceABC
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from objectnav_core.geometry.dual_anchor import FrameTransform2D
from objectnav_core.evaluation.habitat_memory_validity_model import (
    predict_memory_validity,
)


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
DEFAULT_FRONTIER_PROBE_HEADING_COUNT = 4
DEFAULT_NAVMESH_FRONTIER_SAMPLE_ATTEMPTS = 64
DEFAULT_NAVMESH_FRONTIER_MIN_DISTANCE_M = 1.5
SUPPORTED_POST_MEMORY_SEARCH_MODES: tuple[str, ...] = (
    "frontier_mode",
    "navmesh_frontier",
    "memory_local_active",
)
DEFAULT_POST_MEMORY_SEARCH_MODE = "frontier_mode"
DEFAULT_LOCAL_SEARCH_RADII_M: tuple[float, ...] = (1.0, 2.0, 4.0)
DEFAULT_LOCAL_SEARCH_PROBE_COUNT = 8
DEFAULT_LOCAL_SEARCH_HEADING_COUNT = 4
SUPPORTED_LOCAL_SEARCH_SCORE_MODES: tuple[str, ...] = (
    "distance_prior",
    "belief_gain",
)
DEFAULT_LOCAL_SEARCH_SCORE_MODE = "distance_prior"
DEFAULT_REPLAY_SEED_BASE = 313
_REPLAY_SEED_MODULUS = 2_000_000_000
_REPLAY_FRAME_INDEX_MODULUS = 1_000_000
DEFAULT_QUERY_REPEATS = 1
DEFAULT_MEMORY_VALID_PRIOR = 0.5
SUPPORTED_MEMORY_RELIABILITY_MODES: tuple[str, ...] = (
    "fixed",
    "evidence",
    "event_posterior",
)
DEFAULT_MEMORY_RELIABILITY_MODE = "fixed"
SUPPORTED_ROUTE_OBSERVATION_MODES: tuple[str, ...] = ("option_end", "per_action")
DEFAULT_ROUTE_OBSERVATION_MODE = "option_end"
SUPPORTED_DETECTOR_CONFIRMATION_MODES: tuple[str, ...] = (
    "single_frame",
    "multiview",
)
DEFAULT_DETECTOR_CONFIRMATION_MODE = "single_frame"
DEFAULT_DETECTOR_CONFIRMATION_FRAMES = 2
DEFAULT_DETECTOR_CONFIRMATION_MIN_TRANSLATION_M = 0.05
DEFAULT_DETECTOR_CONFIRMATION_MIN_ROTATION_DEG = 5.0
DEFAULT_DETECTOR_CONFIRMATION_MIN_MASK_IOU = 0.05
SUPPORTED_CHALLENGES: tuple[str, ...] = (
    "stable",
    "ambiguous",
    "stale_proxy",
    "goal_object_relocation",
)
DEFAULT_CHALLENGE = "stable"
SUPPORTED_DETECTORS: tuple[str, ...] = (
    "oracle_semantic_visibility",
    "grounding_dino",
)


def _stable_replay_digest_value(*parts: object) -> int:
    payload = "\0".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.blake2s(payload, digest_size=8).digest(), "big")


def _stable_replay_seed(
    *,
    group_id: str,
    context: str,
    base_seed: int = DEFAULT_REPLAY_SEED_BASE,
) -> int:
    return int(
        base_seed
        + (
            _stable_replay_digest_value("replay-seed", group_id, context)
            % _REPLAY_SEED_MODULUS
        )
    )


def _stable_replay_frame_index_base(*, group_id: str) -> int:
    return int(
        (
            _stable_replay_digest_value("replay-frame-index", group_id)
            % _REPLAY_FRAME_INDEX_MODULUS
        )
        * 100
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
    memory_reliability_mode: str = DEFAULT_MEMORY_RELIABILITY_MODE
    memory_reliability: dict[str, Any] | None = None
    expected_memory_first_action_count: float | None = None
    expected_frontier_first_action_count: float | None = None
    route_observation_mode: str = DEFAULT_ROUTE_OBSERVATION_MODE
    memory_route_observation_source: str = ""
    memory_route_observation_step_index: int | None = None
    memory_route_observation_count: int = 0
    fallback_route_observation_source: str = ""
    fallback_route_observation_step_index: int | None = None
    fallback_route_observation_count: int = 0
    fallback_from_memory_route_observation_source: str = ""
    fallback_from_memory_route_observation_step_index: int | None = None
    fallback_from_memory_route_observation_count: int = 0
    memory_anchor_source: str = ""
    fallback_anchor_source: str = ""
    fallback_from_memory_anchor_source: str = ""
    memory_instance_id: str | None = None
    target_instance_id: str | None = None
    relocation_pair_distance_m: float | None = None
    memory_evidence: dict[str, Any] | None = None
    fallback_evidence: dict[str, Any] | None = None
    fallback_from_memory_evidence: dict[str, Any] | None = None
    detector_confirmation_events: Sequence[dict[str, Any]] | None = None


@dataclass(frozen=True)
class NavmeshFrontierRouteResult:
    route: Any
    selected_probe_source: str
    selected_probe_position: tuple[float, float, float] | None
    selected_verification: Any
    verification_count: int


@dataclass(frozen=True)
class LocalSearchCandidate:
    source: str
    position: tuple[float, float, float]
    radius_m: float
    angle_index: int
    score: float


@dataclass(frozen=True)
class MemoryLocalSearchConfig:
    radii_m: tuple[float, ...] = DEFAULT_LOCAL_SEARCH_RADII_M
    probe_count: int = DEFAULT_LOCAL_SEARCH_PROBE_COUNT
    heading_count: int = DEFAULT_LOCAL_SEARCH_HEADING_COUNT
    score_mode: str = DEFAULT_LOCAL_SEARCH_SCORE_MODE


@dataclass(frozen=True)
class DetectorConfirmationConfig:
    frames: int = DEFAULT_DETECTOR_CONFIRMATION_FRAMES
    min_translation_m: float = DEFAULT_DETECTOR_CONFIRMATION_MIN_TRANSLATION_M
    min_rotation_deg: float = DEFAULT_DETECTOR_CONFIRMATION_MIN_ROTATION_DEG
    min_mask_iou: float = DEFAULT_DETECTOR_CONFIRMATION_MIN_MASK_IOU


@dataclass
class DetectorConfirmationState:
    pending_count: int = 0
    origin_position: tuple[float, float, float] | None = None
    origin_rotation: tuple[float, float, float, float] | None = None
    origin_mask: np.ndarray | None = None

    def reset(self) -> None:
        self.pending_count = 0
        self.origin_position = None
        self.origin_rotation = None
        self.origin_mask = None

    def observe(
        self,
        pose: tuple[
            tuple[float, float, float],
            tuple[float, float, float, float],
        ],
        mask: np.ndarray,
    ) -> tuple[int, float, float, float]:
        position, rotation = pose
        candidate_mask = np.asarray(mask, dtype=bool)
        if (
            self.pending_count == 0
            or self.origin_position is None
            or self.origin_rotation is None
            or self.origin_mask is None
        ):
            self.pending_count = 1
            self.origin_position = position
            self.origin_rotation = rotation
            self.origin_mask = candidate_mask.copy()
        else:
            self.pending_count += 1
        translation = _distance3(self.origin_position, position)
        rotation_deg = _quaternion_angle_degrees(self.origin_rotation, rotation)
        mask_iou = _mask_iou(self.origin_mask, candidate_mask)
        return self.pending_count, translation, rotation_deg, mask_iou


@dataclass(frozen=True)
class DetectorConfirmedVerification:
    source: Any
    evidence_type_value: str
    target_visible: bool
    evidence_strength: float
    evidence_reason: str
    detector_confirmation: dict[str, Any]

    @property
    def shared_gate_success(self) -> bool:
        return self.evidence_type_value == "positive" and bool(self.target_visible)

    @property
    def evidence_type(self) -> str:
        return self.evidence_type_value

    @property
    def oracle_target_pixels(self) -> int:
        return int(getattr(self.source, "oracle_target_pixels", 0) or 0)

    @property
    def detector_pixels(self) -> int:
        return int(getattr(self.source, "detector_pixels", 0) or 0)

    @property
    def overlap_pixels(self) -> int:
        return int(getattr(self.source, "overlap_pixels", 0) or 0)

    @property
    def detector_precision(self) -> float:
        return float(getattr(self.source, "detector_precision", 0.0) or 0.0)

    @property
    def oracle_recall(self) -> float:
        return float(getattr(self.source, "oracle_recall", 0.0) or 0.0)

    @property
    def detection_count(self) -> int:
        return int(getattr(self.source, "detection_count", 0) or 0)

    @property
    def detection_filtered_count(self) -> int:
        return int(getattr(self.source, "detection_filtered_count", 0) or 0)


@dataclass(frozen=True)
class MemoryReliabilityEstimate:
    mode: str
    value: float
    components: dict[str, float]
    reason: str


@dataclass(frozen=True)
class RouteObservationResult:
    route: Any
    selected_source: str
    selected_verification: Any
    selected_step_index: int | None
    observation_count: int


def run_habitat_closed_loop_dual_anchor_preflight(
    output_dir: str | Path,
    *,
    dataset_dir: str | Path,
    scene_root: str | Path,
    target_categories: Sequence[str] = TARGET_CATEGORIES,
    policies: Sequence[str] = POLICIES,
    max_groups: int | None = DEFAULT_MAX_GROUPS,
    selected_group_ids: Sequence[str] | None = None,
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    gate_threshold: float = DEFAULT_GATE_THRESHOLD,
    ambiguity_margin: float = DEFAULT_AMBIGUITY_MARGIN,
    frontier_proxy_waypoints: int = DEFAULT_FRONTIER_PROXY_WAYPOINTS,
    frontier_mode: str = DEFAULT_FRONTIER_MODE,
    frontier_probe_count: int = DEFAULT_FRONTIER_PROBE_COUNT,
    frontier_probe_heading_count: int = DEFAULT_FRONTIER_PROBE_HEADING_COUNT,
    post_memory_search_mode: str = DEFAULT_POST_MEMORY_SEARCH_MODE,
    local_search_radii_m: Sequence[float] = DEFAULT_LOCAL_SEARCH_RADII_M,
    local_search_probe_count: int = DEFAULT_LOCAL_SEARCH_PROBE_COUNT,
    local_search_heading_count: int = DEFAULT_LOCAL_SEARCH_HEADING_COUNT,
    local_search_score_mode: str = DEFAULT_LOCAL_SEARCH_SCORE_MODE,
    challenge: str = DEFAULT_CHALLENGE,
    query_repeats: int = DEFAULT_QUERY_REPEATS,
    memory_valid_prior: float = DEFAULT_MEMORY_VALID_PRIOR,
    memory_reliability_mode: str = DEFAULT_MEMORY_RELIABILITY_MODE,
    memory_validity_model_path: str | Path | None = None,
    route_observation_mode: str = DEFAULT_ROUTE_OBSERVATION_MODE,
    detector_confirmation_mode: str = DEFAULT_DETECTOR_CONFIRMATION_MODE,
    detector_confirmation_frames: int = DEFAULT_DETECTOR_CONFIRMATION_FRAMES,
    detector_confirmation_min_translation: float = (
        DEFAULT_DETECTOR_CONFIRMATION_MIN_TRANSLATION_M
    ),
    detector_confirmation_min_rotation_deg: float = (
        DEFAULT_DETECTOR_CONFIRMATION_MIN_ROTATION_DEG
    ),
    detector_confirmation_min_mask_iou: float = (
        DEFAULT_DETECTOR_CONFIRMATION_MIN_MASK_IOU
    ),
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
        selected_group_ids=selected_group_ids,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        frontier_mode=frontier_mode,
        frontier_probe_count=frontier_probe_count,
        frontier_probe_heading_count=frontier_probe_heading_count,
        post_memory_search_mode=post_memory_search_mode,
        local_search_radii_m=local_search_radii_m,
        local_search_probe_count=local_search_probe_count,
        local_search_heading_count=local_search_heading_count,
        local_search_score_mode=local_search_score_mode,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
        memory_reliability_mode=memory_reliability_mode,
        memory_validity_model_path=memory_validity_model_path,
        route_observation_mode=route_observation_mode,
        detector_confirmation_mode=detector_confirmation_mode,
        detector_confirmation_frames=detector_confirmation_frames,
        detector_confirmation_min_translation=detector_confirmation_min_translation,
        detector_confirmation_min_rotation_deg=(
            detector_confirmation_min_rotation_deg
        ),
        detector_confirmation_min_mask_iou=detector_confirmation_min_mask_iou,
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
        selected_group_ids=selected_group_ids,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        frontier_mode=frontier_mode,
        frontier_probe_count=frontier_probe_count,
        frontier_probe_heading_count=frontier_probe_heading_count,
        post_memory_search_mode=post_memory_search_mode,
        local_search_radii_m=local_search_radii_m,
        local_search_probe_count=local_search_probe_count,
        local_search_heading_count=local_search_heading_count,
        local_search_score_mode=local_search_score_mode,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
        memory_reliability_mode=memory_reliability_mode,
        memory_validity_model_path=memory_validity_model_path,
        route_observation_mode=route_observation_mode,
        detector_confirmation_mode=detector_confirmation_mode,
        detector_confirmation_frames=detector_confirmation_frames,
        detector_confirmation_min_translation=detector_confirmation_min_translation,
        detector_confirmation_min_rotation_deg=(
            detector_confirmation_min_rotation_deg
        ),
        detector_confirmation_min_mask_iou=detector_confirmation_min_mask_iou,
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
    selected_group_ids: Sequence[str] | None = None,
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    gate_threshold: float = DEFAULT_GATE_THRESHOLD,
    ambiguity_margin: float = DEFAULT_AMBIGUITY_MARGIN,
    frontier_proxy_waypoints: int = DEFAULT_FRONTIER_PROXY_WAYPOINTS,
    frontier_mode: str = DEFAULT_FRONTIER_MODE,
    frontier_probe_count: int = DEFAULT_FRONTIER_PROBE_COUNT,
    frontier_probe_heading_count: int = DEFAULT_FRONTIER_PROBE_HEADING_COUNT,
    post_memory_search_mode: str = DEFAULT_POST_MEMORY_SEARCH_MODE,
    local_search_radii_m: Sequence[float] = DEFAULT_LOCAL_SEARCH_RADII_M,
    local_search_probe_count: int = DEFAULT_LOCAL_SEARCH_PROBE_COUNT,
    local_search_heading_count: int = DEFAULT_LOCAL_SEARCH_HEADING_COUNT,
    local_search_score_mode: str = DEFAULT_LOCAL_SEARCH_SCORE_MODE,
    challenge: str = DEFAULT_CHALLENGE,
    query_repeats: int = DEFAULT_QUERY_REPEATS,
    memory_valid_prior: float = DEFAULT_MEMORY_VALID_PRIOR,
    memory_reliability_mode: str = DEFAULT_MEMORY_RELIABILITY_MODE,
    memory_validity_model_path: str | Path | None = None,
    route_observation_mode: str = DEFAULT_ROUTE_OBSERVATION_MODE,
    detector_confirmation_mode: str = DEFAULT_DETECTOR_CONFIRMATION_MODE,
    detector_confirmation_frames: int = DEFAULT_DETECTOR_CONFIRMATION_FRAMES,
    detector_confirmation_min_translation: float = (
        DEFAULT_DETECTOR_CONFIRMATION_MIN_TRANSLATION_M
    ),
    detector_confirmation_min_rotation_deg: float = (
        DEFAULT_DETECTOR_CONFIRMATION_MIN_ROTATION_DEG
    ),
    detector_confirmation_min_mask_iou: float = (
        DEFAULT_DETECTOR_CONFIRMATION_MIN_MASK_IOU
    ),
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
        selected_group_ids=selected_group_ids,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        frontier_mode=frontier_mode,
        frontier_probe_count=frontier_probe_count,
        frontier_probe_heading_count=frontier_probe_heading_count,
        post_memory_search_mode=post_memory_search_mode,
        local_search_radii_m=local_search_radii_m,
        local_search_probe_count=local_search_probe_count,
        local_search_heading_count=local_search_heading_count,
        local_search_score_mode=local_search_score_mode,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
        memory_reliability_mode=memory_reliability_mode,
        memory_validity_model_path=memory_validity_model_path,
        route_observation_mode=route_observation_mode,
        detector_confirmation_mode=detector_confirmation_mode,
        detector_confirmation_frames=detector_confirmation_frames,
        detector_confirmation_min_translation=detector_confirmation_min_translation,
        detector_confirmation_min_rotation_deg=(
            detector_confirmation_min_rotation_deg
        ),
        detector_confirmation_min_mask_iou=detector_confirmation_min_mask_iou,
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
    memory_validity_model = _load_memory_validity_model(memory_validity_model_path)

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
    if challenge == "goal_object_relocation":
        groups = _build_goal_object_relocation_groups(groups)
    groups = _select_closed_loop_groups(
        groups,
        max_groups=max_groups,
        selected_group_ids=selected_group_ids,
    )
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
    detector_confirmation = DetectorConfirmationConfig(
        frames=detector_confirmation_frames,
        min_translation_m=detector_confirmation_min_translation,
        min_rotation_deg=detector_confirmation_min_rotation_deg,
        min_mask_iou=detector_confirmation_min_mask_iou,
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
                memory_target_semantic_ids, target_semantic_ids = (
                    _semantic_ids_for_closed_loop_group(
                        semantic_id_to_category=semantic_id_to_category,
                        group=group,
                        challenge=challenge,
                    )
                )
                if not memory_target_semantic_ids:
                    memory_target_semantic_ids = _semantic_ids_for_target_category(
                        semantic_id_to_category,
                        group.category,
                    )
                if not target_semantic_ids:
                    target_semantic_ids = _semantic_ids_for_target_category(
                        semantic_id_to_category,
                        group.category,
                    )
                target_semantic_ids = tuple(target_semantic_ids)
                memory_target_semantic_ids = tuple(memory_target_semantic_ids)
                memory_verification_target_semantic_ids = (
                    _candidate_verification_semantic_ids(
                        challenge=challenge,
                        candidate_role="memory_anchor",
                        memory_target_semantic_ids=memory_target_semantic_ids,
                        target_semantic_ids=target_semantic_ids,
                    )
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
                        target_semantic_ids=memory_target_semantic_ids,
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
                base_frame_index = _stable_replay_frame_index_base(
                    group_id=group.group_id
                )
                fallback_seed = _stable_replay_seed(
                    group_id=group.group_id,
                    context="fallback",
                )
                fallback_from_memory_seed = _stable_replay_seed(
                    group_id=group.group_id,
                    context="fallback_from_memory",
                )
                detector_confirmation_events: list[dict[str, Any]] = []
                memory_verifications = _verify_candidate_views(
                    detector=detector,
                    verify_view=_verify_lifecycle_view,
                    sim=sim,
                    candidates=memory_candidates,
                    target_semantic_ids=memory_verification_target_semantic_ids,
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
                    detector_confirmation_mode=detector_confirmation_mode,
                    detector_confirmation=detector_confirmation,
                    helpers=helper_bundle,
                    detector_confirmation_events=(
                        None
                        if challenge == "goal_object_relocation"
                        else detector_confirmation_events
                    ),
                    detector_confirmation_context="memory",
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
                    detector_confirmation_mode=detector_confirmation_mode,
                    detector_confirmation=detector_confirmation,
                    helpers=helper_bundle,
                    detector_confirmation_events=detector_confirmation_events,
                    detector_confirmation_context="fallback",
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
                if challenge == "goal_object_relocation":
                    initial_memory_verification = _route_observation_verifier(
                        detector=detector,
                        sim=sim,
                        target_semantic_ids=target_semantic_ids,
                        target_category=group.category,
                        detector_adapter=detector_adapter,
                        accepted_detection_labels=accepted_labels,
                        noise_level=noise_level,
                        rgb_noise=rgb_noise,
                        depth_noise=depth_noise,
                        min_target_pixels=min_target_pixels,
                        min_detector_pixels=min_detector_pixels,
                        max_detection_area_ratio=max_detection_area_ratio,
                        detector_confirmation_mode=detector_confirmation_mode,
                        detector_confirmation=detector_confirmation,
                        helpers=helper_bundle,
                        frame_index_base=base_frame_index + 150,
                        detector_confirmation_events=detector_confirmation_events,
                        detector_confirmation_context="memory",
                    )(
                        source=memory_candidate.source,
                        position=memory_candidate.position,
                        rotation=memory_candidate.rotation,
                        step_index=None,
                        action="memory_candidate",
                    )
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
                memory_route_observation = RouteObservationResult(
                    route=memory_route,
                    selected_source=f"{memory_candidate.source}:route:option_end",
                    selected_verification=initial_memory_verification,
                    selected_step_index=None,
                    observation_count=1,
                )
                fallback_route_observation: RouteObservationResult | None = None
                fallback_from_memory_observation: RouteObservationResult | None = None
                if route_observation_mode == "per_action":
                    memory_observation = _observe_initial_memory_route(
                        route=memory_route,
                        route_source=f"{memory_candidate.source}:route",
                        challenge=challenge,
                        mode=route_observation_mode,
                        initial_memory_verification=initial_memory_verification,
                        verify_observation=_route_observation_verifier(
                            detector=detector,
                            sim=sim,
                            target_semantic_ids=target_semantic_ids,
                            target_category=group.category,
                            detector_adapter=detector_adapter,
                            accepted_detection_labels=accepted_labels,
                            noise_level=noise_level,
                            rgb_noise=rgb_noise,
                            depth_noise=depth_noise,
                            min_target_pixels=min_target_pixels,
                            min_detector_pixels=min_detector_pixels,
                            max_detection_area_ratio=max_detection_area_ratio,
                            detector_confirmation_mode=detector_confirmation_mode,
                            detector_confirmation=detector_confirmation,
                            helpers=helper_bundle,
                            frame_index_base=base_frame_index + 500,
                            detector_confirmation_events=(
                                detector_confirmation_events
                            ),
                            detector_confirmation_context="memory",
                        ),
                    )
                    memory_route = memory_observation.route
                    memory_route_observation = memory_observation
                    initial_memory_verification = (
                        memory_observation.selected_verification
                    )
                fallback_from_memory_verification = fallback_verification
                fallback_from_memory_anchor_source = fallback_candidate.source
                fallback_from_memory_evidence_source = fallback_verification
                post_memory_effective_mode = _effective_post_memory_search_mode(
                    frontier_mode=frontier_mode,
                    post_memory_search_mode=post_memory_search_mode,
                )
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
                            seed=fallback_seed,
                            waypoint_count=frontier_proxy_waypoints,
                        )[0],
                    )
                    if route_observation_mode == "per_action":
                        fallback_observation = _observe_route_until_positive(
                            route=fallback_route,
                            route_source=f"{fallback_candidate.source}:route",
                            mode=route_observation_mode,
                            verify_observation=_route_observation_verifier(
                                detector=detector,
                                sim=sim,
                                target_semantic_ids=target_semantic_ids,
                                target_category=group.category,
                                detector_adapter=detector_adapter,
                                accepted_detection_labels=accepted_labels,
                                noise_level=noise_level,
                                rgb_noise=rgb_noise,
                                depth_noise=depth_noise,
                                min_target_pixels=min_target_pixels,
                                min_detector_pixels=min_detector_pixels,
                                max_detection_area_ratio=max_detection_area_ratio,
                                detector_confirmation_mode=detector_confirmation_mode,
                                detector_confirmation=detector_confirmation,
                                helpers=helper_bundle,
                                frame_index_base=base_frame_index + 600,
                                detector_confirmation_events=(
                                    detector_confirmation_events
                                ),
                                detector_confirmation_context="fallback",
                            ),
                        )
                        fallback_route = fallback_observation.route
                        fallback_route_observation = fallback_observation
                        fallback_verification = fallback_observation.selected_verification
                        fallback_candidate = _replace_candidate_pose(
                            fallback_candidate,
                            source=fallback_observation.selected_source,
                            position=tuple(fallback_route.final_position),
                            rotation=tuple(fallback_route.final_rotation),
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
                        detector_confirmation_mode=detector_confirmation_mode,
                        detector_confirmation=detector_confirmation,
                        helpers=helper_bundle,
                        detector_confirmation_events=detector_confirmation_events,
                        detector_confirmation_context="fallback",
                        start_position=group.query_episode.start_position,
                        start_rotation=group.query_episode.start_rotation,
                        seed=fallback_seed,
                        probe_count=frontier_probe_count,
                        probe_heading_count=frontier_probe_heading_count,
                        route_observation_mode=route_observation_mode,
                        frame_index_base=base_frame_index + 300,
                    )
                    fallback_route = fallback_result.route
                    fallback_verification = fallback_result.selected_verification
                    fallback_route_observation = _route_observation_from_navmesh_result(
                        fallback_result
                    )
                    fallback_candidate = _replace_candidate_pose(
                        fallback_candidate,
                        source=fallback_result.selected_probe_source,
                        position=(
                            fallback_result.selected_probe_position
                            or fallback_candidate.position
                        ),
                        rotation=tuple(fallback_route.final_rotation),
                    )
                if post_memory_effective_mode == "search_proxy":
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
                            seed=fallback_from_memory_seed,
                            waypoint_count=(
                                frontier_proxy_waypoints
                                if challenge == "stale_proxy"
                                else 0
                            ),
                        )[0],
                    )
                    if route_observation_mode == "per_action":
                        fallback_from_memory_observation = (
                            _observe_route_until_positive(
                                route=fallback_from_memory_route,
                                route_source=(
                                    f"{fallback_candidate.source}:from_memory_route"
                                ),
                                mode=route_observation_mode,
                                verify_observation=_route_observation_verifier(
                                    detector=detector,
                                    sim=sim,
                                    target_semantic_ids=target_semantic_ids,
                                    target_category=group.category,
                                    detector_adapter=detector_adapter,
                                    accepted_detection_labels=accepted_labels,
                                    noise_level=noise_level,
                                    rgb_noise=rgb_noise,
                                    depth_noise=depth_noise,
                                    min_target_pixels=min_target_pixels,
                                    min_detector_pixels=min_detector_pixels,
                                    max_detection_area_ratio=max_detection_area_ratio,
                                    detector_confirmation_mode=detector_confirmation_mode,
                                    detector_confirmation=detector_confirmation,
                                    helpers=helper_bundle,
                                    frame_index_base=base_frame_index + 700,
                                    detector_confirmation_events=(
                                        detector_confirmation_events
                                    ),
                                    detector_confirmation_context=(
                                        "fallback_from_memory"
                                    ),
                                ),
                            )
                        )
                        fallback_from_memory_route = (
                            fallback_from_memory_observation.route
                        )
                        fallback_from_memory_verification = (
                            fallback_from_memory_observation.selected_verification
                        )
                        fallback_from_memory_anchor_source = (
                            fallback_from_memory_observation.selected_source
                        )
                        fallback_from_memory_evidence_source = (
                            fallback_from_memory_observation.selected_verification
                        )
                elif post_memory_effective_mode == "navmesh_frontier":
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
                        detector_confirmation_mode=detector_confirmation_mode,
                        detector_confirmation=detector_confirmation,
                        helpers=helper_bundle,
                        detector_confirmation_events=detector_confirmation_events,
                        detector_confirmation_context="fallback_from_memory",
                        start_position=memory_candidate.position,
                        start_rotation=memory_candidate.rotation,
                        seed=fallback_from_memory_seed,
                        probe_count=frontier_probe_count,
                        probe_heading_count=frontier_probe_heading_count,
                        route_observation_mode=route_observation_mode,
                        frame_index_base=base_frame_index + 400,
                    )
                    fallback_from_memory_route = fallback_from_memory_result.route
                    fallback_from_memory_verification = (
                        fallback_from_memory_result.selected_verification
                    )
                    fallback_from_memory_observation = (
                        _route_observation_from_navmesh_result(
                            fallback_from_memory_result
                        )
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
                else:
                    fallback_from_memory_result = _habitat_memory_local_active_result(
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
                        detector_confirmation_mode=detector_confirmation_mode,
                        detector_confirmation=detector_confirmation,
                        helpers=helper_bundle,
                        detector_confirmation_events=detector_confirmation_events,
                        detector_confirmation_context="fallback_from_memory",
                        start_position=memory_candidate.position,
                        start_rotation=memory_candidate.rotation,
                        memory_anchor=memory_candidate.position,
                        seed=fallback_from_memory_seed,
                        radii_m=local_search_radii_m,
                        probe_count=local_search_probe_count,
                        angle_count=local_search_probe_count,
                        score_mode=local_search_score_mode,
                        probe_heading_count=local_search_heading_count,
                        route_observation_mode=route_observation_mode,
                        frame_index_base=base_frame_index + 400,
                    )
                    fallback_from_memory_route = fallback_from_memory_result.route
                    fallback_from_memory_verification = (
                        fallback_from_memory_result.selected_verification
                    )
                    fallback_from_memory_observation = (
                        _route_observation_from_navmesh_result(
                            fallback_from_memory_result
                        )
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
                        reliability_estimate = _estimate_memory_valid_prior(
                            base_prior=memory_valid_prior,
                            mode=memory_reliability_mode,
                            matching_reason=matching_reason,
                            verification=active_memory_verification,
                            category=group.category,
                            transform=_session_restart_transform(),
                            repeat_index=repeat_index,
                            detector_confirmation_events=(
                                detector_confirmation_events
                            ),
                            detector_confirmation_context=(
                                _memory_reliability_detector_confirmation_context(
                                    challenge=challenge,
                                    policy=policy,
                                    repeat_index=repeat_index,
                                    repair_succeeded=repair_succeeded,
                                )
                            ),
                        )
                        active_memory_evidence_payload = _verification_payload(
                            active_memory_verification
                        )
                        if memory_validity_model is not None:
                            reliability_estimate = (
                                _apply_learned_memory_validity_model(
                                    model=memory_validity_model,
                                    base_estimate=reliability_estimate,
                                    memory_action_count=(
                                        active_memory_route.action_count
                                    ),
                                    fallback_action_count=(
                                        fallback_route.action_count
                                    ),
                                    fallback_from_memory_action_count=(
                                        fallback_from_memory_route.action_count
                                    ),
                                    memory_valid_prior=memory_valid_prior,
                                    relocation_pair_distance_m=getattr(
                                        group,
                                        "relocation_pair_distance_m",
                                        None,
                                    ),
                                    memory_evidence=active_memory_evidence_payload,
                                )
                            )
                        fallback_available = (
                            int(fallback_route.action_count) > 0
                            or bool(fallback_verification.shared_gate_success)
                        )
                        fallback_from_memory_available = (
                            int(fallback_from_memory_route.action_count) > 0
                            or bool(
                                fallback_from_memory_verification.shared_gate_success
                            )
                        )
                        expected_memory_first = (
                            _expected_memory_first_action_count(
                                memory_action_count=active_memory_route.action_count,
                                fallback_from_memory_action_count=(
                                    fallback_from_memory_route.action_count
                                ),
                                memory_valid_prior=reliability_estimate.value,
                            )
                            if (
                                fallback_from_memory_available
                                or reliability_estimate.value >= 1.0
                            )
                            else None
                        )
                        expected_frontier_first = float(fallback_route.action_count)
                        memory_decision = _memory_first_decision(
                            memory_action_count=active_memory_route.action_count,
                            fallback_from_memory_action_count=(
                                fallback_from_memory_route.action_count
                            ),
                            fallback_action_count=fallback_route.action_count,
                            memory_valid_prior=reliability_estimate.value,
                            fallback_available=fallback_available,
                            fallback_from_memory_available=(
                                fallback_from_memory_available
                            ),
                        )
                        if (
                            policy == "memory_guided"
                            and matching_reason == "no_current_observation"
                            and memory_decision == "frontier_first"
                        ):
                            matching_reason = "expected_utility_frontier"
                        rows.append(
                            make_habitat_closed_loop_option_row(
                                HabitatClosedLoopOptionPlan(
                                    group_id=group.group_id,
                                    category=group.category,
                                    policy=policy,
                                    memory_instance_id=(
                                        getattr(group, "memory_instance_id", None)
                                        or getattr(group, "instance_id", None)
                                    ),
                                    target_instance_id=(
                                        getattr(group, "target_instance_id", None)
                                        or getattr(group, "instance_id", None)
                                    ),
                                    relocation_pair_distance_m=getattr(
                                        group,
                                        "relocation_pair_distance_m",
                                        None,
                                    ),
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
                                    memory_valid_prior=reliability_estimate.value,
                                    memory_reliability_mode=reliability_estimate.mode,
                                    memory_reliability=_memory_reliability_payload(
                                        reliability_estimate
                                    ),
                                    route_observation_mode=route_observation_mode,
                                    memory_route_observation_source=(
                                        memory_route_observation.selected_source
                                    ),
                                    memory_route_observation_step_index=(
                                        memory_route_observation.selected_step_index
                                    ),
                                    memory_route_observation_count=(
                                        memory_route_observation.observation_count
                                    ),
                                    fallback_route_observation_source=(
                                        fallback_route_observation.selected_source
                                        if fallback_route_observation is not None
                                        else f"{fallback_candidate.source}:route:option_end"
                                    ),
                                    fallback_route_observation_step_index=(
                                        fallback_route_observation.selected_step_index
                                        if fallback_route_observation is not None
                                        else None
                                    ),
                                    fallback_route_observation_count=(
                                        fallback_route_observation.observation_count
                                        if fallback_route_observation is not None
                                        else 1
                                    ),
                                    fallback_from_memory_route_observation_source=(
                                        fallback_from_memory_observation.selected_source
                                        if fallback_from_memory_observation is not None
                                        else (
                                            f"{fallback_from_memory_anchor_source}"
                                            ":route:option_end"
                                        )
                                    ),
                                    fallback_from_memory_route_observation_step_index=(
                                        fallback_from_memory_observation.selected_step_index
                                        if fallback_from_memory_observation is not None
                                        else None
                                    ),
                                    fallback_from_memory_route_observation_count=(
                                        fallback_from_memory_observation.observation_count
                                        if fallback_from_memory_observation is not None
                                        else 1
                                    ),
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
                                    memory_evidence=_audit_evidence_payload(
                                        active_memory_evidence_payload
                                    ),
                                    fallback_evidence=_audit_evidence_payload(
                                        _verification_payload(fallback_verification)
                                    ),
                                    fallback_from_memory_evidence=(
                                        _audit_evidence_payload(
                                            _verification_payload(
                                                fallback_from_memory_evidence_source
                                            )
                                        )
                                    ),
                                    detector_confirmation_events=tuple(
                                        detector_confirmation_events
                                    ),
                                )
                            )
                        )
        finally:
            sim.close()

    requested_group_ids = (
        [str(group_id) for group_id in selected_group_ids]
        if selected_group_ids is not None
        else []
    )
    summary = _base_summary(
        task="habitat_closed_loop_dual_anchor_objectnav",
        full_habitat_run=True,
        dataset_dir=dataset_path,
        scene_root=scene_root_path,
        target_categories=target_categories,
        policies=policies,
        max_groups=max_groups,
        selected_group_ids=selected_group_ids,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        frontier_mode=frontier_mode,
        frontier_probe_count=frontier_probe_count,
        frontier_probe_heading_count=frontier_probe_heading_count,
        post_memory_search_mode=post_memory_search_mode,
        local_search_radii_m=local_search_radii_m,
        local_search_probe_count=local_search_probe_count,
        local_search_heading_count=local_search_heading_count,
        local_search_score_mode=local_search_score_mode,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
        memory_reliability_mode=memory_reliability_mode,
        memory_validity_model_path=memory_validity_model_path,
        route_observation_mode=route_observation_mode,
        detector_confirmation_mode=detector_confirmation_mode,
        detector_confirmation_frames=detector_confirmation_frames,
        detector_confirmation_min_translation=detector_confirmation_min_translation,
        detector_confirmation_min_rotation_deg=detector_confirmation_min_rotation_deg,
        detector_confirmation_min_mask_iou=detector_confirmation_min_mask_iou,
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
                "selection_mode": (
                    "explicit_group_ids"
                    if selected_group_ids is not None
                    else "balanced_categories"
                ),
                "requested_group_count": len(requested_group_ids),
                "requested_group_ids": requested_group_ids,
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
    elif plan.matching_reason in {"ambiguous", "expected_utility_frontier"} or (
        plan.policy == "memory_guided" and plan.memory_decision == "frontier_first"
    ):
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
    elif (
        plan.policy == "memory_guided"
        and plan.memory_decision == "memory_first"
        and int(plan.fallback_from_memory_action_count) > 0
    ):
        selected = ["memory", "frontier"]
        action_count = plan.memory_action_count + plan.fallback_from_memory_action_count
        distance = (
            plan.memory_executed_distance_m
            + plan.fallback_from_memory_executed_distance_m
        )
        success = False
        memory_reused = False
    else:
        selected = ["memory"]
        action_count = plan.memory_action_count
        distance = plan.memory_executed_distance_m
        success = False
        memory_reused = False
    decision_bucket = _memory_decision_bucket(
        plan=plan,
        selected=selected,
        success=bool(success),
    )
    hindsight = _hindsight_decision_metrics(
        plan=plan,
        selected=selected,
        action_count=int(action_count),
        distance_m=float(distance),
    )
    return {
        "group_id": plan.group_id,
        "category": plan.category,
        "policy": plan.policy,
        "memory_instance_id": plan.memory_instance_id,
        "target_instance_id": plan.target_instance_id,
        "relocation_pair_distance_m": (
            None
            if plan.relocation_pair_distance_m is None
            else round(float(plan.relocation_pair_distance_m), 6)
        ),
        "query_repeat_index": int(plan.query_repeat_index),
        "success": bool(success),
        "selected_candidate_types": selected,
        "matching_reason": plan.matching_reason,
        "memory_reused": memory_reused,
        "memory_decision_bucket": decision_bucket,
        "hindsight_best_candidate_type": hindsight["best_candidate_type"],
        "hindsight_action_regret": hindsight["action_regret"],
        "hindsight_distance_regret_m": hindsight["distance_regret_m"],
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
        "memory_evidence": _audit_evidence_payload(plan.memory_evidence),
        "fallback_evidence": _audit_evidence_payload(plan.fallback_evidence),
        "fallback_from_memory_evidence": _audit_evidence_payload(
            plan.fallback_from_memory_evidence
        ),
        "detector_confirmation_events": [
            dict(event) for event in (plan.detector_confirmation_events or ())
        ],
        "memory_decision": plan.memory_decision,
        "memory_valid_prior": round(float(plan.memory_valid_prior), 6),
        "memory_reliability_mode": plan.memory_reliability_mode,
        "memory_reliability": plan.memory_reliability,
        "route_observation_mode": plan.route_observation_mode,
        "memory_route_observation": _route_observation_payload(
            source=plan.memory_route_observation_source,
            step_index=plan.memory_route_observation_step_index,
            observation_count=plan.memory_route_observation_count,
        ),
        "fallback_route_observation": _route_observation_payload(
            source=plan.fallback_route_observation_source,
            step_index=plan.fallback_route_observation_step_index,
            observation_count=plan.fallback_route_observation_count,
        ),
        "fallback_from_memory_route_observation": _route_observation_payload(
            source=plan.fallback_from_memory_route_observation_source,
            step_index=plan.fallback_from_memory_route_observation_step_index,
            observation_count=plan.fallback_from_memory_route_observation_count,
        ),
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


def _route_observation_payload(
    *,
    source: str,
    step_index: int | None,
    observation_count: int,
) -> dict[str, Any]:
    return {
        "source": str(source),
        "step_index": None if step_index is None else int(step_index),
        "observation_count": int(observation_count),
    }


def _detector_confirmation_config_payload(
    config: DetectorConfirmationConfig,
) -> dict[str, Any]:
    return {
        "frames": int(config.frames),
        "min_translation_m": round(float(config.min_translation_m), 6),
        "min_rotation_deg": round(float(config.min_rotation_deg), 6),
        "min_mask_iou": round(float(config.min_mask_iou), 6),
    }


def _apply_detector_confirmation(
    *,
    verification: Any,
    state: DetectorConfirmationState,
    mode: str,
    pose: tuple[
        tuple[float, float, float],
        tuple[float, float, float, float],
    ],
    detector_mask: np.ndarray,
    config: DetectorConfirmationConfig,
    events: list[dict[str, Any]] | None = None,
    source: str = "",
    context: str = "",
) -> Any:
    if mode not in SUPPORTED_DETECTOR_CONFIRMATION_MODES:
        raise ValueError(
            "mode must be one of: "
            + ", ".join(SUPPORTED_DETECTOR_CONFIRMATION_MODES)
        )
    if config.frames <= 0:
        raise ValueError("config.frames must be positive")
    if mode == "single_frame":
        return verification
    if not _is_detector_evidence_reason(str(getattr(verification, "evidence_reason", ""))):
        if not bool(getattr(verification, "shared_gate_success", False)):
            state.reset()
        return verification
    if not bool(getattr(verification, "shared_gate_success", False)):
        state.reset()
        return verification

    if config.frames <= 1:
        confirmation_payload = {
            "mode": mode,
            "candidate_reason": str(getattr(verification, "evidence_reason", "")),
            "pending_count": 1,
            "translation_m": 0.0,
            "rotation_deg": 0.0,
            "mask_iou": 1.0,
            "confirmed": True,
        }
        _record_detector_confirmation_event(
            events=events,
            source=source,
            context=context,
            verification=verification,
            confirmation=confirmation_payload,
        )
        return DetectorConfirmedVerification(
            source=verification,
            evidence_type_value=_verification_evidence_type_value(verification),
            target_visible=bool(getattr(verification, "target_visible", False)),
            evidence_strength=float(getattr(verification, "evidence_strength", 1.0)),
            evidence_reason=str(getattr(verification, "evidence_reason", "")),
            detector_confirmation=confirmation_payload,
        )

    pending_count, translation, rotation_deg, mask_iou = state.observe(
        pose,
        detector_mask,
    )
    temporal_confirmed = pending_count >= config.frames
    view_confirmed = (
        translation >= config.min_translation_m
        or rotation_deg >= config.min_rotation_deg
    )
    mask_confirmed = mask_iou >= config.min_mask_iou
    confirmation_payload = {
        "mode": mode,
        "candidate_reason": str(getattr(verification, "evidence_reason", "")),
        "pending_count": int(pending_count),
        "translation_m": round(float(translation), 6),
        "rotation_deg": round(float(rotation_deg), 6),
        "mask_iou": round(float(mask_iou), 6),
        "confirmed": bool(
            temporal_confirmed and view_confirmed and mask_confirmed
        ),
    }
    if confirmation_payload["confirmed"]:
        _record_detector_confirmation_event(
            events=events,
            source=source,
            context=context,
            verification=verification,
            confirmation=confirmation_payload,
        )
        position, rotation = pose
        state.pending_count = 1
        state.origin_position = position
        state.origin_rotation = rotation
        state.origin_mask = np.asarray(detector_mask, dtype=bool).copy()
        return DetectorConfirmedVerification(
            source=verification,
            evidence_type_value="positive",
            target_visible=bool(getattr(verification, "target_visible", False)),
            evidence_strength=float(getattr(verification, "evidence_strength", 1.0)),
            evidence_reason=(
                "confirmed_"
                + str(getattr(verification, "evidence_reason", "detector_positive"))
            ),
            detector_confirmation=confirmation_payload,
        )

    if not temporal_confirmed:
        reason = "pending_detector_confirmation"
    elif not view_confirmed:
        reason = "waiting_for_multiview_detector_confirmation"
    else:
        reason = "waiting_for_detector_mask_consistency"
    _record_detector_confirmation_event(
        events=events,
        source=source,
        context=context,
        verification=verification,
        confirmation=confirmation_payload,
    )
    return DetectorConfirmedVerification(
        source=verification,
        evidence_type_value="unknown",
        target_visible=False,
        evidence_strength=0.35,
        evidence_reason=reason,
        detector_confirmation=confirmation_payload,
    )


def _record_detector_confirmation_event(
    *,
    events: list[dict[str, Any]] | None,
    source: str,
    context: str,
    verification: Any,
    confirmation: dict[str, Any],
) -> None:
    if events is None:
        return
    events.append(
        {
            "context": str(context),
            "source": str(source),
            "candidate_reason": str(confirmation.get("candidate_reason", "")),
            "outcome": (
                "confirmed" if bool(confirmation.get("confirmed", False)) else "suppressed"
            ),
            "pending_count": int(confirmation.get("pending_count", 0) or 0),
            "translation_m": round(float(confirmation.get("translation_m", 0.0)), 6),
            "rotation_deg": round(float(confirmation.get("rotation_deg", 0.0)), 6),
            "mask_iou": round(float(confirmation.get("mask_iou", 0.0)), 6),
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
        }
    )


def _verification_evidence_type_value(verification: Any) -> str:
    evidence_type = getattr(verification, "evidence_type", None)
    if evidence_type is None:
        return "positive" if bool(verification.shared_gate_success) else "unknown"
    return str(getattr(evidence_type, "value", evidence_type))


def _route_observation_result_payload(result: RouteObservationResult) -> dict[str, Any]:
    return _route_observation_payload(
        source=result.selected_source,
        step_index=result.selected_step_index,
        observation_count=result.observation_count,
    )


def _route_observation_from_navmesh_result(
    result: NavmeshFrontierRouteResult,
) -> RouteObservationResult:
    return RouteObservationResult(
        route=result.route,
        selected_source=result.selected_probe_source,
        selected_verification=result.selected_verification,
        selected_step_index=_step_index_from_observation_source(
            result.selected_probe_source
        ),
        observation_count=result.verification_count,
    )


def _step_index_from_observation_source(source: str) -> int | None:
    marker = ":step:"
    if marker not in source:
        return None
    try:
        return int(source.rsplit(marker, maxsplit=1)[1])
    except ValueError:
        return None


def _base_summary(
    *,
    task: str,
    full_habitat_run: bool,
    dataset_dir: str | Path,
    scene_root: str | Path,
    target_categories: Sequence[str],
    policies: Sequence[str],
    max_groups: int | None,
    selected_group_ids: Sequence[str] | None,
    sensor_width: int,
    sensor_height: int,
    gate_threshold: float,
    ambiguity_margin: float,
    frontier_proxy_waypoints: int,
    frontier_mode: str,
    frontier_probe_count: int,
    frontier_probe_heading_count: int,
    post_memory_search_mode: str,
    local_search_radii_m: Sequence[float],
    local_search_probe_count: int,
    local_search_heading_count: int,
    local_search_score_mode: str,
    challenge: str,
    query_repeats: int,
    memory_valid_prior: float,
    memory_reliability_mode: str,
    memory_validity_model_path: str | Path | None,
    route_observation_mode: str,
    detector_confirmation_mode: str,
    detector_confirmation_frames: int,
    detector_confirmation_min_translation: float,
    detector_confirmation_min_rotation_deg: float,
    detector_confirmation_min_mask_iou: float,
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
        "frontier_probe_heading_count": int(frontier_probe_heading_count),
        "post_memory_search_mode": post_memory_search_mode,
        "local_search_radii_m": [
            round(float(radius), 6) for radius in local_search_radii_m
        ],
        "local_search_probe_count": int(local_search_probe_count),
        "local_search_heading_count": int(local_search_heading_count),
        "local_search_score_mode": local_search_score_mode,
        "challenge": challenge,
        "query_repeats": int(query_repeats),
        "memory_valid_prior": round(float(memory_valid_prior), 6),
        "memory_reliability_mode": memory_reliability_mode,
        "memory_validity_model": (
            None
            if memory_validity_model_path is None
            else str(memory_validity_model_path)
        ),
        "route_observation_mode": route_observation_mode,
        "detector_confirmation_mode": detector_confirmation_mode,
        "detector_confirmation": _detector_confirmation_config_payload(
            DetectorConfirmationConfig(
                frames=detector_confirmation_frames,
                min_translation_m=detector_confirmation_min_translation,
                min_rotation_deg=detector_confirmation_min_rotation_deg,
                min_mask_iou=detector_confirmation_min_mask_iou,
            )
        ),
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
        "episode_selection": {
            "selection_mode": (
                "explicit_group_ids"
                if selected_group_ids is not None
                else "balanced_categories"
            ),
            "requested_group_count": (
                len(selected_group_ids) if selected_group_ids is not None else 0
            ),
            "requested_group_ids": (
                [str(group_id) for group_id in selected_group_ids]
                if selected_group_ids is not None
                else []
            ),
        },
        "session_restart": {
            "memory_frame_id": "map_session_1",
            "runtime_frame_id": "map_session_2",
            "frame_transform": _transform_payload(_session_restart_transform()),
        },
        "artifact_files": {"summary": "summary.json"},
        "limits": [
            "Preflight does not import Habitat or detector weights.",
            "Current Habitat slice is option-level action smoke, not official SPL.",
            (
                "Grounding-DINO route checks are controlled by "
                "route_observation_mode; per_action verifies route poses but "
                "still does not build a map."
            ),
            "navmesh_frontier samples deterministic navmesh probes but is not an occupancy-grid frontier.",
        ],
    }


def _load_memory_validity_model(
    memory_validity_model_path: str | Path | None,
) -> dict[str, Any] | None:
    if memory_validity_model_path is None:
        return None
    model_path = Path(memory_validity_model_path)
    payload = json.loads(model_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("memory validity model JSON must contain an object")
    return payload


def _effective_post_memory_search_mode(
    *,
    frontier_mode: str,
    post_memory_search_mode: str,
) -> str:
    if post_memory_search_mode == "frontier_mode":
        return frontier_mode
    return post_memory_search_mode


def _validate_common(
    *,
    target_categories: Sequence[str],
    policies: Sequence[str],
    max_groups: int | None,
    selected_group_ids: Sequence[str] | None,
    sensor_width: int,
    sensor_height: int,
    gate_threshold: float,
    ambiguity_margin: float,
    frontier_proxy_waypoints: int,
    frontier_mode: str,
    frontier_probe_count: int,
    frontier_probe_heading_count: int,
    post_memory_search_mode: str,
    local_search_radii_m: Sequence[float],
    local_search_probe_count: int,
    local_search_heading_count: int,
    local_search_score_mode: str,
    challenge: str,
    query_repeats: int,
    memory_valid_prior: float,
    memory_reliability_mode: str,
    memory_validity_model_path: str | Path | None,
    route_observation_mode: str,
    detector_confirmation_mode: str,
    detector_confirmation_frames: int,
    detector_confirmation_min_translation: float,
    detector_confirmation_min_rotation_deg: float,
    detector_confirmation_min_mask_iou: float,
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
    if selected_group_ids is not None:
        requested_group_ids = [str(group_id) for group_id in selected_group_ids]
        if not requested_group_ids:
            raise ValueError(
                "selected_group_ids must contain at least one group id when provided"
            )
        duplicates = sorted(
            {
                group_id
                for group_id in requested_group_ids
                if requested_group_ids.count(group_id) > 1
            }
        )
        if duplicates:
            raise ValueError(
                "selected_group_ids contains duplicates: " + ", ".join(duplicates)
            )
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
    if frontier_probe_heading_count <= 0:
        raise ValueError("frontier_probe_heading_count must be positive")
    if post_memory_search_mode not in SUPPORTED_POST_MEMORY_SEARCH_MODES:
        raise ValueError(
            "post_memory_search_mode must be one of: "
            + ", ".join(SUPPORTED_POST_MEMORY_SEARCH_MODES)
        )
    local_radii = tuple(float(radius) for radius in local_search_radii_m)
    if not local_radii or any(radius <= 0.0 for radius in local_radii):
        raise ValueError("local_search_radii_m must contain positive radii")
    if local_search_probe_count <= 0:
        raise ValueError("local_search_probe_count must be positive")
    if local_search_heading_count <= 0:
        raise ValueError("local_search_heading_count must be positive")
    if local_search_score_mode not in SUPPORTED_LOCAL_SEARCH_SCORE_MODES:
        raise ValueError(
            "local_search_score_mode must be one of: "
            + ", ".join(SUPPORTED_LOCAL_SEARCH_SCORE_MODES)
        )
    if challenge not in SUPPORTED_CHALLENGES:
        raise ValueError(
            "challenge must be one of: " + ", ".join(SUPPORTED_CHALLENGES)
        )
    if query_repeats <= 0:
        raise ValueError("query_repeats must be positive")
    if not 0.0 <= memory_valid_prior <= 1.0:
        raise ValueError("memory_valid_prior must be in [0, 1]")
    if memory_reliability_mode not in SUPPORTED_MEMORY_RELIABILITY_MODES:
        raise ValueError(
            "memory_reliability_mode must be one of: "
            + ", ".join(SUPPORTED_MEMORY_RELIABILITY_MODES)
        )
    if memory_validity_model_path is not None and not Path(
        memory_validity_model_path
    ).is_file():
        raise ValueError(
            "memory_validity_model_path must point to an existing JSON file"
        )
    if route_observation_mode not in SUPPORTED_ROUTE_OBSERVATION_MODES:
        raise ValueError(
            "route_observation_mode must be one of: "
            + ", ".join(SUPPORTED_ROUTE_OBSERVATION_MODES)
        )
    if detector_confirmation_mode not in SUPPORTED_DETECTOR_CONFIRMATION_MODES:
        raise ValueError(
            "detector_confirmation_mode must be one of: "
            + ", ".join(SUPPORTED_DETECTOR_CONFIRMATION_MODES)
        )
    if detector_confirmation_frames <= 0:
        raise ValueError("detector_confirmation_frames must be positive")
    if detector_confirmation_min_translation < 0.0:
        raise ValueError(
            "detector_confirmation_min_translation must be non-negative"
        )
    if detector_confirmation_min_rotation_deg < 0.0:
        raise ValueError(
            "detector_confirmation_min_rotation_deg must be non-negative"
        )
    if not 0.0 <= detector_confirmation_min_mask_iou <= 1.0:
        raise ValueError("detector_confirmation_min_mask_iou must be in [0, 1]")
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


def _select_closed_loop_groups(
    groups: Sequence[Any],
    *,
    max_groups: int | None,
    selected_group_ids: Sequence[str] | None = None,
) -> list[Any]:
    if selected_group_ids is not None:
        requested_group_ids = [str(group_id) for group_id in selected_group_ids]
        if not requested_group_ids:
            raise ValueError(
                "selected_group_ids must contain at least one group id when provided"
            )
        group_by_id = {
            str(getattr(group, "group_id")): group for group in groups
        }
        missing_group_ids = [
            group_id for group_id in requested_group_ids if group_id not in group_by_id
        ]
        if missing_group_ids:
            raise ValueError(
                "selected_group_ids missing from lifecycle groups: "
                + ", ".join(missing_group_ids)
            )
        return [group_by_id[group_id] for group_id in requested_group_ids]
    if max_groups is not None:
        return _select_balanced_groups(groups, max_groups=max_groups)
    return list(groups)


def _build_goal_object_relocation_groups(groups: Sequence[Any]) -> list[Any]:
    by_scene_category: dict[tuple[str, str], list[Any]] = {}
    for group in groups:
        instance_id = str(getattr(group, "instance_id", ""))
        if not instance_id.startswith("goal_object:"):
            continue
        key = (str(getattr(group, "scene_key", "")), str(getattr(group, "category", "")))
        by_scene_category.setdefault(key, []).append(group)

    relocated: list[Any] = []
    for (scene_key, category), bucket in sorted(by_scene_category.items()):
        ordered = sorted(bucket, key=lambda group: str(getattr(group, "instance_id", "")))
        for old_group in ordered:
            old_instance_id = str(getattr(old_group, "instance_id"))
            for new_group in ordered:
                new_instance_id = str(getattr(new_group, "instance_id"))
                if old_instance_id == new_instance_id:
                    continue
                relocation_pair_distance_m = _relocation_pair_distance_m(
                    old_group=old_group,
                    new_group=new_group,
                )
                relocated.append(
                    replace(
                        old_group,
                        group_id=(
                            f"{scene_key}|{category}|relocated:"
                            f"{old_instance_id}->{new_instance_id}"
                        ),
                        instance_id=f"relocated:{old_instance_id}->{new_instance_id}",
                        query_episode=getattr(new_group, "query_episode"),
                        fallback_position=getattr(new_group, "fallback_position"),
                        fallback_rotation=getattr(new_group, "fallback_rotation"),
                        memory_instance_id=old_instance_id,
                        target_instance_id=new_instance_id,
                        relocation_pair_distance_m=relocation_pair_distance_m,
                    )
                )
    return sorted(
        relocated,
        key=lambda group: (
            -float(getattr(group, "relocation_pair_distance_m", 0.0) or 0.0),
            str(getattr(group, "group_id", "")),
        ),
    )


def _relocation_pair_distance_m(*, old_group: Any, new_group: Any) -> float:
    return round(
        math.dist(
            tuple(float(value) for value in getattr(old_group, "memory_position")),
            tuple(float(value) for value in getattr(new_group, "fallback_position")),
        ),
        6,
    )


def _semantic_ids_for_closed_loop_group(
    *,
    semantic_id_to_category: dict[int, str],
    group: Any,
    challenge: str,
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    from objectnav_core.evaluation.habitat_objectnav_valmini_semantic_stress import (
        _semantic_ids_for_target_category,
    )

    category = str(getattr(group, "category"))
    category_ids = _semantic_ids_for_target_category(
        semantic_id_to_category,
        category,
    )
    if challenge != "goal_object_relocation":
        return category_ids, category_ids

    memory_ids = _semantic_ids_for_goal_object_instance(
        semantic_id_to_category=semantic_id_to_category,
        category=category,
        instance_id=(
            str(getattr(group, "memory_instance_id", "") or "")
            or str(getattr(group, "instance_id", ""))
        ),
        fallback_ids=category_ids,
    )
    query_ids = _semantic_ids_for_goal_object_instance(
        semantic_id_to_category=semantic_id_to_category,
        category=category,
        instance_id=(
            str(getattr(group, "target_instance_id", "") or "")
            or str(getattr(group, "instance_id", ""))
        ),
        fallback_ids=category_ids,
    )
    return memory_ids, query_ids


def _candidate_verification_semantic_ids(
    *,
    challenge: str,
    candidate_role: str,
    memory_target_semantic_ids: Sequence[int],
    target_semantic_ids: Sequence[int],
) -> tuple[int, ...]:
    if candidate_role not in {"memory_anchor", "query_task"}:
        raise ValueError("candidate_role must be memory_anchor or query_task")
    if challenge == "goal_object_relocation" and candidate_role == "memory_anchor":
        return tuple(memory_target_semantic_ids)
    return tuple(target_semantic_ids)


def _semantic_ids_for_goal_object_instance(
    *,
    semantic_id_to_category: dict[int, str],
    category: str,
    instance_id: str,
    fallback_ids: tuple[int, ...],
) -> tuple[int, ...]:
    semantic_id = _goal_object_semantic_id(instance_id)
    if semantic_id is None:
        return fallback_ids
    if semantic_id not in semantic_id_to_category:
        return fallback_ids

    from objectnav_core.evaluation.habitat_objectnav_valmini_semantic_stress import (
        _semantic_ids_for_target_category,
    )

    category_ids = _semantic_ids_for_target_category(
        semantic_id_to_category,
        category,
    )
    if semantic_id not in category_ids:
        return fallback_ids
    return (semantic_id,)


def _goal_object_semantic_id(instance_id: str) -> int | None:
    prefix = "goal_object:"
    if not instance_id.startswith(prefix):
        return None
    try:
        return int(instance_id[len(prefix) :])
    except ValueError:
        return None


def _matching_reason_for_challenge(challenge: str) -> str:
    if challenge == "stable":
        return "accepted"
    if challenge == "ambiguous":
        return "ambiguous"
    if challenge == "goal_object_relocation":
        return "accepted"
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


def _memory_reliability_detector_confirmation_context(
    *,
    challenge: str,
    policy: str,
    repeat_index: int,
    repair_succeeded: bool,
) -> str:
    if (
        challenge == "stale_proxy"
        and policy == "memory_guided"
        and repeat_index > 0
        and repair_succeeded
    ):
        return "fallback_from_memory"
    return "memory"


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
    fallback_available: bool = True,
    fallback_from_memory_available: bool = True,
) -> str:
    if not fallback_available:
        return "memory_first"
    if not fallback_from_memory_available and memory_valid_prior < 1.0:
        return "frontier_first"
    expected_memory = _expected_memory_first_action_count(
        memory_action_count=memory_action_count,
        fallback_from_memory_action_count=fallback_from_memory_action_count,
        memory_valid_prior=memory_valid_prior,
    )
    if expected_memory <= float(fallback_action_count):
        return "memory_first"
    return "frontier_first"


def _estimate_memory_valid_prior(
    *,
    base_prior: float,
    mode: str,
    matching_reason: str,
    verification: Any,
    category: str,
    transform: FrameTransform2D,
    repeat_index: int,
    detector_confirmation_events: Sequence[dict[str, Any]] | None = None,
    detector_confirmation_context: str = "memory",
) -> MemoryReliabilityEstimate:
    if not 0.0 <= base_prior <= 1.0:
        raise ValueError("base_prior must be in [0, 1]")
    if mode not in SUPPORTED_MEMORY_RELIABILITY_MODES:
        raise ValueError(
            "mode must be one of: " + ", ".join(SUPPORTED_MEMORY_RELIABILITY_MODES)
        )
    if mode == "fixed":
        value = round(float(base_prior), 6)
        return MemoryReliabilityEstimate(
            mode=mode,
            value=value,
            components={"base_prior": value},
            reason="fixed_prior",
        )

    evidence_estimate = _evidence_memory_reliability_estimate(
        base_prior=base_prior,
        matching_reason=matching_reason,
        verification=verification,
        category=category,
        transform=transform,
        repeat_index=repeat_index,
    )
    if mode == "evidence":
        return evidence_estimate
    return _event_posterior_memory_reliability_estimate(
        base_prior=base_prior,
        evidence_estimate=evidence_estimate,
        detector_confirmation_events=detector_confirmation_events,
        detector_confirmation_context=detector_confirmation_context,
    )


def _evidence_memory_reliability_estimate(
    *,
    base_prior: float,
    matching_reason: str,
    verification: Any,
    category: str,
    transform: FrameTransform2D,
    repeat_index: int,
) -> MemoryReliabilityEstimate:
    matching = _matching_reliability_component(matching_reason)
    current_evidence = _current_evidence_reliability_component(verification)
    covariance = _transform_covariance_reliability_component(transform)
    category_prior = _category_reliability_component(category)
    recency = _repeat_reliability_component(repeat_index)
    if matching < 0.5:
        value = min(0.3, base_prior * matching)
        reason = f"matching_{matching_reason}"
    elif current_evidence < 0.5:
        value = min(0.34, 0.5 * float(base_prior) + 0.25 * current_evidence)
        reason = "weak_current_evidence"
    else:
        value = (
            0.10 * float(base_prior)
            + 0.50 * current_evidence
            + 0.22 * matching
            + 0.08 * covariance
            + 0.05 * category_prior
            + 0.05 * recency
        )
        reason = "evidence_weighted"
        if current_evidence >= 0.95 and matching >= 1.0 and covariance >= 0.85:
            value = max(value, 0.96)
            reason = "strong_current_evidence_floor"
    components = {
        "base_prior": round(float(base_prior), 6),
        "current_evidence": round(current_evidence, 6),
        "matching": round(matching, 6),
        "transform_covariance": round(covariance, 6),
        "category_prior": round(category_prior, 6),
        "recency": round(recency, 6),
    }
    return MemoryReliabilityEstimate(
        mode="evidence",
        value=round(_clamp01(value), 6),
        components=components,
        reason=reason,
    )


def _event_posterior_memory_reliability_estimate(
    *,
    base_prior: float,
    evidence_estimate: MemoryReliabilityEstimate,
    detector_confirmation_events: Sequence[dict[str, Any]] | None,
    detector_confirmation_context: str,
) -> MemoryReliabilityEstimate:
    event_components = _detector_confirmation_event_posterior_components(
        base_prior=base_prior,
        detector_confirmation_events=detector_confirmation_events,
        detector_confirmation_context=detector_confirmation_context,
    )
    components = dict(evidence_estimate.components)
    components.update(event_components)
    if event_components["detector_event_count"] <= 0.0:
        return MemoryReliabilityEstimate(
            mode="event_posterior",
            value=evidence_estimate.value,
            components=components,
            reason="event_posterior_no_events",
        )

    posterior = event_components["detector_event_posterior"]
    value = 0.45 * float(evidence_estimate.value) + 0.55 * float(posterior)
    reason = "event_posterior_weighted"
    if components.get("matching", 1.0) < 0.5:
        value = min(value, float(evidence_estimate.value))
        reason = "event_posterior_matching_limited"
    elif components.get("current_evidence", 1.0) < 0.5:
        value = min(value, float(evidence_estimate.value))
        reason = "event_posterior_weak_evidence_limited"
    return MemoryReliabilityEstimate(
        mode="event_posterior",
        value=round(_clamp01(value), 6),
        components=components,
        reason=reason,
    )


def _apply_learned_memory_validity_model(
    *,
    model: Mapping[str, Any],
    base_estimate: MemoryReliabilityEstimate,
    memory_action_count: int,
    fallback_action_count: int,
    fallback_from_memory_action_count: int,
    memory_valid_prior: float,
    relocation_pair_distance_m: float | None,
    memory_evidence: Mapping[str, Any] | None,
) -> MemoryReliabilityEstimate:
    features = _learned_memory_validity_features(
        base_estimate=base_estimate,
        memory_action_count=memory_action_count,
        fallback_action_count=fallback_action_count,
        fallback_from_memory_action_count=fallback_from_memory_action_count,
        memory_valid_prior=memory_valid_prior,
        relocation_pair_distance_m=relocation_pair_distance_m,
        memory_evidence=memory_evidence,
    )
    probability = predict_memory_validity(model, features)
    feature_names = model.get("feature_names", ())
    if not isinstance(feature_names, SequenceABC) or isinstance(feature_names, str):
        feature_count = 0
    else:
        feature_count = len(feature_names)
    components = {
        "base_reliability_value": round(float(base_estimate.value), 6),
        "model_feature_count": float(feature_count),
    }
    return MemoryReliabilityEstimate(
        mode="learned_model",
        value=round(_clamp01(probability), 6),
        components=components,
        reason="learned_memory_validity_model",
    )


def _learned_memory_validity_features(
    *,
    base_estimate: MemoryReliabilityEstimate,
    memory_action_count: int,
    fallback_action_count: int,
    fallback_from_memory_action_count: int,
    memory_valid_prior: float,
    relocation_pair_distance_m: float | None,
    memory_evidence: Mapping[str, Any] | None,
) -> dict[str, float | None]:
    evidence = memory_evidence or {}
    features: dict[str, float | None] = {
        "memory_action_count": float(memory_action_count),
        "fallback_action_count": float(fallback_action_count),
        "fallback_from_memory_action_count": float(fallback_from_memory_action_count),
        "memory_valid_prior": float(memory_valid_prior),
        "relocation_pair_distance_m": (
            None
            if relocation_pair_distance_m is None
            else float(relocation_pair_distance_m)
        ),
        "memory_evidence_detector_pixels": _feature_float(
            evidence.get("detector_pixels")
        ),
        "memory_evidence_overlap_pixels": _feature_float(
            evidence.get("overlap_pixels")
        ),
        "memory_evidence_detector_precision": _feature_float(
            evidence.get("detector_precision")
        ),
        "memory_evidence_oracle_recall": _feature_float(
            evidence.get("oracle_recall")
        ),
    }
    for component_name, component_value in base_estimate.components.items():
        feature_name = _memory_reliability_feature_name(component_name)
        if feature_name is not None:
            features[feature_name] = _feature_float(component_value)
    return features


def _memory_reliability_feature_name(component_name: str) -> str | None:
    if component_name in {
        "base_prior",
        "current_evidence",
        "matching",
        "transform_covariance",
        "recency",
    }:
        return f"memory_reliability_{component_name}"
    if component_name in {
        "detector_event_count",
        "detector_event_confirmed_weight",
        "detector_event_suppressed_weight",
        "detector_event_posterior",
    }:
        return f"memory_{component_name}"
    return None


def _feature_float(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _detector_confirmation_event_posterior_components(
    *,
    base_prior: float,
    detector_confirmation_events: Sequence[dict[str, Any]] | None,
    detector_confirmation_context: str,
) -> dict[str, float]:
    alpha = max(0.01, float(base_prior))
    beta = max(0.01, 1.0 - float(base_prior))
    confirmed_weight = 0.0
    suppressed_weight = 0.0
    event_count = 0
    for event in detector_confirmation_events or ():
        if str(event.get("context", "")) != detector_confirmation_context:
            continue
        outcome = str(event.get("outcome", ""))
        quality = _detector_confirmation_event_quality(event)
        if outcome == "confirmed":
            confirmed_weight += 1.0 + quality
        elif outcome == "suppressed":
            suppressed_weight += 0.75 + quality
        else:
            continue
        event_count += 1
    posterior = (
        (alpha + confirmed_weight)
        / (alpha + beta + confirmed_weight + suppressed_weight)
        if event_count
        else float(base_prior)
    )
    return {
        "detector_event_count": float(event_count),
        "detector_event_confirmed_weight": round(confirmed_weight, 6),
        "detector_event_suppressed_weight": round(suppressed_weight, 6),
        "detector_event_posterior": round(_clamp01(posterior), 6),
    }


def _detector_confirmation_event_quality(event: dict[str, Any]) -> float:
    detector_pixels = max(0, int(event.get("detector_pixels", 0) or 0))
    pixel_quality = (
        _clamp01(math.log1p(detector_pixels) / math.log1p(4096.0))
        if detector_pixels > 0
        else 0.0
    )
    mask_quality = _clamp01(float(event.get("mask_iou", 0.0) or 0.0))
    translation_quality = _clamp01(
        float(event.get("translation_m", 0.0) or 0.0) / 0.25
    )
    rotation_quality = _clamp01(float(event.get("rotation_deg", 0.0) or 0.0) / 10.0)
    view_quality = max(translation_quality, rotation_quality)
    pending_quality = _clamp01(float(event.get("pending_count", 0.0) or 0.0) / 2.0)
    return _clamp01(
        0.35 * pixel_quality
        + 0.25 * mask_quality
        + 0.25 * view_quality
        + 0.15 * pending_quality
    )


def _memory_reliability_payload(
    estimate: MemoryReliabilityEstimate,
) -> dict[str, Any]:
    return {
        "mode": estimate.mode,
        "value": round(float(estimate.value), 6),
        "components": {
            key: round(float(value), 6)
            for key, value in sorted(estimate.components.items())
        },
        "reason": estimate.reason,
    }


def _matching_reliability_component(matching_reason: str) -> float:
    if matching_reason in {"accepted", "expected_utility_frontier"}:
        return 1.0
    if matching_reason == "no_current_observation":
        return 0.45
    if matching_reason == "ambiguous":
        return 0.25
    return 0.2


def _current_evidence_reliability_component(verification: Any) -> float:
    if not bool(getattr(verification, "shared_gate_success", False)):
        return 0.15
    oracle_pixels = int(getattr(verification, "oracle_target_pixels", 0) or 0)
    detector_pixels = int(getattr(verification, "detector_pixels", 0) or 0)
    evidence_reason = str(getattr(verification, "evidence_reason", ""))
    if _is_detector_evidence_reason(evidence_reason):
        visible_pixels = detector_pixels
    else:
        visible_pixels = max(oracle_pixels, detector_pixels)
    if visible_pixels >= 4096:
        return 0.98
    if visible_pixels >= 512:
        return 0.9
    if visible_pixels >= 24:
        return 0.72
    return 0.62


def _transform_covariance_reliability_component(transform: FrameTransform2D) -> float:
    variance = max(
        0.0,
        float(transform.covariance[0][0]) + float(transform.covariance[1][1]),
    )
    return _clamp01(1.0 / (1.0 + variance))


def _category_reliability_component(category: str) -> float:
    category_priors = {
        "chair": 0.82,
        "toilet": 0.78,
        "bed": 0.76,
        "sofa": 0.74,
        "tv_monitor": 0.68,
        "plant": 0.62,
    }
    return category_priors.get(category, 0.7)


def _repeat_reliability_component(repeat_index: int) -> float:
    return _clamp01(1.0 - 0.08 * max(0, int(repeat_index)))


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, float(value)))


def _memory_decision_for_row(
    *,
    policy: str,
    matching_reason: str,
    raw_memory_decision: str,
) -> str:
    if policy == "frontier_only":
        return "memory_first"
    if policy == "naive_count":
        return "memory_first"
    return raw_memory_decision


def _memory_decision_bucket(
    *,
    plan: HabitatClosedLoopOptionPlan,
    selected: Sequence[str],
    success: bool,
) -> str:
    selected_tuple = tuple(selected)
    if plan.policy == "frontier_only":
        return "frontier_only"
    if plan.policy == "naive_count":
        return "naive_memory_reuse" if selected_tuple == ("memory",) else "naive_other"
    if plan.matching_reason == "ambiguous":
        return "ambiguous_memory_deferred"
    if plan.matching_reason == "expected_utility_frontier":
        return "frontier_shorter_selected"
    if selected_tuple == ("memory", "frontier"):
        return "memory_missed_then_frontier_repaired" if success else "memory_then_frontier_failed"
    if selected_tuple == ("frontier",):
        if plan.memory_verified and plan.memory_action_count < plan.fallback_action_count:
            return "valid_memory_wrongly_deferred"
        if not plan.memory_verified:
            return "harmful_memory_reuse_avoided"
        return "frontier_shorter_selected"
    if selected_tuple == ("memory",):
        if plan.memory_verified and not plan.fallback_verified:
            return "memory_rescued_frontier_failure"
        if plan.memory_verified and plan.memory_action_count <= plan.fallback_action_count:
            return "memory_shorter_reused"
        if plan.memory_verified:
            return "memory_reused_despite_shorter_frontier"
        return "memory_attempt_failed"
    return "other"


def _hindsight_decision_metrics(
    *,
    plan: HabitatClosedLoopOptionPlan,
    selected: Sequence[str],
    action_count: int,
    distance_m: float,
) -> dict[str, Any]:
    feasible: list[tuple[str, int, float]] = []
    if plan.memory_verified:
        feasible.append(
            ("memory", int(plan.memory_action_count), float(plan.memory_executed_distance_m))
        )
    if plan.fallback_verified:
        feasible.append(
            ("frontier", int(plan.fallback_action_count), float(plan.fallback_executed_distance_m))
        )
    fallback_from_memory_verified = (
        plan.fallback_from_memory_verified
        if plan.fallback_from_memory_verified is not None
        else plan.fallback_verified
    )
    if fallback_from_memory_verified:
        feasible.append(
            (
                "memory_then_frontier",
                int(plan.memory_action_count + plan.fallback_from_memory_action_count),
                float(
                    plan.memory_executed_distance_m
                    + plan.fallback_from_memory_executed_distance_m
                ),
            )
        )
    if not feasible:
        return {
            "best_candidate_type": "none",
            "action_regret": 0,
            "distance_regret_m": 0.0,
        }
    best_type, best_actions, best_distance = min(
        feasible,
        key=lambda item: (item[1], item[2], item[0]),
    )
    return {
        "best_candidate_type": best_type,
        "action_regret": max(0, int(action_count) - int(best_actions)),
        "distance_regret_m": round(max(0.0, float(distance_m) - best_distance), 6),
    }


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
    detector_confirmation_mode: str,
    detector_confirmation: DetectorConfirmationConfig,
    helpers: dict[str, Any],
    detector_confirmation_events: list[dict[str, Any]] | None = None,
    detector_confirmation_context: str = "",
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
    state = DetectorConfirmationState()
    verifications: dict[str, Any] = {}
    for candidate_index, candidate in enumerate(candidates):
        verification = verify_view(
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
        verifications[candidate.source] = _apply_detector_confirmation(
            verification=verification,
            state=state,
            mode=detector_confirmation_mode,
            pose=(
                _tuple3(candidate.position) or (0.0, 0.0, 0.0),
                _tuple4(candidate.rotation) or (0.0, 0.0, 0.0, 1.0),
            ),
            detector_mask=getattr(verification, "detector_mask", None)
            if getattr(verification, "detector_mask", None) is not None
            else np.zeros((1, 1), dtype=bool),
            config=detector_confirmation,
            events=detector_confirmation_events,
            source=str(candidate.source),
            context=detector_confirmation_context,
        )
    return verifications


def _route_observation_verifier(
    *,
    detector: str,
    sim: Any,
    target_semantic_ids: Sequence[int],
    target_category: str,
    detector_adapter: Any,
    accepted_detection_labels: set[str],
    noise_level: str,
    rgb_noise: Any,
    depth_noise: Any,
    min_target_pixels: int,
    min_detector_pixels: int,
    max_detection_area_ratio: float | None,
    detector_confirmation_mode: str,
    detector_confirmation: DetectorConfirmationConfig,
    helpers: dict[str, Any],
    frame_index_base: int,
    detector_confirmation_events: list[dict[str, Any]] | None = None,
    detector_confirmation_context: str = "",
) -> Any:
    from objectnav_core.evaluation.habitat_memory_lifecycle_objectnav import (
        _verify_lifecycle_view,
    )
    confirmation_state = DetectorConfirmationState()

    def verify_observation(
        *,
        source: str,
        position: tuple[float, float, float] | None,
        rotation: tuple[float, float, float, float] | None,
        step_index: int | None,
        action: str,
    ) -> Any:
        del action
        if position is None or rotation is None:
            return _OracleVisible(target_visible=False)
        if detector == "oracle_semantic_visibility":
            return _verify_oracle_pose(
                sim=sim,
                position=position,
                rotation=rotation,
                target_semantic_ids=target_semantic_ids,
                min_target_pixels=min_target_pixels,
            )
        verification = _verify_lifecycle_view(
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
            frame_index=frame_index_base + max(0, int(step_index or 0)),
            min_target_pixels=min_target_pixels,
            min_detector_pixels=min_detector_pixels,
            max_detection_area_ratio=max_detection_area_ratio,
            helpers=helpers,
        )
        return _apply_detector_confirmation(
            verification=verification,
            state=confirmation_state,
            mode=detector_confirmation_mode,
            pose=(position, rotation),
            detector_mask=getattr(verification, "detector_mask", None)
            if getattr(verification, "detector_mask", None) is not None
            else np.zeros((1, 1), dtype=bool),
            config=detector_confirmation,
            events=detector_confirmation_events,
            source=source,
            context=detector_confirmation_context,
        )

    return verify_observation


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


def _memory_local_probe_goals(
    *,
    sim: Any,
    memory_anchor: Sequence[float],
    start: Sequence[float],
    seed: int,
    radii_m: Sequence[float],
    probe_count: int,
    angle_count: int,
    score_mode: str,
    min_separation_m: float = 0.25,
) -> tuple[LocalSearchCandidate, ...]:
    del seed
    if probe_count <= 0:
        raise ValueError("probe_count must be positive")
    if angle_count <= 0:
        raise ValueError("angle_count must be positive")
    if min_separation_m < 0.0:
        raise ValueError("min_separation_m must be non-negative")
    if score_mode not in {"distance_prior", "belief_gain"}:
        raise ValueError("score_mode must be distance_prior or belief_gain")
    anchor = _tuple3(memory_anchor)
    start_tuple = _tuple3(start)
    if anchor is None or start_tuple is None:
        raise ValueError("memory_anchor and start must be valid 3D positions")
    radii = tuple(float(radius) for radius in radii_m)
    if not radii or any(radius <= 0.0 for radius in radii):
        raise ValueError("radii_m must contain positive radii")

    pathfinder = sim.pathfinder
    max_radius = max(radii)
    candidates: list[LocalSearchCandidate] = []
    for radius in radii:
        for angle_index in range(angle_count):
            if len(candidates) >= probe_count:
                break
            theta = (2.0 * math.pi * angle_index) / float(angle_count)
            raw_point = (
                round(anchor[0] + math.cos(theta) * radius, 6),
                round(anchor[1], 6),
                round(anchor[2] + math.sin(theta) * radius, 6),
            )
            point = raw_point
            if hasattr(pathfinder, "snap_point"):
                snapped = _tuple3(pathfinder.snap_point(raw_point))
                if snapped is None:
                    continue
                point = tuple(round(float(value), 6) for value in snapped)
            if hasattr(pathfinder, "is_navigable") and not bool(
                pathfinder.is_navigable(point)
            ):
                continue
            if any(
                _distance3(point, existing.position) < min_separation_m
                for existing in candidates
            ):
                continue
            cost_proxy = max(_distance3(start_tuple, point), 1.0)
            distance_prior = math.exp(-radius / max(max_radius, 1e-6))
            if score_mode == "belief_gain":
                distance_prior *= 1.0 + (radius / max(max_radius, 1e-6))
            candidates.append(
                LocalSearchCandidate(
                    source=f"memory_local_active_probe:{len(candidates)}",
                    position=point,
                    radius_m=round(radius, 6),
                    angle_index=angle_index,
                    score=round(distance_prior / cost_proxy, 6),
                )
            )
        if len(candidates) >= probe_count:
            break
    return tuple(candidates)


def _observe_route_until_positive(
    *,
    route: Any,
    route_source: str,
    mode: str,
    verify_observation: Any,
) -> RouteObservationResult:
    if mode not in SUPPORTED_ROUTE_OBSERVATION_MODES:
        raise ValueError(
            "mode must be one of: " + ", ".join(SUPPORTED_ROUTE_OBSERVATION_MODES)
        )
    if mode == "option_end":
        source = f"{route_source}:option_end"
        verification = verify_observation(
            source=source,
            position=_tuple3(getattr(route, "final_position", None)),
            rotation=_tuple4(getattr(route, "final_rotation", None)),
            step_index=None,
            action="option_end",
        )
        return RouteObservationResult(
            route=route,
            selected_source=source,
            selected_verification=verification,
            selected_step_index=None,
            observation_count=1,
        )

    observations = tuple(getattr(route, "observations", ()) or ())
    if not observations:
        return _observe_route_until_positive(
            route=route,
            route_source=route_source,
            mode="option_end",
            verify_observation=verify_observation,
        )

    selected_source = f"{route_source}:step:none"
    selected_verification: Any = _OracleVisible(target_visible=False)
    selected_step_index: int | None = None
    for observation_count, observation in enumerate(observations, start=1):
        step_index = int(getattr(observation, "action_index", observation_count - 1))
        selected_step_index = step_index
        selected_source = f"{route_source}:step:{step_index}"
        selected_verification = verify_observation(
            source=selected_source,
            position=_tuple3(getattr(observation, "position", None)),
            rotation=_tuple4(getattr(observation, "rotation", None)),
            step_index=step_index,
            action=str(getattr(observation, "action", "")),
        )
        if bool(selected_verification.shared_gate_success):
            return RouteObservationResult(
                route=_truncate_route_at_observation(
                    route=route,
                    observation=observation,
                    observation_count=observation_count,
                ),
                selected_source=selected_source,
                selected_verification=selected_verification,
                selected_step_index=step_index,
                observation_count=observation_count,
            )

    return RouteObservationResult(
        route=route,
        selected_source=selected_source,
        selected_verification=selected_verification,
        selected_step_index=selected_step_index,
        observation_count=len(observations),
    )


def _observe_initial_memory_route(
    *,
    route: Any,
    route_source: str,
    challenge: str,
    mode: str,
    initial_memory_verification: Any,
    verify_observation: Any,
) -> RouteObservationResult:
    if challenge == "stale_proxy":
        del mode, verify_observation
        return RouteObservationResult(
            route=route,
            selected_source=f"{route_source}:stale_proxy_absent",
            selected_verification=_stale_proxy_initial_memory_verification(
                initial_memory_verification
            ),
            selected_step_index=None,
            observation_count=0,
        )
    return _observe_route_until_positive(
        route=route,
        route_source=route_source,
        mode=mode,
        verify_observation=verify_observation,
    )


def _truncate_route_at_observation(
    *,
    route: Any,
    observation: Any,
    observation_count: int,
) -> _RouteAggregate:
    action_count = int(getattr(observation, "action_index", observation_count - 1)) + 1
    actions = tuple(str(action) for action in getattr(route, "actions", ())[:action_count])
    return _RouteAggregate(
        actions=actions,
        reached_stop=bool(getattr(route, "reached_stop", False)),
        final_position=_tuple3(getattr(observation, "position", None))
        or _tuple3(getattr(route, "final_position", None))
        or (0.0, 0.0, 0.0),
        final_rotation=_tuple4(getattr(observation, "rotation", None))
        or _tuple4(getattr(route, "final_rotation", None))
        or (0.0, 0.0, 0.0, 1.0),
        executed_distance_m=round(
            float(getattr(observation, "cumulative_distance_m", 0.0) or 0.0),
            6,
        ),
        observations=tuple(getattr(route, "observations", ())[:observation_count]),
    )


def _run_navmesh_frontier_probe_route(
    *,
    start_position: Sequence[float],
    start_rotation: Sequence[float],
    probe_goals: Sequence[Sequence[float]],
    route_segment: Any,
    verify_probe: Any,
    route_error_types: tuple[type[BaseException], ...] = (),
    probe_heading_count: int = DEFAULT_FRONTIER_PROBE_HEADING_COUNT,
    route_observation_mode: str = DEFAULT_ROUTE_OBSERVATION_MODE,
    source_prefix: str = "navmesh_frontier_probe",
) -> NavmeshFrontierRouteResult:
    if probe_heading_count <= 0:
        raise ValueError("probe_heading_count must be positive")
    if not source_prefix:
        raise ValueError("source_prefix must be non-empty")
    if route_observation_mode not in SUPPORTED_ROUTE_OBSERVATION_MODES:
        raise ValueError(
            "route_observation_mode must be one of: "
            + ", ".join(SUPPORTED_ROUTE_OBSERVATION_MODES)
        )
    current_position = _tuple3(start_position)
    current_rotation = _tuple4(start_rotation)
    if current_position is None or current_rotation is None:
        raise ValueError("start position and rotation must be valid")

    actions: list[str] = []
    executed_distance_m = 0.0
    reached_stop = bool(probe_goals)
    selected_verification: Any | None = None
    selected_source = f"{source_prefix}:none"
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
        segment_actions = tuple(str(action) for action in getattr(segment, "actions", ()))
        if route_observation_mode == "per_action":
            for observation in tuple(getattr(segment, "observations", ()) or ()):
                step_index = int(getattr(observation, "action_index", 0))
                selected_source = f"{source_prefix}:{probe_index}:step:{step_index}"
                verification_count += 1
                selected_verification = verify_probe(
                    source=selected_source,
                    position=(
                        _tuple3(getattr(observation, "position", None))
                        or current_position
                    ),
                    rotation=(
                        _tuple4(getattr(observation, "rotation", None))
                        or current_rotation
                    ),
                    probe_index=probe_index,
                )
                selected_position = (
                    _tuple3(getattr(observation, "position", None))
                    or current_position
                )
                if bool(selected_verification.shared_gate_success):
                    action_count = step_index + 1
                    actions.extend(segment_actions[:action_count])
                    executed_distance_m += float(
                        getattr(observation, "cumulative_distance_m", 0.0) or 0.0
                    )
                    current_position = selected_position
                    current_rotation = (
                        _tuple4(getattr(observation, "rotation", None))
                        or current_rotation
                    )
                    reached_stop = reached_stop and bool(
                        getattr(segment, "reached_stop", False)
                    )
                    break
            if (
                selected_verification is not None
                and bool(selected_verification.shared_gate_success)
            ):
                break
        actions.extend(segment_actions)
        executed_distance_m += float(getattr(segment, "executed_distance_m", 0.0) or 0.0)
        reached_stop = reached_stop and bool(getattr(segment, "reached_stop", False))
        current_position = _tuple3(getattr(segment, "final_position", None)) or goal
        current_rotation = (
            _tuple4(getattr(segment, "final_rotation", None)) or current_rotation
        )
        for heading_index, heading_rotation in enumerate(
            _probe_heading_rotations(
                base_rotation=current_rotation,
                heading_count=probe_heading_count,
            )
        ):
            if heading_index > 0:
                actions.append(f"scan_heading:{probe_index}:{heading_index}")
            selected_source = (
                f"{source_prefix}:{probe_index}:heading:{heading_index}"
            )
            verification_count += 1
            selected_verification = verify_probe(
                source=selected_source,
                position=current_position,
                rotation=heading_rotation,
                probe_index=probe_index,
            )
            selected_position = current_position
            current_rotation = heading_rotation
            if bool(selected_verification.shared_gate_success):
                break
        if (
            selected_verification is not None
            and bool(selected_verification.shared_gate_success)
        ):
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
            observations=tuple(),
        ),
        selected_probe_source=selected_source,
        selected_probe_position=selected_position,
        selected_verification=selected_verification,
        verification_count=verification_count,
    )


def _memory_local_active_result(
    *,
    sim: Any,
    start_position: Sequence[float],
    start_rotation: Sequence[float],
    memory_anchor: Sequence[float],
    seed: int,
    radii_m: Sequence[float],
    probe_count: int,
    angle_count: int,
    score_mode: str,
    route_segment: Any,
    verify_probe: Any,
    route_error_types: tuple[type[BaseException], ...] = (),
    probe_heading_count: int = DEFAULT_LOCAL_SEARCH_HEADING_COUNT,
    route_observation_mode: str = DEFAULT_ROUTE_OBSERVATION_MODE,
) -> NavmeshFrontierRouteResult:
    candidates = _memory_local_probe_goals(
        sim=sim,
        memory_anchor=memory_anchor,
        start=start_position,
        seed=seed,
        radii_m=radii_m,
        probe_count=probe_count,
        angle_count=angle_count,
        score_mode=score_mode,
    )
    return _run_navmesh_frontier_probe_route(
        start_position=start_position,
        start_rotation=start_rotation,
        probe_goals=tuple(candidate.position for candidate in candidates),
        route_segment=route_segment,
        verify_probe=verify_probe,
        route_error_types=route_error_types,
        probe_heading_count=probe_heading_count,
        route_observation_mode=route_observation_mode,
        source_prefix="memory_local_active_probe",
    )


def _habitat_probe_route_result(
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
    detector_confirmation_mode: str,
    detector_confirmation: DetectorConfirmationConfig,
    helpers: dict[str, Any],
    detector_confirmation_events: list[dict[str, Any]] | None = None,
    detector_confirmation_context: str = "",
    start_position: Sequence[float],
    start_rotation: Sequence[float],
    probe_goals: Sequence[Sequence[float]],
    probe_heading_count: int,
    route_observation_mode: str,
    frame_index_base: int,
    source_prefix: str = "navmesh_frontier_probe",
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

    confirmation_state = DetectorConfirmationState()

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
        if detector == "oracle_semantic_visibility":
            return _verify_oracle_pose(
                sim=sim,
                position=position,
                rotation=rotation,
                target_semantic_ids=target_semantic_ids,
                min_target_pixels=min_target_pixels,
            )
        verification = _verify_lifecycle_view(
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
        return _apply_detector_confirmation(
            verification=verification,
            state=confirmation_state,
            mode=detector_confirmation_mode,
            pose=(position, rotation),
            detector_mask=getattr(verification, "detector_mask", None)
            if getattr(verification, "detector_mask", None) is not None
            else np.zeros((1, 1), dtype=bool),
            config=detector_confirmation,
            events=detector_confirmation_events,
            source=source,
            context=detector_confirmation_context,
        )

    return _run_navmesh_frontier_probe_route(
        start_position=start_position,
        start_rotation=start_rotation,
        probe_goals=probe_goals,
        route_segment=route_segment,
        verify_probe=verify_probe,
        route_error_types=(GreedyFollowerError,),
        probe_heading_count=probe_heading_count,
        route_observation_mode=route_observation_mode,
        source_prefix=source_prefix,
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
    detector_confirmation_mode: str,
    detector_confirmation: DetectorConfirmationConfig,
    helpers: dict[str, Any],
    detector_confirmation_events: list[dict[str, Any]] | None = None,
    detector_confirmation_context: str = "",
    start_position: Sequence[float],
    start_rotation: Sequence[float],
    seed: int,
    probe_count: int,
    probe_heading_count: int,
    route_observation_mode: str,
    frame_index_base: int,
) -> NavmeshFrontierRouteResult:
    probe_goals = _navmesh_frontier_probe_goals(
        sim=sim,
        start=start_position,
        seed=seed,
        probe_count=probe_count,
    )
    return _habitat_probe_route_result(
        habitat_sim=habitat_sim,
        sim=sim,
        target_semantic_ids=target_semantic_ids,
        target_category=target_category,
        detector=detector,
        detector_adapter=detector_adapter,
        accepted_detection_labels=accepted_detection_labels,
        noise_level=noise_level,
        rgb_noise=rgb_noise,
        depth_noise=depth_noise,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
        max_detection_area_ratio=max_detection_area_ratio,
        detector_confirmation_mode=detector_confirmation_mode,
        detector_confirmation=detector_confirmation,
        helpers=helpers,
        detector_confirmation_events=detector_confirmation_events,
        detector_confirmation_context=detector_confirmation_context,
        start_position=start_position,
        start_rotation=start_rotation,
        probe_goals=probe_goals,
        probe_heading_count=probe_heading_count,
        route_observation_mode=route_observation_mode,
        frame_index_base=frame_index_base,
    )


def _habitat_memory_local_active_result(
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
    detector_confirmation_mode: str,
    detector_confirmation: DetectorConfirmationConfig,
    helpers: dict[str, Any],
    detector_confirmation_events: list[dict[str, Any]] | None = None,
    detector_confirmation_context: str = "",
    start_position: Sequence[float],
    start_rotation: Sequence[float],
    memory_anchor: Sequence[float],
    seed: int,
    radii_m: Sequence[float],
    probe_count: int,
    angle_count: int,
    score_mode: str,
    probe_heading_count: int,
    route_observation_mode: str,
    frame_index_base: int,
) -> NavmeshFrontierRouteResult:
    candidates = _memory_local_probe_goals(
        sim=sim,
        memory_anchor=memory_anchor,
        start=start_position,
        seed=seed,
        radii_m=radii_m,
        probe_count=probe_count,
        angle_count=angle_count,
        score_mode=score_mode,
    )
    return _habitat_probe_route_result(
        habitat_sim=habitat_sim,
        sim=sim,
        target_semantic_ids=target_semantic_ids,
        target_category=target_category,
        detector=detector,
        detector_adapter=detector_adapter,
        accepted_detection_labels=accepted_detection_labels,
        noise_level=noise_level,
        rgb_noise=rgb_noise,
        depth_noise=depth_noise,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
        max_detection_area_ratio=max_detection_area_ratio,
        detector_confirmation_mode=detector_confirmation_mode,
        detector_confirmation=detector_confirmation,
        helpers=helpers,
        detector_confirmation_events=detector_confirmation_events,
        detector_confirmation_context=detector_confirmation_context,
        start_position=start_position,
        start_rotation=start_rotation,
        probe_goals=tuple(candidate.position for candidate in candidates),
        probe_heading_count=probe_heading_count,
        route_observation_mode=route_observation_mode,
        frame_index_base=frame_index_base,
        source_prefix="memory_local_active_probe",
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


def _probe_heading_rotations(
    *,
    base_rotation: tuple[float, float, float, float],
    heading_count: int,
) -> tuple[tuple[float, float, float, float], ...]:
    if heading_count <= 0:
        raise ValueError("heading_count must be positive")
    base = _normalize_quaternion_xyzw(base_rotation)
    rotations: list[tuple[float, float, float, float]] = []
    for index in range(heading_count):
        yaw = 2.0 * np.pi * float(index) / float(heading_count)
        half_yaw = yaw / 2.0
        rotations.append(
            _multiply_quaternion_xyzw(
                base,
                _normalize_quaternion_xyzw(
                    (0.0, float(np.sin(half_yaw)), 0.0, float(np.cos(half_yaw)))
                ),
            )
        )
    return tuple(rotations)


def _multiply_quaternion_xyzw(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    x1, y1, z1, w1 = first
    x2, y2, z2, w2 = second
    return _normalize_quaternion_xyzw(
        (
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        )
    )


def _normalize_quaternion_xyzw(
    rotation: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    norm = float(np.sqrt(sum(value * value for value in rotation)))
    if norm == 0.0:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(float(value / norm) for value in rotation)  # type: ignore[return-value]


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
    payload = {
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
    detector_confirmation = getattr(verification, "detector_confirmation", None)
    if detector_confirmation is not None:
        payload["detector_confirmation"] = dict(detector_confirmation)
    return payload


def _audit_evidence_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    enriched = dict(payload)
    is_detector_positive = (
        bool(enriched.get("shared_gate_success", False))
        and _is_detector_evidence_reason(str(enriched.get("evidence_reason", "")))
    )
    overlap_pixels = int(enriched.get("overlap_pixels", 0) or 0)
    detector_precision = float(enriched.get("detector_precision", 0.0) or 0.0)
    detector_overlap_success = is_detector_positive and (
        overlap_pixels > 0 or detector_precision > 0.0
    )
    enriched["detector_overlap_success"] = detector_overlap_success
    enriched["detector_false_confirmation"] = (
        is_detector_positive and not detector_overlap_success
    )
    return enriched


def _is_detector_evidence_reason(reason: str) -> bool:
    return reason.startswith("detector_") or reason.startswith("confirmed_detector_")


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


def _quaternion_angle_degrees(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    first_norm = _normalize_quaternion_xyzw(first)
    second_norm = _normalize_quaternion_xyzw(second)
    dot = abs(sum(left * right for left, right in zip(first_norm, second_norm)))
    dot = min(1.0, max(-1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


def _mask_iou(first: np.ndarray, second: np.ndarray) -> float:
    lhs = np.asarray(first, dtype=bool)
    rhs = np.asarray(second, dtype=bool)
    union = int((lhs | rhs).sum())
    if union == 0:
        return 0.0
    return float((lhs & rhs).sum() / union)


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
    observations: tuple[Any, ...] = ()

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
            "memory_decision_buckets": _count_memory_decision_buckets(policy_rows),
            "detector_false_confirmation_counts": (
                _count_detector_false_confirmations(policy_rows)
            ),
            "detector_confirmation_counts": (
                _count_detector_confirmation_outcomes(policy_rows)
            ),
            "detector_confirmation_event_counts": (
                _count_detector_confirmation_events(policy_rows)
            ),
            "detector_confirmation_event_counts_by_context": (
                _count_detector_confirmation_events_by_context(policy_rows)
            ),
            "total_hindsight_action_regret": sum(
                int(row.get("hindsight_action_regret", 0) or 0)
                for row in policy_rows
            ),
            "mean_hindsight_action_regret": round(
                _safe_div(
                    float(
                        sum(
                            int(row.get("hindsight_action_regret", 0) or 0)
                            for row in policy_rows
                        )
                    ),
                    len(policy_rows),
                ),
                6,
            ),
            "total_hindsight_distance_regret_m": round(
                sum(
                    float(row.get("hindsight_distance_regret_m", 0.0) or 0.0)
                    for row in policy_rows
                ),
                6,
            ),
        }
    return summaries


def _count_memory_decision_buckets(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        bucket = str(row.get("memory_decision_bucket", "unknown"))
        counts[bucket] = counts.get(bucket, 0) + 1
    return dict(sorted(counts.items()))


def _count_detector_false_confirmations(
    rows: Sequence[dict[str, Any]],
) -> dict[str, int]:
    fields = {
        "memory": "memory_evidence",
        "fallback": "fallback_evidence",
        "fallback_from_memory": "fallback_from_memory_evidence",
    }
    counts: dict[str, int] = {}
    for label, field in fields.items():
        count = sum(
            int(
                bool(
                    (row.get(field) or {}).get(
                        "detector_false_confirmation",
                        False,
                    )
                )
            )
            for row in rows
        )
        if count:
            counts[label] = count
    return dict(sorted(counts.items()))


def _count_detector_confirmation_outcomes(
    rows: Sequence[dict[str, Any]],
) -> dict[str, int]:
    fields = (
        "memory_evidence",
        "fallback_evidence",
        "fallback_from_memory_evidence",
    )
    counts = {"confirmed": 0, "suppressed": 0}
    for row in rows:
        for field in fields:
            confirmation = (row.get(field) or {}).get("detector_confirmation")
            if not isinstance(confirmation, dict):
                continue
            if bool(confirmation.get("confirmed", False)):
                counts["confirmed"] += 1
            else:
                counts["suppressed"] += 1
    return {key: value for key, value in counts.items() if value}


def _count_detector_confirmation_events(
    rows: Sequence[dict[str, Any]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        for event in _row_detector_confirmation_events(row):
            outcome = str(event.get("outcome", "unknown"))
            counts[outcome] = counts.get(outcome, 0) + 1
    return dict(sorted(counts.items()))


def _count_detector_confirmation_events_by_context(
    rows: Sequence[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        for event in _row_detector_confirmation_events(row):
            context = str(event.get("context", "unknown"))
            outcome = str(event.get("outcome", "unknown"))
            context_counts = counts.setdefault(context, {})
            context_counts[outcome] = context_counts.get(outcome, 0) + 1
    return {
        context: dict(sorted(context_counts.items()))
        for context, context_counts in sorted(counts.items())
    }


def _row_detector_confirmation_events(
    row: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    events = row.get("detector_confirmation_events") or ()
    return tuple(event for event in events if isinstance(event, dict))


def _safe_div(numerator: float, denominator: int | float) -> float:
    return 0.0 if float(denominator) == 0.0 else float(numerator) / float(denominator)


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
