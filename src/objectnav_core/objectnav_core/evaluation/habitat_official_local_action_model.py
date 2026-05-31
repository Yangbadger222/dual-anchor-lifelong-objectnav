from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_EPOCHS = 400
DEFAULT_LEARNING_RATE = 0.1
DEFAULT_L2 = 0.001
LABEL_NAME = "next_target_visible"

DEFAULT_FEATURE_NAMES: tuple[str, ...] = (
    "current_target_visible",
    "current_target_match_count",
    "current_detector_confidence",
    "current_bbox_area_fraction",
    "current_abs_center_offset_fraction",
    "x_m",
    "z_m",
    "heading_rad",
    "action_move_forward",
    "action_turn_left",
    "action_turn_right",
    "action_stop",
    "suppressed_action_none",
    "suppressed_action_turn_left",
    "suppressed_action_turn_right",
)
_CANDIDATE_SCORE_CSV_BASE_FIELDS: tuple[str, ...] = (
    "row_index",
    "episode_index",
    "episode_id",
    "scene_id",
    "target_category",
    "step_index",
    "observed_action",
    "label_name",
    "label_value",
    "current_target_visible",
    "current_abs_center_offset_fraction",
    "best_action",
    "best_matches_observed_action",
)


def train_official_local_action_logistic_model(
    dataset: Mapping[str, Any],
    *,
    feature_names: Sequence[str] | None = None,
    label_name: str = LABEL_NAME,
    current_visible_only: bool = False,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    l2: float = DEFAULT_L2,
) -> dict[str, Any]:
    source_examples = _examples(dataset)
    examples = _filter_training_examples(
        source_examples,
        current_visible_only=current_visible_only,
    )
    selected_features = [str(name) for name in (feature_names or DEFAULT_FEATURE_NAMES)]
    selected_label = str(label_name or LABEL_NAME)
    labels = [_label(example, label_name=selected_label) for example in examples]
    raw_rows, preprocessing = _preprocess_training_rows(
        examples=examples,
        feature_names=selected_features,
    )
    rows = [_standardize(row, selected_features, preprocessing) for row in raw_rows]
    weights = [0.0 for _ in selected_features]
    positive_rate = sum(labels) / float(len(labels))
    bias = _logit(_clamp_probability(positive_rate))
    safe_epochs = max(0, int(epochs))
    safe_learning_rate = float(learning_rate)
    safe_l2 = max(0.0, float(l2))

    for _ in range(safe_epochs):
        grad_weights = [0.0 for _ in selected_features]
        grad_bias = 0.0
        for row, label in zip(rows, labels):
            predicted = _sigmoid(_dot(weights, row) + bias)
            error = predicted - label
            grad_bias += error
            for index, value in enumerate(row):
                grad_weights[index] += error * value
        scale = 1.0 / float(len(rows))
        bias -= safe_learning_rate * grad_bias * scale
        for index, weight in enumerate(weights):
            gradient = grad_weights[index] * scale + safe_l2 * weight
            weights[index] = weight - safe_learning_rate * gradient

    predictions = [_sigmoid(_dot(weights, row) + bias) for row in rows]
    positive_count = int(sum(labels))
    negative_count = len(labels) - positive_count
    warnings = list(preprocessing["warnings"])
    if positive_count == 0 or negative_count == 0:
        warnings.append("dataset has only one label class")
    return {
        "task": "habitat_official_local_action_logistic_model",
        "model_type": "logistic_regression",
        "label_name": selected_label,
        "feature_names": selected_features,
        "weights": weights,
        "bias": bias,
        "preprocessing": {
            "feature_means": preprocessing["feature_means"],
            "feature_scales": preprocessing["feature_scales"],
            "missing_value_count": preprocessing["missing_value_count"],
            "warnings": warnings,
        },
        "training": {
            "epochs": safe_epochs,
            "learning_rate": safe_learning_rate,
            "l2": safe_l2,
        },
        "dataset": {
            "source_example_count": len(source_examples),
            "example_count": len(labels),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "training_filter": {
                "current_visible_only": bool(current_visible_only),
            },
        },
        "metrics": _metrics(labels=labels, predictions=predictions),
    }


def predict_official_local_action_success(
    model: Mapping[str, Any],
    example: Mapping[str, Any],
    *,
    action: str | None = None,
) -> float:
    feature_names = [str(name) for name in model.get("feature_names", [])]
    weights = [_to_float(value, default=0.0) for value in model.get("weights", [])]
    if len(weights) < len(feature_names):
        weights = weights + [0.0 for _ in range(len(feature_names) - len(weights))]
    preprocessing = model.get("preprocessing", {})
    if not isinstance(preprocessing, Mapping):
        preprocessing = {}
    feature_means = _float_mapping(preprocessing.get("feature_means"))
    feature_scales = _float_mapping(preprocessing.get("feature_scales"))
    values = _feature_values(example, action=action, feature_names=feature_names)
    row: list[float] = []
    for feature_name in feature_names:
        raw_value = values.get(feature_name)
        value = (
            float(raw_value)
            if _is_finite_number(raw_value)
            else feature_means.get(feature_name, 0.0)
        )
        scale = feature_scales.get(feature_name, 1.0)
        if scale <= 0.0 or not math.isfinite(scale):
            scale = 1.0
        row.append((value - feature_means.get(feature_name, 0.0)) / scale)
    bias = _to_float(model.get("bias"), default=0.0)
    return _sigmoid(_dot(weights[: len(feature_names)], row) + bias)


def score_official_local_action_candidates(
    model: Mapping[str, Any],
    example: Mapping[str, Any],
    *,
    actions: Sequence[str] = ("move_forward", "turn_left", "turn_right"),
) -> dict[str, Any]:
    scores = {
        str(action): predict_official_local_action_success(
            model,
            example,
            action=str(action),
        )
        for action in actions
    }
    best_action = max(scores, key=scores.get) if scores else None
    return {
        "task": "habitat_official_local_action_candidate_scores",
        "label_name": str(model.get("label_name", LABEL_NAME)),
        "best_action": best_action,
        "scores": {action: round(score, 6) for action, score in scores.items()},
    }


def score_official_local_action_dataset_candidates(
    dataset: Mapping[str, Any],
    model: Mapping[str, Any],
    *,
    actions: Sequence[str] = ("move_forward", "turn_left", "turn_right"),
    current_visible_only: bool = False,
) -> dict[str, Any]:
    selected_actions = [str(action) for action in actions if str(action)]
    if not selected_actions:
        raise ValueError("at least one candidate action is required")
    source_examples = _examples(dataset)
    examples = _filter_training_examples(
        source_examples,
        current_visible_only=current_visible_only,
    )
    label_name = str(model.get("label_name", LABEL_NAME))
    rows: list[dict[str, Any]] = []
    for row_index, example in enumerate(examples):
        scores = score_official_local_action_candidates(
            model,
            example,
            actions=selected_actions,
        )
        observed_action = str(example.get("action", ""))
        best_action = str(scores.get("best_action") or "")
        label_value = bool(_label(example, label_name=label_name))
        features = example.get("features", {})
        if not isinstance(features, Mapping):
            features = {}
        rows.append(
            {
                "row_index": row_index,
                "episode_index": example.get("episode_index"),
                "episode_id": str(example.get("episode_id", "")),
                "scene_id": str(example.get("scene_id", "")),
                "target_category": str(example.get("target_category", "")),
                "step_index": example.get("step_index"),
                "observed_action": observed_action,
                "label_name": label_name,
                "label_value": label_value,
                "current_target_visible": bool(
                    features.get("current_target_visible")
                ),
                "current_abs_center_offset_fraction": features.get(
                    "current_abs_center_offset_fraction"
                ),
                "best_action": best_action,
                "best_matches_observed_action": (
                    best_action == observed_action if observed_action else None
                ),
                "candidate_scores": scores.get("scores", {}),
            }
        )
    return {
        "task": "habitat_official_local_action_candidate_score_report",
        "label_name": label_name,
        "candidate_actions": selected_actions,
        "source_example_count": len(source_examples),
        "example_count": len(rows),
        "filter": {
            "current_visible_only": bool(current_visible_only),
        },
        "aggregate": {
            "best_action_counts": _string_counts(
                row["best_action"] for row in rows
            ),
            "observed_action_counts": _string_counts(
                row["observed_action"] for row in rows
            ),
            "label_positive_count": sum(
                1 for row in rows if bool(row["label_value"])
            ),
            "label_negative_count": sum(
                1 for row in rows if not bool(row["label_value"])
            ),
            "best_matches_observed_action_count": sum(
                1 for row in rows if row["best_matches_observed_action"] is True
            ),
        },
        "rows": rows,
    }


def write_official_local_action_candidate_scores_csv(
    path: str | Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    candidate_actions: Sequence[str] = ("move_forward", "turn_left", "turn_right"),
) -> None:
    score_fields = [f"candidate_score_{action}" for action in candidate_actions]
    fieldnames = [*_CANDIDATE_SCORE_CSV_BASE_FIELDS, *score_fields]
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            scores = row.get("candidate_scores", {})
            if not isinstance(scores, Mapping):
                scores = {}
            payload = {
                field: _csv_value(row.get(field))
                for field in _CANDIDATE_SCORE_CSV_BASE_FIELDS
            }
            for action, field in zip(candidate_actions, score_fields):
                payload[field] = _csv_value(scores.get(str(action)))
            writer.writerow(payload)


def _examples(dataset: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    examples = dataset.get("examples", [])
    if not isinstance(examples, list):
        raise ValueError("dataset examples must be a list")
    parsed = [example for example in examples if isinstance(example, Mapping)]
    if not parsed:
        raise ValueError("dataset has no examples")
    return parsed


def _string_counts(values: Sequence[str] | Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        if not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _filter_training_examples(
    examples: Sequence[Mapping[str, Any]],
    *,
    current_visible_only: bool,
) -> list[Mapping[str, Any]]:
    if not current_visible_only:
        return list(examples)
    filtered = [
        example
        for example in examples
        if _example_current_target_visible(example)
    ]
    if not filtered:
        raise ValueError("dataset has no current-target-visible examples")
    return filtered


def _example_current_target_visible(example: Mapping[str, Any]) -> bool:
    features = example.get("features", {})
    if not isinstance(features, Mapping):
        return False
    return bool(features.get("current_target_visible"))


def _label(example: Mapping[str, Any], *, label_name: str = LABEL_NAME) -> float:
    labels = example.get("labels", {})
    if not isinstance(labels, Mapping):
        return 0.0
    return 1.0 if bool(labels.get(label_name)) else 0.0


def _feature_values(
    example: Mapping[str, Any],
    *,
    action: str | None = None,
    feature_names: Sequence[str] | None = None,
) -> dict[str, float | None]:
    features = example.get("features", {})
    if not isinstance(features, Mapping):
        features = {}
    selected_action = str(action or example.get("action", ""))
    decision = str(example.get("decision", ""))
    suppressed_action = str(features.get("suppressed_detector_center_action", ""))
    if not suppressed_action:
        suppressed_action = "none"
    values: dict[str, float | None] = {
        "current_target_visible": _bool_float(features.get("current_target_visible")),
        "current_target_match_count": _optional_float(
            features.get("current_target_match_count")
        ),
        "current_detector_confidence": _optional_float(
            features.get("current_detector_confidence")
        ),
        "current_bbox_area_fraction": _optional_float(
            features.get("current_bbox_area_fraction")
        ),
        "current_abs_center_offset_fraction": _optional_float(
            features.get("current_abs_center_offset_fraction")
        ),
        "x_m": _optional_float(features.get("x_m")),
        "z_m": _optional_float(features.get("z_m")),
        "heading_rad": _optional_float(features.get("heading_rad")),
        "action_move_forward": _one_hot(selected_action, "move_forward"),
        "action_turn_left": _one_hot(selected_action, "turn_left"),
        "action_turn_right": _one_hot(selected_action, "turn_right"),
        "action_stop": _one_hot(selected_action, "stop"),
        "decision_center_detector_target": _one_hot(
            decision,
            "center_detector_target",
        ),
        "decision_reacquire_detector_target": _one_hot(
            decision,
            "reacquire_detector_target",
        ),
        "decision_approach_detector_target": _one_hot(
            decision,
            "approach_detector_target",
        ),
        "decision_approach_detector_target_after_center_loss": _one_hot(
            decision,
            "approach_detector_target_after_center_loss",
        ),
        "decision_fallback_occupancy_frontier": _one_hot(
            decision,
            "fallback_occupancy_frontier",
        ),
        "decision_turn_toward_memory_belief_frontier": _one_hot(
            decision,
            "turn_toward_memory_belief_frontier",
        ),
        "suppressed_action_none": _one_hot(suppressed_action, "none"),
        "suppressed_action_turn_left": _one_hot(suppressed_action, "turn_left"),
        "suppressed_action_turn_right": _one_hot(suppressed_action, "turn_right"),
    }
    for key, value in features.items():
        if key not in values and _is_finite_number(value):
            values[str(key)] = float(value)
    for feature_name in feature_names or ():
        if "__" not in feature_name or feature_name in values:
            continue
        left_name, right_name = feature_name.split("__", 1)
        left_value = values.get(left_name)
        right_value = values.get(right_name)
        if _is_finite_number(left_value) and _is_finite_number(right_value):
            values[feature_name] = float(left_value) * float(right_value)
        else:
            values[feature_name] = None
    return values


def _preprocess_training_rows(
    *,
    examples: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
) -> tuple[list[dict[str, float | None]], dict[str, Any]]:
    raw_rows = [
        _feature_values(
            example,
            action=str(example.get("action", "")),
            feature_names=feature_names,
        )
        for example in examples
    ]
    feature_means: dict[str, float] = {}
    feature_scales: dict[str, float] = {}
    missing_value_count = 0
    warnings: list[str] = []
    for feature_name in feature_names:
        values = [
            row.get(feature_name)
            for row in raw_rows
            if _is_finite_number(row.get(feature_name))
        ]
        missing_value_count += len(raw_rows) - len(values)
        if not values:
            feature_means[feature_name] = 0.0
            feature_scales[feature_name] = 1.0
            warnings.append(f"feature {feature_name} has no finite values")
            continue
        mean = sum(float(value) for value in values) / float(len(values))
        variance = sum((float(value) - mean) ** 2 for value in values) / float(
            len(values)
        )
        scale = math.sqrt(variance)
        feature_means[feature_name] = mean
        feature_scales[feature_name] = scale if scale > 1e-12 else 1.0
    return raw_rows, {
        "feature_means": feature_means,
        "feature_scales": feature_scales,
        "missing_value_count": missing_value_count,
        "warnings": warnings,
    }


def _standardize(
    row: Mapping[str, float | None],
    feature_names: Sequence[str],
    preprocessing: Mapping[str, Any],
) -> list[float]:
    means = _float_mapping(preprocessing.get("feature_means"))
    scales = _float_mapping(preprocessing.get("feature_scales"))
    values: list[float] = []
    for feature_name in feature_names:
        raw_value = row.get(feature_name)
        value = (
            float(raw_value)
            if _is_finite_number(raw_value)
            else means.get(feature_name, 0.0)
        )
        scale = scales.get(feature_name, 1.0)
        if scale <= 0.0 or not math.isfinite(scale):
            scale = 1.0
        values.append((value - means.get(feature_name, 0.0)) / scale)
    return values


def _metrics(
    *,
    labels: Sequence[float],
    predictions: Sequence[float],
) -> dict[str, Any]:
    positive_count = int(sum(labels))
    negative_count = len(labels) - positive_count
    correct = sum(
        1
        for label, prediction in zip(labels, predictions)
        if (prediction >= 0.5) == bool(label)
    )
    log_loss = 0.0
    brier = 0.0
    for label, prediction in zip(labels, predictions):
        safe_prediction = _clamp_probability(prediction)
        log_loss += -(
            label * math.log(safe_prediction)
            + (1.0 - label) * math.log(1.0 - safe_prediction)
        )
        brier += (prediction - label) ** 2
    count = max(1, len(labels))
    return {
        "example_count": len(labels),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "accuracy": round(correct / float(count), 6),
        "log_loss": round(log_loss / float(count), 6),
        "brier_score": round(brier / float(count), 6),
        "mean_prediction": round(sum(predictions) / float(count), 6),
    }


def _one_hot(value: str, expected: str) -> float:
    return 1.0 if value == expected else 0.0


def _bool_float(value: object) -> float:
    return 1.0 if bool(value) else 0.0


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _is_finite_number(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value))


def _to_float(value: object, *, default: float) -> float:
    parsed = _optional_float(value)
    return default if parsed is None else parsed


def _float_mapping(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): float(raw)
        for key, raw in value.items()
        if _is_finite_number(raw)
    }


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _dot(weights: Sequence[float], row: Sequence[float]) -> float:
    return sum(weight * value for weight, value in zip(weights, row))


def _logit(probability: float) -> float:
    return math.log(probability / (1.0 - probability))


def _clamp_probability(value: float) -> float:
    return min(1.0 - 1e-9, max(1e-9, float(value)))


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value
