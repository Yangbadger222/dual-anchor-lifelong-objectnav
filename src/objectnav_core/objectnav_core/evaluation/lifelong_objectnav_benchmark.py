from __future__ import annotations

import csv
import json
from html import escape
from pathlib import Path
from typing import Any, Sequence

from objectnav_core.evaluation.logger import TrialLogger
from objectnav_core.mapping.fixtures import build_multiroom_grid
from objectnav_core.mapping.frontiers import extract_frontier_clusters
from objectnav_core.mapping.grid import CellState
from objectnav_core.memory.sqlite_store import SQLiteMemoryStore
from objectnav_core.models import (
    MemoryState,
    ObjectObservation,
    ObjectConfig,
    Pose2D,
    SceneConfig,
    TrialEvent,
    TrialMetrics,
    TrialResult,
    make_default_multiroom_lifelong_scene,
)
from objectnav_core.planning.memory_guided import (
    NavigationCandidate,
    select_memory_guided_candidate,
)
from objectnav_core.planning.viewpoints import plan_verification_viewpoint
from objectnav_core.simulation.navigation import AStarGridNavigationClient
from objectnav_core.simulation.observations import ConfigTruthObjectSource


POLICIES: tuple[str, ...] = ("memory_guided", "frontier_only")
EPISODES: tuple[str, ...] = (
    "discover",
    "reuse_different_start",
    "stale_repair",
)
TARGET_CLASS = "plant"
EPISODE_MAX_STEPS = 36


def run_lifelong_objectnav_benchmark(
    output_dir: str | Path,
    *,
    policies: Sequence[str] = POLICIES,
    scene: SceneConfig | None = None,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    scene_config = scene or make_default_multiroom_lifelong_scene()
    unknown_policies = sorted(set(policies) - set(POLICIES))
    if unknown_policies:
        raise ValueError(f"unknown policy/policies: {', '.join(unknown_policies)}")

    all_policy_summaries: dict[str, Any] = {}
    artifact_files: dict[str, Any] = {
        "summary": "summary.json",
        "report": "report.html",
    }
    for policy_name in policies:
        policy_dir = output_path / policy_name
        policy_dir.mkdir(parents=True, exist_ok=True)
        runner = LifelongObjectNavBenchmarkRunner(
            memory_path=policy_dir / "memory.sqlite",
            scene=scene_config,
            policy=policy_name,
        )
        results = runner.run_all()
        events = [event for result in results for event in result.events]
        memory_snapshot = json.loads(runner.memory.export_json())
        _write_json(policy_dir / "memory_snapshot.json", memory_snapshot)
        _write_events_csv(policy_dir / "events.csv", events)
        all_policy_summaries[policy_name] = {
            "runs": [
                {
                    "trial_id": result.trial_id,
                    "metrics": result.metrics.model_dump(mode="json"),
                    "event_count": len(result.events),
                }
                for result in results
            ],
            "aggregate": _aggregate_results(results),
            "memory_snapshot": memory_snapshot,
            "artifact_files": {
                "memory": f"{policy_name}/memory.sqlite",
                "memory_snapshot": f"{policy_name}/memory_snapshot.json",
                "events": f"{policy_name}/events.csv",
            },
        }
        artifact_files[policy_name] = all_policy_summaries[policy_name]["artifact_files"]

    comparison = _compare_policies(all_policy_summaries)
    summary: dict[str, Any] = {
        "task": "lifelong_objectnav_active_benchmark",
        "scene_id": scene_config.scene_id,
        "target_class": TARGET_CLASS,
        "policies": list(policies),
        "episodes": list(EPISODES),
        "policy_summaries": all_policy_summaries,
        "comparison": comparison,
        "limits": [
            "Deterministic ROS-free grid benchmark; not an official Habitat score.",
            "Config-truth observations replace detector outputs in this first active slice.",
            "The next validation step is Habitat action-level Grounding-DINO replay.",
        ],
        "artifact_files": artifact_files,
    }
    _write_json(output_path / "summary.json", summary)
    _write_report(output_path / "report.html", summary)
    return summary


class LifelongObjectNavBenchmarkRunner:
    def __init__(
        self,
        *,
        memory_path: str | Path,
        scene: SceneConfig | None = None,
        policy: str = "memory_guided",
    ) -> None:
        if policy not in POLICIES:
            raise ValueError(f"unknown policy: {policy}")
        self.scene = scene or make_default_multiroom_lifelong_scene()
        self.policy = policy
        self.memory = SQLiteMemoryStore(memory_path)

    def run_all(self) -> list[TrialResult]:
        return [
            self.run("discover"),
            self.run("reuse_different_start"),
            self.run("stale_repair"),
        ]

    def run(self, trial_name: str) -> TrialResult:
        if trial_name == "discover":
            return self._run_discover()
        if trial_name == "reuse_different_start":
            return self._run_reuse_different_start()
        if trial_name == "stale_repair":
            return self._run_stale_repair()
        raise ValueError(f"unknown lifelong ObjectNav trial: {trial_name}")

    def _run_discover(self) -> Any:
        return self._run_query_episode(
            trial_id="discover",
            start_pose=Pose2D(x=1.4, y=5.0, yaw=0.0),
            scene=self.scene,
            allow_memory=True,
            force_search_first=True,
        )

    def _run_reuse_different_start(self) -> Any:
        return self._run_query_episode(
            trial_id="reuse_different_start",
            start_pose=Pose2D(x=2.2, y=5.4, yaw=0.0),
            scene=self.scene,
            allow_memory=self.policy == "memory_guided",
            force_search_first=False,
        )

    def _run_stale_repair(self) -> Any:
        moved_scene = self.scene.model_copy(deep=True)
        moved_object = moved_scene.objects[0]
        moved_object.active = False
        replacement = ObjectConfig(
            object_id="plant_002",
            class_name=moved_object.class_name,
            pose_map=Pose2D(x=10.6, y=8.2, yaw=-1.5708),
            preferred_standoff_m=moved_object.preferred_standoff_m,
        )
        moved_scene.objects.append(replacement)
        return self._run_query_episode(
            trial_id="stale_repair",
            start_pose=Pose2D(x=1.4, y=5.0, yaw=0.0),
            scene=moved_scene,
            allow_memory=self.policy == "memory_guided",
            force_search_first=False,
        )

    def _run_query_episode(
        self,
        *,
        trial_id: str,
        start_pose: Pose2D,
        scene: SceneConfig,
        allow_memory: bool,
        force_search_first: bool,
    ) -> TrialResult:
        logger = TrialLogger(self.memory, trial_id)
        grid = build_multiroom_grid(scene)
        full_grid = build_multiroom_grid(scene, reveal_all=True)
        source = ConfigTruthObjectSource(scene)
        pose = start_pose
        path_length = 0.0
        ticks = 0.0
        nav_goals = 0
        nav_failures = 0
        frontier_total = 0
        frontier_selected = 0
        observations: list[ObjectObservation] = []
        selected_types: list[str] = []
        memory_query_count = 0
        memory_hit_count = 0
        memory_reused = False
        stale_recheck_count = 0
        memory_transitions = 0
        relocation_recorded = False
        failed_viewpoint_count = 0
        first_observation_ticks: float | None = None
        time_to_verify: float | None = None
        final_score: float | None = None
        before_unknown = _unknown_cell_count(grid)
        active_target_ids = {obj.object_id for obj in scene.objects if obj.active}
        visited_frontier_cells: set[tuple[int, int]] = set()

        for step in range(EPISODE_MAX_STEPS):
            _mark_robot_footprint_free(grid, pose)
            changed = grid.reveal_forward_sector(pose, scene.reveal_model)
            logger.record(
                "map_reveal",
                "revealed forward sector",
                {"step": step, "changed_cells": changed, "pose": pose.model_dump()},
            )
            observations = source.observations_at(pose, full_grid)
            target_observations = [
                observation
                for observation in observations
                if observation.class_name == TARGET_CLASS
            ]
            if target_observations:
                observation = target_observations[0]
                if first_observation_ticks is None:
                    first_observation_ticks = ticks
                verification_viewpoint = plan_verification_viewpoint(
                    full_grid,
                    _object_for_observation(scene, observation),
                )
                path_to_verify = _estimate_path_length(full_grid, pose, verification_viewpoint)
                if path_to_verify is None:
                    nav_failures += 1
                    failed_viewpoint_count += 1
                    break
                pose, distance, nav_ticks = _navigate(full_grid, pose, verification_viewpoint)
                path_length += distance
                ticks += nav_ticks
                nav_goals += 1
                verification_observations = source.observations_at(pose, full_grid)
                matched = [
                    item
                    for item in verification_observations
                    if item.object_id == observation.object_id
                ]
                if matched:
                    previous_missing = _missing_memories_for_class(
                        TARGET_CLASS,
                        self.memory,
                        self.scene.anchor.anchor_id,
                    )
                    self.memory.upsert_object_from_observation(
                        matched[0],
                        MemoryState.REUSABLE,
                        verification_viewpoint=verification_viewpoint,
                    )
                    if previous_missing and matched[0].object_id not in previous_missing:
                        self.memory.add_relation(
                            source_object_id=matched[0].object_id,
                            target_object_id=sorted(previous_missing)[0],
                            relation_type="possible_relocation_of",
                        )
                        relocation_recorded = True
                    memory_transitions += 1
                    time_to_verify = ticks
                    selected_types.append("object_verification")
                    logger.record(
                        "verification",
                        "target verified",
                        {
                            "object_id": matched[0].object_id,
                            "viewpoint": verification_viewpoint.model_dump(),
                        },
                    )
                    break

            memories = (
                self.memory.query_objects(
                    class_name=TARGET_CLASS,
                    states=[MemoryState.REUSABLE, MemoryState.VERIFIED],
                    anchor_id=self.scene.anchor.anchor_id,
                )
                if allow_memory
                else []
            )
            if force_search_first:
                memories = []
            memory_query_count += int(allow_memory)
            memory_hit_count += int(bool(memories))
            frontiers = extract_frontier_clusters(grid)
            frontier_total += len(frontiers)
            if not frontiers and not memories:
                nav_failures += 1
                break
            try:
                candidate = self._select_candidate(
                    grid=grid,
                    memory_grid=full_grid,
                    pose=pose,
                    memories=memories,
                    frontiers=frontiers,
                    visited_frontier_cells=visited_frontier_cells,
                )
            except ValueError:
                nav_failures += 1
                break
            selected_types.append(candidate.candidate_type)
            final_score = candidate.score
            logger.record(
                "candidate_selected",
                "selected navigation candidate",
                {
                    "step": step,
                    "policy": self.policy,
                    **_candidate_payload(candidate),
                },
            )
            pose, distance, nav_ticks = _navigate(grid if candidate.candidate_type == "frontier" else full_grid, pose, candidate.goal_pose)
            _mark_robot_footprint_free(grid, pose)
            path_length += distance
            ticks += nav_ticks
            nav_goals += 1
            if candidate.candidate_type == "frontier":
                visited_frontier_cells.update(candidate.frontier_cells)
                frontier_selected += 1
                continue
            memory_reused = True
            stale_recheck_count += 1
            memory_observations = source.observations_at(pose, full_grid)
            matched_memory = [
                observation
                for observation in memory_observations
                if observation.object_id == candidate.object_id
                and observation.object_id in active_target_ids
            ]
            if matched_memory:
                self.memory.upsert_object_from_observation(
                    matched_memory[0],
                    MemoryState.REUSABLE,
                    verification_viewpoint=candidate.goal_pose,
                )
                time_to_verify = ticks
                observations = matched_memory
                logger.record(
                    "memory_reuse",
                    "verified object from memory",
                    {"object_id": candidate.object_id},
                )
                break
            if candidate.object_id is not None:
                self.memory.update_object_state(candidate.object_id, MemoryState.MISSING)
                memory_transitions += 1
                failed_viewpoint_count += 1
                logger.record(
                    "memory_mutation",
                    "memory target missing at verification pose",
                    {"object_id": candidate.object_id},
                )

        success = bool(observations) and any(
            observation.object_id in active_target_ids
            for observation in observations
            if observation.class_name == TARGET_CLASS
        )
        after_unknown = _unknown_cell_count(grid)
        unknown_reduction = before_unknown - after_unknown
        metrics = TrialMetrics(
            success=success,
            failure_reason=None if success else "target_not_verified",
            final_state=MemoryState.REUSABLE.value if success else "failed",
            path_length_m=round(path_length, 6),
            elapsed_time_s=round(ticks, 6),
            num_nav_goals=nav_goals,
            num_nav_failures=nav_failures,
            frontier_count_total=frontier_total,
            frontier_selected_count=frontier_selected,
            time_to_first_observation_s=first_observation_ticks,
            time_to_verify_s=time_to_verify,
            observation_count=len(observations),
            verification_attempt_count=stale_recheck_count + int(success),
            failed_viewpoint_count=failed_viewpoint_count,
            memory_reused=memory_reused,
            memory_query_count=memory_query_count,
            memory_hit_count=memory_hit_count,
            memory_state_transition_count=memory_transitions,
            stale_recheck_count=stale_recheck_count,
            missing_detection_success=failed_viewpoint_count > 0,
            relocation_recorded=relocation_recorded,
            unknown_area_reduction=float(unknown_reduction),
            repeated_exploration_ratio=_safe_div(frontier_selected, max(1, nav_goals)),
            selected_candidate_types=selected_types,
            final_candidate_score=final_score,
        )
        self.memory.record_trial_metrics(trial_id, metrics)
        return TrialResult(trial_id=trial_id, metrics=metrics, events=logger.events)

    def _select_candidate(
        self,
        *,
        grid: Any,
        memory_grid: Any,
        pose: Pose2D,
        memories: list[Any],
        frontiers: list[Any],
        visited_frontier_cells: set[tuple[int, int]],
    ) -> NavigationCandidate:
        if self.policy == "memory_guided":
            return select_memory_guided_candidate(
                grid=grid,
                start_pose=pose,
                target_class=TARGET_CLASS,
                memories=memories,
                frontiers=frontiers,
                visited_frontier_cells=visited_frontier_cells,
                memory_grid=memory_grid,
            )
        return select_memory_guided_candidate(
            grid=grid,
            start_pose=pose,
            target_class=TARGET_CLASS,
            memories=[],
            frontiers=frontiers,
            visited_frontier_cells=visited_frontier_cells,
        )


def _estimate_path_length(grid: Any, start: Pose2D, goal: Pose2D) -> float | None:
    navigator = AStarGridNavigationClient(grid=grid, start_pose=start)
    navigator.send_goal(goal)
    if navigator.status.value == "FAILED":
        return None
    if navigator.status.value == "SUCCEEDED":
        return start.distance_to(goal)
    path = [start, *navigator.planned_path[1:]]
    return sum(first.distance_to(second) for first, second in zip(path, path[1:]))


def _navigate(grid: Any, start: Pose2D, goal: Pose2D) -> tuple[Pose2D, float, float]:
    navigator = AStarGridNavigationClient(
        grid=grid,
        start_pose=start,
        step_size_m=0.5,
        success_radius_m=0.05,
    )
    navigator.send_goal(goal)
    ticks = 0
    while ticks < 500 and navigator.status.value == "ACTIVE":
        navigator.tick(1.0)
        ticks += 1
    return navigator.current_pose, round(navigator.path_length_m, 6), float(ticks)


def _object_for_observation(scene: SceneConfig, observation: ObjectObservation) -> ObjectConfig:
    for obj in scene.objects:
        if obj.object_id == observation.object_id:
            return obj
    raise KeyError(observation.object_id)


def _unknown_cell_count(grid: Any) -> int:
    return sum(
        1
        for row in range(grid.height_cells)
        for col in range(grid.width_cells)
        if grid.is_unknown_cell(col, row)
    )


def _mark_robot_footprint_free(grid: Any, pose: Pose2D) -> None:
    col, row = grid.world_to_cell(pose.x, pose.y)
    if grid.in_bounds_cell(col, row):
        grid.set_cell(col, row, CellState.FREE)


def _missing_memories_for_class(
    class_name: str,
    memory: SQLiteMemoryStore,
    anchor_id: str,
) -> set[str]:
    try:
        return {
            obj.object_id
            for obj in memory.query_objects(
                class_name=class_name,
                states=[MemoryState.MISSING, MemoryState.SUSPECT_MISSING],
                anchor_id=anchor_id,
            )
        }
    except Exception:
        return set()


def _candidate_payload(candidate: NavigationCandidate) -> dict[str, Any]:
    return {
        "candidate_type": candidate.candidate_type,
        "object_id": candidate.object_id,
        "class_name": candidate.class_name,
        "goal": candidate.goal_pose.model_dump(),
        "expected_success": round(candidate.expected_success, 6),
        "information_gain": round(candidate.information_gain, 6),
        "path_cost_m": round(candidate.path_cost_m, 6),
        "verification_cost_m": round(candidate.verification_cost_m, 6),
        "stale_penalty": round(candidate.stale_penalty, 6),
        "score": round(candidate.score, 6),
    }


def _aggregate_results(results: Sequence[Any]) -> dict[str, Any]:
    metrics = [result.metrics for result in results]
    return {
        "episodes": len(metrics),
        "success_episodes": sum(int(metric.success) for metric in metrics),
        "total_path_length_m": round(sum(metric.path_length_m for metric in metrics), 6),
        "total_nav_goals": sum(metric.num_nav_goals for metric in metrics),
        "frontier_selected_count": sum(metric.frontier_selected_count for metric in metrics),
        "memory_reuse_episodes": sum(int(metric.memory_reused) for metric in metrics),
        "stale_recheck_count": sum(metric.stale_recheck_count for metric in metrics),
        "relocation_recorded": any(metric.relocation_recorded for metric in metrics),
        "mean_repeated_exploration_ratio": round(
            _safe_div(sum(metric.repeated_exploration_ratio for metric in metrics), len(metrics)),
            6,
        ),
    }


def _compare_policies(policy_summaries: dict[str, Any]) -> dict[str, Any]:
    memory = policy_summaries.get("memory_guided", {}).get("aggregate", {})
    frontier = policy_summaries.get("frontier_only", {}).get("aggregate", {})
    if not memory or not frontier:
        return {}
    frontier_path = float(frontier.get("total_path_length_m", 0.0))
    memory_path = float(memory.get("total_path_length_m", 0.0))
    return {
        "memory_guided_path_delta_m": round(frontier_path - memory_path, 6),
        "memory_guided_path_reduction_ratio": round(
            _safe_div(frontier_path - memory_path, frontier_path),
            6,
        ),
        "memory_guided_frontier_reduction": int(frontier.get("frontier_selected_count", 0))
        - int(memory.get("frontier_selected_count", 0)),
        "memory_guided_success_delta": int(memory.get("success_episodes", 0))
        - int(frontier.get("success_episodes", 0)),
        "relocation_recorded": bool(memory.get("relocation_recorded")),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_events_csv(path: Path, events: list[TrialEvent]) -> None:
    rows = [
        {
            "trial_id": event.trial_id,
            "timestamp": round(event.timestamp, 6),
            "event_type": event.event_type,
            "message": event.message,
            "payload_json": json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
        }
        for event in events
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "trial_id",
                "timestamp",
                "event_type",
                "message",
                "payload_json",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    html = _render_report(summary)
    path.write_text(html, encoding="utf-8")


def _render_report(summary: dict[str, Any]) -> str:
    policy_cards = "\n".join(
        _render_policy_card(policy, payload)
        for policy, payload in summary["policy_summaries"].items()
    )
    comparison = summary.get("comparison", {})
    comparison_rows = "\n".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape(str(value))}</td></tr>"
        for key, value in comparison.items()
    )
    limits = "\n".join(
        f"<li>{escape(str(limit))}</li>" for limit in summary.get("limits", [])
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Lifelong ObjectNav Active Benchmark</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #17202a; background: #f5f7f4; line-height: 1.6; }}
    main {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0 56px; }}
    h1 {{ margin: 0; font-size: clamp(30px, 5vw, 52px); line-height: 1.12; letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 24px; letter-spacing: 0; }}
    section {{ margin-top: 24px; padding: 22px; border: 1px solid #d9ded3; border-radius: 8px; background: #fff; }}
    .sub {{ max-width: 900px; color: #5e6b74; font-size: 17px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }}
    .card {{ border: 1px solid #d9ded3; border-radius: 8px; padding: 16px; background: #fbfcfa; }}
    .metric {{ display: grid; grid-template-columns: 1fr auto; gap: 8px; border-bottom: 1px solid #e5e9e1; padding: 8px 0; }}
    .metric:last-child {{ border-bottom: 0; }}
    table {{ width: 100%; border-collapse: collapse; border: 1px solid #d9ded3; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #e5e9e1; text-align: left; }}
    th {{ background: #edf2ed; }}
    code {{ padding: 2px 6px; border: 1px solid #d5dbd0; border-radius: 5px; background: #f7f9f4; }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Lifelong ObjectNav Active Benchmark</h1>
      <p class="sub">这是第一个闭环记忆复用评测切片：同一多房间/走廊环境中先发现物体，再跨 episode 查询记忆，最后测试物体移动后的 stale-memory repair。</p>
    </header>
    <section>
      <h2>概览</h2>
      <p>Scene: <code>{escape(str(summary["scene_id"]))}</code> · Target: <code>{escape(str(summary["target_class"]))}</code></p>
      <div class="grid">{policy_cards}</div>
    </section>
    <section>
      <h2>Memory vs Frontier</h2>
      <table>{comparison_rows}</table>
    </section>
    <section>
      <h2>当前边界</h2>
      <ul>{limits}</ul>
    </section>
  </main>
</body>
</html>
"""


def _render_policy_card(policy: str, payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    runs = payload["runs"]
    run_lines = "".join(
        f"<div class='metric'><span>{escape(run['trial_id'])}</span><strong>{escape(str(run['metrics']['path_length_m']))} m</strong></div>"
        for run in runs
    )
    return f"""<article class="card">
  <h3>{escape(policy)}</h3>
  <div class="metric"><span>success</span><strong>{aggregate["success_episodes"]}/{aggregate["episodes"]}</strong></div>
  <div class="metric"><span>path</span><strong>{aggregate["total_path_length_m"]} m</strong></div>
  <div class="metric"><span>frontier selected</span><strong>{aggregate["frontier_selected_count"]}</strong></div>
  <div class="metric"><span>memory reuse episodes</span><strong>{aggregate["memory_reuse_episodes"]}</strong></div>
  {run_lines}
</article>"""


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0
