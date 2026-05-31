from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from objectnav_core.evaluation.habitat_official_local_action_model import (
    DEFAULT_EPOCHS,
    DEFAULT_L2,
    DEFAULT_LEARNING_RATE,
    train_official_local_action_logistic_model,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Train a deterministic logistic local action-effect scorer from "
            "official ObjectNav action-effect examples."
        )
    )
    parser.add_argument("dataset", help="JSON report from the local action exporter")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--features",
        help="Comma-separated feature names. Defaults to the built-in safe schema.",
    )
    parser.add_argument(
        "--label",
        default="next_target_visible",
        help="Boolean label field under each example's labels object.",
    )
    parser.add_argument(
        "--current-visible-only",
        action="store_true",
        help="Train only on examples where features.current_target_visible is true.",
    )
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--l2", type=float, default=DEFAULT_L2)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_path = Path(args.dataset)
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(dataset, dict):
        raise ValueError("dataset JSON root must be an object")
    report = train_official_local_action_logistic_model(
        dataset,
        feature_names=_split_csv(args.features) if args.features else None,
        label_name=args.label,
        current_visible_only=bool(args.current_visible_only),
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        l2=args.l2,
    )
    report["source_dataset"] = str(dataset_path)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_console_summary(report), ensure_ascii=False, sort_keys=True))
    return 0


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _console_summary(report: dict[str, object]) -> dict[str, object]:
    return {
        "task": report.get("task"),
        "label_name": report.get("label_name"),
        "dataset": report.get("dataset"),
        "metrics": report.get("metrics"),
        "source_dataset": report.get("source_dataset"),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
