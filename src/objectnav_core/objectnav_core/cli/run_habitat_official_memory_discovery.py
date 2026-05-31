from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Sequence

from objectnav_core.evaluation.habitat_official_memory_discovery import (
    SUPPORTED_MEMORY_ANCHOR_COMMIT_POLICIES,
    SUPPORTED_MEMORY_ANCHOR_MODES,
    SUPPORTED_MEMORY_ANCHOR_SELECTION_POLICIES,
    run_habitat_official_memory_discovery,
)
from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    SUPPORTED_OFFICIAL_POLICIES,
)
from objectnav_core.cli.run_habitat_official_objectnav_eval import (
    resolve_detector_weights,
)
from objectnav_core.perception.grounding_dino_adapter import GroundingDinoDetector
from objectnav_core.perception.yolo_world_adapter import YoloWorldDetector


DEFAULT_OBJECTNAV_CATEGORIES: tuple[str, ...] = (
    "bed",
    "chair",
    "plant",
    "sofa",
    "toilet",
    "tv_monitor",
)
SUPPORTED_DISCOVERY_DETECTORS: tuple[str, ...] = ("yolo_world", "grounding_dino")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run official Habitat ObjectNav detector-backed memory discovery."
    )
    parser.add_argument("--output", required=True)
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
    parser.add_argument(
        "--scene-root",
        default="datasets/habitat/scene_datasets/hm3d",
        help="HM3D scene root used by the official Habitat ObjectNav config.",
    )
    parser.add_argument("--split", default="val_mini")
    parser.add_argument(
        "--policy",
        choices=SUPPORTED_OFFICIAL_POLICIES,
        default="occupancy_frontier",
        help="Exploration policy used while collecting detector memories.",
    )
    parser.add_argument("--max-episodes", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument(
        "--detector",
        choices=SUPPORTED_DISCOVERY_DETECTORS,
        default="grounding_dino",
    )
    parser.add_argument(
        "--detector-weights",
        default=None,
        help=(
            "YOLO-World weights path or Grounding-DINO model id. If omitted, "
            "the default is detector-specific."
        ),
    )
    parser.add_argument("--detector-conf", type=float, default=0.25)
    parser.add_argument("--detector-device", default="auto")
    parser.add_argument(
        "--categories",
        default=",".join(DEFAULT_OBJECTNAV_CATEGORIES),
        help="Comma-separated detector prompt/category labels.",
    )
    parser.add_argument("--grounding-dino-text-threshold", type=float, default=0.25)
    parser.add_argument("--grounding-dino-max-image-side", type=int, default=None)
    parser.add_argument("--min-detection-confidence", type=float, default=0.25)
    parser.add_argument("--max-anchors-per-episode", type=int, default=8)
    parser.add_argument(
        "--positive-count-threshold",
        type=int,
        default=1,
        help=(
            "Minimum number of target-category positive detections in an "
            "episode before exporting anchors. Use 2 for a positive-only "
            "naive_count memory prior."
        ),
    )
    parser.add_argument(
        "--anchor-mode",
        choices=SUPPORTED_MEMORY_ANCHOR_MODES,
        default="projected_detection",
        help=(
            "Use projected_detection for bbox-depth object centers or "
            "robot_viewpoint for detector-positive robot poses."
        ),
    )
    parser.add_argument(
        "--anchor-selection-policy",
        choices=SUPPORTED_MEMORY_ANCHOR_SELECTION_POLICIES,
        default="confidence",
        help=(
            "Use confidence to preserve the historical detector-confidence rank, "
            "or view_quality to prefer larger centered target-visible viewpoints."
        ),
    )
    parser.add_argument(
        "--anchor-commit-policy",
        choices=SUPPORTED_MEMORY_ANCHOR_COMMIT_POLICIES,
        default="immediate",
        help=(
            "Use immediate to commit the current observation or detector_approach "
            "to defer until after bounded detector-guided local control. Use "
            "confirmed_detector_approach to write only range-confirmed target views."
        ),
    )
    parser.add_argument("--detector-approach-max-steps", type=int, default=1)
    parser.add_argument("--hfov-deg", type=float, default=79.0)
    parser.add_argument("--min-depth-m", type=float, default=0.5)
    parser.add_argument("--max-depth-m", type=float, default=5.0)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    detector_factory: Callable[..., Any] | None = None,
    runner: Callable[..., dict[str, Any]] = run_habitat_official_memory_discovery,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    categories = _parse_categories(args.categories, parser=parser)
    detector_weights = resolve_detector_weights(args.detector, args.detector_weights)
    detector_adapter = _build_detector(args, categories, detector_factory)
    summary = runner(
        Path(args.output),
        detector_adapter=detector_adapter,
        config_path=args.config_path,
        dataset_data_path=args.dataset_data_path,
        scene_root=args.scene_root,
        split=args.split,
        policy=args.policy,
        max_episodes=args.max_episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        detector_name=f"{args.detector}:{detector_weights}",
        min_detection_confidence=args.min_detection_confidence,
        max_anchors_per_episode=args.max_anchors_per_episode,
        positive_count_threshold=args.positive_count_threshold,
        anchor_mode=args.anchor_mode,
        anchor_selection_policy=args.anchor_selection_policy,
        anchor_commit_policy=args.anchor_commit_policy,
        detector_approach_max_steps=args.detector_approach_max_steps,
        hfov_deg=args.hfov_deg,
        min_depth_m=args.min_depth_m,
        max_depth_m=args.max_depth_m,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _parse_categories(
    raw_categories: str,
    *,
    parser: argparse.ArgumentParser,
) -> list[str]:
    categories = [
        category.strip()
        for category in str(raw_categories).split(",")
        if category.strip()
    ]
    if not categories:
        parser.error("--categories must contain at least one label")
    return categories


def _build_detector(
    args: argparse.Namespace,
    categories: list[str],
    detector_factory: Callable[..., Any] | None,
) -> Any:
    detector_weights = resolve_detector_weights(args.detector, args.detector_weights)
    if args.detector == "yolo_world":
        kwargs = {
            "weights": detector_weights,
            "categories": categories,
            "conf": args.detector_conf,
            "device": args.detector_device,
        }
    else:
        kwargs = {
            "model_id": detector_weights,
            "categories": categories,
            "conf": args.detector_conf,
            "text_threshold": args.grounding_dino_text_threshold,
            "max_image_side": args.grounding_dino_max_image_side,
            "device": args.detector_device,
        }
    if detector_factory is not None:
        return detector_factory(args.detector, **kwargs)
    if args.detector == "yolo_world":
        return YoloWorldDetector(**kwargs)
    return GroundingDinoDetector(**kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
