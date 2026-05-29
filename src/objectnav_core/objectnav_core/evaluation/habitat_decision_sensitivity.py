from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Sequence


DEFAULT_MAX_MARGIN_ACTIONS = 5.0
DEFAULT_MIN_DETECTOR_EVENT_COUNT = 1
DEFAULT_MIN_RELIABILITY_DELTA = 0.1
DEFAULT_MAX_RELIABILITY_INTERVAL_GAP = 0.05
DEFAULT_POLICIES: tuple[str, ...] = ("memory_guided",)

_CSV_FIELDS: tuple[str, ...] = (
    "source_summary",
    "run_id",
    "group_id",
    "category",
    "relocation_pair_distance_m",
    "policy",
    "query_repeat_index",
    "challenge",
    "detector",
    "frontier_mode",
    "route_observation_mode",
    "actual_memory_decision",
    "memory_decision_bucket",
    "memory_action_count",
    "fallback_action_count",
    "fallback_from_memory_action_count",
    "actual_reliability",
    "fixed_reliability",
    "evidence_reliability",
    "event_posterior_reliability",
    "decision_boundary_reliability",
    "decision_boundary_reliability_raw",
    "decision_boundary_region",
    "reliability_delta",
    "reliability_interval_min",
    "reliability_interval_max",
    "boundary_reliability_interval_gap",
    "boundary_reliability_interval_position",
    "expected_memory_first_action_count",
    "expected_frontier_first_action_count",
    "event_posterior_expected_memory_first_action_count",
    "decision_margin_actions",
    "fixed_decision",
    "evidence_decision",
    "event_posterior_decision",
    "counterfactual_decision_flip",
    "detector_event_count",
    "detector_event_posterior",
    "detector_event_confirmed_weight",
    "detector_event_suppressed_weight",
    "current_evidence",
    "matching",
    "hindsight_best_candidate_type",
    "hindsight_action_regret",
    "hindsight_distance_regret_m",
    "sensitivity_score",
    "sensitivity_reasons",
)


def mine_habitat_decision_sensitivity(
    inputs: Sequence[str | Path],
    *,
    max_margin_actions: float = DEFAULT_MAX_MARGIN_ACTIONS,
    min_detector_event_count: int = DEFAULT_MIN_DETECTOR_EVENT_COUNT,
    min_reliability_delta: float = DEFAULT_MIN_RELIABILITY_DELTA,
    max_reliability_interval_gap: float = DEFAULT_MAX_RELIABILITY_INTERVAL_GAP,
    policies: Sequence[str] = DEFAULT_POLICIES,
    top_k: int | None = None,
) -> dict[str, Any]:
    """Rank Habitat summary rows where reliability can affect decisions."""

    policy_filter = {str(policy) for policy in policies}
    summary_paths = _resolve_summary_paths(inputs)
    candidates: list[dict[str, Any]] = []
    row_count = 0
    warning_count = 0
    warnings: list[str] = []
    for summary_path in summary_paths:
        try:
            summary = _load_summary(summary_path)
        except (OSError, json.JSONDecodeError) as exc:
            warning_count += 1
            warnings.append(f"{summary_path}: {exc}")
            continue
        rows = summary.get("rows", [])
        if not isinstance(rows, list):
            warning_count += 1
            warnings.append(f"{summary_path}: rows is not a list")
            continue
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                warning_count += 1
                warnings.append(f"{summary_path}: row {row_index} is not an object")
                continue
            if policy_filter and str(row.get("policy", "")) not in policy_filter:
                continue
            row_count += 1
            try:
                candidate = _candidate_from_row(
                    summary=summary,
                    summary_path=summary_path,
                    row=row,
                    max_margin_actions=max_margin_actions,
                    min_detector_event_count=min_detector_event_count,
                    min_reliability_delta=min_reliability_delta,
                    max_reliability_interval_gap=max_reliability_interval_gap,
                )
            except (TypeError, ValueError, KeyError) as exc:
                warning_count += 1
                warnings.append(f"{summary_path}: row {row_index}: {exc}")
                continue
            if candidate is not None:
                candidates.append(candidate)

    candidates.sort(
        key=lambda candidate: (
            -float(candidate["sensitivity_score"]),
            float(candidate["decision_margin_actions"]),
            str(candidate["source_summary"]),
            str(candidate["group_id"]),
        )
    )
    if top_k is not None:
        candidates = candidates[: max(0, int(top_k))]
    return {
        "task": "habitat_decision_sensitivity_mining",
        "summary_count": len(summary_paths),
        "row_count": row_count,
        "candidate_count": len(candidates),
        "filters": {
            "max_margin_actions": round(float(max_margin_actions), 6),
            "min_detector_event_count": int(min_detector_event_count),
            "min_reliability_delta": round(float(min_reliability_delta), 6),
            "max_reliability_interval_gap": round(
                float(max_reliability_interval_gap),
                6,
            ),
            "policies": sorted(policy_filter),
            "top_k": top_k,
        },
        "aggregate": _aggregate_candidates(candidates),
        "warnings": warnings,
        "warning_count": warning_count,
        "candidates": candidates,
    }


def write_decision_sensitivity_csv(
    path: str | Path,
    candidates: Sequence[dict[str, Any]],
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for candidate in candidates:
            writer.writerow(
                {
                    field: _csv_value(candidate.get(field))
                    for field in _CSV_FIELDS
                }
            )


def _resolve_summary_paths(inputs: Sequence[str | Path]) -> list[Path]:
    paths: list[Path] = []
    for raw_input in inputs:
        input_path = Path(raw_input)
        if input_path.is_dir():
            paths.extend(sorted(input_path.rglob("summary.json")))
        elif input_path.name == "summary.json" and input_path.exists():
            paths.append(input_path)
        elif input_path.exists():
            paths.append(input_path)
    return sorted(dict.fromkeys(path.resolve() for path in paths))


def _load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("summary root is not an object")
    return payload


def _candidate_from_row(
    *,
    summary: dict[str, Any],
    summary_path: Path,
    row: dict[str, Any],
    max_margin_actions: float,
    min_detector_event_count: int,
    min_reliability_delta: float,
    max_reliability_interval_gap: float,
) -> dict[str, Any] | None:
    memory_actions = _require_int(row, "memory_action_count")
    frontier_actions = _require_int(row, "fallback_action_count")
    fallback_from_memory_actions = _require_int(
        row,
        "fallback_from_memory_action_count",
    )
    reliability = _float(row.get("memory_valid_prior"), default=0.5)
    reliability_payload = row.get("memory_reliability")
    components = _reliability_components(reliability_payload)
    base_prior = _float(
        components.get("base_prior"),
        default=_float(summary.get("memory_valid_prior"), default=0.5),
    )
    evidence_reliability = _evidence_reliability_from_components(
        components,
        fallback=reliability
        if _payload_mode(reliability_payload) == "evidence"
        else base_prior,
    )
    event_posterior_reliability = _event_posterior_reliability_from_components(
        components,
        evidence_reliability=evidence_reliability,
    )
    fixed_reliability = round(_clamp01(base_prior), 6)
    actual_expected_memory = _float(
        row.get("expected_memory_first_action_count"),
        default=_expected_memory_first_action_count(
            memory_actions,
            fallback_from_memory_actions,
            reliability,
        ),
    )
    expected_frontier = _float(
        row.get("expected_frontier_first_action_count"),
        default=float(frontier_actions),
    )
    event_expected_memory = _expected_memory_first_action_count(
        memory_actions,
        fallback_from_memory_actions,
        event_posterior_reliability,
    )
    decision_margin = round(abs(event_expected_memory - expected_frontier), 6)
    detector_event_count = _float(
        components.get("detector_event_count"),
        default=0.0,
    )
    confirmed_weight = _float(
        components.get("detector_event_confirmed_weight"),
        default=0.0,
    )
    suppressed_weight = _float(
        components.get("detector_event_suppressed_weight"),
        default=0.0,
    )
    reliability_delta = round(
        abs(evidence_reliability - event_posterior_reliability),
        6,
    )
    evidence_decision = _memory_first_decision(
        memory_actions,
        fallback_from_memory_actions,
        frontier_actions,
        evidence_reliability,
    )
    event_decision = _memory_first_decision(
        memory_actions,
        fallback_from_memory_actions,
        frontier_actions,
        event_posterior_reliability,
    )
    fixed_decision = _memory_first_decision(
        memory_actions,
        fallback_from_memory_actions,
        frontier_actions,
        fixed_reliability,
    )
    counterfactual_flip = evidence_decision != event_decision
    hindsight_regret = _int(row.get("hindsight_action_regret"), default=0)
    boundary_raw = _decision_boundary_reliability_raw(
        memory_actions,
        fallback_from_memory_actions,
        frontier_actions,
    )
    boundary_region = _decision_boundary_region(boundary_raw)
    reliability_interval_min = min(evidence_reliability, event_posterior_reliability)
    reliability_interval_max = max(evidence_reliability, event_posterior_reliability)
    boundary_interval_gap = _boundary_reliability_interval_gap(
        boundary_raw,
        reliability_interval_min,
        reliability_interval_max,
    )
    boundary_interval_position = _boundary_reliability_interval_position(
        boundary_raw,
        reliability_interval_min,
        reliability_interval_max,
    )
    reasons = _sensitivity_reasons(
        decision_margin=decision_margin,
        max_margin_actions=max_margin_actions,
        decision_boundary_region=boundary_region,
        boundary_reliability_interval_gap=boundary_interval_gap,
        max_reliability_interval_gap=max_reliability_interval_gap,
        detector_event_count=detector_event_count,
        min_detector_event_count=min_detector_event_count,
        confirmed_weight=confirmed_weight,
        suppressed_weight=suppressed_weight,
        reliability_delta=reliability_delta,
        min_reliability_delta=min_reliability_delta,
        counterfactual_flip=counterfactual_flip,
        hindsight_regret=hindsight_regret,
    )
    if not reasons:
        return None
    candidate = {
        "source_summary": str(summary_path),
        "run_id": summary_path.parent.name,
        "group_id": str(row.get("group_id", "")),
        "category": str(row.get("category", "")),
        "relocation_pair_distance_m": _optional_rounded_float(
            row.get("relocation_pair_distance_m")
        ),
        "policy": str(row.get("policy", "")),
        "query_repeat_index": _int(row.get("query_repeat_index"), default=0),
        "challenge": str(summary.get("challenge", "")),
        "detector": str(summary.get("detector", "")),
        "frontier_mode": str(summary.get("frontier_mode", "")),
        "route_observation_mode": str(summary.get("route_observation_mode", "")),
        "actual_memory_decision": str(row.get("memory_decision", "")),
        "memory_decision_bucket": str(row.get("memory_decision_bucket", "")),
        "memory_action_count": memory_actions,
        "fallback_action_count": frontier_actions,
        "fallback_from_memory_action_count": fallback_from_memory_actions,
        "actual_reliability": round(reliability, 6),
        "fixed_reliability": fixed_reliability,
        "evidence_reliability": evidence_reliability,
        "event_posterior_reliability": event_posterior_reliability,
        "decision_boundary_reliability": (
            None if boundary_raw is None else round(_clamp01(boundary_raw), 6)
        ),
        "decision_boundary_reliability_raw": (
            None if boundary_raw is None else round(float(boundary_raw), 6)
        ),
        "decision_boundary_region": boundary_region,
        "reliability_delta": reliability_delta,
        "reliability_interval_min": round(reliability_interval_min, 6),
        "reliability_interval_max": round(reliability_interval_max, 6),
        "boundary_reliability_interval_gap": boundary_interval_gap,
        "boundary_reliability_interval_position": boundary_interval_position,
        "expected_memory_first_action_count": round(actual_expected_memory, 6),
        "expected_frontier_first_action_count": round(expected_frontier, 6),
        "event_posterior_expected_memory_first_action_count": round(
            event_expected_memory,
            6,
        ),
        "decision_margin_actions": decision_margin,
        "fixed_decision": fixed_decision,
        "evidence_decision": evidence_decision,
        "event_posterior_decision": event_decision,
        "counterfactual_decision_flip": counterfactual_flip,
        "detector_event_count": detector_event_count,
        "detector_event_posterior": round(
            _float(components.get("detector_event_posterior"), default=base_prior),
            6,
        ),
        "detector_event_confirmed_weight": round(confirmed_weight, 6),
        "detector_event_suppressed_weight": round(suppressed_weight, 6),
        "current_evidence": round(
            _float(components.get("current_evidence"), default=0.0),
            6,
        ),
        "matching": round(_float(components.get("matching"), default=0.0), 6),
        "hindsight_best_candidate_type": str(
            row.get("hindsight_best_candidate_type", "")
        ),
        "hindsight_action_regret": hindsight_regret,
        "hindsight_distance_regret_m": round(
            _float(row.get("hindsight_distance_regret_m"), default=0.0),
            6,
        ),
        "sensitivity_reasons": reasons,
    }
    candidate["sensitivity_score"] = _sensitivity_score(candidate)
    return candidate


def _optional_rounded_float(value: object) -> float | None:
    if value is None:
        return None
    return round(_float(value, default=0.0), 6)


def _reliability_components(payload: object) -> dict[str, float]:
    if not isinstance(payload, dict):
        return {}
    components = payload.get("components", {})
    if not isinstance(components, dict):
        return {}
    return {
        str(key): _float(value, default=0.0)
        for key, value in components.items()
    }


def _payload_mode(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("mode", ""))


def _evidence_reliability_from_components(
    components: dict[str, float],
    *,
    fallback: float,
) -> float:
    base_prior = _float(components.get("base_prior"), default=fallback)
    matching = _float(components.get("matching"), default=1.0)
    current_evidence = _float(components.get("current_evidence"), default=1.0)
    covariance = _float(components.get("transform_covariance"), default=1.0)
    category_prior = _float(components.get("category_prior"), default=base_prior)
    recency = _float(components.get("recency"), default=1.0)
    if matching < 0.5:
        value = min(0.3, base_prior * matching)
    elif current_evidence < 0.5:
        value = min(0.34, 0.5 * base_prior + 0.25 * current_evidence)
    else:
        value = (
            0.10 * base_prior
            + 0.50 * current_evidence
            + 0.22 * matching
            + 0.08 * covariance
            + 0.05 * category_prior
            + 0.05 * recency
        )
        if current_evidence >= 0.95 and matching >= 1.0 and covariance >= 0.85:
            value = max(value, 0.96)
    return round(_clamp01(value), 6)


def _event_posterior_reliability_from_components(
    components: dict[str, float],
    *,
    evidence_reliability: float,
) -> float:
    event_count = _float(components.get("detector_event_count"), default=0.0)
    if event_count <= 0.0:
        return round(_clamp01(evidence_reliability), 6)
    posterior = _float(
        components.get("detector_event_posterior"),
        default=evidence_reliability,
    )
    value = 0.45 * evidence_reliability + 0.55 * posterior
    if _float(components.get("matching"), default=1.0) < 0.5:
        value = min(value, evidence_reliability)
    elif _float(components.get("current_evidence"), default=1.0) < 0.5:
        value = min(value, evidence_reliability)
    return round(_clamp01(value), 6)


def _expected_memory_first_action_count(
    memory_action_count: int,
    fallback_from_memory_action_count: int,
    reliability: float,
) -> float:
    return round(
        float(memory_action_count)
        + (1.0 - _clamp01(reliability)) * float(fallback_from_memory_action_count),
        6,
    )


def _memory_first_decision(
    memory_action_count: int,
    fallback_from_memory_action_count: int,
    fallback_action_count: int,
    reliability: float,
) -> str:
    expected_memory = _expected_memory_first_action_count(
        memory_action_count,
        fallback_from_memory_action_count,
        reliability,
    )
    if expected_memory <= float(fallback_action_count):
        return "memory_first"
    return "frontier_first"


def _decision_boundary_reliability_raw(
    memory_action_count: int,
    fallback_from_memory_action_count: int,
    fallback_action_count: int,
) -> float | None:
    if fallback_from_memory_action_count <= 0:
        return None
    return 1.0 - (
        float(fallback_action_count) - float(memory_action_count)
    ) / float(fallback_from_memory_action_count)


def _decision_boundary_region(boundary: float | None) -> str:
    if boundary is None:
        return "no_post_memory_fallback"
    if boundary <= 0.0:
        return "memory_always_no_worse"
    if boundary >= 1.0:
        return "frontier_requires_perfect_memory"
    return "reliability_sensitive"


def _boundary_reliability_interval_gap(
    boundary: float | None,
    reliability_interval_min: float,
    reliability_interval_max: float,
) -> float | None:
    if boundary is None:
        return None
    if boundary < reliability_interval_min:
        return round(float(reliability_interval_min) - float(boundary), 6)
    if boundary > reliability_interval_max:
        return round(float(boundary) - float(reliability_interval_max), 6)
    return 0.0


def _boundary_reliability_interval_position(
    boundary: float | None,
    reliability_interval_min: float,
    reliability_interval_max: float,
) -> str:
    if boundary is None:
        return "no_boundary"
    if boundary < reliability_interval_min:
        return "below_interval"
    if boundary > reliability_interval_max:
        return "above_interval"
    return "inside_interval"


def _sensitivity_reasons(
    *,
    decision_margin: float,
    max_margin_actions: float,
    decision_boundary_region: str,
    boundary_reliability_interval_gap: float | None,
    max_reliability_interval_gap: float,
    detector_event_count: float,
    min_detector_event_count: int,
    confirmed_weight: float,
    suppressed_weight: float,
    reliability_delta: float,
    min_reliability_delta: float,
    counterfactual_flip: bool,
    hindsight_regret: int,
) -> list[str]:
    reasons: list[str] = []
    if counterfactual_flip:
        reasons.append("counterfactual_flip")
    if decision_margin <= float(max_margin_actions):
        reasons.append("close_expected_costs")
    if decision_boundary_region == "reliability_sensitive":
        reasons.append("reliability_sensitive_boundary")
    if (
        boundary_reliability_interval_gap is not None
        and boundary_reliability_interval_gap <= float(max_reliability_interval_gap)
    ):
        reasons.append("near_reliability_interval_boundary")
    if hindsight_regret > 0:
        reasons.append("hindsight_regret")
    if (
        detector_event_count >= float(min_detector_event_count)
        and confirmed_weight > 0.0
        and suppressed_weight > 0.0
    ):
        reasons.append("mixed_detector_events")
    if reliability_delta >= float(min_reliability_delta):
        reasons.append("reliability_delta")
    return reasons


def _sensitivity_score(candidate: dict[str, Any]) -> float:
    margin = float(candidate["decision_margin_actions"])
    event_count = float(candidate["detector_event_count"])
    reliability_delta = float(candidate["reliability_delta"])
    confirmed_weight = float(candidate["detector_event_confirmed_weight"])
    suppressed_weight = float(candidate["detector_event_suppressed_weight"])
    mixed_balance = (
        min(confirmed_weight, suppressed_weight)
        / max(confirmed_weight, suppressed_weight)
        if max(confirmed_weight, suppressed_weight) > 0.0
        else 0.0
    )
    score = 10.0 / (1.0 + margin)
    score += 20.0 * reliability_delta
    score += min(event_count, 20.0) * 0.25
    score += 3.0 * mixed_balance
    if bool(candidate["counterfactual_decision_flip"]):
        score += 100.0
    if candidate["decision_boundary_region"] == "reliability_sensitive":
        score += 50.0
    gap = candidate.get("boundary_reliability_interval_gap")
    if gap is not None:
        score += 60.0 / (1.0 + 20.0 * float(gap))
    if "near_reliability_interval_boundary" in candidate["sensitivity_reasons"]:
        score += 35.0
    score += 2.0 * float(candidate["hindsight_action_regret"])
    return round(score, 6)


def _aggregate_candidates(candidates: Sequence[dict[str, Any]]) -> dict[str, Any]:
    by_reason: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_boundary_region: dict[str, int] = {}
    flip_count = 0
    for candidate in candidates:
        by_category[candidate["category"]] = (
            by_category.get(candidate["category"], 0) + 1
        )
        region = str(candidate.get("decision_boundary_region", "unknown"))
        by_boundary_region[region] = by_boundary_region.get(region, 0) + 1
        if bool(candidate["counterfactual_decision_flip"]):
            flip_count += 1
        for reason in candidate["sensitivity_reasons"]:
            by_reason[reason] = by_reason.get(reason, 0) + 1
    return {
        "counterfactual_flip_count": flip_count,
        "by_reason": dict(sorted(by_reason.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_boundary_region": dict(sorted(by_boundary_region.items())),
    }


def _require_int(row: dict[str, Any], field: str) -> int:
    if field not in row:
        raise KeyError(f"missing {field}")
    return int(row[field])


def _int(value: object, *, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _float(value: object, *, default: float) -> float:
    if value is None:
        return float(default)
    return float(value)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _csv_value(value: object) -> object:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    if isinstance(value, bool):
        return str(value).lower()
    return value
