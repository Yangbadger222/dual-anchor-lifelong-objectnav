from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from objectnav_core.evaluation.habitat_official_view_recall_model import (
    score_official_view_recall_dataset,
    write_official_view_recall_scores_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a trained official ObjectNav view-recall model to exported "
            "view-recall examples and score candidate action rankings."
        )
    )
    parser.add_argument("dataset", help="JSON report from the view-recall exporter")
    parser.add_argument("--model", required=True, help="JSON view-recall model")
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output")
    parser.add_argument(
        "--actions",
        default="move_forward,turn_left,turn_right",
        help="Comma-separated candidate actions to score.",
    )
    parser.add_argument(
        "--include-current-visible",
        action="store_true",
        help=(
            "Score rows where the target is already visible. By default the "
            "report includes only current-hidden examples."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset_path = Path(args.dataset)
    model_path = Path(args.model)
    dataset = _load_json_object(dataset_path, kind="dataset")
    model = _load_json_object(model_path, kind="model")
    actions = _split_csv(args.actions)
    report = score_official_view_recall_dataset(
        dataset,
        model,
        actions=actions,
        current_hidden_only=not bool(args.include_current_visible),
    )
    report["source_dataset"] = str(dataset_path)
    report["source_model"] = str(model_path)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.csv_output:
        write_official_view_recall_scores_csv(
            args.csv_output,
            report["rows"],
            candidate_actions=report["candidate_actions"],
        )
    print(json.dumps(_console_summary(report), ensure_ascii=False, sort_keys=True))
    return 0


def _load_json_object(path: str | Path, *, kind: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{kind} JSON root must be an object")
    return payload


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _console_summary(report: dict[str, object]) -> dict[str, object]:
    return {
        "task": report.get("task"),
        "label_name": report.get("label_name"),
        "candidate_actions": report.get("candidate_actions"),
        "source_example_count": report.get("source_example_count"),
        "example_count": report.get("example_count"),
        "filter": report.get("filter"),
        "metrics": report.get("metrics"),
        "aggregate": report.get("aggregate"),
        "source_dataset": report.get("source_dataset"),
        "source_model": report.get("source_model"),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
