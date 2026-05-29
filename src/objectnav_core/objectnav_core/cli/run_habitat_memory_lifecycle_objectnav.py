from __future__ import annotations

import argparse
import json
from typing import Sequence

from objectnav_core.evaluation.habitat_memory_lifecycle_objectnav import (
    DEFAULT_SENSOR_HEIGHT,
    DEFAULT_SENSOR_WIDTH,
    DEFAULT_SEARCH_PROXY_WAYPOINTS,
    DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE,
    DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS,
    DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO,
    DEFAULT_DETECTOR_PROMPT_MODE,
    DEFAULT_ANCHOR_STRATEGY,
    DEFAULT_ANCHOR_CANDIDATE_LIMIT,
    SUPPORTED_ANCHOR_STRATEGIES,
    SUPPORTED_LIFECYCLE_DETECTORS,
    SUPPORTED_LIFECYCLE_MODES,
    TARGET_CATEGORIES,
    run_habitat_memory_lifecycle_objectnav,
    run_habitat_memory_lifecycle_preflight,
)
from objectnav_core.evaluation.habitat_objectnav_rgb_noise_stress import (
    SUPPORTED_YOLO_PROMPT_MODES,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run or preflight the Habitat memory-lifecycle ObjectNav evaluation."
    )
    parser.add_argument(
        "--dataset-dir",
        default="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini",
        help="HM3D ObjectNav val_mini dataset directory.",
    )
    parser.add_argument(
        "--scene-root",
        default="datasets/habitat/scene_datasets/hm3d",
        help="HM3D scene root containing habitat and semantic assets.",
    )
    parser.add_argument("--output", required=True, help="Output directory for artifacts.")
    parser.add_argument(
        "--rgb-noise-profile",
        default="configs/noise/rgb_published_v1.yaml",
        help="YAML RGB noise profile.",
    )
    parser.add_argument(
        "--depth-noise-profile",
        default="configs/noise/depth_realsense_d435_v1.yaml",
        help="YAML D435 depth noise profile.",
    )
    parser.add_argument(
        "--noise-levels",
        default="clean,mild,heavy",
        help="Comma-separated noise levels to run.",
    )
    parser.add_argument(
        "--detector",
        default="grounding_dino",
        choices=SUPPORTED_LIFECYCLE_DETECTORS,
        help="Detector backend.",
    )
    parser.add_argument(
        "--detector-weights",
        default="IDEA-Research/grounding-dino-tiny",
        help="Detector weights or Hugging Face model id.",
    )
    parser.add_argument("--detector-conf", type=float, default=0.25)
    parser.add_argument("--grounding-dino-text-threshold", type=float, default=0.25)
    parser.add_argument(
        "--grounding-dino-max-image-side",
        type=int,
        default=384,
        help="Optional Grounding-DINO inference resize cap.",
    )
    parser.add_argument(
        "--detector-prompt-mode",
        default=DEFAULT_DETECTOR_PROMPT_MODE,
        choices=SUPPORTED_YOLO_PROMPT_MODES,
        help=(
            "Detector prompt policy. target uses only the ObjectNav category; "
            "target_aliases adds category synonyms such as tv/television/monitor."
        ),
    )
    parser.add_argument(
        "--anchor-strategy",
        default=DEFAULT_ANCHOR_STRATEGY,
        choices=SUPPORTED_ANCHOR_STRATEGIES,
        help=(
            "Memory anchor policy. detector_positive selects a discovery viewpoint "
            "that actually passes detector-backed verification before storing memory."
        ),
    )
    parser.add_argument(
        "--anchor-candidate-limit",
        type=int,
        default=DEFAULT_ANCHOR_CANDIDATE_LIMIT,
        help=(
            "Maximum number of discovery viewpoints to detector-verify per group/noise "
            "cell, after sorting by Habitat target pixels."
        ),
    )
    parser.add_argument(
        "--modes",
        default=",".join(SUPPORTED_LIFECYCLE_MODES),
        help="Comma-separated modes: memory_guided,naive_count,no_memory.",
    )
    parser.add_argument(
        "--target-categories",
        default=",".join(TARGET_CATEGORIES),
        help="Comma-separated ObjectNav categories to include.",
    )
    parser.add_argument("--episodes-per-category", type=int, default=None)
    parser.add_argument(
        "--max-groups",
        type=int,
        default=None,
        help="Optional cap on lifecycle groups after selection.",
    )
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument("--sensor-width", type=int, default=DEFAULT_SENSOR_WIDTH)
    parser.add_argument("--sensor-height", type=int, default=DEFAULT_SENSOR_HEIGHT)
    parser.add_argument("--min-target-pixels", type=int, default=24)
    parser.add_argument("--min-detector-pixels", type=int, default=20)
    parser.add_argument(
        "--search-proxy-waypoints",
        type=int,
        default=DEFAULT_SEARCH_PROXY_WAYPOINTS,
        help=(
            "Number of deterministic random navigable waypoints charged before "
            "fallback goal verification. This models no-memory search effort; "
            "set 0 to use the oracle shortest-path lower bound."
        ),
    )
    parser.add_argument(
        "--query-repeats",
        type=int,
        default=1,
        help=(
            "Repeat each lifecycle query this many times. memory_guided can "
            "reuse a repaired fallback anchor after the first stale check; "
            "naive_count remains positive-only."
        ),
    )
    parser.add_argument(
        "--structured-min-goal-viewpoints",
        type=int,
        default=DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS,
        help="Minimum goal viewpoints for lifecycle candidate episodes.",
    )
    parser.add_argument(
        "--structured-min-geodesic-distance",
        type=float,
        default=DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE,
        help="Minimum geodesic distance for lifecycle candidate episodes.",
    )
    parser.add_argument(
        "--structured-min-path-complexity-ratio",
        type=float,
        default=DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO,
        help="Minimum geodesic/euclidean ratio for lifecycle candidate episodes.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate config and write summary without loading Habitat or detector weights.",
    )
    args = parser.parse_args(argv)

    run = (
        run_habitat_memory_lifecycle_preflight
        if args.preflight_only
        else run_habitat_memory_lifecycle_objectnav
    )
    summary = run(
        args.output,
        dataset_dir=args.dataset_dir,
        scene_root=args.scene_root,
        rgb_noise_profile=args.rgb_noise_profile,
        depth_noise_profile=args.depth_noise_profile,
        noise_levels=_split_csv(args.noise_levels),
        detector=args.detector,
        detector_weights=args.detector_weights,
        detector_conf=args.detector_conf,
        modes=_split_csv(args.modes),
        target_categories=_split_csv(args.target_categories),
        episodes_per_category=args.episodes_per_category,
        **(
            {}
            if args.preflight_only
            else {
                "max_groups": args.max_groups,
                "structured_min_goal_viewpoints": args.structured_min_goal_viewpoints,
                "structured_min_geodesic_distance": args.structured_min_geodesic_distance,
                "structured_min_path_complexity_ratio": args.structured_min_path_complexity_ratio,
                "search_proxy_waypoints": args.search_proxy_waypoints,
                "query_repeats": args.query_repeats,
            }
        ),
        seed=args.seed,
        sensor_width=args.sensor_width,
        sensor_height=args.sensor_height,
        grounding_dino_text_threshold=args.grounding_dino_text_threshold,
        grounding_dino_max_image_side=args.grounding_dino_max_image_side,
        detector_prompt_mode=args.detector_prompt_mode,
        anchor_strategy=args.anchor_strategy,
        anchor_candidate_limit=args.anchor_candidate_limit,
        min_target_pixels=args.min_target_pixels,
        min_detector_pixels=args.min_detector_pixels,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


if __name__ == "__main__":
    raise SystemExit(main())
