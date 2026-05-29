from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from objectnav_core.geometry.dual_anchor import (
    PoseEstimate2D,
    match_instance_by_mahalanobis,
)


@dataclass(frozen=True)
class DualAnchorPressureCase:
    name: str
    observed_xy: tuple[float, float]
    candidate_xy: Mapping[str, tuple[float, float]]
    covariance_scale: float


def run_dual_anchor_matching_pressure(
    *,
    cases: Sequence[DualAnchorPressureCase],
    gate_threshold: float,
    ambiguity_margin: float,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for case in cases:
        covariance = (
            (float(case.covariance_scale), 0.0),
            (0.0, float(case.covariance_scale)),
        )
        observed = PoseEstimate2D(
            x=case.observed_xy[0],
            y=case.observed_xy[1],
            covariance=covariance,
        )
        candidates = {
            object_id: PoseEstimate2D(
                x=xy[0],
                y=xy[1],
                covariance=covariance,
            )
            for object_id, xy in case.candidate_xy.items()
        }
        match = match_instance_by_mahalanobis(
            observed=observed,
            candidates=candidates,
            gate_threshold=gate_threshold,
            ambiguity_margin=ambiguity_margin,
        )
        rows.append(
            {
                "case": case.name,
                "accepted": match.accepted,
                "object_id": match.object_id,
                "reason": match.reason,
                "best_distance": match.best_distance,
                "second_best_distance": match.second_best_distance,
                "distances": match.distances,
            }
        )
    return {
        "case_count": len(rows),
        "accepted_count": sum(1 for row in rows if row["accepted"]),
        "ambiguous_count": sum(1 for row in rows if row["reason"] == "ambiguous"),
        "outside_gate_count": sum(1 for row in rows if row["reason"] == "outside_gate"),
        "rows": rows,
    }


def run_dual_anchor_matching_pressure_report(
    output_dir: str | Path,
    *,
    cases: Sequence[DualAnchorPressureCase],
    gate_threshold: float,
    ambiguity_margin: float,
) -> dict[str, object]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    summary = run_dual_anchor_matching_pressure(
        cases=cases,
        gate_threshold=gate_threshold,
        ambiguity_margin=ambiguity_margin,
    )
    summary.update(
        {
            "task": "dual_anchor_matching_pressure",
            "gate_threshold": float(gate_threshold),
            "ambiguity_margin": float(ambiguity_margin),
            "artifact_files": {"summary": "summary.json"},
        }
    )
    (output_path / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary
