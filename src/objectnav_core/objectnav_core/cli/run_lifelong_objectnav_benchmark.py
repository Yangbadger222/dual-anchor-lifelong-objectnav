from __future__ import annotations

import argparse
import json
from typing import Sequence

from objectnav_core.evaluation.lifelong_objectnav_benchmark import (
    POLICIES,
    run_lifelong_objectnav_benchmark,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the deterministic active lifelong ObjectNav benchmark."
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for summary, report, policy memory DBs, and traces.",
    )
    parser.add_argument(
        "--policies",
        default=",".join(POLICIES),
        help="Comma-separated policies to run: memory_guided,frontier_only.",
    )
    args = parser.parse_args(argv)
    policies = tuple(
        policy.strip()
        for policy in args.policies.split(",")
        if policy.strip()
    )
    summary = run_lifelong_objectnav_benchmark(args.output, policies=policies)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
