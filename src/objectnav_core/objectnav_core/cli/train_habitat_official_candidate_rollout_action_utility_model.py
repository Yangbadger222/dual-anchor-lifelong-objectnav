from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from objectnav_core.evaluation.habitat_official_candidate_rollout_action_utility_model import (
    DEFAULT_EPOCHS,
    DEFAULT_L2,
    DEFAULT_LEARNING_RATE,
    evaluate_action_utility_leave_one_source,
    score_official_candidate_rollout_action_utility_report,
    train_official_candidate_rollout_action_utility_model,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a cost-aware action utility model from rollout reports."
    )
    parser.add_argument("report")
    parser.add_argument("--output", required=True)
    parser.add_argument("--scores-output", default=None)
    parser.add_argument("--leave-one-source-output", default=None)
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=DEFAULT_LEARNING_RATE)
    parser.add_argument("--l2", type=float, default=DEFAULT_L2)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = _load_report(Path(args.report))
    model = train_official_candidate_rollout_action_utility_model(
        report,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        l2=args.l2,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if args.scores_output:
        scores = score_official_candidate_rollout_action_utility_report(report, model)
        Path(args.scores_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.scores_output).write_text(
            json.dumps(scores, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    if args.leave_one_source_output:
        leave_one_source = evaluate_action_utility_leave_one_source(
            report,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            l2=args.l2,
        )
        Path(args.leave_one_source_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.leave_one_source_output).write_text(
            json.dumps(leave_one_source, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(json.dumps(_summary(model), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def _summary(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": model.get("task"),
        "model_type": model.get("model_type"),
        "dataset": model.get("dataset"),
        "metrics": model.get("metrics"),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
