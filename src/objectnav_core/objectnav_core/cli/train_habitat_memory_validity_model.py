from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from objectnav_core.evaluation.habitat_memory_validity_model import (
    DEFAULT_EPOCHS,
    DEFAULT_L2,
    DEFAULT_LEARNING_RATE,
    evaluate_memory_validity_model,
    split_memory_validity_dataset,
    train_memory_validity_logistic_model,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Train a deterministic logistic baseline on exported Habitat "
            "memory-validity examples."
        )
    )
    parser.add_argument("dataset", help="JSON report from the memory-validity exporter")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--features",
        help="Comma-separated feature names. Defaults to dataset feature_schema.",
    )
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--l2", type=float, default=DEFAULT_L2)
    parser.add_argument(
        "--holdout-field",
        help="Example metadata field to reserve for held-out evaluation.",
    )
    parser.add_argument(
        "--holdout-values",
        help="Comma-separated metadata values reserved for held-out evaluation.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_path = Path(args.dataset)
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(dataset, dict):
        raise ValueError("dataset JSON root must be an object")
    training_dataset = dataset
    split_report: dict[str, object] | None = None
    if args.holdout_field or args.holdout_values:
        if not args.holdout_field or not args.holdout_values:
            raise ValueError("--holdout-field and --holdout-values must be used together")
        split_report = split_memory_validity_dataset(
            dataset,
            holdout_field=args.holdout_field,
            holdout_values=_split_csv(args.holdout_values),
        )
        training_dataset = split_report["train"]
    report = train_memory_validity_logistic_model(
        training_dataset,
        feature_names=_split_csv(args.features) if args.features else None,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        l2=args.l2,
    )
    if split_report is not None:
        report["split"] = split_report["split"]
        report["evaluation"] = {
            "train": evaluate_memory_validity_model(split_report["train"], report),
            "holdout": evaluate_memory_validity_model(split_report["holdout"], report),
        }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
