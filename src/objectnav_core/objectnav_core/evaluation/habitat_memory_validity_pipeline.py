from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from objectnav_core.evaluation.habitat_memory_validity_dataset import (
    DEFAULT_POLICIES,
    export_habitat_memory_validity_dataset,
    write_memory_validity_dataset_csv,
)
from objectnav_core.evaluation.habitat_memory_validity_model import (
    DEFAULT_EPOCHS,
    DEFAULT_L2,
    DEFAULT_LEARNING_RATE,
    evaluate_memory_validity_model,
    score_memory_validity_decisions,
    split_memory_validity_dataset,
    train_memory_validity_logistic_model,
    write_memory_validity_decision_scores_csv,
)


def run_memory_validity_learning_pipeline(
    inputs: Sequence[str | Path],
    *,
    output_dir: str | Path,
    policies: Sequence[str] = DEFAULT_POLICIES,
    feature_names: Sequence[str] | None = None,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    l2: float = DEFAULT_L2,
    holdout_field: str | None = None,
    holdout_values: Sequence[str] = (),
) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    dataset_json = output_path / "dataset.json"
    dataset_csv = output_path / "examples.csv"
    model_json = output_path / "model.json"
    scores_json = output_path / "scores.json"
    scores_csv = output_path / "scores.csv"
    pipeline_report_json = output_path / "pipeline_report.json"

    dataset = export_habitat_memory_validity_dataset(inputs, policies=policies)
    _write_json(dataset_json, dataset)
    write_memory_validity_dataset_csv(dataset_csv, dataset["examples"])

    training_dataset: dict[str, Any] = dataset
    split_report: dict[str, Any] | None = None
    if holdout_field or holdout_values:
        if not holdout_field or not holdout_values:
            raise ValueError("holdout_field and holdout_values must be used together")
        split_report = split_memory_validity_dataset(
            dataset,
            holdout_field=holdout_field,
            holdout_values=holdout_values,
        )
        training_dataset = split_report["train"]

    model = train_memory_validity_logistic_model(
        training_dataset,
        feature_names=feature_names,
        epochs=epochs,
        learning_rate=learning_rate,
        l2=l2,
    )
    if split_report is not None:
        model["split"] = split_report["split"]
        model["evaluation"] = {
            "train": evaluate_memory_validity_model(split_report["train"], model),
            "holdout": evaluate_memory_validity_model(split_report["holdout"], model),
        }
    _write_json(model_json, model)

    scores = score_memory_validity_decisions(dataset, model)
    _write_json(scores_json, scores)
    write_memory_validity_decision_scores_csv(scores_csv, scores["rows"])

    report = {
        "task": "habitat_memory_validity_learning_pipeline",
        "inputs": [str(input_path) for input_path in inputs],
        "artifacts": {
            "dataset_json": str(dataset_json),
            "dataset_csv": str(dataset_csv),
            "model_json": str(model_json),
            "scores_json": str(scores_json),
            "scores_csv": str(scores_csv),
            "pipeline_report_json": str(pipeline_report_json),
        },
        "dataset": {
            "summary_count": dataset["summary_count"],
            "row_count": dataset["row_count"],
            "example_count": dataset["example_count"],
            "label_counts": dataset["label_counts"],
            "skipped_count": dataset["skipped_count"],
        },
        "model": {
            "feature_names": model["feature_names"],
            "metrics": model["metrics"],
            "split": model.get("split"),
            "evaluation": model.get("evaluation"),
        },
        "scores": {
            "example_count": scores["example_count"],
            "skipped_count": scores["skipped_count"],
            "aggregate": scores["aggregate"],
        },
    }
    _write_json(pipeline_report_json, report)
    return report


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
