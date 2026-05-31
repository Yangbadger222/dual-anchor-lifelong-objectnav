from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from objectnav_core.evaluation.habitat_official_candidate_viewpoint_ranker_model import (
    DEFAULT_EPOCHS,
    DEFAULT_L2,
    DEFAULT_LEARNING_RATE,
    LABEL_NAME,
    evaluate_candidate_viewpoint_ranker_leave_one_source,
    evaluate_candidate_viewpoint_ranker_state_folds,
    score_official_candidate_viewpoint_ranker_dataset,
    train_official_candidate_viewpoint_ranker_model,
    write_official_candidate_viewpoint_ranker_scores_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Train a deterministic candidate-viewpoint ranker from official "
            "ObjectNav candidate-viewpoint restore labels."
        )
    )
    parser.add_argument(
        "datasets",
        nargs="+",
        help="One or more JSON candidate-viewpoint restore datasets",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--scores-output", default=None)
    parser.add_argument("--csv-output", default=None)
    parser.add_argument("--state-fold-output", default=None)
    parser.add_argument("--leave-one-source-output", default=None)
    parser.add_argument("--fold-count", type=int, default=3)
    parser.add_argument(
        "--label",
        default=LABEL_NAME,
        help="Boolean label field under each candidate row's labels object.",
    )
    parser.add_argument(
        "--include-current-visible",
        action="store_true",
        help=(
            "Include rows where the restored current view already sees the "
            "target. By default only current-hidden states are used."
        ),
    )
    parser.add_argument(
        "--exclude-feature",
        action="append",
        default=[],
        help=(
            "Feature name to exclude from training. May be repeated for "
            "feature ablations."
        ),
    )
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--l2", type=float, default=DEFAULT_L2)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_paths = [Path(path) for path in args.datasets]
    dataset = _load_datasets(dataset_paths)
    current_hidden_only = not bool(args.include_current_visible)
    model = train_official_candidate_viewpoint_ranker_model(
        dataset,
        label_name=args.label,
        current_hidden_only=current_hidden_only,
        excluded_feature_names=args.exclude_feature,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        l2=args.l2,
    )
    model["source_datasets"] = [str(path) for path in dataset_paths]
    if len(dataset_paths) == 1:
        model["source_dataset"] = str(dataset_paths[0])
    _write_json(Path(args.output), model)

    scores: dict[str, Any] | None = None
    if args.scores_output or args.csv_output:
        scores = score_official_candidate_viewpoint_ranker_dataset(
            dataset,
            model,
            current_hidden_only=current_hidden_only,
        )
        scores["source_datasets"] = [str(path) for path in dataset_paths]
        if len(dataset_paths) == 1:
            scores["source_dataset"] = str(dataset_paths[0])
    if args.scores_output and scores is not None:
        _write_json(Path(args.scores_output), scores)
    if args.csv_output and scores is not None:
        write_official_candidate_viewpoint_ranker_scores_csv(
            scores,
            Path(args.csv_output),
        )
    if args.state_fold_output:
        folds = evaluate_candidate_viewpoint_ranker_state_folds(
            dataset,
            label_name=args.label,
            fold_count=args.fold_count,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            l2=args.l2,
            current_hidden_only=current_hidden_only,
            excluded_feature_names=args.exclude_feature,
        )
        folds["source_datasets"] = [str(path) for path in dataset_paths]
        if len(dataset_paths) == 1:
            folds["source_dataset"] = str(dataset_paths[0])
        _write_json(Path(args.state_fold_output), folds)
    if args.leave_one_source_output:
        leave_one_source = evaluate_candidate_viewpoint_ranker_leave_one_source(
            dataset,
            label_name=args.label,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            l2=args.l2,
            current_hidden_only=current_hidden_only,
            excluded_feature_names=args.exclude_feature,
        )
        leave_one_source["source_datasets"] = [str(path) for path in dataset_paths]
        if len(dataset_paths) == 1:
            leave_one_source["source_dataset"] = str(dataset_paths[0])
        _write_json(Path(args.leave_one_source_output), leave_one_source)

    print(json.dumps(_summary(model), ensure_ascii=False, sort_keys=True))
    return 0


def _load_datasets(paths: Sequence[Path]) -> dict[str, Any]:
    if not paths:
        raise ValueError("at least one dataset path is required")
    loaded = [_load_dataset(path) for path in paths]
    rows: list[dict[str, Any]] = []
    for path, dataset in zip(paths, loaded):
        dataset_rows = dataset.get("candidate_viewpoints", [])
        if not isinstance(dataset_rows, list):
            raise ValueError(f"{path} candidate_viewpoints must be a list")
        for row in dataset_rows:
            if not isinstance(row, Mapping):
                continue
            tagged = dict(row)
            tagged["source_dataset"] = str(path)
            rows.append(tagged)
    merged = dict(loaded[0])
    merged["candidate_viewpoints"] = rows
    merged["candidate_viewpoint_count"] = len(rows)
    merged["source_dataset_count"] = len(paths)
    merged["source_datasets"] = [str(path) for path in paths]
    return merged


def _load_dataset(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _summary(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": model.get("task"),
        "model_type": model.get("model_type"),
        "label_name": model.get("label_name"),
        "dataset": model.get("dataset"),
        "metrics": model.get("metrics"),
        "source_dataset": model.get("source_dataset"),
        "source_datasets": model.get("source_datasets"),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
