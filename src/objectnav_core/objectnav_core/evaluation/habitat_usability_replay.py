from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from objectnav_core.evaluation.habitat_objectnav_smoke import (
    run_habitat_objectnav_smoke,
)
from objectnav_core.memory.usability import (
    DecisionContext,
    DecisionType,
    EvidenceEvent,
    EvidenceType,
    MemoryBelief,
    UsabilityDecisionPolicy,
    UsabilityUpdater,
)


DEFAULT_REPLAY_ACTIONS: tuple[tuple[str, ...], ...] = (
    ("move_forward", "turn_left", "move_forward", "turn_right", "move_forward"),
    ("turn_left", "move_forward", "move_forward", "turn_right", "move_forward"),
    ("move_forward", "move_forward", "turn_left", "move_forward", "turn_left"),
)


@dataclass(frozen=True)
class ReplayScenario:
    name: str
    target_near_radius: float | None


DEFAULT_REPLAY_SCENARIOS: tuple[ReplayScenario, ...] = (
    ReplayScenario(name="near_anchor", target_near_radius=1.0),
    ReplayScenario(name="local_verify", target_near_radius=2.5),
    ReplayScenario(name="random_anchor", target_near_radius=None),
)


def run_habitat_usability_replay(
    output_dir: str | Path,
    *,
    scene_paths: Sequence[str | Path],
    scene_dataset_config: str | Path | None = None,
    episodes: int = 9,
    seed: int = 23,
    sensor_size: int = 96,
    actions: Sequence[str] | None = None,
    positive_radius: float = 1.25,
    free_radius: float = 2.5,
) -> dict[str, Any]:
    """Run multiple Habitat-Lab ObjectNav smokes and replay usability memory.

    The Habitat episodes are still synthetic ObjectNav-v1 episodes, but the
    observations, collisions, depth health, poses, and navmesh sampling come
    from Habitat. This gives a middle layer between pure unit tests and an
    official ObjectNav benchmark run.
    """

    if not scene_paths:
        raise ValueError("At least one Habitat scene path is required")
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    if sensor_size <= 0:
        raise ValueError("sensor_size must be positive")
    if positive_radius <= 0.0:
        raise ValueError("positive_radius must be positive")
    if free_radius < positive_radius:
        raise ValueError("free_radius must be greater than or equal to positive_radius")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    scene_config = (
        Path(scene_dataset_config).expanduser().resolve()
        if scene_dataset_config is not None
        else None
    )
    scenes = [Path(path).expanduser().resolve() for path in scene_paths]

    aggregate_trace_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    episode_summaries: list[dict[str, Any]] = []

    for episode_index in range(episodes):
        scene = scenes[episode_index % len(scenes)]
        scenario = DEFAULT_REPLAY_SCENARIOS[episode_index % len(DEFAULT_REPLAY_SCENARIOS)]
        action_sequence = tuple(actions) if actions is not None else _actions_for_episode(episode_index)
        episode_dir = output_path / f"episode_{episode_index:03d}"
        smoke_summary = run_habitat_objectnav_smoke(
            episode_dir,
            scene_path=scene,
            scene_dataset_config=scene_config,
            seed=seed + episode_index,
            sensor_size=sensor_size,
            actions=action_sequence,
            stop_at_end=True,
            sample_navigable=True,
            sample_target_near_radius=scenario.target_near_radius,
        )
        trace_rows = _read_csv(episode_dir / "habitat_trace.csv")
        for row in trace_rows:
            aggregate_trace_rows.append(
                {
                    "replay_episode_index": episode_index,
                    "replay_scenario": scenario.name,
                    "source_episode_id": row["episode_id"],
                    **row,
                }
            )

        episode_replay_rows, episode_summary = _replay_algorithm(
            trace_rows,
            episode_index=episode_index,
            scenario=scenario,
            scene_path=str(scene),
            smoke_summary=smoke_summary,
            positive_radius=positive_radius,
            free_radius=free_radius,
        )
        replay_rows.extend(episode_replay_rows)
        episode_summaries.append(episode_summary)

    _write_csv(output_path / "habitat_trace.csv", aggregate_trace_rows)
    _write_csv(output_path / "usability_replay.csv", replay_rows)

    summary = _summarize_replay(
        scenes=scenes,
        scene_dataset_config=scene_config,
        episodes_requested=episodes,
        seed=seed,
        sensor_size=sensor_size,
        positive_radius=positive_radius,
        free_radius=free_radius,
        replay_rows=replay_rows,
        episode_summaries=episode_summaries,
    )
    _write_json(output_path / "summary.json", summary)
    _write_report(output_path / "report.html", summary)
    return summary


def _actions_for_episode(index: int) -> tuple[str, ...]:
    return DEFAULT_REPLAY_ACTIONS[index % len(DEFAULT_REPLAY_ACTIONS)]


def _replay_algorithm(
    trace_rows: Sequence[dict[str, str]],
    *,
    episode_index: int,
    scenario: ReplayScenario,
    scene_path: str,
    smoke_summary: dict[str, Any],
    positive_radius: float,
    free_radius: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    updater = UsabilityUpdater()
    policy = UsabilityDecisionPolicy()
    belief = MemoryBelief(p_existence=0.9, p_location_valid=0.85, p_usable=0.85)
    replay_rows: list[dict[str, Any]] = []
    previous_distance: float | None = None
    negative_streak = 0
    min_distance: float | None = None
    collision_steps = 0

    total_steps = len(trace_rows)
    for local_index, row in enumerate(trace_rows):
        distance = _float_value(row, "distance_to_synthetic_target")
        min_distance = distance if min_distance is None else min(min_distance, distance)
        evidence_type, strength = _classify_evidence(
            row,
            previous_distance=previous_distance,
            positive_radius=positive_radius,
            free_radius=free_radius,
        )
        if evidence_type is EvidenceType.POSITIVE:
            negative_streak = 0
        elif evidence_type in {
            EvidenceType.FREE,
            EvidenceType.NON_CONFIRMATION,
            EvidenceType.ACCESS_BLOCKED,
            EvidenceType.SCENE_CHANGED,
        }:
            negative_streak += 1

        event = EvidenceEvent(evidence_type=evidence_type, strength=strength)
        belief = updater.apply(belief, event)
        context = _decision_context(
            distance=distance,
            step_index=local_index,
            total_steps=total_steps,
            negative_streak=negative_streak,
            belief=belief,
        )
        decision = policy.choose(belief, context)
        if _bool_value(row, "previous_step_collided"):
            collision_steps += 1

        replay_rows.append(
            {
                "replay_episode_index": episode_index,
                "replay_scenario": scenario.name,
                "scene_path": scene_path,
                "source_episode_id": row["episode_id"],
                "step_index": int(row["step_index"]),
                "action": row["action"],
                "distance_to_synthetic_target": round(distance, 6),
                "depth_valid_ratio": _float_value(row, "depth_valid_ratio"),
                "previous_step_collided": _bool_value(row, "previous_step_collided"),
                "evidence_type": evidence_type.value,
                "evidence_strength": round(strength, 6),
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
        previous_distance = distance

    return replay_rows, {
        "episode_index": episode_index,
        "scenario": scenario.name,
        "scene_path": scene_path,
        "trace_rows": len(trace_rows),
        "episode_over": bool(smoke_summary.get("episode_over")),
        "navmesh_loaded": bool(smoke_summary.get("navmesh_loaded")),
        "semantic_object_count": smoke_summary.get("semantic_object_count"),
        "collision_steps": collision_steps,
        "min_distance_to_synthetic_target": round(min_distance, 6)
        if min_distance is not None
        else None,
        "final_belief": _belief_dict(belief),
        "final_p_valid": round(belief.p_valid, 6),
    }


def _classify_evidence(
    row: dict[str, str],
    *,
    previous_distance: float | None,
    positive_radius: float,
    free_radius: float,
) -> tuple[EvidenceType, float]:
    distance = _float_value(row, "distance_to_synthetic_target")
    depth_valid_ratio = _float_value(row, "depth_valid_ratio")
    if row["action"] == "reset":
        return EvidenceType.UNKNOWN, 0.2
    if _bool_value(row, "previous_step_collided"):
        return EvidenceType.ACCESS_BLOCKED, 1.0
    if depth_valid_ratio < 0.25:
        return EvidenceType.UNKNOWN, 0.8
    if depth_valid_ratio < 0.75:
        return EvidenceType.OCCLUDED, round(0.75 - depth_valid_ratio, 6)
    if distance <= positive_radius:
        closeness = (positive_radius - distance) / positive_radius
        return EvidenceType.POSITIVE, round(1.0 + max(0.0, closeness), 6)
    if distance <= free_radius:
        local_strength = 0.7 + 0.3 * ((free_radius - distance) / free_radius)
        return EvidenceType.FREE, round(local_strength, 6)
    if previous_distance is not None and distance < previous_distance - 0.05:
        return EvidenceType.NON_CONFIRMATION, 0.55
    return EvidenceType.NON_CONFIRMATION, 0.85


def _decision_context(
    *,
    distance: float,
    step_index: int,
    total_steps: int,
    negative_streak: int,
    belief: MemoryBelief,
) -> DecisionContext:
    d_nav = max(0.25, distance)
    d_verify = 2.0 + 0.15 * d_nav
    c_search = 12.0 + 2.0 * min(d_nav, 6.0)
    return DecisionContext(
        d_nav=d_nav,
        d_verify=d_verify,
        c_fail=14.0,
        c_search=c_search,
        b_remaining=max(0.0, float(total_steps - step_index - 1)),
        verification_repeatedly_failed=negative_streak >= 4 and belief.p_usable < 0.35,
    )


def _summarize_replay(
    *,
    scenes: Sequence[Path],
    scene_dataset_config: Path | None,
    episodes_requested: int,
    seed: int,
    sensor_size: int,
    positive_radius: float,
    free_radius: float,
    replay_rows: Sequence[dict[str, Any]],
    episode_summaries: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    final_p_values = [episode["final_p_valid"] for episode in episode_summaries]
    min_distances = [
        episode["min_distance_to_synthetic_target"]
        for episode in episode_summaries
        if episode["min_distance_to_synthetic_target"] is not None
    ]
    return {
        "task": "habitat_usability_replay",
        "episode_type": "synthetic_objectnav_v1_multi_episode",
        "benchmark_dataset": False,
        "episodes_requested": episodes_requested,
        "episodes_completed": len(episode_summaries),
        "scene_paths": [str(scene) for scene in scenes],
        "scene_dataset_config": str(scene_dataset_config) if scene_dataset_config else None,
        "seed": seed,
        "sensor_size": sensor_size,
        "positive_radius": positive_radius,
        "free_radius": free_radius,
        "trace_rows": len(replay_rows),
        "evidence_counts": _count_values(replay_rows, "evidence_type"),
        "decision_counts": _count_values(replay_rows, "decision"),
        "mean_final_p_valid": round(float(np.mean(final_p_values)), 6)
        if final_p_values
        else None,
        "min_distance_to_synthetic_target": round(float(min(min_distances)), 6)
        if min_distances
        else None,
        "episode_summaries": list(episode_summaries),
        "artifact_files": {
            "habitat_trace": "habitat_trace.csv",
            "usability_replay": "usability_replay.csv",
            "summary": "summary.json",
            "report": "report.html",
            "per_episode_smoke_dirs": "episode_*/",
        },
        "limits": [
            "Uses real Habitat scene loading, RGB-D observations, navmesh sampling, and collisions.",
            "Uses synthetic ObjectNav-v1 episodes, not an official ObjectNav benchmark split.",
            "Evidence labels are deterministic proxies from target distance, depth health, and collision state.",
            "No learned detector, success, SPL, or Habitat leaderboard metric is claimed.",
        ],
    }


def _count_values(rows: Sequence[dict[str, Any]], key: str) -> dict[str, int]:
    values = {value.value: 0 for value in EvidenceType} if key == "evidence_type" else {}
    if key == "decision":
        values = {value.value: 0 for value in DecisionType}
    for row in rows:
        value = str(row[key])
        values[value] = values.get(value, 0) + 1
    return values


def _belief_dict(belief: MemoryBelief) -> dict[str, float]:
    return {
        "p_existence": round(belief.p_existence, 6),
        "p_location_valid": round(belief.p_location_valid, 6),
        "p_usable": round(belief.p_usable, 6),
        "p_valid": round(belief.p_valid, 6),
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    evidence_rows = "\n".join(
        f"<tr><td>{escape(key)}</td><td>{count}</td></tr>"
        for key, count in summary["evidence_counts"].items()
    )
    decision_rows = "\n".join(
        f"<tr><td>{escape(key)}</td><td>{count}</td></tr>"
        for key, count in summary["decision_counts"].items()
    )
    episode_rows = "\n".join(
        _render_episode_row(episode) for episode in summary["episode_summaries"]
    )
    limits = "".join(
        f"<li>{escape(str(limit))}</li>" for limit in summary["limits"]
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Habitat Usability Replay</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.45; margin: 2rem; color: #202124; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 1.5rem; }}
    th, td {{ border: 1px solid #dadce0; padding: 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #f8f9fa; }}
    code {{ background: #f1f3f4; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Habitat Usability Replay</h1>
  <p>Episodes: <code>{summary["episodes_completed"]}</code>; trace rows: <code>{summary["trace_rows"]}</code>; mean final p_valid: <code>{summary["mean_final_p_valid"]}</code>.</p>
  <h2>Evidence Counts</h2>
  <table><tr><th>Evidence</th><th>Count</th></tr>{evidence_rows}</table>
  <h2>Decision Counts</h2>
  <table><tr><th>Decision</th><th>Count</th></tr>{decision_rows}</table>
  <h2>Episodes</h2>
  <table>
    <tr><th>Episode</th><th>Scenario</th><th>Rows</th><th>Collisions</th><th>Min Distance</th><th>Final p_valid</th></tr>
    {episode_rows}
  </table>
  <h2>Limits</h2>
  <ul>{limits}</ul>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _render_episode_row(episode: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td>{episode['episode_index']}</td>"
        f"<td><code>{escape(str(episode['scenario']))}</code></td>"
        f"<td>{episode['trace_rows']}</td>"
        f"<td>{episode['collision_steps']}</td>"
        f"<td>{episode['min_distance_to_synthetic_target']}</td>"
        f"<td>{episode['final_p_valid']}</td>"
        "</tr>"
    )


def _float_value(row: dict[str, str], key: str) -> float:
    value = row[key]
    if value in {"", "None", "null"}:
        return 0.0
    return float(value)


def _bool_value(row: dict[str, str], key: str) -> bool:
    value = row[key]
    return value is True or str(value).lower() in {"1", "true", "yes"}
