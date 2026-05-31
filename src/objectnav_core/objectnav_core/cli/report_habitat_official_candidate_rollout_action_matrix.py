from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
    build_official_candidate_rollout_action_matrix_report,
    write_official_candidate_rollout_action_matrix_report_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report cost-aware official Habitat candidate rollout action matrices."
    )
    parser.add_argument("datasets", nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output", default=None)
    parser.add_argument(
        "--include-current-visible",
        action="store_true",
        help="Include rows whose branch state already had the target visible.",
    )
    parser.add_argument(
        "--actions",
        default="move_forward,turn_left,turn_right",
        help="Comma-separated action order to summarize.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    datasets = [_load_dataset(Path(path)) for path in args.datasets]
    report = build_official_candidate_rollout_action_matrix_report(
        datasets,
        current_hidden_only=not bool(args.include_current_visible),
        actions=_split_csv(args.actions),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if args.csv_output:
        write_official_candidate_rollout_action_matrix_report_csv(
            report,
            args.csv_output,
        )
    print(json.dumps(_summary(report), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _load_dataset(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    payload = dict(payload)
    payload["source_dataset_path"] = str(path)
    return payload


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": report.get("task"),
        "dataset_count": report.get("dataset_count"),
        "current_hidden_only": report.get("current_hidden_only"),
        "state_count": report.get("state_count"),
        "rollout_count": report.get("rollout_count"),
        "aggregate": report.get("aggregate"),
    }


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in str(raw).split(",") if part.strip())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
