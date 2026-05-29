from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


DEFAULT_EPOCHS = 400
DEFAULT_LEARNING_RATE = 0.1
DEFAULT_L2 = 0.001


def train_memory_validity_logistic_model(
    dataset: Mapping[str, Any],
    *,
    feature_names: Sequence[str] | None = None,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    l2: float = DEFAULT_L2,
) -> dict[str, Any]:
    examples = _examples(dataset)
    selected_features = _feature_names(dataset, feature_names=feature_names)
    labels = [1.0 if bool(example.get("label_memory_valid")) else 0.0 for example in examples]
    raw_rows, preprocessing = _preprocess_training_rows(
        examples=examples,
        feature_names=selected_features,
    )
    rows = [
        _standardize(row, selected_features, preprocessing)
        for row in raw_rows
    ]
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
        "task": "habitat_memory_validity_logistic_model",
        "model_type": "logistic_regression",
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
            "example_count": len(labels),
            "positive_count": positive_count,
            "negative_count": negative_count,
        },
        "metrics": _metrics(labels=labels, predictions=predictions),
    }


def predict_memory_validity(
    model: Mapping[str, Any],
    features: Mapping[str, Any],
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
    row: list[float] = []
    for feature_name in feature_names:
        raw_value = features.get(feature_name)
        if _is_finite_number(raw_value):
            value = float(raw_value)
        else:
            value = feature_means.get(feature_name, 0.0)
        scale = feature_scales.get(feature_name, 1.0)
        if scale <= 0.0 or not math.isfinite(scale):
            scale = 1.0
        row.append((value - feature_means.get(feature_name, 0.0)) / scale)
    bias = _to_float(model.get("bias"), default=0.0)
    return _sigmoid(_dot(weights[: len(feature_names)], row) + bias)


def _examples(dataset: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    examples = dataset.get("examples", [])
    if not isinstance(examples, list):
        raise ValueError("dataset examples must be a list")
    parsed = [example for example in examples if isinstance(example, Mapping)]
    if not parsed:
        raise ValueError("dataset has no examples")
    return parsed


def _feature_names(
    dataset: Mapping[str, Any],
    *,
    feature_names: Sequence[str] | None,
) -> list[str]:
    if feature_names is not None:
        selected = [str(name) for name in feature_names]
    else:
        schema = dataset.get("feature_schema", [])
        if isinstance(schema, Sequence) and not isinstance(schema, (str, bytes)):
            selected = [str(name) for name in schema]
        else:
            selected = []
    if selected:
        return selected
    discovered: set[str] = set()
    for example in _examples(dataset):
        features = example.get("features", {})
        if isinstance(features, Mapping):
            discovered.update(str(name) for name in features)
    return sorted(discovered)


def _preprocess_training_rows(
    *,
    examples: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
) -> tuple[list[dict[str, float | None]], dict[str, Any]]:
    raw_rows: list[dict[str, float | None]] = []
    present_values: dict[str, list[float]] = {name: [] for name in feature_names}
    missing_value_count = 0
    non_numeric_count = 0
    for example in examples:
        features = example.get("features", {})
        if not isinstance(features, Mapping):
            features = {}
        row: dict[str, float | None] = {}
        for feature_name in feature_names:
            raw_value = features.get(feature_name)
            if _is_finite_number(raw_value):
                value = float(raw_value)
                present_values[feature_name].append(value)
            else:
                value = None
                missing_value_count += 1
                if raw_value is not None:
                    non_numeric_count += 1
            row[feature_name] = value
        raw_rows.append(row)

    feature_means = {
        feature_name: (
            sum(values) / float(len(values))
            if values
            else 0.0
        )
        for feature_name, values in present_values.items()
    }
    imputed_rows: list[dict[str, float]] = []
    for row in raw_rows:
        imputed_rows.append(
            {
                feature_name: (
                    value
                    if value is not None
                    else feature_means[feature_name]
                )
                for feature_name, value in row.items()
            }
        )
    feature_scales: dict[str, float] = {}
    for feature_name in feature_names:
        mean = feature_means[feature_name]
        variance = sum(
            (row[feature_name] - mean) ** 2
            for row in imputed_rows
        ) / float(len(imputed_rows))
        scale = math.sqrt(variance)
        feature_scales[feature_name] = scale if scale > 1e-12 else 1.0
    warnings: list[str] = []
    if non_numeric_count:
        warnings.append(f"ignored {non_numeric_count} non-numeric feature values")
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
    feature_means = _float_mapping(preprocessing.get("feature_means"))
    feature_scales = _float_mapping(preprocessing.get("feature_scales"))
    values: list[float] = []
    for feature_name in feature_names:
        value = row.get(feature_name)
        if value is None:
            value = feature_means.get(feature_name, 0.0)
        scale = feature_scales.get(feature_name, 1.0)
        if scale <= 0.0 or not math.isfinite(scale):
            scale = 1.0
        values.append((float(value) - feature_means.get(feature_name, 0.0)) / scale)
    return values


def _metrics(*, labels: Sequence[float], predictions: Sequence[float]) -> dict[str, Any]:
    correct_count = 0
    log_loss = 0.0
    brier_score = 0.0
    for label, prediction in zip(labels, predictions):
        probability = _clamp_probability(prediction)
        predicted_label = 1.0 if probability >= 0.5 else 0.0
        if predicted_label == label:
            correct_count += 1
        log_loss += -(
            label * math.log(probability)
            + (1.0 - label) * math.log(1.0 - probability)
        )
        brier_score += (probability - label) ** 2
    example_count = len(labels)
    positive_count = int(sum(labels))
    return {
        "example_count": example_count,
        "positive_count": positive_count,
        "negative_count": example_count - positive_count,
        "accuracy": correct_count / float(example_count),
        "log_loss": log_loss / float(example_count),
        "brier_score": brier_score / float(example_count),
    }


def _float_mapping(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): _to_float(raw_value, default=0.0)
        for key, raw_value in value.items()
    }


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _to_float(value: object, *, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _logit(probability: float) -> float:
    probability = _clamp_probability(probability)
    return math.log(probability / (1.0 - probability))


def _clamp_probability(probability: float) -> float:
    return min(1.0 - 1e-12, max(1e-12, float(probability)))


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right))
