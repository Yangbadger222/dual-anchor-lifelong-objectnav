from __future__ import annotations

import argparse
from typing import Sequence

from objectnav_core.evaluation.dual_anchor_pressure import (
    DualAnchorPressureCase,
    run_dual_anchor_matching_pressure_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a deterministic dual-anchor Mahalanobis matching pressure test."
    )
    parser.add_argument("--output", required=True, help="Output directory.")
    parser.add_argument(
        "--gate-threshold",
        type=float,
        default=5.991,
        help="Chi-square style Mahalanobis squared acceptance gate.",
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
    run_dual_anchor_matching_pressure_report(
        args.output,
        cases=_default_cases(),
        gate_threshold=args.gate_threshold,
        ambiguity_margin=args.ambiguity_margin,
    )
    return 0


def _default_cases() -> tuple[DualAnchorPressureCase, ...]:
    return (
        DualAnchorPressureCase(
            name="clear_match_low_drift",
            observed_xy=(0.2, 0.0),
            candidate_xy={"target": (0.0, 0.0), "distractor": (3.0, 0.0)},
            covariance_scale=0.2,
        ),
        DualAnchorPressureCase(
            name="ambiguous_same_class_instances",
            observed_xy=(1.0, 0.0),
            candidate_xy={"left": (0.9, 0.0), "right": (1.1, 0.0)},
            covariance_scale=0.2,
        ),
        DualAnchorPressureCase(
            name="outside_gate_high_drift",
            observed_xy=(5.0, 0.0),
            candidate_xy={"target": (0.0, 0.0)},
            covariance_scale=0.1,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
