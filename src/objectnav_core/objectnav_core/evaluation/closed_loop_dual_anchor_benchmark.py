from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from objectnav_core.geometry.dual_anchor import (
    FrameTransform2D,
    PoseEstimate2D,
    match_instance_by_mahalanobis,
    transform_pose_estimate,
)
from objectnav_core.mapping.fixtures import build_multiroom_grid
from objectnav_core.mapping.frontiers import FrontierCluster
from objectnav_core.models import (
    AnchorType,
    MemoryObject,
    MemoryState,
    ObjectConfig,
    Pose2D,
    make_default_multiroom_lifelong_scene,
)
from objectnav_core.planning.frontier_policies import estimate_astar_path_cost_m
from objectnav_core.planning.memory_guided import (
    MemoryMatchEvidence,
    select_memory_guided_candidate,
)
from objectnav_core.planning.viewpoints import plan_verification_viewpoint


POLICIES: tuple[str, ...] = ("memory_guided", "frontier_only", "naive_count")
EPISODES: tuple[str, ...] = (
    "session_1_discover",
    "session_2_reuse",
    "session_2_ambiguous",
    "session_2_stale_repair",
)
TARGET_CLASS = "plant"
SESSION_1_FRAME = "map_session_1"
SESSION_2_FRAME = "map_session_2"
SESSION_1_ANCHOR = "anchor_session_1"
SESSION_2_ANCHOR = "anchor_session_2"


def run_closed_loop_dual_anchor_benchmark(
    output_dir: str | Path,
    *,
    policies: Sequence[str] = POLICIES,
    gate_threshold: float = 5.991,
    ambiguity_margin: float = 0.5,
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    unknown = sorted(set(policies) - set(POLICIES))
    if unknown:
        raise ValueError(f"unknown policy/policies: {', '.join(unknown)}")

    policy_summaries = {
        policy: _run_policy(
            policy,
            gate_threshold=gate_threshold,
            ambiguity_margin=ambiguity_margin,
        )
        for policy in policies
    }
    summary: dict[str, Any] = {
        "task": "closed_loop_dual_anchor_grid_benchmark",
        "target_class": TARGET_CLASS,
        "policies": list(policies),
        "episodes": list(EPISODES),
        "gate_threshold": float(gate_threshold),
        "ambiguity_margin": float(ambiguity_margin),
        "policy_summaries": policy_summaries,
        "comparison": _compare_policies(policy_summaries),
        "limits": [
            "Deterministic grid closed loop; not Habitat and not official SPL.",
            "Config-truth object observations replace Grounding-DINO in this slice.",
            "The purpose is to exercise dual-anchor decisions before Habitat integration.",
        ],
        "artifact_files": {"summary": "summary.json"},
    }
    _write_json(output_path / "summary.json", summary)
    return summary


def _run_policy(
    policy: str,
    *,
    gate_threshold: float,
    ambiguity_margin: float,
) -> dict[str, Any]:
    memory = _session_1_memory()
    episodes = [
        _session_1_discover_row(memory),
        _run_session_2_episode(
            "session_2_reuse",
            policy=policy,
            memory=memory,
            observed_candidates={"plant_001": (12.2, 8.2)},
            active_objects=("plant_001",),
            gate_threshold=gate_threshold,
            ambiguity_margin=ambiguity_margin,
        ),
        _run_session_2_episode(
            "session_2_ambiguous",
            policy=policy,
            memory=memory,
            observed_candidates={"plant_001": (12.1, 8.2), "plant_003": (12.3, 8.2)},
            active_objects=("plant_001", "plant_003"),
            gate_threshold=gate_threshold,
            ambiguity_margin=ambiguity_margin,
        ),
        _run_session_2_episode(
            "session_2_stale_repair",
            policy=policy,
            memory=memory,
            observed_candidates={},
            active_objects=("plant_002",),
            gate_threshold=gate_threshold,
            ambiguity_margin=ambiguity_margin,
        ),
    ]
    aggregate = {
        "episodes": len(episodes),
        "success_episodes": sum(int(row["success"]) for row in episodes),
        "total_path_length_m": round(sum(float(row["path_length_m"]) for row in episodes), 6),
        "frontier_selected_count": sum(
            row["selected_candidate_types"].count("frontier") for row in episodes
        ),
        "memory_reuse_episodes": sum(int(row["memory_reused"]) for row in episodes),
        "stale_repair_count": sum(int(row["stale_repair_recorded"]) for row in episodes),
        "accepted_match_count": sum(row["matching_reason"] == "accepted" for row in episodes),
        "ambiguous_match_count": sum(row["matching_reason"] == "ambiguous" for row in episodes),
        "outside_gate_count": sum(row["matching_reason"] == "outside_gate" for row in episodes),
    }
    return {"episodes": episodes, "aggregate": aggregate}


def _session_1_memory() -> MemoryObject:
    scene = _scene_for_objects(("plant_001",))
    grid = build_multiroom_grid(scene, reveal_all=True)
    target = _object_by_id(scene.objects, "plant_001")
    return MemoryObject(
        object_id=target.object_id,
        class_name=target.class_name,
        state=MemoryState.REUSABLE,
        pose=target.pose_map,
        anchor_id=SESSION_1_ANCHOR,
        anchor_type=AnchorType.INDOOR_MAP,
        frame_id=SESSION_1_FRAME,
        confidence=0.95,
        detector_name="config_truth",
        verification_viewpoint=plan_verification_viewpoint(grid, target),
    )


def _session_1_discover_row(memory: MemoryObject) -> dict[str, Any]:
    scene = _scene_for_objects(("plant_001",))
    grid = build_multiroom_grid(scene, reveal_all=True)
    start = Pose2D(x=1.4, y=5.0, yaw=0.0)
    assert memory.verification_viewpoint is not None
    path = _path_cost(grid, start, memory.verification_viewpoint)
    return {
        "episode_id": "session_1_discover",
        "success": True,
        "policy": "bootstrap",
        "selected_candidate_types": ["frontier", "object_verification"],
        "path_length_m": path,
        "memory_reused": False,
        "matching_reason": "not_applicable",
        "match_distances": {},
        "memory_frame_id": SESSION_1_FRAME,
        "runtime_frame_id": SESSION_1_FRAME,
        "frame_transform": None,
        "stale_repair_recorded": False,
        "relocation_recorded": False,
        "verified_object_id": memory.object_id,
    }


def _run_session_2_episode(
    episode_id: str,
    *,
    policy: str,
    memory: MemoryObject,
    observed_candidates: dict[str, tuple[float, float]],
    active_objects: tuple[str, ...],
    gate_threshold: float,
    ambiguity_margin: float,
) -> dict[str, Any]:
    scene = _scene_for_objects(active_objects)
    grid = build_multiroom_grid(scene, reveal_all=True)
    start = Pose2D(x=2.2, y=5.4, yaw=0.0)
    transform = _session_restart_transform()
    runtime_memory = _transform_memory(memory, transform)
    match = (
        _match_runtime_memory(
            runtime_memory,
            observed_candidates,
            gate_threshold=gate_threshold,
            ambiguity_margin=ambiguity_margin,
        )
        if observed_candidates
        else _NoCurrentObservationMatch()
    )
    frontiers = [_frontier_pressure_candidate()]
    candidate = _select_candidate(
        policy=policy,
        grid=grid,
        start=start,
        memory=runtime_memory,
        frontiers=frontiers,
        match=match,
    )
    selected_types = [candidate.candidate_type]
    path_length = _path_cost(grid, start, candidate.goal_pose)
    memory_reused = False
    stale_repair_recorded = False
    relocation_recorded = False
    verified_object_id: str | None = None

    if candidate.candidate_type == "memory":
        if candidate.object_id in active_objects:
            memory_reused = True
            verified_object_id = candidate.object_id
        else:
            stale_repair_recorded = True
            selected_types.append("frontier")
            repair_object = _first_active_target(scene)
            repair_viewpoint = plan_verification_viewpoint(grid, repair_object)
            path_length += _path_cost(grid, candidate.goal_pose, repair_viewpoint)
            verified_object_id = repair_object.object_id
            relocation_recorded = repair_object.object_id != candidate.object_id
    else:
        repair_object = _first_active_target(scene)
        repair_viewpoint = plan_verification_viewpoint(grid, repair_object)
        path_length += _path_cost(grid, candidate.goal_pose, repair_viewpoint)
        verified_object_id = repair_object.object_id

    return {
        "episode_id": episode_id,
        "success": verified_object_id is not None,
        "policy": policy,
        "selected_candidate_types": selected_types,
        "path_length_m": round(path_length, 6),
        "memory_reused": memory_reused,
        "matching_reason": match.reason,
        "match_distances": match.distances,
        "memory_frame_id": memory.frame_id,
        "runtime_frame_id": runtime_memory.frame_id,
        "frame_transform": {
            "dx": transform.dx,
            "dy": transform.dy,
            "dyaw": transform.dyaw,
            "covariance": transform.covariance,
        },
        "stale_repair_recorded": stale_repair_recorded,
        "relocation_recorded": relocation_recorded,
        "verified_object_id": verified_object_id,
    }


def _select_candidate(
    *,
    policy: str,
    grid: Any,
    start: Pose2D,
    memory: MemoryObject,
    frontiers: list[FrontierCluster],
    match: Any,
) -> Any:
    if policy == "frontier_only":
        memories: list[MemoryObject] = []
        evidence = None
    elif policy == "naive_count":
        memories = [memory]
        evidence = {
            memory.object_id: MemoryMatchEvidence(
                accepted=match.accepted,
                reason=match.reason,
                mahalanobis_distance=match.best_distance,
            )
        }
    elif policy == "memory_guided":
        memories = [memory]
        evidence = {
            memory.object_id: MemoryMatchEvidence(
                accepted=match.accepted,
                reason=match.reason,
                mahalanobis_distance=match.best_distance,
            )
        }
    else:
        raise ValueError(f"unknown policy: {policy}")
    return select_memory_guided_candidate(
        grid=grid,
        memory_grid=grid,
        start_pose=start,
        target_class=TARGET_CLASS,
        memories=memories,
        frontiers=frontiers,
        memory_match_evidence=evidence,
    )


def _match_runtime_memory(
    memory: MemoryObject,
    observed_candidates: dict[str, tuple[float, float]],
    *,
    gate_threshold: float,
    ambiguity_margin: float,
) -> Any:
    predicted = {
        object_id: PoseEstimate2D(
            x=xy[0],
            y=xy[1],
            covariance=((0.2, 0.0), (0.0, 0.2)),
        )
        for object_id, xy in {
            memory.object_id: (memory.pose.x, memory.pose.y),
            **{
                object_id: xy
                for object_id, xy in observed_candidates.items()
                if object_id != memory.object_id
            },
        }.items()
    }
    observed_xy = observed_candidates.get(memory.object_id) or next(
        iter(observed_candidates.values())
    )
    observed = PoseEstimate2D(
        x=observed_xy[0],
        y=observed_xy[1],
        covariance=((0.2, 0.0), (0.0, 0.2)),
    )
    return match_instance_by_mahalanobis(
        observed=observed,
        candidates=predicted,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
    )


class _NoCurrentObservationMatch:
    object_id: str | None = None
    accepted = True
    reason = "no_current_observation"
    best_distance: float | None = None
    second_best_distance: float | None = None
    distances: dict[str, float] = {}


def _transform_memory(memory: MemoryObject, transform: FrameTransform2D) -> MemoryObject:
    pose = transform_pose_estimate(
        PoseEstimate2D(
            x=memory.pose.x,
            y=memory.pose.y,
            yaw=memory.pose.yaw,
            covariance=((0.15, 0.0), (0.0, 0.15)),
        ),
        transform,
    )
    assert memory.verification_viewpoint is not None
    viewpoint = transform_pose_estimate(
        PoseEstimate2D(
            x=memory.verification_viewpoint.x,
            y=memory.verification_viewpoint.y,
            yaw=memory.verification_viewpoint.yaw,
            covariance=((0.15, 0.0), (0.0, 0.15)),
        ),
        transform,
    )
    return memory.model_copy(
        update={
            "pose": Pose2D(x=pose.x, y=pose.y, yaw=pose.yaw),
            "anchor_id": SESSION_2_ANCHOR,
            "frame_id": SESSION_2_FRAME,
            "verification_viewpoint": Pose2D(
                x=viewpoint.x,
                y=viewpoint.y,
                yaw=viewpoint.yaw,
            ),
        }
    )


def _session_restart_transform() -> FrameTransform2D:
    return FrameTransform2D(
        dx=0.2,
        dy=-0.15,
        dyaw=0.0,
        covariance=((0.05, 0.0), (0.0, 0.05)),
    )


def _scene_for_objects(active_ids: tuple[str, ...]) -> Any:
    scene = make_default_multiroom_lifelong_scene().model_copy(deep=True)
    base = scene.objects[0]
    objects = [
        ObjectConfig(
            object_id="plant_001",
            class_name=TARGET_CLASS,
            pose_map=Pose2D(x=12.0, y=8.2, yaw=base.pose_map.yaw),
            active="plant_001" in active_ids,
            preferred_standoff_m=base.preferred_standoff_m,
        ),
        ObjectConfig(
            object_id="plant_002",
            class_name=TARGET_CLASS,
            pose_map=Pose2D(x=10.6, y=8.2, yaw=base.pose_map.yaw),
            active="plant_002" in active_ids,
            preferred_standoff_m=base.preferred_standoff_m,
        ),
        ObjectConfig(
            object_id="plant_003",
            class_name=TARGET_CLASS,
            pose_map=Pose2D(x=12.3, y=8.2, yaw=base.pose_map.yaw),
            active="plant_003" in active_ids,
            preferred_standoff_m=base.preferred_standoff_m,
        ),
    ]
    return scene.model_copy(update={"objects": objects})


def _frontier_pressure_candidate() -> FrontierCluster:
    return FrontierCluster(
        cells=tuple((16 + index // 8, 2 + index % 8) for index in range(6)),
        centroid=Pose2D(x=4.5, y=1.25, yaw=0.0),
    )


def _first_active_target(scene: Any) -> ObjectConfig:
    for obj in scene.objects:
        if obj.active and obj.class_name == TARGET_CLASS:
            return obj
    raise ValueError("scene has no active target")


def _object_by_id(objects: Sequence[ObjectConfig], object_id: str) -> ObjectConfig:
    for obj in objects:
        if obj.object_id == object_id:
            return obj
    raise KeyError(object_id)


def _path_cost(grid: Any, start: Pose2D, goal: Pose2D) -> float:
    cost = estimate_astar_path_cost_m(grid, start, goal)
    if cost is None:
        raise ValueError(f"no grid path from {start} to {goal}")
    return round(float(cost), 6)


def _compare_policies(policy_summaries: dict[str, Any]) -> dict[str, Any]:
    memory = policy_summaries.get("memory_guided", {}).get("aggregate", {})
    frontier = policy_summaries.get("frontier_only", {}).get("aggregate", {})
    if not memory or not frontier:
        return {}
    frontier_path = float(frontier["total_path_length_m"])
    memory_path = float(memory["total_path_length_m"])
    return {
        "memory_guided_path_delta_m": round(frontier_path - memory_path, 6),
        "memory_guided_path_reduction_ratio": round(
            (frontier_path - memory_path) / frontier_path if frontier_path else 0.0,
            6,
        ),
        "memory_guided_frontier_reduction": int(frontier["frontier_selected_count"])
        - int(memory["frontier_selected_count"]),
        "memory_guided_success_delta": int(memory["success_episodes"])
        - int(frontier["success_episodes"]),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
