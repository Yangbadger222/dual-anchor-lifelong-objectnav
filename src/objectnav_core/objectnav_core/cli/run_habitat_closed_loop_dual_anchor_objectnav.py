from __future__ import annotations

import argparse
from typing import Sequence

from objectnav_core.evaluation.habitat_closed_loop_dual_anchor_objectnav import (
    DEFAULT_AMBIGUITY_MARGIN,
    DEFAULT_DEPTH_NOISE_PROFILE,
    DEFAULT_DETECTOR,
    DEFAULT_DETECTOR_CONFIRMATION_FRAMES,
    DEFAULT_DETECTOR_CONFIRMATION_MIN_MASK_IOU,
    DEFAULT_DETECTOR_CONFIRMATION_MIN_ROTATION_DEG,
    DEFAULT_DETECTOR_CONFIRMATION_MIN_TRANSLATION_M,
    DEFAULT_DETECTOR_CONFIRMATION_MODE,
    DEFAULT_DETECTOR_CONF,
    DEFAULT_DETECTOR_PROMPT_MODE,
    DEFAULT_DETECTOR_WEIGHTS,
    DEFAULT_FRONTIER_MODE,
    DEFAULT_FRONTIER_PROBE_COUNT,
    DEFAULT_FRONTIER_PROBE_HEADING_COUNT,
    DEFAULT_GATE_THRESHOLD,
    DEFAULT_FRONTIER_PROXY_WAYPOINTS,
    DEFAULT_GROUNDING_DINO_MAX_IMAGE_SIDE,
    DEFAULT_GROUNDING_DINO_TEXT_THRESHOLD,
    DEFAULT_MAX_DETECTION_AREA_RATIO,
    DEFAULT_MAX_GROUPS,
    DEFAULT_MEMORY_RELIABILITY_MODE,
    DEFAULT_MEMORY_VALID_PRIOR,
    DEFAULT_MIN_DETECTOR_PIXELS,
    DEFAULT_MIN_TARGET_PIXELS,
    DEFAULT_NOISE_LEVEL,
    DEFAULT_QUERY_REPEATS,
    DEFAULT_ROUTE_OBSERVATION_MODE,
    DEFAULT_RGB_NOISE_PROFILE,
    DEFAULT_SENSOR_HEIGHT,
    DEFAULT_SENSOR_WIDTH,
    DEFAULT_CHALLENGE,
    POLICIES,
    SUPPORTED_CHALLENGES,
    SUPPORTED_DETECTORS,
    SUPPORTED_DETECTOR_CONFIRMATION_MODES,
    SUPPORTED_DETECTOR_PROMPT_MODES,
    SUPPORTED_FRONTIER_MODES,
    SUPPORTED_MEMORY_RELIABILITY_MODES,
    SUPPORTED_NOISE_LEVELS,
    SUPPORTED_ROUTE_OBSERVATION_MODES,
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
    parser.add_argument(
        "--frontier-mode",
        default=DEFAULT_FRONTIER_MODE,
        choices=SUPPORTED_FRONTIER_MODES,
    )
    parser.add_argument(
        "--frontier-probe-count",
        type=int,
        default=DEFAULT_FRONTIER_PROBE_COUNT,
    )
    parser.add_argument(
        "--frontier-probe-heading-count",
        type=int,
        default=DEFAULT_FRONTIER_PROBE_HEADING_COUNT,
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
    parser.add_argument(
        "--memory-reliability-mode",
        default=DEFAULT_MEMORY_RELIABILITY_MODE,
        choices=SUPPORTED_MEMORY_RELIABILITY_MODES,
    )
    parser.add_argument(
        "--route-observation-mode",
        default=DEFAULT_ROUTE_OBSERVATION_MODE,
        choices=SUPPORTED_ROUTE_OBSERVATION_MODES,
    )
    parser.add_argument(
        "--detector-confirmation-mode",
        default=DEFAULT_DETECTOR_CONFIRMATION_MODE,
        choices=SUPPORTED_DETECTOR_CONFIRMATION_MODES,
    )
    parser.add_argument(
        "--detector-confirmation-frames",
        type=int,
        default=DEFAULT_DETECTOR_CONFIRMATION_FRAMES,
    )
    parser.add_argument(
        "--detector-confirmation-min-translation",
        type=float,
        default=DEFAULT_DETECTOR_CONFIRMATION_MIN_TRANSLATION_M,
    )
    parser.add_argument(
        "--detector-confirmation-min-rotation-deg",
        type=float,
        default=DEFAULT_DETECTOR_CONFIRMATION_MIN_ROTATION_DEG,
    )
    parser.add_argument(
        "--detector-confirmation-min-mask-iou",
        type=float,
        default=DEFAULT_DETECTOR_CONFIRMATION_MIN_MASK_IOU,
    )
    parser.add_argument("--challenge", default=DEFAULT_CHALLENGE, choices=SUPPORTED_CHALLENGES)
    parser.add_argument("--detector", default=DEFAULT_DETECTOR, choices=SUPPORTED_DETECTORS)
    parser.add_argument("--detector-weights", default=DEFAULT_DETECTOR_WEIGHTS)
    parser.add_argument("--detector-conf", type=float, default=DEFAULT_DETECTOR_CONF)
    parser.add_argument(
        "--grounding-dino-text-threshold",
        type=float,
        default=DEFAULT_GROUNDING_DINO_TEXT_THRESHOLD,
    )
    parser.add_argument(
        "--grounding-dino-max-image-side",
        type=int,
        default=DEFAULT_GROUNDING_DINO_MAX_IMAGE_SIDE,
    )
    parser.add_argument("--rgb-noise-profile", default=DEFAULT_RGB_NOISE_PROFILE)
    parser.add_argument("--depth-noise-profile", default=DEFAULT_DEPTH_NOISE_PROFILE)
    parser.add_argument(
        "--noise-level",
        default=DEFAULT_NOISE_LEVEL,
        choices=SUPPORTED_NOISE_LEVELS,
    )
    parser.add_argument(
        "--min-target-pixels",
        type=int,
        default=DEFAULT_MIN_TARGET_PIXELS,
    )
    parser.add_argument(
        "--min-detector-pixels",
        type=int,
        default=DEFAULT_MIN_DETECTOR_PIXELS,
    )
    parser.add_argument(
        "--max-detection-area-ratio",
        type=float,
        default=DEFAULT_MAX_DETECTION_AREA_RATIO,
    )
    parser.add_argument(
        "--detector-prompt-mode",
        default=DEFAULT_DETECTOR_PROMPT_MODE,
        choices=SUPPORTED_DETECTOR_PROMPT_MODES,
    )
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
        frontier_mode=args.frontier_mode,
        frontier_probe_count=args.frontier_probe_count,
        frontier_probe_heading_count=args.frontier_probe_heading_count,
        challenge=args.challenge,
        query_repeats=args.query_repeats,
        memory_valid_prior=args.memory_valid_prior,
        memory_reliability_mode=args.memory_reliability_mode,
        route_observation_mode=args.route_observation_mode,
        detector_confirmation_mode=args.detector_confirmation_mode,
        detector_confirmation_frames=args.detector_confirmation_frames,
        detector_confirmation_min_translation=(
            args.detector_confirmation_min_translation
        ),
        detector_confirmation_min_rotation_deg=(
            args.detector_confirmation_min_rotation_deg
        ),
        detector_confirmation_min_mask_iou=args.detector_confirmation_min_mask_iou,
        detector=args.detector,
        detector_weights=args.detector_weights,
        detector_conf=args.detector_conf,
        grounding_dino_text_threshold=args.grounding_dino_text_threshold,
        grounding_dino_max_image_side=args.grounding_dino_max_image_side,
        rgb_noise_profile=args.rgb_noise_profile,
        depth_noise_profile=args.depth_noise_profile,
        noise_level=args.noise_level,
        min_target_pixels=args.min_target_pixels,
        min_detector_pixels=args.min_detector_pixels,
        max_detection_area_ratio=args.max_detection_area_ratio,
        detector_prompt_mode=args.detector_prompt_mode,
    )
    return 0


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


if __name__ == "__main__":
    raise SystemExit(main())
