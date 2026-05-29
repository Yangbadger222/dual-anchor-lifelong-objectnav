from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Sequence


DEFAULT_POLICIES: tuple[str, ...] = ("memory_guided",)

FEATURE_FIELDS: tuple[str, ...] = (
    "memory_action_count",
    "fallback_action_count",
    "fallback_from_memory_action_count",
    "memory_valid_prior",
    "relocation_pair_distance_m",
    "memory_evidence_detector_pixels",
    "memory_evidence_overlap_pixels",
    "memory_evidence_detector_precision",
    "memory_evidence_oracle_recall",
    "memory_reliability_base_prior",
    "memory_reliability_current_evidence",
    "memory_reliability_matching",
    "memory_reliability_transform_covariance",
    "memory_reliability_recency",
    "memory_detector_event_count",
    "memory_detector_event_confirmed_weight",
    "memory_detector_event_suppressed_weight",
    "memory_detector_event_posterior",
)

_CSV_FIELDS: tuple[str, ...] = (
    "source_summary",
    "run_id",
    "group_id",
    "category",
    "policy",
    "challenge",
    "detector",
    "query_repeat_index",
    "memory_instance_id",
    "target_instance_id",
    "label_memory_valid",
    "aux_memory_decision",
    "aux_memory_decision_bucket",
    "aux_hindsight_best_candidate_type",
) + FEATURE_FIELDS


def export_habitat_memory_validity_dataset(
    inputs: Sequence[str | Path],
    *,
    policies: Sequence[str] = DEFAULT_POLICIES,
) -> dict[str, Any]:
    policy_filter = {str(policy) for policy in policies}
    summary_paths = _resolve_summary_paths(inputs)
    examples: list[dict[str, Any]] = []
    row_count = 0
    skipped_count = 0
    warnings: list[str] = []
    for summary_path in summary_paths:
        try:
            summary = _load_summary(summary_path)
        except (OSError, json.JSONDecodeError) as exc:
            skipped_count += 1
            warnings.append(f"{summary_path}: {exc}")
            continue
        rows = summary.get("rows", [])
        if not isinstance(rows, list):
            skipped_count += 1
            warnings.append(f"{summary_path}: rows is not a list")
            continue
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                skipped_count += 1
                warnings.append(f"{summary_path}: row {row_index} is not an object")
                continue
            if policy_filter and str(row.get("policy", "")) not in policy_filter:
                continue
            row_count += 1
            example = _example_from_row(
                summary=summary,
                summary_path=summary_path,
                row=row,
            )
            if example is None:
                skipped_count += 1
                warnings.append(
                    f"{summary_path}: row {row_index}: missing memory_evidence label"
                )
                continue
            examples.append(example)

    valid_count = sum(int(example["label_memory_valid"]) for example in examples)
    invalid_count = len(examples) - valid_count
    return {
        "task": "habitat_memory_validity_dataset",
        "summary_count": len(summary_paths),
        "row_count": row_count,
        "example_count": len(examples),
        "skipped_count": skipped_count,
        "label_counts": {"invalid": invalid_count, "valid": valid_count},
        "policies": sorted(policy_filter),
        "feature_schema": list(FEATURE_FIELDS),
        "warnings": warnings,
        "examples": examples,
    }


def write_memory_validity_dataset_csv(
    path: str | Path,
    examples: Sequence[dict[str, Any]],
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for example in examples:
            row = {field: example.get(field) for field in _CSV_FIELDS}
            features = example.get("features", {})
            if isinstance(features, dict):
                row.update({field: features.get(field) for field in FEATURE_FIELDS})
            writer.writerow(row)


def _example_from_row(
    *,
    summary: dict[str, Any],
    summary_path: Path,
    row: dict[str, Any],
) -> dict[str, Any] | None:
    memory_evidence = row.get("memory_evidence")
    if not isinstance(memory_evidence, dict):
        return None
    if "shared_gate_success" not in memory_evidence:
        return None
    label = bool(memory_evidence.get("shared_gate_success"))
    return {
        "source_summary": str(summary_path),
        "run_id": summary_path.parent.name,
        "group_id": str(row.get("group_id", "")),
        "category": str(row.get("category", "")),
        "policy": str(row.get("policy", "")),
        "challenge": str(summary.get("challenge", "")),
        "detector": str(summary.get("detector", "")),
        "frontier_mode": str(summary.get("frontier_mode", "")),
        "route_observation_mode": str(summary.get("route_observation_mode", "")),
        "query_repeat_index": _int(row.get("query_repeat_index"), default=0),
        "memory_instance_id": _optional_str(row.get("memory_instance_id")),
        "target_instance_id": _optional_str(row.get("target_instance_id")),
        "label_memory_valid": label,
        "aux_memory_decision": str(row.get("memory_decision", "")),
        "aux_memory_decision_bucket": str(row.get("memory_decision_bucket", "")),
        "aux_hindsight_best_candidate_type": str(
            row.get("hindsight_best_candidate_type", "")
        ),
        "features": _features_from_row(row=row, memory_evidence=memory_evidence),
    }


def _features_from_row(
    *,
    row: dict[str, Any],
    memory_evidence: dict[str, Any],
) -> dict[str, float | None]:
    components = _memory_reliability_components(row.get("memory_reliability"))
    return {
        "memory_action_count": _optional_float(row.get("memory_action_count")),
        "fallback_action_count": _optional_float(row.get("fallback_action_count")),
        "fallback_from_memory_action_count": _optional_float(
            row.get("fallback_from_memory_action_count")
        ),
        "memory_valid_prior": _optional_float(row.get("memory_valid_prior")),
        "relocation_pair_distance_m": _optional_float(
            row.get("relocation_pair_distance_m")
        ),
        "memory_evidence_detector_pixels": _optional_float(
            memory_evidence.get("detector_pixels")
        ),
        "memory_evidence_overlap_pixels": _optional_float(
            memory_evidence.get("overlap_pixels")
        ),
        "memory_evidence_detector_precision": _optional_float(
            memory_evidence.get("detector_precision")
        ),
        "memory_evidence_oracle_recall": _optional_float(
            memory_evidence.get("oracle_recall")
        ),
        "memory_reliability_base_prior": _optional_float(
            components.get("base_prior")
        ),
        "memory_reliability_current_evidence": _optional_float(
            components.get("current_evidence")
        ),
        "memory_reliability_matching": _optional_float(components.get("matching")),
        "memory_reliability_transform_covariance": _optional_float(
            components.get("transform_covariance")
        ),
        "memory_reliability_recency": _optional_float(components.get("recency")),
        "memory_detector_event_count": _optional_float(
            components.get("detector_event_count")
        ),
        "memory_detector_event_confirmed_weight": _optional_float(
            components.get("detector_event_confirmed_weight")
        ),
        "memory_detector_event_suppressed_weight": _optional_float(
            components.get("detector_event_suppressed_weight")
        ),
        "memory_detector_event_posterior": _optional_float(
            components.get("detector_event_posterior")
        ),
    }


def _memory_reliability_components(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    components = payload.get("components", {})
    if not isinstance(components, dict):
        return {}
    return {str(key): value for key, value in components.items()}


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


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return round(_float(value, default=0.0), 6)


def _float(value: object, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int(value: object, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
