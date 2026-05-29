from __future__ import annotations

import argparse
from typing import Sequence

from objectnav_core.evaluation.habitat_closed_loop_dual_anchor_objectnav import (
    DEFAULT_AMBIGUITY_MARGIN,
    DEFAULT_GATE_THRESHOLD,
    DEFAULT_FRONTIER_PROXY_WAYPOINTS,
    DEFAULT_MAX_GROUPS,
    DEFAULT_MEMORY_VALID_PRIOR,
    DEFAULT_QUERY_REPEATS,
    DEFAULT_SENSOR_HEIGHT,
    DEFAULT_SENSOR_WIDTH,
    DEFAULT_CHALLENGE,
    POLICIES,
    SUPPORTED_CHALLENGES,
    TARGET_CATEGORIES,
    run_habitat_closed_loop_dual_anchor_objectnav,
    run_habitat_closed_loop_dual_anchor_preflight,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or preflight Habitat closed-loop dual-anchor ObjectNav smoke."
    )
    parser.add_argument(
        "--dataset-dir",
        default="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
    )
    parser.add_argument(
        "--scene-root",
        default="datasets/habitat/scene_datasets/hm3d",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--target-categories",
        default=",".join(TARGET_CATEGORIES),
    )
    parser.add_argument("--policies", default=",".join(POLICIES))
    parser.add_argument("--max-groups", type=int, default=DEFAULT_MAX_GROUPS)
    parser.add_argument("--sensor-width", type=int, default=DEFAULT_SENSOR_WIDTH)
    parser.add_argument("--sensor-height", type=int, default=DEFAULT_SENSOR_HEIGHT)
    parser.add_argument("--gate-threshold", type=float, default=DEFAULT_GATE_THRESHOLD)
    parser.add_argument("--ambiguity-margin", type=float, default=DEFAULT_AMBIGUITY_MARGIN)
    parser.add_argument(
        "--frontier-proxy-waypoints",
        type=int,
        default=DEFAULT_FRONTIER_PROXY_WAYPOINTS,
    )
    parser.add_argument("--query-repeats", type=int, default=DEFAULT_QUERY_REPEATS)
    parser.add_argument(
        "--memory-valid-prior",
        type=float,
        default=DEFAULT_MEMORY_VALID_PRIOR,
        help=(
            "Prior probability that an unconfirmed memory anchor is still valid "
            "for expected-utility memory-vs-frontier decisions."
        ),
    )
    parser.add_argument("--challenge", default=DEFAULT_CHALLENGE, choices=SUPPORTED_CHALLENGES)
    parser.add_argument("--preflight-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run = (
        run_habitat_closed_loop_dual_anchor_preflight
        if args.preflight_only
        else run_habitat_closed_loop_dual_anchor_objectnav
    )
    run(
        args.output,
        dataset_dir=args.dataset_dir,
        scene_root=args.scene_root,
        target_categories=_split_csv(args.target_categories),
        policies=_split_csv(args.policies),
        max_groups=args.max_groups,
        sensor_width=args.sensor_width,
        sensor_height=args.sensor_height,
        gate_threshold=args.gate_threshold,
        ambiguity_margin=args.ambiguity_margin,
        frontier_proxy_waypoints=args.frontier_proxy_waypoints,
        challenge=args.challenge,
        query_repeats=args.query_repeats,
        memory_valid_prior=args.memory_valid_prior,
    )
    return 0


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


if __name__ == "__main__":
    raise SystemExit(main())
