from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from objectnav_core.geometry.dual_anchor import FrameTransform2D


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
DEFAULT_QUERY_REPEATS = 1
DEFAULT_MEMORY_VALID_PRIOR = 0.5
SUPPORTED_CHALLENGES: tuple[str, ...] = ("stable", "ambiguous", "stale_proxy")
DEFAULT_CHALLENGE = "stable"


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
    stale_repair: bool = False
    query_repeat_index: int = 0
    memory_decision: str = "memory_first"
    memory_valid_prior: float = DEFAULT_MEMORY_VALID_PRIOR
    expected_memory_first_action_count: float | None = None
    expected_frontier_first_action_count: float | None = None


def run_habitat_closed_loop_dual_anchor_preflight(
    output_dir: str | Path,
    *,
    dataset_dir: str | Path,
    scene_root: str | Path,
    target_categories: Sequence[str] = TARGET_CATEGORIES,
    policies: Sequence[str] = POLICIES,
    max_groups: int | None = DEFAULT_MAX_GROUPS,
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    gate_threshold: float = DEFAULT_GATE_THRESHOLD,
    ambiguity_margin: float = DEFAULT_AMBIGUITY_MARGIN,
    frontier_proxy_waypoints: int = DEFAULT_FRONTIER_PROXY_WAYPOINTS,
    challenge: str = DEFAULT_CHALLENGE,
    query_repeats: int = DEFAULT_QUERY_REPEATS,
    memory_valid_prior: float = DEFAULT_MEMORY_VALID_PRIOR,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _validate_common(
        target_categories=target_categories,
        policies=policies,
        max_groups=max_groups,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
    )
    summary = _base_summary(
        task="habitat_closed_loop_dual_anchor_objectnav_preflight",
        full_habitat_run=False,
        dataset_dir=dataset_dir,
        scene_root=scene_root,
        target_categories=target_categories,
        policies=policies,
        max_groups=max_groups,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
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
    sensor_width: int = DEFAULT_SENSOR_WIDTH,
    sensor_height: int = DEFAULT_SENSOR_HEIGHT,
    gate_threshold: float = DEFAULT_GATE_THRESHOLD,
    ambiguity_margin: float = DEFAULT_AMBIGUITY_MARGIN,
    frontier_proxy_waypoints: int = DEFAULT_FRONTIER_PROXY_WAYPOINTS,
    challenge: str = DEFAULT_CHALLENGE,
    query_repeats: int = DEFAULT_QUERY_REPEATS,
    memory_valid_prior: float = DEFAULT_MEMORY_VALID_PRIOR,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _validate_common(
        target_categories=target_categories,
        policies=policies,
        max_groups=max_groups,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
    )

    from objectnav_core.evaluation.habitat_memory_lifecycle_objectnav import (
        _build_lifecycle_groups,
        _cached_action_route_sequence,
        _search_proxy_route_goals,
        _choose_lifecycle_anchor_candidate,
        _choose_lifecycle_fallback_candidate,
        _episode_selection_key,
        _rank_lifecycle_anchor_candidates,
    )
    from objectnav_core.evaluation.habitat_objectnav_rgb_noise_stress import (
        _select_episodes,
        _sample_replay_view_candidates,
    )
    from objectnav_core.evaluation.habitat_objectnav_valmini_semantic_stress import (
        _group_by_scene,
        _load_valmini_episodes,
        _semantic_id_to_category,
        _semantic_ids_for_target_category,
        _write_scene_dataset_config,
    )
    from objectnav_core.evaluation.habitat_semantic_yolo_stress import (
        _load_habitat_sim,
        _make_simulator,
    )

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
    if max_groups is not None:
        groups = _select_balanced_groups(groups, max_groups=max_groups)
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
                target_semantic_ids = _semantic_ids_for_target_category(
                    semantic_id_to_category,
                    group.category,
                )
                memory_candidates = _rank_lifecycle_anchor_candidates(
                    _sample_replay_view_candidates(
                        sim=sim,
                        agent=agent,
                        episode=group.discovery_episode,
                        target_semantic_ids=target_semantic_ids,
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
                fake_verifications = {
                    candidate.source: _OracleVisible(target_visible=candidate.target_pixels > 0)
                    for candidate in (*memory_candidates, *fallback_candidates)
                }
                memory_candidate = _choose_lifecycle_anchor_candidate(
                    candidates=memory_candidates,
                    verifications=fake_verifications,
                    strategy="most_visible",
                    min_target_pixels=1,
                )
                fallback_candidate = _choose_lifecycle_fallback_candidate(
                    candidates=fallback_candidates,
                    verifications=fake_verifications,
                    min_target_pixels=1,
                )
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
                        seed=313 + len(rows),
                        waypoint_count=frontier_proxy_waypoints,
                    )[0],
                )
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
                        seed=313 + len(rows) + 500000,
                        waypoint_count=(
                            frontier_proxy_waypoints
                            if challenge == "stale_proxy"
                            else 0
                        ),
                    )[0],
                )
                for policy in policies:
                    for repeat_index in range(query_repeats):
                        matching_reason = _matching_reason_for_repeat(
                            challenge=challenge,
                            policy=policy,
                            repeat_index=repeat_index,
                        )
                        active_memory_route = _active_memory_route_for_repeat(
                            challenge=challenge,
                            policy=policy,
                            repeat_index=repeat_index,
                            initial_memory_route=memory_route,
                            repaired_memory_route=repaired_memory_route,
                            fallback_route=fallback_route,
                        )
                        expected_memory_first = _expected_memory_first_action_count(
                            memory_action_count=active_memory_route.action_count,
                            fallback_from_memory_action_count=(
                                fallback_from_memory_route.action_count
                            ),
                            memory_valid_prior=memory_valid_prior,
                        )
                        expected_frontier_first = float(fallback_route.action_count)
                        memory_decision = _memory_first_decision(
                            memory_action_count=active_memory_route.action_count,
                            fallback_from_memory_action_count=(
                                fallback_from_memory_route.action_count
                            ),
                            fallback_action_count=fallback_route.action_count,
                            memory_valid_prior=memory_valid_prior,
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
                                    memory_verified=(
                                        policy != "frontier_only"
                                        and matching_reason == "accepted"
                                    ),
                                    fallback_verified=True,
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
                                    memory_valid_prior=memory_valid_prior,
                                    expected_memory_first_action_count=(
                                        expected_memory_first
                                    ),
                                    expected_frontier_first_action_count=(
                                        expected_frontier_first
                                    ),
                                )
                            )
                        )
        finally:
            sim.close()

    summary = _base_summary(
        task="habitat_closed_loop_dual_anchor_objectnav",
        full_habitat_run=True,
        dataset_dir=dataset_path,
        scene_root=scene_root_path,
        target_categories=target_categories,
        policies=policies,
        max_groups=max_groups,
        sensor_width=sensor_width,
        sensor_height=sensor_height,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
        frontier_proxy_waypoints=frontier_proxy_waypoints,
        challenge=challenge,
        query_repeats=query_repeats,
        memory_valid_prior=memory_valid_prior,
    )
    summary.update(
        {
            "detector": "oracle_semantic_visibility",
            "selected_groups": len(groups),
            "episode_selection": {
                "candidate_episode_count": len(selected_episodes),
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
    elif plan.matching_reason in {"ambiguous", "expected_utility_frontier"}:
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
    elif plan.fallback_verified:
        selected = ["memory", "frontier"]
        action_count = plan.memory_action_count + plan.fallback_from_memory_action_count
        distance = (
            plan.memory_executed_distance_m
            + plan.fallback_from_memory_executed_distance_m
        )
        success = True
        memory_reused = False
    else:
        selected = ["memory"]
        action_count = plan.memory_action_count
        distance = plan.memory_executed_distance_m
        success = False
        memory_reused = False
    return {
        "group_id": plan.group_id,
        "category": plan.category,
        "policy": plan.policy,
        "query_repeat_index": int(plan.query_repeat_index),
        "success": bool(success),
        "selected_candidate_types": selected,
        "matching_reason": plan.matching_reason,
        "memory_reused": memory_reused,
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
        "memory_decision": plan.memory_decision,
        "memory_valid_prior": round(float(plan.memory_valid_prior), 6),
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


def _base_summary(
    *,
    task: str,
    full_habitat_run: bool,
    dataset_dir: str | Path,
    scene_root: str | Path,
    target_categories: Sequence[str],
    policies: Sequence[str],
    max_groups: int | None,
    sensor_width: int,
    sensor_height: int,
    gate_threshold: float,
    ambiguity_margin: float,
    frontier_proxy_waypoints: int,
    challenge: str,
    query_repeats: int,
    memory_valid_prior: float,
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
        "challenge": challenge,
        "query_repeats": int(query_repeats),
        "memory_valid_prior": round(float(memory_valid_prior), 6),
        "session_restart": {
            "memory_frame_id": "map_session_1",
            "runtime_frame_id": "map_session_2",
            "frame_transform": _transform_payload(_session_restart_transform()),
        },
        "artifact_files": {"summary": "summary.json"},
        "limits": [
            "Preflight does not import Habitat or detector weights.",
            "First Habitat slice is oracle/action-level smoke, not official SPL.",
            "Grounding-DINO per-step closed-loop perception is still pending.",
        ],
    }


def _validate_common(
    *,
    target_categories: Sequence[str],
    policies: Sequence[str],
    max_groups: int | None,
    sensor_width: int,
    sensor_height: int,
    gate_threshold: float,
    ambiguity_margin: float,
    frontier_proxy_waypoints: int,
    challenge: str,
    query_repeats: int,
    memory_valid_prior: float,
) -> None:
    unknown_policies = sorted(set(policies) - set(POLICIES))
    if unknown_policies:
        raise ValueError(f"unknown policy/policies: {', '.join(unknown_policies)}")
    unknown_categories = sorted(set(target_categories) - set(TARGET_CATEGORIES))
    if unknown_categories:
        raise ValueError(f"unknown target category/categories: {', '.join(unknown_categories)}")
    if max_groups is not None and max_groups <= 0:
        raise ValueError("max_groups must be positive when provided")
    if sensor_width <= 0 or sensor_height <= 0:
        raise ValueError("sensor dimensions must be positive")
    if gate_threshold <= 0.0:
        raise ValueError("gate_threshold must be positive")
    if ambiguity_margin < 0.0:
        raise ValueError("ambiguity_margin must be non-negative")
    if frontier_proxy_waypoints < 0:
        raise ValueError("frontier_proxy_waypoints must be non-negative")
    if challenge not in SUPPORTED_CHALLENGES:
        raise ValueError(
            "challenge must be one of: " + ", ".join(SUPPORTED_CHALLENGES)
        )
    if query_repeats <= 0:
        raise ValueError("query_repeats must be positive")
    if not 0.0 <= memory_valid_prior <= 1.0:
        raise ValueError("memory_valid_prior must be in [0, 1]")


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


def _matching_reason_for_challenge(challenge: str) -> str:
    if challenge == "stable":
        return "accepted"
    if challenge == "ambiguous":
        return "ambiguous"
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
) -> str:
    expected_memory = _expected_memory_first_action_count(
        memory_action_count=memory_action_count,
        fallback_from_memory_action_count=fallback_from_memory_action_count,
        memory_valid_prior=memory_valid_prior,
    )
    if expected_memory <= float(fallback_action_count):
        return "memory_first"
    return "frontier_first"


def _memory_decision_for_row(
    *,
    policy: str,
    matching_reason: str,
    raw_memory_decision: str,
) -> str:
    if policy != "memory_guided":
        return "memory_first"
    if matching_reason == "accepted":
        return "memory_first"
    return raw_memory_decision


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


@dataclass(frozen=True)
class _OracleVisible:
    target_visible: bool

    @property
    def shared_gate_success(self) -> bool:
        return bool(self.target_visible)


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
        }
    return summaries


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
