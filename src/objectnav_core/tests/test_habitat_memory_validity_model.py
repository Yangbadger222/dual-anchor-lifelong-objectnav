from __future__ import annotations

import json
import math
from pathlib import Path

from objectnav_core.evaluation.habitat_memory_validity_model import (
    predict_memory_validity,
    train_memory_validity_logistic_model,
)


def test_memory_validity_logistic_model_separates_synthetic_examples() -> None:
    dataset = _memory_validity_dataset(
        [
            (False, {"memory_evidence_detector_precision": 0.0, "memory_action_count": 18}),
            (False, {"memory_evidence_detector_precision": 0.1, "memory_action_count": 20}),
            (True, {"memory_evidence_detector_precision": 0.9, "memory_action_count": 4}),
            (True, {"memory_evidence_detector_precision": 1.0, "memory_action_count": 3}),
        ],
        feature_names=(
            "memory_evidence_detector_precision",
            "memory_action_count",
        ),
    )

    model = train_memory_validity_logistic_model(
        dataset,
        feature_names=(
            "memory_evidence_detector_precision",
            "memory_action_count",
        ),
        epochs=500,
        learning_rate=0.2,
        l2=0.0,
    )

    invalid_score = predict_memory_validity(
        model,
        {"memory_evidence_detector_precision": 0.0, "memory_action_count": 21},
    )
    valid_score = predict_memory_validity(
        model,
        {"memory_evidence_detector_precision": 0.95, "memory_action_count": 3},
    )
    assert valid_score > invalid_score
    assert valid_score > 0.75
    assert invalid_score < 0.25
    assert model["feature_names"] == [
        "memory_evidence_detector_precision",
        "memory_action_count",
    ]
    assert model["metrics"]["example_count"] == 4
    assert model["metrics"]["positive_count"] == 2
    assert model["metrics"]["negative_count"] == 2
    assert model["metrics"]["accuracy"] == 1.0
    assert model["metrics"]["log_loss"] < 0.4
    assert model["metrics"]["brier_score"] < 0.1


def test_memory_validity_prediction_uses_persisted_imputation_stats() -> None:
    dataset = _memory_validity_dataset(
        [
            (False, {"memory_evidence_detector_precision": 0.0, "memory_action_count": 18}),
            (False, {"memory_evidence_detector_precision": None, "memory_action_count": 20}),
            (True, {"memory_evidence_detector_precision": 1.0, "memory_action_count": 4}),
            (True, {"memory_evidence_detector_precision": 0.9, "memory_action_count": None}),
        ],
        feature_names=(
            "memory_evidence_detector_precision",
            "memory_action_count",
        ),
    )

    model = train_memory_validity_logistic_model(
        dataset,
        epochs=250,
        learning_rate=0.1,
    )
    score_before = predict_memory_validity(
        model,
        {"memory_evidence_detector_precision": 0.8},
    )
    reloaded_model = json.loads(json.dumps(model))
    score_after = predict_memory_validity(
        reloaded_model,
        {"memory_evidence_detector_precision": 0.8},
    )

    assert math.isfinite(score_before)
    assert score_before == score_after
    assert model["preprocessing"]["missing_value_count"] == 2
    assert set(model["preprocessing"]["feature_means"]) == {
        "memory_evidence_detector_precision",
        "memory_action_count",
    }


def test_memory_validity_training_cli_writes_model_report(tmp_path: Path) -> None:
    from objectnav_core.cli.train_habitat_memory_validity_model import main

    dataset = _memory_validity_dataset(
        [
            (False, {"memory_evidence_detector_precision": 0.0, "memory_action_count": 18}),
            (True, {"memory_evidence_detector_precision": 1.0, "memory_action_count": 4}),
        ],
        feature_names=(
            "memory_evidence_detector_precision",
            "memory_action_count",
        ),
    )
    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "model.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    assert (
        main(
            [
                str(dataset_path),
                "--output",
                str(output_path),
                "--features",
                "memory_evidence_detector_precision,memory_action_count",
                "--epochs",
                "50",
            ]
        )
        == 0
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["task"] == "habitat_memory_validity_logistic_model"
    assert report["dataset"]["example_count"] == 2
    assert report["feature_names"] == [
        "memory_evidence_detector_precision",
        "memory_action_count",
    ]
    assert len(report["weights"]) == 2
    assert report["metrics"]["example_count"] == 2


def _memory_validity_dataset(
    rows: list[tuple[bool, dict[str, object]]],
    *,
    feature_names: tuple[str, ...],
) -> dict[str, object]:
    return {
        "task": "habitat_memory_validity_dataset",
        "feature_schema": list(feature_names),
        "example_count": len(rows),
        "examples": [
            {"label_memory_valid": label, "features": features}
            for label, features in rows
        ],
    }
