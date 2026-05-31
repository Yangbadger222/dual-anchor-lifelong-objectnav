from __future__ import annotations

import csv
import json
import random
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_official_candidate_viewpoint_ranker_model import (
    predict_official_candidate_viewpoint_ranker,
)
from objectnav_core.evaluation.habitat_official_local_action_model import (
    score_official_local_action_candidates,
)
from objectnav_core.models import NavigationStatus, Pose2D
from objectnav_core.navigation import (
    HabitatOracleFollowerBackend,
    NavigationBackendStatus,
    NavigationGoal,
)


OFFICIAL_OBJECTNAV_MEASURE_KEYS: tuple[str, ...] = (
    "success",
    "spl",
    "soft_spl",
    "distance_to_goal",
)
OPTIONAL_OBJECTNAV_MEASURE_KEYS: tuple[str, ...] = ("distance_to_goal_reward",)
SUPPORTED_OFFICIAL_POLICIES: tuple[str, ...] = (
    "noop",
    "random",
    "frontier_only",
    "occupancy_frontier",
    "memory_guided_frontier",
    "memory_belief_frontier",
    "memory_evidence_frontier",
    "memory_active_perception_frontier",
    "memory_active_perception_frontier_pathfinder_suffix",
    "no_memory_targetnav",
    "naive_count_targetnav",
    "memory_active_perception_frontier_targetnav",
    "memory_active_perception_frontier_targetnav_fmm",
    "memory_active_perception_frontier_targetnav_ddppo",
    "memory_learned_local_frontier",
)
SUPPORTED_TARGETNAV_BACKENDS: tuple[str, ...] = (
    "occupancy_grid",
    "fmm_grid",
    "ddppo_pointnav",
    "oracle_follower",
)
METRIC_SOURCE = "habitat.Env.get_metrics"
FRONTIER_CLEAR_DEPTH_M = 1.0
FRONTIER_CLEAR_DEPTH_NORMALIZED = 0.75
FRONTIER_CLEAR_FRACTION = 0.6
OCCUPANCY_BLOCKED_TURN_BURST_STEPS = 4
OCCUPANCY_UNKNOWN = -1
OCCUPANCY_FREE = 0
OCCUPANCY_OCCUPIED = 1
ACTIVE_PERCEPTION_SCAN_STEPS = 4
DETECTOR_CENTER_TOLERANCE_FRACTION = 0.15
DETECTOR_STOP_MIN_BBOX_AREA_FRACTION = 0.04
DETECTOR_STOP_MAX_DEPTH_M = 1.0
DETECTOR_STOP_MAX_DEPTH_NORMALIZED = 0.18
LOCAL_ACTION_HISTORY_STEPS = 3
TARGETNAV_GOAL_SMOOTHING_ALPHA = 0.5
TARGETNAV_MIN_MEASUREMENT_VARIANCE_M2 = 0.05
TARGETNAV_MAX_RANGE_VARIANCE_M2 = 36.0


@dataclass(frozen=True)
class OfficialObjectNavRunConfig:
    config_path: str
    dataset_data_path: str
    scene_root: str
    split: str = "val_mini"
    policy: str = "noop"
    max_episodes: int | None = 1
    max_steps: int = 500
    seed: int = 313
    validate_habitat: bool = False
    memory_prior_path: str | None = None
    memory_stop_radius_m: float = 0.35
    memory_bearing_tolerance_deg: float = 20.0
    memory_min_confidence: float = 0.0
    detector_center_direction_sign: int = 1
    local_action_model_path: str | None = None
    candidate_viewpoint_ranker_model_path: str | None = None
    pathfinder_suffix_goal_radius_m: float = 1.0
    targetnav_backend: str = "occupancy_grid"
    targetnav_ddppo_checkpoint_path: str | None = None
    targetnav_ddppo_device: str = "auto"


@dataclass(frozen=True)
class OfficialMemoryAnchor:
    object_category: str
    x_m: float
    z_m: float
    y_m: float | None = None
    scene_id: str | None = None
    episode_id: str | None = None
    confidence: float = 1.0
    source: str = "unknown"
    coordinate_frame: str = "episode_start_relative"


def load_official_memory_prior(path: str | Path) -> tuple[OfficialMemoryAnchor, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return load_official_memory_prior_from_payload(payload)


def load_official_memory_prior_from_payload(
    payload: Mapping[str, Any],
) -> tuple[OfficialMemoryAnchor, ...]:
    raw_anchors = payload.get("anchors")
    if not isinstance(raw_anchors, list):
        raise ValueError("memory prior must contain an anchors list")
    return tuple(
        _memory_anchor_from_payload(raw_anchor, index=index)
        for index, raw_anchor in enumerate(raw_anchors)
    )


def select_official_memory_anchor(
    anchors: Sequence[OfficialMemoryAnchor],
    *,
    object_category: str,
    scene_id: str,
    episode_id: str | None = None,
    min_confidence: float = 0.0,
    allowed_coordinate_frames: tuple[str, ...] = ("episode_start_relative",),
) -> OfficialMemoryAnchor | None:
    candidates = [
        anchor
        for anchor in anchors
        if anchor.object_category == object_category
        and anchor.confidence >= min_confidence
        and anchor.coordinate_frame in allowed_coordinate_frames
        and _memory_anchor_scene_matches(anchor.scene_id, scene_id)
        and _memory_anchor_episode_matches(anchor.episode_id, episode_id)
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda anchor: (
            _memory_anchor_episode_exact_match(anchor.episode_id, episode_id),
            anchor.confidence,
        ),
    )


def load_official_local_action_model(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("local action model must be a JSON object")
    if payload.get("task") != "habitat_official_local_action_logistic_model":
        raise ValueError("local action model has unsupported task")
    if not isinstance(payload.get("feature_names"), list):
        raise ValueError("local action model must contain feature_names")
    return payload


def load_official_candidate_viewpoint_ranker_model(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("candidate viewpoint ranker model must be a JSON object")
    if payload.get("task") != "habitat_official_candidate_viewpoint_ranker_model":
        raise ValueError("candidate viewpoint ranker model has unsupported task")
    if not isinstance(payload.get("feature_names"), list):
        raise ValueError("candidate viewpoint ranker model must contain feature_names")
    return payload


def run_habitat_official_objectnav_preflight(
    output_dir: str | Path,
    *,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    policy: str = "noop",
    max_episodes: int | None = 1,
    max_steps: int = 500,
    seed: int = 313,
    validate_habitat: bool = False,
    memory_prior_path: str | Path | None = None,
    memory_stop_radius_m: float = 0.35,
    memory_bearing_tolerance_deg: float = 20.0,
    memory_min_confidence: float = 0.0,
    pathfinder_suffix_goal_radius_m: float = 1.0,
    detector_center_direction_sign: int = 1,
    local_action_model_path: str | Path | None = None,
    candidate_viewpoint_ranker_model_path: str | Path | None = None,
    targetnav_ddppo_checkpoint_path: str | Path | None = None,
    targetnav_backend: str = "occupancy_grid",
    targetnav_ddppo_device: str = "auto",
) -> dict[str, Any]:
    config = OfficialObjectNavRunConfig(
        config_path=str(config_path),
        dataset_data_path=str(dataset_data_path),
        scene_root=str(scene_root),
        split=split,
        policy=policy,
        max_episodes=max_episodes,
        max_steps=max_steps,
        seed=seed,
        validate_habitat=validate_habitat,
        memory_prior_path=str(memory_prior_path) if memory_prior_path else None,
        memory_stop_radius_m=memory_stop_radius_m,
        memory_bearing_tolerance_deg=memory_bearing_tolerance_deg,
        memory_min_confidence=memory_min_confidence,
        pathfinder_suffix_goal_radius_m=pathfinder_suffix_goal_radius_m,
        detector_center_direction_sign=detector_center_direction_sign,
        local_action_model_path=(
            str(local_action_model_path) if local_action_model_path else None
        ),
        candidate_viewpoint_ranker_model_path=(
            str(candidate_viewpoint_ranker_model_path)
            if candidate_viewpoint_ranker_model_path
            else None
        ),
        targetnav_backend=targetnav_backend,
        targetnav_ddppo_checkpoint_path=(
            str(targetnav_ddppo_checkpoint_path)
            if targetnav_ddppo_checkpoint_path
            else None
        ),
        targetnav_ddppo_device=targetnav_ddppo_device,
    )
    _validate_run_config(config)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    habitat_metadata = (
        _load_habitat_metadata(config) if validate_habitat else {"validated": False}
    )
    manifest = make_protocol_manifest(config, habitat_metadata=habitat_metadata)
    summary = {
        "task": "habitat_official_objectnav_preflight",
        "full_habitat_run": False,
        "policy": policy,
        "config": asdict(config),
        "official_metrics": None,
        "protocol_manifest": manifest,
        "artifact_files": {
            "summary": "summary.json",
            "protocol_manifest": "protocol_manifest.json",
        },
        "notes": [
            "Official metrics must come from habitat.Env.get_metrics.",
            "Preflight and trivial-policy smoke runs are not benchmark claims.",
        ],
    }
    write_json(output_path / "protocol_manifest.json", manifest)
    write_json(output_path / "summary.json", summary)
    return summary


def run_habitat_official_objectnav_eval(
    output_dir: str | Path,
    *,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    policy: str = "noop",
    max_episodes: int | None = 1,
    max_steps: int = 500,
    seed: int = 313,
    validate_habitat: bool = True,
    memory_prior_path: str | Path | None = None,
    memory_stop_radius_m: float = 0.35,
    memory_bearing_tolerance_deg: float = 20.0,
    memory_min_confidence: float = 0.0,
    env_factory: Callable[[OfficialObjectNavRunConfig], Any] | None = None,
    target_detector_adapter: Any | None = None,
    target_detector_min_confidence: float = 0.0,
    pathfinder_suffix_goal_radius_m: float = 1.0,
    detector_center_direction_sign: int = 1,
    local_action_model_path: str | Path | None = None,
    candidate_viewpoint_ranker_model_path: str | Path | None = None,
    targetnav_ddppo_checkpoint_path: str | Path | None = None,
    targetnav_backend: str = "occupancy_grid",
    targetnav_ddppo_device: str = "auto",
    targetnav_ddppo_backend: Any | None = None,
    write_detector_trace: bool = True,
    write_policy_trace: bool = True,
) -> dict[str, Any]:
    config = OfficialObjectNavRunConfig(
        config_path=str(config_path),
        dataset_data_path=str(dataset_data_path),
        scene_root=str(scene_root),
        split=split,
        policy=policy,
        max_episodes=max_episodes,
        max_steps=max_steps,
        seed=seed,
        validate_habitat=validate_habitat,
        memory_prior_path=str(memory_prior_path) if memory_prior_path else None,
        memory_stop_radius_m=memory_stop_radius_m,
        memory_bearing_tolerance_deg=memory_bearing_tolerance_deg,
        memory_min_confidence=memory_min_confidence,
        pathfinder_suffix_goal_radius_m=pathfinder_suffix_goal_radius_m,
        detector_center_direction_sign=detector_center_direction_sign,
        local_action_model_path=(
            str(local_action_model_path) if local_action_model_path else None
        ),
        candidate_viewpoint_ranker_model_path=(
            str(candidate_viewpoint_ranker_model_path)
            if candidate_viewpoint_ranker_model_path
            else None
        ),
        targetnav_backend=targetnav_backend,
        targetnav_ddppo_checkpoint_path=(
            str(targetnav_ddppo_checkpoint_path)
            if targetnav_ddppo_checkpoint_path
            else None
        ),
        targetnav_ddppo_device=targetnav_ddppo_device,
    )
    _validate_run_config(config)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    factory = env_factory or _make_habitat_env
    env = factory(config)
    local_action_model = (
        load_official_local_action_model(config.local_action_model_path)
        if config.local_action_model_path
        else None
    )
    candidate_viewpoint_ranker_model = (
        load_official_candidate_viewpoint_ranker_model(
            config.candidate_viewpoint_ranker_model_path
        )
        if config.candidate_viewpoint_ranker_model_path
        else None
    )
    ddppo_backend = (
        targetnav_ddppo_backend
        if targetnav_ddppo_backend is not None
        else _load_targetnav_ddppo_backend(config)
        if config.policy == "memory_active_perception_frontier_targetnav_ddppo"
        or (
            config.policy
            in {
                "no_memory_targetnav",
                "naive_count_targetnav",
                "memory_active_perception_frontier_targetnav",
            }
            and config.targetnav_backend == "ddppo_pointnav"
        )
        else None
    )
    detector_trace = (
        OfficialDetectorTrace()
        if target_detector_adapter is not None and write_detector_trace
        else None
    )
    policy_trace: list[dict[str, Any]] | None = [] if write_policy_trace else None
    try:
        pathfinder_suffix_controller_factory = (
            lambda episode_env: OfficialPathfinderSuffixController(
                episode_env,
                goal_radius_m=config.pathfinder_suffix_goal_radius_m,
            )
            if config.policy == "memory_active_perception_frontier_pathfinder_suffix"
            or (
                config.policy
                in {
                    "no_memory_targetnav",
                    "naive_count_targetnav",
                    "memory_active_perception_frontier_targetnav",
                }
                and config.targetnav_backend == "oracle_follower"
            )
            else None
        )
        rows = run_official_objectnav_episode_loop(
            env,
            policy=config.policy,
            max_episodes=config.max_episodes,
            max_steps=config.max_steps,
            seed=config.seed,
            memory_anchors=(
                load_official_memory_prior(config.memory_prior_path)
                if config.memory_prior_path
                else ()
            ),
            memory_stop_radius_m=config.memory_stop_radius_m,
            memory_bearing_tolerance_deg=config.memory_bearing_tolerance_deg,
            memory_min_confidence=config.memory_min_confidence,
            target_detector_adapter=target_detector_adapter,
            target_detector_min_confidence=target_detector_min_confidence,
            detector_center_direction_sign=config.detector_center_direction_sign,
            local_action_model=local_action_model,
            candidate_viewpoint_ranker_model=candidate_viewpoint_ranker_model,
            targetnav_backend=config.targetnav_backend,
            targetnav_ddppo_backend=ddppo_backend,
            detector_trace=detector_trace,
            policy_trace=policy_trace,
            pathfinder_suffix_controller_factory=pathfinder_suffix_controller_factory,
        )
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    habitat_metadata = (
        _load_habitat_metadata(config) if validate_habitat else {"validated": False}
    )
    manifest = make_protocol_manifest(config, habitat_metadata=habitat_metadata)
    official_metrics = summarize_official_objectnav_metrics(rows)
    summary = {
        "task": "habitat_official_objectnav_eval",
        "full_habitat_run": True,
        "policy": policy,
        "config": asdict(config),
        "protocol_manifest": manifest,
        "official_metrics": official_metrics,
        "episodes": rows,
        "artifact_files": {
            "summary": "summary.json",
            "protocol_manifest": "protocol_manifest.json",
            "episodes": "episodes.csv",
        },
        "notes": [
            "Success, SPL, SoftSPL, and distance-to-goal are copied from Habitat-Lab metrics.",
            "The noop/random policies are protocol smokes, not competitive baselines.",
        ],
    }
    if detector_trace is not None:
        write_json(output_path / "detector_trace.json", detector_trace.payload())
        summary["artifact_files"]["detector_trace"] = "detector_trace.json"
        summary["detector_trace"] = detector_trace.summary()
        summary["notes"].append(
            "Detector traces are diagnostic only and are not official Habitat metrics."
        )
    if policy_trace is not None:
        write_json(output_path / "policy_trace.json", _policy_trace_payload(policy_trace))
        summary["artifact_files"]["policy_trace"] = "policy_trace.json"
        summary["policy_trace"] = _policy_trace_summary(policy_trace)
        summary["notes"].append(
            "Policy traces are diagnostic only and are not official Habitat metrics."
        )
    write_json(output_path / "protocol_manifest.json", manifest)
    write_json(output_path / "summary.json", summary)
    write_csv(output_path / "episodes.csv", rows)
    return summary


def run_official_objectnav_episode_loop(
    env: Any,
    *,
    policy: str,
    max_episodes: int | None,
    max_steps: int,
    seed: int = 313,
    memory_anchors: Sequence[OfficialMemoryAnchor] = (),
    memory_stop_radius_m: float = 0.35,
    memory_bearing_tolerance_deg: float = 20.0,
    memory_min_confidence: float = 0.0,
    target_detector_adapter: Any | None = None,
    target_detector_min_confidence: float = 0.0,
    detector_center_direction_sign: int = 1,
    local_action_model: Mapping[str, Any] | None = None,
    candidate_viewpoint_ranker_model: Mapping[str, Any] | None = None,
    targetnav_backend: str = "occupancy_grid",
    targetnav_ddppo_backend: Any | None = None,
    detector_trace: "OfficialDetectorTrace | None" = None,
    policy_trace: list[dict[str, Any]] | None = None,
    pathfinder_suffix_controller_factory: Callable[[Any], Any] | None = None,
) -> list[dict[str, Any]]:
    if policy not in SUPPORTED_OFFICIAL_POLICIES:
        raise ValueError(f"Unsupported official ObjectNav policy: {policy}")
    if max_episodes is not None and max_episodes <= 0:
        raise ValueError("max_episodes must be positive when provided")
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    if target_detector_min_confidence < 0.0:
        raise ValueError("target_detector_min_confidence must be non-negative")
    if detector_center_direction_sign not in {-1, 1}:
        raise ValueError("detector_center_direction_sign must be -1 or 1")
    if targetnav_backend not in SUPPORTED_TARGETNAV_BACKENDS:
        raise ValueError(
            "targetnav_backend must be one of: "
            f"{', '.join(SUPPORTED_TARGETNAV_BACKENDS)}"
        )

    episode_limit = max_episodes or _env_episode_count(env)
    rows: list[dict[str, Any]] = []
    for episode_index in range(episode_limit):
        observation = env.reset()
        _reset_targetnav_ddppo_backend(targetnav_ddppo_backend)
        episode = getattr(env, "current_episode", None)
        state = OfficialPolicyState(
            rng=random.Random(seed + episode_index),
            episode_index=episode_index,
            episode_id=str(
                getattr(episode, "episode_id", f"episode-{episode_index}")
            ),
            object_category=str(getattr(episode, "object_category", "")),
            scene_id=str(getattr(episode, "scene_id", "")),
            episode_start_position=_tuple3_position(
                getattr(episode, "start_position", None)
            ),
            episode_start_rotation=_tuple4_values(
                getattr(episode, "start_rotation", None)
            ),
            memory_anchors=tuple(memory_anchors),
            memory_stop_radius_m=memory_stop_radius_m,
            memory_bearing_tolerance_rad=float(
                np.deg2rad(memory_bearing_tolerance_deg)
            ),
            memory_min_confidence=memory_min_confidence,
            target_detector_adapter=target_detector_adapter,
            target_detector_min_confidence=target_detector_min_confidence,
            detector_center_direction_sign=detector_center_direction_sign,
            local_action_model=local_action_model,
            candidate_viewpoint_ranker_model=candidate_viewpoint_ranker_model,
            targetnav_backend=targetnav_backend,
            targetnav_ddppo_backend=targetnav_ddppo_backend,
            detector_trace=detector_trace,
            pathfinder_suffix_controller=(
                pathfinder_suffix_controller_factory(env)
                if pathfinder_suffix_controller_factory is not None
                else None
            ),
        )
        actions: list[str] = []
        for step_index in range(max_steps):
            if bool(getattr(env, "episode_over", False)):
                break
            action = _select_policy_action(
                policy,
                observation=observation,
                step_index=step_index,
                max_steps=max_steps,
                state=state,
            )
            actions.append(action)
            _record_policy_trace_step(
                policy_trace,
                policy=policy,
                observation=observation,
                step_index=step_index,
                max_steps=max_steps,
                action=action,
                state=state,
            )
            _record_local_action_history(
                state,
                observation=observation,
                step_index=step_index,
                action=action,
            )
            observation = env.step(action)
            if bool(getattr(env, "episode_over", False)):
                break
        metrics = _official_metrics_from_env(env)
        rows.append(
            {
                "episode_index": episode_index,
                "episode_id": str(
                    getattr(episode, "episode_id", f"episode-{episode_index}")
                ),
                "scene_id": str(getattr(episode, "scene_id", "")),
                "object_category": str(getattr(episode, "object_category", "")),
                "habitat_official": metrics,
                "policy_debug": {
                    "policy": policy,
                    "policy_kind": _policy_kind(policy),
                    "actions": actions,
                    "action_count": len(actions),
                    "metric_source": METRIC_SOURCE,
                    **_policy_debug_payload(state),
                },
            }
        )
    return rows


@dataclass
class OfficialPolicyState:
    rng: random.Random
    episode_index: int = 0
    episode_id: str = ""
    object_category: str = ""
    scene_id: str = ""
    episode_start_position: tuple[float, float, float] | None = None
    episode_start_rotation: tuple[float, float, float, float] | None = None
    memory_anchors: tuple[OfficialMemoryAnchor, ...] = ()
    memory_stop_radius_m: float = 0.35
    memory_bearing_tolerance_rad: float = float(np.deg2rad(20.0))
    memory_min_confidence: float = 0.0
    target_detector_adapter: Any | None = None
    target_detector_min_confidence: float = 0.0
    detector_center_direction_sign: int = 1
    local_action_model: Mapping[str, Any] | None = None
    candidate_viewpoint_ranker_model: Mapping[str, Any] | None = None
    targetnav_backend: str = "occupancy_grid"
    targetnav_ddppo_backend: Any | None = None
    detector_trace: "OfficialDetectorTrace | None" = None
    blocked_turn_count: int = 0
    blocked_turn_action: str = "turn_left"
    occupancy_map: OccupancyFrontierMap | None = None
    selected_frontier_bearing_rad: float | None = None
    memory_debug: dict[str, Any] | None = None
    detector_center_direction_sign: int = 1
    last_detector_center_step: int | None = None
    last_detector_center_action: str | None = None
    last_detector_center_offset_fraction: float | None = None
    last_detector_center_offset_sign: int | None = None
    failed_detector_center_effects: set[tuple[str, int]] = field(default_factory=set)
    local_action_history: list[tuple[dict[str, Any], dict[str, Any]]] = field(
        default_factory=list
    )
    active_perception_scan_steps_remaining: int = 0
    active_perception_scanned_viewpoint_cell: tuple[int, int] | None = None
    active_perception_target_viewpoint_cell: tuple[int, int] | None = None
    active_perception_blocked_scan_viewpoint_cell: tuple[int, int] | None = None
    pathfinder_suffix_controller: Any | None = None
    pathfinder_suffix_active: bool = False
    pathfinder_suffix_activation_step: int | None = None
    pathfinder_suffix_goal_position: tuple[float, float, float] | None = None
    pathfinder_suffix_debug: dict[str, Any] | None = None
    targetnav_goal: dict[str, Any] | None = None
    targetnav_debug: dict[str, Any] | None = None


@dataclass
class OfficialDetectorTrace:
    calls: list[dict[str, Any]] = field(default_factory=list)

    def record_missing_rgb(
        self,
        *,
        episode_index: int,
        episode_id: str,
        scene_id: str,
        target_category: str,
        step_index: int,
    ) -> None:
        self.calls.append(
            {
                "call_index": len(self.calls),
                "episode_index": episode_index,
                "episode_id": episode_id,
                "scene_id": scene_id,
                "target_category": target_category,
                "step_index": step_index,
                "missing_rgb": True,
                "detection_count": 0,
                "target_match_count": 0,
                "detections": [],
            }
        )

    def record_detections(
        self,
        *,
        episode_index: int,
        episode_id: str,
        scene_id: str,
        target_category: str,
        step_index: int,
        detections: Sequence[Mapping[str, Any]],
        target_match_count: int,
    ) -> None:
        detection_payloads = [dict(detection) for detection in detections]
        self.calls.append(
            {
                "call_index": len(self.calls),
                "episode_index": episode_index,
                "episode_id": episode_id,
                "scene_id": scene_id,
                "target_category": target_category,
                "step_index": step_index,
                "missing_rgb": False,
                "detection_count": len(detection_payloads),
                "target_match_count": int(target_match_count),
                "detections": detection_payloads,
            }
        )

    def summary(self) -> dict[str, int]:
        return {
            "call_count": len(self.calls),
            "missing_rgb_count": sum(
                1 for call in self.calls if bool(call.get("missing_rgb"))
            ),
            "detection_count": sum(
                int(call.get("detection_count", 0)) for call in self.calls
            ),
            "target_match_call_count": sum(
                1 for call in self.calls if int(call.get("target_match_count", 0)) > 0
            ),
            "target_match_detection_count": sum(
                int(call.get("target_match_count", 0)) for call in self.calls
            ),
        }

    def payload(self) -> dict[str, Any]:
        return {
            "task": "official_query_detector_trace",
            **self.summary(),
            "calls": list(self.calls),
        }


class OfficialPathfinderSuffixController:
    def __init__(
        self,
        env: Any,
        *,
        goal_radius_m: float = 1.0,
        backend_factory: Callable[..., Any] | None = None,
    ) -> None:
        if goal_radius_m <= 0.0:
            raise ValueError("goal_radius_m must be positive")
        self.env = env
        self.goal_radius_m = float(goal_radius_m)
        self._backend = (
            backend_factory or _make_habitat_oracle_follower_backend
        )(
            env,
            goal_radius_m=goal_radius_m,
        )
        self._active_goal_position: tuple[float, float, float] | None = None
        self._last_status: NavigationBackendStatus | None = None

    def select_goal_position(self) -> tuple[float, float, float] | None:
        positions = _episode_goal_positions(getattr(self.env, "current_episode", None))
        if not positions:
            return None
        return _nearest_goal_position(self.env, positions)

    def next_action(self, goal_position: Sequence[float]) -> Any:
        parsed_goal_position = _tuple3_position(goal_position)
        if parsed_goal_position is None:
            return None
        if parsed_goal_position != self._active_goal_position:
            self._last_status = self._backend.go_to(
                NavigationGoal(
                    goal_id="pathfinder_suffix_goal",
                    pose=Pose2D(
                        x=parsed_goal_position[0],
                        y=parsed_goal_position[2],
                    ),
                    frame_id="habitat_world",
                    tolerance_m=self.goal_radius_m,
                    source="pathfinder_suffix_oracle",
                    metadata={
                        "habitat_goal_position": list(parsed_goal_position),
                    },
                )
            )
            if self._last_status.status is NavigationStatus.FAILED:
                return None
            self._active_goal_position = parsed_goal_position
        action = self._backend.next_action()
        self._last_status = self._backend.status()
        return action

    def backend_status(self) -> NavigationBackendStatus | None:
        if self._last_status is not None:
            return self._last_status
        status = getattr(self._backend, "status", None)
        return status() if callable(status) else None


def _record_policy_trace_step(
    policy_trace: list[dict[str, Any]] | None,
    *,
    policy: str,
    observation: Mapping[str, Any],
    step_index: int,
    max_steps: int,
    action: str,
    state: OfficialPolicyState,
) -> None:
    if policy_trace is None:
        return
    x_m, z_m = _observation_xz(observation)
    decision = _policy_step_decision(
        policy=policy,
        action=action,
        step_index=step_index,
        max_steps=max_steps,
        state=state,
    )
    record: dict[str, Any] = {
        "episode_index": state.episode_index,
        "episode_id": state.episode_id,
        "scene_id": state.scene_id,
        "target_category": state.object_category,
        "policy": policy,
        "policy_kind": _policy_kind(policy),
        "step_index": step_index,
        "action": action,
        "decision": decision,
        "x_m": x_m,
        "z_m": z_m,
        "heading_rad": _observation_heading(observation),
    }
    memory_debug = _policy_step_memory_debug(
        policy=policy,
        action=action,
        step_index=step_index,
        max_steps=max_steps,
        state=state,
    )
    if memory_debug is not None:
        record["memory_prior"] = memory_debug
    if state.pathfinder_suffix_debug is not None:
        record["pathfinder_suffix"] = dict(state.pathfinder_suffix_debug)
    if state.targetnav_debug is not None:
        record["targetnav"] = dict(state.targetnav_debug)
    if state.occupancy_map is not None:
        occupancy_debug = occupancy_frontier_counts(state.occupancy_map)
        if state.selected_frontier_bearing_rad is not None:
            occupancy_debug["selected_bearing_rad"] = (
                state.selected_frontier_bearing_rad
            )
        record["occupancy_frontier"] = occupancy_debug
    policy_trace.append(record)


def _policy_step_decision(
    *,
    policy: str,
    action: str,
    step_index: int,
    max_steps: int,
    state: OfficialPolicyState,
) -> str | None:
    if _is_budget_stop(policy=policy, action=action, step_index=step_index, max_steps=max_steps):
        return "budget_stop"
    if state.memory_debug is not None:
        decision = state.memory_debug.get("decision")
        if decision is not None:
            return str(decision)
    if action == "stop" and policy == "noop":
        return "noop_stop"
    return None


def _policy_step_memory_debug(
    *,
    policy: str,
    action: str,
    step_index: int,
    max_steps: int,
    state: OfficialPolicyState,
) -> dict[str, Any] | None:
    if _is_budget_stop(policy=policy, action=action, step_index=step_index, max_steps=max_steps):
        if policy in {
            "memory_guided_frontier",
            "memory_belief_frontier",
            "memory_evidence_frontier",
            "memory_active_perception_frontier",
            "memory_active_perception_frontier_pathfinder_suffix",
            "memory_active_perception_frontier_targetnav",
            "memory_active_perception_frontier_targetnav_ddppo",
            "memory_learned_local_frontier",
        }:
            return {"decision": "budget_stop"}
        return None
    if state.memory_debug is None:
        return None
    return dict(state.memory_debug)


def _is_budget_stop(
    *,
    policy: str,
    action: str,
    step_index: int,
    max_steps: int,
) -> bool:
    if action != "stop" or step_index < max_steps - 1:
        return False
    return policy != "noop"


def _policy_trace_summary(steps: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "step_count": len(steps),
        "action_counts": _count_trace_values(steps, key="action"),
        "decision_counts": _count_trace_values(steps, key="decision"),
    }


def _policy_trace_payload(steps: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "task": "official_policy_step_trace",
        **_policy_trace_summary(steps),
        "steps": [dict(step) for step in steps],
    }


def _count_trace_values(
    records: Sequence[Mapping[str, Any]],
    *,
    key: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        value = record.get(key)
        if value is None:
            continue
        value_key = str(value)
        counts[value_key] = counts.get(value_key, 0) + 1
    return counts


@dataclass
class OccupancyFrontierMap:
    grid: np.ndarray
    cell_size_m: float
    origin_cell: tuple[int, int]


def create_occupancy_frontier_map(
    *,
    size_cells: int = 81,
    cell_size_m: float = 0.25,
) -> OccupancyFrontierMap:
    if size_cells <= 2:
        raise ValueError("size_cells must be greater than 2")
    if size_cells % 2 == 0:
        raise ValueError("size_cells must be odd so the origin is centered")
    if cell_size_m <= 0.0:
        raise ValueError("cell_size_m must be positive")
    grid = np.full((size_cells, size_cells), OCCUPANCY_UNKNOWN, dtype=np.int8)
    origin = (size_cells // 2, size_cells // 2)
    return OccupancyFrontierMap(
        grid=grid,
        cell_size_m=cell_size_m,
        origin_cell=origin,
    )


def update_occupancy_frontier_map(
    frontier_map: OccupancyFrontierMap,
    observation: Mapping[str, Any],
    *,
    hfov_deg: float = 79.0,
    min_depth_m: float = 0.5,
    max_depth_m: float = 5.0,
    sample_columns: int = 9,
) -> None:
    depth = _depth_frame_2d(observation.get("depth"))
    if depth is None:
        return
    x_m, z_m = _observation_xz(observation)
    heading_rad = _observation_heading(observation)
    agent_cell = _world_to_grid_cell(frontier_map, x_m=x_m, z_m=z_m)
    _mark_cell(frontier_map, agent_cell, OCCUPANCY_FREE)

    finite_depth = depth[np.isfinite(depth)]
    if finite_depth.size == 0:
        return
    normalized = float(np.nanmax(finite_depth)) <= 1.0
    height, width = depth.shape
    row = height // 2
    columns = _sample_depth_columns(width, sample_columns)
    hfov_rad = np.deg2rad(hfov_deg)
    for column in columns:
        raw_depth = float(depth[row, column])
        if not np.isfinite(raw_depth) or raw_depth <= 0.0:
            continue
        depth_m = _depth_value_to_meters(
            raw_depth,
            normalized=normalized,
            min_depth_m=min_depth_m,
            max_depth_m=max_depth_m,
        )
        rel = 0.0 if width <= 1 else (float(column) / float(width - 1)) - 0.5
        bearing = heading_rad + rel * hfov_rad
        endpoint_distance = min(depth_m, max_depth_m)
        _mark_free_ray(
            frontier_map,
            start_cell=agent_cell,
            x_m=x_m,
            z_m=z_m,
            bearing_rad=bearing,
            distance_m=endpoint_distance,
        )
        if depth_m < max_depth_m * 0.98:
            obstacle_cell = _world_to_grid_cell(
                frontier_map,
                x_m=x_m + np.sin(bearing) * depth_m,
                z_m=z_m + np.cos(bearing) * depth_m,
            )
            _mark_cell(frontier_map, obstacle_cell, OCCUPANCY_OCCUPIED)


def occupancy_frontier_counts(frontier_map: OccupancyFrontierMap) -> dict[str, int]:
    return {
        "unknown": int(np.count_nonzero(frontier_map.grid == OCCUPANCY_UNKNOWN)),
        "free": int(np.count_nonzero(frontier_map.grid == OCCUPANCY_FREE)),
        "occupied": int(np.count_nonzero(frontier_map.grid == OCCUPANCY_OCCUPIED)),
        "frontier": len(_frontier_cells(frontier_map)),
    }


def summarize_official_objectnav_metrics(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    required_present = all(
        all(key in _row_metrics(row) for key in OFFICIAL_OBJECTNAV_MEASURE_KEYS)
        for row in rows
    )
    means = {
        key: _mean_metric(rows, key)
        for key in OFFICIAL_OBJECTNAV_MEASURE_KEYS + OPTIONAL_OBJECTNAV_MEASURE_KEYS
        if any(key in _row_metrics(row) for row in rows)
    }
    return {
        "episodes": len(rows),
        "measure_source": METRIC_SOURCE,
        "success_rate": means.get("success"),
        "spl": means.get("spl"),
        "soft_spl": means.get("soft_spl"),
        "distance_to_goal": means.get("distance_to_goal"),
        "distance_to_goal_reward": means.get("distance_to_goal_reward"),
        "required_measures": list(OFFICIAL_OBJECTNAV_MEASURE_KEYS),
        "required_measures_present": required_present,
    }


def make_protocol_manifest(
    config: OfficialObjectNavRunConfig,
    *,
    habitat_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "task": "official_habitat_objectnav_measure_adapter",
        "metric_source": METRIC_SOURCE,
        "official_measure_keys": list(OFFICIAL_OBJECTNAV_MEASURE_KEYS),
        "optional_measure_keys": list(OPTIONAL_OBJECTNAV_MEASURE_KEYS),
        "config_path": config.config_path,
        "dataset_data_path": config.dataset_data_path,
        "scene_root": config.scene_root,
        "habitat_dataset_scenes_dir": str(_habitat_scenes_dir(config.scene_root)),
        "split": config.split,
        "policy": config.policy,
        "max_episodes": config.max_episodes,
        "max_steps": config.max_steps,
        "seed": config.seed,
        "policy_kind": _policy_kind(config.policy),
        "memory_prior": _memory_prior_manifest(config),
        "local_action_model": _local_action_model_manifest(config),
        "candidate_viewpoint_ranker_model": (
            _candidate_viewpoint_ranker_model_manifest(config)
        ),
        "detector_control": {
            "center_direction_sign": config.detector_center_direction_sign,
        },
        "pathfinder_suffix": _pathfinder_suffix_manifest(config),
        "targetnav": _targetnav_manifest(config),
        "habitat": dict(habitat_metadata),
        "invalid_for_benchmark_claim_reason": (
            _invalid_for_benchmark_claim_reason(config)
        ),
    }


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "episode_index",
        "episode_id",
        "scene_id",
        "object_category",
        "habitat_official",
        "policy_debug",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (
                        json.dumps(row.get(key, {}), sort_keys=True)
                        if key in {"habitat_official", "policy_debug"}
                        else row.get(key, "")
                    )
                    for key in fieldnames
                }
            )


def _validate_run_config(config: OfficialObjectNavRunConfig) -> None:
    if config.policy not in SUPPORTED_OFFICIAL_POLICIES:
        raise ValueError(f"policy must be one of: {', '.join(SUPPORTED_OFFICIAL_POLICIES)}")
    if config.max_episodes is not None and config.max_episodes <= 0:
        raise ValueError("max_episodes must be positive when provided")
    if config.max_steps <= 0:
        raise ValueError("max_steps must be positive")
    if config.memory_stop_radius_m <= 0.0:
        raise ValueError("memory_stop_radius_m must be positive")
    if config.memory_bearing_tolerance_deg <= 0.0:
        raise ValueError("memory_bearing_tolerance_deg must be positive")
    if config.memory_min_confidence < 0.0:
        raise ValueError("memory_min_confidence must be non-negative")
    if config.detector_center_direction_sign not in {-1, 1}:
        raise ValueError("detector_center_direction_sign must be -1 or 1")
    if config.targetnav_backend not in SUPPORTED_TARGETNAV_BACKENDS:
        raise ValueError(
            "targetnav_backend must be one of: "
            f"{', '.join(SUPPORTED_TARGETNAV_BACKENDS)}"
        )
    if config.pathfinder_suffix_goal_radius_m <= 0.0:
        raise ValueError("pathfinder_suffix_goal_radius_m must be positive")
    if config.policy in {
        "memory_guided_frontier",
        "memory_belief_frontier",
        "memory_evidence_frontier",
        "memory_active_perception_frontier",
        "memory_active_perception_frontier_pathfinder_suffix",
        "naive_count_targetnav",
        "memory_active_perception_frontier_targetnav",
        "memory_active_perception_frontier_targetnav_fmm",
        "memory_active_perception_frontier_targetnav_ddppo",
        "memory_learned_local_frontier",
    } and not (config.memory_prior_path):
        raise ValueError(f"{config.policy} requires memory_prior_path")
    if (
        config.policy == "memory_active_perception_frontier_targetnav_ddppo"
        or (
            config.policy
            in {
                "no_memory_targetnav",
                "naive_count_targetnav",
                "memory_active_perception_frontier_targetnav",
            }
            and config.targetnav_backend == "ddppo_pointnav"
        )
    ) and not config.targetnav_ddppo_checkpoint_path:
        raise ValueError(
            "memory_active_perception_frontier_targetnav_ddppo requires "
            "targetnav DDPPO checkpoint path"
        )
    if (
        config.policy == "memory_active_perception_frontier_targetnav_ddppo"
        and not config.targetnav_ddppo_checkpoint_path
    ):
        raise ValueError(
            "memory_active_perception_frontier_targetnav_ddppo requires "
            "targetnav DDPPO checkpoint path"
        )
    if (
        config.policy == "memory_learned_local_frontier"
        and not config.local_action_model_path
    ):
        raise ValueError("memory_learned_local_frontier requires local_action_model_path")
    if config.memory_prior_path:
        load_official_memory_prior(config.memory_prior_path)
    if config.local_action_model_path:
        load_official_local_action_model(config.local_action_model_path)
    if config.candidate_viewpoint_ranker_model_path:
        load_official_candidate_viewpoint_ranker_model(
            config.candidate_viewpoint_ranker_model_path
        )


def _invalid_for_benchmark_claim_reason(
    config: OfficialObjectNavRunConfig,
) -> str | None:
    if config.policy in {"noop", "random"}:
        return "preflight_or_trivial_policy_only"
    if config.policy == "memory_active_perception_frontier_pathfinder_suffix":
        return "pathfinder_suffix_oracle_diagnostic"
    if (
        config.policy
        in {
            "no_memory_targetnav",
            "naive_count_targetnav",
            "memory_active_perception_frontier_targetnav",
        }
        and config.targetnav_backend == "oracle_follower"
    ):
        return "targetnav_oracle_backend_diagnostic"
    if config.policy in {
        "memory_guided_frontier",
        "memory_belief_frontier",
        "memory_evidence_frontier",
        "memory_active_perception_frontier",
        "memory_active_perception_frontier_pathfinder_suffix",
        "naive_count_targetnav",
        "memory_active_perception_frontier_targetnav",
        "memory_active_perception_frontier_targetnav_fmm",
        "memory_active_perception_frontier_targetnav_ddppo",
        "memory_learned_local_frontier",
    }:
        if _memory_prior_source_validity(config) == "oracle_diagnostic_only":
            return "oracle_memory_prior_diagnostic"
        return "memory_prior_source_not_benchmark_validated"
    return None


def _memory_prior_manifest(config: OfficialObjectNavRunConfig) -> dict[str, Any] | None:
    if not config.memory_prior_path:
        return None
    anchors = load_official_memory_prior(config.memory_prior_path)
    metadata = _memory_prior_metadata(config.memory_prior_path)
    source_validity = str(
        metadata.get("source_validity", "not_benchmark_validated")
    )
    manifest: dict[str, Any] = {
        "path": config.memory_prior_path,
        "anchor_count": len(anchors),
        "stop_radius_m": config.memory_stop_radius_m,
        "bearing_tolerance_deg": config.memory_bearing_tolerance_deg,
        "min_confidence": config.memory_min_confidence,
        "source_validity": source_validity,
    }
    if metadata.get("source") is not None:
        manifest["metadata_source"] = str(metadata["source"])
    if metadata.get("coordinate_frame") is not None:
        manifest["metadata_coordinate_frame"] = str(metadata["coordinate_frame"])
    return manifest


def _memory_prior_source_validity(config: OfficialObjectNavRunConfig) -> str:
    if not config.memory_prior_path:
        return "not_used"
    return str(
        _memory_prior_metadata(config.memory_prior_path).get(
            "source_validity",
            "not_benchmark_validated",
        )
    )


def _memory_prior_metadata(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return {}
    metadata = payload.get("metadata") if isinstance(payload, Mapping) else None
    if not isinstance(metadata, Mapping):
        return {}
    return dict(metadata)


def _local_action_model_manifest(
    config: OfficialObjectNavRunConfig,
) -> dict[str, Any] | None:
    if not config.local_action_model_path:
        return None
    model = load_official_local_action_model(config.local_action_model_path)
    return {
        "path": config.local_action_model_path,
        "task": str(model.get("task", "")),
        "model_type": str(model.get("model_type", "")),
        "label_name": str(model.get("label_name", "")),
        "feature_count": len(model.get("feature_names", [])),
        "source_validity": "not_benchmark_validated",
    }


def _candidate_viewpoint_ranker_model_manifest(
    config: OfficialObjectNavRunConfig,
) -> dict[str, Any] | None:
    if not config.candidate_viewpoint_ranker_model_path:
        return None
    model = load_official_candidate_viewpoint_ranker_model(
        config.candidate_viewpoint_ranker_model_path
    )
    return {
        "path": config.candidate_viewpoint_ranker_model_path,
        "task": str(model.get("task", "")),
        "model_type": str(model.get("model_type", "")),
        "label_name": str(model.get("label_name", "")),
        "feature_count": len(model.get("feature_names", [])),
        "source_validity": "not_benchmark_validated",
    }


def _pathfinder_suffix_manifest(config: OfficialObjectNavRunConfig) -> dict[str, Any]:
    enabled = config.policy == "memory_active_perception_frontier_pathfinder_suffix"
    return {
        "enabled": enabled,
        "goal_radius_m": config.pathfinder_suffix_goal_radius_m,
        "source_validity": "oracle_diagnostic_only" if enabled else "not_used",
    }


def _targetnav_manifest(config: OfficialObjectNavRunConfig) -> dict[str, Any]:
    enabled = config.policy in {
        "no_memory_targetnav",
        "naive_count_targetnav",
        "memory_active_perception_frontier_targetnav",
        "memory_active_perception_frontier_targetnav_fmm",
        "memory_active_perception_frontier_targetnav_ddppo",
    }
    backend = (
        "fmm_grid"
        if config.policy == "memory_active_perception_frontier_targetnav_fmm"
        else "ddppo_pointnav"
        if config.policy == "memory_active_perception_frontier_targetnav_ddppo"
        else config.targetnav_backend
        if enabled
        else None
    )
    manifest = {
        "enabled": enabled,
        "target_estimator": "bbox_depth" if enabled else None,
        "backend": backend,
        "source_validity": (
            "oracle_diagnostic_only"
            if backend == "oracle_follower"
            else "sensor_depth_learned_pointnav_policy"
            if backend == "ddppo_pointnav"
            else "sensor_depth_local_planner"
            if enabled
            else "not_used"
        ),
    }
    if backend == "ddppo_pointnav":
        manifest["checkpoint_path"] = config.targetnav_ddppo_checkpoint_path
        manifest["device"] = config.targetnav_ddppo_device
    return manifest


def _memory_anchor_from_payload(
    raw_anchor: Any,
    *,
    index: int,
) -> OfficialMemoryAnchor:
    if not isinstance(raw_anchor, Mapping):
        raise ValueError(f"memory prior anchor {index} must be an object")
    for key in ("object_category", "x_m", "z_m"):
        if key not in raw_anchor:
            raise ValueError(f"memory prior anchor {index} missing {key}")
    object_category = str(raw_anchor["object_category"])
    if not object_category:
        raise ValueError(f"memory prior anchor {index} has empty object_category")
    try:
        x_m = float(raw_anchor["x_m"])
        z_m = float(raw_anchor["z_m"])
        raw_y_m = raw_anchor.get("y_m")
        y_m = float(raw_y_m) if raw_y_m is not None else None
        confidence = float(raw_anchor.get("confidence", 1.0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"memory prior anchor {index} has non-numeric fields") from exc
    if not np.isfinite(x_m):
        raise ValueError(f"memory prior anchor {index} has non-finite x_m")
    if not np.isfinite(z_m):
        raise ValueError(f"memory prior anchor {index} has non-finite z_m")
    if y_m is not None and not np.isfinite(y_m):
        raise ValueError(f"memory prior anchor {index} has non-finite y_m")
    if not np.isfinite(confidence):
        raise ValueError(f"memory prior anchor {index} has non-finite confidence")
    scene_id = raw_anchor.get("scene_id")
    episode_id = raw_anchor.get("episode_id")
    source = str(raw_anchor.get("source", "unknown"))
    coordinate_frame = str(
        raw_anchor.get("coordinate_frame", "episode_start_relative")
    )
    return OfficialMemoryAnchor(
        object_category=object_category,
        x_m=x_m,
        z_m=z_m,
        y_m=y_m,
        scene_id=str(scene_id) if scene_id is not None else None,
        episode_id=str(episode_id) if episode_id is not None else None,
        confidence=confidence,
        source=source,
        coordinate_frame=coordinate_frame,
    )


def _memory_anchor_scene_matches(anchor_scene_id: str | None, scene_id: str) -> bool:
    if anchor_scene_id is None or not anchor_scene_id:
        return True
    return (
        scene_id == anchor_scene_id
        or scene_id.endswith(anchor_scene_id)
        or anchor_scene_id in scene_id
    )


def _memory_anchor_episode_matches(
    anchor_episode_id: str | None,
    episode_id: str | None,
) -> bool:
    if anchor_episode_id is None or not anchor_episode_id:
        return True
    if episode_id is None or not episode_id:
        return False
    return str(anchor_episode_id) == str(episode_id)


def _memory_anchor_episode_exact_match(
    anchor_episode_id: str | None,
    episode_id: str | None,
) -> bool:
    return bool(
        anchor_episode_id
        and episode_id
        and str(anchor_episode_id) == str(episode_id)
    )


def _load_habitat_metadata(config: OfficialObjectNavRunConfig) -> dict[str, Any]:
    habitat = _import_habitat()
    cfg = _habitat_config(habitat, config)
    task = cfg.habitat.task
    measurements = list(getattr(task, "measurements", {}).keys())
    return {
        "validated": True,
        "version": str(getattr(habitat, "__version__", "unknown")),
        "task_type": str(task.type),
        "measurements": measurements,
        "max_episode_steps": int(cfg.habitat.environment.max_episode_steps),
        "dataset_type": str(cfg.habitat.dataset.type),
        "dataset_split": str(cfg.habitat.dataset.split),
        "dataset_data_path": str(cfg.habitat.dataset.data_path),
        "dataset_scenes_dir": str(cfg.habitat.dataset.scenes_dir),
    }


def _make_habitat_env(config: OfficialObjectNavRunConfig) -> Any:
    habitat = _import_habitat()
    cfg = _habitat_config(habitat, config)
    dataset = habitat.datasets.make_dataset(
        id_dataset=cfg.habitat.dataset.type,
        config=cfg.habitat.dataset,
    )
    _patch_hm3d_scene_dataset_configs(dataset, scene_root=config.scene_root)
    return habitat.Env(config=cfg, dataset=dataset)


def _load_targetnav_ddppo_backend(config: OfficialObjectNavRunConfig) -> Any:
    if not config.targetnav_ddppo_checkpoint_path:
        raise ValueError("targetnav DDPPO checkpoint path is required")
    from objectnav_core.evaluation.habitat_pointnav_ddppo_backend import (
        HabitatPointNavDDPPOBackend,
    )

    return HabitatPointNavDDPPOBackend.from_checkpoint(
        config.targetnav_ddppo_checkpoint_path,
        device=config.targetnav_ddppo_device,
    )


def _reset_targetnav_ddppo_backend(backend: Any | None) -> None:
    reset = getattr(backend, "reset", None)
    if callable(reset):
        reset()


def _habitat_config(habitat: Any, config: OfficialObjectNavRunConfig) -> Any:
    overrides = [
        f"habitat.dataset.split={config.split}",
        f"habitat.dataset.data_path={config.dataset_data_path}",
        f"habitat.dataset.scenes_dir={_habitat_scenes_dir(config.scene_root)}",
        f"habitat.environment.max_episode_steps={config.max_steps}",
    ]
    return habitat.get_config(config_path=config.config_path, overrides=overrides)


def _import_habitat() -> Any:
    try:
        import habitat  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised on machines without Habitat.
        raise RuntimeError(
            "Habitat-Lab is required for --validate-habitat or full official eval. "
            "Run this command in the Linux conda habitat environment."
        ) from exc
    return habitat


def _habitat_scenes_dir(scene_root: str | Path) -> Path:
    root = Path(scene_root)
    return root.parent if root.name == "hm3d" else root


def _patch_hm3d_scene_dataset_configs(dataset: Any, *, scene_root: str | Path) -> None:
    root = Path(scene_root)
    if root.name != "hm3d":
        candidate_root = root / "hm3d"
    else:
        candidate_root = root
    for episode in getattr(dataset, "episodes", []) or []:
        config_path = Path(str(getattr(episode, "scene_dataset_config", "")))
        candidate = candidate_root / config_path.name
        if config_path.name and candidate.exists():
            episode.scene_dataset_config = str(candidate)


def _official_metrics_from_env(env: Any) -> dict[str, float]:
    raw_metrics = env.get_metrics()
    metrics: dict[str, float] = {}
    for key in OFFICIAL_OBJECTNAV_MEASURE_KEYS + OPTIONAL_OBJECTNAV_MEASURE_KEYS:
        if key in raw_metrics:
            metrics[key] = float(raw_metrics[key])
    return metrics


def _select_policy_action(
    policy: str,
    *,
    observation: Mapping[str, Any],
    step_index: int,
    max_steps: int,
    state: OfficialPolicyState,
) -> str:
    if policy == "noop":
        return "stop"
    if policy == "random":
        if step_index >= max_steps - 1:
            return "stop"
        move_actions = ("move_forward", "turn_left", "turn_right")
        return state.rng.choice(move_actions)
    if policy == "frontier_only":
        if step_index >= max_steps - 1:
            return "stop"
        if _center_depth_is_clear(observation.get("depth")):
            state.blocked_turn_count = 0
            return "move_forward"
        action = state.blocked_turn_action
        state.blocked_turn_count += 1
        return action
    if policy == "occupancy_frontier":
        if step_index >= max_steps - 1:
            return "stop"
        return _select_occupancy_frontier_action(observation, state)
    if policy == "memory_guided_frontier":
        if step_index >= max_steps - 1:
            return "stop"
        return _select_memory_guided_frontier_action(
            observation,
            state,
            step_index=step_index,
        )
    if policy == "memory_belief_frontier":
        if step_index >= max_steps - 1:
            return "stop"
        return _select_memory_belief_frontier_action(
            observation,
            state,
            step_index=step_index,
        )
    if policy == "memory_evidence_frontier":
        if step_index >= max_steps - 1:
            return "stop"
        return _select_memory_evidence_frontier_action(
            observation,
            state,
            step_index=step_index,
        )
    if policy == "memory_active_perception_frontier":
        if step_index >= max_steps - 1:
            return "stop"
        return _select_memory_active_perception_frontier_action(
            observation,
            state,
            step_index=step_index,
        )
    if policy == "memory_active_perception_frontier_pathfinder_suffix":
        if step_index >= max_steps - 1:
            return "stop"
        return _select_memory_active_perception_frontier_pathfinder_suffix_action(
            observation,
            state,
            step_index=step_index,
        )
    if policy in {
        "no_memory_targetnav",
        "naive_count_targetnav",
        "memory_active_perception_frontier_targetnav",
        "memory_active_perception_frontier_targetnav_fmm",
        "memory_active_perception_frontier_targetnav_ddppo",
    }:
        if step_index >= max_steps - 1:
            return "stop"
        return _select_memory_active_perception_frontier_targetnav_action(
            observation,
            state,
            step_index=step_index,
            use_memory=(policy != "no_memory_targetnav"),
            backend=(
                "fmm_grid"
                if policy == "memory_active_perception_frontier_targetnav_fmm"
                else "ddppo_pointnav"
                if policy == "memory_active_perception_frontier_targetnav_ddppo"
                else state.targetnav_backend
            ),
        )
    if policy == "memory_learned_local_frontier":
        if step_index >= max_steps - 1:
            return "stop"
        return _select_memory_learned_local_frontier_action(
            observation,
            state,
            step_index=step_index,
        )
    raise ValueError(f"Unsupported official ObjectNav policy: {policy}")


def _select_occupancy_frontier_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
) -> str:
    if state.occupancy_map is None:
        state.occupancy_map = create_occupancy_frontier_map()
    update_occupancy_frontier_map(state.occupancy_map, observation)
    if _center_depth_is_clear(observation.get("depth")):
        state.blocked_turn_count = 0
        state.selected_frontier_bearing_rad = 0.0
        return "move_forward"
    if 0 < state.blocked_turn_count < OCCUPANCY_BLOCKED_TURN_BURST_STEPS:
        state.blocked_turn_count += 1
        return state.blocked_turn_action
    action, bearing = _turn_toward_nearest_frontier(
        state.occupancy_map,
        observation,
    )
    state.blocked_turn_action = action
    state.blocked_turn_count = 1
    state.selected_frontier_bearing_rad = bearing
    return action


def _select_memory_guided_frontier_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int,
) -> str:
    detector_match = _detector_confirmed_target(
        observation,
        state,
        step_index=step_index,
    )
    if detector_match is not None:
        state.memory_debug = {
            "decision": "stop_on_detector",
            **detector_match,
        }
        return "stop"

    anchor = select_official_memory_anchor(
        state.memory_anchors,
        object_category=state.object_category,
        scene_id=state.scene_id,
        episode_id=state.episode_id,
        min_confidence=state.memory_min_confidence,
    )
    if anchor is None:
        state.active_perception_target_viewpoint_cell = None
        state.active_perception_blocked_scan_viewpoint_cell = None
        state.memory_debug = {
            "decision": "fallback_occupancy_frontier",
            "fallback_reason": "no_matching_memory",
            "candidate_count": len(state.memory_anchors),
        }
        return _select_occupancy_frontier_action(observation, state)

    x_m, z_m = _observation_xz(observation)
    dx = anchor.x_m - x_m
    dz = anchor.z_m - z_m
    range_m = float(np.hypot(dx, dz))
    bearing = float(np.arctan2(dx, dz))
    heading = _observation_heading(observation)
    bearing_error = _wrap_angle(bearing - heading)
    state.memory_debug = {
        "selected_source": anchor.source,
        "selected_category": anchor.object_category,
        "selected_scene_id": anchor.scene_id,
        "confidence": anchor.confidence,
        "range_m": range_m,
        "bearing_error_rad": bearing_error,
    }
    if range_m <= state.memory_stop_radius_m:
        state.memory_debug["decision"] = "stop_at_memory"
        return "stop"
    if abs(bearing_error) > state.memory_bearing_tolerance_rad:
        state.blocked_turn_count = 0
        state.memory_debug["decision"] = "turn_toward_memory"
        return "turn_right" if bearing_error > 0.0 else "turn_left"
    if _center_depth_is_clear(observation.get("depth")):
        state.blocked_turn_count = 0
        state.memory_debug["decision"] = "move_toward_memory"
        return "move_forward"
    state.memory_debug["decision"] = "fallback_occupancy_frontier"
    state.memory_debug["fallback_reason"] = "blocked_memory_corridor"
    return _select_occupancy_frontier_action(observation, state)


def _select_memory_belief_frontier_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int,
) -> str:
    detector_match = _detector_confirmed_target(
        observation,
        state,
        step_index=step_index,
    )
    if detector_match is not None:
        detector_action = _select_detector_guided_target_action(
            observation,
            state,
            detector_match,
            step_index=step_index,
        )
        if detector_action is not None:
            return detector_action
    else:
        reacquire_action = _select_detector_reacquire_action(
            state,
            step_index=step_index,
        )
        if reacquire_action is not None:
            return reacquire_action

    return _select_memory_belief_frontier_fallback(observation, state)


def _select_memory_evidence_frontier_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int,
) -> str:
    detector_match = _detector_confirmed_target(
        observation,
        state,
        step_index=step_index,
    )
    if detector_match is not None:
        detector_action = _select_detector_action_effect_target_action(
            observation,
            state,
            detector_match,
            step_index=step_index,
        )
        if detector_action is not None:
            return detector_action
    else:
        reacquire_action = _select_detector_reacquire_action(
            state,
            step_index=step_index,
            record_failed_center_effect=True,
        )
        if reacquire_action is not None:
            return reacquire_action

    return _select_memory_belief_frontier_fallback(observation, state)


def _select_memory_learned_local_frontier_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int,
) -> str:
    detector_match = _detector_confirmed_target(
        observation,
        state,
        step_index=step_index,
    )
    if detector_match is not None:
        detector_action = _select_detector_learned_local_target_action(
            observation,
            state,
            detector_match,
            step_index=step_index,
        )
        if detector_action is not None:
            return detector_action
    else:
        reacquire_action = _select_detector_reacquire_action(
            state,
            step_index=step_index,
            record_failed_center_effect=True,
        )
        if reacquire_action is not None:
            return reacquire_action

    return _select_memory_belief_frontier_fallback(observation, state)


def _select_memory_active_perception_frontier_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int,
) -> str:
    detector_match = _detector_confirmed_target(
        observation,
        state,
        step_index=step_index,
    )
    return _select_memory_active_perception_frontier_action_after_detector(
        observation,
        state,
        step_index=step_index,
        detector_match=detector_match,
    )


def _select_memory_active_perception_frontier_action_after_detector(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int,
    detector_match: Mapping[str, Any] | None,
) -> str:
    if detector_match is not None:
        detector_action = _select_detector_action_effect_target_action(
            observation,
            state,
            detector_match,
            step_index=step_index,
        )
        if detector_action is not None:
            return detector_action
    else:
        reacquire_action = _select_detector_reacquire_action(
            state,
            step_index=step_index,
            record_failed_center_effect=True,
        )
        if reacquire_action is not None:
            return reacquire_action

    return _select_memory_active_perception_frontier_fallback(
        observation,
        state,
        step_index=step_index,
    )


def _select_memory_active_perception_frontier_pathfinder_suffix_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int,
) -> str:
    if state.pathfinder_suffix_active:
        action = _select_pathfinder_suffix_follow_action(state, step_index=step_index)
        if action is not None:
            return action

    detector_match = _detector_confirmed_target(
        observation,
        state,
        step_index=step_index,
    )
    if detector_match is not None:
        action = _activate_and_select_pathfinder_suffix_action(
            state,
            detector_match=detector_match,
            step_index=step_index,
        )
        if action is not None:
            return action

    return _select_memory_active_perception_frontier_action_after_detector(
        observation,
        state,
        step_index=step_index,
        detector_match=detector_match,
    )


def _select_memory_active_perception_frontier_targetnav_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int,
    use_memory: bool = True,
    backend: str = "occupancy_grid",
) -> str:
    if backend == "oracle_follower":
        if state.pathfinder_suffix_active:
            action = _select_pathfinder_suffix_follow_action(
                state,
                step_index=step_index,
            )
            if action is not None:
                _record_targetnav_oracle_debug(state)
                return action
        detector_match = _detector_confirmed_target(
            observation,
            state,
            step_index=step_index,
        )
        if detector_match is not None:
            action = _activate_and_select_pathfinder_suffix_action(
                state,
                detector_match=detector_match,
                step_index=step_index,
            )
            if action is not None:
                _record_targetnav_oracle_debug(state)
                return action
            state.targetnav_debug = {
                "backend": "oracle_follower",
                "source_validity": "oracle_diagnostic_only",
                "fallback_reason": "oracle_follower_unavailable",
            }
        if use_memory:
            anchor = select_official_memory_anchor(
                state.memory_anchors,
                object_category=state.object_category,
                scene_id=state.scene_id,
                episode_id=state.episode_id,
                min_confidence=state.memory_min_confidence,
            )
            if anchor is not None:
                action = _activate_and_select_memory_anchor_oracle_action(
                    state,
                    anchor=anchor,
                    step_index=step_index,
                )
                if action is not None:
                    _record_targetnav_oracle_debug(state)
                    return action
        return _select_memory_active_perception_frontier_action_after_detector(
            observation,
            state,
            step_index=step_index,
            detector_match=detector_match,
        )

    select_targetnav_action = (
        _select_targetnav_fmm_action
        if backend == "fmm_grid"
        else _select_targetnav_ddppo_action
        if backend == "ddppo_pointnav"
        else _select_targetnav_occupancy_action
    )
    detector_match = _detector_confirmed_target(
        observation,
        state,
        step_index=step_index,
    )
    if detector_match is not None:
        target_goal = _targetnav_goal_from_detector_match(
            observation,
            state,
            detector_match,
        )
        if target_goal is not None:
            state.targetnav_goal = _smooth_targetnav_goal(
                state.targetnav_goal,
                target_goal,
            )
            action = select_targetnav_action(
                observation,
                state,
                state.targetnav_goal,
                step_index=step_index,
            )
            if action is not None:
                return action
        state.targetnav_debug = {
            "target_estimator": "bbox_depth",
            "backend": backend,
            "fallback_reason": "target_projection_or_path_failed",
        }

    if state.targetnav_goal is not None:
        action = select_targetnav_action(
            observation,
            state,
            state.targetnav_goal,
            step_index=step_index,
        )
        if action is not None:
            return action

    if use_memory:
        anchor = select_official_memory_anchor(
            state.memory_anchors,
            object_category=state.object_category,
            scene_id=state.scene_id,
            episode_id=state.episode_id,
            min_confidence=state.memory_min_confidence,
        )
        if anchor is not None:
            target_goal = _targetnav_goal_from_memory_anchor(anchor)
            state.targetnav_goal = target_goal
            action = select_targetnav_action(
                observation,
                state,
                target_goal,
                step_index=step_index,
            )
            if action is not None:
                return action

    return _select_memory_active_perception_frontier_action_after_detector(
        observation,
        state,
        step_index=step_index,
        detector_match=detector_match,
    )


def _activate_and_select_memory_anchor_oracle_action(
    state: OfficialPolicyState,
    *,
    anchor: OfficialMemoryAnchor,
    step_index: int,
) -> str | None:
    state.targetnav_goal = _targetnav_goal_from_memory_anchor(anchor)
    goal_position = _memory_anchor_oracle_goal_position(state, anchor)
    if goal_position is None:
        state.targetnav_debug = {
            "backend": "oracle_follower",
            "source_validity": "oracle_diagnostic_only",
            "target_goal": dict(state.targetnav_goal),
            "memory_anchor": _memory_anchor_debug_payload(anchor),
            "fallback_reason": "missing_episode_start_pose_for_memory_anchor",
        }
        return None
    state.pathfinder_suffix_active = True
    state.pathfinder_suffix_activation_step = step_index
    state.pathfinder_suffix_goal_position = tuple(float(value) for value in goal_position)
    return _select_pathfinder_suffix_follow_action(state, step_index=step_index)


def _activate_and_select_pathfinder_suffix_action(
    state: OfficialPolicyState,
    *,
    detector_match: Mapping[str, Any],
    step_index: int,
) -> str | None:
    controller = state.pathfinder_suffix_controller
    if controller is None:
        state.pathfinder_suffix_debug = {
            "active": False,
            "activation_step": None,
            "fallback_reason": "pathfinder_suffix_unavailable",
        }
        return None
    goal_position = controller.select_goal_position()
    if goal_position is None:
        state.pathfinder_suffix_debug = {
            "active": False,
            "activation_step": None,
            "fallback_reason": "no_pathfinder_goal",
            "detector_match": dict(detector_match),
        }
        return None
    state.pathfinder_suffix_active = True
    state.pathfinder_suffix_activation_step = step_index
    state.pathfinder_suffix_goal_position = tuple(float(value) for value in goal_position)
    return _select_pathfinder_suffix_follow_action(state, step_index=step_index)


def _select_pathfinder_suffix_follow_action(
    state: OfficialPolicyState,
    *,
    step_index: int,
) -> str | None:
    controller = state.pathfinder_suffix_controller
    goal_position = state.pathfinder_suffix_goal_position
    if controller is None or goal_position is None:
        state.pathfinder_suffix_active = False
        state.pathfinder_suffix_debug = {
            "active": False,
            "activation_step": state.pathfinder_suffix_activation_step,
            "fallback_reason": "pathfinder_suffix_unavailable",
        }
        return None
    raw_action = controller.next_action(goal_position)
    backend_status = _controller_backend_status(controller)
    if (
        raw_action is None
        and backend_status is not None
        and backend_status.status is NavigationStatus.FAILED
    ):
        state.pathfinder_suffix_active = False
        state.pathfinder_suffix_debug = {
            "active": False,
            "activation_step": state.pathfinder_suffix_activation_step,
            "goal_position": [float(value) for value in goal_position],
            "last_step": step_index,
            "fallback_reason": "pathfinder_suffix_backend_failed",
            "backend_status": _navigation_backend_status_payload(backend_status),
        }
        return None
    action = _follower_action_name(raw_action)
    state.memory_debug = {
        "decision": "follow_pathfinder_suffix",
        "pathfinder_suffix_action": action,
    }
    state.pathfinder_suffix_debug = {
        "active": True,
        "activation_step": state.pathfinder_suffix_activation_step,
        "goal_position": [float(value) for value in goal_position],
        "last_step": step_index,
        "last_action": action,
    }
    if backend_status is not None:
        state.pathfinder_suffix_debug["backend_status"] = (
            _navigation_backend_status_payload(backend_status)
        )
    return action


def _record_targetnav_oracle_debug(state: OfficialPolicyState) -> None:
    state.targetnav_debug = {
        "backend": "oracle_follower",
        "source_validity": "oracle_diagnostic_only",
    }
    if state.targetnav_goal is not None:
        state.targetnav_debug["target_goal"] = dict(state.targetnav_goal)
        if state.targetnav_goal.get("targetnav_estimator") == "memory_anchor":
            state.targetnav_debug["memory_anchor"] = {
                "object_category": state.targetnav_goal.get("object_category"),
                "scene_id": state.targetnav_goal.get("scene_id"),
                "episode_id": state.targetnav_goal.get("episode_id"),
                "source": state.targetnav_goal.get("source"),
                "confidence": state.targetnav_goal.get("confidence"),
                "coordinate_frame": state.targetnav_goal.get("coordinate_frame"),
                "x_m": state.targetnav_goal.get("x_m"),
                "y_m": state.targetnav_goal.get("y_m"),
                "z_m": state.targetnav_goal.get("z_m"),
            }
    if state.pathfinder_suffix_debug is not None:
        state.targetnav_debug["oracle_follower"] = dict(state.pathfinder_suffix_debug)


def _select_memory_belief_frontier_fallback(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
) -> str:
    anchor = select_official_memory_anchor(
        state.memory_anchors,
        object_category=state.object_category,
        scene_id=state.scene_id,
        episode_id=state.episode_id,
        min_confidence=state.memory_min_confidence,
    )
    if anchor is None:
        state.memory_debug = {
            "decision": "fallback_occupancy_frontier",
            "fallback_reason": "no_matching_memory",
            "candidate_count": len(state.memory_anchors),
        }
        return _select_occupancy_frontier_action(observation, state)

    if state.occupancy_map is None:
        state.occupancy_map = create_occupancy_frontier_map()
    update_occupancy_frontier_map(state.occupancy_map, observation)
    selected = _select_memory_belief_frontier(
        state.occupancy_map,
        observation,
        anchor,
    )
    state.memory_debug = {
        "selected_source": anchor.source,
        "selected_category": anchor.object_category,
        "selected_scene_id": anchor.scene_id,
        "confidence": anchor.confidence,
    }
    if selected is None:
        state.memory_debug["decision"] = "fallback_occupancy_frontier"
        state.memory_debug["fallback_reason"] = "no_memory_belief_frontier"
        return _select_occupancy_frontier_action(observation, state)

    state.selected_frontier_bearing_rad = float(selected["bearing_error_rad"])
    state.memory_debug.update(
        {
            "selected_frontier_cell": selected["frontier_cell"],
            "belief_mass": selected["belief_mass"],
            "distance_to_anchor_m": selected["distance_to_anchor_m"],
            "travel_distance_m": selected["travel_distance_m"],
            "score": selected["score"],
            "bearing_error_rad": selected["bearing_error_rad"],
        }
    )
    if abs(float(selected["bearing_error_rad"])) > state.memory_bearing_tolerance_rad:
        state.blocked_turn_count = 0
        state.memory_debug["decision"] = "turn_toward_memory_belief_frontier"
        return "turn_right" if float(selected["bearing_error_rad"]) > 0.0 else "turn_left"
    if _center_depth_is_clear(observation.get("depth")):
        state.blocked_turn_count = 0
        state.memory_debug["decision"] = "move_toward_memory_belief_frontier"
        return "move_forward"
    state.memory_debug["decision"] = "fallback_occupancy_frontier"
    state.memory_debug["fallback_reason"] = "blocked_memory_belief_frontier_corridor"
    return _select_occupancy_frontier_action(observation, state)


def _select_memory_active_perception_frontier_fallback(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int | None = None,
) -> str:
    anchor = select_official_memory_anchor(
        state.memory_anchors,
        object_category=state.object_category,
        scene_id=state.scene_id,
        episode_id=state.episode_id,
        min_confidence=state.memory_min_confidence,
    )
    if anchor is None:
        state.memory_debug = {
            "decision": "fallback_occupancy_frontier",
            "fallback_reason": "no_matching_memory",
            "candidate_count": len(state.memory_anchors),
        }
        return _select_occupancy_frontier_action(observation, state)

    if state.occupancy_map is None:
        state.occupancy_map = create_occupancy_frontier_map()
    update_occupancy_frontier_map(state.occupancy_map, observation)
    committed_viewpoint_cell = state.active_perception_target_viewpoint_cell
    if (
        committed_viewpoint_cell == state.active_perception_scanned_viewpoint_cell
        and state.active_perception_scan_steps_remaining <= 0
    ):
        committed_viewpoint_cell = None
        state.active_perception_target_viewpoint_cell = None
    selected = _select_memory_active_perception_frontier(
        state.occupancy_map,
        observation,
        anchor,
        target_category=state.object_category,
        step_index=step_index,
        candidate_viewpoint_ranker_model=state.candidate_viewpoint_ranker_model,
        committed_viewpoint_cell=committed_viewpoint_cell,
    )
    state.memory_debug = {
        "selected_source": anchor.source,
        "selected_category": anchor.object_category,
        "selected_scene_id": anchor.scene_id,
        "confidence": anchor.confidence,
    }
    if selected is None:
        state.active_perception_target_viewpoint_cell = None
        state.active_perception_blocked_scan_viewpoint_cell = None
        state.memory_debug["decision"] = "fallback_occupancy_frontier"
        state.memory_debug["fallback_reason"] = "no_active_perception_frontier"
        return _select_occupancy_frontier_action(observation, state)

    selected_viewpoint_values = selected.get("viewpoint_cell")
    if (
        isinstance(selected_viewpoint_values, Sequence)
        and len(selected_viewpoint_values) >= 2
    ):
        state.active_perception_target_viewpoint_cell = (
            int(selected_viewpoint_values[0]),
            int(selected_viewpoint_values[1]),
        )
    state.selected_frontier_bearing_rad = float(selected["bearing_error_rad"])
    state.memory_debug.update(
        {
            "selected_viewpoint_cell": selected["viewpoint_cell"],
            "selected_frontier_cell": selected["frontier_cell"],
            "belief_mass": selected["belief_mass"],
            "distance_to_anchor_m": selected["distance_to_anchor_m"],
            "view_distance_quality": selected["view_distance_quality"],
            "view_bearing_quality": selected["view_bearing_quality"],
            "view_quality": selected["view_quality"],
            "expected_evidence": selected["expected_evidence"],
            "path_distance_m": selected["path_distance_m"],
            "travel_distance_m": selected["travel_distance_m"],
            "score": selected["score"],
            "active_perception_candidate_count": selected["candidate_count"],
            "top_candidates": selected["top_candidates"],
            "active_perception_commitment": selected[
                "active_perception_commitment"
            ],
        }
    )
    if selected.get("candidate_viewpoint_ranker_model") is not None:
        state.memory_debug.update(
            {
                "candidate_viewpoint_ranker_model": selected[
                    "candidate_viewpoint_ranker_model"
                ],
                "ranker_prediction": selected["ranker_prediction"],
                "ranker_candidate_count": selected["ranker_candidate_count"],
                "ranker_selected_candidate_rank": selected[
                    "ranker_selected_candidate_rank"
                ],
            }
        )
    scan_action = _select_active_perception_viewpoint_scan_action(
        observation,
        state,
        anchor,
        selected,
    )
    if scan_action is not None:
        return scan_action
    if abs(float(selected["bearing_error_rad"])) > state.memory_bearing_tolerance_rad:
        state.active_perception_blocked_scan_viewpoint_cell = None
        state.blocked_turn_count = 0
        state.memory_debug["decision"] = (
            "turn_toward_memory_active_perception_frontier"
        )
        return "turn_right" if float(selected["bearing_error_rad"]) > 0.0 else "turn_left"
    if _center_depth_is_clear(observation.get("depth")):
        state.active_perception_blocked_scan_viewpoint_cell = None
        state.blocked_turn_count = 0
        state.memory_debug["decision"] = (
            "move_toward_memory_active_perception_frontier"
        )
        return "move_forward"
    blocked_scan_action = _select_blocked_active_perception_scan_action(
        state,
        selected,
    )
    if blocked_scan_action is not None:
        return blocked_scan_action
    state.active_perception_target_viewpoint_cell = None
    state.memory_debug["decision"] = "fallback_occupancy_frontier"
    state.memory_debug["fallback_reason"] = (
        "blocked_memory_active_perception_frontier_corridor"
    )
    return _select_occupancy_frontier_action(observation, state)


def _select_active_perception_viewpoint_scan_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    anchor: OfficialMemoryAnchor,
    selected: Mapping[str, Any],
) -> str | None:
    if state.occupancy_map is None:
        return None
    try:
        path_distance_m = float(selected["path_distance_m"])
    except (KeyError, TypeError, ValueError):
        return None
    if path_distance_m > state.occupancy_map.cell_size_m + 1e-9:
        return None
    state.active_perception_blocked_scan_viewpoint_cell = None
    viewpoint_values = selected.get("viewpoint_cell")
    if not isinstance(viewpoint_values, Sequence) or len(viewpoint_values) < 2:
        return None
    viewpoint_cell = (int(viewpoint_values[0]), int(viewpoint_values[1]))
    x_m, z_m = _observation_xz(observation)
    heading = _observation_heading(observation)
    anchor_bearing = float(np.arctan2(anchor.x_m - x_m, anchor.z_m - z_m))
    anchor_error = _wrap_angle(anchor_bearing - heading)
    if state.memory_debug is not None:
        state.memory_debug.update(
            {
                "anchor_bearing_rad": anchor_bearing,
                "anchor_bearing_error_rad": anchor_error,
                "active_perception_scan_steps_remaining": (
                    state.active_perception_scan_steps_remaining
                ),
            }
        )
    if abs(anchor_error) > state.memory_bearing_tolerance_rad:
        state.active_perception_scan_steps_remaining = ACTIVE_PERCEPTION_SCAN_STEPS
        state.active_perception_scanned_viewpoint_cell = None
        state.selected_frontier_bearing_rad = anchor_error
        state.blocked_turn_count = 0
        if state.memory_debug is not None:
            state.memory_debug["active_perception_phase"] = "orient_anchor"
            state.memory_debug["decision"] = (
                "orient_memory_anchor_from_active_viewpoint"
            )
            state.memory_debug["active_perception_scan_steps_remaining"] = (
                state.active_perception_scan_steps_remaining
            )
        return "turn_right" if anchor_error > 0.0 else "turn_left"

    if (
        state.active_perception_scanned_viewpoint_cell == viewpoint_cell
        and state.active_perception_scan_steps_remaining <= 0
    ):
        return None
    if state.active_perception_scan_steps_remaining <= 0:
        state.active_perception_scan_steps_remaining = ACTIVE_PERCEPTION_SCAN_STEPS
    state.active_perception_scan_steps_remaining -= 1
    if state.active_perception_scan_steps_remaining <= 0:
        state.active_perception_scanned_viewpoint_cell = viewpoint_cell
        state.active_perception_target_viewpoint_cell = None
    state.selected_frontier_bearing_rad = anchor_error
    state.blocked_turn_count = 0
    if state.memory_debug is not None:
        state.memory_debug["active_perception_phase"] = "scan_anchor"
        state.memory_debug["decision"] = "scan_memory_anchor_from_active_viewpoint"
        state.memory_debug["active_perception_scan_steps_remaining"] = (
            state.active_perception_scan_steps_remaining
        )
    return "turn_left"


def _select_blocked_active_perception_scan_action(
    state: OfficialPolicyState,
    selected: Mapping[str, Any],
) -> str | None:
    viewpoint_values = selected.get("viewpoint_cell")
    if not isinstance(viewpoint_values, Sequence) or len(viewpoint_values) < 2:
        return None
    viewpoint_cell = (int(viewpoint_values[0]), int(viewpoint_values[1]))
    if state.active_perception_blocked_scan_viewpoint_cell != viewpoint_cell:
        state.active_perception_blocked_scan_viewpoint_cell = viewpoint_cell
        state.active_perception_scan_steps_remaining = ACTIVE_PERCEPTION_SCAN_STEPS
    if state.active_perception_scan_steps_remaining <= 0:
        return None
    state.active_perception_scan_steps_remaining -= 1
    if state.active_perception_scan_steps_remaining <= 0:
        state.active_perception_target_viewpoint_cell = None
    state.selected_frontier_bearing_rad = float(selected["bearing_error_rad"])
    state.blocked_turn_count = 0
    if state.memory_debug is not None:
        state.memory_debug["active_perception_phase"] = "blocked_scan_anchor"
        state.memory_debug["decision"] = "scan_blocked_active_perception_target"
        state.memory_debug["active_perception_scan_steps_remaining"] = (
            state.active_perception_scan_steps_remaining
        )
    return "turn_left"


def _detector_confirmed_target(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    *,
    step_index: int,
) -> dict[str, Any] | None:
    detector = state.target_detector_adapter
    if detector is None:
        return None
    rgb = observation.get("rgb")
    if rgb is None:
        if state.detector_trace is not None:
            state.detector_trace.record_missing_rgb(
                episode_index=state.episode_index,
                episode_id=state.episode_id,
                scene_id=state.scene_id,
                target_category=state.object_category,
                step_index=step_index,
            )
        return None
    detections = list(detector.detect(np.asarray(rgb)))
    best: dict[str, Any] | None = None
    trace_detections: list[dict[str, Any]] = []
    target_match_count = 0
    for detection in detections:
        confidence = float(getattr(detection, "confidence", 0.0))
        category = str(getattr(detection, "category", ""))
        bbox = _detector_bbox_payload(getattr(detection, "bbox", None))
        matches_target = (
            confidence >= state.target_detector_min_confidence
            and _normalize_object_label(category)
            == _normalize_object_label(state.object_category)
        )
        trace_detections.append(
            {
                "category": category,
                "confidence": confidence,
                "bbox": bbox,
                "matches_target": matches_target,
            }
        )
        if not matches_target:
            continue
        target_match_count += 1
        match = {
            "detector_category": category,
            "detector_confidence": confidence,
            "detector_bbox": bbox,
            **_detector_target_evidence(observation, bbox),
        }
        if best is None or confidence > float(best["detector_confidence"]):
            best = match
    if state.detector_trace is not None:
        state.detector_trace.record_detections(
            episode_index=state.episode_index,
            episode_id=state.episode_id,
            scene_id=state.scene_id,
            target_category=state.object_category,
            step_index=step_index,
            detections=trace_detections,
            target_match_count=target_match_count,
        )
    return best


def _select_detector_guided_target_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    detector_match: Mapping[str, Any],
    *,
    step_index: int,
) -> str | None:
    debug = {
        **dict(detector_match),
        "detector_center_tolerance_fraction": DETECTOR_CENTER_TOLERANCE_FRACTION,
        "detector_stop_min_bbox_area_fraction": DETECTOR_STOP_MIN_BBOX_AREA_FRACTION,
        "detector_stop_max_depth_m": DETECTOR_STOP_MAX_DEPTH_M,
        "detector_stop_max_depth_normalized": DETECTOR_STOP_MAX_DEPTH_NORMALIZED,
    }
    center_offset = detector_match.get("detector_center_offset_fraction")
    if center_offset is not None:
        center_offset = float(center_offset)
        if abs(center_offset) > DETECTOR_CENTER_TOLERANCE_FRACTION:
            action = _detector_center_action(
                center_offset,
                direction_sign=state.detector_center_direction_sign,
            )
            state.blocked_turn_count = 0
            state.last_detector_center_step = step_index
            state.last_detector_center_action = action
            state.last_detector_center_offset_fraction = center_offset
            state.last_detector_center_offset_sign = _detector_center_offset_sign(
                center_offset
            )
            debug["decision"] = "center_detector_target"
            debug["detector_center_direction_sign"] = (
                state.detector_center_direction_sign
            )
            state.memory_debug = debug
            return action

    if _detector_stop_is_range_confirmed(detector_match):
        debug["decision"] = "stop_on_detector_range_confirmed"
        state.memory_debug = debug
        return "stop"

    if _center_depth_is_clear(observation.get("depth")):
        state.blocked_turn_count = 0
        debug["decision"] = "approach_detector_target"
        state.memory_debug = debug
        return "move_forward"

    debug["decision"] = "fallback_detector_target_blocked"
    debug["fallback_reason"] = "blocked_detector_approach_corridor"
    state.memory_debug = debug
    return None


def _select_detector_action_effect_target_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    detector_match: Mapping[str, Any],
    *,
    step_index: int,
) -> str | None:
    debug = {
        **dict(detector_match),
        "detector_center_tolerance_fraction": DETECTOR_CENTER_TOLERANCE_FRACTION,
        "detector_stop_min_bbox_area_fraction": DETECTOR_STOP_MIN_BBOX_AREA_FRACTION,
        "detector_stop_max_depth_m": DETECTOR_STOP_MAX_DEPTH_M,
        "detector_stop_max_depth_normalized": DETECTOR_STOP_MAX_DEPTH_NORMALIZED,
        "failed_detector_center_effect_count": len(
            state.failed_detector_center_effects
        ),
    }
    center_offset = detector_match.get("detector_center_offset_fraction")
    if center_offset is not None:
        center_offset = float(center_offset)
        if abs(center_offset) > DETECTOR_CENTER_TOLERANCE_FRACTION:
            action = _detector_center_action(
                center_offset,
                direction_sign=state.detector_center_direction_sign,
            )
            offset_sign = _detector_center_offset_sign(center_offset)
            failed_action = _failed_detector_center_action_for_offset(
                state,
                offset_sign=offset_sign,
            )
            if (
                failed_action is not None
                and _center_depth_is_clear(observation.get("depth"))
            ):
                state.blocked_turn_count = 0
                debug["decision"] = "approach_detector_target_after_center_loss"
                debug["suppressed_detector_center_action"] = failed_action
                debug["detector_center_offset_sign"] = offset_sign
                state.memory_debug = debug
                return "move_forward"
            state.blocked_turn_count = 0
            state.last_detector_center_step = step_index
            state.last_detector_center_action = action
            state.last_detector_center_offset_fraction = center_offset
            state.last_detector_center_offset_sign = offset_sign
            debug["decision"] = "center_detector_target"
            debug["detector_center_direction_sign"] = (
                state.detector_center_direction_sign
            )
            debug["detector_center_offset_sign"] = offset_sign
            state.memory_debug = debug
            return action

    if _detector_stop_is_range_confirmed(detector_match):
        debug["decision"] = "stop_on_detector_range_confirmed"
        state.memory_debug = debug
        return "stop"

    if _center_depth_is_clear(observation.get("depth")):
        state.blocked_turn_count = 0
        debug["decision"] = "approach_detector_target"
        state.memory_debug = debug
        return "move_forward"

    debug["decision"] = "fallback_detector_target_blocked"
    debug["fallback_reason"] = "blocked_detector_approach_corridor"
    state.memory_debug = debug
    return None


def _select_detector_learned_local_target_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    detector_match: Mapping[str, Any],
    *,
    step_index: int,
) -> str | None:
    debug = {
        **dict(detector_match),
        "detector_center_tolerance_fraction": DETECTOR_CENTER_TOLERANCE_FRACTION,
        "detector_stop_min_bbox_area_fraction": DETECTOR_STOP_MIN_BBOX_AREA_FRACTION,
        "detector_stop_max_depth_m": DETECTOR_STOP_MAX_DEPTH_M,
        "detector_stop_max_depth_normalized": DETECTOR_STOP_MAX_DEPTH_NORMALIZED,
        "failed_detector_center_effect_count": len(
            state.failed_detector_center_effects
        ),
    }
    center_offset = detector_match.get("detector_center_offset_fraction")
    if center_offset is not None:
        center_offset = float(center_offset)
        if abs(center_offset) > DETECTOR_CENTER_TOLERANCE_FRACTION:
            action = _detector_center_action(
                center_offset,
                direction_sign=state.detector_center_direction_sign,
            )
            offset_sign = _detector_center_offset_sign(center_offset)
            failed_action = _failed_detector_center_action_for_offset(
                state,
                offset_sign=offset_sign,
            )
            if failed_action is not None and state.local_action_model is not None:
                failed_actions = _failed_detector_center_actions_for_offset(
                    state,
                    offset_sign=offset_sign,
                )
                candidates = [
                    action
                    for action in ("turn_left", "turn_right")
                    if action not in failed_actions
                ]
                if _center_depth_is_clear(observation.get("depth")):
                    candidates.insert(0, "move_forward")
                if not candidates:
                    debug["decision"] = "fallback_detector_target_blocked"
                    debug["fallback_reason"] = (
                        "no_learned_local_candidate_after_failed_center_loss"
                    )
                    debug["suppressed_detector_center_action"] = failed_action
                    debug["suppressed_detector_center_actions"] = failed_actions
                    debug["detector_center_offset_sign"] = offset_sign
                    state.memory_debug = debug
                    return None
                model_example = _local_action_model_example(
                    observation=observation,
                    detector_match=detector_match,
                    decision="learned_local_action_score",
                    suppressed_detector_center_action=failed_action,
                    suppressed_detector_center_actions=failed_actions,
                    history=state.local_action_history,
                )
                scores = score_official_local_action_candidates(
                    state.local_action_model,
                    model_example,
                    actions=tuple(candidates),
                )
                learned_action = str(scores.get("best_action") or candidates[0])
                if learned_action in {"turn_left", "turn_right"}:
                    state.last_detector_center_step = step_index
                    state.last_detector_center_action = learned_action
                    state.last_detector_center_offset_fraction = center_offset
                    state.last_detector_center_offset_sign = offset_sign
                state.blocked_turn_count = 0
                debug["decision"] = "learned_local_action_score"
                debug["suppressed_detector_center_action"] = failed_action
                debug["suppressed_detector_center_actions"] = failed_actions
                debug["detector_center_offset_sign"] = offset_sign
                debug["learned_local_action"] = learned_action
                debug["learned_local_label_name"] = scores.get("label_name")
                debug["learned_local_candidate_scores"] = scores.get("scores", {})
                debug["learned_local_temporal_features"] = (
                    _local_action_temporal_debug_features(model_example["features"])
                )
                state.memory_debug = debug
                return learned_action

            state.blocked_turn_count = 0
            state.last_detector_center_step = step_index
            state.last_detector_center_action = action
            state.last_detector_center_offset_fraction = center_offset
            state.last_detector_center_offset_sign = offset_sign
            debug["decision"] = "center_detector_target"
            debug["detector_center_direction_sign"] = (
                state.detector_center_direction_sign
            )
            debug["detector_center_offset_sign"] = offset_sign
            state.memory_debug = debug
            return action

    if _detector_stop_is_range_confirmed(detector_match):
        debug["decision"] = "stop_on_detector_range_confirmed"
        state.memory_debug = debug
        return "stop"

    if _center_depth_is_clear(observation.get("depth")):
        state.blocked_turn_count = 0
        debug["decision"] = "approach_detector_target"
        state.memory_debug = debug
        return "move_forward"

    debug["decision"] = "fallback_detector_target_blocked"
    debug["fallback_reason"] = "blocked_detector_approach_corridor"
    state.memory_debug = debug
    return None


def _select_detector_reacquire_action(
    state: OfficialPolicyState,
    *,
    step_index: int,
    record_failed_center_effect: bool = False,
) -> str | None:
    if state.last_detector_center_step is None:
        return None
    if step_index != state.last_detector_center_step + 1:
        return None
    if state.last_detector_center_action not in {"turn_left", "turn_right"}:
        return None
    if (
        record_failed_center_effect
        and state.last_detector_center_offset_sign is not None
    ):
        state.failed_detector_center_effects.add(
            (
                state.last_detector_center_action,
                state.last_detector_center_offset_sign,
            )
        )
    state.detector_center_direction_sign *= -1
    action = _opposite_turn(state.last_detector_center_action)
    state.blocked_turn_count = 0
    state.memory_debug = {
        "decision": "reacquire_detector_target",
        "detector_center_direction_sign": state.detector_center_direction_sign,
        "last_detector_center_action": state.last_detector_center_action,
        "last_detector_center_offset_fraction": (
            state.last_detector_center_offset_fraction
        ),
        "last_detector_center_offset_sign": state.last_detector_center_offset_sign,
        "failed_detector_center_effect_count": len(
            state.failed_detector_center_effects
        ),
        "detector_evidence_age_steps": step_index - state.last_detector_center_step,
    }
    return action


def _local_action_model_example(
    *,
    observation: Mapping[str, Any],
    detector_match: Mapping[str, Any],
    decision: str,
    suppressed_detector_center_action: str,
    suppressed_detector_center_actions: Sequence[str] = (),
    history: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]] = (),
) -> dict[str, Any]:
    x_m, z_m = _observation_xz(observation)
    center_offset = detector_match.get("detector_center_offset_fraction")
    center_offset_float = (
        float(center_offset) if center_offset is not None else None
    )
    current_evidence = {
        "target_visible": True,
        "target_match_count": 1,
        "detector_confidence": detector_match.get("detector_confidence"),
        "detector_bbox_area_fraction": detector_match.get(
            "detector_bbox_area_fraction"
        ),
        "detector_depth_median": detector_match.get("detector_depth_median"),
        "detector_center_offset_fraction": center_offset_float,
    }
    features = {
        "current_target_visible": True,
        "current_target_match_count": 1,
        "current_detector_confidence": detector_match.get("detector_confidence"),
        "current_bbox_area_fraction": detector_match.get(
            "detector_bbox_area_fraction"
        ),
        "current_center_offset_fraction": center_offset_float,
        "current_abs_center_offset_fraction": (
            abs(center_offset_float) if center_offset_float is not None else None
        ),
        "current_depth_median": detector_match.get("detector_depth_median"),
        "x_m": x_m,
        "z_m": z_m,
        "heading_rad": _observation_heading(observation),
        "suppressed_detector_center_action": suppressed_detector_center_action,
    }
    features.update(
        _local_action_temporal_features(
            current_evidence=current_evidence,
            history=history,
            suppressed_detector_center_actions=suppressed_detector_center_actions,
        )
    )
    return {
        "action": "move_forward",
        "decision": decision,
        "features": features,
    }


def _record_local_action_history(
    state: OfficialPolicyState,
    *,
    observation: Mapping[str, Any],
    step_index: int,
    action: str,
) -> None:
    debug = state.memory_debug if isinstance(state.memory_debug, Mapping) else {}
    x_m, z_m = _observation_xz(observation)
    step = {
        "step_index": step_index,
        "action": action,
        "decision": str(debug.get("decision", "")),
        "x_m": x_m,
        "z_m": z_m,
        "heading_rad": _observation_heading(observation),
    }
    state.local_action_history.append((step, _local_action_history_evidence(debug)))
    if len(state.local_action_history) > LOCAL_ACTION_HISTORY_STEPS:
        del state.local_action_history[:-LOCAL_ACTION_HISTORY_STEPS]


def _local_action_history_evidence(debug: Mapping[str, Any]) -> dict[str, Any]:
    target_visible = any(
        debug.get(key) is not None
        for key in (
            "detector_confidence",
            "detector_bbox",
            "detector_center_offset_fraction",
            "detector_bbox_area_fraction",
            "detector_depth_median",
        )
    )
    if not target_visible:
        return {
            "target_visible": False,
            "target_match_count": 0,
        }
    return {
        "target_visible": True,
        "target_match_count": 1,
        "detector_confidence": debug.get("detector_confidence"),
        "detector_bbox_area_fraction": debug.get("detector_bbox_area_fraction"),
        "detector_depth_median": debug.get("detector_depth_median"),
        "detector_center_offset_fraction": debug.get(
            "detector_center_offset_fraction"
        ),
    }


def _local_action_temporal_features(
    *,
    current_evidence: Mapping[str, Any],
    history: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    suppressed_detector_center_actions: Sequence[str],
) -> dict[str, Any]:
    recent_history = list(history)[-LOCAL_ACTION_HISTORY_STEPS:]
    previous_step, previous_evidence = (
        recent_history[-1] if recent_history else ({}, {})
    )
    current_offset = _optional_float(
        current_evidence.get("detector_center_offset_fraction")
    )
    previous_offset = _optional_float(
        previous_evidence.get("detector_center_offset_fraction")
    )
    current_abs_offset = abs(current_offset) if current_offset is not None else None
    previous_abs_offset = (
        abs(previous_offset) if previous_offset is not None else None
    )
    current_visible = bool(current_evidence.get("target_visible"))
    suppressed_actions = {
        str(action) for action in suppressed_detector_center_actions if str(action)
    }
    return {
        "suppressed_turn_left": "turn_left" in suppressed_actions,
        "suppressed_turn_right": "turn_right" in suppressed_actions,
        "history_observed_step_count": len(recent_history),
        "previous_target_visible": bool(previous_evidence.get("target_visible")),
        "recent_target_visible_count": sum(
            1 for _, evidence in recent_history if bool(evidence.get("target_visible"))
        )
        + (1 if current_visible else 0),
        "steps_since_last_target_visible": 0 if current_visible else None,
        "previous_action": str(previous_step.get("action", "")),
        "previous_decision": str(previous_step.get("decision", "")),
        "recent_move_forward_count": _recent_local_action_count(
            recent_history,
            "move_forward",
        ),
        "recent_turn_left_count": _recent_local_action_count(
            recent_history,
            "turn_left",
        ),
        "recent_turn_right_count": _recent_local_action_count(
            recent_history,
            "turn_right",
        ),
        "recent_reacquire_count": sum(
            1
            for step, _ in recent_history
            if str(step.get("decision", "")) == "reacquire_detector_target"
        ),
        "current_confidence_minus_previous": _delta(
            _optional_float(current_evidence.get("detector_confidence")),
            _optional_float(previous_evidence.get("detector_confidence")),
        ),
        "current_bbox_area_minus_previous": _delta(
            _optional_float(current_evidence.get("detector_bbox_area_fraction")),
            _optional_float(previous_evidence.get("detector_bbox_area_fraction")),
        ),
        "current_depth_minus_previous": _delta(
            _optional_float(current_evidence.get("detector_depth_median")),
            _optional_float(previous_evidence.get("detector_depth_median")),
        ),
        "current_abs_center_offset_minus_previous": _delta(
            current_abs_offset,
            previous_abs_offset,
        ),
    }


def _recent_local_action_count(
    history: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    action: str,
) -> int:
    return sum(1 for step, _ in history if str(step.get("action", "")) == action)


def _local_action_temporal_debug_features(
    features: Mapping[str, Any],
) -> dict[str, Any]:
    keys = (
        "history_observed_step_count",
        "previous_target_visible",
        "recent_target_visible_count",
        "steps_since_last_target_visible",
        "recent_move_forward_count",
        "recent_turn_left_count",
        "recent_turn_right_count",
        "recent_reacquire_count",
        "current_confidence_minus_previous",
        "current_bbox_area_minus_previous",
        "current_depth_minus_previous",
        "current_abs_center_offset_minus_previous",
        "suppressed_turn_left",
        "suppressed_turn_right",
    )
    return {key: features.get(key) for key in keys}


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(result):
        return None
    return result


def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None:
        return None
    return current - previous


def _detector_center_action(
    center_offset: float,
    *,
    direction_sign: int,
) -> str:
    positive_offset_action = "turn_right" if direction_sign >= 0 else "turn_left"
    negative_offset_action = "turn_left" if direction_sign >= 0 else "turn_right"
    return positive_offset_action if center_offset > 0.0 else negative_offset_action


def _detector_center_offset_sign(center_offset: float) -> int:
    return 1 if center_offset > 0.0 else -1


def _failed_detector_center_action_for_offset(
    state: OfficialPolicyState,
    *,
    offset_sign: int,
) -> str | None:
    for action in ("turn_left", "turn_right"):
        if (action, offset_sign) in state.failed_detector_center_effects:
            return action
    return None


def _failed_detector_center_actions_for_offset(
    state: OfficialPolicyState,
    *,
    offset_sign: int,
) -> list[str]:
    return [
        action
        for action in ("turn_left", "turn_right")
        if (action, offset_sign) in state.failed_detector_center_effects
    ]


def _opposite_turn(action: str) -> str:
    return "turn_left" if action == "turn_right" else "turn_right"


def _detector_stop_is_range_confirmed(detector_match: Mapping[str, Any]) -> bool:
    center_offset = detector_match.get("detector_center_offset_fraction")
    area_fraction = detector_match.get("detector_bbox_area_fraction")
    depth_median = detector_match.get("detector_depth_median")
    if center_offset is None or area_fraction is None or depth_median is None:
        return False
    if abs(float(center_offset)) > DETECTOR_CENTER_TOLERANCE_FRACTION:
        return False
    if float(area_fraction) < DETECTOR_STOP_MIN_BBOX_AREA_FRACTION:
        return False
    if bool(detector_match.get("detector_depth_is_normalized", False)):
        return float(depth_median) <= DETECTOR_STOP_MAX_DEPTH_NORMALIZED
    return float(depth_median) <= DETECTOR_STOP_MAX_DEPTH_M


def _detector_target_evidence(
    observation: Mapping[str, Any],
    bbox: Sequence[int] | None,
) -> dict[str, Any]:
    if bbox is None:
        return {}
    image_shape = _image_shape_2d(observation.get("rgb"))
    depth_frame = _depth_frame_2d(observation.get("depth"))
    if image_shape is None and depth_frame is None:
        return {}
    if image_shape is not None:
        height, width = image_shape
    else:
        height, width = int(depth_frame.shape[0]), int(depth_frame.shape[1])
    clipped = _clip_bbox_to_shape(bbox, height=height, width=width)
    if clipped is None:
        return {}
    x1, y1, x2, y2 = clipped
    payload: dict[str, Any] = {
        "detector_center_offset_fraction": float(
            (((x1 + x2) / 2.0) - (width / 2.0)) / width
        ),
        "detector_bbox_area_fraction": float(
            ((x2 - x1) * (y2 - y1)) / (width * height)
        ),
    }
    if depth_frame is None:
        return payload
    depth_bbox = _scale_bbox_between_shapes(
        clipped,
        from_height=height,
        from_width=width,
        to_height=depth_frame.shape[0],
        to_width=depth_frame.shape[1],
    )
    crop = depth_frame[depth_bbox[1] : depth_bbox[3], depth_bbox[0] : depth_bbox[2]]
    finite_positive = crop[np.isfinite(crop) & (crop > 0.0)]
    finite_frame = depth_frame[np.isfinite(depth_frame)]
    payload["detector_depth_is_normalized"] = bool(
        finite_frame.size and float(np.nanmax(finite_frame)) <= 1.0
    )
    if finite_positive.size:
        payload["detector_depth_median"] = float(np.median(finite_positive))
    return payload


def _image_shape_2d(image: Any) -> tuple[int, int] | None:
    if image is None:
        return None
    try:
        array = np.asarray(image)
    except (TypeError, ValueError):
        return None
    if array.ndim < 2:
        return None
    height, width = array.shape[:2]
    if height <= 0 or width <= 0:
        return None
    return int(height), int(width)


def _clip_bbox_to_shape(
    bbox: Sequence[int],
    *,
    height: int,
    width: int,
) -> tuple[int, int, int, int] | None:
    try:
        x1, y1, x2, y2 = bbox
    except (TypeError, ValueError):
        return None
    left = max(0, min(int(x1), width))
    top = max(0, min(int(y1), height))
    right = max(0, min(int(x2), width))
    bottom = max(0, min(int(y2), height))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _scale_bbox_between_shapes(
    bbox: tuple[int, int, int, int],
    *,
    from_height: int,
    from_width: int,
    to_height: int,
    to_width: int,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    scaled = (
        int(np.floor(x1 * to_width / from_width)),
        int(np.floor(y1 * to_height / from_height)),
        int(np.ceil(x2 * to_width / from_width)),
        int(np.ceil(y2 * to_height / from_height)),
    )
    clipped = _clip_bbox_to_shape(scaled, height=to_height, width=to_width)
    if clipped is None:
        return (0, 0, to_width, to_height)
    return clipped


def _normalize_object_label(label: str) -> str:
    return " ".join(str(label).lower().replace("_", " ").split())


def _detector_bbox_payload(bbox: Any) -> list[int] | None:
    if bbox is None:
        return None
    try:
        x1, y1, x2, y2 = bbox
    except (TypeError, ValueError):
        return None
    return [int(x1), int(y1), int(x2), int(y2)]


def _targetnav_goal_from_detector_match(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    detector_match: Mapping[str, Any],
    *,
    hfov_deg: float = 79.0,
    min_depth_m: float = 0.5,
    max_depth_m: float = 5.0,
) -> dict[str, Any] | None:
    bbox = detector_match.get("detector_bbox")
    if bbox is None:
        return None
    depth = _depth_frame_2d(observation.get("depth"))
    if depth is None:
        return None
    image_shape = _image_shape_2d(observation.get("rgb"))
    if image_shape is None:
        image_shape = (int(depth.shape[0]), int(depth.shape[1]))
    image_height, image_width = image_shape
    clipped = _clip_bbox_to_shape(bbox, height=image_height, width=image_width)
    if clipped is None:
        return None
    depth_bbox = _scale_bbox_between_shapes(
        clipped,
        from_height=image_height,
        from_width=image_width,
        to_height=depth.shape[0],
        to_width=depth.shape[1],
    )
    crop = depth[depth_bbox[1] : depth_bbox[3], depth_bbox[0] : depth_bbox[2]]
    finite = crop[np.isfinite(crop) & (crop > 0.0)]
    if finite.size == 0:
        return None
    finite_depth = depth[np.isfinite(depth)]
    normalized = bool(finite_depth.size and float(np.nanmax(finite_depth)) <= 1.0)
    depth_m = _depth_value_to_meters(
        float(np.median(finite)),
        normalized=normalized,
        min_depth_m=min_depth_m,
        max_depth_m=max_depth_m,
    )
    x1, _, x2, _ = clipped
    bbox_area_fraction = (
        float((clipped[2] - clipped[0]) * (clipped[3] - clipped[1]))
        / max(1.0, float(image_height * image_width))
    )
    bbox_touches_image_edge = (
        clipped[0] <= 0
        or clipped[1] <= 0
        or clipped[2] >= image_width
        or clipped[3] >= image_height
    )
    center_x = (x1 + x2 - 1) / 2.0
    horizontal_offset = (
        (center_x - (image_width - 1) / 2.0)
        / max(1.0, (image_width - 1) / 2.0)
    )
    bearing = horizontal_offset * np.deg2rad(hfov_deg) / 2.0
    current_x, current_z = _observation_xz(observation)
    heading = _observation_heading(observation)
    episode_angle = heading + bearing
    target_x = float(current_x + depth_m * np.sin(episode_angle))
    target_z = float(current_z + depth_m * np.cos(episode_angle))
    confidence = _optional_float(detector_match.get("detector_confidence"))
    depth_at_max_range = bool(depth_m >= max_depth_m * 0.98)
    return {
        "targetnav_estimator": "bbox_depth",
        "x_m": round(target_x, 6),
        "z_m": round(target_z, 6),
        "depth_m": round(float(depth_m), 6),
        "bearing_rad": round(float(bearing), 6),
        "detector_category": detector_match.get("detector_category"),
        "detector_confidence": detector_match.get("detector_confidence"),
        "bbox_area_fraction": round(bbox_area_fraction, 6),
        "bbox_touches_image_edge": bbox_touches_image_edge,
        "depth_at_max_range": depth_at_max_range,
        "targetnav_measurement_variance_m2": _targetnav_measurement_variance_m2(
            depth_m=depth_m,
            detector_confidence=confidence,
            depth_at_max_range=depth_at_max_range,
            bbox_touches_image_edge=bbox_touches_image_edge,
            bbox_area_fraction=bbox_area_fraction,
        ),
        "scene_id": state.scene_id,
        "object_category": state.object_category,
    }


def _targetnav_goal_from_memory_anchor(anchor: OfficialMemoryAnchor) -> dict[str, Any]:
    return {
        "targetnav_estimator": "memory_anchor",
        "x_m": float(anchor.x_m),
        "z_m": float(anchor.z_m),
        "y_m": float(anchor.y_m) if anchor.y_m is not None else None,
        "object_category": anchor.object_category,
        "scene_id": anchor.scene_id,
        "episode_id": anchor.episode_id,
        "confidence": float(anchor.confidence),
        "source": anchor.source,
        "coordinate_frame": anchor.coordinate_frame,
    }


def _memory_anchor_debug_payload(anchor: OfficialMemoryAnchor) -> dict[str, Any]:
    return {
        "object_category": anchor.object_category,
        "scene_id": anchor.scene_id,
        "episode_id": anchor.episode_id,
        "source": anchor.source,
        "confidence": float(anchor.confidence),
        "coordinate_frame": anchor.coordinate_frame,
        "x_m": float(anchor.x_m),
        "y_m": float(anchor.y_m) if anchor.y_m is not None else None,
        "z_m": float(anchor.z_m),
    }


def _memory_anchor_oracle_goal_position(
    state: OfficialPolicyState,
    anchor: OfficialMemoryAnchor,
) -> tuple[float, float, float] | None:
    if anchor.coordinate_frame != "episode_start_relative":
        return None
    if state.episode_start_position is None or state.episode_start_rotation is None:
        return None
    world = _episode_relative_xz_to_world_position(
        x_m=float(anchor.x_m),
        z_m=float(anchor.z_m),
        start_position=state.episode_start_position,
        start_rotation=state.episode_start_rotation,
    )
    if anchor.y_m is None:
        return world
    return world[0], state.episode_start_position[1] + float(anchor.y_m), world[2]


def _smooth_targetnav_goal(
    previous_goal: Mapping[str, Any] | None,
    current_goal: Mapping[str, Any],
    *,
    alpha: float = TARGETNAV_GOAL_SMOOTHING_ALPHA,
) -> dict[str, Any]:
    if previous_goal is None:
        goal = dict(current_goal)
        goal["smoothing_sample_count"] = 1
        measurement_variance = _optional_float(
            goal.get("targetnav_measurement_variance_m2")
        )
        if measurement_variance is not None:
            goal["targetnav_position_variance_m2"] = round(measurement_variance, 6)
        return goal
    if _uses_targetnav_probabilistic_update(previous_goal, current_goal):
        return _smooth_targetnav_goal_probabilistic(previous_goal, current_goal)
    weight = min(max(float(alpha), 0.0), 1.0)
    smoothed = dict(current_goal)
    for key in ("x_m", "z_m", "depth_m", "bearing_rad"):
        previous_value = _optional_float(previous_goal.get(key))
        current_value = _optional_float(current_goal.get(key))
        if previous_value is None or current_value is None:
            continue
        smoothed[key] = round(
            (1.0 - weight) * previous_value + weight * current_value,
            6,
        )
    previous_count = int(previous_goal.get("smoothing_sample_count", 1) or 1)
    smoothed["smoothing_sample_count"] = previous_count + 1
    smoothed["targetnav_estimator"] = "bbox_depth_smoothed"
    smoothed["raw_target_goal"] = dict(current_goal)
    return smoothed


def _uses_targetnav_probabilistic_update(
    previous_goal: Mapping[str, Any],
    current_goal: Mapping[str, Any],
) -> bool:
    return (
        "targetnav_position_variance_m2" in previous_goal
        or "targetnav_measurement_variance_m2" in current_goal
    )


def _smooth_targetnav_goal_probabilistic(
    previous_goal: Mapping[str, Any],
    current_goal: Mapping[str, Any],
) -> dict[str, Any]:
    previous_variance = _optional_float(
        previous_goal.get("targetnav_position_variance_m2")
    )
    if previous_variance is None:
        previous_variance = _targetnav_measurement_variance_from_goal(previous_goal)
    measurement_variance = _optional_float(
        current_goal.get("targetnav_measurement_variance_m2")
    )
    if measurement_variance is None:
        measurement_variance = _targetnav_measurement_variance_from_goal(current_goal)
    previous_variance = max(previous_variance, TARGETNAV_MIN_MEASUREMENT_VARIANCE_M2)
    measurement_variance = max(
        measurement_variance,
        TARGETNAV_MIN_MEASUREMENT_VARIANCE_M2,
    )
    update_gain = previous_variance / (previous_variance + measurement_variance)
    smoothed = dict(current_goal)
    for key in ("x_m", "z_m", "depth_m"):
        previous_value = _optional_float(previous_goal.get(key))
        current_value = _optional_float(current_goal.get(key))
        if previous_value is None or current_value is None:
            continue
        smoothed[key] = round(
            previous_value + update_gain * (current_value - previous_value),
            6,
        )
    previous_bearing = _optional_float(previous_goal.get("bearing_rad"))
    current_bearing = _optional_float(current_goal.get("bearing_rad"))
    if previous_bearing is not None and current_bearing is not None:
        smoothed["bearing_rad"] = round(
            previous_bearing
            + update_gain * _wrap_angle(current_bearing - previous_bearing),
            6,
        )
    previous_count = int(previous_goal.get("smoothing_sample_count", 1) or 1)
    smoothed["smoothing_sample_count"] = previous_count + 1
    smoothed["targetnav_estimator"] = "bbox_depth_robust_smoothed"
    smoothed["raw_target_goal"] = dict(current_goal)
    smoothed["targetnav_update_gain"] = round(float(update_gain), 6)
    smoothed["targetnav_position_variance_m2"] = round(
        float((1.0 - update_gain) * previous_variance),
        6,
    )
    return smoothed


def _targetnav_measurement_variance_from_goal(goal: Mapping[str, Any]) -> float:
    return _targetnav_measurement_variance_m2(
        depth_m=_optional_float(goal.get("depth_m")),
        detector_confidence=_optional_float(goal.get("detector_confidence")),
        depth_at_max_range=bool(goal.get("depth_at_max_range", False)),
        bbox_touches_image_edge=bool(goal.get("bbox_touches_image_edge", False)),
        bbox_area_fraction=_optional_float(goal.get("bbox_area_fraction")),
    )


def _targetnav_measurement_variance_m2(
    *,
    depth_m: float | None,
    detector_confidence: float | None,
    depth_at_max_range: bool = False,
    bbox_touches_image_edge: bool = False,
    bbox_area_fraction: float | None = None,
) -> float:
    depth = max(0.0, float(depth_m)) if depth_m is not None else 5.0
    confidence = min(max(float(detector_confidence or 0.0), 0.0), 1.0)
    depth_variance = (0.2 * depth + 0.05) ** 2
    confidence_variance = (1.0 - confidence) * 2.0
    edge_variance = 1.0 if bbox_touches_image_edge else 0.0
    area_variance = 0.0
    if bbox_area_fraction is not None and bbox_area_fraction < 0.01:
        area_variance = 1.0
    max_range_variance = TARGETNAV_MAX_RANGE_VARIANCE_M2 if depth_at_max_range else 0.0
    return round(
        max(
            TARGETNAV_MIN_MEASUREMENT_VARIANCE_M2,
            depth_variance
            + confidence_variance
            + edge_variance
            + area_variance
            + max_range_variance,
        ),
        6,
    )


def _targetnav_pointgoal_with_gps_compass(
    observation: Mapping[str, Any],
    target_goal: Mapping[str, Any],
) -> list[float] | None:
    x_m = _optional_float(target_goal.get("x_m"))
    z_m = _optional_float(target_goal.get("z_m"))
    if x_m is None or z_m is None:
        return None
    current_x, current_z = _observation_xz(observation)
    delta_x = float(x_m - current_x)
    delta_z = float(z_m - current_z)
    distance = float(np.hypot(delta_x, delta_z))
    if not np.isfinite(distance):
        return None
    bearing = float(np.arctan2(delta_x, delta_z))
    relative_bearing = _wrap_angle(bearing - _observation_heading(observation))
    return [
        round(distance, 6),
        round(float(-relative_bearing), 6),
    ]


def _select_targetnav_fmm_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    target_goal: Mapping[str, Any],
    *,
    step_index: int,
) -> str | None:
    if state.occupancy_map is None:
        state.occupancy_map = create_occupancy_frontier_map()
    update_occupancy_frontier_map(state.occupancy_map, observation)
    x_m = _optional_float(target_goal.get("x_m"))
    z_m = _optional_float(target_goal.get("z_m"))
    if x_m is None or z_m is None:
        state.targetnav_debug = {
            "backend": "fmm_grid",
            "fallback_reason": "missing_target_coordinate",
        }
        return None
    frontier_map = state.occupancy_map
    current_x, current_z = _observation_xz(observation)
    start_cell = _world_to_grid_cell(frontier_map, x_m=current_x, z_m=current_z)
    target_cell = _world_to_grid_cell(frontier_map, x_m=x_m, z_m=z_m)
    pointgoal = _targetnav_pointgoal_with_gps_compass(observation, target_goal)
    selected_cell = _nearest_reachable_free_cell_to_target(
        frontier_map,
        start_cell=start_cell,
        target_cell=target_cell,
    )
    if selected_cell is None:
        state.targetnav_debug = {
            "backend": "fmm_grid",
            "target_cell": list(target_cell),
            "fallback_reason": "no_reachable_free_target_cell",
        }
        return None
    distance_field = _targetnav_distance_field(frontier_map, selected_cell)
    next_cell = _targetnav_fmm_next_cell(frontier_map, start_cell, distance_field)
    if next_cell is None:
        state.targetnav_debug = {
            "backend": "fmm_grid",
            "target_cell": list(target_cell),
            "selected_target_cell": list(selected_cell),
            "fallback_reason": "no_fmm_path",
        }
        return None
    blocked_forward_cell: tuple[int, int] | None = None
    replanned_after_blocked_forward = False
    depth = observation.get("depth")
    if (
        next_cell != start_cell
        and depth is not None
        and not _center_depth_is_clear(depth)
    ):
        forward_cell = _forward_grid_cell(frontier_map, observation)
        if next_cell == forward_cell:
            blocked_forward_cell = forward_cell
            _mark_cell(frontier_map, forward_cell, OCCUPANCY_OCCUPIED)
            temporary_grid = np.array(frontier_map.grid, copy=True)
            row, col = forward_cell
            if 0 <= row < temporary_grid.shape[0] and 0 <= col < temporary_grid.shape[1]:
                temporary_grid[row, col] = OCCUPANCY_OCCUPIED
            replanned_field = _targetnav_distance_field(
                frontier_map,
                selected_cell,
                grid=temporary_grid,
            )
            replanned_next = _targetnav_fmm_next_cell(
                frontier_map,
                start_cell,
                replanned_field,
                grid=temporary_grid,
            )
            if replanned_next is None or replanned_next == forward_cell:
                state.targetnav_debug = {
                    "backend": "fmm_grid",
                    "target_cell": list(target_cell),
                    "selected_target_cell": list(selected_cell),
                    "blocked_forward_cell": list(forward_cell),
                    "fallback_reason": "blocked_forward_no_fmm_alternative",
                }
                return None
            distance_field = replanned_field
            next_cell = replanned_next
            replanned_after_blocked_forward = True
    if next_cell == start_cell:
        target_distance_m = _targetnav_pointgoal_distance_m(
            pointgoal,
            target_goal=target_goal,
            current_x=current_x,
            current_z=current_z,
        )
        stop_radius_m = max(
            float(state.memory_stop_radius_m),
            float(frontier_map.cell_size_m),
        )
        if target_distance_m is None or target_distance_m > stop_radius_m:
            state.targetnav_goal = dict(target_goal)
            state.targetnav_debug = {
                "backend": "fmm_grid",
                "target_cell": list(target_cell),
                "selected_target_cell": list(selected_cell),
                "selected_next_cell": list(next_cell),
                "current_distance_cells": (
                    None
                    if not np.isfinite(distance_field[start_cell])
                    else int(distance_field[start_cell])
                ),
                "last_step": step_index,
                "target_goal": dict(target_goal),
                "pointgoal_with_gps_compass": pointgoal,
                "target_distance_m": target_distance_m,
                "stop_radius_m": stop_radius_m,
                "fallback_reason": "selected_current_cell_far_from_target",
            }
            return None
        action = "stop"
        decision = "targetnav_fmm_stop"
    else:
        action = _turn_or_move_toward_grid_cell(
            observation,
            state,
            frontier_map,
            next_cell=next_cell,
        )
        decision = "targetnav_fmm_move" if action == "move_forward" else "targetnav_fmm_turn"
    state.targetnav_goal = dict(target_goal)
    debug = {
        "backend": "fmm_grid",
        "target_cell": list(target_cell),
        "selected_target_cell": list(selected_cell),
        "selected_next_cell": list(next_cell),
        "current_distance_cells": (
            None
            if not np.isfinite(distance_field[start_cell])
            else int(distance_field[start_cell])
        ),
        "last_step": step_index,
        "last_action": action,
        "target_goal": dict(target_goal),
        "pointgoal_with_gps_compass": pointgoal,
        "replanned_after_blocked_forward": replanned_after_blocked_forward,
    }
    if blocked_forward_cell is not None:
        debug["blocked_forward_cell"] = list(blocked_forward_cell)
    state.targetnav_debug = debug
    state.memory_debug = {
        "decision": decision,
        "targetnav_backend": "fmm_grid",
        "targetnav_action": action,
    }
    return action


def _select_targetnav_ddppo_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    target_goal: Mapping[str, Any],
    *,
    step_index: int,
) -> str | None:
    backend = state.targetnav_ddppo_backend
    if backend is None:
        state.targetnav_debug = {
            "backend": "ddppo_pointnav",
            "fallback_reason": "ddppo_backend_unavailable",
        }
        return None
    pointgoal = _targetnav_pointgoal_with_gps_compass(observation, target_goal)
    if pointgoal is None:
        state.targetnav_debug = {
            "backend": "ddppo_pointnav",
            "target_goal": dict(target_goal),
            "fallback_reason": "missing_pointgoal",
        }
        return None
    depth = observation.get("depth")
    if depth is None:
        state.targetnav_debug = {
            "backend": "ddppo_pointnav",
            "target_goal": dict(target_goal),
            "pointgoal_with_gps_compass": pointgoal,
            "fallback_reason": "missing_depth",
        }
        return None
    try:
        action_id = int(
            backend.act(
                depth=depth,
                pointgoal_with_gps_compass=pointgoal,
            )
        )
    except Exception as exc:
        state.targetnav_debug = {
            "backend": "ddppo_pointnav",
            "target_goal": dict(target_goal),
            "pointgoal_with_gps_compass": pointgoal,
            "fallback_reason": "ddppo_backend_error",
            "error": str(exc),
        }
        return None
    action = _ddppo_action_name(action_id)
    if action is None:
        state.targetnav_debug = {
            "backend": "ddppo_pointnav",
            "target_goal": dict(target_goal),
            "pointgoal_with_gps_compass": pointgoal,
            "action_id": action_id,
            "fallback_reason": "invalid_ddppo_action",
        }
        return None
    state.targetnav_goal = dict(target_goal)
    state.targetnav_debug = {
        "backend": "ddppo_pointnav",
        "last_step": step_index,
        "last_action": action,
        "action_id": action_id,
        "target_goal": dict(target_goal),
        "pointgoal_with_gps_compass": pointgoal,
    }
    decision = (
        "targetnav_ddppo_stop"
        if action == "stop"
        else "targetnav_ddppo_move"
        if action == "move_forward"
        else "targetnav_ddppo_turn"
    )
    state.memory_debug = {
        "decision": decision,
        "targetnav_backend": "ddppo_pointnav",
        "targetnav_action": action,
    }
    return action


def _ddppo_action_name(action_id: int) -> str | None:
    return {
        0: "stop",
        1: "move_forward",
        2: "turn_left",
        3: "turn_right",
    }.get(action_id)


def _targetnav_pointgoal_distance_m(
    pointgoal: Sequence[float] | None,
    *,
    target_goal: Mapping[str, Any],
    current_x: float,
    current_z: float,
) -> float | None:
    if pointgoal is not None:
        try:
            distance = float(np.asarray(pointgoal, dtype=float).reshape(-1)[0])
            if np.isfinite(distance):
                return distance
        except (IndexError, TypeError, ValueError):
            pass
    x_m = _optional_float(target_goal.get("x_m"))
    z_m = _optional_float(target_goal.get("z_m"))
    if x_m is None or z_m is None:
        return None
    distance = float(np.hypot(x_m - current_x, z_m - current_z))
    return distance if np.isfinite(distance) else None


def _targetnav_distance_field(
    frontier_map: OccupancyFrontierMap,
    goal_cell: tuple[int, int],
    *,
    grid: np.ndarray | None = None,
) -> np.ndarray:
    occupancy = frontier_map.grid if grid is None else grid
    distances = np.full(occupancy.shape, np.inf, dtype=float)
    if not _cell_is_free_in_grid(occupancy, goal_cell):
        return distances
    queue: deque[tuple[int, int]] = deque([goal_cell])
    distances[goal_cell] = 0.0
    while queue:
        cell = queue.popleft()
        for neighbor in _grid_neighbors(frontier_map, cell):
            if not _cell_is_free_in_grid(occupancy, neighbor):
                continue
            if np.isfinite(distances[neighbor]):
                continue
            distances[neighbor] = distances[cell] + 1.0
            queue.append(neighbor)
    return distances


def _targetnav_fmm_next_cell(
    frontier_map: OccupancyFrontierMap,
    start_cell: tuple[int, int],
    distance_field: np.ndarray,
    *,
    grid: np.ndarray | None = None,
) -> tuple[int, int] | None:
    occupancy = frontier_map.grid if grid is None else grid
    if not _cell_is_free_in_grid(occupancy, start_cell):
        return None
    if not np.isfinite(distance_field[start_cell]):
        return None
    if float(distance_field[start_cell]) == 0.0:
        return start_cell
    candidates = [
        neighbor
        for neighbor in _grid_neighbors(frontier_map, start_cell)
        if _cell_is_free_in_grid(occupancy, neighbor)
        and np.isfinite(distance_field[neighbor])
        and distance_field[neighbor] < distance_field[start_cell]
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda cell: (float(distance_field[cell]), cell[0], cell[1]))
    return candidates[0]


def _forward_grid_cell(
    frontier_map: OccupancyFrontierMap,
    observation: Mapping[str, Any],
) -> tuple[int, int]:
    current_x, current_z = _observation_xz(observation)
    heading = _observation_heading(observation)
    return _world_to_grid_cell(
        frontier_map,
        x_m=current_x + np.sin(heading) * frontier_map.cell_size_m,
        z_m=current_z + np.cos(heading) * frontier_map.cell_size_m,
    )


def _cell_is_free_in_grid(grid: np.ndarray, cell: tuple[int, int]) -> bool:
    row, col = cell
    if row < 0 or col < 0:
        return False
    if row >= grid.shape[0] or col >= grid.shape[1]:
        return False
    return int(grid[row, col]) == OCCUPANCY_FREE


def _select_targetnav_occupancy_action(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    target_goal: Mapping[str, Any],
    *,
    step_index: int,
) -> str | None:
    if state.occupancy_map is None:
        state.occupancy_map = create_occupancy_frontier_map()
    update_occupancy_frontier_map(state.occupancy_map, observation)
    x_m = _optional_float(target_goal.get("x_m"))
    z_m = _optional_float(target_goal.get("z_m"))
    if x_m is None or z_m is None:
        state.targetnav_debug = {
            "backend": "occupancy_grid",
            "fallback_reason": "missing_target_coordinate",
        }
        return None
    frontier_map = state.occupancy_map
    current_x, current_z = _observation_xz(observation)
    start_cell = _world_to_grid_cell(frontier_map, x_m=current_x, z_m=current_z)
    target_cell = _world_to_grid_cell(frontier_map, x_m=x_m, z_m=z_m)
    selected_cell = _nearest_reachable_free_cell_to_target(
        frontier_map,
        start_cell=start_cell,
        target_cell=target_cell,
    )
    if selected_cell is None:
        state.targetnav_debug = {
            "backend": "occupancy_grid",
            "target_cell": list(target_cell),
            "fallback_reason": "no_reachable_free_target_cell",
        }
        return None
    path = _shortest_occupancy_path(frontier_map, start_cell, selected_cell)
    if not path:
        state.targetnav_debug = {
            "backend": "occupancy_grid",
            "target_cell": list(target_cell),
            "selected_target_cell": list(selected_cell),
            "fallback_reason": "no_occupancy_path",
        }
        return None
    if len(path) <= 1:
        action = "stop"
        decision = "targetnav_occupancy_stop"
    else:
        action = _turn_or_move_toward_grid_cell(
            observation,
            state,
            frontier_map,
            next_cell=path[1],
        )
        decision = (
            "targetnav_occupancy_move"
            if action == "move_forward"
            else "targetnav_occupancy_turn"
        )
    state.targetnav_goal = dict(target_goal)
    state.targetnav_debug = {
        "backend": "occupancy_grid",
        "target_cell": list(target_cell),
        "selected_target_cell": list(selected_cell),
        "path_length_cells": len(path),
        "last_step": step_index,
        "last_action": action,
        "target_goal": dict(target_goal),
    }
    state.memory_debug = {
        "decision": decision,
        "targetnav_backend": "occupancy_grid",
        "targetnav_action": action,
    }
    return action


def _nearest_reachable_free_cell_to_target(
    frontier_map: OccupancyFrontierMap,
    *,
    start_cell: tuple[int, int],
    target_cell: tuple[int, int],
) -> tuple[int, int] | None:
    free_cells = [
        (int(row), int(col))
        for row, col in zip(*np.nonzero(frontier_map.grid == OCCUPANCY_FREE))
    ]
    free_cells.sort(
        key=lambda cell: (
            abs(cell[0] - target_cell[0]) + abs(cell[1] - target_cell[1]),
            abs(cell[0] - start_cell[0]) + abs(cell[1] - start_cell[1]),
        )
    )
    for cell in free_cells:
        if _shortest_occupancy_path(frontier_map, start_cell, cell):
            return cell
    return None


def _shortest_occupancy_path(
    frontier_map: OccupancyFrontierMap,
    start_cell: tuple[int, int],
    goal_cell: tuple[int, int],
) -> list[tuple[int, int]]:
    if not _cell_is_free(frontier_map, start_cell) or not _cell_is_free(
        frontier_map, goal_cell
    ):
        return []
    queue: deque[tuple[int, int]] = deque([start_cell])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start_cell: None}
    while queue:
        cell = queue.popleft()
        if cell == goal_cell:
            break
        for neighbor in _grid_neighbors(frontier_map, cell):
            if neighbor in previous or not _cell_is_free(frontier_map, neighbor):
                continue
            previous[neighbor] = cell
            queue.append(neighbor)
    if goal_cell not in previous:
        return []
    path: list[tuple[int, int]] = []
    cell: tuple[int, int] | None = goal_cell
    while cell is not None:
        path.append(cell)
        cell = previous[cell]
    path.reverse()
    return path


def _grid_neighbors(
    frontier_map: OccupancyFrontierMap,
    cell: tuple[int, int],
) -> tuple[tuple[int, int], ...]:
    row, col = cell
    candidates = (
        (row - 1, col),
        (row + 1, col),
        (row, col - 1),
        (row, col + 1),
    )
    max_row, max_col = frontier_map.grid.shape
    return tuple(
        candidate
        for candidate in candidates
        if 0 <= candidate[0] < max_row and 0 <= candidate[1] < max_col
    )


def _cell_is_free(
    frontier_map: OccupancyFrontierMap,
    cell: tuple[int, int],
) -> bool:
    row, col = cell
    if row < 0 or col < 0:
        return False
    if row >= frontier_map.grid.shape[0] or col >= frontier_map.grid.shape[1]:
        return False
    return int(frontier_map.grid[row, col]) == OCCUPANCY_FREE


def _turn_or_move_toward_grid_cell(
    observation: Mapping[str, Any],
    state: OfficialPolicyState,
    frontier_map: OccupancyFrontierMap,
    *,
    next_cell: tuple[int, int],
) -> str:
    next_x, next_z = _grid_cell_to_world(frontier_map, next_cell)
    current_x, current_z = _observation_xz(observation)
    bearing = float(np.arctan2(next_x - current_x, next_z - current_z))
    heading = _observation_heading(observation)
    bearing_error = _wrap_angle(bearing - heading)
    if abs(bearing_error) > state.memory_bearing_tolerance_rad:
        return "turn_right" if bearing_error > 0.0 else "turn_left"
    depth = observation.get("depth")
    if depth is None or _center_depth_is_clear(depth):
        return "move_forward"
    return state.blocked_turn_action


def _grid_cell_to_world(
    frontier_map: OccupancyFrontierMap,
    cell: tuple[int, int],
) -> tuple[float, float]:
    origin_row, origin_col = frontier_map.origin_cell
    row, col = cell
    x_m = (col - origin_col) * frontier_map.cell_size_m
    z_m = (origin_row - row) * frontier_map.cell_size_m
    return float(x_m), float(z_m)


def _make_shortest_path_follower(env: Any, *, goal_radius_m: float) -> Any | None:
    sim = getattr(env, "sim", None)
    if sim is None:
        return None
    try:
        from habitat.tasks.nav.shortest_path_follower import ShortestPathFollower
    except Exception:
        return None
    try:
        return ShortestPathFollower(
            sim,
            goal_radius=float(goal_radius_m),
            return_one_hot=False,
        )
    except Exception:
        return None


def _make_habitat_oracle_follower_backend(
    env: Any,
    *,
    goal_radius_m: float,
) -> HabitatOracleFollowerBackend:
    return HabitatOracleFollowerBackend(
        env,
        goal_radius_m=goal_radius_m,
        backend_id="pathfinder_suffix_oracle",
    )


def _episode_goal_positions(episode: Any) -> tuple[tuple[float, float, float], ...]:
    positions: list[tuple[float, float, float]] = []
    for goal in getattr(episode, "goals", ()) or ():
        for viewpoint in getattr(goal, "view_points", ()) or ():
            agent_state = getattr(viewpoint, "agent_state", viewpoint)
            position = _tuple3_position(getattr(agent_state, "position", None))
            if position is not None:
                positions.append(position)
        position = _tuple3_position(getattr(goal, "position", None))
        if position is not None:
            positions.append(position)
    return tuple(positions)


def _tuple3_position(position: Any) -> tuple[float, float, float] | None:
    if position is None:
        return None
    try:
        values = tuple(float(value) for value in position)
    except (TypeError, ValueError):
        return None
    if len(values) != 3 or not all(np.isfinite(value) for value in values):
        return None
    return values


def _tuple4_values(values: Any) -> tuple[float, float, float, float] | None:
    if values is None:
        return None
    try:
        parsed = tuple(float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if len(parsed) != 4 or not all(np.isfinite(value) for value in parsed):
        return None
    return parsed


def _episode_relative_xz_to_world_position(
    *,
    x_m: float,
    z_m: float,
    start_position: tuple[float, float, float],
    start_rotation: tuple[float, float, float, float],
) -> tuple[float, float, float]:
    yaw = _yaw_from_quaternion_xyzw(start_rotation)
    right = np.asarray((np.cos(yaw), 0.0, -np.sin(yaw)), dtype=float)
    forward = np.asarray((-np.sin(yaw), 0.0, -np.cos(yaw)), dtype=float)
    delta = (float(x_m) * right) + (float(z_m) * forward)
    world = np.asarray(start_position, dtype=float) + delta
    return float(world[0]), float(world[1]), float(world[2])


def _yaw_from_quaternion_xyzw(
    rotation: tuple[float, float, float, float],
) -> float:
    x, y, z, w = _normalize_quaternion_xyzw(rotation)
    siny_cosp = 2.0 * (w * y + x * z)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return float(np.arctan2(siny_cosp, cosy_cosp))


def _normalize_quaternion_xyzw(
    rotation: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    norm = float(np.sqrt(sum(float(value) * float(value) for value in rotation)))
    if norm == 0.0:
        return 0.0, 0.0, 0.0, 1.0
    return tuple(float(value) / norm for value in rotation)  # type: ignore[return-value]


def _nearest_goal_position(
    env: Any,
    positions: Sequence[tuple[float, float, float]],
) -> tuple[float, float, float] | None:
    if not positions:
        return None
    current_position = _sim_agent_position(env)
    if current_position is None:
        return tuple(positions[0])
    return min(
        positions,
        key=lambda position: _goal_distance(env, current_position, position),
    )


def _sim_agent_position(env: Any) -> tuple[float, float, float] | None:
    sim = getattr(env, "sim", None)
    if sim is None:
        return None
    state = None
    if hasattr(sim, "get_agent_state"):
        try:
            state = sim.get_agent_state()
        except Exception:
            state = None
    if state is None and hasattr(sim, "get_agent"):
        try:
            agent = sim.get_agent(0)
            state = agent.get_state()
        except Exception:
            state = None
    return _tuple3_position(getattr(state, "position", None))


def _goal_distance(
    env: Any,
    current_position: tuple[float, float, float],
    goal_position: tuple[float, float, float],
) -> float:
    sim = getattr(env, "sim", None)
    pathfinder = getattr(sim, "pathfinder", None)
    if pathfinder is not None and hasattr(pathfinder, "geodesic_distance"):
        try:
            distance = float(pathfinder.geodesic_distance(current_position, goal_position))
            if np.isfinite(distance):
                return distance
        except Exception:
            pass
    return float(np.linalg.norm(np.asarray(goal_position) - np.asarray(current_position)))


def _follower_action_name(action: Any) -> str:
    if action is None:
        return "stop"
    if isinstance(action, str):
        return action
    action_names = {
        0: "stop",
        1: "move_forward",
        2: "turn_left",
        3: "turn_right",
    }
    array = np.asarray(action)
    if array.ndim > 0 and array.size > 1:
        action_id = int(np.argmax(array))
        return action_names.get(action_id, str(action_id))
    if array.size == 1:
        try:
            action_id = int(array.reshape(-1)[0])
        except (TypeError, ValueError):
            return str(action)
        return action_names.get(action_id, str(action_id))
    return str(action)


def _controller_backend_status(controller: Any) -> NavigationBackendStatus | None:
    backend_status = getattr(controller, "backend_status", None)
    if not callable(backend_status):
        return None
    status = backend_status()
    return status if isinstance(status, NavigationBackendStatus) else None


def _navigation_backend_status_payload(
    status: NavigationBackendStatus,
) -> dict[str, Any]:
    return {
        "backend_id": status.backend_id,
        "status": status.status.value,
        "active_goal_id": status.active_goal_id,
        "reason": status.reason,
        "metadata": dict(status.metadata),
    }


def _policy_kind(policy: str) -> str:
    if policy == "memory_active_perception_frontier_pathfinder_suffix":
        return "memory_active_perception_frontier_pathfinder_suffix_diagnostic"
    if policy == "no_memory_targetnav":
        return "no_memory_targetnav"
    if policy == "naive_count_targetnav":
        return "naive_count_targetnav"
    if policy == "memory_active_perception_frontier_targetnav_ddppo":
        return "memory_active_perception_frontier_targetnav_ddppo"
    if policy == "memory_active_perception_frontier_targetnav_fmm":
        return "memory_active_perception_frontier_targetnav_fmm"
    if policy == "memory_active_perception_frontier_targetnav":
        return "memory_active_perception_frontier_targetnav"
    if policy == "memory_learned_local_frontier":
        return "memory_learned_local_frontier_active_search"
    if policy == "memory_active_perception_frontier":
        return "memory_active_perception_frontier_active_search"
    if policy == "memory_evidence_frontier":
        return "memory_evidence_frontier_active_search"
    if policy == "memory_belief_frontier":
        return "memory_belief_frontier_active_search"
    if policy == "memory_guided_frontier":
        return "memory_guided_occupancy_frontier"
    if policy == "occupancy_frontier":
        return "target_agnostic_occupancy_frontier_baseline"
    if policy == "frontier_only":
        return "target_agnostic_depth_frontier_baseline"
    if policy in {"noop", "random"}:
        return "trivial_protocol_smoke"
    return "unknown"


def _policy_debug_payload(state: OfficialPolicyState) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if state.occupancy_map is not None:
        payload["occupancy_frontier"] = occupancy_frontier_counts(state.occupancy_map)
    if state.selected_frontier_bearing_rad is not None:
        payload["occupancy_frontier"]["selected_bearing_rad"] = (
            state.selected_frontier_bearing_rad
        )
    if state.memory_debug is not None:
        payload["memory_prior"] = dict(state.memory_debug)
    if state.pathfinder_suffix_debug is not None:
        payload["pathfinder_suffix"] = dict(state.pathfinder_suffix_debug)
    if state.targetnav_debug is not None:
        payload["targetnav"] = dict(state.targetnav_debug)
    return payload


def _center_depth_is_clear(depth: Any) -> bool:
    if depth is None:
        return False
    try:
        array = np.asarray(depth, dtype=float)
    except (TypeError, ValueError):
        return False
    if array.size == 0:
        return False
    array = np.squeeze(array)
    if array.ndim != 2:
        return False
    height, width = array.shape
    row_start = height // 3
    row_end = max(row_start + 1, (2 * height) // 3)
    col_start = width // 3
    col_end = max(col_start + 1, (2 * width) // 3)
    center = array[row_start:row_end, col_start:col_end]
    finite = np.isfinite(center)
    if not bool(finite.any()):
        return False
    finite_depth = array[np.isfinite(array)]
    threshold = (
        FRONTIER_CLEAR_DEPTH_NORMALIZED
        if finite_depth.size and float(np.nanmax(finite_depth)) <= 1.0
        else FRONTIER_CLEAR_DEPTH_M
    )
    clear = np.logical_and(finite, center >= threshold)
    return float(clear.sum()) / float(finite.sum()) >= FRONTIER_CLEAR_FRACTION


def _depth_frame_2d(depth: Any) -> np.ndarray | None:
    if depth is None:
        return None
    try:
        array = np.asarray(depth, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.size == 0:
        return None
    array = np.squeeze(array)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.ndim != 2:
        return None
    return array


def _depth_value_to_meters(
    value: float,
    *,
    normalized: bool,
    min_depth_m: float,
    max_depth_m: float,
) -> float:
    if normalized:
        clipped = min(max(value, 0.0), 1.0)
        return min_depth_m + clipped * (max_depth_m - min_depth_m)
    return min(max(value, min_depth_m), max_depth_m)


def _sample_depth_columns(width: int, sample_columns: int) -> tuple[int, ...]:
    count = max(1, min(width, sample_columns))
    if count == 1:
        return (width // 2,)
    return tuple(int(round(v)) for v in np.linspace(0, width - 1, count))


def _observation_xz(observation: Mapping[str, Any]) -> tuple[float, float]:
    gps = observation.get("gps")
    if gps is None:
        return 0.0, 0.0
    array = np.asarray(gps, dtype=float).reshape(-1)
    if array.size < 2:
        return 0.0, 0.0
    # Habitat's 2D EpisodicGPSSensor returns [forward, right]. Internally this
    # adapter uses x=right, z=forward so bearing math matches the action frame.
    return float(array[1]), float(array[0])


def _observation_heading(observation: Mapping[str, Any]) -> float:
    compass = observation.get("compass")
    if compass is None:
        return 0.0
    array = np.asarray(compass, dtype=float).reshape(-1)
    if array.size == 0:
        return 0.0
    # Habitat compass decreases after a right turn. The adapter's internal
    # heading is positive-right to match atan2(x_right, z_forward).
    return -float(array[0])


def _world_to_grid_cell(
    frontier_map: OccupancyFrontierMap,
    *,
    x_m: float,
    z_m: float,
) -> tuple[int, int]:
    origin_row, origin_col = frontier_map.origin_cell
    row = origin_row - int(round(z_m / frontier_map.cell_size_m))
    col = origin_col + int(round(x_m / frontier_map.cell_size_m))
    return row, col


def _mark_free_ray(
    frontier_map: OccupancyFrontierMap,
    *,
    start_cell: tuple[int, int],
    x_m: float,
    z_m: float,
    bearing_rad: float,
    distance_m: float,
) -> None:
    steps = max(1, int(distance_m / frontier_map.cell_size_m))
    for step in range(steps + 1):
        ray_distance = min(distance_m, step * frontier_map.cell_size_m)
        cell = _world_to_grid_cell(
            frontier_map,
            x_m=x_m + np.sin(bearing_rad) * ray_distance,
            z_m=z_m + np.cos(bearing_rad) * ray_distance,
        )
        _mark_cell(frontier_map, cell, OCCUPANCY_FREE)
    _mark_cell(frontier_map, start_cell, OCCUPANCY_FREE)


def _mark_cell(
    frontier_map: OccupancyFrontierMap,
    cell: tuple[int, int],
    value: int,
) -> None:
    row, col = cell
    if not _cell_in_bounds(frontier_map, cell):
        return
    if value == OCCUPANCY_FREE and frontier_map.grid[row, col] == OCCUPANCY_OCCUPIED:
        return
    frontier_map.grid[row, col] = value


def _cell_in_bounds(
    frontier_map: OccupancyFrontierMap,
    cell: tuple[int, int],
) -> bool:
    row, col = cell
    return 0 <= row < frontier_map.grid.shape[0] and 0 <= col < frontier_map.grid.shape[1]


def _frontier_cells(frontier_map: OccupancyFrontierMap) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    rows, cols = frontier_map.grid.shape
    for row in range(rows):
        for col in range(cols):
            if frontier_map.grid[row, col] != OCCUPANCY_UNKNOWN:
                continue
            for n_row, n_col in _neighbor4(row, col):
                if (
                    0 <= n_row < rows
                    and 0 <= n_col < cols
                    and frontier_map.grid[n_row, n_col] == OCCUPANCY_FREE
                ):
                    cells.append((row, col))
                    break
    return cells


def _active_perception_viewpoint_candidates(
    frontier_map: OccupancyFrontierMap,
) -> list[dict[str, tuple[int, int]]]:
    candidates: list[dict[str, tuple[int, int]]] = []
    seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for frontier in _frontier_cells(frontier_map):
        for neighbor in _neighbor4(*frontier):
            if not _cell_in_bounds(frontier_map, neighbor):
                continue
            row, col = neighbor
            if frontier_map.grid[row, col] != OCCUPANCY_FREE:
                continue
            key = (neighbor, frontier)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                {
                    "viewpoint_cell": neighbor,
                    "frontier_cell": frontier,
                }
            )
    return candidates


def _shortest_free_path_distance_cells(
    frontier_map: OccupancyFrontierMap,
    *,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> int | None:
    if not _cell_in_bounds(frontier_map, start) or not _cell_in_bounds(
        frontier_map, goal
    ):
        return None
    start_row, start_col = start
    goal_row, goal_col = goal
    if frontier_map.grid[start_row, start_col] != OCCUPANCY_FREE:
        return None
    if frontier_map.grid[goal_row, goal_col] != OCCUPANCY_FREE:
        return None
    if start == goal:
        return 0

    queue: deque[tuple[tuple[int, int], int]] = deque([(start, 0)])
    visited = {start}
    while queue:
        cell, distance = queue.popleft()
        for neighbor in _neighbor4(*cell):
            if neighbor in visited or not _cell_in_bounds(frontier_map, neighbor):
                continue
            row, col = neighbor
            if frontier_map.grid[row, col] != OCCUPANCY_FREE:
                continue
            if neighbor == goal:
                return distance + 1
            visited.add(neighbor)
            queue.append((neighbor, distance + 1))
    return None


def _neighbor4(row: int, col: int) -> tuple[tuple[int, int], ...]:
    return (
        (row - 1, col),
        (row + 1, col),
        (row, col - 1),
        (row, col + 1),
    )


def _turn_toward_nearest_frontier(
    frontier_map: OccupancyFrontierMap,
    observation: Mapping[str, Any],
) -> tuple[str, float | None]:
    frontiers = _frontier_cells(frontier_map)
    if not frontiers:
        return "turn_left", None
    x_m, z_m = _observation_xz(observation)
    current = _world_to_grid_cell(frontier_map, x_m=x_m, z_m=z_m)
    frontier = min(
        frontiers,
        key=lambda cell: (cell[0] - current[0]) ** 2 + (cell[1] - current[1]) ** 2,
    )
    bearing = _bearing_to_cell(frontier_map, current=current, target=frontier)
    heading = _observation_heading(observation)
    delta = _wrap_angle(bearing - heading)
    return ("turn_right" if delta > 0.0 else "turn_left"), delta


def _select_memory_belief_frontier(
    frontier_map: OccupancyFrontierMap,
    observation: Mapping[str, Any],
    anchor: OfficialMemoryAnchor,
    *,
    belief_sigma_m: float = 2.0,
    travel_distance_weight: float = 0.05,
) -> dict[str, Any] | None:
    frontiers = _frontier_cells(frontier_map)
    if not frontiers:
        return None
    sigma = max(float(belief_sigma_m), 1e-6)
    x_m, z_m = _observation_xz(observation)
    current = _world_to_grid_cell(frontier_map, x_m=x_m, z_m=z_m)
    heading = _observation_heading(observation)
    best: dict[str, Any] | None = None
    for frontier in frontiers:
        frontier_x_m, frontier_z_m = _grid_cell_center_xz(frontier_map, frontier)
        distance_to_anchor_m = float(
            np.hypot(frontier_x_m - anchor.x_m, frontier_z_m - anchor.z_m)
        )
        travel_distance_m = float(
            np.hypot(frontier[0] - current[0], frontier[1] - current[1])
            * frontier_map.cell_size_m
        )
        belief_mass = float(
            anchor.confidence
            * np.exp(-(distance_to_anchor_m**2) / (2.0 * sigma**2))
        )
        score = belief_mass - float(travel_distance_weight) * travel_distance_m
        bearing = _bearing_to_cell(frontier_map, current=current, target=frontier)
        candidate = {
            "frontier_cell": [int(frontier[0]), int(frontier[1])],
            "bearing_rad": bearing,
            "bearing_error_rad": _wrap_angle(bearing - heading),
            "belief_mass": belief_mass,
            "distance_to_anchor_m": distance_to_anchor_m,
            "travel_distance_m": travel_distance_m,
            "score": score,
        }
        if best is None or (score, -travel_distance_m) > (
            float(best["score"]),
            -float(best["travel_distance_m"]),
        ):
            best = candidate
    return best


def _select_memory_active_perception_frontier(
    frontier_map: OccupancyFrontierMap,
    observation: Mapping[str, Any],
    anchor: OfficialMemoryAnchor,
    *,
    belief_sigma_m: float = 2.0,
    preferred_view_distance_m: float = 2.0,
    view_distance_sigma_m: float = 0.75,
    travel_distance_weight: float = 0.05,
    top_k: int = 5,
    target_category: str = "",
    step_index: int | None = None,
    candidate_viewpoint_ranker_model: Mapping[str, Any] | None = None,
    committed_viewpoint_cell: tuple[int, int] | None = None,
) -> dict[str, Any] | None:
    viewpoint_candidates = _active_perception_viewpoint_candidates(frontier_map)
    if not viewpoint_candidates:
        return None
    belief_sigma = max(float(belief_sigma_m), 1e-6)
    view_sigma = max(float(view_distance_sigma_m), 1e-6)
    preferred_distance = max(0.0, float(preferred_view_distance_m))
    x_m, z_m = _observation_xz(observation)
    current = _world_to_grid_cell(frontier_map, x_m=x_m, z_m=z_m)
    heading = _observation_heading(observation)
    candidates: list[dict[str, Any]] = []
    for candidate_spec in viewpoint_candidates:
        viewpoint = candidate_spec["viewpoint_cell"]
        frontier = candidate_spec["frontier_cell"]
        path_distance_cells = _shortest_free_path_distance_cells(
            frontier_map,
            start=current,
            goal=viewpoint,
        )
        if path_distance_cells is None:
            continue
        viewpoint_x_m, viewpoint_z_m = _grid_cell_center_xz(frontier_map, viewpoint)
        anchor_dx = anchor.x_m - viewpoint_x_m
        anchor_dz = anchor.z_m - viewpoint_z_m
        distance_to_anchor_m = float(np.hypot(anchor_dx, anchor_dz))
        path_distance_m = float(path_distance_cells * frontier_map.cell_size_m)
        travel_distance_m = path_distance_m
        belief_mass = float(
            anchor.confidence
            * np.exp(-(distance_to_anchor_m**2) / (2.0 * belief_sigma**2))
        )
        view_distance_quality = float(
            np.exp(
                -((distance_to_anchor_m - preferred_distance) ** 2)
                / (2.0 * view_sigma**2)
            )
        )
        bearing_to_viewpoint = _bearing_to_cell(
            frontier_map,
            current=current,
            target=viewpoint,
        )
        # The frontier is a prospective viewpoint. After reaching it the agent
        # can rotate in place before sensing, so approach heading should not
        # zero otherwise valid side/standoff views.
        view_bearing_quality = 1.0
        view_quality = view_distance_quality * view_bearing_quality
        expected_evidence = belief_mass * view_quality
        score = expected_evidence - float(travel_distance_weight) * travel_distance_m
        candidates.append(
            {
                "viewpoint_cell": [int(viewpoint[0]), int(viewpoint[1])],
                "frontier_cell": [int(frontier[0]), int(frontier[1])],
                "candidate_x_m": viewpoint_x_m,
                "candidate_z_m": viewpoint_z_m,
                "bearing_rad": bearing_to_viewpoint,
                "bearing_error_rad": _wrap_angle(bearing_to_viewpoint - heading),
                "belief_mass": belief_mass,
                "distance_to_anchor_m": distance_to_anchor_m,
                "view_distance_quality": view_distance_quality,
                "view_bearing_quality": view_bearing_quality,
                "view_quality": view_quality,
                "expected_evidence": expected_evidence,
                "path_distance_m": path_distance_m,
                "travel_distance_m": travel_distance_m,
                "score": score,
            }
        )
    hand_ranked = sorted(
        candidates,
        key=lambda candidate: (
            float(candidate["score"]),
            float(candidate["expected_evidence"]),
            -float(candidate["travel_distance_m"]),
        ),
        reverse=True,
    )
    if not hand_ranked:
        return None
    for candidate_rank, candidate in enumerate(hand_ranked):
        candidate["candidate_rank"] = candidate_rank
        candidate["hand_score_rank"] = candidate_rank
        candidate["candidate_count"] = len(hand_ranked)
        candidate["candidate_score"] = candidate["score"]
    ranked = hand_ranked
    top_candidate_count = max(1, int(top_k))
    if candidate_viewpoint_ranker_model is not None:
        model_payload = _candidate_viewpoint_ranker_model_payload(
            candidate_viewpoint_ranker_model
        )
        ranker_candidates = hand_ranked[:top_candidate_count]
        for candidate in ranker_candidates:
            row = _online_candidate_viewpoint_ranker_row(
                candidate,
                target_category=target_category,
                step_index=step_index,
            )
            candidate["ranker_prediction"] = (
                predict_official_candidate_viewpoint_ranker(
                    candidate_viewpoint_ranker_model,
                    row,
                )
            )
            candidate["candidate_viewpoint_ranker_model"] = model_payload
        ranked = sorted(
            ranker_candidates,
            key=lambda candidate: (
                float(candidate["ranker_prediction"]),
                float(candidate["score"]),
                float(candidate["expected_evidence"]),
                -float(candidate["travel_distance_m"]),
            ),
            reverse=True,
        )
        for ranker_rank, candidate in enumerate(ranked):
            candidate["ranker_candidate_rank"] = ranker_rank
    selected_source = ranked[0]
    active_perception_commitment = "new"
    if committed_viewpoint_cell is not None:
        for candidate in ranked:
            values = candidate.get("viewpoint_cell")
            if (
                isinstance(values, Sequence)
                and len(values) >= 2
                and (int(values[0]), int(values[1])) == committed_viewpoint_cell
            ):
                selected_source = candidate
                active_perception_commitment = "continued"
                break
    selected = dict(selected_source)
    selected["candidate_count"] = len(candidates)
    selected["active_perception_commitment"] = active_perception_commitment
    if candidate_viewpoint_ranker_model is not None:
        selected["ranker_candidate_count"] = len(ranked)
        selected["ranker_selected_candidate_rank"] = int(selected["candidate_rank"])
    selected["top_candidates"] = ranked[:top_candidate_count]
    return selected


def _candidate_viewpoint_ranker_model_payload(model: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": str(model.get("task", "")),
        "model_type": str(model.get("model_type", "")),
        "label_name": str(model.get("label_name", "")),
        "feature_count": len(model.get("feature_names", [])),
    }


def _online_candidate_viewpoint_ranker_row(
    candidate: Mapping[str, Any],
    *,
    target_category: str,
    step_index: int | None,
) -> dict[str, Any]:
    row = {
        "candidate_rank": candidate.get("candidate_rank"),
        "candidate_count": candidate.get("candidate_count"),
        "candidate_score": candidate.get("candidate_score", candidate.get("score")),
        "expected_evidence": candidate.get("expected_evidence"),
        "belief_mass": candidate.get("belief_mass"),
        "distance_to_anchor_m": candidate.get("distance_to_anchor_m"),
        "bearing_error_rad": candidate.get("bearing_error_rad"),
        "view_quality": candidate.get("view_quality"),
        "view_bearing_quality": candidate.get("view_bearing_quality"),
        "view_distance_quality": candidate.get("view_distance_quality"),
        "path_distance_m": candidate.get("path_distance_m"),
        "travel_distance_m": candidate.get("travel_distance_m"),
        "target_category": target_category,
        "state_action": "online_policy",
        "state_decision": "memory_active_perception_frontier",
    }
    row["candidate_x_m"] = candidate.get("candidate_x_m")
    row["candidate_z_m"] = candidate.get("candidate_z_m")
    if step_index is not None:
        row["step_index"] = step_index
    return row


def _grid_cell_center_xz(
    frontier_map: OccupancyFrontierMap,
    cell: tuple[int, int],
) -> tuple[float, float]:
    origin_row, origin_col = frontier_map.origin_cell
    row, col = cell
    x_m = (col - origin_col) * frontier_map.cell_size_m
    z_m = (origin_row - row) * frontier_map.cell_size_m
    return float(x_m), float(z_m)


def _bearing_to_cell(
    frontier_map: OccupancyFrontierMap,
    *,
    current: tuple[int, int],
    target: tuple[int, int],
) -> float:
    d_row = target[0] - current[0]
    d_col = target[1] - current[1]
    x_m = d_col * frontier_map.cell_size_m
    z_m = -d_row * frontier_map.cell_size_m
    return float(np.arctan2(x_m, z_m))


def _wrap_angle(angle: float) -> float:
    return float((angle + np.pi) % (2.0 * np.pi) - np.pi)


def _row_metrics(row: Mapping[str, Any]) -> Mapping[str, Any]:
    return row.get("habitat_official", {})  # type: ignore[return-value]


def _mean_metric(rows: Sequence[Mapping[str, Any]], key: str) -> float | None:
    values = [
        float(_row_metrics(row)[key])
        for row in rows
        if key in _row_metrics(row)
    ]
    if not values:
        return None
    return sum(values) / len(values)


def _env_episode_count(env: Any) -> int:
    episodes = getattr(env, "episodes", None)
    if episodes is not None:
        return len(episodes)
    number = getattr(env, "number_of_episodes", None)
    if number is not None:
        return int(number)
    raise ValueError("max_episodes is required when env does not expose episode count")
