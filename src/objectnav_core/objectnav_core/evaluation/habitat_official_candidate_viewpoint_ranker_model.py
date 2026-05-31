from __future__ import annotations

import csv
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_EPOCHS = 600
DEFAULT_LEARNING_RATE = 0.2
DEFAULT_L2 = 0.001
LABEL_NAME = "hidden_to_visible_from_candidate_viewpoint"

_SCORE_CSV_FIELDS: tuple[str, ...] = (
    "state_key",
    "source_policy_trace",
    "state_index",
    "episode_index",
    "episode_id",
    "scene_id",
    "target_category",
    "step_index",
    "state_action",
    "state_decision",
    "oracle_recoverable",
    "model_recovered",
    "model_candidate_rank",
    "model_prediction",
    "top_rank_recovered",
    "top_rank_candidate_rank",
    "top_score_recovered",
    "top_score_candidate_rank",
)


def train_official_candidate_viewpoint_ranker_model(
    dataset: Mapping[str, Any],
    *,
    label_name: str = LABEL_NAME,
    current_hidden_only: bool = True,
    excluded_feature_names: Sequence[str] | None = None,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    l2: float = DEFAULT_L2,
) -> dict[str, Any]:
    source_candidates = _candidates(dataset)
    candidates = _filter_candidates(
        source_candidates,
        current_hidden_only=current_hidden_only,
        label_name=label_name,
    )
    excluded_features = _normalized_feature_names(excluded_feature_names)
    feature_names = _feature_names(
        candidates,
        excluded_feature_names=excluded_features,
    )
    labels = [_label(candidate, label_name=label_name) for candidate in candidates]
    raw_rows = [_feature_row(candidate, feature_names) for candidate in candidates]
    preprocessing = _preprocessing(raw_rows, feature_names)
    rows = [_standardize(row, feature_names, preprocessing) for row in raw_rows]
    weights = [0.0 for _ in feature_names]
    positive_rate = sum(labels) / float(len(labels))
    bias = _logit(_clamp_probability(positive_rate))
    safe_epochs = max(0, int(epochs))
    safe_learning_rate = float(learning_rate)
    safe_l2 = max(0.0, float(l2))

    for _ in range(safe_epochs):
        grad_weights = [0.0 for _ in feature_names]
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
        "task": "habitat_official_candidate_viewpoint_ranker_model",
        "model_type": "logistic_regression",
        "label_name": str(label_name),
        "feature_names": feature_names,
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
            "source_candidate_count": len(source_candidates),
            "candidate_count": len(labels),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "training_filter": {
                "current_hidden_only": bool(current_hidden_only),
                "excluded_feature_names": excluded_features,
            },
        },
        "metrics": _metrics(labels=labels, predictions=predictions),
    }


def predict_official_candidate_viewpoint_ranker(
    model: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> float:
    feature_names = [str(name) for name in model.get("feature_names", [])]
    weights = [_float(value) for value in model.get("weights", [])]
    if len(weights) < len(feature_names):
        weights.extend(0.0 for _ in range(len(feature_names) - len(weights)))
    preprocessing = model.get("preprocessing", {})
    if not isinstance(preprocessing, Mapping):
        preprocessing = {}
    row = _feature_row(candidate, feature_names)
    values = _standardize(row, feature_names, preprocessing)
    return _sigmoid(_dot(weights[: len(feature_names)], values) + _float(model.get("bias")))


def score_official_candidate_viewpoint_ranker_dataset(
    dataset: Mapping[str, Any],
    model: Mapping[str, Any],
    *,
    current_hidden_only: bool = True,
) -> dict[str, Any]:
    label_name = str(model.get("label_name", LABEL_NAME))
    candidates = _filter_candidates(
        _candidates(dataset),
        current_hidden_only=current_hidden_only,
        label_name=label_name,
    )
    grouped = _group_candidates_by_state(candidates)
    states = [
        _score_state_candidates(state_key, rows, model=model, label_name=label_name)
        for state_key, rows in grouped.items()
    ]
    return {
        "task": "habitat_official_candidate_viewpoint_ranker_scores",
        "model_task": str(model.get("task", "")),
        "label_name": label_name,
        "candidate_count": len(candidates),
        "state_count": len(states),
        "filter": {
            "current_hidden_only": bool(current_hidden_only),
        },
        "aggregate": _score_aggregate(states),
        "states": states,
    }


def evaluate_candidate_viewpoint_ranker_state_folds(
    dataset: Mapping[str, Any],
    *,
    label_name: str = LABEL_NAME,
    fold_count: int = 3,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    l2: float = DEFAULT_L2,
    current_hidden_only: bool = True,
    excluded_feature_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    candidates = _filter_candidates(
        _candidates(dataset),
        current_hidden_only=current_hidden_only,
        label_name=label_name,
    )
    grouped = _group_candidates_by_state(candidates)
    state_items = list(grouped.items())
    safe_fold_count = max(2, int(fold_count))
    folds: list[dict[str, Any]] = []
    for fold_index in range(safe_fold_count):
        holdout_keys = [
            state_key
            for index, (state_key, _rows) in enumerate(state_items)
            if index % safe_fold_count == fold_index
        ]
        train_keys = [
            state_key
            for state_key, _rows in state_items
            if state_key not in holdout_keys
        ]
        train_rows = [row for key in train_keys for row in grouped[key]]
        holdout_rows = [row for key in holdout_keys for row in grouped[key]]
        if not train_rows or not holdout_rows:
            continue
        train_dataset = {**dict(dataset), "candidate_viewpoints": train_rows}
        holdout_dataset = {**dict(dataset), "candidate_viewpoints": holdout_rows}
        model = train_official_candidate_viewpoint_ranker_model(
            train_dataset,
            label_name=label_name,
            current_hidden_only=False,
            excluded_feature_names=excluded_feature_names,
            epochs=epochs,
            learning_rate=learning_rate,
            l2=l2,
        )
        scores = score_official_candidate_viewpoint_ranker_dataset(
            holdout_dataset,
            model,
            current_hidden_only=False,
        )
        folds.append(
            {
                "fold_index": fold_index,
                "train_state_count": len(train_keys),
                "holdout_state_count": len(holdout_keys),
                "train_candidate_count": len(train_rows),
                "holdout_candidate_count": len(holdout_rows),
                "train_state_keys": train_keys,
                "holdout_state_keys": holdout_keys,
                "aggregate": scores["aggregate"],
            }
        )
    return {
        "task": "habitat_official_candidate_viewpoint_ranker_state_folds",
        "label_name": str(label_name),
        "fold_count": safe_fold_count,
        "filter": {
            "current_hidden_only": bool(current_hidden_only),
            "excluded_feature_names": _normalized_feature_names(excluded_feature_names),
        },
        "aggregate": _fold_aggregate(folds),
        "folds": folds,
    }


def evaluate_candidate_viewpoint_ranker_leave_one_source(
    dataset: Mapping[str, Any],
    *,
    label_name: str = LABEL_NAME,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    l2: float = DEFAULT_L2,
    current_hidden_only: bool = True,
    excluded_feature_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    candidates = _filter_candidates(
        _candidates(dataset),
        current_hidden_only=current_hidden_only,
        label_name=label_name,
    )
    sources = sorted({_candidate_source(candidate) for candidate in candidates})
    splits: list[dict[str, Any]] = []
    for holdout_source in sources:
        train_rows = [
            candidate
            for candidate in candidates
            if _candidate_source(candidate) != holdout_source
        ]
        holdout_rows = [
            candidate
            for candidate in candidates
            if _candidate_source(candidate) == holdout_source
        ]
        if not train_rows or not holdout_rows:
            continue
        train_dataset = {**dict(dataset), "candidate_viewpoints": train_rows}
        holdout_dataset = {**dict(dataset), "candidate_viewpoints": holdout_rows}
        model = train_official_candidate_viewpoint_ranker_model(
            train_dataset,
            label_name=label_name,
            current_hidden_only=False,
            excluded_feature_names=excluded_feature_names,
            epochs=epochs,
            learning_rate=learning_rate,
            l2=l2,
        )
        scores = score_official_candidate_viewpoint_ranker_dataset(
            holdout_dataset,
            model,
            current_hidden_only=False,
        )
        splits.append(
            {
                "holdout_source": holdout_source,
                "train_sources": sorted(
                    {_candidate_source(candidate) for candidate in train_rows}
                ),
                "train_candidate_count": len(train_rows),
                "holdout_candidate_count": len(holdout_rows),
                "train_state_count": len(_group_candidates_by_state(train_rows)),
                "holdout_state_count": len(_group_candidates_by_state(holdout_rows)),
                "aggregate": scores["aggregate"],
            }
        )
    return {
        "task": "habitat_official_candidate_viewpoint_ranker_leave_one_source",
        "label_name": str(label_name),
        "split_field": "source_dataset",
        "filter": {
            "current_hidden_only": bool(current_hidden_only),
            "excluded_feature_names": _normalized_feature_names(excluded_feature_names),
        },
        "aggregate": _leave_one_source_aggregate(splits),
        "splits": splits,
    }


def write_official_candidate_viewpoint_ranker_scores_csv(
    report: Mapping[str, Any],
    path: str | Path,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = report.get("states", [])
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_SCORE_CSV_FIELDS)
        writer.writeheader()
        if not isinstance(rows, Sequence):
            return
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            writer.writerow(
                {field: _csv_value(row.get(field)) for field in _SCORE_CSV_FIELDS}
            )


def _score_state_candidates(
    state_key: str,
    candidates: Sequence[Mapping[str, Any]],
    *,
    model: Mapping[str, Any],
    label_name: str,
) -> dict[str, Any]:
    scored = [
        {
            **dict(candidate),
            "prediction": predict_official_candidate_viewpoint_ranker(model, candidate),
            "label_value": bool(_label(candidate, label_name=label_name)),
        }
        for candidate in candidates
    ]
    model_candidate = max(scored, key=lambda row: float(row["prediction"]))
    top_rank_candidate = min(scored, key=lambda row: _int(row.get("candidate_rank")))
    top_score_candidate = max(
        scored,
        key=lambda row: _float(row.get("candidate_score")),
    )
    exemplar = scored[0]
    return {
        "state_key": state_key,
        "source_policy_trace": str(exemplar.get("source_policy_trace", "")),
        "state_index": exemplar.get("state_index"),
        "episode_index": exemplar.get("episode_index"),
        "episode_id": str(exemplar.get("episode_id", "")),
        "scene_id": str(exemplar.get("scene_id", "")),
        "target_category": str(exemplar.get("target_category", "")),
        "step_index": exemplar.get("step_index"),
        "state_action": str(exemplar.get("state_action", "")),
        "state_decision": str(exemplar.get("state_decision", "")),
        "candidate_count": len(scored),
        "oracle_recoverable": any(bool(row["label_value"]) for row in scored),
        "model_recovered": bool(model_candidate["label_value"]),
        "model_candidate_rank": _int(model_candidate.get("candidate_rank")),
        "model_prediction": round(float(model_candidate["prediction"]), 6),
        "top_rank_recovered": bool(top_rank_candidate["label_value"]),
        "top_rank_candidate_rank": _int(top_rank_candidate.get("candidate_rank")),
        "top_score_recovered": bool(top_score_candidate["label_value"]),
        "top_score_candidate_rank": _int(top_score_candidate.get("candidate_rank")),
        "candidates": [
            {
                "candidate_rank": _int(row.get("candidate_rank")),
                "candidate_score": _optional_float(row.get("candidate_score")),
                "prediction": round(float(row["prediction"]), 6),
                "label_value": bool(row["label_value"]),
            }
            for row in scored
        ],
    }


def _candidates(dataset: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = dataset.get("candidate_viewpoints", [])
    if not isinstance(rows, list):
        raise ValueError("dataset candidate_viewpoints must be a list")
    candidates = [row for row in rows if isinstance(row, Mapping)]
    if not candidates:
        raise ValueError("dataset has no candidate viewpoint rows")
    return candidates


def _filter_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    current_hidden_only: bool,
    label_name: str,
) -> list[Mapping[str, Any]]:
    filtered = [
        candidate
        for candidate in candidates
        if _candidate_label_available(candidate)
        and (not current_hidden_only or not _current_visible(candidate))
        and _label(candidate, label_name=label_name) is not None
    ]
    if not filtered:
        raise ValueError("dataset has no label-available candidate rows")
    return filtered


def _candidate_label_available(candidate: Mapping[str, Any]) -> bool:
    labels = _mapping(candidate.get("labels"))
    return bool(labels.get("label_available"))


def _current_visible(candidate: Mapping[str, Any]) -> bool:
    labels = _mapping(candidate.get("labels"))
    return bool(labels.get("current_target_visible_at_restore"))


def _label(candidate: Mapping[str, Any], *, label_name: str) -> float:
    labels = _mapping(candidate.get("labels"))
    return 1.0 if bool(labels.get(label_name)) else 0.0


def _feature_names(
    candidates: Sequence[Mapping[str, Any]],
    *,
    excluded_feature_names: Sequence[str] | None = None,
) -> list[str]:
    state_actions = sorted({_token(candidate.get("state_action")) for candidate in candidates})
    state_decisions = sorted({_token(candidate.get("state_decision")) for candidate in candidates})
    targets = sorted({_token(candidate.get("target_category")) for candidate in candidates})
    state_feature_names = sorted(
        {
            name
            for candidate in candidates
            for name in _numeric_state_features(candidate)
        }
    )
    names = [
        "candidate_rank",
        "candidate_count",
        "candidate_score",
        "expected_evidence",
        "belief_mass",
        "distance_to_anchor_m",
        "bearing_error_rad",
        "abs_bearing_error_rad",
        "view_quality",
        "view_bearing_quality",
        "view_distance_quality",
        "path_distance_m",
        "travel_distance_m",
        "candidate_x_m",
        "candidate_z_m",
        "step_index",
    ]
    names.extend(f"state_action={value}" for value in state_actions)
    names.extend(f"state_decision={value}" for value in state_decisions)
    names.extend(f"target_category={value}" for value in targets)
    names.extend(f"state_feature={name}" for name in state_feature_names)
    excluded = set(_normalized_feature_names(excluded_feature_names))
    return [name for name in names if name not in excluded]


def _normalized_feature_names(names: Sequence[str] | None) -> list[str]:
    if names is None:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for name in names:
        parsed = str(name).strip()
        if not parsed or parsed in seen:
            continue
        normalized.append(parsed)
        seen.add(parsed)
    return normalized


def _feature_row(
    candidate: Mapping[str, Any],
    feature_names: Sequence[str],
) -> dict[str, float]:
    bearing_error = _optional_float(candidate.get("bearing_error_rad"))
    values = {name: 0.0 for name in feature_names}
    numeric_values = {
        "candidate_rank": _optional_float(candidate.get("candidate_rank")),
        "candidate_count": _optional_float(candidate.get("candidate_count")),
        "candidate_score": _optional_float(candidate.get("candidate_score")),
        "expected_evidence": _optional_float(candidate.get("expected_evidence")),
        "belief_mass": _optional_float(candidate.get("belief_mass")),
        "distance_to_anchor_m": _optional_float(candidate.get("distance_to_anchor_m")),
        "bearing_error_rad": bearing_error,
        "abs_bearing_error_rad": abs(bearing_error) if bearing_error is not None else None,
        "view_quality": _optional_float(candidate.get("view_quality")),
        "view_bearing_quality": _optional_float(candidate.get("view_bearing_quality")),
        "view_distance_quality": _optional_float(candidate.get("view_distance_quality")),
        "path_distance_m": _optional_float(candidate.get("path_distance_m")),
        "travel_distance_m": _optional_float(candidate.get("travel_distance_m")),
        "candidate_x_m": _optional_float(candidate.get("candidate_x_m")),
        "candidate_z_m": _optional_float(candidate.get("candidate_z_m")),
        "step_index": _optional_float(candidate.get("step_index")),
    }
    for name, value in numeric_values.items():
        if name in values and value is not None:
            values[name] = value
    for name in (
        f"state_action={_token(candidate.get('state_action'))}",
        f"state_decision={_token(candidate.get('state_decision'))}",
        f"target_category={_token(candidate.get('target_category'))}",
    ):
        if name in values:
            values[name] = 1.0
    for feature_name, feature_value in _numeric_state_features(candidate).items():
        state_feature_name = f"state_feature={feature_name}"
        if state_feature_name in values:
            values[state_feature_name] = feature_value
    return values


def _numeric_state_features(candidate: Mapping[str, Any]) -> dict[str, float]:
    state_features = candidate.get("state_features", {})
    if not isinstance(state_features, Mapping):
        return {}
    parsed: dict[str, float] = {}
    for name, value in state_features.items():
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
    missing_value_count = 0
    warnings: list[str] = []
    for feature_name in feature_names:
        values = [float(row.get(feature_name, 0.0)) for row in rows]
        missing_value_count += sum(1 for row in rows if feature_name not in row)
        if not values:
            means[feature_name] = 0.0
            scales[feature_name] = 1.0
            warnings.append(f"feature {feature_name} has no finite values")
            continue
        mean = sum(values) / float(len(values))
        variance = sum((value - mean) ** 2 for value in values) / float(len(values))
        scale = math.sqrt(variance)
        means[feature_name] = mean
        scales[feature_name] = scale if scale > 1.0e-9 else 1.0
    return {
        "feature_means": means,
        "feature_scales": scales,
        "missing_value_count": missing_value_count,
        "warnings": warnings,
    }


def _standardize(
    row: Mapping[str, float],
    feature_names: Sequence[str],
    preprocessing: Mapping[str, Any],
) -> list[float]:
    means = _mapping(preprocessing.get("feature_means"))
    scales = _mapping(preprocessing.get("feature_scales"))
    return [
        (float(row.get(name, 0.0)) - _float(means.get(name)))
        / max(_float(scales.get(name), default=1.0), 1.0e-9)
        for name in feature_names
    ]


def _group_candidates_by_state(
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for candidate in candidates:
        grouped.setdefault(_state_key(candidate), []).append(candidate)
    return dict(sorted(grouped.items()))


def _state_key(candidate: Mapping[str, Any]) -> str:
    return "|".join(
        str(part)
        for part in (
            candidate.get("source_policy_trace", ""),
            candidate.get("episode_index", ""),
            candidate.get("episode_id", ""),
            candidate.get("step_index", ""),
            candidate.get("state_index", ""),
        )
    )


def _candidate_source(candidate: Mapping[str, Any]) -> str:
    source_dataset = str(candidate.get("source_dataset", ""))
    if source_dataset:
        return source_dataset
    source_policy_trace = str(candidate.get("source_policy_trace", ""))
    return source_policy_trace or "unknown"


def _score_aggregate(states: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    state_count = len(states)
    return {
        "state_count": state_count,
        "oracle_recoverable_state_count": sum(
            1 for state in states if bool(state.get("oracle_recoverable"))
        ),
        "model_recovered_state_count": sum(
            1 for state in states if bool(state.get("model_recovered"))
        ),
        "top_rank_recovered_state_count": sum(
            1 for state in states if bool(state.get("top_rank_recovered"))
        ),
        "top_score_recovered_state_count": sum(
            1 for state in states if bool(state.get("top_score_recovered"))
        ),
    }


def _leave_one_source_aggregate(splits: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    state_count = sum(
        _int(_mapping(split.get("aggregate")).get("state_count"))
        for split in splits
    )
    return {
        "split_count": len(splits),
        "state_count": state_count,
        "oracle_recoverable_state_count": sum(
            _int(_mapping(split.get("aggregate")).get("oracle_recoverable_state_count"))
            for split in splits
        ),
        "model_recovered_state_count": sum(
            _int(_mapping(split.get("aggregate")).get("model_recovered_state_count"))
            for split in splits
        ),
        "top_rank_recovered_state_count": sum(
            _int(_mapping(split.get("aggregate")).get("top_rank_recovered_state_count"))
            for split in splits
        ),
        "top_score_recovered_state_count": sum(
            _int(_mapping(split.get("aggregate")).get("top_score_recovered_state_count"))
            for split in splits
        ),
    }


def _fold_aggregate(folds: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    state_count = sum(_int(_mapping(fold.get("aggregate")).get("state_count")) for fold in folds)
    return {
        "fold_count": len(folds),
        "state_count": state_count,
        "oracle_recoverable_state_count": sum(
            _int(_mapping(fold.get("aggregate")).get("oracle_recoverable_state_count"))
            for fold in folds
        ),
        "model_recovered_state_count": sum(
            _int(_mapping(fold.get("aggregate")).get("model_recovered_state_count"))
            for fold in folds
        ),
        "top_rank_recovered_state_count": sum(
            _int(_mapping(fold.get("aggregate")).get("top_rank_recovered_state_count"))
            for fold in folds
        ),
        "top_score_recovered_state_count": sum(
            _int(_mapping(fold.get("aggregate")).get("top_score_recovered_state_count"))
            for fold in folds
        ),
    }


def _metrics(
    *,
    labels: Sequence[float],
    predictions: Sequence[float],
) -> dict[str, Any]:
    correct = sum(
        1
        for label, prediction in zip(labels, predictions)
        if (prediction >= 0.5) == bool(label)
    )
    count = max(1, len(labels))
    return {
        "candidate_count": len(labels),
        "positive_count": int(sum(labels)),
        "negative_count": len(labels) - int(sum(labels)),
        "accuracy": round(correct / float(count), 6),
        "roc_auc": _rounded_or_none(_roc_auc(labels, predictions)),
        "mean_prediction": round(sum(predictions) / float(count), 6),
    }


def _roc_auc(labels: Sequence[float], predictions: Sequence[float]) -> float | None:
    pairs = sorted(
        (
            (float(prediction), 1 if bool(label) else 0)
            for label, prediction in zip(labels, predictions)
        ),
        key=lambda pair: pair[0],
    )
    positive_count = sum(label for _, label in pairs)
    negative_count = len(pairs) - positive_count
    if positive_count == 0 or negative_count == 0:
        return None
    rank_sum = 0.0
    rank = 1
    index = 0
    while index < len(pairs):
        end = index
        while end < len(pairs) and pairs[end][0] == pairs[index][0]:
            end += 1
        average_rank = (rank + rank + (end - index) - 1) / 2.0
        rank_sum += average_rank * sum(label for _, label in pairs[index:end])
        rank += end - index
        index = end
    return (rank_sum - positive_count * (positive_count + 1) / 2.0) / (
        positive_count * negative_count
    )


def _rounded_or_none(value: float | None) -> float | None:
    return None if value is None else round(value, 6)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _float(value: Any, *, default: float = 0.0) -> float:
    parsed = _optional_float(value)
    return default if parsed is None else parsed


def _int(value: Any, *, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _token(value: Any) -> str:
    token = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "none")).strip("_")
    return token or "none"


def _dot(weights: Sequence[float], row: Sequence[float]) -> float:
    return sum(weight * value for weight, value in zip(weights, row))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _logit(probability: float) -> float:
    safe = _clamp_probability(probability)
    return math.log(safe / (1.0 - safe))


def _clamp_probability(value: float) -> float:
    return min(max(float(value), 1.0e-6), 1.0 - 1.0e-6)


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return value
