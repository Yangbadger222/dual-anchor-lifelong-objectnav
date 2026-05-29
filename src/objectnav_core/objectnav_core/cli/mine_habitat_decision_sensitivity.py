from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from objectnav_core.evaluation.habitat_decision_sensitivity import (
    DEFAULT_MAX_MARGIN_ACTIONS,
    DEFAULT_MAX_RELIABILITY_INTERVAL_GAP,
    DEFAULT_MIN_DETECTOR_EVENT_COUNT,
    DEFAULT_MIN_RELIABILITY_DELTA,
    DEFAULT_POLICIES,
    mine_habitat_decision_sensitivity,
    write_decision_sensitivity_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mine Habitat closed-loop summary.json artifacts for "
            "memory-vs-frontier decision-sensitive rows."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="summary.json files or directories recursively containing summary.json",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output")
    parser.add_argument("--top-k", type=int)
    parser.add_argument(
        "--max-margin-actions",
        type=float,
        default=DEFAULT_MAX_MARGIN_ACTIONS,
    )
    parser.add_argument(
        "--min-detector-event-count",
        type=int,
        default=DEFAULT_MIN_DETECTOR_EVENT_COUNT,
    )
    parser.add_argument(
        "--min-reliability-delta",
        type=float,
        default=DEFAULT_MIN_RELIABILITY_DELTA,
    )
    parser.add_argument(
        "--max-reliability-interval-gap",
        type=float,
        default=DEFAULT_MAX_RELIABILITY_INTERVAL_GAP,
    )
    parser.add_argument("--policies", default=",".join(DEFAULT_POLICIES))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = mine_habitat_decision_sensitivity(
        args.inputs,
        max_margin_actions=args.max_margin_actions,
        min_detector_event_count=args.min_detector_event_count,
        min_reliability_delta=args.min_reliability_delta,
        max_reliability_interval_gap=args.max_reliability_interval_gap,
        policies=_split_csv(args.policies),
        top_k=args.top_k,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.csv_output:
        write_decision_sensitivity_csv(args.csv_output, report["candidates"])
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
