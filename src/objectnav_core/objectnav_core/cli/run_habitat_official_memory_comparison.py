from __future__ import annotations

import argparse
import json
from typing import Any, Callable, Sequence

from objectnav_core.cli.run_habitat_official_objectnav_eval import (
    DEFAULT_OBJECTNAV_CATEGORIES,
    SUPPORTED_QUERY_DETECTORS,
    _build_detector,
    _parse_categories,
)
from objectnav_core.evaluation.habitat_official_memory_comparison import (
    DEFAULT_COMPARISON_SPECS,
    compare_official_memory_summaries,
    run_habitat_official_memory_comparison,
)
from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    SUPPORTED_OFFICIAL_POLICIES,
    SUPPORTED_TARGETNAV_BACKENDS,
    run_habitat_official_objectnav_eval,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or aggregate official Habitat memory baseline SR/SPL tables."
    )
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--from-summary",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help=(
            "Aggregate an existing official summary instead of running Habitat. "
            "Provide memory_guided=..., no_memory=..., and naive_count=...."
        ),
    )
    parser.add_argument(
        "--config-path",
        default=(
            "third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/"
            "objectnav/objectnav_hm3d.yaml"
        ),
    )
    parser.add_argument(
        "--dataset-data-path",
        default=(
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/"
            "val_mini/val_mini.json.gz"
        ),
    )
    parser.add_argument("--scene-root", default="datasets/habitat/scene_datasets/hm3d")
    parser.add_argument("--split", default="val_mini")
    parser.add_argument("--max-episodes", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument("--validate-habitat", action="store_true")
    parser.add_argument("--memory-guided-prior-path", default=None)
    parser.add_argument("--naive-count-prior-path", default=None)
    parser.add_argument(
        "--memory-guided-policy",
        choices=SUPPORTED_OFFICIAL_POLICIES,
        default=DEFAULT_COMPARISON_SPECS["memory_guided"].policy,
    )
    parser.add_argument(
        "--no-memory-policy",
        choices=SUPPORTED_OFFICIAL_POLICIES,
        default=DEFAULT_COMPARISON_SPECS["no_memory"].policy,
    )
    parser.add_argument(
        "--naive-count-policy",
        choices=SUPPORTED_OFFICIAL_POLICIES,
        default=DEFAULT_COMPARISON_SPECS["naive_count"].policy,
    )
    parser.add_argument("--memory-stop-radius-m", type=float, default=0.35)
    parser.add_argument("--memory-bearing-tolerance-deg", type=float, default=20.0)
    parser.add_argument("--memory-min-confidence", type=float, default=0.0)
    parser.add_argument(
        "--detector",
        choices=SUPPORTED_QUERY_DETECTORS,
        default="none",
        help="Optional detector shared by memory policies during run mode.",
    )
    parser.add_argument(
        "--detector-weights",
        default=None,
        help="Detector weights or model id. If omitted, the default is detector-specific.",
    )
    parser.add_argument("--detector-conf", type=float, default=0.25)
    parser.add_argument("--detector-device", default="auto")
    parser.add_argument("--target-detector-min-confidence", type=float, default=0.25)
    parser.add_argument(
        "--categories",
        default=",".join(DEFAULT_OBJECTNAV_CATEGORIES),
        help="Comma-separated detector prompt/category labels.",
    )
    parser.add_argument("--grounding-dino-text-threshold", type=float, default=0.25)
    parser.add_argument("--grounding-dino-max-image-side", type=int, default=None)
    parser.add_argument(
        "--detector-center-direction-sign",
        type=int,
        choices=(-1, 1),
        default=1,
    )
    parser.add_argument("--local-action-model-path", default=None)
    parser.add_argument("--candidate-viewpoint-ranker-model-path", default=None)
    parser.add_argument("--pathfinder-suffix-goal-radius-m", type=float, default=1.0)
    parser.add_argument(
        "--targetnav-backend",
        choices=SUPPORTED_TARGETNAV_BACKENDS,
        default="oracle_follower",
        help=(
            "Shared TargetNav backend for targetnav-equated memory comparisons. "
            "Use oracle_follower for diagnostic sim comparisons matching Nav2 handoff."
        ),
    )
    parser.add_argument("--targetnav-ddppo-checkpoint-path", default=None)
    parser.add_argument("--targetnav-ddppo-device", default="auto")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    detector_factory: Callable[..., Any] | None = None,
    runner: Callable[..., dict[str, Any]] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.from_summary:
        summary_paths = _parse_from_summary(args.from_summary, parser=parser)
        report = compare_official_memory_summaries(args.output, summary_paths)
    else:
        categories = _parse_categories(args.categories, parser=parser)
        detector = _build_detector(args, categories, detector_factory)
        report = run_habitat_official_memory_comparison(
            args.output,
            config_path=args.config_path,
            dataset_data_path=args.dataset_data_path,
            scene_root=args.scene_root,
            split=args.split,
            max_episodes=args.max_episodes,
            max_steps=args.max_steps,
            seed=args.seed,
            validate_habitat=args.validate_habitat,
            memory_guided_prior_path=args.memory_guided_prior_path,
            naive_count_prior_path=args.naive_count_prior_path,
            memory_guided_policy=args.memory_guided_policy,
            no_memory_policy=args.no_memory_policy,
            naive_count_policy=args.naive_count_policy,
            memory_stop_radius_m=args.memory_stop_radius_m,
            memory_bearing_tolerance_deg=args.memory_bearing_tolerance_deg,
            memory_min_confidence=args.memory_min_confidence,
            target_detector_adapter=detector,
            target_detector_min_confidence=args.target_detector_min_confidence,
            detector_center_direction_sign=args.detector_center_direction_sign,
            local_action_model_path=args.local_action_model_path,
            candidate_viewpoint_ranker_model_path=(
                args.candidate_viewpoint_ranker_model_path
            ),
            pathfinder_suffix_goal_radius_m=args.pathfinder_suffix_goal_radius_m,
            targetnav_backend=args.targetnav_backend,
            targetnav_ddppo_checkpoint_path=args.targetnav_ddppo_checkpoint_path,
            targetnav_ddppo_device=args.targetnav_ddppo_device,
            runner=runner or run_habitat_official_objectnav_eval,
        )

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _parse_from_summary(
    raw_items: Sequence[str],
    *,
    parser: argparse.ArgumentParser,
) -> dict[str, str]:
    summaries: dict[str, str] = {}
    for raw in raw_items:
        if "=" not in raw:
            parser.error("--from-summary must use LABEL=PATH")
        label, path = raw.split("=", 1)
        label = label.strip()
        path = path.strip()
        if not label or not path:
            parser.error("--from-summary must use non-empty LABEL=PATH")
        if label in summaries:
            parser.error(f"duplicate --from-summary label: {label}")
        summaries[label] = path
    return summaries


if __name__ == "__main__":
    raise SystemExit(main())
