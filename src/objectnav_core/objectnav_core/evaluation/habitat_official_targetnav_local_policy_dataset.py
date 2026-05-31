from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    OfficialObjectNavRunConfig,
    _depth_frame_2d,
    _env_episode_count,
    _episode_goal_positions,
    _follower_action_name,
    _make_habitat_env,
    _make_shortest_path_follower,
    _nearest_goal_position,
    _observation_xz,
    _official_metrics_from_env,
    _sim_agent_position,
    _targetnav_pointgoal_with_gps_compass,
)


SCHEMA_VERSION = "official-targetnav-local-policy-v1"
SOURCE_VALIDITY = "oracle_teacher_only"
ALLOWED_ACTIONS: tuple[str, ...] = ("stop", "move_forward", "turn_left", "turn_right")

_CSV_FIELDS: tuple[str, ...] = (
    "source_validity",
    "episode_index",
    "episode_id",
    "scene_id",
    "target_category",
    "step_index",
    "teacher_action",
    "teacher_action_raw",
    "pointgoal_distance",
    "pointgoal_heading",
    "target_x_m",
    "target_z_m",
    "goal_x",
    "goal_y",
    "goal_z",
    "gps_forward",
    "gps_right",
    "compass",
    "depth_height",
    "depth_width",
    "depth_finite_count",
    "depth_min",
    "depth_max",
    "depth_mean",
    "depth_median",
    "distance_to_goal",
)


def export_official_targetnav_local_policy_dataset(
    *,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    max_episodes: int | None = 1,
    max_steps: int = 500,
    seed: int = 313,
    goal_radius_m: float = 0.2,
    env_factory: Callable[[OfficialObjectNavRunConfig], Any] | None = None,
    follower_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if max_episodes is not None and max_episodes <= 0:
        raise ValueError("max_episodes must be positive when provided")
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    if goal_radius_m <= 0.0:
        raise ValueError("goal_radius_m must be positive")

    config = OfficialObjectNavRunConfig(
        config_path=str(config_path),
        dataset_data_path=str(dataset_data_path),
        scene_root=str(scene_root),
        split=split,
        policy="noop",
        max_episodes=max_episodes,
        max_steps=max_steps,
        seed=seed,
        validate_habitat=True,
    )
    make_env = env_factory or _make_habitat_env
    make_follower = follower_factory or _make_shortest_path_follower
    env = make_env(config)

    examples: list[dict[str, Any]] = []
    skipped_no_goal_episode_count = 0
    skipped_teacher_unavailable_episode_count = 0
    invalid_teacher_action_count = 0
    completed_episode_count = 0
    try:
        episode_limit = max_episodes if max_episodes is not None else _env_episode_count(env)
        for episode_index in range(episode_limit):
            observation = env.reset()
            episode = getattr(env, "current_episode", None)
            goal_positions = _episode_goal_positions(episode)
            if not goal_positions:
                skipped_no_goal_episode_count += 1
                continue
            follower = _call_follower_factory(
                make_follower,
                env,
                goal_radius_m=goal_radius_m,
            )
            if follower is None:
                skipped_teacher_unavailable_episode_count += 1
                continue

            completed_episode_count += 1
            for step_index in range(max_steps):
                if bool(getattr(env, "episode_over", False)):
                    break
                goal_position = _nearest_goal_position(env, goal_positions)
                if goal_position is None:
                    skipped_no_goal_episode_count += 1
                    break
                raw_action = follower.get_next_action(
                    np.asarray(goal_position, dtype=float)
                )
                teacher_action = _follower_action_name(raw_action)
                if teacher_action not in ALLOWED_ACTIONS:
                    invalid_teacher_action_count += 1
                    break
                examples.append(
                    _targetnav_local_policy_example(
                        observation=observation,
                        env=env,
                        episode=episode,
                        episode_index=episode_index,
                        step_index=step_index,
                        goal_position=goal_position,
                        teacher_action=teacher_action,
                        teacher_action_raw=raw_action,
                    )
                )
                observation = env.step(teacher_action)
                if bool(getattr(env, "episode_over", False)):
                    break
    finally:
        close = getattr(env, "close", None)
        if callable(close):
            close()

    action_distribution = Counter(
        str(example["teacher_action"]) for example in examples
    )
    return {
        "task": "habitat_official_targetnav_local_policy_dataset",
        "schema_version": SCHEMA_VERSION,
        "source_validity": SOURCE_VALIDITY,
        "config": asdict(config),
        "goal_radius_m": float(goal_radius_m),
        "episode_count": completed_episode_count,
        "example_count": len(examples),
        "skipped_no_goal_episode_count": skipped_no_goal_episode_count,
        "skipped_teacher_unavailable_episode_count": (
            skipped_teacher_unavailable_episode_count
        ),
        "invalid_teacher_action_count": invalid_teacher_action_count,
        "action_distribution": dict(sorted(action_distribution.items())),
        "examples": examples,
    }


def write_official_targetnav_local_policy_dataset_csv(
    dataset: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    examples = dataset.get("examples", [])
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        if not isinstance(examples, Sequence):
            return
        for example in examples:
            if not isinstance(example, Mapping):
                continue
            writer.writerow(_csv_row(example))


def _targetnav_local_policy_example(
    *,
    observation: Mapping[str, Any],
    env: Any,
    episode: Any,
    episode_index: int,
    step_index: int,
    goal_position: tuple[float, float, float],
    teacher_action: str,
    teacher_action_raw: Any,
) -> dict[str, Any]:
    target_goal = _target_goal_from_goal_position(
        observation=observation,
        env=env,
        episode=episode,
        goal_position=goal_position,
    )
    pointgoal = _targetnav_pointgoal_with_gps_compass(observation, target_goal)
    return {
        "source_validity": SOURCE_VALIDITY,
        "episode_index": int(episode_index),
        "episode_id": str(getattr(episode, "episode_id", f"episode-{episode_index}")),
        "scene_id": str(getattr(episode, "scene_id", "")),
        "target_category": str(getattr(episode, "object_category", "")),
        "step_index": int(step_index),
        "goal_position": [round(float(value), 6) for value in goal_position],
        "target_goal": target_goal,
        "pointgoal_with_gps_compass": pointgoal,
        "teacher_action": teacher_action,
        "teacher_action_raw": _jsonable_action(teacher_action_raw),
        "depth_stats": _depth_stats(observation.get("depth")),
        "gps": _flat_float_list(observation.get("gps")),
        "compass": _flat_float_list(observation.get("compass")),
        "habitat_official": _safe_official_metrics(env),
        "provenance": {
            "source_validity": SOURCE_VALIDITY,
            "teacher": "habitat_shortest_path_follower",
            "online_benchmark_use": "forbidden",
        },
    }


def _target_goal_from_goal_position(
    *,
    observation: Mapping[str, Any],
    env: Any,
    episode: Any,
    goal_position: tuple[float, float, float],
) -> dict[str, Any]:
    start_position = _tuple3(getattr(episode, "start_position", None))
    start_rotation = _tuple4(getattr(episode, "start_rotation", None))
    if start_position is not None and start_rotation is not None:
        x_m, z_m = _world_position_to_episode_relative_xz(
            goal_position=goal_position,
            start_position=start_position,
            start_rotation=start_rotation,
        )
        conversion = "episode_start_pose"
    else:
        current_position = _sim_agent_position(env)
        current_x, current_z = _observation_xz(observation)
        if current_position is None:
            x_m = float(goal_position[0])
            z_m = float(goal_position[2])
            conversion = "world_xz_fallback"
        else:
            x_m = current_x + float(goal_position[0] - current_position[0])
            z_m = current_z + float(goal_position[2] - current_position[2])
            conversion = "sim_world_delta_plus_current_gps"
    return {
        "x_m": round(float(x_m), 6),
        "z_m": round(float(z_m), 6),
        "coordinate_frame": "episode_start_relative",
        "conversion": conversion,
    }


def _world_position_to_episode_relative_xz(
    *,
    goal_position: tuple[float, float, float],
    start_position: tuple[float, float, float],
    start_rotation: tuple[float, float, float, float],
) -> tuple[float, float]:
    yaw = _yaw_from_quaternion_xyzw(start_rotation)
    right = np.asarray((np.cos(yaw), 0.0, -np.sin(yaw)), dtype=float)
    forward = np.asarray((-np.sin(yaw), 0.0, -np.cos(yaw)), dtype=float)
    delta = np.asarray(goal_position, dtype=float) - np.asarray(start_position, dtype=float)
    return float(np.dot(delta, right)), float(np.dot(delta, forward))


def _call_follower_factory(
    follower_factory: Callable[..., Any],
    env: Any,
    *,
    goal_radius_m: float,
) -> Any | None:
    try:
        return follower_factory(env, goal_radius_m=goal_radius_m)
    except TypeError:
        return follower_factory(env)


def _safe_official_metrics(env: Any) -> dict[str, float]:
    try:
        return _official_metrics_from_env(env)
    except Exception:
        return {}


def _depth_stats(depth: Any) -> dict[str, Any] | None:
    array = _depth_frame_2d(depth)
    if array is None:
        return None
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return {
            "height": int(array.shape[0]),
            "width": int(array.shape[1]),
            "finite_count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
        }
    return {
        "height": int(array.shape[0]),
        "width": int(array.shape[1]),
        "finite_count": int(finite.size),
        "min": round(float(np.min(finite)), 6),
        "max": round(float(np.max(finite)), 6),
        "mean": round(float(np.mean(finite)), 6),
        "median": round(float(np.median(finite)), 6),
    }


def _flat_float_list(value: Any) -> list[float] | None:
    if value is None:
        return None
    try:
        array = np.asarray(value, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return None
    return [round(float(part), 6) for part in array]


def _jsonable_action(action: Any) -> Any:
    if action is None or isinstance(action, (str, int, float, bool)):
        return action
    array = np.asarray(action)
    if array.size == 1:
        return _jsonable_action(array.reshape(-1)[0].item())
    return [_jsonable_action(value.item() if hasattr(value, "item") else value) for value in array.reshape(-1)]


def _csv_row(example: Mapping[str, Any]) -> dict[str, Any]:
    goal_position = _sequence_or_empty(example.get("goal_position"))
    pointgoal = _sequence_or_empty(example.get("pointgoal_with_gps_compass"))
    gps = _sequence_or_empty(example.get("gps"))
    compass = _sequence_or_empty(example.get("compass"))
    target_goal = example.get("target_goal", {})
    depth_stats = example.get("depth_stats", {})
    metrics = example.get("habitat_official", {})
    if not isinstance(target_goal, Mapping):
        target_goal = {}
    if not isinstance(depth_stats, Mapping):
        depth_stats = {}
    if not isinstance(metrics, Mapping):
        metrics = {}
    return {
        "source_validity": example.get("source_validity"),
        "episode_index": example.get("episode_index"),
        "episode_id": example.get("episode_id"),
        "scene_id": example.get("scene_id"),
        "target_category": example.get("target_category"),
        "step_index": example.get("step_index"),
        "teacher_action": example.get("teacher_action"),
        "teacher_action_raw": example.get("teacher_action_raw"),
        "pointgoal_distance": _at(pointgoal, 0),
        "pointgoal_heading": _at(pointgoal, 1),
        "target_x_m": target_goal.get("x_m"),
        "target_z_m": target_goal.get("z_m"),
        "goal_x": _at(goal_position, 0),
        "goal_y": _at(goal_position, 1),
        "goal_z": _at(goal_position, 2),
        "gps_forward": _at(gps, 0),
        "gps_right": _at(gps, 1),
        "compass": _at(compass, 0),
        "depth_height": depth_stats.get("height"),
        "depth_width": depth_stats.get("width"),
        "depth_finite_count": depth_stats.get("finite_count"),
        "depth_min": depth_stats.get("min"),
        "depth_max": depth_stats.get("max"),
        "depth_mean": depth_stats.get("mean"),
        "depth_median": depth_stats.get("median"),
        "distance_to_goal": metrics.get("distance_to_goal"),
    }


def _sequence_or_empty(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()


def _at(values: Sequence[Any], index: int) -> Any:
    return values[index] if len(values) > index else None


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


def _tuple3(value: Any) -> tuple[float, float, float] | None:
    if value is None:
        return None
    try:
        values = tuple(float(part) for part in value)
    except (TypeError, ValueError):
        return None
    if len(values) != 3 or not all(np.isfinite(part) for part in values):
        return None
    return values


def _tuple4(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    try:
        values = tuple(float(part) for part in value)
    except (TypeError, ValueError):
        return None
    if len(values) != 4 or not all(np.isfinite(part) for part in values):
        return None
    return values
