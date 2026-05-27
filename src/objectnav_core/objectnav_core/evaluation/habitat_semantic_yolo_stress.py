from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from objectnav_core.memory.usability import (
    DecisionContext,
    DecisionType,
    EvidenceEvent,
    EvidenceType,
    MemoryBelief,
    UsabilityDecisionPolicy,
    UsabilityUpdater,
)


DEFAULT_ACTIONS: tuple[str, ...] = (
    "turn_left",
    "move_forward",
    "turn_right",
    "move_forward",
    "turn_left",
    "move_forward",
)
DEFAULT_BREAKER_MODES: tuple[str, ...] = (
    "clean",
    "miss",
    "fly_point",
    "edge_break",
    "mixed",
)
STRUCTURAL_CATEGORIES = {
    "ceiling",
    "floor",
    "wall",
    "window",
    "door",
    "stairs",
    "railing",
}


@dataclass(frozen=True)
class BreakerResult:
    detector_mask: np.ndarray
    miss_applied: bool
    fly_point_pixels: int
    edge_break_pixels: int


def run_habitat_semantic_yolo_stress(
    output_dir: str | Path,
    *,
    scene_path: str | Path,
    scene_dataset_config: str | Path | None = None,
    episodes: int = 20,
    seed: int = 211,
    sensor_size: int = 96,
    actions: Sequence[str] = DEFAULT_ACTIONS,
    breaker_modes: Sequence[str] = DEFAULT_BREAKER_MODES,
    min_target_pixels: int = 24,
    min_detector_pixels: int = 20,
) -> dict[str, Any]:
    """Stress usability memory with corrupted Habitat semantic masks.

    This runner uses Habitat-Sim directly so it can request RGB, depth, and
    semantic sensors and mutate the semantic mask before evidence extraction.
    Habitat imports stay inside this function to preserve the core package
    boundary for normal tests.
    """

    if episodes <= 0:
        raise ValueError("episodes must be positive")
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

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    scene = Path(scene_path).expanduser().resolve()
    if not scene.exists():
        raise FileNotFoundError(f"Habitat scene does not exist: {scene}")
    scene_config = (
        Path(scene_dataset_config).expanduser().resolve()
        if scene_dataset_config is not None
        else None
    )
    if scene_config is not None and not scene_config.exists():
        raise FileNotFoundError(f"Habitat scene dataset config does not exist: {scene_config}")

    habitat_sim = _load_habitat_sim()
    sim = _make_simulator(
        habitat_sim=habitat_sim,
        scene=scene,
        scene_dataset_config=scene_config,
        sensor_size=sensor_size,
    )
    trace_rows: list[dict[str, Any]] = []
    episode_summaries: list[dict[str, Any]] = []
    try:
        sim.seed(seed)
        semantic_id_to_category = _semantic_id_to_category(sim)
        semantic_object_count = len(getattr(sim.semantic_scene, "objects", []) or [])
        semantic_category_count = len(getattr(sim.semantic_scene, "categories", []) or [])
        for episode_index in range(episodes):
            rng = np.random.default_rng(seed + episode_index)
            breaker_mode = breaker_modes[episode_index % len(breaker_modes)]
            rows, episode_summary = _run_episode(
                sim=sim,
                rng=rng,
                episode_index=episode_index,
                breaker_mode=breaker_mode,
                actions=actions,
                semantic_id_to_category=semantic_id_to_category,
                min_target_pixels=min_target_pixels,
                min_detector_pixels=min_detector_pixels,
            )
            trace_rows.extend(rows)
            episode_summaries.append(episode_summary)
    finally:
        sim.close()

    _write_csv(output_path / "semantic_yolo_trace.csv", trace_rows)
    summary = _summarize(
        scene=scene,
        scene_dataset_config=scene_config,
        episodes=episodes,
        seed=seed,
        sensor_size=sensor_size,
        breaker_modes=breaker_modes,
        min_target_pixels=min_target_pixels,
        min_detector_pixels=min_detector_pixels,
        semantic_object_count=semantic_object_count,
        semantic_category_count=semantic_category_count,
        rows=trace_rows,
        episode_summaries=episode_summaries,
    )
    _write_json(output_path / "summary.json", summary)
    _write_report(output_path / "report.html", summary)
    return summary


def _load_habitat_sim():
    try:
        import habitat_sim
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Habitat-Sim is required for semantic YOLO stress. Run from the "
            "habitat conda environment, for example: conda run -n habitat ..."
        ) from exc
    return habitat_sim


def _make_simulator(
    *,
    habitat_sim: Any,
    scene: Path,
    scene_dataset_config: Path | None,
    sensor_size: int,
) -> Any:
    sim_cfg = habitat_sim.SimulatorConfiguration()
    sim_cfg.scene_id = str(scene)
    sim_cfg.enable_physics = False
    if scene_dataset_config is not None:
        sim_cfg.scene_dataset_config_file = str(scene_dataset_config)

    sensor_specs = []
    for uuid, sensor_type in (
        ("rgb", habitat_sim.SensorType.COLOR),
        ("depth", habitat_sim.SensorType.DEPTH),
        ("semantic", habitat_sim.SensorType.SEMANTIC),
    ):
        spec = habitat_sim.CameraSensorSpec()
        spec.uuid = uuid
        spec.sensor_type = sensor_type
        spec.resolution = [sensor_size, sensor_size]
        spec.position = [0.0, 0.88, 0.0]
        spec.hfov = 79
        sensor_specs.append(spec)

    agent_cfg = habitat_sim.AgentConfiguration()
    agent_cfg.sensor_specifications = sensor_specs
    return habitat_sim.Simulator(habitat_sim.Configuration(sim_cfg, [agent_cfg]))


def _run_episode(
    *,
    sim: Any,
    rng: np.random.Generator,
    episode_index: int,
    breaker_mode: str,
    actions: Sequence[str],
    semantic_id_to_category: dict[int, str],
    min_target_pixels: int,
    min_detector_pixels: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    agent = sim.initialize_agent(0)
    observations = _reset_to_visible_target(
        sim=sim,
        agent=agent,
        rng=rng,
        min_target_pixels=min_target_pixels,
        semantic_id_to_category=semantic_id_to_category,
    )
    target_semantic_id = observations["target_semantic_id"]
    target_category = semantic_id_to_category.get(target_semantic_id, "unknown")

    updater = UsabilityUpdater()
    policy = UsabilityDecisionPolicy()
    belief = MemoryBelief(p_existence=0.9, p_location_valid=0.85, p_usable=0.85)
    rows: list[dict[str, Any]] = []
    negative_streak = 0
    collision_steps = 0
    false_positive_positive_rows = 0
    missed_visible_target_rows = 0
    total_actions = ["reset", *actions]

    for step_index, action in enumerate(total_actions):
        if action != "reset":
            observations = sim.step(action)
        semantic = np.asarray(observations["semantic"])
        depth = np.asarray(observations["depth"])
        oracle_mask = semantic == target_semantic_id
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
        false_positive_positive_rows += int(false_positive_positive)
        missed_visible_target_rows += int(missed_visible_target)

        rows.append(
            {
                "episode_index": episode_index,
                "breaker_mode": breaker_mode,
                "step_index": step_index,
                "action": action,
                "target_semantic_id": target_semantic_id,
                "target_category": target_category,
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
        "breaker_mode": breaker_mode,
        "target_semantic_id": target_semantic_id,
        "target_category": target_category,
        "trace_rows": len(rows),
        "collision_steps": collision_steps,
        "false_positive_positive_rows": false_positive_positive_rows,
        "missed_visible_target_rows": missed_visible_target_rows,
        "final_belief": _belief_dict(belief),
        "final_p_valid": round(belief.p_valid, 6),
    }


def _reset_to_visible_target(
    *,
    sim: Any,
    agent: Any,
    rng: np.random.Generator,
    min_target_pixels: int,
    semantic_id_to_category: dict[int, str],
) -> dict[str, Any]:
    if not sim.pathfinder.is_loaded:
        raise RuntimeError("Scene navmesh is not loaded")

    for _ in range(80):
        state = agent.get_state()
        state.position = sim.pathfinder.get_random_navigable_point()
        agent.set_state(state)
        observations = sim.get_sensor_observations()
        semantic = np.asarray(observations["semantic"])
        target_id = _select_visible_target_id(
            semantic,
            min_target_pixels=min_target_pixels,
            semantic_id_to_category=semantic_id_to_category,
        )
        if target_id is not None:
            return {**observations, "target_semantic_id": target_id}
        for _ in range(int(rng.integers(0, 4))):
            observations = sim.step("turn_left")
            semantic = np.asarray(observations["semantic"])
            target_id = _select_visible_target_id(
                semantic,
                min_target_pixels=min_target_pixels,
                semantic_id_to_category=semantic_id_to_category,
            )
            if target_id is not None:
                return {**observations, "target_semantic_id": target_id}
    raise RuntimeError("Could not sample a visible semantic target")


def _select_visible_target_id(
    semantic: np.ndarray,
    *,
    min_target_pixels: int,
    semantic_id_to_category: dict[int, str],
) -> int | None:
    ids, counts = np.unique(semantic, return_counts=True)
    candidates: list[tuple[int, int, bool]] = []
    for raw_id, raw_count in zip(ids, counts):
        semantic_id = int(raw_id)
        pixel_count = int(raw_count)
        if semantic_id <= 0 or pixel_count < min_target_pixels:
            continue
        category = semantic_id_to_category.get(semantic_id, "unknown")
        is_structural = _is_structural_category(category)
        candidates.append((pixel_count, semantic_id, is_structural))
    if not candidates:
        return None
    non_structural = [candidate for candidate in candidates if not candidate[2]]
    selected = max(non_structural or candidates, key=lambda value: value[0])
    return selected[1]


def _is_structural_category(category: str) -> bool:
    normalized = category.lower().replace("_", " ")
    return any(token in normalized for token in STRUCTURAL_CATEGORIES)


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


def _apply_yolo_breaker(
    oracle_mask: np.ndarray,
    *,
    rng: np.random.Generator,
    mode: str,
) -> BreakerResult:
    detector = np.asarray(oracle_mask, dtype=bool).copy()
    miss_applied = False
    fly_point_pixels = 0
    edge_break_pixels = 0

    if mode in {"miss", "mixed"}:
        miss_probability = 0.65 if mode == "miss" else 0.35
        if rng.random() < miss_probability:
            miss_applied = True
            if rng.random() < 0.55:
                detector[:] = False
            else:
                keep = rng.random(detector.shape) > 0.82
                detector &= keep

    if mode in {"edge_break", "mixed"}:
        boundary = _boundary(detector)
        leak_zone = _dilate(detector) & ~detector
        cut = boundary & (rng.random(detector.shape) < 0.45)
        leak = leak_zone & (rng.random(detector.shape) < 0.35)
        detector[cut] = False
        detector[leak] = True
        edge_break_pixels = int(cut.sum() + leak.sum())

    if mode in {"fly_point", "mixed"}:
        point_count = 9 if mode == "fly_point" else 5
        for _ in range(point_count):
            radius = int(rng.integers(1, 4))
            center_y = int(rng.integers(0, detector.shape[0]))
            center_x = int(rng.integers(0, detector.shape[1]))
            blob = _disk_mask(detector.shape, center_y, center_x, radius)
            new_pixels = blob & ~detector
            detector |= blob
            fly_point_pixels += int(new_pixels.sum())

    return BreakerResult(
        detector_mask=detector,
        miss_applied=miss_applied,
        fly_point_pixels=fly_point_pixels,
        edge_break_pixels=edge_break_pixels,
    )


def _mask_metrics(
    *,
    oracle_mask: np.ndarray,
    detector_mask: np.ndarray,
) -> dict[str, Any]:
    oracle = np.asarray(oracle_mask, dtype=bool)
    detector = np.asarray(detector_mask, dtype=bool)
    oracle_pixels = int(oracle.sum())
    detector_pixels = int(detector.sum())
    overlap_pixels = int((oracle & detector).sum())
    false_positive_pixels = int((detector & ~oracle).sum())
    component_count, largest_component_pixels = _component_stats(detector)
    largest_component_ratio = (
        largest_component_pixels / detector_pixels if detector_pixels else 0.0
    )
    edge_touch_ratio = _edge_touch_ratio(detector)
    return {
        "oracle_target_pixels": oracle_pixels,
        "detector_pixels": detector_pixels,
        "overlap_pixels": overlap_pixels,
        "false_positive_pixels": false_positive_pixels,
        "oracle_recall": round(overlap_pixels / oracle_pixels, 6)
        if oracle_pixels
        else 0.0,
        "detector_precision": round(overlap_pixels / detector_pixels, 6)
        if detector_pixels
        else 0.0,
        "false_positive_ratio": round(false_positive_pixels / detector_pixels, 6)
        if detector_pixels
        else 0.0,
        "component_count": component_count,
        "largest_component_pixels": largest_component_pixels,
        "largest_component_ratio": round(largest_component_ratio, 6),
        "edge_touch_ratio": round(edge_touch_ratio, 6),
    }


def _classify_semantic_evidence(
    *,
    action: str,
    collided: bool,
    depth_valid_ratio: float,
    metrics: dict[str, Any],
    min_target_pixels: int,
    min_detector_pixels: int,
) -> tuple[EvidenceType, float, bool, str]:
    if action == "reset":
        return EvidenceType.UNKNOWN, 0.2, False, "reset"
    if collided:
        return EvidenceType.ACCESS_BLOCKED, 1.0, False, "collision"
    if depth_valid_ratio < 0.25:
        return EvidenceType.UNKNOWN, 0.8, False, "depth_unhealthy"

    detector_pixels = int(metrics["detector_pixels"])
    oracle_pixels = int(metrics["oracle_target_pixels"])
    component_count = int(metrics["component_count"])
    largest_component_ratio = float(metrics["largest_component_ratio"])
    edge_touch_ratio = float(metrics["edge_touch_ratio"])
    if detector_pixels >= min_detector_pixels:
        if component_count >= 8 or largest_component_ratio < 0.38:
            return EvidenceType.UNKNOWN, 0.85, True, "fragmented_detector_mask"
        if edge_touch_ratio > 0.45:
            return EvidenceType.OCCLUDED, 0.75, True, "edge_touch_breakthrough"
        area_strength = min(1.6, 0.75 + detector_pixels / max(min_detector_pixels * 6.0, 1.0))
        return EvidenceType.POSITIVE, area_strength, False, "detector_positive_mask"

    if oracle_pixels >= min_target_pixels:
        return EvidenceType.NON_CONFIRMATION, 1.0, False, "missed_visible_oracle_target"
    if depth_valid_ratio >= 0.85:
        return EvidenceType.UNKNOWN, 0.45, False, "target_out_of_current_view"
    return EvidenceType.UNKNOWN, 0.5, False, "weak_observation"


def _decision_context(
    *,
    step_index: int,
    total_steps: int,
    negative_streak: int,
    metrics: dict[str, Any],
) -> DecisionContext:
    detector_pixels = int(metrics["detector_pixels"])
    d_nav = 2.0 + min(8.0, negative_streak * 1.25)
    d_verify = 1.5 if detector_pixels else 3.0
    c_search = 18.0 + min(8.0, negative_streak * 2.0)
    return DecisionContext(
        d_nav=d_nav,
        d_verify=d_verify,
        c_fail=14.0,
        c_search=c_search,
        b_remaining=max(0.0, float(total_steps - step_index - 1)),
        verification_repeatedly_failed=negative_streak >= 4,
    )


def _depth_valid_ratio(depth: np.ndarray) -> float:
    finite = np.isfinite(depth)
    valid = finite & (depth > 0.0)
    return round(float(valid.mean()), 6)


def _dilate(mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    return (
        mask
        | _shift(mask, -1, 0)
        | _shift(mask, 1, 0)
        | _shift(mask, 0, -1)
        | _shift(mask, 0, 1)
    )


def _erode(mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    return (
        mask
        & _shift(mask, -1, 0)
        & _shift(mask, 1, 0)
        & _shift(mask, 0, -1)
        & _shift(mask, 0, 1)
    )


def _boundary(mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    return mask & ~_erode(mask)


def _shift(mask: np.ndarray, dy: int, dx: int) -> np.ndarray:
    shifted = np.zeros_like(mask, dtype=bool)
    src_y0 = max(0, -dy)
    src_y1 = mask.shape[0] - max(0, dy)
    src_x0 = max(0, -dx)
    src_x1 = mask.shape[1] - max(0, dx)
    dst_y0 = max(0, dy)
    dst_y1 = dst_y0 + max(0, src_y1 - src_y0)
    dst_x0 = max(0, dx)
    dst_x1 = dst_x0 + max(0, src_x1 - src_x0)
    if src_y1 > src_y0 and src_x1 > src_x0:
        shifted[dst_y0:dst_y1, dst_x0:dst_x1] = mask[src_y0:src_y1, src_x0:src_x1]
    return shifted


def _disk_mask(
    shape: tuple[int, ...],
    center_y: int,
    center_x: int,
    radius: int,
) -> np.ndarray:
    height, width = shape[:2]
    yy, xx = np.ogrid[:height, :width]
    return (yy - center_y) ** 2 + (xx - center_x) ** 2 <= radius**2


def _component_stats(mask: np.ndarray) -> tuple[int, int]:
    mask = np.asarray(mask, dtype=bool)
    visited = np.zeros(mask.shape, dtype=bool)
    component_count = 0
    largest = 0
    height, width = mask.shape
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue
            component_count += 1
            stack = [(y, x)]
            visited[y, x] = True
            size = 0
            while stack:
                cy, cx = stack.pop()
                size += 1
                for ny, nx in (
                    (cy - 1, cx),
                    (cy + 1, cx),
                    (cy, cx - 1),
                    (cy, cx + 1),
                ):
                    if (
                        0 <= ny < height
                        and 0 <= nx < width
                        and mask[ny, nx]
                        and not visited[ny, nx]
                    ):
                        visited[ny, nx] = True
                        stack.append((ny, nx))
            largest = max(largest, size)
    return component_count, largest


def _edge_touch_ratio(mask: np.ndarray) -> float:
    mask = np.asarray(mask, dtype=bool)
    pixels = int(mask.sum())
    if pixels == 0:
        return 0.0
    edge = np.zeros(mask.shape, dtype=bool)
    edge[0, :] = True
    edge[-1, :] = True
    edge[:, 0] = True
    edge[:, -1] = True
    return float((mask & edge).sum() / pixels)


def _summarize(
    *,
    scene: Path,
    scene_dataset_config: Path | None,
    episodes: int,
    seed: int,
    sensor_size: int,
    breaker_modes: Sequence[str],
    min_target_pixels: int,
    min_detector_pixels: int,
    semantic_object_count: int,
    semantic_category_count: int,
    rows: Sequence[dict[str, Any]],
    episode_summaries: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    mode_summaries: dict[str, dict[str, Any]] = {}
    for mode in breaker_modes:
        mode_rows = [row for row in rows if row["breaker_mode"] == mode]
        mode_episodes = [
            episode for episode in episode_summaries if episode["breaker_mode"] == mode
        ]
        final_values = [episode["final_p_valid"] for episode in mode_episodes]
        mode_summaries[mode] = {
            "rows": len(mode_rows),
            "episodes": len(mode_episodes),
            "evidence_counts": _count_values(mode_rows, "evidence_type"),
            "decision_counts": _count_values(mode_rows, "decision"),
            "false_positive_positive_rows": sum(
                int(row["false_positive_positive"]) for row in mode_rows
            ),
            "missed_visible_target_rows": sum(
                int(row["missed_visible_target"]) for row in mode_rows
            ),
            "mean_final_p_valid": round(float(np.mean(final_values)), 6)
            if final_values
            else None,
        }

    final_values = [episode["final_p_valid"] for episode in episode_summaries]
    return {
        "task": "habitat_semantic_yolo_stress",
        "benchmark_dataset": False,
        "scene_path": str(scene),
        "scene_dataset_config": str(scene_dataset_config) if scene_dataset_config else None,
        "episodes_requested": episodes,
        "episodes_completed": len(episode_summaries),
        "seed": seed,
        "sensor_size": sensor_size,
        "breaker_modes": list(breaker_modes),
        "min_target_pixels": min_target_pixels,
        "min_detector_pixels": min_detector_pixels,
        "semantic_object_count": semantic_object_count,
        "semantic_category_count": semantic_category_count,
        "trace_rows": len(rows),
        "evidence_counts": _count_values(rows, "evidence_type"),
        "decision_counts": _count_values(rows, "decision"),
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
        "episode_summaries": list(episode_summaries),
        "artifact_files": {
            "trace": "semantic_yolo_trace.csv",
            "summary": "summary.json",
            "report": "report.html",
        },
        "limits": [
            "Uses Habitat-Sim semantic sensor output and corrupted semantic masks.",
            "Uses oracle semantic ids as detector input before corruption; no learned YOLO model is run.",
            "Synthetic breaker modes simulate misses, false-positive fly points, and edge failures.",
            "Not an official Habitat ObjectNav benchmark; no success or SPL is claimed.",
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
    mode_rows = "\n".join(
        _render_mode_row(mode, payload)
        for mode, payload in summary["mode_summaries"].items()
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
  <title>Habitat Semantic YOLO Stress</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.45; margin: 2rem; color: #202124; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0 1.5rem; }}
    th, td {{ border: 1px solid #dadce0; padding: 0.55rem; text-align: left; vertical-align: top; }}
    th {{ background: #f8f9fa; }}
    code {{ background: #f1f3f4; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Habitat Semantic YOLO Stress</h1>
  <p>Episodes: <code>{summary["episodes_completed"]}</code>; rows: <code>{summary["trace_rows"]}</code>; mean final p_valid: <code>{summary["mean_final_p_valid"]}</code>.</p>
  <h2>Breaker Modes</h2>
  <table>
    <tr><th>Mode</th><th>Episodes</th><th>Rows</th><th>Mean Final p_valid</th><th>False Positive Positives</th><th>Missed Visible Targets</th></tr>
    {mode_rows}
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


def _render_mode_row(mode: str, payload: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td><code>{escape(mode)}</code></td>"
        f"<td>{payload['episodes']}</td>"
        f"<td>{payload['rows']}</td>"
        f"<td>{payload['mean_final_p_valid']}</td>"
        f"<td>{payload['false_positive_positive_rows']}</td>"
        f"<td>{payload['missed_visible_target_rows']}</td>"
        "</tr>"
    )
