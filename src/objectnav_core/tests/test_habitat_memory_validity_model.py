from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from objectnav_core.evaluation.habitat_memory_validity_model import (
    predict_memory_validity,
    score_memory_validity_decisions,
    train_memory_validity_logistic_model,
    write_memory_validity_decision_scores_csv,
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


def test_memory_validity_scorer_reports_learned_decision_flips() -> None:
    report = score_memory_validity_decisions(
        _decision_dataset(),
        _deterministic_precision_model(),
    )

    assert report["task"] == "habitat_memory_validity_decision_scores"
    assert report["example_count"] == 2
    assert report["aggregate"]["learned_memory_first_count"] == 1
    assert report["aggregate"]["learned_frontier_first_count"] == 1
    assert report["aggregate"]["decision_flip_count"] == 1
    assert report["aggregate"]["boundary_region_counts"] == {
        "reliability_sensitive": 2
    }
    memory_row = report["rows"][0]
    frontier_row = report["rows"][1]
    assert memory_row["learned_decision"] == "memory_first"
    assert memory_row["decision_flip_from_aux"] is True
    assert memory_row["decision_boundary_region"] == "reliability_sensitive"
    assert memory_row["decision_boundary_reliability_raw"] == 0.6
    assert memory_row["learned_expected_memory_first_action_count"] < (
        memory_row["learned_expected_frontier_first_action_count"]
    )
    assert frontier_row["learned_decision"] == "frontier_first"
    assert frontier_row["decision_flip_from_aux"] is False


def test_memory_validity_score_csv_writer(tmp_path: Path) -> None:
    report = score_memory_validity_decisions(
        _decision_dataset(),
        _deterministic_precision_model(),
    )
    csv_path = tmp_path / "scores.csv"

    write_memory_validity_decision_scores_csv(csv_path, report["rows"])

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["group_id"] == "scene|toilet|relocated:old->new"
    assert rows[0]["learned_decision"] == "memory_first"
    assert rows[0]["decision_flip_from_aux"] == "True"
    assert rows[0]["decision_boundary_reliability_raw"] == "0.6"


def test_memory_validity_score_cli_writes_json_and_csv(tmp_path: Path) -> None:
    from objectnav_core.cli.score_habitat_memory_validity_model import main

    dataset_path = tmp_path / "dataset.json"
    model_path = tmp_path / "model.json"
    output_path = tmp_path / "scores.json"
    csv_path = tmp_path / "scores.csv"
    dataset_path.write_text(json.dumps(_decision_dataset()), encoding="utf-8")
    model_path.write_text(
        json.dumps(_deterministic_precision_model()),
        encoding="utf-8",
    )

    assert (
        main(
            [
                str(dataset_path),
                "--model",
                str(model_path),
                "--output",
                str(output_path),
                "--csv-output",
                str(csv_path),
            ]
        )
        == 0
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["example_count"] == 2
    assert report["aggregate"]["decision_flip_count"] == 1
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[1]["learned_decision"] == "frontier_first"


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


def _decision_dataset() -> dict[str, object]:
    return {
        "task": "habitat_memory_validity_dataset",
        "feature_schema": [
            "memory_evidence_detector_precision",
            "memory_action_count",
            "fallback_action_count",
            "fallback_from_memory_action_count",
        ],
        "example_count": 2,
        "examples": [
            {
                "source_summary": "/tmp/ranked/summary.json",
                "run_id": "ranked",
                "group_id": "scene|toilet|relocated:old->new",
                "category": "toilet",
                "label_memory_valid": True,
                "aux_memory_decision": "frontier_first",
                "features": {
                    "memory_evidence_detector_precision": 1.0,
                    "memory_action_count": 10,
                    "fallback_action_count": 30,
                    "fallback_from_memory_action_count": 50,
                },
            },
            {
                "source_summary": "/tmp/ranked/summary.json",
                "run_id": "ranked",
                "group_id": "scene|chair|relocated:old->new",
                "category": "chair",
                "label_memory_valid": False,
                "aux_memory_decision": "frontier_first",
                "features": {
                    "memory_evidence_detector_precision": 0.0,
                    "memory_action_count": 10,
                    "fallback_action_count": 30,
                    "fallback_from_memory_action_count": 50,
                },
            },
        ],
    }


def _deterministic_precision_model() -> dict[str, object]:
    return {
        "task": "habitat_memory_validity_logistic_model",
        "model_type": "logistic_regression",
        "feature_names": ["memory_evidence_detector_precision"],
        "weights": [4.0],
        "bias": 0.0,
        "preprocessing": {
            "feature_means": {"memory_evidence_detector_precision": 0.5},
            "feature_scales": {"memory_evidence_detector_precision": 0.5},
            "missing_value_count": 0,
            "warnings": [],
        },
    }
