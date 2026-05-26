from __future__ import annotations

import argparse
import json
from pathlib import Path

from objectnav_core.evaluation.grid_trace_experiment import run_grid_trace_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the 2D grid trace experiment.")
    parser.add_argument(
        "--output",
        required=True,
        help="Directory where summary.json, events.csv, and trace_report.html will be written.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--episodes", type=int, default=12)
    parser.add_argument("--steps-per-episode", type=int, default=8)
    args = parser.parse_args(argv)

    summary = run_grid_trace_experiment(
        Path(args.output),
        seed=args.seed,
        episodes=args.episodes,
        steps_per_episode=args.steps_per_episode,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
