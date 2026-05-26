from __future__ import annotations

import argparse
import json
from pathlib import Path

from objectnav_core.evaluation.usability_stress import run_usability_stress


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run usability-memory stress tests.")
    parser.add_argument(
        "--output",
        required=True,
        help="Directory where summary.json, decision_boundary.csv, and stress_report.html will be written.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--monte-carlo-runs", type=int, default=200)
    args = parser.parse_args(argv)

    summary = run_usability_stress(
        Path(args.output),
        seed=args.seed,
        monte_carlo_runs=args.monte_carlo_runs,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
