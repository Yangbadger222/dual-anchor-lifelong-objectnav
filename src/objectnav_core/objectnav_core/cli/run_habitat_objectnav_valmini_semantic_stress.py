from __future__ import annotations

import argparse
import json
from pathlib import Path

from objectnav_core.evaluation.habitat_objectnav_valmini_semantic_stress import (
    DEFAULT_ACTIONS,
    DEFAULT_BREAKER_MODES,
    VALID_START_SOURCES,
    run_habitat_objectnav_valmini_semantic_stress,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run HM3D ObjectNav val_mini semantic-mask YOLO-breaker stress."
    )
    parser.add_argument(
        "--dataset-dir",
        required=True,
        help="Path to objectnav_hm3d_v1/val_mini or its content directory.",
    )
    parser.add_argument(
        "--scene-root",
        required=True,
        help="Path to the local HM3D scene root, usually scene_datasets/hm3d.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Directory for trace, summary, report, and generated scene config.",
    )
    parser.add_argument(
        "--max-episodes",
        type=int,
        help="Limit the number of ObjectNav episodes to run.",
    )
    parser.add_argument(
        "--start-source",
        choices=VALID_START_SOURCES,
        default="goal_viewpoint",
        help="Use official episode starts or goal viewpoints from the episode file.",
    )
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument("--sensor-size", type=int, default=96)
    parser.add_argument(
        "--actions",
        default=",".join(DEFAULT_ACTIONS),
        help="Comma-separated Habitat-Sim action names to run after reset.",
    )
    parser.add_argument(
        "--breaker-modes",
        default=",".join(DEFAULT_BREAKER_MODES),
        help="Comma-separated breaker modes: clean,miss,fly_point,edge_break,mixed.",
    )
    parser.add_argument("--min-target-pixels", type=int, default=24)
    parser.add_argument("--min-detector-pixels", type=int, default=20)
    parser.add_argument(
        "--positive-confirmation-frames",
        type=int,
        default=2,
        help="Number of positive candidate frames required before memory update.",
    )
    parser.add_argument(
        "--positive-confirmation-min-translation",
        type=float,
        default=0.05,
        help="Minimum agent translation in meters for multi-view confirmation.",
    )
    parser.add_argument(
        "--positive-confirmation-min-rotation-deg",
        type=float,
        default=5.0,
        help="Minimum agent rotation in degrees for multi-view confirmation.",
    )
    parser.add_argument(
        "--positive-confirmation-min-mask-iou",
        type=float,
        default=0.05,
        help="Minimum detector-mask IoU between candidate views for confirmation.",
    )
    args = parser.parse_args(argv)

    actions = [action.strip() for action in args.actions.split(",") if action.strip()]
    breaker_modes = [
        mode.strip() for mode in args.breaker_modes.split(",") if mode.strip()
    ]
    summary = run_habitat_objectnav_valmini_semantic_stress(
        Path(args.output),
        dataset_dir=Path(args.dataset_dir),
        scene_root=Path(args.scene_root),
        max_episodes=args.max_episodes,
        start_source=args.start_source,
        seed=args.seed,
        sensor_size=args.sensor_size,
        actions=actions,
        breaker_modes=breaker_modes,
        min_target_pixels=args.min_target_pixels,
        min_detector_pixels=args.min_detector_pixels,
        positive_confirmation_frames=args.positive_confirmation_frames,
        positive_confirmation_min_translation=args.positive_confirmation_min_translation,
        positive_confirmation_min_rotation_deg=args.positive_confirmation_min_rotation_deg,
        positive_confirmation_min_mask_iou=args.positive_confirmation_min_mask_iou,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
