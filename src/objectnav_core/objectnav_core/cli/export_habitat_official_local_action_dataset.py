from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from objectnav_core.evaluation.habitat_official_local_action_dataset import (
    export_official_local_action_dataset,
    write_official_local_action_dataset_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export self-supervised local action-effect examples from official "
            "Habitat ObjectNav policy and detector traces."
        )
    )
    parser.add_argument("policy_trace", help="Path to policy_trace.json")
    parser.add_argument(
        "--detector-trace",
        required=True,
        help="Path to detector_trace.json from the same official run",
    )
    parser.add_argument("--output", required=True, help="Output dataset JSON path")
    parser.add_argument("--csv-output", help="Optional flat examples CSV path")
    parser.add_argument(
        "--source-run-id",
        help="Optional human-readable run id; defaults to policy trace parent name",
    )
    parser.add_argument(
        "--history-steps",
        type=int,
        default=1,
        help="Number of previous consecutive same-episode steps used for features.",
    )
    parser.add_argument(
        "--horizon-steps",
        type=int,
        default=1,
        help="Number of future consecutive same-episode steps used for labels.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = export_official_local_action_dataset(
        args.policy_trace,
        detector_trace_path=args.detector_trace,
        source_run_id=args.source_run_id,
        history_steps=args.history_steps,
        horizon_steps=args.horizon_steps,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.csv_output:
        write_official_local_action_dataset_csv(report, args.csv_output)
    print(json.dumps(_console_summary(report), ensure_ascii=False, sort_keys=True))
    return 0


def _console_summary(report: dict[str, object]) -> dict[str, object]:
    return {
        "task": report.get("task"),
        "schema_version": report.get("schema_version"),
        "source_run_id": report.get("source_run_id"),
        "history_steps": report.get("history_steps"),
        "horizon_steps": report.get("horizon_steps"),
        "step_count": report.get("step_count"),
        "example_count": report.get("example_count"),
        "visible_before_count": report.get("visible_before_count"),
        "visible_after_count": report.get("visible_after_count"),
        "transition_counts": report.get("transition_counts"),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
