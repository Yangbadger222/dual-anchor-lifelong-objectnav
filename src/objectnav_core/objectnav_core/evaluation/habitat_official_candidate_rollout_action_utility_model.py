from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence


DEFAULT_EPOCHS = 600
DEFAULT_LEARNING_RATE = 0.2
DEFAULT_L2 = 0.001


def train_official_candidate_rollout_action_utility_model(
    report: Mapping[str, Any],
    *,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    l2: float = DEFAULT_L2,
) -> dict[str, Any]:
    actions = _actions(report)
    states = _states(report)
    feature_names = _feature_names(states, actions=actions)
    examples = _examples(states, actions=actions)
    labels = [example["utility"] for example in examples]
    raw_rows = [
        _feature_row(example["state"], str(example["action"]), feature_names)
        for example in examples
    ]
    preprocessing = _preprocessing(raw_rows, feature_names)
    rows = [_standardize(row, feature_names, preprocessing) for row in raw_rows]
    weights = [0.0 for _ in feature_names]
    bias = sum(labels) / float(len(labels)) if labels else 0.0
    safe_epochs = max(0, int(epochs))
    safe_learning_rate = float(learning_rate)
    safe_l2 = max(0.0, float(l2))

    for _ in range(safe_epochs):
        grad_weights = [0.0 for _ in feature_names]
        grad_bias = 0.0
        for row, label in zip(rows, labels):
            predicted = _dot(weights, row) + bias
            error = predicted - label
            grad_bias += error
            for index, value in enumerate(row):
                grad_weights[index] += error * value
        if not rows:
            break
        scale = 1.0 / float(len(rows))
        bias -= safe_learning_rate * grad_bias * scale
        for index, weight in enumerate(weights):
            gradient = grad_weights[index] * scale + safe_l2 * weight
            weights[index] = weight - safe_learning_rate * gradient

    model = {
        "task": "habitat_official_candidate_rollout_action_utility_model",
        "model_type": "linear_utility_regression",
        "actions": list(actions),
        "feature_names": feature_names,
        "weights": weights,
        "bias": bias,
        "preprocessing": preprocessing,
        "training": {
            "epochs": safe_epochs,
            "learning_rate": safe_learning_rate,
            "l2": safe_l2,
        },
        "dataset": {
            "state_count": len(states),
            "example_count": len(examples),
        },
    }
    model["metrics"] = score_official_candidate_rollout_action_utility_report(
        report,
        model,
    )["aggregate"]
    return model


def score_official_candidate_rollout_action_utility_report(
    report: Mapping[str, Any],
    model: Mapping[str, Any],
) -> dict[str, Any]:
    actions = tuple(str(action) for action in model.get("actions", []) if str(action))
    feature_names = [str(name) for name in model.get("feature_names", [])]
    weights = [_float(value) for value in model.get("weights", [])]
    if len(weights) < len(feature_names):
        weights.extend(0.0 for _ in range(len(feature_names) - len(weights)))
    preprocessing = model.get("preprocessing", {})
    if not isinstance(preprocessing, Mapping):
        preprocessing = {}
    rows: list[dict[str, Any]] = []
    for state in _states(report):
        action_scores = {
            action: _predict_state_action_utility(
                state,
                action,
                feature_names=feature_names,
                weights=weights,
                bias=_float(model.get("bias")),
                preprocessing=preprocessing,
            )
            for action in actions
        }
        chosen_action = max(actions, key=lambda action: action_scores[action])
        actual_utilities = {
            action: _actual_action_utility(state, action) for action in actions
        }
        oracle_best_utility = max(actual_utilities.values(), default=0.0)
        chosen_utility = actual_utilities.get(chosen_action, 0.0)
        fastest_actions = _fastest_actions(state, actions=actions)
        rows.append(
            {
                "source_dataset": str(state.get("source_dataset", "")),
                "state_index": state.get("state_index"),
                "episode_index": state.get("episode_index"),
                "episode_id": str(state.get("episode_id", "")),
                "step_index": state.get("step_index"),
                "state_action": str(state.get("state_action", "")),
                "state_decision": str(state.get("state_decision", "")),
                "chosen_action": chosen_action,
                "chosen_success": chosen_utility > 0.0,
                "chosen_in_fastest": chosen_action in fastest_actions,
                "chosen_utility": round(chosen_utility, 6),
                "oracle_best_utility": round(oracle_best_utility, 6),
                "utility_regret": round(oracle_best_utility - chosen_utility, 6),
                "fastest_actions": list(fastest_actions),
                "action_scores": {
                    action: round(score, 6) for action, score in action_scores.items()
                },
                "actual_utilities": {
                    action: round(value, 6)
                    for action, value in actual_utilities.items()
                },
            }
        )
    return {
        "task": "habitat_official_candidate_rollout_action_utility_scores",
        "model_task": str(model.get("task", "")),
        "state_count": len(rows),
        "aggregate": _score_aggregate(rows),
        "rows": rows,
    }


def evaluate_action_utility_leave_one_source(
    report: Mapping[str, Any],
    *,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    l2: float = DEFAULT_L2,
) -> dict[str, Any]:
    states = _states(report)
    sources = sorted({str(state.get("source_dataset", "")) for state in states})
    splits: list[dict[str, Any]] = []
    for source in sources:
        train_states = [state for state in states if str(state.get("source_dataset", "")) != source]
        holdout_states = [state for state in states if str(state.get("source_dataset", "")) == source]
        if not train_states or not holdout_states:
            continue
        train_report = {**dict(report), "states": train_states}
        holdout_report = {**dict(report), "states": holdout_states}
        model = train_official_candidate_rollout_action_utility_model(
            train_report,
            epochs=epochs,
            learning_rate=learning_rate,
            l2=l2,
        )
        scores = score_official_candidate_rollout_action_utility_report(
            holdout_report,
            model,
        )
        splits.append(
            {
                "holdout_source": source,
                "train_state_count": len(train_states),
                "holdout_state_count": len(holdout_states),
                "aggregate": scores["aggregate"],
            }
        )
    return {
        "task": "habitat_official_candidate_rollout_action_utility_leave_one_source",
        "split_field": "source_dataset",
        "aggregate": _leave_one_source_aggregate(splits),
        "splits": splits,
    }


def _actions(report: Mapping[str, Any]) -> tuple[str, ...]:
    actions = tuple(str(action) for action in report.get("actions", []) if str(action))
    if not actions:
        raise ValueError("report has no actions")
    return actions


def _states(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    states = report.get("states", [])
    if not isinstance(states, list):
        raise ValueError("report states must be a list")
    parsed = [state for state in states if isinstance(state, Mapping)]
    if not parsed:
        raise ValueError("report has no states")
    return parsed


def _examples(
    states: Sequence[Mapping[str, Any]],
    *,
    actions: Sequence[str],
) -> list[dict[str, Any]]:
    return [
        {
            "state": state,
            "action": action,
            "utility": _actual_action_utility(state, action),
        }
        for state in states
        for action in actions
    ]


def _feature_names(
    states: Sequence[Mapping[str, Any]],
    *,
    actions: Sequence[str],
) -> list[str]:
    decisions = sorted({_token(state.get("state_decision")) for state in states})
    state_actions = sorted({_token(state.get("state_action")) for state in states})
    targets = sorted({_token(state.get("target_category")) for state in states})
    state_feature_names = _numeric_state_feature_names(states)
    names = [f"action={_token(action)}" for action in actions]
    names.extend(f"state_action={value}" for value in state_actions)
    names.extend(f"state_decision={value}" for value in decisions)
    names.extend(f"target_category={value}" for value in targets)
    names.extend(
        f"action_decision={_token(action)}__{decision}"
        for action in actions
        for decision in decisions
    )
    names.extend(f"action_step={_token(action)}" for action in actions)
    names.extend(f"action_step_squared={_token(action)}" for action in actions)
    names.append("step_index")
    names.extend(f"state_feature={name}" for name in state_feature_names)
    names.extend(
        f"action_state_feature={_token(action)}__{name}"
        for action in actions
        for name in state_feature_names
    )
    return names


def _feature_row(
    state: Mapping[str, Any],
    action: str,
    feature_names: Sequence[str],
) -> dict[str, float]:
    action_token = _token(action)
    decision_token = _token(state.get("state_decision"))
    step_index = _float(state.get("step_index"))
    values = {name: 0.0 for name in feature_names}
    for name in (
        f"action={action_token}",
        f"state_action={_token(state.get('state_action'))}",
        f"state_decision={decision_token}",
        f"target_category={_token(state.get('target_category'))}",
        f"action_decision={action_token}__{decision_token}",
    ):
        if name in values:
            values[name] = 1.0
    if "step_index" in values:
        values["step_index"] = step_index
    action_step_name = f"action_step={action_token}"
    if action_step_name in values:
        values[action_step_name] = step_index
    action_step_squared_name = f"action_step_squared={action_token}"
    if action_step_squared_name in values:
        values[action_step_squared_name] = step_index * step_index
    for feature_name, feature_value in _numeric_state_features(state).items():
        state_feature_name = f"state_feature={feature_name}"
        if state_feature_name in values:
            values[state_feature_name] = feature_value
        action_feature_name = f"action_state_feature={action_token}__{feature_name}"
        if action_feature_name in values:
            values[action_feature_name] = feature_value
    return values


def _numeric_state_feature_names(states: Sequence[Mapping[str, Any]]) -> list[str]:
    names: set[str] = set()
    for state in states:
        names.update(_numeric_state_features(state))
    return sorted(names)


def _numeric_state_features(state: Mapping[str, Any]) -> dict[str, float]:
    features = state.get("state_features", {})
    if not isinstance(features, Mapping):
        return {}
    parsed: dict[str, float] = {}
    for name, value in features.items():
        numeric = _numeric_feature_value(value)
        if numeric is not None:
            parsed[str(name)] = numeric
    return parsed


def _numeric_feature_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _preprocessing(
    rows: Sequence[Mapping[str, float]],
    feature_names: Sequence[str],
) -> dict[str, Any]:
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    for feature_name in feature_names:
        values = [float(row.get(feature_name, 0.0)) for row in rows]
        mean = sum(values) / float(len(values)) if values else 0.0
        variance = (
            sum((value - mean) ** 2 for value in values) / float(len(values))
            if values
            else 0.0
        )
        scale = math.sqrt(variance)
        means[feature_name] = mean
        scales[feature_name] = scale if scale > 1.0e-9 else 1.0
    return {
        "feature_means": means,
        "feature_scales": scales,
    }


def _standardize(
    row: Mapping[str, float],
    feature_names: Sequence[str],
    preprocessing: Mapping[str, Any],
) -> list[float]:
    means = preprocessing.get("feature_means", {})
    scales = preprocessing.get("feature_scales", {})
    if not isinstance(means, Mapping):
        means = {}
    if not isinstance(scales, Mapping):
        scales = {}
    return [
        (float(row.get(name, 0.0)) - _float(means.get(name)))
        / max(_float(scales.get(name), default=1.0), 1.0e-9)
        for name in feature_names
    ]


def _predict_state_action_utility(
    state: Mapping[str, Any],
    action: str,
    *,
    feature_names: Sequence[str],
    weights: Sequence[float],
    bias: float,
    preprocessing: Mapping[str, Any],
) -> float:
    raw_row = _feature_row(state, action, feature_names)
    row = _standardize(raw_row, feature_names, preprocessing)
    return _dot(weights[: len(feature_names)], row) + bias


def _actual_action_utility(state: Mapping[str, Any], action: str) -> float:
    payload = _action_payload(state, action)
    if not bool(payload.get("success")):
        return 0.0
    time_to_visible = _float(payload.get("time_to_visible_steps"))
    if time_to_visible <= 0.0:
        return 0.0
    return 1.0 / time_to_visible


def _fastest_actions(
    state: Mapping[str, Any],
    *,
    actions: Sequence[str],
) -> tuple[str, ...]:
    explicit = state.get("fastest_actions")
    if isinstance(explicit, Sequence) and not isinstance(explicit, (str, bytes)):
        return tuple(str(action) for action in explicit if str(action) in actions)
    utilities = {action: _actual_action_utility(state, action) for action in actions}
    best = max(utilities.values(), default=0.0)
    if best <= 0.0:
        return ()
    return tuple(action for action in actions if utilities[action] == best)


def _action_payload(state: Mapping[str, Any], action: str) -> Mapping[str, Any]:
    actions = state.get("actions", {})
    if not isinstance(actions, Mapping):
        return {}
    payload = actions.get(action, {})
    return payload if isinstance(payload, Mapping) else {}


def _score_aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    state_count = len(rows)
    chosen_success_count = sum(1 for row in rows if bool(row.get("chosen_success")))
    chosen_in_fastest_count = sum(
        1 for row in rows if bool(row.get("chosen_in_fastest"))
    )
    regret_sum = sum(_float(row.get("utility_regret")) for row in rows)
    return {
        "state_count": state_count,
        "chosen_success_count": chosen_success_count,
        "chosen_in_fastest_count": chosen_in_fastest_count,
        "mean_utility_regret": round(
            regret_sum / float(state_count),
            6,
        )
        if state_count
        else 0.0,
    }


def _leave_one_source_aggregate(splits: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    state_count = sum(
        int(_float(_mapping(split.get("aggregate")).get("state_count")))
        for split in splits
    )
    chosen_success_count = sum(
        int(_float(_mapping(split.get("aggregate")).get("chosen_success_count")))
        for split in splits
    )
    chosen_in_fastest_count = sum(
        int(_float(_mapping(split.get("aggregate")).get("chosen_in_fastest_count")))
        for split in splits
    )
    regret_total = sum(
        _float(_mapping(split.get("aggregate")).get("mean_utility_regret"))
        * int(_float(_mapping(split.get("aggregate")).get("state_count")))
        for split in splits
    )
    return {
        "split_count": len(splits),
        "state_count": state_count,
        "chosen_success_count": chosen_success_count,
        "chosen_in_fastest_count": chosen_in_fastest_count,
        "mean_utility_regret": round(regret_total / float(state_count), 6)
        if state_count
        else 0.0,
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _dot(weights: Sequence[float], row: Sequence[float]) -> float:
    return sum(weight * value for weight, value in zip(weights, row))


def _token(value: Any) -> str:
    token = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "none")).strip("_")
    return token or "none"


def _float(value: Any, *, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default
