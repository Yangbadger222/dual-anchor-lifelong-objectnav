from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    OfficialMemoryAnchor,
    OfficialObjectNavRunConfig,
    OfficialPolicyState,
    SUPPORTED_OFFICIAL_POLICIES,
    _detector_bbox_payload,
    _detector_target_evidence,
    _make_habitat_env,
    _select_detector_action_effect_target_action,
    _select_policy_action,
)
from objectnav_core.evaluation.official_episode_memory import (
    estimate_episode_detection_anchor,
    estimate_episode_robot_viewpoint_anchor,
    make_official_memory_prior_payload,
)


SUPPORTED_MEMORY_ANCHOR_MODES: tuple[str, ...] = (
    "projected_detection",
    "robot_viewpoint",
)
SUPPORTED_MEMORY_ANCHOR_SELECTION_POLICIES: tuple[str, ...] = (
    "confidence",
    "view_quality",
)
SUPPORTED_MEMORY_ANCHOR_COMMIT_POLICIES: tuple[str, ...] = (
    "immediate",
    "detector_approach",
    "confirmed_detector_approach",
)


@dataclass(frozen=True)
class OfficialMemoryDiscoveryConfig:
    config_path: str = (
        "third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/"
        "objectnav/objectnav_hm3d.yaml"
    )
    dataset_data_path: str = (
        "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/"
        "val_mini/val_mini.json.gz"
    )
    scene_root: str = "datasets/habitat/scene_datasets/hm3d"
    split: str = "val_mini"
    policy: str = "occupancy_frontier"
    max_episodes: int | None = 1
    max_steps: int = 100
    seed: int = 313
    detector_name: str = "injected_detector"
    min_detection_confidence: float = 0.0
    max_anchors_per_episode: int = 8
    positive_count_threshold: int = 1
    anchor_mode: str = "projected_detection"
    anchor_selection_policy: str = "confidence"
    anchor_commit_policy: str = "immediate"
    detector_approach_max_steps: int = 1
    hfov_deg: float = 79.0
    min_depth_m: float = 0.5
    max_depth_m: float = 5.0


def run_habitat_official_memory_discovery(
    output_dir: str | Path,
    *,
    detector_adapter: Any,
    env_factory: Callable[[OfficialObjectNavRunConfig], Any] | None = None,
    config_path: str | None = None,
    dataset_data_path: str | None = None,
    scene_root: str | None = None,
    split: str = "val_mini",
    policy: str = "occupancy_frontier",
    max_episodes: int | None = 1,
    max_steps: int = 100,
    seed: int = 313,
    detector_name: str = "injected_detector",
    min_detection_confidence: float = 0.0,
    max_anchors_per_episode: int = 8,
    positive_count_threshold: int = 1,
    anchor_mode: str = "projected_detection",
    anchor_selection_policy: str = "confidence",
    anchor_commit_policy: str = "immediate",
    detector_approach_max_steps: int = 1,
    hfov_deg: float = 79.0,
    min_depth_m: float = 0.5,
    max_depth_m: float = 5.0,
) -> dict[str, Any]:
    config = OfficialMemoryDiscoveryConfig(
        config_path=config_path or OfficialMemoryDiscoveryConfig.config_path,
        dataset_data_path=(
            dataset_data_path or OfficialMemoryDiscoveryConfig.dataset_data_path
        ),
        scene_root=scene_root or OfficialMemoryDiscoveryConfig.scene_root,
        split=split,
        policy=policy,
        max_episodes=max_episodes,
        max_steps=max_steps,
        seed=seed,
        detector_name=detector_name,
        min_detection_confidence=min_detection_confidence,
        max_anchors_per_episode=max_anchors_per_episode,
        positive_count_threshold=positive_count_threshold,
        anchor_mode=anchor_mode,
        anchor_selection_policy=anchor_selection_policy,
        anchor_commit_policy=anchor_commit_policy,
        detector_approach_max_steps=detector_approach_max_steps,
        hfov_deg=hfov_deg,
        min_depth_m=min_depth_m,
        max_depth_m=max_depth_m,
    )
    _validate_discovery_config(config)
    if detector_adapter is None:
        raise ValueError("detector_adapter is required")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    run_config = OfficialObjectNavRunConfig(
        config_path=config.config_path,
        dataset_data_path=config.dataset_data_path,
        scene_root=config.scene_root,
        split=config.split,
        policy=config.policy,
        max_episodes=config.max_episodes,
        max_steps=config.max_steps,
        seed=config.seed,
        validate_habitat=False,
    )
    env = (env_factory or _make_habitat_env)(run_config)
    try:
        anchors, rows, counts = _run_discovery_loop(
            env,
            detector_adapter=detector_adapter,
            config=config,
        )
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    prior_payload = make_official_memory_prior_payload(
        anchors,
        metadata={
            "source": "habitat_official_memory_discovery",
            "detector_name": config.detector_name,
            "policy": config.policy,
            "memory_source_policy": (
                "naive_count_positive_only"
                if config.positive_count_threshold > 1
                else "single_positive_detector_memory"
            ),
            "positive_count_threshold": config.positive_count_threshold,
            "anchor_mode": config.anchor_mode,
            "anchor_selection_policy": config.anchor_selection_policy,
            "anchor_commit_policy": config.anchor_commit_policy,
            "detector_approach_max_steps": config.detector_approach_max_steps,
            "source_validity": (
                "positive_only_count_baseline"
                if config.positive_count_threshold > 1
                else "not_benchmark_validated"
            ),
        },
    )
    _write_json(output_path / "memory_prior.json", prior_payload)
    _write_detection_csv(output_path / "detections.csv", rows)
    summary = {
        "task": "habitat_official_memory_discovery",
        "config": asdict(config),
        "artifact_files": {
            "memory_prior": "memory_prior.json",
            "summary": "summary.json",
            "detections": "detections.csv",
        },
        "exported_anchor_count": len(anchors),
        **counts,
        "notes": [
            "Detector-injected discovery artifacts are not benchmark claims.",
            (
                "Anchors are projected from detector bbox/depth into episode_start_relative frame."
                if config.anchor_mode == "projected_detection"
                else "Anchors store the detector-positive robot viewpoint in episode_start_relative frame."
            ),
            (
                "View-quality selection ranks candidates by bbox area, centering, and confidence."
                if config.anchor_selection_policy == "view_quality"
                else "Confidence selection keeps the highest-confidence detector candidates."
            ),
            (
                "Detector-approach commit defers memory until after bounded local detector control."
                if config.anchor_commit_policy == "detector_approach"
                else (
                    "Confirmed detector-approach commit writes memory only after range-confirmed local detector control."
                    if config.anchor_commit_policy
                    == "confirmed_detector_approach"
                    else "Immediate commit stores the first accepted detector-positive observation."
                )
            ),
        ],
    }
    _write_json(output_path / "summary.json", summary)
    return summary


def _run_discovery_loop(
    env: Any,
    *,
    detector_adapter: Any,
    config: OfficialMemoryDiscoveryConfig,
) -> tuple[list[OfficialMemoryAnchor], list[dict[str, Any]], dict[str, int]]:
    episode_limit = config.max_episodes or _env_episode_count(env)
    anchors: list[OfficialMemoryAnchor] = []
    rows: list[dict[str, Any]] = []
    counts = {
        "episode_count": 0,
        "observation_count": 0,
        "detection_count": 0,
        "confidence_filtered_count": 0,
        "label_filtered_count": 0,
        "projection_failed_count": 0,
        "anchor_cap_filtered_count": 0,
        "positive_count_threshold_filtered_count": 0,
        "missing_rgb_count": 0,
        "detector_approach_deferred_count": 0,
        "detector_approach_confirmed_count": 0,
        "detector_approach_unconfirmed_count": 0,
    }
    for episode_index in range(episode_limit):
        observation = env.reset()
        episode = getattr(env, "current_episode", None)
        object_category = str(getattr(episode, "object_category", ""))
        scene_id = str(getattr(episode, "scene_id", ""))
        episode_id = str(getattr(episode, "episode_id", f"episode-{episode_index}"))
        policy_state = OfficialPolicyState(
            rng=random.Random(config.seed + episode_index),
            object_category=object_category,
            scene_id=scene_id,
        )
        detector_approach_steps = 0
        episode_candidates: list[tuple[OfficialMemoryAnchor, dict[str, Any]]] = []
        counts["episode_count"] += 1
        for step_index in range(config.max_steps):
            if bool(getattr(env, "episode_over", False)):
                break
            counts["observation_count"] += 1
            rgb = observation.get("rgb") if isinstance(observation, Mapping) else None
            detector_approach_action: str | None = None
            if rgb is None:
                counts["missing_rgb_count"] += 1
            else:
                detections = list(detector_adapter.detect(np.asarray(rgb)))
                counts["detection_count"] += len(detections)
                for detection_index, detection in enumerate(detections):
                    detection_confidence = float(getattr(detection, "confidence", 0.0))
                    if detection_confidence < config.min_detection_confidence:
                        counts["confidence_filtered_count"] += 1
                        continue
                    detection_category = str(getattr(detection, "category", ""))
                    if _normalize_label(detection_category) != _normalize_label(
                        object_category
                    ):
                        counts["label_filtered_count"] += 1
                        continue
                    source = (
                        f"{config.detector_name}:episode={episode_id}:"
                        f"step={step_index}:detection={detection_index}"
                    )
                    detector_evidence = _detector_target_evidence(
                        observation,
                        _detector_bbox_payload(getattr(detection, "bbox", None)),
                    )
                    if (
                        config.anchor_commit_policy
                        in {"detector_approach", "confirmed_detector_approach"}
                        and config.anchor_mode == "robot_viewpoint"
                    ):
                        action = _select_discovery_detector_approach_action(
                            observation,
                            policy_state,
                            detection=detection,
                            step_index=step_index,
                        )
                        if (
                            config.anchor_commit_policy
                            == "confirmed_detector_approach"
                        ):
                            if action == "stop":
                                counts["detector_approach_confirmed_count"] += 1
                            elif (
                                detector_approach_steps
                                < config.detector_approach_max_steps
                                and action
                                in {"move_forward", "turn_left", "turn_right"}
                            ):
                                detector_approach_action = action
                                detector_approach_steps += 1
                                counts["detector_approach_deferred_count"] += 1
                                break
                            else:
                                counts["detector_approach_unconfirmed_count"] += 1
                                detector_approach_steps = 0
                                continue
                        elif (
                            detector_approach_steps
                            < config.detector_approach_max_steps
                            and action in {"move_forward", "turn_left", "turn_right"}
                        ):
                            detector_approach_action = action
                            detector_approach_steps += 1
                            counts["detector_approach_deferred_count"] += 1
                            break
                    if config.anchor_mode == "robot_viewpoint":
                        anchor = estimate_episode_robot_viewpoint_anchor(
                            observation,
                            object_category=object_category,
                            confidence=detection_confidence,
                            source=source,
                            scene_id=scene_id,
                            episode_id=episode_id,
                        )
                    else:
                        anchor = estimate_episode_detection_anchor(
                            observation,
                            bbox_xyxy=getattr(detection, "bbox"),
                            object_category=object_category,
                            confidence=detection_confidence,
                            source=source,
                            scene_id=scene_id,
                            episode_id=episode_id,
                            hfov_deg=config.hfov_deg,
                            min_depth_m=config.min_depth_m,
                            max_depth_m=config.max_depth_m,
                        )
                    if anchor is None:
                        counts["projection_failed_count"] += 1
                        continue
                    episode_candidates.append(
                        (
                            anchor,
                            _detection_row(
                                episode_index=episode_index,
                                episode_id=episode_id,
                                scene_id=scene_id,
                                object_category=object_category,
                                step_index=step_index,
                                detection_index=detection_index,
                                detection=detection,
                                detector_evidence=detector_evidence,
                                anchor=anchor,
                                anchor_mode=config.anchor_mode,
                                anchor_selection_policy=(
                                    config.anchor_selection_policy
                                ),
                                anchor_commit_policy=config.anchor_commit_policy,
                                detector_approach_deferred_steps=(
                                    detector_approach_steps
                                ),
                            ),
                        )
                    )
                    detector_approach_steps = 0
            action = detector_approach_action or _select_policy_action(
                config.policy,
                observation=observation,
                step_index=step_index,
                max_steps=config.max_steps,
                state=policy_state,
            )
            observation = env.step(action)
        if len(episode_candidates) < config.positive_count_threshold:
            counts["positive_count_threshold_filtered_count"] += len(
                episode_candidates
            )
            kept_candidates = []
        else:
            kept_candidates = sorted(
                episode_candidates,
                key=lambda candidate: _anchor_selection_key(
                    candidate,
                    policy=config.anchor_selection_policy,
                ),
                reverse=True,
            )[: config.max_anchors_per_episode]
        counts["anchor_cap_filtered_count"] += max(
            0,
            len(episode_candidates) - len(kept_candidates),
        )
        anchors.extend(anchor for anchor, _row in kept_candidates)
        rows.extend(row for _anchor, row in kept_candidates)
    return anchors, rows, counts


def _validate_discovery_config(config: OfficialMemoryDiscoveryConfig) -> None:
    if config.policy not in SUPPORTED_OFFICIAL_POLICIES:
        raise ValueError(f"Unsupported discovery policy: {config.policy}")
    if config.max_episodes is not None and config.max_episodes <= 0:
        raise ValueError("max_episodes must be positive when provided")
    if config.max_steps <= 0:
        raise ValueError("max_steps must be positive")
    if config.min_detection_confidence < 0.0:
        raise ValueError("min_detection_confidence must be non-negative")
    if config.max_anchors_per_episode <= 0:
        raise ValueError("max_anchors_per_episode must be positive")
    if config.positive_count_threshold <= 0:
        raise ValueError("positive_count_threshold must be positive")
    if config.anchor_mode not in SUPPORTED_MEMORY_ANCHOR_MODES:
        raise ValueError(f"Unsupported memory anchor mode: {config.anchor_mode}")
    if config.anchor_selection_policy not in SUPPORTED_MEMORY_ANCHOR_SELECTION_POLICIES:
        raise ValueError(
            f"Unsupported memory anchor selection policy: "
            f"{config.anchor_selection_policy}"
        )
    if config.anchor_commit_policy not in SUPPORTED_MEMORY_ANCHOR_COMMIT_POLICIES:
        raise ValueError(
            f"Unsupported memory anchor commit policy: {config.anchor_commit_policy}"
        )
    if (
        config.anchor_commit_policy
        in {"detector_approach", "confirmed_detector_approach"}
        and config.anchor_mode != "robot_viewpoint"
    ):
        raise ValueError(
            f"{config.anchor_commit_policy} commit requires "
            "anchor_mode=robot_viewpoint"
        )
    if config.detector_approach_max_steps <= 0:
        raise ValueError("detector_approach_max_steps must be positive")


def _select_discovery_detector_approach_action(
    observation: Mapping[str, Any],
    policy_state: OfficialPolicyState,
    *,
    detection: Any,
    step_index: int,
) -> str | None:
    bbox = _detector_bbox_payload(getattr(detection, "bbox", None))
    detector_match = {
        "detector_category": str(getattr(detection, "category", "")),
        "detector_confidence": float(getattr(detection, "confidence", 0.0)),
        "detector_bbox": bbox,
        **_detector_target_evidence(observation, bbox),
    }
    return _select_detector_action_effect_target_action(
        observation,
        policy_state,
        detector_match,
        step_index=step_index,
    )


def _normalize_label(label: str) -> str:
    return " ".join(str(label).lower().replace("_", " ").split())


def _anchor_selection_key(
    candidate: tuple[OfficialMemoryAnchor, dict[str, Any]],
    *,
    policy: str,
) -> tuple[float, ...]:
    anchor, row = candidate
    if policy == "confidence":
        return (float(anchor.confidence),)
    area = _finite_float(row.get("detector_bbox_area_fraction"))
    center_offset = _finite_float(row.get("detector_center_offset_fraction"))
    return (
        1.0 if area is not None else 0.0,
        area if area is not None else -1.0,
        1.0 if center_offset is not None else 0.0,
        -(abs(center_offset) if center_offset is not None else 1.0),
        float(anchor.confidence),
    )


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def _detection_row(
    *,
    episode_index: int,
    episode_id: str,
    scene_id: str,
    object_category: str,
    step_index: int,
    detection_index: int,
    detection: Any,
    detector_evidence: Mapping[str, Any],
    anchor: OfficialMemoryAnchor,
    anchor_mode: str,
    anchor_selection_policy: str,
    anchor_commit_policy: str,
    detector_approach_deferred_steps: int,
) -> dict[str, Any]:
    x1, y1, x2, y2 = getattr(detection, "bbox")
    return {
        "episode_index": episode_index,
        "episode_id": episode_id,
        "scene_id": scene_id,
        "object_category": object_category,
        "step_index": step_index,
        "detection_index": detection_index,
        "detection_category": str(getattr(detection, "category", "")),
        "detection_confidence": float(getattr(detection, "confidence", 0.0)),
        "bbox_x1": int(x1),
        "bbox_y1": int(y1),
        "bbox_x2": int(x2),
        "bbox_y2": int(y2),
        "detector_center_offset_fraction": detector_evidence.get(
            "detector_center_offset_fraction"
        ),
        "detector_bbox_area_fraction": detector_evidence.get(
            "detector_bbox_area_fraction"
        ),
        "detector_depth_is_normalized": detector_evidence.get(
            "detector_depth_is_normalized"
        ),
        "detector_depth_median": detector_evidence.get("detector_depth_median"),
        "anchor_mode": anchor_mode,
        "anchor_selection_policy": anchor_selection_policy,
        "anchor_commit_policy": anchor_commit_policy,
        "detector_approach_deferred_steps": detector_approach_deferred_steps,
        "anchor_x_m": anchor.x_m,
        "anchor_z_m": anchor.z_m,
        "anchor_source": anchor.source,
    }


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _write_detection_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "episode_index",
        "episode_id",
        "scene_id",
        "object_category",
        "step_index",
        "detection_index",
        "detection_category",
        "detection_confidence",
        "bbox_x1",
        "bbox_y1",
        "bbox_x2",
        "bbox_y2",
        "detector_center_offset_fraction",
        "detector_bbox_area_fraction",
        "detector_depth_is_normalized",
        "detector_depth_median",
        "anchor_mode",
        "anchor_selection_policy",
        "anchor_commit_policy",
        "detector_approach_deferred_steps",
        "anchor_x_m",
        "anchor_z_m",
        "anchor_source",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _env_episode_count(env: Any) -> int:
    episodes = getattr(env, "episodes", None)
    if episodes is not None:
        return len(episodes)
    number = getattr(env, "number_of_episodes", None)
    if number is not None:
        return int(number)
    raise ValueError("max_episodes is required when env does not expose episode count")
