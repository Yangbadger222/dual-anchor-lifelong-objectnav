from __future__ import annotations

import argparse
import json
from typing import Sequence

from objectnav_core.evaluation.habitat_memory_validity_dataset import DEFAULT_POLICIES
from objectnav_core.evaluation.habitat_memory_validity_model import (
    DEFAULT_EPOCHS,
    DEFAULT_L2,
    DEFAULT_LEARNING_RATE,
)
from objectnav_core.evaluation.habitat_memory_validity_pipeline import (
    run_memory_validity_learning_pipeline,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export, train, evaluate, and score Habitat memory-validity "
            "learning artifacts in one offline pipeline."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="summary.json files or directories recursively containing summary.json",
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--policies", default=",".join(DEFAULT_POLICIES))
    parser.add_argument(
        "--features",
        help="Comma-separated feature names. Defaults to dataset feature_schema.",
    )
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--l2", type=float, default=DEFAULT_L2)
    parser.add_argument("--holdout-field")
    parser.add_argument("--holdout-values")
    parser.add_argument(
        "--skip-decision-sensitivity",
        action="store_true",
        help="Skip fixed/evidence/event-posterior decision-sensitivity mining.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_memory_validity_learning_pipeline(
        args.inputs,
        output_dir=args.output_dir,
        policies=_split_csv(args.policies),
        feature_names=_split_csv(args.features) if args.features else None,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        l2=args.l2,
        holdout_field=args.holdout_field,
        holdout_values=_split_csv(args.holdout_values)
        if args.holdout_values
        else (),
        include_decision_sensitivity=not args.skip_decision_sensitivity,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
