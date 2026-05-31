from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "official-local-action-effect-v2"

FEATURE_FIELDS: tuple[str, ...] = (
    "current_target_visible",
    "current_target_match_count",
    "current_detector_confidence",
    "current_bbox_area_fraction",
    "current_center_offset_fraction",
    "current_abs_center_offset_fraction",
    "current_depth_median",
    "x_m",
    "z_m",
    "heading_rad",
    "suppressed_detector_center_action",
    "suppressed_turn_left",
    "suppressed_turn_right",
    "history_observed_step_count",
    "previous_target_visible",
    "recent_target_visible_count",
    "steps_since_last_target_visible",
    "previous_action",
    "previous_decision",
    "recent_move_forward_count",
    "recent_turn_left_count",
    "recent_turn_right_count",
    "recent_reacquire_count",
    "current_confidence_minus_previous",
    "current_bbox_area_minus_previous",
    "current_depth_minus_previous",
    "current_abs_center_offset_minus_previous",
)

LABEL_FIELDS: tuple[str, ...] = (
    "next_target_visible",
    "next_target_match_count",
    "next_detector_confidence",
    "next_bbox_area_fraction",
    "next_center_offset_fraction",
    "next_abs_center_offset_fraction",
    "next_depth_median",
    "target_retained",
    "target_lost",
    "target_acquired",
    "detector_confidence_delta",
    "bbox_area_fraction_delta",
    "abs_center_offset_fraction_delta",
    "depth_median_delta",
    "translation_delta_m",
    "heading_delta_rad",
    "horizon_observed_step_count",
    "target_visible_within_horizon",
    "target_visible_at_horizon",
    "target_lost_within_horizon",
    "first_target_loss_step_delta",
    "best_future_detector_confidence",
    "best_future_bbox_area_fraction",
    "best_future_abs_center_offset_fraction",
    "best_future_depth_median",
    "best_future_bbox_area_delta",
    "best_future_abs_center_offset_delta",
    "best_future_depth_delta",
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
    "next_step_index",
    "action",
    "decision",
) + FEATURE_FIELDS + LABEL_FIELDS


def export_official_local_action_dataset(
    policy_trace_path: str | Path,
    *,
    detector_trace_path: str | Path,
    source_run_id: str | None = None,
    history_steps: int = 1,
    horizon_steps: int = 1,
) -> dict[str, Any]:
    policy_path = Path(policy_trace_path)
    detector_path = Path(detector_trace_path)
    safe_history_steps = max(1, _int(history_steps, default=1))
    safe_horizon_steps = max(1, _int(horizon_steps, default=1))
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
    skipped_nonconsecutive_count = 0

    for index, (current, next_step) in enumerate(zip(steps, steps[1:])):
        if _episode_key(current) != _episode_key(next_step):
            continue
        if _int(next_step.get("step_index")) != _int(current.get("step_index")) + 1:
            skipped_nonconsecutive_count += 1
            continue
        current_key = _step_key(current)
        next_key = _step_key(next_step)
        current_evidence = evidence_by_step.get(current_key, _empty_evidence())
        next_evidence = evidence_by_step.get(next_key, _empty_evidence())
        examples.append(
            _action_effect_example(
                current=current,
                next_step=next_step,
                current_evidence=current_evidence,
                next_evidence=next_evidence,
                history=_history_context(
                    steps,
                    index=index,
                    evidence_by_step=evidence_by_step,
                    history_steps=safe_history_steps,
                ),
                horizon=_horizon_context(
                    steps,
                    index=index,
                    evidence_by_step=evidence_by_step,
                    horizon_steps=safe_horizon_steps,
                ),
                policy_path=policy_path,
                detector_path=detector_path,
                source_run_id=source_run_id or policy_path.parent.name,
            )
        )

    transition_counts = _transition_counts(examples)
    return {
        "task": "habitat_official_local_action_dataset",
        "schema_version": SCHEMA_VERSION,
        "source_policy_trace": str(policy_path),
        "source_detector_trace": str(detector_path),
        "source_run_id": source_run_id or policy_path.parent.name,
        "history_steps": safe_history_steps,
        "horizon_steps": safe_horizon_steps,
        "step_count": len(steps),
        "example_count": len(examples),
        "skipped_nonconsecutive_count": skipped_nonconsecutive_count,
        "visible_before_count": sum(
            1
            for example in examples
            if bool(example["features"]["current_target_visible"])
        ),
        "visible_after_count": sum(
            1 for example in examples if bool(example["labels"]["next_target_visible"])
        ),
        "transition_counts": transition_counts,
        "feature_schema": list(FEATURE_FIELDS),
        "label_schema": list(LABEL_FIELDS),
        "examples": examples,
    }


def write_official_local_action_dataset_csv(
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
    explicit = call.get("primary_target_evidence")
    if isinstance(explicit, Mapping):
        return {
            **_empty_evidence(),
            "target_visible": target_match_count > 0,
            "target_match_count": target_match_count,
            "detector_confidence": _optional_float(
                explicit.get("detector_confidence")
            ),
            "detector_bbox": _optional_list(explicit.get("detector_bbox")),
            "detector_center_offset_fraction": _optional_float(
                explicit.get("detector_center_offset_fraction")
            ),
            "detector_bbox_area_fraction": _optional_float(
                explicit.get("detector_bbox_area_fraction")
            ),
            "detector_depth_median": _optional_float(
                explicit.get("detector_depth_median")
            ),
        }
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
        **_empty_evidence(),
        "target_visible": True,
        "target_match_count": max(1, target_match_count),
        "detector_confidence": _optional_float(best.get("confidence")),
        "detector_bbox": _optional_list(best.get("bbox")),
        "detector_center_offset_fraction": None,
        "detector_bbox_area_fraction": None,
        "detector_depth_median": None,
    }


def _empty_evidence(*, target_match_count: int = 0) -> dict[str, Any]:
    return {
        "target_visible": False,
        "target_match_count": target_match_count,
        "detector_confidence": None,
        "detector_bbox": None,
        "detector_center_offset_fraction": None,
        "detector_bbox_area_fraction": None,
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
    center_offset = _optional_float(
        memory_prior.get("detector_center_offset_fraction")
    )
    area = _optional_float(memory_prior.get("detector_bbox_area_fraction"))
    depth = _optional_float(memory_prior.get("detector_depth_median"))
    bbox = _optional_list(memory_prior.get("detector_bbox"))
    if confidence is not None:
        evidence["detector_confidence"] = confidence
        evidence["target_visible"] = True
        evidence["target_match_count"] = max(
            1, _int(evidence.get("target_match_count"), default=0)
        )
    if center_offset is not None:
        evidence["detector_center_offset_fraction"] = center_offset
    if area is not None:
        evidence["detector_bbox_area_fraction"] = area
    if depth is not None:
        evidence["detector_depth_median"] = depth
    if bbox is not None:
        evidence["detector_bbox"] = bbox
    return evidence


def _action_effect_example(
    *,
    current: Mapping[str, Any],
    next_step: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    next_evidence: Mapping[str, Any],
    history: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    horizon: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    policy_path: Path,
    detector_path: Path,
    source_run_id: str,
) -> dict[str, Any]:
    current_visible = bool(current_evidence.get("target_visible"))
    next_visible = bool(next_evidence.get("target_visible"))
    return {
        "source_policy_trace": str(policy_path),
        "source_detector_trace": str(detector_path),
        "source_run_id": source_run_id,
        "episode_index": _int(current.get("episode_index")),
        "episode_id": str(current.get("episode_id", "")),
        "scene_id": str(current.get("scene_id", "")),
        "target_category": str(current.get("target_category", "")),
        "policy": str(current.get("policy", "")),
        "policy_kind": str(current.get("policy_kind", "")),
        "step_index": _int(current.get("step_index")),
        "next_step_index": _int(next_step.get("step_index")),
        "action": str(current.get("action", "")),
        "decision": str(current.get("decision", "")),
        "features": _features(current, current_evidence, history=history),
        "labels": _labels(
            current=current,
            next_step=next_step,
            current_evidence=current_evidence,
            next_evidence=next_evidence,
            current_visible=current_visible,
            next_visible=next_visible,
            horizon=horizon,
        ),
    }


def _features(
    current: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    *,
    history: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]] = (),
) -> dict[str, Any]:
    center_offset = _optional_float(
        current_evidence.get("detector_center_offset_fraction")
    )
    memory_prior = current.get("memory_prior", {})
    if not isinstance(memory_prior, Mapping):
        memory_prior = {}
    previous_step, previous_evidence = history[-1] if history else ({}, {})
    previous_offset = _optional_float(
        previous_evidence.get("detector_center_offset_fraction")
    )
    current_abs_offset = abs(center_offset) if center_offset is not None else None
    previous_abs_offset = (
        abs(previous_offset) if previous_offset is not None else None
    )
    current_visible = bool(current_evidence.get("target_visible"))
    suppressed_actions = _suppressed_detector_center_actions(memory_prior)
    return {
        "current_target_visible": current_visible,
        "current_target_match_count": _int(
            current_evidence.get("target_match_count"), default=0
        ),
        "current_detector_confidence": _optional_float(
            current_evidence.get("detector_confidence")
        ),
        "current_bbox_area_fraction": _optional_float(
            current_evidence.get("detector_bbox_area_fraction")
        ),
        "current_center_offset_fraction": center_offset,
        "current_abs_center_offset_fraction": (
            abs(center_offset) if center_offset is not None else None
        ),
        "current_depth_median": _optional_float(
            current_evidence.get("detector_depth_median")
        ),
        "x_m": _optional_float(current.get("x_m")),
        "z_m": _optional_float(current.get("z_m")),
        "heading_rad": _optional_float(current.get("heading_rad")),
        "suppressed_detector_center_action": str(
            memory_prior.get("suppressed_detector_center_action", "")
        ),
        "suppressed_turn_left": "turn_left" in suppressed_actions,
        "suppressed_turn_right": "turn_right" in suppressed_actions,
        "history_observed_step_count": len(history),
        "previous_target_visible": bool(previous_evidence.get("target_visible")),
        "recent_target_visible_count": sum(
            1 for _, evidence in history if bool(evidence.get("target_visible"))
        )
        + (1 if current_visible else 0),
        "steps_since_last_target_visible": _steps_since_last_target_visible(
            current,
            current_visible=current_visible,
            history=history,
        ),
        "previous_action": str(previous_step.get("action", "")),
        "previous_decision": str(previous_step.get("decision", "")),
        "recent_move_forward_count": _recent_action_count(history, "move_forward"),
        "recent_turn_left_count": _recent_action_count(history, "turn_left"),
        "recent_turn_right_count": _recent_action_count(history, "turn_right"),
        "recent_reacquire_count": sum(
            1
            for step, _ in history
            if str(step.get("decision", "")) == "reacquire_detector_target"
        ),
        "current_confidence_minus_previous": _delta(
            _optional_float(current_evidence.get("detector_confidence")),
            _optional_float(previous_evidence.get("detector_confidence")),
        ),
        "current_bbox_area_minus_previous": _delta(
            _optional_float(current_evidence.get("detector_bbox_area_fraction")),
            _optional_float(previous_evidence.get("detector_bbox_area_fraction")),
        ),
        "current_depth_minus_previous": _delta(
            _optional_float(current_evidence.get("detector_depth_median")),
            _optional_float(previous_evidence.get("detector_depth_median")),
        ),
        "current_abs_center_offset_minus_previous": _delta(
            current_abs_offset,
            previous_abs_offset,
        ),
    }


def _labels(
    *,
    current: Mapping[str, Any],
    next_step: Mapping[str, Any],
    current_evidence: Mapping[str, Any],
    next_evidence: Mapping[str, Any],
    current_visible: bool,
    next_visible: bool,
    horizon: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]] = (),
) -> dict[str, Any]:
    current_confidence = _optional_float(current_evidence.get("detector_confidence"))
    next_confidence = _optional_float(next_evidence.get("detector_confidence"))
    current_area = _optional_float(current_evidence.get("detector_bbox_area_fraction"))
    next_area = _optional_float(next_evidence.get("detector_bbox_area_fraction"))
    current_depth = _optional_float(current_evidence.get("detector_depth_median"))
    next_depth = _optional_float(next_evidence.get("detector_depth_median"))
    current_offset = _optional_float(
        current_evidence.get("detector_center_offset_fraction")
    )
    next_offset = _optional_float(next_evidence.get("detector_center_offset_fraction"))
    current_abs_offset = abs(current_offset) if current_offset is not None else None
    next_abs_offset = abs(next_offset) if next_offset is not None else None
    horizon_labels = _horizon_labels(
        current=current,
        current_visible=current_visible,
        current_confidence=current_confidence,
        current_area=current_area,
        current_abs_offset=current_abs_offset,
        current_depth=current_depth,
        horizon=horizon,
    )
    return {
        "next_target_visible": next_visible,
        "next_target_match_count": _int(
            next_evidence.get("target_match_count"), default=0
        ),
        "next_detector_confidence": next_confidence,
        "next_bbox_area_fraction": next_area,
        "next_center_offset_fraction": next_offset,
        "next_abs_center_offset_fraction": next_abs_offset,
        "next_depth_median": next_depth,
        "target_retained": current_visible and next_visible,
        "target_lost": current_visible and not next_visible,
        "target_acquired": (not current_visible) and next_visible,
        "detector_confidence_delta": _delta(next_confidence, current_confidence),
        "bbox_area_fraction_delta": _delta(next_area, current_area),
        "abs_center_offset_fraction_delta": _delta(next_abs_offset, current_abs_offset),
        "depth_median_delta": _delta(next_depth, current_depth),
        "translation_delta_m": _translation_delta_m(current, next_step),
        "heading_delta_rad": _angle_delta_rad(current, next_step),
        **horizon_labels,
    }


def _history_context(
    steps: Sequence[Mapping[str, Any]],
    *,
    index: int,
    evidence_by_step: Mapping[tuple[int, int], Mapping[str, Any]],
    history_steps: int,
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    current = steps[index]
    current_step_index = _int(current.get("step_index"))
    history: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    expected_step_index = current_step_index - 1
    for step in reversed(steps[:index]):
        if _episode_key(step) != _episode_key(current):
            break
        step_index = _int(step.get("step_index"))
        if step_index != expected_step_index:
            break
        history.insert(0, (step, evidence_by_step.get(_step_key(step), _empty_evidence())))
        if len(history) >= history_steps:
            break
        expected_step_index -= 1
    return history


def _horizon_context(
    steps: Sequence[Mapping[str, Any]],
    *,
    index: int,
    evidence_by_step: Mapping[tuple[int, int], Mapping[str, Any]],
    horizon_steps: int,
) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    current = steps[index]
    current_step_index = _int(current.get("step_index"))
    horizon: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    expected_step_index = current_step_index + 1
    for step in steps[index + 1 :]:
        if _episode_key(step) != _episode_key(current):
            break
        step_index = _int(step.get("step_index"))
        if step_index != expected_step_index:
            break
        horizon.append((step, evidence_by_step.get(_step_key(step), _empty_evidence())))
        if len(horizon) >= horizon_steps:
            break
        expected_step_index += 1
    return horizon


def _horizon_labels(
    *,
    current: Mapping[str, Any],
    current_visible: bool,
    current_confidence: float | None,
    current_area: float | None,
    current_abs_offset: float | None,
    current_depth: float | None,
    horizon: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> dict[str, Any]:
    visible_future = [
        (step, evidence)
        for step, evidence in horizon
        if bool(evidence.get("target_visible"))
    ]
    best_step: Mapping[str, Any] | None = None
    best_evidence: Mapping[str, Any] | None = None
    if visible_future:
        best_step, best_evidence = max(
            visible_future,
            key=lambda item: _optional_float(
                item[1].get("detector_confidence")
            )
            or -1.0,
        )
    del best_step
    best_confidence = (
        _optional_float(best_evidence.get("detector_confidence"))
        if best_evidence is not None
        else None
    )
    best_area = (
        _optional_float(best_evidence.get("detector_bbox_area_fraction"))
        if best_evidence is not None
        else None
    )
    best_offset = (
        _optional_float(best_evidence.get("detector_center_offset_fraction"))
        if best_evidence is not None
        else None
    )
    best_abs_offset = abs(best_offset) if best_offset is not None else None
    best_depth = (
        _optional_float(best_evidence.get("detector_depth_median"))
        if best_evidence is not None
        else None
    )
    first_loss_delta = None
    if current_visible:
        for step, evidence in horizon:
            if not bool(evidence.get("target_visible")):
                first_loss_delta = _int(step.get("step_index")) - _int(
                    current.get("step_index")
                )
                break
    return {
        "horizon_observed_step_count": len(horizon),
        "target_visible_within_horizon": bool(visible_future),
        "target_visible_at_horizon": bool(
            horizon[-1][1].get("target_visible")
        )
        if horizon
        else False,
        "target_lost_within_horizon": first_loss_delta is not None,
        "first_target_loss_step_delta": first_loss_delta,
        "best_future_detector_confidence": best_confidence,
        "best_future_bbox_area_fraction": best_area,
        "best_future_abs_center_offset_fraction": best_abs_offset,
        "best_future_depth_median": best_depth,
        "best_future_bbox_area_delta": _delta(best_area, current_area),
        "best_future_abs_center_offset_delta": _delta(
            best_abs_offset,
            current_abs_offset,
        ),
        "best_future_depth_delta": _delta(best_depth, current_depth),
    }


def _transition_counts(examples: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"acquired": 0, "lost": 0, "remained_absent": 0, "retained": 0}
    for example in examples:
        labels = example.get("labels", {})
        features = example.get("features", {})
        if not isinstance(labels, Mapping) or not isinstance(features, Mapping):
            continue
        before = bool(features.get("current_target_visible"))
        after = bool(labels.get("next_target_visible"))
        if before and after:
            counts["retained"] += 1
        elif before and not after:
            counts["lost"] += 1
        elif not before and after:
            counts["acquired"] += 1
        else:
            counts["remained_absent"] += 1
    return counts


def _suppressed_detector_center_actions(memory_prior: Mapping[str, Any]) -> set[str]:
    actions: set[str] = set()
    plural = memory_prior.get("suppressed_detector_center_actions")
    if isinstance(plural, list):
        actions.update(str(action) for action in plural if str(action))
    singular = str(memory_prior.get("suppressed_detector_center_action", ""))
    if singular:
        actions.add(singular)
    return actions


def _steps_since_last_target_visible(
    current: Mapping[str, Any],
    *,
    current_visible: bool,
    history: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> int | None:
    if current_visible:
        return 0
    current_step_index = _int(current.get("step_index"))
    for step, evidence in reversed(history):
        if bool(evidence.get("target_visible")):
            return current_step_index - _int(step.get("step_index"))
    return None


def _recent_action_count(
    history: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
    action: str,
) -> int:
    return sum(1 for step, _ in history if str(step.get("action", "")) == action)


def _translation_delta_m(
    current: Mapping[str, Any],
    next_step: Mapping[str, Any],
) -> float | None:
    x0 = _optional_float(current.get("x_m"))
    z0 = _optional_float(current.get("z_m"))
    x1 = _optional_float(next_step.get("x_m"))
    z1 = _optional_float(next_step.get("z_m"))
    if x0 is None or z0 is None or x1 is None or z1 is None:
        return None
    return round(((x1 - x0) ** 2 + (z1 - z0) ** 2) ** 0.5, 12)


def _angle_delta_rad(
    current: Mapping[str, Any],
    next_step: Mapping[str, Any],
) -> float | None:
    h0 = _optional_float(current.get("heading_rad"))
    h1 = _optional_float(next_step.get("heading_rad"))
    if h0 is None or h1 is None:
        return None
    return round(h1 - h0, 12)


def _delta(next_value: float | None, current_value: float | None) -> float | None:
    if next_value is None or current_value is None:
        return None
    return round(next_value - current_value, 12)


def _step_key(step: Mapping[str, Any]) -> tuple[int, int]:
    return (_int(step.get("episode_index")), _int(step.get("step_index")))


def _episode_key(step: Mapping[str, Any]) -> tuple[int, str]:
    return (_int(step.get("episode_index")), str(step.get("episode_id", "")))


def _int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _optional_list(value: object) -> list[Any] | None:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return None
