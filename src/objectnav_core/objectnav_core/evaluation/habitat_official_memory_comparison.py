from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    METRIC_SOURCE,
    run_habitat_official_objectnav_eval,
    write_json,
)


COMPARISON_TASK = "habitat_official_memory_baseline_comparison"
COMPARISON_LABELS: tuple[str, ...] = ("memory_guided", "no_memory", "naive_count")


@dataclass(frozen=True)
class OfficialMemoryComparisonSpec:
    label: str
    policy: str
    memory_prior_role: str | None = None
    description: str = ""


DEFAULT_COMPARISON_SPECS: dict[str, OfficialMemoryComparisonSpec] = {
    "memory_guided": OfficialMemoryComparisonSpec(
        label="memory_guided",
        policy="memory_active_perception_frontier_targetnav",
        memory_prior_role="memory_guided",
        description="Proposed memory-guided ObjectNav policy.",
    ),
    "no_memory": OfficialMemoryComparisonSpec(
        label="no_memory",
        policy="no_memory_targetnav",
        memory_prior_role=None,
        description="No-memory exploration with shared TargetNav handoff.",
    ),
    "naive_count": OfficialMemoryComparisonSpec(
        label="naive_count",
        policy="naive_count_targetnav",
        memory_prior_role="naive_count",
        description="Positive-only count memory baseline with shared TargetNav handoff.",
    ),
}

_CSV_FIELDS: tuple[str, ...] = (
    "label",
    "policy",
    "episodes",
    "success_rate",
    "spl",
    "soft_spl",
    "distance_to_goal",
    "policy_kind",
    "metric_source",
    "summary_path",
    "run_dir",
    "invalid_for_benchmark_claim_reason",
)


def compare_official_memory_summaries(
    output_dir: str | Path,
    summary_paths: Mapping[str, str | Path],
) -> dict[str, Any]:
    """Build a paper-facing memory comparison from completed official summaries."""

    _validate_required_labels(summary_paths)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    rows = [
        _row_from_summary_path(label, summary_paths[label])
        for label in _ordered_labels(summary_paths)
    ]
    report = {
        "task": COMPARISON_TASK,
        "metric_source": METRIC_SOURCE,
        "labels": [row["label"] for row in rows],
        "rows": rows,
        "comparison": _comparison_deltas(rows),
        "artifact_files": {
            "comparison": "comparison.json",
            "csv": "comparison.csv",
            "markdown": "comparison.md",
        },
        "notes": [
            "All SR/SPL/SoftSPL/DistanceToGoal values are copied from official Habitat summaries.",
            "Smoke-sized comparisons are diagnostic and are not leaderboard claims.",
            "The naive_count row is only paper-valid when its prior comes from a documented positive-only count source.",
        ],
    }
    write_json(output_path / "comparison.json", report)
    _write_comparison_csv(output_path / "comparison.csv", rows)
    _write_comparison_markdown(output_path / "comparison.md", rows)
    return report


def run_habitat_official_memory_comparison(
    output_dir: str | Path,
    *,
    config_path: str,
    dataset_data_path: str,
    scene_root: str,
    split: str = "val_mini",
    max_episodes: int | None = 4,
    max_steps: int = 100,
    seed: int = 313,
    validate_habitat: bool = False,
    memory_guided_prior_path: str | Path | None,
    naive_count_prior_path: str | Path | None,
    memory_guided_policy: str = DEFAULT_COMPARISON_SPECS["memory_guided"].policy,
    no_memory_policy: str = DEFAULT_COMPARISON_SPECS["no_memory"].policy,
    naive_count_policy: str = DEFAULT_COMPARISON_SPECS["naive_count"].policy,
    memory_stop_radius_m: float = 0.35,
    memory_bearing_tolerance_deg: float = 20.0,
    memory_min_confidence: float = 0.0,
    target_detector_adapter: Any | None = None,
    target_detector_min_confidence: float = 0.25,
    detector_center_direction_sign: int = 1,
    local_action_model_path: str | Path | None = None,
    candidate_viewpoint_ranker_model_path: str | Path | None = None,
    pathfinder_suffix_goal_radius_m: float = 1.0,
    targetnav_backend: str = "oracle_follower",
    targetnav_ddppo_checkpoint_path: str | Path | None = None,
    targetnav_ddppo_device: str = "auto",
    runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the three official policies, then aggregate their Habitat metrics."""

    if memory_guided_prior_path is None:
        raise ValueError("memory_guided_prior_path is required in run mode")
    if naive_count_prior_path is None:
        raise ValueError("naive_count_prior_path is required in run mode")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    specs = {
        "memory_guided": OfficialMemoryComparisonSpec(
            label="memory_guided",
            policy=memory_guided_policy,
            memory_prior_role="memory_guided",
            description=DEFAULT_COMPARISON_SPECS["memory_guided"].description,
        ),
        "no_memory": OfficialMemoryComparisonSpec(
            label="no_memory",
            policy=no_memory_policy,
            memory_prior_role=None,
            description=DEFAULT_COMPARISON_SPECS["no_memory"].description,
        ),
        "naive_count": OfficialMemoryComparisonSpec(
            label="naive_count",
            policy=naive_count_policy,
            memory_prior_role="naive_count",
            description=DEFAULT_COMPARISON_SPECS["naive_count"].description,
        ),
    }
    prior_paths = {
        "memory_guided": str(memory_guided_prior_path),
        "naive_count": str(naive_count_prior_path),
    }
    run = runner or run_habitat_official_objectnav_eval
    summary_paths: dict[str, Path] = {}

    for label in COMPARISON_LABELS:
        spec = specs[label]
        run_dir = output_path / label
        run_dir.mkdir(parents=True, exist_ok=True)
        memory_prior_path = (
            prior_paths[spec.memory_prior_role]
            if spec.memory_prior_role is not None
            else None
        )
        summary = run(
            run_dir,
            config_path=config_path,
            dataset_data_path=dataset_data_path,
            scene_root=scene_root,
            split=split,
            policy=spec.policy,
            max_episodes=max_episodes,
            max_steps=max_steps,
            seed=seed,
            validate_habitat=validate_habitat,
            memory_prior_path=memory_prior_path,
            memory_stop_radius_m=memory_stop_radius_m,
            memory_bearing_tolerance_deg=memory_bearing_tolerance_deg,
            memory_min_confidence=memory_min_confidence,
            target_detector_adapter=target_detector_adapter,
            target_detector_min_confidence=target_detector_min_confidence,
            detector_center_direction_sign=detector_center_direction_sign,
            local_action_model_path=(
                str(local_action_model_path) if local_action_model_path else None
            ),
            candidate_viewpoint_ranker_model_path=(
                str(candidate_viewpoint_ranker_model_path)
                if candidate_viewpoint_ranker_model_path
                else None
            ),
            pathfinder_suffix_goal_radius_m=pathfinder_suffix_goal_radius_m,
            targetnav_backend=targetnav_backend,
            targetnav_ddppo_checkpoint_path=(
                str(targetnav_ddppo_checkpoint_path)
                if targetnav_ddppo_checkpoint_path
                else None
            ),
            targetnav_ddppo_device=targetnav_ddppo_device,
        )
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            write_json(summary_path, summary)
        summary_paths[label] = summary_path

    return compare_official_memory_summaries(output_path, summary_paths)


def _validate_required_labels(summary_paths: Mapping[str, str | Path]) -> None:
    missing = [label for label in COMPARISON_LABELS if label not in summary_paths]
    if missing:
        raise ValueError(
            "official memory comparison requires summaries for: "
            + ", ".join(missing)
        )


def _ordered_labels(summary_paths: Mapping[str, str | Path]) -> list[str]:
    ordered = [label for label in COMPARISON_LABELS if label in summary_paths]
    ordered.extend(sorted(label for label in summary_paths if label not in ordered))
    return ordered


def _row_from_summary_path(label: str, summary_path: str | Path) -> dict[str, Any]:
    path = Path(summary_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} summary must be a JSON object")

    metrics = payload.get("official_metrics")
    if not isinstance(metrics, dict):
        raise ValueError(f"{label} summary lacks Habitat official metrics")
    if metrics.get("measure_source") != METRIC_SOURCE:
        raise ValueError(
            f"{label} summary does not use Habitat official metrics from {METRIC_SOURCE}"
        )
    if metrics.get("required_measures_present") is not True:
        raise ValueError(f"{label} summary is missing required official measures")

    manifest = payload.get("protocol_manifest")
    if not isinstance(manifest, dict):
        manifest = {}
    config = payload.get("config")
    if not isinstance(config, dict):
        config = {}
    policy = str(payload.get("policy") or manifest.get("policy") or "")
    return {
        "label": label,
        "policy": policy,
        "policy_kind": str(manifest.get("policy_kind") or ""),
        "episodes": int(metrics.get("episodes", 0)),
        "success_rate": _required_float(metrics, "success_rate", label=label),
        "spl": _required_float(metrics, "spl", label=label),
        "soft_spl": _required_float(metrics, "soft_spl", label=label),
        "distance_to_goal": _required_float(
            metrics, "distance_to_goal", label=label
        ),
        "metric_source": str(metrics["measure_source"]),
        "summary_path": str(path),
        "run_dir": str(path.parent),
        "split": config.get("split"),
        "max_episodes": config.get("max_episodes"),
        "max_steps": config.get("max_steps"),
        "seed": config.get("seed"),
        "invalid_for_benchmark_claim_reason": manifest.get(
            "invalid_for_benchmark_claim_reason"
        ),
    }


def _required_float(
    metrics: Mapping[str, Any],
    key: str,
    *,
    label: str,
) -> float:
    value = metrics.get(key)
    if value is None:
        raise ValueError(f"{label} official metric {key} is missing")
    return float(value)


def _comparison_deltas(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_label = {str(row["label"]): row for row in rows}
    memory = by_label.get("memory_guided")
    if memory is None:
        return {}
    comparison: dict[str, Any] = {}
    for baseline_label in ("no_memory", "naive_count"):
        baseline = by_label.get(baseline_label)
        if baseline is None:
            continue
        prefix = f"memory_guided_vs_{baseline_label}"
        for metric in ("success_rate", "spl", "soft_spl"):
            comparison[f"{prefix}_{metric}_delta"] = round(
                float(memory[metric]) - float(baseline[metric]),
                6,
            )
        comparison[f"{prefix}_distance_to_goal_reduction_m"] = round(
            float(baseline["distance_to_goal"]) - float(memory["distance_to_goal"]),
            6,
        )
    return comparison


def _write_comparison_csv(
    path: str | Path,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_CSV_FIELDS))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in _CSV_FIELDS})


def _write_comparison_markdown(
    path: str | Path,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    lines = [
        "# Official Memory Baseline Comparison",
        "",
        "| Method | Policy | Episodes | SR | SPL | SoftSPL | DistanceToGoal | Caveat |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| {label} | {policy} | {episodes} | {success_rate:.4f} | "
            "{spl:.4f} | {soft_spl:.4f} | {distance_to_goal:.4f} | {caveat} |".format(
                label=row["label"],
                policy=row["policy"],
                episodes=row["episodes"],
                success_rate=float(row["success_rate"]),
                spl=float(row["spl"]),
                soft_spl=float(row["soft_spl"]),
                distance_to_goal=float(row["distance_to_goal"]),
                caveat=row.get("invalid_for_benchmark_claim_reason") or "",
            )
        )
    lines.extend(
        [
            "",
            "Metric source: `habitat.Env.get_metrics`.",
            "",
            "This table is paper-facing only when all memory priors are produced by documented non-oracle sources and the run size matches the declared protocol.",
        ]
    )
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
