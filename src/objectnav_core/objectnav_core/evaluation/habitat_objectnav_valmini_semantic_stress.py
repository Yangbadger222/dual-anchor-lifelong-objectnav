from __future__ import annotations

import csv
import gzip
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_semantic_yolo_stress import (
    DEFAULT_ACTIONS,
    DEFAULT_BREAKER_MODES,
    _apply_yolo_breaker,
    _belief_dict,
    _classify_semantic_evidence,
    _count_values,
    _decision_context,
    _depth_valid_ratio,
    _load_habitat_sim,
    _make_simulator,
    _mask_metrics,
    _write_csv,
    _write_json,
)
from objectnav_core.memory.usability import (
    DecisionType,
    EvidenceEvent,
    EvidenceType,
    MemoryBelief,
    UsabilityDecisionPolicy,
    UsabilityUpdater,
)


VALID_START_SOURCES = ("episode_start", "goal_viewpoint")
TARGET_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "tv monitor": ("tv monitor", "tv", "television", "monitor"),
    "sofa": ("sofa", "couch"),
    "plant": ("plant", "potted plant", "houseplant"),
}


@dataclass(frozen=True)
class ObjectNavValMiniEpisode:
    episode_id: str
    content_file: str
    original_scene_id: str
    resolved_scene_path: Path
    object_category: str
    start_position: tuple[float, float, float]
    start_rotation: tuple[float, float, float, float]
    goal_viewpoints: tuple[dict[str, Any], ...]
    geodesic_distance: float | None
    euclidean_distance: float | None


@dataclass(frozen=True)
class EpisodeStart:
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    source_used: str


def run_habitat_objectnav_valmini_semantic_stress(
    output_dir: str | Path,
    *,
    dataset_dir: str | Path,
    scene_root: str | Path,
    max_episodes: int | None = None,
    start_source: str = "goal_viewpoint",
    seed: int = 313,
    sensor_size: int = 96,
    actions: Sequence[str] = DEFAULT_ACTIONS,
    breaker_modes: Sequence[str] = DEFAULT_BREAKER_MODES,
    min_target_pixels: int = 24,
    min_detector_pixels: int = 20,
) -> dict[str, Any]:
    """Run semantic-mask YOLO-breaker stress from official HM3D val_mini episodes."""

    if max_episodes is not None and max_episodes <= 0:
        raise ValueError("max_episodes must be positive when provided")
    if sensor_size <= 0:
        raise ValueError("sensor_size must be positive")
    if min_target_pixels <= 0:
        raise ValueError("min_target_pixels must be positive")
    if min_detector_pixels <= 0:
        raise ValueError("min_detector_pixels must be positive")
    if not breaker_modes:
        raise ValueError("At least one breaker mode is required")
    unknown_modes = sorted(set(breaker_modes) - set(DEFAULT_BREAKER_MODES))
    if unknown_modes:
        raise ValueError(f"Unknown breaker mode(s): {', '.join(unknown_modes)}")
    if start_source not in VALID_START_SOURCES:
        raise ValueError(
            f"start_source must be one of: {', '.join(VALID_START_SOURCES)}"
        )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    dataset_path = Path(dataset_dir).expanduser().resolve()
    scene_root_path = Path(scene_root).expanduser().resolve()
    episodes = _load_valmini_episodes(
        dataset_path,
        scene_root=scene_root_path,
    )
    selected_episodes = episodes[:max_episodes] if max_episodes is not None else episodes
    if not selected_episodes:
        raise ValueError(f"No ObjectNav episodes found under {dataset_path}")

    scene_config_path = output_path / "hm3d_valmini_annotated_basis.scene_dataset_config.json"
    _write_scene_dataset_config(
        scene_config_path,
        sorted({episode.resolved_scene_path for episode in selected_episodes}),
    )

    habitat_sim = _load_habitat_sim()
    trace_rows: list[dict[str, Any]] = []
    episode_summaries: list[dict[str, Any]] = []
    scene_summaries: dict[str, dict[str, Any]] = {}
    grouped = _group_by_scene(selected_episodes)
    for scene_index, (scene, scene_episodes) in enumerate(grouped.items()):
        sim = _make_simulator(
            habitat_sim=habitat_sim,
            scene=scene,
            scene_dataset_config=scene_config_path,
            sensor_size=sensor_size,
        )
        try:
            sim.seed(seed + scene_index * 1000)
            if not sim.pathfinder.is_loaded:
                raise RuntimeError(f"Scene navmesh is not loaded: {scene}")
            semantic_id_to_category = _semantic_id_to_category(sim)
            semantic_object_count = len(getattr(sim.semantic_scene, "objects", []) or [])
            semantic_category_count = len(getattr(sim.semantic_scene, "categories", []) or [])
            if semantic_object_count <= 0:
                raise RuntimeError(f"Scene semantic metadata is empty: {scene}")
            scene_summaries[str(scene)] = {
                "episodes": len(scene_episodes),
                "semantic_object_count": semantic_object_count,
                "semantic_category_count": semantic_category_count,
                "navmesh_loaded": bool(sim.pathfinder.is_loaded),
            }
            for episode in scene_episodes:
                episode_index = selected_episodes.index(episode)
                rng = np.random.default_rng(seed + episode_index)
                breaker_mode = breaker_modes[episode_index % len(breaker_modes)]
                rows, episode_summary = _run_official_episode(
                    sim=sim,
                    episode=episode,
                    episode_index=episode_index,
                    rng=rng,
                    breaker_mode=breaker_mode,
                    start_source=start_source,
                    actions=actions,
                    semantic_id_to_category=semantic_id_to_category,
                    min_target_pixels=min_target_pixels,
                    min_detector_pixels=min_detector_pixels,
                )
                trace_rows.extend(rows)
                episode_summaries.append(episode_summary)
        finally:
            sim.close()

    _write_csv(output_path / "objectnav_valmini_semantic_trace.csv", trace_rows)
    summary = _summarize(
        output_path=output_path,
        dataset_dir=dataset_path,
        scene_root=scene_root_path,
        scene_dataset_config=scene_config_path,
        episodes=selected_episodes,
        start_source=start_source,
        seed=seed,
        sensor_size=sensor_size,
        actions=actions,
        breaker_modes=breaker_modes,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
        scene_summaries=scene_summaries,
        rows=trace_rows,
        episode_summaries=episode_summaries,
    )
    _write_json(output_path / "summary.json", summary)
    _write_report(output_path / "report.html", summary)
    return summary


def _load_valmini_episodes(
    dataset_dir: Path,
    *,
    scene_root: Path,
) -> list[ObjectNavValMiniEpisode]:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"ObjectNav dataset directory does not exist: {dataset_dir}")
    content_dir = dataset_dir / "content"
    if not content_dir.exists() and dataset_dir.name == "content":
        content_dir = dataset_dir
    if not content_dir.exists():
        raise FileNotFoundError(f"ObjectNav content directory does not exist: {content_dir}")

    episodes: list[ObjectNavValMiniEpisode] = []
    for content_file in sorted(content_dir.glob("*.json.gz")):
        episodes.extend(
            _load_content_file(
                content_file,
                scene_root=scene_root,
            )
        )
    return episodes


def _load_content_file(
    content_file: Path,
    *,
    scene_root: Path,
) -> list[ObjectNavValMiniEpisode]:
    with gzip.open(content_file, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    goals_by_category = payload.get("goals_by_category", {})
    episodes: list[ObjectNavValMiniEpisode] = []
    for raw_episode in payload.get("episodes", []):
        original_scene_id = str(raw_episode["scene_id"])
        object_category = str(raw_episode["object_category"])
        scene_path = _resolve_hm3d_scene_path(original_scene_id, scene_root=scene_root)
        scene_filename = Path(original_scene_id).name
        goal_key = f"{scene_filename}_{object_category}"
        goal_viewpoints = tuple(
            viewpoint
            for goal in goals_by_category.get(goal_key, [])
            for viewpoint in goal.get("view_points", [])
        )
        info = raw_episode.get("info", {}) or {}
        episodes.append(
            ObjectNavValMiniEpisode(
                episode_id=str(raw_episode["episode_id"]),
                content_file=str(content_file),
                original_scene_id=original_scene_id,
                resolved_scene_path=scene_path,
                object_category=object_category,
                start_position=_tuple3(raw_episode["start_position"]),
                start_rotation=_tuple4(raw_episode["start_rotation"]),
                goal_viewpoints=goal_viewpoints,
                geodesic_distance=_optional_float(info.get("geodesic_distance")),
                euclidean_distance=_optional_float(info.get("euclidean_distance")),
            )
        )
    return episodes


def _resolve_hm3d_scene_path(scene_id: str, *, scene_root: Path) -> Path:
    scene_id_path = Path(scene_id)
    if scene_id_path.is_absolute() and scene_id_path.exists():
        return scene_id_path.resolve()
    parts = scene_id_path.parts
    if len(parts) >= 4 and parts[0] == "hm3d":
        split_name, scene_dir, scene_file = parts[1], parts[2], parts[3]
        candidates = [
            scene_root / split_name / scene_dir / scene_file,
            scene_root / "habitat" / scene_dir / scene_file,
            scene_root / "example" / scene_dir / scene_file,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
    candidate = scene_root / scene_id_path
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(
        f"Could not resolve ObjectNav scene_id {scene_id!r} under {scene_root}"
    )


def _write_scene_dataset_config(path: Path, scene_paths: Sequence[Path]) -> None:
    if not scene_paths:
        raise ValueError("Cannot write a Habitat scene config without scenes")
    payload = {
        "stages": {
            "paths": {
                ".glb": [str(scene.expanduser().resolve()) for scene in scene_paths]
            },
            "default_attributes": {
                "shader_type": "flat",
                "up": [0, 0, 1],
                "front": [0, 1, 0],
                "origin": [0, 0, 0],
                "semantic_descriptor_filename": "%%CONFIG_NAME_AS_ASSET_FILENAME%%.semantic.txt",
                "semantic_asset": "%%CONFIG_NAME_AS_ASSET_FILENAME%%.semantic.glb",
                "has_semantic_textures": True,
            },
        },
        "objects": {},
        "light_setups": {},
        "scene_instances": {
            "default_attributes": {"default_lighting": "no_lights"},
            "paths": {".json": []},
        },
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _group_by_scene(
    episodes: Sequence[ObjectNavValMiniEpisode],
) -> dict[Path, list[ObjectNavValMiniEpisode]]:
    grouped: dict[Path, list[ObjectNavValMiniEpisode]] = {}
    for episode in episodes:
        grouped.setdefault(episode.resolved_scene_path, []).append(episode)
    return grouped


def _run_official_episode(
    *,
    sim: Any,
    episode: ObjectNavValMiniEpisode,
    episode_index: int,
    rng: np.random.Generator,
    breaker_mode: str,
    start_source: str,
    actions: Sequence[str],
    semantic_id_to_category: dict[int, str],
    min_target_pixels: int,
    min_detector_pixels: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
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
    updater = UsabilityUpdater()
    policy = UsabilityDecisionPolicy()
    belief = MemoryBelief(p_existence=0.9, p_location_valid=0.85, p_usable=0.85)
    rows: list[dict[str, Any]] = []
    negative_streak = 0
    collision_steps = 0
    false_positive_positive_rows = 0
    missed_visible_target_rows = 0
    target_visible_rows = 0
    total_actions = ["reset", *actions]

    for step_index, action in enumerate(total_actions):
        if action != "reset":
            observations = sim.step(action)
        semantic = np.asarray(observations["semantic"])
        depth = np.asarray(observations["depth"])
        oracle_mask = np.isin(semantic, list(target_semantic_ids))
        breaker = _apply_yolo_breaker(
            oracle_mask,
            rng=rng,
            mode=breaker_mode,
        )
        mask_metrics = _mask_metrics(
            oracle_mask=oracle_mask,
            detector_mask=breaker.detector_mask,
        )
        depth_valid_ratio = _depth_valid_ratio(depth)
        collided = bool(getattr(sim, "previous_step_collided", False))
        evidence_type, evidence_strength, quarantined, evidence_reason = _classify_semantic_evidence(
            action=action,
            collided=collided,
            depth_valid_ratio=depth_valid_ratio,
            metrics=mask_metrics,
            min_target_pixels=min_target_pixels,
            min_detector_pixels=min_detector_pixels,
        )
        if not target_semantic_ids and evidence_reason == "target_out_of_current_view":
            evidence_reason = "target_category_not_in_semantic_scene"
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
        belief = updater.apply(belief, event)
        decision = policy.choose(
            belief,
            _decision_context(
                step_index=step_index,
                total_steps=len(total_actions),
                negative_streak=negative_streak,
                metrics=mask_metrics,
            ),
        )
        if collided:
            collision_steps += 1
        false_positive_positive = (
            evidence_type is EvidenceType.POSITIVE
            and mask_metrics["detector_precision"] < 0.25
        )
        missed_visible_target = (
            mask_metrics["oracle_target_pixels"] >= min_target_pixels
            and mask_metrics["detector_pixels"] < min_detector_pixels
        )
        target_visible = mask_metrics["oracle_target_pixels"] >= min_target_pixels
        false_positive_positive_rows += int(false_positive_positive)
        missed_visible_target_rows += int(missed_visible_target)
        target_visible_rows += int(target_visible)

        rows.append(
            {
                "episode_index": episode_index,
                "episode_id": episode.episode_id,
                "content_file": episode.content_file,
                "original_scene_id": episode.original_scene_id,
                "resolved_scene_path": str(episode.resolved_scene_path),
                "object_category": episode.object_category,
                "breaker_mode": breaker_mode,
                "start_source_requested": start_source,
                "start_source_used": start.source_used,
                "goal_viewpoint_count": len(episode.goal_viewpoints),
                "geodesic_distance": episode.geodesic_distance,
                "euclidean_distance": episode.euclidean_distance,
                "step_index": step_index,
                "action": action,
                "target_semantic_id_count": len(target_semantic_ids),
                "target_semantic_ids": ";".join(str(value) for value in target_semantic_ids),
                "target_visible": target_visible,
                "depth_valid_ratio": depth_valid_ratio,
                "previous_step_collided": collided,
                "miss_applied": breaker.miss_applied,
                "fly_point_pixels": breaker.fly_point_pixels,
                "edge_break_pixels": breaker.edge_break_pixels,
                **mask_metrics,
                "false_positive_positive": false_positive_positive,
                "missed_visible_target": missed_visible_target,
                "evidence_type": evidence_type.value,
                "evidence_strength": round(evidence_strength, 6),
                "evidence_quarantined": quarantined,
                "evidence_reason": evidence_reason,
                "p_existence": round(belief.p_existence, 6),
                "p_location_valid": round(belief.p_location_valid, 6),
                "p_usable": round(belief.p_usable, 6),
                "p_valid": round(decision.p_valid, 6),
                "decision": decision.decision.value,
                "cost_trust": round(decision.expected_costs[DecisionType.TRUST], 6),
                "cost_verify": round(decision.expected_costs[DecisionType.VERIFY], 6),
                "cost_search": round(decision.expected_costs[DecisionType.SEARCH], 6),
                "cost_retire": round(decision.expected_costs[DecisionType.RETIRE], 6),
                "negative_streak": negative_streak,
            }
        )

    return rows, {
        "episode_index": episode_index,
        "episode_id": episode.episode_id,
        "original_scene_id": episode.original_scene_id,
        "resolved_scene_path": str(episode.resolved_scene_path),
        "object_category": episode.object_category,
        "breaker_mode": breaker_mode,
        "start_source_used": start.source_used,
        "target_semantic_id_count": len(target_semantic_ids),
        "trace_rows": len(rows),
        "target_visible_rows": target_visible_rows,
        "collision_steps": collision_steps,
        "false_positive_positive_rows": false_positive_positive_rows,
        "missed_visible_target_rows": missed_visible_target_rows,
        "final_belief": _belief_dict(belief),
        "final_p_valid": round(belief.p_valid, 6),
    }


def _select_episode_start(
    episode: ObjectNavValMiniEpisode,
    *,
    start_source: str,
) -> EpisodeStart:
    if start_source == "goal_viewpoint" and episode.goal_viewpoints:
        viewpoint = episode.goal_viewpoints[0]
        agent_state = viewpoint.get("agent_state", {})
        return EpisodeStart(
            position=_tuple3(agent_state["position"]),
            rotation=_tuple4(agent_state["rotation"]),
            source_used="goal_viewpoint",
        )
    return EpisodeStart(
        position=episode.start_position,
        rotation=episode.start_rotation,
        source_used="episode_start",
    )


def _semantic_ids_for_target_category(
    semantic_id_to_category: dict[int, str],
    target_category: str,
) -> tuple[int, ...]:
    aliases = _target_aliases(target_category)
    matches = [
        semantic_id
        for semantic_id, category in semantic_id_to_category.items()
        if _normalize_category(category) in aliases
    ]
    return tuple(sorted(matches))


def _target_aliases(target_category: str) -> set[str]:
    normalized = _normalize_category(target_category)
    aliases = {normalized}
    aliases.update(TARGET_CATEGORY_ALIASES.get(normalized, ()))
    return {_normalize_category(alias) for alias in aliases}


def _normalize_category(category: str) -> str:
    return category.strip().lower().replace("_", " ")


def _semantic_id_to_category(sim: Any) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for obj in getattr(sim.semantic_scene, "objects", []) or []:
        if obj is None:
            continue
        semantic_id = int(getattr(obj, "semantic_id", -1))
        if semantic_id < 0:
            continue
        category = getattr(obj, "category", None)
        name = "unknown"
        if category is not None:
            category_name = getattr(category, "name", None)
            if callable(category_name):
                name = str(category_name())
            elif category_name is not None:
                name = str(category_name)
        mapping[semantic_id] = name
    return mapping


def _summarize(
    *,
    output_path: Path,
    dataset_dir: Path,
    scene_root: Path,
    scene_dataset_config: Path,
    episodes: Sequence[ObjectNavValMiniEpisode],
    start_source: str,
    seed: int,
    sensor_size: int,
    actions: Sequence[str],
    breaker_modes: Sequence[str],
    min_target_pixels: int,
    min_detector_pixels: int,
    scene_summaries: dict[str, dict[str, Any]],
    rows: Sequence[dict[str, Any]],
    episode_summaries: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    mode_summaries = _mode_summaries(rows, episode_summaries, breaker_modes)
    category_summaries: dict[str, dict[str, Any]] = {}
    for category in sorted({episode.object_category for episode in episodes}):
        category_rows = [row for row in rows if row["object_category"] == category]
        category_episodes = [
            episode for episode in episode_summaries if episode["object_category"] == category
        ]
        category_summaries[category] = _summary_block(category_rows, category_episodes)

    final_values = [episode["final_p_valid"] for episode in episode_summaries]
    target_visible_episodes = sum(
        int(episode["target_visible_rows"] > 0) for episode in episode_summaries
    )
    return {
        "task": "habitat_objectnav_valmini_semantic_stress",
        "benchmark_dataset": True,
        "official_objectnav_metrics": False,
        "dataset_dir": str(dataset_dir),
        "scene_root": str(scene_root),
        "scene_dataset_config": str(scene_dataset_config),
        "episodes_requested": len(episodes),
        "episodes_completed": len(episode_summaries),
        "scenes": sorted({str(episode.resolved_scene_path) for episode in episodes}),
        "start_source": start_source,
        "seed": seed,
        "sensor_size": sensor_size,
        "actions": list(actions),
        "breaker_modes": list(breaker_modes),
        "min_target_pixels": min_target_pixels,
        "min_detector_pixels": min_detector_pixels,
        "trace_rows": len(rows),
        "evidence_counts": _count_values(rows, "evidence_type"),
        "decision_counts": _count_values(rows, "decision"),
        "target_visible_rows": sum(int(row["target_visible"]) for row in rows),
        "target_visible_episodes": target_visible_episodes,
        "false_positive_positive_rows": sum(
            int(row["false_positive_positive"]) for row in rows
        ),
        "missed_visible_target_rows": sum(
            int(row["missed_visible_target"]) for row in rows
        ),
        "mean_final_p_valid": round(float(np.mean(final_values)), 6)
        if final_values
        else None,
        "mode_summaries": mode_summaries,
        "category_summaries": category_summaries,
        "scene_summaries": scene_summaries,
        "episode_summaries": list(episode_summaries),
        "artifact_files": {
            "trace": "objectnav_valmini_semantic_trace.csv",
            "summary": "summary.json",
            "report": "report.html",
            "scene_dataset_config": scene_dataset_config.name,
        },
        "artifact_dir": str(output_path),
        "limits": [
            "Uses official HM3D ObjectNav val_mini episode metadata and local HM3D scene assets.",
            "Reports no official success, SPL, or navigation-policy benchmark score.",
            "Runs scripted actions after the selected episode or goal-viewpoint start pose.",
            "Uses Habitat semantic ids as oracle detector input before synthetic YOLO-breaker corruption.",
            "Does not run a learned YOLO model.",
        ],
    }


def _mode_summaries(
    rows: Sequence[dict[str, Any]],
    episode_summaries: Sequence[dict[str, Any]],
    breaker_modes: Sequence[str],
) -> dict[str, dict[str, Any]]:
    return {
        mode: _summary_block(
            [row for row in rows if row["breaker_mode"] == mode],
            [episode for episode in episode_summaries if episode["breaker_mode"] == mode],
        )
        for mode in breaker_modes
    }


def _summary_block(
    rows: Sequence[dict[str, Any]],
    episode_summaries: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    final_values = [episode["final_p_valid"] for episode in episode_summaries]
    return {
        "rows": len(rows),
        "episodes": len(episode_summaries),
        "evidence_counts": _count_values(rows, "evidence_type"),
        "decision_counts": _count_values(rows, "decision"),
        "target_visible_rows": sum(int(row["target_visible"]) for row in rows),
        "target_visible_episodes": sum(
            int(episode["target_visible_rows"] > 0) for episode in episode_summaries
        ),
        "false_positive_positive_rows": sum(
            int(row["false_positive_positive"]) for row in rows
        ),
        "missed_visible_target_rows": sum(
            int(row["missed_visible_target"]) for row in rows
        ),
        "mean_final_p_valid": round(float(np.mean(final_values)), 6)
        if final_values
        else None,
    }


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    mode_rows = "\n".join(
        _render_summary_row(mode, payload)
        for mode, payload in summary["mode_summaries"].items()
    )
    category_rows = "\n".join(
        _render_summary_row(category, payload)
        for category, payload in summary["category_summaries"].items()
    )
    evidence_rows = "\n".join(
        f"<tr><td>{escape(key)}</td><td>{count}</td></tr>"
        for key, count in summary["evidence_counts"].items()
    )
    decision_rows = "\n".join(
        f"<tr><td>{escape(key)}</td><td>{count}</td></tr>"
        for key, count in summary["decision_counts"].items()
    )
    limits = "".join(
        f"<li>{escape(str(limit))}</li>" for limit in summary["limits"]
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Habitat ObjectNav Val-Mini Semantic Stress</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.45; margin: 2rem; color: #202124; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 1.5rem; }}
    th, td {{ border: 1px solid #dadce0; padding: 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #f8f9fa; }}
    code {{ background: #f1f3f4; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Habitat ObjectNav Val-Mini Semantic Stress</h1>
  <p>Episodes: <code>{summary["episodes_completed"]}</code>; rows: <code>{summary["trace_rows"]}</code>; target-visible episodes: <code>{summary["target_visible_episodes"]}</code>; mean final p_valid: <code>{summary["mean_final_p_valid"]}</code>.</p>
  <h2>Breaker Modes</h2>
  <table>
    <tr><th>Group</th><th>Episodes</th><th>Rows</th><th>Target Visible Rows</th><th>Mean Final p_valid</th><th>False Positive Positives</th><th>Missed Visible Targets</th></tr>
    {mode_rows}
  </table>
  <h2>Categories</h2>
  <table>
    <tr><th>Group</th><th>Episodes</th><th>Rows</th><th>Target Visible Rows</th><th>Mean Final p_valid</th><th>False Positive Positives</th><th>Missed Visible Targets</th></tr>
    {category_rows}
  </table>
  <h2>Evidence Counts</h2>
  <table><tr><th>Evidence</th><th>Count</th></tr>{evidence_rows}</table>
  <h2>Decision Counts</h2>
  <table><tr><th>Decision</th><th>Count</th></tr>{decision_rows}</table>
  <h2>Limits</h2>
  <ul>{limits}</ul>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _render_summary_row(label: str, payload: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td><code>{escape(label)}</code></td>"
        f"<td>{payload['episodes']}</td>"
        f"<td>{payload['rows']}</td>"
        f"<td>{payload['target_visible_rows']}</td>"
        f"<td>{payload['mean_final_p_valid']}</td>"
        f"<td>{payload['false_positive_positive_rows']}</td>"
        f"<td>{payload['missed_visible_target_rows']}</td>"
        "</tr>"
    )


def _tuple3(values: Sequence[Any]) -> tuple[float, float, float]:
    if len(values) != 3:
        raise ValueError(f"Expected 3 values, got {values!r}")
    return (float(values[0]), float(values[1]), float(values[2]))


def _tuple4(values: Sequence[Any]) -> tuple[float, float, float, float]:
    if len(values) != 4:
        raise ValueError(f"Expected 4 values, got {values!r}")
    return (float(values[0]), float(values[1]), float(values[2]), float(values[3]))


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
