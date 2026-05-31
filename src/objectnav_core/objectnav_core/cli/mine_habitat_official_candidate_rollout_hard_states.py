from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from objectnav_core.evaluation.habitat_official_candidate_rollout_hard_state_mining import (
    mine_official_candidate_rollout_hard_states,
    write_official_candidate_rollout_hard_states_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mine hard states from official Habitat action-matrix reports."
    )
    parser.add_argument("report")
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output", default=None)
    parser.add_argument(
        "--baseline-action",
        default="turn_left",
        help="Action to treat as the trivial baseline.",
    )
    parser.add_argument(
        "--include-baseline-ties",
        action="store_true",
        help="Also include states where the baseline is fastest but tied.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = _load_report(Path(args.report))
    mined = mine_official_candidate_rollout_hard_states(
        report,
        baseline_action=args.baseline_action,
        include_baseline_ties=bool(args.include_baseline_ties),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(mined, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if args.csv_output:
        write_official_candidate_rollout_hard_states_csv(mined, args.csv_output)
    print(json.dumps(_summary(mined), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def _summary(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": report.get("task"),
        "baseline_action": report.get("baseline_action"),
        "include_baseline_ties": report.get("include_baseline_ties"),
        "input_state_count": report.get("input_state_count"),
        "hard_state_count": report.get("hard_state_count"),
        "aggregate": report.get("aggregate"),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
