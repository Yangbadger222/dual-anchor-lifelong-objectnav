from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "official-view-candidate-recall-v1"

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
    "candidate_rank",
    "candidate_count",
    "candidate_score",
    "expected_evidence",
    "belief_mass",
    "distance_to_anchor_m",
    "bearing_rad",
    "bearing_error_rad",
    "view_quality",
    "view_bearing_quality",
    "view_distance_quality",
    "path_distance_m",
    "travel_distance_m",
    "viewpoint_row",
    "viewpoint_col",
    "frontier_row",
    "frontier_col",
    "is_selected_candidate",
    "state_target_visible_within_horizon",
    "state_hidden_to_visible_within_horizon",
    "observed_candidate_label_available",
    "observed_candidate_hidden_to_visible_within_horizon",
)


def export_official_view_candidate_dataset(
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
    evidence_by_step = _detector_evidence_by_step(detector_trace)
    candidates: list[dict[str, Any]] = []
    skipped_horizon_count = 0
    state_count = 0
    for index, step in enumerate(steps):
        memory_prior = step.get("memory_prior", {})
        if not isinstance(memory_prior, Mapping):
            continue
        top_candidates = memory_prior.get("top_candidates", [])
        if not isinstance(top_candidates, list) or not top_candidates:
            continue
        future = _future_context(
            steps,
            index=index,
            evidence_by_step=evidence_by_step,
            horizon_steps=safe_horizon_steps,
        )
        if not future:
            skipped_horizon_count += 1
            continue
        state_count += 1
        state_labels = _state_labels(
            current_evidence=evidence_by_step.get(_step_key(step), _empty_evidence()),
            future=future,
        )
        for candidate_rank, candidate in enumerate(top_candidates):
            if not isinstance(candidate, Mapping):
                continue
            is_selected = _candidate_matches_selection(candidate, memory_prior)
            candidates.append(
                _candidate_row(
                    step=step,
                    candidate=candidate,
                    candidate_rank=candidate_rank,
                    candidate_count=len(top_candidates),
                    is_selected=is_selected,
                    state_labels=state_labels,
                    policy_path=policy_path,
                    detector_path=detector_path,
                    source_run_id=source_run_id or policy_path.parent.name,
                )
            )
    return {
        "task": "habitat_official_view_candidate_dataset",
        "schema_version": SCHEMA_VERSION,
        "source_policy_trace": str(policy_path),
        "source_detector_trace": str(detector_path),
        "source_run_id": source_run_id or policy_path.parent.name,
        "horizon_steps": safe_horizon_steps,
        "state_count": state_count,
        "candidate_count": len(candidates),
        "selected_candidate_count": sum(
            1 for candidate in candidates if candidate["is_selected_candidate"]
        ),
        "observed_positive_candidate_count": sum(
            1
            for candidate in candidates
            if candidate["labels"]["observed_candidate_hidden_to_visible_within_horizon"]
            is True
        ),
        "unobserved_candidate_count": sum(
            1
            for candidate in candidates
            if not candidate["labels"]["observed_candidate_label_available"]
        ),
        "skipped_horizon_count": skipped_horizon_count,
        "candidates": candidates,
    }


def write_official_view_candidate_dataset_csv(
    dataset: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = dataset.get("candidates", [])
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        if not isinstance(rows, Sequence):
            return
        for candidate in rows:
            if not isinstance(candidate, Mapping):
                continue
            labels = candidate.get("labels", {})
            if not isinstance(labels, Mapping):
                labels = {}
            row = {field: candidate.get(field) for field in _CSV_FIELDS}
            for field in (
                "state_target_visible_within_horizon",
                "state_hidden_to_visible_within_horizon",
                "observed_candidate_label_available",
                "observed_candidate_hidden_to_visible_within_horizon",
            ):
                row[field] = labels.get(field)
            writer.writerow({field: _csv_value(row.get(field)) for field in _CSV_FIELDS})


def _candidate_row(
    *,
    step: Mapping[str, Any],
    candidate: Mapping[str, Any],
    candidate_rank: int,
    candidate_count: int,
    is_selected: bool,
    state_labels: Mapping[str, bool],
    policy_path: Path,
    detector_path: Path,
    source_run_id: str,
) -> dict[str, Any]:
    viewpoint = _optional_cell(candidate.get("viewpoint_cell"))
    frontier = _optional_cell(candidate.get("frontier_cell"))
    observed_label = (
        bool(state_labels["state_hidden_to_visible_within_horizon"])
        if is_selected
        else None
    )
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
        "candidate_rank": int(candidate_rank),
        "candidate_count": int(candidate_count),
        "candidate_score": _optional_float(candidate.get("score")),
        "expected_evidence": _optional_float(candidate.get("expected_evidence")),
        "belief_mass": _optional_float(candidate.get("belief_mass")),
        "distance_to_anchor_m": _optional_float(candidate.get("distance_to_anchor_m")),
        "bearing_rad": _optional_float(candidate.get("bearing_rad")),
        "bearing_error_rad": _optional_float(candidate.get("bearing_error_rad")),
        "view_quality": _optional_float(candidate.get("view_quality")),
        "view_bearing_quality": _optional_float(candidate.get("view_bearing_quality")),
        "view_distance_quality": _optional_float(candidate.get("view_distance_quality")),
        "path_distance_m": _optional_float(candidate.get("path_distance_m")),
        "travel_distance_m": _optional_float(candidate.get("travel_distance_m")),
        "viewpoint_row": viewpoint[0],
        "viewpoint_col": viewpoint[1],
        "frontier_row": frontier[0],
        "frontier_col": frontier[1],
        "is_selected_candidate": bool(is_selected),
        "labels": {
            "state_target_visible_within_horizon": bool(
                state_labels["state_target_visible_within_horizon"]
            ),
            "state_hidden_to_visible_within_horizon": bool(
                state_labels["state_hidden_to_visible_within_horizon"]
            ),
            "observed_candidate_label_available": bool(is_selected),
            "observed_candidate_hidden_to_visible_within_horizon": observed_label,
        },
    }


def _state_labels(
    *,
    current_evidence: Mapping[str, Any],
    future: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> dict[str, bool]:
    current_visible = bool(current_evidence.get("target_visible"))
    future_visible = any(bool(evidence.get("target_visible")) for _, evidence in future)
    return {
        "state_target_visible_within_horizon": future_visible,
        "state_hidden_to_visible_within_horizon": (
            not current_visible and future_visible
        ),
    }


def _candidate_matches_selection(
    candidate: Mapping[str, Any],
    memory_prior: Mapping[str, Any],
) -> bool:
    selected_viewpoint = _optional_cell(memory_prior.get("selected_viewpoint_cell"))
    selected_frontier = _optional_cell(memory_prior.get("selected_frontier_cell"))
    candidate_viewpoint = _optional_cell(candidate.get("viewpoint_cell"))
    candidate_frontier = _optional_cell(candidate.get("frontier_cell"))
    if selected_viewpoint != (None, None) and candidate_viewpoint != selected_viewpoint:
        return False
    if selected_frontier != (None, None) and candidate_frontier != selected_frontier:
        return False
    return selected_viewpoint != (None, None) or selected_frontier != (None, None)


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


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value
