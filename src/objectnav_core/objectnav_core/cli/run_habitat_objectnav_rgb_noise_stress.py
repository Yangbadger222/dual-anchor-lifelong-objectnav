from __future__ import annotations

import argparse
import json

from objectnav_core.evaluation.habitat_objectnav_rgb_noise_stress import (
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
        "--memory-ablation",
        default="on,off",
        help="Comma-separated memory ablations: on,off.",
    )
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument("--max-episodes", type=int, default=None)
    parser.add_argument(
        "--start-source",
        choices=("episode_start", "goal_viewpoint"),
        default="goal_viewpoint",
    )
    parser.add_argument("--sensor-size", type=int, default=96)
    parser.add_argument("--min-target-pixels", type=int, default=24)
    parser.add_argument("--min-detector-pixels", type=int, default=20)
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
            min_target_pixels=args.min_target_pixels,
            min_detector_pixels=args.min_detector_pixels,
        )
    print(json.dumps(summary, indent=2, sort_keys=True))


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


if __name__ == "__main__":
    main()
