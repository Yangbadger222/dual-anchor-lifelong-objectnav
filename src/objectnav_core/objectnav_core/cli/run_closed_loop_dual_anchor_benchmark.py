from __future__ import annotations

import argparse
from typing import Sequence

from objectnav_core.evaluation.closed_loop_dual_anchor_benchmark import (
    run_closed_loop_dual_anchor_benchmark,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic closed-loop dual-anchor grid benchmark."
    )
    parser.add_argument("--output", required=True, help="Output directory.")
    parser.add_argument(
        "--gate-threshold",
        type=float,
        default=5.991,
        help="Mahalanobis squared acceptance gate.",
    )
    parser.add_argument(
        "--ambiguity-margin",
        type=float,
        default=0.5,
        help="Reject matches when best and second-best distances are this close.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_closed_loop_dual_anchor_benchmark(
        args.output,
        gate_threshold=args.gate_threshold,
        ambiguity_margin=args.ambiguity_margin,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
