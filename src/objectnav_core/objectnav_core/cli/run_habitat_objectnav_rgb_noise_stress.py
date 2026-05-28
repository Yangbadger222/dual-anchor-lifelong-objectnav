from __future__ import annotations

import argparse
import json

from objectnav_core.evaluation.habitat_objectnav_rgb_noise_stress import (
    DEFAULT_SENSOR_HEIGHT,
    DEFAULT_SENSOR_WIDTH,
    DEFAULT_STOP_ON_TRUST,
    DEFAULT_YOLO_PROMPT_MODE,
    DEFAULT_DEBUG_EXPORT_CATEGORIES,
    DEFAULT_DEBUG_EXPORT_EVIDENCE_TYPES,
    DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY,
    DEFAULT_DEBUG_EXPORT_REPLAY_PHASES,
    DEFAULT_MAX_DETECTION_AREA_RATIO,
    DEFAULT_EPISODE_SELECTION_STRATEGY,
    DEFAULT_GEODESIC_PATH_MAX_STEPS,
    DEFAULT_REPLAY_PROTOCOL,
    DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE,
    DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS,
    DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO,
    SUPPORTED_DETECTORS,
    SUPPORTED_EPISODE_SELECTION_STRATEGIES,
    SUPPORTED_REPLAY_PROTOCOLS,
    SUPPORTED_YOLO_PROMPT_MODES,
    run_habitat_objectnav_rgb_noise_stress,
    run_rgb_noise_stress_preflight,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run or preflight the HM3D ObjectNav RGB-noise memory stress harness."
    )
    parser.add_argument(
        "--dataset-dir",
        default="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini",
        help="HM3D ObjectNav val_mini dataset directory.",
    )
    parser.add_argument(
        "--scene-root",
        default="datasets/habitat/scene_datasets/hm3d",
        help="HM3D scene root containing habitat/ and semantic/ assets.",
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
        default="yolo_world",
        choices=SUPPORTED_DETECTORS,
        help="Detector backend. oracle_bbox is for smoke tests only.",
    )
    parser.add_argument(
        "--detector-weights",
        default="yolov8s-worldv2.pt",
        help=(
            "Detector weights/model id. Examples: yolov8s-worldv2.pt or "
            "IDEA-Research/grounding-dino-tiny."
        ),
    )
    parser.add_argument("--detector-conf", type=float, default=0.25)
    parser.add_argument("--grounding-dino-text-threshold", type=float, default=0.25)
    parser.add_argument(
        "--grounding-dino-max-image-side",
        type=int,
        default=None,
        help=(
            "Optional detector-only resize cap for Grounding-DINO. Habitat still "
            "renders at the requested sensor resolution; boxes are scaled back."
        ),
    )
    parser.add_argument(
        "--yolo-prompt-mode",
        default=DEFAULT_YOLO_PROMPT_MODE,
        choices=SUPPORTED_YOLO_PROMPT_MODES,
        help=(
            "YOLO-World prompt policy. target conditions detection on the current "
            "ObjectNav goal category; all_categories preserves the legacy shared "
            "category set; target_aliases adds detector-specific synonyms."
        ),
    )
    parser.add_argument(
        "--memory-ablation",
        default="on,naive_count,off",
        help="Comma-separated memory ablations: on,naive_count,off.",
    )
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument("--max-episodes", type=int, default=None)
    parser.add_argument(
        "--episodes-per-category",
        type=int,
        default=None,
        help="Select up to this many episodes per target category.",
    )
    parser.add_argument(
        "--episode-selection-strategy",
        default=DEFAULT_EPISODE_SELECTION_STRATEGY,
        choices=SUPPORTED_EPISODE_SELECTION_STRATEGIES,
        help=(
            "Episode selection policy. structured_visibility keeps episodes "
            "with multiple goal viewpoints and nontrivial geodesic/euclidean "
            "path structure."
        ),
    )
    parser.add_argument(
        "--replay-protocol",
        default=DEFAULT_REPLAY_PROTOCOL,
        choices=SUPPORTED_REPLAY_PROTOCOLS,
        help=(
            "Replay protocol. out_and_back preserves the original fixed action "
            "trace; visibility_challenge teleports between measured visible and "
            "target-hidden viewpoints; expected_empty_challenge marks the hidden "
            "verification interval as expected empty; geodesic_path replays "
            "navmesh shortest-path waypoints from start to goal before final "
            "confirmation."
        ),
    )
    parser.add_argument(
        "--geodesic-path-max-steps",
        type=int,
        default=DEFAULT_GEODESIC_PATH_MAX_STEPS,
        help="Maximum sampled approach waypoints for replay_protocol=geodesic_path.",
    )
    parser.add_argument(
        "--structured-min-goal-viewpoints",
        type=int,
        default=DEFAULT_STRUCTURED_MIN_GOAL_VIEWPOINTS,
        help="Minimum goal viewpoints for structured_visibility episode selection.",
    )
    parser.add_argument(
        "--structured-min-geodesic-distance",
        type=float,
        default=DEFAULT_STRUCTURED_MIN_GEODESIC_DISTANCE,
        help="Minimum geodesic distance for structured_visibility selection.",
    )
    parser.add_argument(
        "--structured-min-path-complexity-ratio",
        type=float,
        default=DEFAULT_STRUCTURED_MIN_PATH_COMPLEXITY_RATIO,
        help=(
            "Minimum geodesic/euclidean distance ratio for "
            "structured_visibility selection."
        ),
    )
    parser.add_argument(
        "--target-categories",
        default="bed,chair,plant,sofa,toilet,tv_monitor",
        help="Comma-separated ObjectNav categories to include.",
    )
    parser.add_argument(
        "--start-source",
        choices=("episode_start", "goal_viewpoint"),
        default="goal_viewpoint",
    )
    parser.add_argument(
        "--sensor-size",
        type=int,
        default=None,
        help="Square sensor override, kept for old smoke commands.",
    )
    parser.add_argument("--sensor-width", type=int, default=DEFAULT_SENSOR_WIDTH)
    parser.add_argument("--sensor-height", type=int, default=DEFAULT_SENSOR_HEIGHT)
    parser.add_argument("--min-target-pixels", type=int, default=24)
    parser.add_argument("--min-detector-pixels", type=int, default=20)
    parser.add_argument(
        "--max-detection-area-ratio",
        type=float,
        default=DEFAULT_MAX_DETECTION_AREA_RATIO,
        help=(
            "Reject detector boxes covering more than this fraction of the image "
            "before building detector masks. Set <=0 to disable."
        ),
    )
    parser.add_argument(
        "--stop-on-trust",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_STOP_ON_TRUST,
        help=(
            "Stop an episode once the policy trusts a visible target, matching "
            "ObjectNav STOP semantics."
        ),
    )
    parser.add_argument(
        "--debug-export-gate-rejections",
        action="store_true",
        help=(
            "Export side-by-side PNG diagnostics when raw TRUST is rejected by "
            "the shared current-view gate."
        ),
    )
    parser.add_argument(
        "--debug-export-categories",
        default=",".join(DEFAULT_DEBUG_EXPORT_CATEGORIES),
        help=(
            "Comma-separated category filter for debug PNG export. "
            "Use an empty value to export every category."
        ),
    )
    parser.add_argument(
        "--debug-export-replay-phases",
        default=",".join(DEFAULT_DEBUG_EXPORT_REPLAY_PHASES),
        help=(
            "Comma-separated replay_phase filter for debug PNG export. "
            "Example: depart,non_confirm."
        ),
    )
    parser.add_argument(
        "--debug-export-evidence-types",
        default=",".join(DEFAULT_DEBUG_EXPORT_EVIDENCE_TYPES),
        help=(
            "Comma-separated evidence_type filter for debug PNG export. "
            "Example: positive."
        ),
    )
    parser.add_argument(
        "--debug-export-limit-per-category",
        type=int,
        default=DEFAULT_DEBUG_EXPORT_LIMIT_PER_CATEGORY,
        help="Maximum number of debug PNGs to write per category.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate config and write summary without loading Habitat or YOLO.",
    )
    args = parser.parse_args()

    if args.preflight_only:
        summary = run_rgb_noise_stress_preflight(
            output_dir=args.output,
            rgb_noise_profile=args.rgb_noise_profile,
            depth_noise_profile=args.depth_noise_profile,
            noise_levels=_split_csv(args.noise_levels),
            detector=args.detector,
            detector_weights=args.detector_weights,
            detector_conf=args.detector_conf,
            grounding_dino_text_threshold=args.grounding_dino_text_threshold,
            grounding_dino_max_image_side=args.grounding_dino_max_image_side,
            memory_ablation=_split_csv(args.memory_ablation),
            seed=args.seed,
            yolo_prompt_mode=args.yolo_prompt_mode,
            stop_on_trust=args.stop_on_trust,
            sensor_size=args.sensor_size,
            sensor_width=args.sensor_width,
            sensor_height=args.sensor_height,
            target_categories=_split_csv(args.target_categories),
            episodes_per_category=args.episodes_per_category,
            debug_export_gate_rejections=args.debug_export_gate_rejections,
            debug_export_categories=_split_csv(args.debug_export_categories),
            debug_export_replay_phases=_split_csv(args.debug_export_replay_phases),
            debug_export_evidence_types=_split_csv(args.debug_export_evidence_types),
            debug_export_limit_per_category=args.debug_export_limit_per_category,
            max_detection_area_ratio=_optional_positive_ratio(
                args.max_detection_area_ratio
            ),
            episode_selection_strategy=args.episode_selection_strategy,
            replay_protocol=args.replay_protocol,
            geodesic_path_max_steps=args.geodesic_path_max_steps,
            structured_min_goal_viewpoints=args.structured_min_goal_viewpoints,
            structured_min_geodesic_distance=args.structured_min_geodesic_distance,
            structured_min_path_complexity_ratio=args.structured_min_path_complexity_ratio,
        )
    else:
        summary = run_habitat_objectnav_rgb_noise_stress(
            output_dir=args.output,
            dataset_dir=args.dataset_dir,
            scene_root=args.scene_root,
            rgb_noise_profile=args.rgb_noise_profile,
            depth_noise_profile=args.depth_noise_profile,
            noise_levels=_split_csv(args.noise_levels),
            detector=args.detector,
            detector_weights=args.detector_weights,
            detector_conf=args.detector_conf,
            grounding_dino_text_threshold=args.grounding_dino_text_threshold,
            grounding_dino_max_image_side=args.grounding_dino_max_image_side,
            memory_ablation=_split_csv(args.memory_ablation),
            max_episodes=args.max_episodes,
            start_source=args.start_source,
            seed=args.seed,
            sensor_size=args.sensor_size,
            sensor_width=args.sensor_width,
            sensor_height=args.sensor_height,
            min_target_pixels=args.min_target_pixels,
            min_detector_pixels=args.min_detector_pixels,
            yolo_prompt_mode=args.yolo_prompt_mode,
            stop_on_trust=args.stop_on_trust,
            target_categories=_split_csv(args.target_categories),
            episodes_per_category=args.episodes_per_category,
            debug_export_gate_rejections=args.debug_export_gate_rejections,
            debug_export_categories=_split_csv(args.debug_export_categories),
            debug_export_replay_phases=_split_csv(args.debug_export_replay_phases),
            debug_export_evidence_types=_split_csv(args.debug_export_evidence_types),
            debug_export_limit_per_category=args.debug_export_limit_per_category,
            max_detection_area_ratio=_optional_positive_ratio(
                args.max_detection_area_ratio
            ),
            episode_selection_strategy=args.episode_selection_strategy,
            replay_protocol=args.replay_protocol,
            geodesic_path_max_steps=args.geodesic_path_max_steps,
            structured_min_goal_viewpoints=args.structured_min_goal_viewpoints,
            structured_min_geodesic_distance=args.structured_min_geodesic_distance,
            structured_min_path_complexity_ratio=args.structured_min_path_complexity_ratio,
        )
    print(json.dumps(summary, indent=2, sort_keys=True))


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _optional_positive_ratio(value: float) -> float | None:
    return value if value > 0.0 else None


if __name__ == "__main__":
    main()
