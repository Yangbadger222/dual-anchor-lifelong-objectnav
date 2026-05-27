from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass
from html import escape
from pathlib import Path
from typing import Any, Sequence

import numpy as np


DEFAULT_ACTIONS = ("turn_left", "move_forward", "turn_right", "move_forward")


@dataclass(frozen=True)
class SyntheticObjectNavSpec:
    scene_path: str
    object_category: str = "chair"
    target_position: tuple[float, float, float] = (0.8, 0.0, -0.8)
    start_position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    start_rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)


def run_habitat_objectnav_smoke(
    output_dir: str | Path,
    *,
    scene_path: str | Path,
    scene_dataset_config: str | Path | None = None,
    seed: int = 23,
    sensor_size: int = 64,
    actions: Sequence[str] = DEFAULT_ACTIONS,
    stop_at_end: bool = True,
    sample_navigable: bool = False,
    sample_target_near_radius: float | None = None,
    spec: SyntheticObjectNavSpec | None = None,
) -> dict[str, Any]:
    """Run a minimal Habitat-Lab ObjectNav task and export an observation trace.

    This is intentionally a smoke test, not a benchmark. It uses Habitat-Lab's
    ObjectNav-v1 task with a synthetic one-episode dataset so the repository can
    verify scene loading, task reset/step, RGB-D observations, and trace export
    before downloading large ObjectNav datasets.
    """

    if sensor_size <= 0:
        raise ValueError("sensor_size must be positive")
    if sample_target_near_radius is not None:
        if sample_target_near_radius <= 0.0:
            raise ValueError("sample_target_near_radius must be positive")
        if not sample_navigable:
            raise ValueError("sample_target_near_radius requires sample_navigable=True")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    scene = Path(scene_path).expanduser().resolve()
    if not scene.exists():
        raise FileNotFoundError(f"Habitat scene does not exist: {scene}")
    dataset_config_path = (
        Path(scene_dataset_config).expanduser().resolve() if scene_dataset_config is not None else None
    )
    if dataset_config_path is not None and not dataset_config_path.exists():
        raise FileNotFoundError(f"Habitat scene dataset config does not exist: {dataset_config_path}")

    episode_spec = spec or SyntheticObjectNavSpec(scene_path=str(scene))
    if Path(episode_spec.scene_path).expanduser().resolve() != scene:
        episode_spec = SyntheticObjectNavSpec(
            scene_path=str(scene),
            object_category=episode_spec.object_category,
            target_position=episode_spec.target_position,
            start_position=episode_spec.start_position,
            start_rotation=episode_spec.start_rotation,
        )

    habitat, habitat_sim, get_config, read_write, objectnav_dataset_cls = _load_habitat()
    scene_probe = _probe_scene(
        habitat_sim=habitat_sim,
        scene_path=scene,
        scene_dataset_config=dataset_config_path,
        seed=seed,
        sample_navigable=sample_navigable,
        sample_target_near_radius=sample_target_near_radius,
        fallback_spec=episode_spec,
    )
    episode_spec = scene_probe["episode_spec"]
    config = get_config(
        "benchmark/nav/objectnav/objectnav_hm3d.yaml",
        overrides=[f"habitat.environment.max_episode_steps={len(actions) + int(stop_at_end) + 1}"],
    )

    with read_write(config):
        config.habitat.seed = seed
        config.habitat.simulator.scene = str(scene)
        if dataset_config_path is not None:
            config.habitat.simulator.scene_dataset = str(dataset_config_path)
        config.habitat.simulator.agents.main_agent.sim_sensors.rgb_sensor.width = sensor_size
        config.habitat.simulator.agents.main_agent.sim_sensors.rgb_sensor.height = sensor_size
        config.habitat.simulator.agents.main_agent.sim_sensors.depth_sensor.width = sensor_size
        config.habitat.simulator.agents.main_agent.sim_sensors.depth_sensor.height = sensor_size
        config.habitat.simulator.agents.main_agent.sim_sensors.depth_sensor.normalize_depth = False
        config.habitat.task.measurements = {}
        config.habitat.task.lab_sensors.objectgoal_sensor.goal_spec = "TASK_CATEGORY_ID"
        config.habitat.task.lab_sensors.objectgoal_sensor.goal_spec_max_val = 10

    dataset = objectnav_dataset_cls()
    dataset.from_json(json.dumps(_synthetic_objectnav_dataset_document(episode_spec)))

    rows: list[dict[str, Any]] = []
    executed_actions: list[str] = []
    observation_keys: list[str] = []
    episode_over = False

    with habitat.Env(config=config, dataset=dataset) as env:
        observations = env.reset()
        observation_keys = sorted(observations.keys())
        rows.append(
            _trace_row(
                env=env,
                observations=observations,
                episode_id="synthetic-0",
                step_index=0,
                action="reset",
                spec=episode_spec,
                task_type="ObjectNav-v1",
                scene_path=str(scene),
            )
        )

        for index, action in enumerate(list(actions) + (["stop"] if stop_at_end else []), start=1):
            observations = env.step({"action": action})
            executed_actions.append(action)
            episode_over = bool(env.episode_over)
            rows.append(
                _trace_row(
                    env=env,
                    observations=observations,
                    episode_id="synthetic-0",
                    step_index=index,
                    action=action,
                    spec=episode_spec,
                    task_type="ObjectNav-v1",
                    scene_path=str(scene),
                )
            )
            if env.episode_over:
                break

    trace_path = output_path / "habitat_trace.csv"
    _write_csv(trace_path, rows)

    summary = _summarize_rows(
        rows,
        scene_path=str(scene),
        scene_dataset_config=str(dataset_config_path) if dataset_config_path is not None else None,
        seed=seed,
        sensor_size=sensor_size,
        actions=executed_actions,
        observation_keys=observation_keys,
        episode_over=episode_over,
        habitat_version=str(getattr(habitat, "__version__", "unknown")),
        habitat_sim_version=str(getattr(habitat_sim, "__version__", "unknown")),
        scene_probe=scene_probe,
    )
    _write_json(output_path / "summary.json", summary)
    _write_report(output_path / "report.html", summary)
    return summary


def _load_habitat():
    try:
        import habitat
        import habitat_sim
        from habitat.config import read_write
        from habitat.config.default import get_config
        from habitat.datasets.object_nav.object_nav_dataset import ObjectNavDatasetV1
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Habitat-Lab is required for this smoke. Run from the habitat conda "
            "environment, for example: conda run -n habitat python -m "
            "objectnav_core.cli.run_habitat_objectnav_smoke ..."
        ) from exc

    return habitat, habitat_sim, get_config, read_write, ObjectNavDatasetV1


def _probe_scene(
    *,
    habitat_sim: Any,
    scene_path: Path,
    scene_dataset_config: Path | None,
    seed: int,
    sample_navigable: bool,
    sample_target_near_radius: float | None,
    fallback_spec: SyntheticObjectNavSpec,
) -> dict[str, Any]:
    sim_cfg = habitat_sim.SimulatorConfiguration()
    sim_cfg.scene_id = str(scene_path)
    sim_cfg.enable_physics = False
    if scene_dataset_config is not None:
        sim_cfg.scene_dataset_config_file = str(scene_dataset_config)

    agent_cfg = habitat_sim.AgentConfiguration()
    sim = habitat_sim.Simulator(habitat_sim.Configuration(sim_cfg, [agent_cfg]))
    try:
        sim.seed(seed)
        navmesh_loaded = bool(sim.pathfinder.is_loaded)
        semantic_scene = sim.semantic_scene
        semantic_object_count = len(getattr(semantic_scene, "objects", []) or [])
        semantic_category_count = len(getattr(semantic_scene, "categories", []) or [])
        sampled_start: tuple[float, float, float] | None = None
        sampled_target: tuple[float, float, float] | None = None
        if sample_navigable and navmesh_loaded:
            start = sim.pathfinder.get_random_navigable_point()
            sampled_start = _tuple3(start)
            if sample_target_near_radius is not None:
                target = sim.pathfinder.get_random_navigable_point_near(
                    start,
                    sample_target_near_radius,
                )
                if _finite_vector3(target):
                    candidate_target = _tuple3(target)
                    if math.dist(sampled_start, candidate_target) <= sample_target_near_radius * 1.5:
                        sampled_target = candidate_target
                    else:
                        sampled_target = sampled_start
            if sampled_target is None and sample_target_near_radius is not None:
                sampled_target = sampled_start
            if sampled_target is None:
                sampled_target = _tuple3(sim.pathfinder.get_random_navigable_point())

        episode_spec = fallback_spec
        if sampled_start is not None and sampled_target is not None:
            episode_spec = SyntheticObjectNavSpec(
                scene_path=str(scene_path),
                object_category=fallback_spec.object_category,
                target_position=sampled_target,
                start_position=sampled_start,
                start_rotation=fallback_spec.start_rotation,
            )

        return {
            "episode_spec": episode_spec,
            "navmesh_loaded": navmesh_loaded,
            "sample_navigable_requested": sample_navigable,
            "sampled_navigable_start": sampled_start is not None,
            "sample_target_near_radius": sample_target_near_radius,
            "semantic_object_count": semantic_object_count,
            "semantic_category_count": semantic_category_count,
        }
    finally:
        sim.close()


def _tuple3(values: Any) -> tuple[float, float, float]:
    return (float(values[0]), float(values[1]), float(values[2]))


def _finite_vector3(values: Any) -> bool:
    return all(math.isfinite(float(values[index])) for index in range(3))


def _synthetic_objectnav_dataset_document(spec: SyntheticObjectNavSpec) -> dict[str, Any]:
    return {
        "category_to_task_category_id": {spec.object_category: 0},
        "category_to_scene_annotation_category_id": {spec.object_category: 0},
        "episodes": [
            {
                "episode_id": "synthetic-0",
                "scene_id": spec.scene_path,
                "start_position": list(spec.start_position),
                "start_rotation": list(spec.start_rotation),
                "object_category": spec.object_category,
                "goals": [
                    {
                        "position": list(spec.target_position),
                        "radius": 0.2,
                        "object_id": f"synthetic_{spec.object_category}_0",
                        "object_name": f"synthetic_{spec.object_category}",
                        "object_name_id": 0,
                        "object_category": spec.object_category,
                        "room_id": "synthetic_room",
                        "room_name": "simple_room",
                        "view_points": [],
                    }
                ],
                "shortest_paths": [],
            }
        ],
    }


def _trace_row(
    *,
    env: Any,
    observations: dict[str, Any],
    episode_id: str,
    step_index: int,
    action: str,
    spec: SyntheticObjectNavSpec,
    task_type: str,
    scene_path: str,
) -> dict[str, Any]:
    state = env.sim.get_agent_state()
    position = [float(value) for value in state.position]
    rotation_xyzw = _rotation_xyzw(state.rotation)
    depth_stats = _depth_stats(np.asarray(observations["depth"]))
    rgb_stats = _rgb_stats(np.asarray(observations["rgb"]))
    objectgoal = np.asarray(observations["objectgoal"]).reshape(-1)
    distance_to_target = math.dist(position, spec.target_position)

    return {
        "episode_id": episode_id,
        "step_index": step_index,
        "action": action,
        "task_type": task_type,
        "scene_path": scene_path,
        "object_category": spec.object_category,
        "objectgoal_id": int(objectgoal[0]),
        "agent_x": round(position[0], 6),
        "agent_y": round(position[1], 6),
        "agent_z": round(position[2], 6),
        "agent_rot_x": round(rotation_xyzw[0], 6),
        "agent_rot_y": round(rotation_xyzw[1], 6),
        "agent_rot_z": round(rotation_xyzw[2], 6),
        "agent_rot_w": round(rotation_xyzw[3], 6),
        "target_x": round(spec.target_position[0], 6),
        "target_y": round(spec.target_position[1], 6),
        "target_z": round(spec.target_position[2], 6),
        "distance_to_synthetic_target": round(distance_to_target, 6),
        "previous_step_collided": bool(getattr(env.sim, "previous_step_collided", False)),
        "episode_over": bool(env.episode_over),
        **depth_stats,
        **rgb_stats,
    }


def _rotation_xyzw(rotation: Any) -> tuple[float, float, float, float]:
    if hasattr(rotation, "vector") and hasattr(rotation, "scalar"):
        return (
            float(rotation.vector.x),
            float(rotation.vector.y),
            float(rotation.vector.z),
            float(rotation.scalar),
        )
    if all(hasattr(rotation, attr) for attr in ("x", "y", "z", "w")):
        return float(rotation.x), float(rotation.y), float(rotation.z), float(rotation.w)
    values = list(rotation)
    if len(values) != 4:
        raise ValueError(f"Expected quaternion with 4 values, got {rotation!r}")
    return float(values[0]), float(values[1]), float(values[2]), float(values[3])


def _depth_stats(depth: np.ndarray) -> dict[str, Any]:
    finite = np.isfinite(depth)
    valid = finite & (depth > 0.0)
    valid_values = depth[valid]
    if valid_values.size == 0:
        return {
            "depth_shape": "x".join(str(v) for v in depth.shape),
            "depth_min": None,
            "depth_max": None,
            "depth_mean": None,
            "depth_valid_ratio": 0.0,
        }
    return {
        "depth_shape": "x".join(str(v) for v in depth.shape),
        "depth_min": round(float(valid_values.min()), 6),
        "depth_max": round(float(valid_values.max()), 6),
        "depth_mean": round(float(valid_values.mean()), 6),
        "depth_valid_ratio": round(float(valid.mean()), 6),
    }


def _rgb_stats(rgb: np.ndarray) -> dict[str, Any]:
    return {
        "rgb_shape": "x".join(str(v) for v in rgb.shape),
        "rgb_mean": round(float(rgb.mean()), 6),
        "rgb_nonzero_ratio": round(float((rgb > 0).mean()), 6),
    }


def _summarize_rows(
    rows: Sequence[dict[str, Any]],
    *,
    scene_path: str,
    scene_dataset_config: str | None = None,
    seed: int,
    sensor_size: int,
    actions: Sequence[str],
    observation_keys: Sequence[str],
    episode_over: bool,
    habitat_version: str,
    habitat_sim_version: str,
    scene_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    depth_means = [row["depth_mean"] for row in rows if row["depth_mean"] is not None]
    valid_ratios = [row["depth_valid_ratio"] for row in rows]
    collisions = sum(1 for row in rows if row["previous_step_collided"])
    limits = [
        "Synthetic one-episode ObjectNav-v1 dataset, not an official benchmark split.",
        "Task measurements were disabled to avoid requiring a benchmark episode/navmesh pair.",
    ]
    semantic_object_count = scene_probe.get("semantic_object_count") if scene_probe else None
    if semantic_object_count:
        limits.append(
            "Semantic scene metadata was detected, but this RGB-D smoke does not export semantic observations."
        )
    else:
        limits.append("No semantic scene metadata was detected for this scene.")
    return {
        "task": "habitat_objectnav_smoke",
        "episode_type": "synthetic_objectnav_v1",
        "benchmark_dataset": False,
        "scene_path": scene_path,
        "scene_dataset_config": scene_dataset_config,
        "seed": seed,
        "sensor_size": sensor_size,
        "habitat_version": habitat_version,
        "habitat_sim_version": habitat_sim_version,
        "navmesh_loaded": bool(scene_probe.get("navmesh_loaded")) if scene_probe else None,
        "sample_navigable_requested": bool(scene_probe.get("sample_navigable_requested"))
        if scene_probe
        else False,
        "sampled_navigable_start": bool(scene_probe.get("sampled_navigable_start"))
        if scene_probe
        else False,
        "sample_target_near_radius": scene_probe.get("sample_target_near_radius")
        if scene_probe
        else None,
        "semantic_object_count": semantic_object_count,
        "semantic_category_count": scene_probe.get("semantic_category_count") if scene_probe else None,
        "trace_rows": len(rows),
        "actions": list(actions),
        "observation_keys": list(observation_keys),
        "episode_over": episode_over,
        "collision_steps": collisions,
        "mean_depth_valid_ratio": round(float(np.mean(valid_ratios)), 6) if valid_ratios else 0.0,
        "mean_depth": round(float(np.mean(depth_means)), 6) if depth_means else None,
        "artifact_files": {
            "trace": "habitat_trace.csv",
            "summary": "summary.json",
            "report": "report.html",
        },
        "limits": limits,
    }


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("Cannot write an empty Habitat trace")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    rows = "\n".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape(json.dumps(value, ensure_ascii=False))}</td></tr>"
        for key, value in summary.items()
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Habitat ObjectNav Smoke</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.45; margin: 2rem; color: #202124; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #dadce0; padding: 0.55rem; text-align: left; vertical-align: top; }}
    th {{ width: 18rem; background: #f8f9fa; }}
    code {{ background: #f1f3f4; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Habitat ObjectNav Smoke</h1>
  <table>
    {rows}
  </table>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
