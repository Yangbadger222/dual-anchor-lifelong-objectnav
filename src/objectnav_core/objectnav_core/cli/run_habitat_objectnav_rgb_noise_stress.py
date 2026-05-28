from __future__ import annotations

import argparse
import json

from objectnav_core.evaluation.habitat_objectnav_rgb_noise_stress import (
    DEFAULT_SENSOR_HEIGHT,
    DEFAULT_SENSOR_WIDTH,
    DEFAULT_STOP_ON_TRUST,
    DEFAULT_YOLO_PROMPT_MODE,
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
        choices=("yolo_world", "oracle_bbox"),
        help="Detector backend. oracle_bbox is for smoke tests only.",
    )
    parser.add_argument(
        "--detector-weights",
        default="yolov8s-worldv2.pt",
        help="YOLO-World weights name or path.",
    )
    parser.add_argument("--detector-conf", type=float, default=0.25)
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
        default="on,off",
        help="Comma-separated memory ablations: on,off.",
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
        "--stop-on-trust",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_STOP_ON_TRUST,
        help=(
            "Stop an episode once the policy trusts a visible target, matching "
            "ObjectNav STOP semantics."
        ),
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
            memory_ablation=_split_csv(args.memory_ablation),
            seed=args.seed,
            yolo_prompt_mode=args.yolo_prompt_mode,
            stop_on_trust=args.stop_on_trust,
            sensor_size=args.sensor_size,
            sensor_width=args.sensor_width,
            sensor_height=args.sensor_height,
            target_categories=_split_csv(args.target_categories),
            episodes_per_category=args.episodes_per_category,
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
        )
    print(json.dumps(summary, indent=2, sort_keys=True))


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


if __name__ == "__main__":
    main()
