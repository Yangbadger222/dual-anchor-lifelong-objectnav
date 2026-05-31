from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    OfficialMemoryAnchor,
    OfficialObjectNavRunConfig,
    _env_episode_count,
    _episode_goal_positions,
    _load_habitat_metadata,
    _make_habitat_env,
    _nearest_goal_position,
    _tuple3_position,
    _tuple4_values,
    _yaw_from_quaternion_xyzw,
    load_official_memory_prior,
    write_json,
)


ORACLE_MEMORY_PRIOR_SOURCE = "habitat_official_oracle_memory_prior"
ORACLE_MEMORY_SOURCE_VALIDITY = "oracle_diagnostic_only"


def export_habitat_official_oracle_memory_prior(
    output_path: str | Path,
    *,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    max_episodes: int | None = None,
    seed: int = 313,
    validate_habitat: bool = False,
    env_factory: Callable[[OfficialObjectNavRunConfig], Any] | None = None,
) -> dict[str, Any]:
    if max_episodes is not None and max_episodes <= 0:
        raise ValueError("max_episodes must be positive when provided")

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
    factory = env_factory or _make_habitat_env
    env = factory(config)
    anchors: list[OfficialMemoryAnchor] = []
    skipped: list[dict[str, Any]] = []
    try:
        episode_limit = max_episodes or _env_episode_count(env)
        for episode_index in range(episode_limit):
            env.reset()
            episode = getattr(env, "current_episode", None)
            positions = _episode_goal_positions(episode)
            goal_position = _nearest_goal_position(env, positions)
            anchor = make_official_oracle_memory_anchor(
                episode,
                goal_position=goal_position,
            )
            if anchor is None:
                skipped.append(
                    {
                        "episode_index": episode_index,
                        "episode_id": str(
                            getattr(episode, "episode_id", f"episode-{episode_index}")
                        ),
                        "scene_id": str(getattr(episode, "scene_id", "")),
                        "object_category": str(
                            getattr(episode, "object_category", "")
                        ),
                        "reason": _oracle_memory_skip_reason(episode, positions),
                    }
                )
                continue
            anchors.append(anchor)
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    payload = make_official_oracle_memory_prior_payload(
        anchors,
        config=config,
        skipped=skipped,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, payload)
    load_official_memory_prior(output)

    habitat_metadata = (
        _load_habitat_metadata(config) if validate_habitat else {"validated": False}
    )
    return {
        "task": "habitat_official_oracle_memory_prior_export",
        "output_path": str(output),
        "config": asdict(config),
        "habitat": dict(habitat_metadata),
        "exported_anchor_count": len(anchors),
        "skipped_episode_count": len(skipped),
        "skipped_episodes": skipped,
        "metadata": dict(payload["metadata"]),
        "artifact_files": {"memory_prior": output.name},
        "notes": [
            "This memory prior is privileged Habitat oracle data.",
            "Use only for upper-bound diagnostics, not benchmark-valid claims.",
        ],
    }


def make_official_oracle_memory_anchor(
    episode: Any,
    *,
    goal_position: Sequence[float] | None = None,
) -> OfficialMemoryAnchor | None:
    if episode is None:
        return None
    object_category = str(getattr(episode, "object_category", ""))
    if not object_category:
        return None
    start_position = _tuple3_position(getattr(episode, "start_position", None))
    start_rotation = _tuple4_values(getattr(episode, "start_rotation", None))
    if start_position is None or start_rotation is None:
        return None
    parsed_goal_position = _tuple3_position(goal_position)
    if parsed_goal_position is None:
        positions = _episode_goal_positions(episode)
        if not positions:
            return None
        parsed_goal_position = positions[0]
    x_m, y_m, z_m = _world_position_to_episode_relative_xzy(
        goal_position=parsed_goal_position,
        start_position=start_position,
        start_rotation=start_rotation,
    )
    episode_id = str(getattr(episode, "episode_id", ""))
    scene_id = str(getattr(episode, "scene_id", ""))
    source_episode_id = episode_id or "unknown_episode"
    return OfficialMemoryAnchor(
        object_category=object_category,
        x_m=round(float(x_m), 6),
        z_m=round(float(z_m), 6),
        y_m=round(float(y_m), 6),
        scene_id=scene_id or None,
        episode_id=episode_id or None,
        confidence=1.0,
        source=f"habitat_oracle_goal:{source_episode_id}",
        coordinate_frame="episode_start_relative",
    )


def make_official_oracle_memory_prior_payload(
    anchors: Sequence[OfficialMemoryAnchor],
    *,
    config: OfficialObjectNavRunConfig,
    skipped: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "anchors": [_oracle_anchor_payload(anchor) for anchor in anchors],
        "metadata": {
            "source": ORACLE_MEMORY_PRIOR_SOURCE,
            "source_validity": ORACLE_MEMORY_SOURCE_VALIDITY,
            "coordinate_frame": "episode_start_relative",
            "goal_source": "nearest_episode_goal_or_viewpoint",
            "config_path": config.config_path,
            "dataset_data_path": config.dataset_data_path,
            "scene_root": config.scene_root,
            "split": config.split,
            "seed": config.seed,
            "max_episodes": config.max_episodes,
            "anchor_count": len(anchors),
            "skipped_episode_count": len(skipped),
        },
    }


def _world_position_to_episode_relative_xz(
    *,
    goal_position: Sequence[float],
    start_position: Sequence[float],
    start_rotation: Sequence[float],
) -> tuple[float, float]:
    parsed_goal = _tuple3_position(goal_position)
    parsed_start = _tuple3_position(start_position)
    parsed_rotation = _tuple4_values(start_rotation)
    if parsed_goal is None:
        raise ValueError("goal_position must contain three finite values")
    if parsed_start is None:
        raise ValueError("start_position must contain three finite values")
    if parsed_rotation is None:
        raise ValueError("start_rotation must contain four finite values")

    yaw = _yaw_from_quaternion_xyzw(parsed_rotation)
    right = np.asarray((np.cos(yaw), 0.0, -np.sin(yaw)), dtype=float)
    forward = np.asarray((-np.sin(yaw), 0.0, -np.cos(yaw)), dtype=float)
    delta = np.asarray(parsed_goal, dtype=float) - np.asarray(parsed_start, dtype=float)
    return float(np.dot(delta, right)), float(np.dot(delta, forward))


def _world_position_to_episode_relative_xzy(
    *,
    goal_position: Sequence[float],
    start_position: Sequence[float],
    start_rotation: Sequence[float],
) -> tuple[float, float, float]:
    parsed_goal = _tuple3_position(goal_position)
    parsed_start = _tuple3_position(start_position)
    if parsed_goal is None:
        raise ValueError("goal_position must contain three finite values")
    if parsed_start is None:
        raise ValueError("start_position must contain three finite values")
    x_m, z_m = _world_position_to_episode_relative_xz(
        goal_position=parsed_goal,
        start_position=parsed_start,
        start_rotation=start_rotation,
    )
    y_m = float(parsed_goal[1] - parsed_start[1])
    return x_m, y_m, z_m


def _oracle_anchor_payload(anchor: OfficialMemoryAnchor) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "object_category": anchor.object_category,
        "x_m": anchor.x_m,
        "z_m": anchor.z_m,
        "confidence": anchor.confidence,
        "source": anchor.source,
        "coordinate_frame": anchor.coordinate_frame,
    }
    if anchor.scene_id is not None:
        payload["scene_id"] = anchor.scene_id
    if anchor.episode_id is not None:
        payload["episode_id"] = anchor.episode_id
    if anchor.y_m is not None:
        payload["y_m"] = anchor.y_m
    return payload


def _oracle_memory_skip_reason(
    episode: Any,
    positions: Sequence[tuple[float, float, float]],
) -> str:
    if episode is None:
        return "missing_episode"
    if not str(getattr(episode, "object_category", "")):
        return "missing_object_category"
    if not positions:
        return "missing_goal_position"
    if _tuple3_position(getattr(episode, "start_position", None)) is None:
        return "missing_start_position"
    if _tuple4_values(getattr(episode, "start_rotation", None)) is None:
        return "missing_start_rotation"
    return "invalid_episode_anchor"
