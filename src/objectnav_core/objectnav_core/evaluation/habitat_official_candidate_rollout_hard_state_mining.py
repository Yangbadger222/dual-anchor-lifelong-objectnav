from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


_CSV_BASE_FIELDS = (
    "source_family",
    "source_dataset",
    "source_policy_trace",
    "state_index",
    "episode_index",
    "episode_id",
    "scene_id",
    "target_category",
    "step_index",
    "state_action",
    "state_decision",
    "hard_state_reason",
    "baseline_action",
    "baseline_success",
    "baseline_in_fastest_actions",
    "baseline_strict_fastest",
    "baseline_time_to_visible_steps",
    "best_time_to_visible_steps",
    "baseline_time_regret_steps",
    "positive_action_count",
    "positive_actions",
    "fastest_actions",
    "strict_fastest_action",
    "oracle_recovered",
    "state_features_json",
)


def mine_official_candidate_rollout_hard_states(
    report: Mapping[str, Any],
    *,
    baseline_action: str = "turn_left",
    include_baseline_ties: bool = False,
) -> dict[str, Any]:
    """Extract action-matrix states where the baseline action is not fastest."""

    if report.get("task") != "habitat_official_candidate_rollout_action_matrix_report":
        raise ValueError("expected a candidate rollout action-matrix report")
    raw_states = report.get("states", [])
    if not isinstance(raw_states, Sequence) or isinstance(raw_states, (str, bytes)):
        raise ValueError("action-matrix report states must be a list")

    safe_baseline_action = str(baseline_action or "").strip()
    if not safe_baseline_action:
        raise ValueError("baseline_action is required")
    report_actions = _string_list(report.get("actions"))
    if safe_baseline_action not in report_actions:
        report_actions = [*report_actions, safe_baseline_action]

    states: list[dict[str, Any]] = []
    input_state_count = 0
    skipped_no_fastest_count = 0
    skipped_baseline_fastest_count = 0
    for raw_state in raw_states:
        if not isinstance(raw_state, Mapping):
            continue
        input_state_count += 1
        fastest_actions = _string_list(raw_state.get("fastest_actions"))
        if not fastest_actions:
            skipped_no_fastest_count += 1
            continue

        strict_fastest_action = _optional_string(raw_state.get("strict_fastest_action"))
        baseline_in_fastest = safe_baseline_action in fastest_actions
        baseline_strict_fastest = strict_fastest_action == safe_baseline_action
        if not baseline_in_fastest:
            hard_state_reason = "baseline_not_fastest"
        elif include_baseline_ties and not baseline_strict_fastest:
            hard_state_reason = "baseline_tied_fastest"
        else:
            skipped_baseline_fastest_count += 1
            continue

        states.append(
            _hard_state_row(
                raw_state,
                actions=report_actions,
                baseline_action=safe_baseline_action,
                fastest_actions=fastest_actions,
                hard_state_reason=hard_state_reason,
            )
        )

    aggregate = _aggregate_hard_states(states)
    return {
        "task": "habitat_official_candidate_rollout_hard_state_mining",
        "source_task": report.get("task"),
        "baseline_action": safe_baseline_action,
        "include_baseline_ties": bool(include_baseline_ties),
        "actions": report_actions,
        "input_state_count": input_state_count,
        "hard_state_count": len(states),
        "skipped_no_fastest_count": skipped_no_fastest_count,
        "skipped_baseline_fastest_count": skipped_baseline_fastest_count,
        "aggregate": aggregate,
        "states": states,
    }


def write_official_candidate_rollout_hard_states_csv(
    report: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    actions = _string_list(report.get("actions"))
    action_fields = [
        field
        for action in actions
        for field in (f"{action}_success", f"{action}_time_to_visible_steps")
    ]
    fieldnames = (*_CSV_BASE_FIELDS, *action_fields)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        states = report.get("states", [])
        if not isinstance(states, Sequence) or isinstance(states, (str, bytes)):
            return
        for state in states:
            if not isinstance(state, Mapping):
                continue
            row = {field: state.get(field) for field in _CSV_BASE_FIELDS}
            row["positive_actions"] = _string_list(state.get("positive_actions"))
            row["fastest_actions"] = _string_list(state.get("fastest_actions"))
            row["state_features_json"] = json.dumps(
                dict(_mapping(state.get("state_features"))),
                ensure_ascii=False,
                sort_keys=True,
            )
            action_payloads = _mapping(state.get("actions"))
            for action in actions:
                payload = _mapping(action_payloads.get(action))
                row[f"{action}_success"] = payload.get("success")
                row[f"{action}_time_to_visible_steps"] = payload.get(
                    "time_to_visible_steps"
                )
            writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})


def _hard_state_row(
    state: Mapping[str, Any],
    *,
    actions: Sequence[str],
    baseline_action: str,
    fastest_actions: Sequence[str],
    hard_state_reason: str,
) -> dict[str, Any]:
    action_payloads = _mapping(state.get("actions"))
    baseline_payload = _mapping(action_payloads.get(baseline_action))
    baseline_time = _optional_int(baseline_payload.get("time_to_visible_steps"))
    best_time = _best_time_to_visible(action_payloads, fastest_actions)
    if baseline_time is None or best_time is None:
        baseline_regret = None
    else:
        baseline_regret = baseline_time - best_time

    source_family = _source_family(state)
    return {
        "source_family": source_family,
        "source_dataset": str(state.get("source_dataset", "")),
        "source_dataset_index": _optional_int(state.get("source_dataset_index")),
        "source_policy_trace": str(state.get("source_policy_trace", "")),
        "state_index": _optional_int(state.get("state_index")),
        "episode_index": _optional_int(state.get("episode_index")),
        "episode_id": str(state.get("episode_id", "")),
        "scene_id": str(state.get("scene_id", "")),
        "target_category": str(state.get("target_category", "")),
        "step_index": _optional_int(state.get("step_index")),
        "state_action": str(state.get("state_action", "")),
        "state_decision": str(state.get("state_decision", "")),
        "hard_state_reason": hard_state_reason,
        "baseline_action": baseline_action,
        "baseline_success": (
            bool(baseline_payload.get("success")) if baseline_payload else None
        ),
        "baseline_in_fastest_actions": baseline_action in fastest_actions,
        "baseline_strict_fastest": state.get("strict_fastest_action") == baseline_action,
        "baseline_time_to_visible_steps": baseline_time,
        "best_time_to_visible_steps": best_time,
        "baseline_time_regret_steps": baseline_regret,
        "positive_action_count": _optional_int(state.get("positive_action_count")),
        "positive_actions": _string_list(state.get("positive_actions")),
        "fastest_actions": list(fastest_actions),
        "strict_fastest_action": _optional_string(state.get("strict_fastest_action")),
        "oracle_recovered": bool(state.get("oracle_recovered")),
        "state_features": dict(_mapping(state.get("state_features"))),
        "actions": {
            action: dict(_mapping(action_payloads.get(action))) for action in actions
        },
    }


def _aggregate_hard_states(states: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    strict_fastest_action_counts: dict[str, int] = {}
    target_category_counts: dict[str, int] = {}
    source_family_counts: dict[str, dict[str, Any]] = {}
    baseline_success_count = 0
    for state in states:
        reason = str(state.get("hard_state_reason", ""))
        reason_counts[reason] = reason_counts.get(reason, 0) + 1

        strict_key = _strict_fastest_key(state)
        strict_fastest_action_counts[strict_key] = (
            strict_fastest_action_counts.get(strict_key, 0) + 1
        )

        target_category = str(state.get("target_category", ""))
        if target_category:
            target_category_counts[target_category] = (
                target_category_counts.get(target_category, 0) + 1
            )
        if bool(state.get("baseline_success")):
            baseline_success_count += 1

        family = str(state.get("source_family", "")) or "unknown"
        family_counts = source_family_counts.setdefault(
            family,
            {
                "state_count": 0,
                "strict_fastest_action_counts": {},
                "target_category_counts": {},
            },
        )
        family_counts["state_count"] += 1
        family_strict_counts = family_counts["strict_fastest_action_counts"]
        family_strict_counts[strict_key] = family_strict_counts.get(strict_key, 0) + 1
        if target_category:
            family_target_counts = family_counts["target_category_counts"]
            family_target_counts[target_category] = (
                family_target_counts.get(target_category, 0) + 1
            )

    return {
        "hard_state_reason_counts": reason_counts,
        "strict_fastest_action_counts": strict_fastest_action_counts,
        "target_category_counts": target_category_counts,
        "source_family_counts": source_family_counts,
        "baseline_success_count": baseline_success_count,
    }


def _source_family(state: Mapping[str, Any]) -> str:
    source_text = " ".join(
        [
            str(state.get("source_dataset", "")),
            str(state.get("source_policy_trace", "")),
        ]
    ).lower()
    patterns = (
        ("active_original", "active_original"),
        ("active_rotation", "active_rotation"),
        ("rotation_aware", "active_rotation"),
        ("active_path", "active_path"),
        ("path_aware", "active_path"),
        ("active_scan", "active_scan"),
        ("viewpoint_scan", "active_scan"),
    )
    for pattern, family in patterns:
        if pattern in source_text:
            return family
    source_dataset_index = _optional_int(state.get("source_dataset_index"))
    if source_dataset_index is not None:
        return f"source_dataset_index:{source_dataset_index}"
    return "unknown"


def _best_time_to_visible(
    action_payloads: Mapping[str, Any],
    fastest_actions: Sequence[str],
) -> int | None:
    times = [
        _optional_int(_mapping(action_payloads.get(action)).get("time_to_visible_steps"))
        for action in fastest_actions
    ]
    finite_times = [time for time in times if time is not None]
    return min(finite_times) if finite_times else None


def _strict_fastest_key(state: Mapping[str, Any]) -> str:
    strict_action = _optional_string(state.get("strict_fastest_action"))
    return strict_action if strict_action else "<tie>"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item) for item in value if str(item)]


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple)):
        return "|".join(str(item) for item in value)
    return str(value)
