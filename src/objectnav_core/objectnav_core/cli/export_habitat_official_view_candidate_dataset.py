from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from objectnav_core.evaluation.habitat_official_view_candidate_dataset import (
    export_official_view_candidate_dataset,
    write_official_view_candidate_dataset_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export active-perception candidate viewpoint examples from "
            "official Habitat ObjectNav policy and detector traces."
        )
    )
    parser.add_argument("policy_trace", help="Path to policy_trace.json")
    parser.add_argument(
        "--detector-trace",
        required=True,
        help="Path to detector_trace.json from the same official run",
    )
    parser.add_argument("--output", required=True, help="Output dataset JSON path")
    parser.add_argument("--csv-output", help="Optional flat candidate CSV path")
    parser.add_argument(
        "--source-run-id",
        help="Optional human-readable run id; defaults to policy trace parent name",
    )
    parser.add_argument(
        "--horizon-steps",
        type=int,
        default=5,
        help="Future same-episode steps used for selected-candidate labels.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset = export_official_view_candidate_dataset(
        args.policy_trace,
        detector_trace_path=args.detector_trace,
        source_run_id=args.source_run_id,
        horizon_steps=args.horizon_steps,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.csv_output:
        write_official_view_candidate_dataset_csv(dataset, args.csv_output)
    print(json.dumps(_console_summary(dataset), ensure_ascii=False, sort_keys=True))
    return 0


def _console_summary(dataset: dict[str, object]) -> dict[str, object]:
    return {
        "task": dataset.get("task"),
        "schema_version": dataset.get("schema_version"),
        "source_run_id": dataset.get("source_run_id"),
        "horizon_steps": dataset.get("horizon_steps"),
        "state_count": dataset.get("state_count"),
        "candidate_count": dataset.get("candidate_count"),
        "selected_candidate_count": dataset.get("selected_candidate_count"),
        "observed_positive_candidate_count": dataset.get(
            "observed_positive_candidate_count"
        ),
        "unobserved_candidate_count": dataset.get("unobserved_candidate_count"),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
