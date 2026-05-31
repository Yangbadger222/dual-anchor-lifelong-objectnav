from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "official-view-recall-v1"

FEATURE_FIELDS: tuple[str, ...] = (
    "current_target_visible",
    "current_target_match_count",
    "current_detector_confidence",
    "x_m",
    "z_m",
    "heading_rad",
    "distance_to_anchor_m",
    "anchor_bearing_error_rad",
    "expected_evidence",
    "view_quality",
    "path_distance_m",
    "travel_distance_m",
    "active_perception_phase",
    "active_perception_scan_steps_remaining",
    "selected_viewpoint_row",
    "selected_viewpoint_col",
    "selected_frontier_row",
    "selected_frontier_col",
)

LABEL_FIELDS: tuple[str, ...] = (
    "target_visible_next",
    "target_visible_within_horizon",
    "first_target_visible_step_delta",
    "future_target_match_count",
    "best_future_detector_confidence",
)

_CSV_FIELDS: tuple[str, ...] = (
    "source_policy_trace",
    "source_detector_trace",
    "source_run_id",
    "episode_index",
    "episode_id",
    "scene_id",
    "target_category",
    "policy",
    "policy_kind",
    "step_index",
    "action",
    "decision",
) + FEATURE_FIELDS + LABEL_FIELDS


def export_official_view_recall_dataset(
    policy_trace_path: str | Path,
    *,
    detector_trace_path: str | Path,
    source_run_id: str | None = None,
    horizon_steps: int = 5,
) -> dict[str, Any]:
    policy_path = Path(policy_trace_path)
    detector_path = Path(detector_trace_path)
    safe_horizon_steps = max(1, _int(horizon_steps, default=5))
    policy_trace = _load_object(policy_path)
    detector_trace = _load_object(detector_path)
    steps = _policy_steps(policy_trace)
    detector_by_step = _detector_evidence_by_step(detector_trace)
    evidence_by_step = {
        _step_key(step): _merge_policy_debug_evidence(
            step,
            detector_by_step.get(_step_key(step), _empty_evidence()),
        )
        for step in steps
    }
    examples: list[dict[str, Any]] = []
    skipped_horizon_count = 0
    for index, step in enumerate(steps):
        future = _future_context(
            steps,
            index=index,
            evidence_by_step=evidence_by_step,
            horizon_steps=safe_horizon_steps,
        )
        if not future:
            skipped_horizon_count += 1
            continue
        current_evidence = evidence_by_step.get(_step_key(step), _empty_evidence())
        examples.append(
            _view_recall_example(
                step=step,
                current_evidence=current_evidence,
                future=future,
                policy_path=policy_path,
                detector_path=detector_path,
                source_run_id=source_run_id or policy_path.parent.name,
            )
        )
    return {
        "task": "habitat_official_view_recall_dataset",
        "schema_version": SCHEMA_VERSION,
        "source_policy_trace": str(policy_path),
        "source_detector_trace": str(detector_path),
        "source_run_id": source_run_id or policy_path.parent.name,
        "horizon_steps": safe_horizon_steps,
        "step_count": len(steps),
        "example_count": len(examples),
        "skipped_horizon_count": skipped_horizon_count,
        "positive_within_horizon_count": sum(
            1
            for example in examples
            if bool(example["labels"]["target_visible_within_horizon"])
        ),
        "active_perception_example_count": sum(
            1 for example in examples if _is_active_perception_example(example)
        ),
        "feature_schema": list(FEATURE_FIELDS),
        "label_schema": list(LABEL_FIELDS),
        "examples": examples,
    }


def write_official_view_recall_dataset_csv(
    dataset: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    examples = dataset.get("examples", [])
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        if not isinstance(examples, Sequence):
            return
        for example in examples:
            if not isinstance(example, Mapping):
                continue
            row = {field: example.get(field) for field in _CSV_FIELDS}
            features = example.get("features", {})
            labels = example.get("labels", {})
            if isinstance(features, Mapping):
                row.update({field: features.get(field) for field in FEATURE_FIELDS})
            if isinstance(labels, Mapping):
                row.update({field: labels.get(field) for field in LABEL_FIELDS})
            writer.writerow(row)


def _is_active_perception_example(example: Mapping[str, Any]) -> bool:
    features = example.get("features", {})
    if isinstance(features, Mapping) and (
        bool(features.get("active_perception_phase"))
        or features.get("selected_viewpoint_row") is not None
    ):
        return True
    decision = str(example.get("decision", ""))
    return "active_perception" in decision


def _view_recall_example(
    *,
    step: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    future: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    policy_path: Path,
    detector_path: Path,
    source_run_id: str,
) -> dict[str, Any]:
    return {
        "source_policy_trace": str(policy_path),
        "source_detector_trace": str(detector_path),
        "source_run_id": source_run_id,
        "episode_index": _int(step.get("episode_index")),
        "episode_id": str(step.get("episode_id", "")),
        "scene_id": str(step.get("scene_id", "")),
        "target_category": str(step.get("target_category", "")),
        "policy": str(step.get("policy", "")),
        "policy_kind": str(step.get("policy_kind", "")),
        "step_index": _int(step.get("step_index")),
        "action": str(step.get("action", "")),
        "decision": str(step.get("decision", "")),
        "features": _features(step, current_evidence),
        "labels": _labels(step, future),
    }


def _features(
    step: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    memory_prior = step.get("memory_prior", {})
    if not isinstance(memory_prior, Mapping):
        memory_prior = {}
    selected_viewpoint = _optional_cell(memory_prior.get("selected_viewpoint_cell"))
    selected_frontier = _optional_cell(memory_prior.get("selected_frontier_cell"))
    return {
        "current_target_visible": bool(current_evidence.get("target_visible")),
        "current_target_match_count": _int(
            current_evidence.get("target_match_count"), default=0
        ),
        "current_detector_confidence": _optional_float(
            current_evidence.get("detector_confidence")
        ),
        "x_m": _optional_float(step.get("x_m")),
        "z_m": _optional_float(step.get("z_m")),
        "heading_rad": _optional_float(step.get("heading_rad")),
        "distance_to_anchor_m": _optional_float(
            memory_prior.get("distance_to_anchor_m")
        ),
        "anchor_bearing_error_rad": _optional_float(
            memory_prior.get("anchor_bearing_error_rad")
        ),
        "expected_evidence": _optional_float(memory_prior.get("expected_evidence")),
        "view_quality": _optional_float(memory_prior.get("view_quality")),
        "path_distance_m": _optional_float(memory_prior.get("path_distance_m")),
        "travel_distance_m": _optional_float(memory_prior.get("travel_distance_m")),
        "active_perception_phase": str(
            memory_prior.get("active_perception_phase", "")
        ),
        "active_perception_scan_steps_remaining": _optional_float(
            memory_prior.get("active_perception_scan_steps_remaining")
        ),
        "selected_viewpoint_row": selected_viewpoint[0],
        "selected_viewpoint_col": selected_viewpoint[1],
        "selected_frontier_row": selected_frontier[0],
        "selected_frontier_col": selected_frontier[1],
    }


def _labels(
    current: Mapping[str, Any],
    future: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> dict[str, Any]:
    first_visible_delta: int | None = None
    future_match_count = 0
    best_confidence: float | None = None
    for future_step, evidence in future:
        match_count = _int(evidence.get("target_match_count"), default=0)
        future_match_count += match_count
        confidence = _optional_float(evidence.get("detector_confidence"))
        if confidence is not None and (
            best_confidence is None or confidence > best_confidence
        ):
            best_confidence = confidence
        if bool(evidence.get("target_visible")) and first_visible_delta is None:
            first_visible_delta = _int(future_step.get("step_index")) - _int(
                current.get("step_index")
            )
    next_visible = bool(future[0][1].get("target_visible")) if future else False
    return {
        "target_visible_next": next_visible,
        "target_visible_within_horizon": first_visible_delta is not None,
        "first_target_visible_step_delta": first_visible_delta,
        "future_target_match_count": future_match_count,
        "best_future_detector_confidence": best_confidence,
    }


def _future_context(
    steps: Sequence[Mapping[str, Any]],
    *,
    index: int,
    evidence_by_step: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon_steps: int,
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    current = steps[index]
    current_step_index = _int(current.get("step_index"))
    future: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    for candidate in steps[index + 1 : index + 1 + horizon_steps]:
        if _episode_key(candidate) != _episode_key(current):
            break
        expected_step = current_step_index + len(future) + 1
        if _int(candidate.get("step_index")) != expected_step:
            break
        future.append(
            (
                candidate,
                evidence_by_step.get(_step_key(candidate), _empty_evidence()),
            )
        )
    return future


def _detector_evidence_by_step(
    payload: Mapping[str, Any],
) -> dict[tuple[int, int], dict[str, Any]]:
    raw_calls = payload.get("calls", [])
    if not isinstance(raw_calls, list):
        raise ValueError("detector trace calls must be a list")
    evidence: dict[tuple[int, int], dict[str, Any]] = {}
    for call in raw_calls:
        if not isinstance(call, Mapping):
            continue
        key = (_int(call.get("episode_index")), _int(call.get("step_index")))
        primary = _primary_target_evidence(call)
        existing = evidence.get(key)
        if existing is None or float(primary.get("detector_confidence") or -1.0) > float(
            existing.get("detector_confidence") or -1.0
        ):
            evidence[key] = primary
    return evidence


def _primary_target_evidence(call: Mapping[str, Any]) -> dict[str, Any]:
    target_match_count = _int(call.get("target_match_count"), default=0)
    best: Mapping[str, Any] | None = None
    detections = call.get("detections", [])
    if isinstance(detections, list):
        for detection in detections:
            if not isinstance(detection, Mapping):
                continue
            if not bool(detection.get("matches_target")):
                continue
            confidence = _optional_float(detection.get("confidence")) or 0.0
            best_confidence = (
                _optional_float(best.get("confidence")) if best is not None else None
            )
            if best is None or confidence > (best_confidence or 0.0):
                best = detection
    if best is None:
        return _empty_evidence(target_match_count=target_match_count)
    return {
        "target_visible": True,
        "target_match_count": max(1, target_match_count),
        "detector_confidence": _optional_float(best.get("confidence")),
    }


def _merge_policy_debug_evidence(
    step: Mapping[str, Any],
    detector_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = dict(detector_evidence)
    memory_prior = step.get("memory_prior", {})
    if not isinstance(memory_prior, Mapping):
        return evidence
    confidence = _optional_float(memory_prior.get("detector_confidence"))
    if confidence is not None:
        evidence["target_visible"] = True
        evidence["target_match_count"] = max(
            1,
            _int(evidence.get("target_match_count"), default=0),
        )
        evidence["detector_confidence"] = confidence
    return evidence


def _empty_evidence(*, target_match_count: int = 0) -> dict[str, Any]:
    return {
        "target_visible": False,
        "target_match_count": target_match_count,
        "detector_confidence": None,
    }


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def _policy_steps(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_steps = payload.get("steps", [])
    if not isinstance(raw_steps, list):
        raise ValueError("policy trace steps must be a list")
    steps = [dict(step) for step in raw_steps if isinstance(step, Mapping)]
    return sorted(steps, key=lambda step: (_episode_key(step), _int(step.get("step_index"))))


def _episode_key(row: Mapping[str, Any]) -> tuple[int, str]:
    return _int(row.get("episode_index")), str(row.get("episode_id", ""))


def _step_key(row: Mapping[str, Any]) -> tuple[int, int]:
    return _int(row.get("episode_index")), _int(row.get("step_index"))


def _optional_cell(value: Any) -> tuple[int | None, int | None]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None, None
    if len(value) < 2:
        return None, None
    return _optional_int(value[0]), _optional_int(value[1])


def _optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any, *, default: int = 0) -> int:
    maybe_value = _optional_int(value)
    return default if maybe_value is None else maybe_value


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), 12)
    except (TypeError, ValueError):
        return None
