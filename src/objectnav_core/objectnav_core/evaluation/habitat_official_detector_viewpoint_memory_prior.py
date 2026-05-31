from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    OfficialMemoryAnchor,
    OfficialObjectNavRunConfig,
    _env_episode_count,
    _load_habitat_metadata,
    _make_habitat_env,
    _tuple3_position,
    _tuple4_values,
    load_official_memory_prior,
    write_json,
)
from objectnav_core.evaluation.habitat_official_oracle_memory_prior import (
    _world_position_to_episode_relative_xzy,
)
from objectnav_core.evaluation.official_episode_memory import (
    make_official_memory_prior_payload,
)


DETECTOR_VIEWPOINT_PRIOR_SOURCE = (
    "habitat_official_detector_positive_viewpoint_memory_prior"
)
DETECTOR_VIEWPOINT_SOURCE_VALIDITY = "privileged_viewpoint_detector_diagnostic"


def export_habitat_official_detector_viewpoint_memory_prior(
    output_path: str | Path,
    *,
    detector_adapter: Any,
    detector_name: str,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    max_episodes: int | None = None,
    max_viewpoints_per_episode: int | None = None,
    seed: int = 313,
    min_detection_confidence: float = 0.25,
    validate_habitat: bool = False,
    viewpoint_trace_path: str | Path | None = None,
    viewpoint_image_dir: str | Path | None = None,
    env_factory: Callable[[OfficialObjectNavRunConfig], Any] | None = None,
) -> dict[str, Any]:
    if detector_adapter is None:
        raise ValueError("detector_adapter is required")
    if not detector_name:
        raise ValueError("detector_name must be non-empty")
    if max_episodes is not None and max_episodes <= 0:
        raise ValueError("max_episodes must be positive when provided")
    if max_viewpoints_per_episode is not None and max_viewpoints_per_episode <= 0:
        raise ValueError("max_viewpoints_per_episode must be positive when provided")
    if min_detection_confidence < 0.0:
        raise ValueError("min_detection_confidence must be non-negative")

    config = OfficialObjectNavRunConfig(
        config_path=str(config_path),
        dataset_data_path=str(dataset_data_path),
        scene_root=str(scene_root),
        split=split,
        policy="noop",
        max_episodes=max_episodes,
        seed=seed,
        validate_habitat=validate_habitat,
    )
    output = Path(output_path)
    trace_output = Path(viewpoint_trace_path) if viewpoint_trace_path else None
    image_output = Path(viewpoint_image_dir) if viewpoint_image_dir else None
    factory = env_factory or _make_habitat_env
    env = factory(config)
    anchors: list[OfficialMemoryAnchor] = []
    skipped: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    counts = {
        "episode_count": 0,
        "candidate_viewpoint_count": 0,
        "restored_viewpoint_count": 0,
        "detector_call_count": 0,
        "detection_count": 0,
        "confidence_filtered_count": 0,
        "label_filtered_count": 0,
        "detector_positive_viewpoint_count": 0,
        "restore_failed_count": 0,
    }
    try:
        episode_limit = max_episodes or _env_episode_count(env)
        for episode_index in range(episode_limit):
            env.reset()
            counts["episode_count"] += 1
            episode = getattr(env, "current_episode", None)
            anchor, episode_counts, skip, episode_trace_rows = (
                _export_episode_viewpoint_anchor(
                    env,
                    episode=episode,
                    episode_index=episode_index,
                    detector_adapter=detector_adapter,
                    detector_name=detector_name,
                    max_viewpoints=max_viewpoints_per_episode,
                    min_detection_confidence=min_detection_confidence,
                    trace_enabled=trace_output is not None or image_output is not None,
                    viewpoint_image_dir=image_output,
                )
            )
            trace_rows.extend(episode_trace_rows)
            for key, value in episode_counts.items():
                counts[key] += value
            if anchor is None:
                skipped.append(skip)
            else:
                anchors.append(anchor)
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    payload = make_official_memory_prior_payload(
        anchors,
        metadata={
            "source": DETECTOR_VIEWPOINT_PRIOR_SOURCE,
            "source_validity": DETECTOR_VIEWPOINT_SOURCE_VALIDITY,
            "detector_name": detector_name,
            "coordinate_frame": "episode_start_relative",
            "viewpoint_source": "official_episode_goal_view_points",
            "config_path": config.config_path,
            "dataset_data_path": config.dataset_data_path,
            "scene_root": config.scene_root,
            "split": config.split,
            "seed": config.seed,
            "max_episodes": config.max_episodes,
            "max_viewpoints_per_episode": max_viewpoints_per_episode,
            "min_detection_confidence": min_detection_confidence,
            "skipped_episode_count": len(skipped),
        },
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, payload)
    load_official_memory_prior(output)
    artifact_files = {"memory_prior": output.name}
    if trace_output is not None:
        trace_output.parent.mkdir(parents=True, exist_ok=True)
        write_json(
            trace_output,
            _viewpoint_trace_payload(
                trace_rows,
                config=config,
                detector_name=detector_name,
                min_detection_confidence=min_detection_confidence,
            ),
        )
        artifact_files["viewpoint_trace"] = trace_output.name
    if image_output is not None:
        artifact_files["viewpoint_images"] = image_output.name

    habitat_metadata = (
        _load_habitat_metadata(config) if validate_habitat else {"validated": False}
    )
    return {
        "task": "habitat_official_detector_viewpoint_memory_prior_export",
        "output_path": str(output),
        "config": asdict(config),
        "habitat": dict(habitat_metadata),
        "exported_anchor_count": len(anchors),
        "skipped_episode_count": len(skipped),
        "skipped_episodes": skipped,
        **counts,
        "metadata": dict(payload["metadata"]),
        "artifact_files": artifact_files,
        "notes": [
            "This prior uses privileged official episode target viewpoints.",
            "Use only for detector/viewpoint diagnostics, not benchmark claims.",
        ],
    }


def _export_episode_viewpoint_anchor(
    env: Any,
    *,
    episode: Any,
    episode_index: int,
    detector_adapter: Any,
    detector_name: str,
    max_viewpoints: int | None,
    min_detection_confidence: float,
    trace_enabled: bool = False,
    viewpoint_image_dir: Path | None = None,
) -> tuple[
    OfficialMemoryAnchor | None,
    dict[str, int],
    dict[str, Any],
    list[dict[str, Any]],
]:
    counts = {
        "candidate_viewpoint_count": 0,
        "restored_viewpoint_count": 0,
        "detector_call_count": 0,
        "detection_count": 0,
        "confidence_filtered_count": 0,
        "label_filtered_count": 0,
        "detector_positive_viewpoint_count": 0,
        "restore_failed_count": 0,
    }
    trace_rows: list[dict[str, Any]] = []
    episode_id = str(getattr(episode, "episode_id", f"episode-{episode_index}"))
    scene_id = str(getattr(episode, "scene_id", ""))
    object_category = str(getattr(episode, "object_category", ""))
    viewpoints = _episode_goal_viewpoints(episode)
    if not viewpoints:
        return None, counts, _skip_record(
            episode_index=episode_index,
            episode_id=episode_id,
            scene_id=scene_id,
            object_category=object_category,
            reason="missing_viewpoints",
        ), trace_rows
    if not object_category:
        return None, counts, _skip_record(
            episode_index=episode_index,
            episode_id=episode_id,
            scene_id=scene_id,
            object_category=object_category,
            reason="missing_object_category",
        ), trace_rows
    start_position = _tuple3_position(getattr(episode, "start_position", None))
    start_rotation = _tuple4_values(getattr(episode, "start_rotation", None))
    if start_position is None or start_rotation is None:
        return None, counts, _skip_record(
            episode_index=episode_index,
            episode_id=episode_id,
            scene_id=scene_id,
            object_category=object_category,
            reason="missing_episode_start_pose",
        ), trace_rows

    for viewpoint_index, (position, rotation) in enumerate(
        viewpoints[:max_viewpoints]
        if max_viewpoints is not None
        else viewpoints
    ):
        counts["candidate_viewpoint_count"] += 1
        trace_row = _base_viewpoint_trace_row(
            episode_index=episode_index,
            episode_id=episode_id,
            scene_id=scene_id,
            object_category=object_category,
            viewpoint_index=viewpoint_index,
            position=position,
            rotation=rotation,
        )
        observation = _restore_viewpoint_observation(
            env,
            position=position,
            rotation=rotation,
        )
        if observation is None:
            counts["restore_failed_count"] += 1
            if trace_enabled:
                trace_row["restored"] = False
                trace_row["invalid_reason"] = "restore_failed"
                trace_rows.append(trace_row)
            continue
        counts["restored_viewpoint_count"] += 1
        rgb = observation.get("rgb") if isinstance(observation, Mapping) else None
        if rgb is None:
            counts["restore_failed_count"] += 1
            if trace_enabled:
                trace_row["restored"] = False
                trace_row["invalid_reason"] = "missing_rgb"
                trace_rows.append(trace_row)
            continue
        rgb_array = np.asarray(rgb)
        detections = list(detector_adapter.detect(rgb_array))
        detection_payloads = [
            _detection_trace_payload(
                detection,
                target_category=object_category,
                min_detection_confidence=min_detection_confidence,
            )
            for detection in detections
        ]
        if viewpoint_image_dir is not None:
            image_path = _write_viewpoint_debug_image(
                viewpoint_image_dir,
                episode_index=episode_index,
                episode_id=episode_id,
                viewpoint_index=viewpoint_index,
                rgb=rgb_array,
                detections=detection_payloads,
            )
            trace_row["image_path"] = str(image_path)
        target_match_count = sum(
            1 for detection in detection_payloads if detection["accepted_target_match"]
        )
        if trace_enabled:
            trace_row.update(
                {
                    "restored": True,
                    "detection_count": len(detection_payloads),
                    "target_match_count": target_match_count,
                    "selected_anchor": False,
                    "detections": detection_payloads,
                }
            )
        counts["detector_call_count"] += 1
        counts["detection_count"] += len(detections)
        for detection_index, (detection, detection_payload) in enumerate(
            zip(detections, detection_payloads)
        ):
            confidence = float(detection_payload["confidence"])
            if confidence < min_detection_confidence:
                counts["confidence_filtered_count"] += 1
                continue
            if not bool(detection_payload["matches_target"]):
                counts["label_filtered_count"] += 1
                continue
            counts["detector_positive_viewpoint_count"] += 1
            anchor_source = (
                f"{detector_name}:episode={episode_id}:"
                f"viewpoint={viewpoint_index}:detection={detection_index}"
            )
            if trace_enabled:
                trace_row["selected_anchor"] = True
                trace_row["anchor_source"] = anchor_source
                trace_row["selected_detection_index"] = detection_index
                trace_rows.append(trace_row)
            return (
                _make_viewpoint_anchor(
                    episode=episode,
                    object_category=object_category,
                    scene_id=scene_id,
                    episode_id=episode_id,
                    position=position,
                    start_position=start_position,
                    start_rotation=start_rotation,
                    confidence=confidence,
                    source=anchor_source,
                ),
                counts,
                {},
                trace_rows,
            )
        if trace_enabled:
            trace_rows.append(trace_row)
    return None, counts, _skip_record(
        episode_index=episode_index,
        episode_id=episode_id,
        scene_id=scene_id,
        object_category=object_category,
        reason="no_detector_positive_viewpoint",
    ), trace_rows


def _make_viewpoint_anchor(
    *,
    episode: Any,
    object_category: str,
    scene_id: str,
    episode_id: str,
    position: tuple[float, float, float],
    start_position: tuple[float, float, float],
    start_rotation: tuple[float, float, float, float],
    confidence: float,
    source: str,
) -> OfficialMemoryAnchor:
    del episode
    x_m, y_m, z_m = _world_position_to_episode_relative_xzy(
        goal_position=position,
        start_position=start_position,
        start_rotation=start_rotation,
    )
    return OfficialMemoryAnchor(
        object_category=object_category,
        x_m=round(float(x_m), 6),
        y_m=round(float(y_m), 6),
        z_m=round(float(z_m), 6),
        scene_id=scene_id or None,
        episode_id=episode_id or None,
        confidence=float(confidence),
        source=source,
        coordinate_frame="episode_start_relative",
    )


def _episode_goal_viewpoints(
    episode: Any,
) -> tuple[tuple[tuple[float, float, float], tuple[float, float, float, float]], ...]:
    viewpoints: list[
        tuple[tuple[float, float, float], tuple[float, float, float, float]]
    ] = []
    for goal in getattr(episode, "goals", ()) or ():
        for viewpoint in getattr(goal, "view_points", ()) or ():
            agent_state = getattr(viewpoint, "agent_state", viewpoint)
            position = _tuple3_position(getattr(agent_state, "position", None))
            rotation = _tuple4_values(getattr(agent_state, "rotation", None))
            if position is not None and rotation is not None:
                viewpoints.append((position, rotation))
    return tuple(viewpoints)


def _restore_viewpoint_observation(
    env: Any,
    *,
    position: tuple[float, float, float],
    rotation: tuple[float, float, float, float],
) -> Mapping[str, Any] | None:
    custom_restore = getattr(env, "restore_viewpoint_observation", None)
    if callable(custom_restore):
        try:
            observation = custom_restore(position=position, rotation=rotation)
        except Exception:
            return None
        return _normalize_observation(observation)

    sim = getattr(env, "sim", None) or getattr(env, "_sim", None)
    if sim is None:
        return None
    try:
        agent = sim.initialize_agent(0)
        state = agent.get_state()
        state.position = np.asarray(position, dtype=float)
        state.rotation = list(rotation)
        agent.set_state(state)
        observation = sim.get_sensor_observations()
    except Exception:  # pragma: no cover - depends on Habitat runtime
        return None
    return _normalize_observation(observation)


def _normalize_observation(observation: Any) -> Mapping[str, Any] | None:
    if not isinstance(observation, Mapping):
        return None
    normalized = dict(observation)
    if "rgb" not in normalized and "color_sensor" in normalized:
        normalized["rgb"] = normalized["color_sensor"]
    rgb = normalized.get("rgb")
    if rgb is not None:
        array = np.asarray(rgb)
        if array.ndim == 3 and array.shape[2] > 3:
            normalized["rgb"] = array[:, :, :3]
    return normalized


def _viewpoint_trace_payload(
    rows: Sequence[Mapping[str, Any]],
    *,
    config: OfficialObjectNavRunConfig,
    detector_name: str,
    min_detection_confidence: float,
) -> dict[str, Any]:
    viewpoint_rows = [dict(row) for row in rows]
    return {
        "task": "habitat_official_detector_viewpoint_memory_prior_trace",
        "detector_name": detector_name,
        "config": asdict(config),
        "min_detection_confidence": float(min_detection_confidence),
        "viewpoint_count": len(viewpoint_rows),
        "restored_viewpoint_count": sum(
            1 for row in viewpoint_rows if bool(row.get("restored"))
        ),
        "detection_count": sum(
            int(row.get("detection_count", 0)) for row in viewpoint_rows
        ),
        "target_match_viewpoint_count": sum(
            1 for row in viewpoint_rows if int(row.get("target_match_count", 0)) > 0
        ),
        "selected_anchor_count": sum(
            1 for row in viewpoint_rows if bool(row.get("selected_anchor"))
        ),
        "viewpoints": viewpoint_rows,
    }


def _base_viewpoint_trace_row(
    *,
    episode_index: int,
    episode_id: str,
    scene_id: str,
    object_category: str,
    viewpoint_index: int,
    position: Sequence[float],
    rotation: Sequence[float],
) -> dict[str, Any]:
    return {
        "episode_index": int(episode_index),
        "episode_id": episode_id,
        "scene_id": scene_id,
        "target_category": object_category,
        "viewpoint_index": int(viewpoint_index),
        "position": [float(value) for value in position],
        "rotation": [float(value) for value in rotation],
        "restored": False,
        "detection_count": 0,
        "target_match_count": 0,
        "selected_anchor": False,
        "detections": [],
    }


def _detection_trace_payload(
    detection: Any,
    *,
    target_category: str,
    min_detection_confidence: float,
) -> dict[str, Any]:
    confidence = float(getattr(detection, "confidence", 0.0))
    category = str(getattr(detection, "category", ""))
    matches_target = _normalize_label(category) == _normalize_label(target_category)
    passes_confidence = confidence >= min_detection_confidence
    return {
        "category": category,
        "confidence": confidence,
        "bbox": _bbox_payload(getattr(detection, "bbox", None)),
        "passes_confidence": bool(passes_confidence),
        "matches_target": bool(matches_target),
        "accepted_target_match": bool(passes_confidence and matches_target),
    }


def _bbox_payload(bbox: Any) -> list[int] | None:
    if bbox is None:
        return None
    try:
        x1, y1, x2, y2 = bbox
    except (TypeError, ValueError):
        return None
    return [int(round(float(value))) for value in (x1, y1, x2, y2)]


def _write_viewpoint_debug_image(
    image_dir: Path,
    *,
    episode_index: int,
    episode_id: str,
    viewpoint_index: int,
    rgb: np.ndarray,
    detections: Sequence[Mapping[str, Any]],
) -> Path:
    from PIL import Image, ImageDraw

    image_dir.mkdir(parents=True, exist_ok=True)
    path = image_dir / (
        f"episode_{episode_index:04d}_{_safe_path_token(episode_id)}_"
        f"viewpoint_{viewpoint_index:03d}.png"
    )
    image = Image.fromarray(_rgb_uint8(rgb)).convert("RGB")
    draw = ImageDraw.Draw(image)
    for detection in detections:
        bbox = detection.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        color = (
            (0, 190, 80)
            if detection.get("accepted_target_match")
            else (230, 150, 0)
        )
        draw.rectangle([int(value) for value in bbox], outline=color, width=2)
        label = (
            f"{detection.get('category')}:"
            f"{float(detection.get('confidence', 0.0)):.2f}"
        )
        draw.text((int(bbox[0]), max(0, int(bbox[1]) - 12)), label, fill=color)
    image.save(path)
    return path


def _rgb_uint8(rgb: np.ndarray) -> np.ndarray:
    array = np.asarray(rgb)
    if array.ndim != 3:
        raise ValueError("rgb image must be HxWxC")
    if array.shape[2] > 3:
        array = array[:, :, :3]
    if array.dtype == np.uint8:
        return array
    clipped = np.clip(array, 0, 255)
    return clipped.astype(np.uint8)


def _safe_path_token(value: str) -> str:
    safe = "".join(character if character.isalnum() else "_" for character in value)
    return safe.strip("_") or "episode"


def _skip_record(
    *,
    episode_index: int,
    episode_id: str,
    scene_id: str,
    object_category: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "episode_index": int(episode_index),
        "episode_id": episode_id,
        "scene_id": scene_id,
        "object_category": object_category,
        "reason": reason,
    }


def _normalize_label(label: str) -> str:
    return " ".join(str(label).lower().replace("_", " ").split())
