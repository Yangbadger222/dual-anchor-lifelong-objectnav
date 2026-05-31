from __future__ import annotations

import argparse
import json
from typing import Any, Callable, Sequence

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    SUPPORTED_OFFICIAL_POLICIES,
    SUPPORTED_TARGETNAV_BACKENDS,
    run_habitat_official_objectnav_eval,
    run_habitat_official_objectnav_preflight,
)
from objectnav_core.perception.grounding_dino_adapter import (
    DEFAULT_GROUNDING_DINO_MODEL,
    GroundingDinoDetector,
)
from objectnav_core.perception.yolo_world_adapter import YoloWorldDetector


DEFAULT_YOLO_WORLD_WEIGHTS = "yolov8s-worldv2.pt"
DEFAULT_OBJECTNAV_CATEGORIES: tuple[str, ...] = (
    "bed",
    "chair",
    "plant",
    "sofa",
    "toilet",
    "tv_monitor",
)
SUPPORTED_QUERY_DETECTORS: tuple[str, ...] = (
    "none",
    "yolo_world",
    "grounding_dino",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run official Habitat-Lab ObjectNav measure preflight/smoke."
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
        help=(
            "HM3D scene root. If this path ends in hm3d, the Habitat dataset "
            "scenes_dir override uses its parent, matching episode scene ids."
        ),
    )
    parser.add_argument("--split", default="val_mini")
    parser.add_argument(
        "--policy",
        choices=SUPPORTED_OFFICIAL_POLICIES,
        default="noop",
    )
    parser.add_argument("--max-episodes", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument(
        "--memory-prior-path",
        default=None,
        help="JSON memory prior with remembered object anchors for memory policies.",
    )
    parser.add_argument("--memory-stop-radius-m", type=float, default=0.35)
    parser.add_argument("--memory-bearing-tolerance-deg", type=float, default=20.0)
    parser.add_argument("--memory-min-confidence", type=float, default=0.0)
    parser.add_argument(
        "--pathfinder-suffix-goal-radius-m",
        type=float,
        default=1.0,
        help=(
            "Diagnostic pathfinder suffix stop radius in meters. Only used by "
            "memory_active_perception_frontier_pathfinder_suffix."
        ),
    )
    parser.add_argument(
        "--targetnav-ddppo-checkpoint-path",
        default=None,
        help=(
            "HM3D PointNav/DDPPO checkpoint path required by "
            "memory_active_perception_frontier_targetnav_ddppo."
        ),
    )
    parser.add_argument(
        "--targetnav-ddppo-device",
        default="auto",
        help=(
            "Device for the TargetNav DDPPO backend. Use auto, cpu, cuda, or "
            "a torch device string."
        ),
    )
    parser.add_argument(
        "--targetnav-backend",
        choices=SUPPORTED_TARGETNAV_BACKENDS,
        default="occupancy_grid",
        help=(
            "Backend used by memory_active_perception_frontier_targetnav. "
            "Legacy targetnav_fmm and targetnav_ddppo policy names still "
            "select their matching backends."
        ),
    )
    parser.add_argument(
        "--local-action-model-path",
        default=None,
        help=(
            "JSON local action-effect model required by "
            "memory_learned_local_frontier."
        ),
    )
    parser.add_argument(
        "--candidate-viewpoint-ranker-model-path",
        default=None,
        help=(
            "Optional JSON candidate-viewpoint ranker model used to rerank "
            "memory_active_perception_frontier candidates."
        ),
    )
    parser.add_argument(
        "--detector-center-direction-sign",
        type=int,
        choices=(-1, 1),
        default=1,
        help=(
            "Initial sign mapping detector bbox horizontal offset to turn "
            "direction. Use -1 only for diagnostic centering-sign ablations."
        ),
    )
    parser.add_argument(
        "--detector",
        choices=SUPPORTED_QUERY_DETECTORS,
        default="none",
        help="Optional current-view detector to inject into query policies.",
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
        "--target-detector-min-confidence",
        type=float,
        default=0.25,
        help="Minimum target-category detection confidence used by query policy.",
    )
    parser.add_argument(
        "--categories",
        default=",".join(DEFAULT_OBJECTNAV_CATEGORIES),
        help="Comma-separated detector prompt/category labels.",
    )
    parser.add_argument("--grounding-dino-text-threshold", type=float, default=0.25)
    parser.add_argument("--grounding-dino-max-image-side", type=int, default=None)
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Write protocol manifest and summary without creating habitat.Env.",
    )
    parser.add_argument(
        "--validate-habitat",
        action="store_true",
        help="Import Habitat-Lab and inspect the official config during preflight.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    detector_factory: Callable[..., Any] | None = None,
    runner: Callable[..., dict[str, Any]] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run = (
        run_habitat_official_objectnav_preflight
        if args.preflight_only
        else runner or run_habitat_official_objectnav_eval
    )
    kwargs: dict[str, Any] = {
        "config_path": args.config_path,
        "dataset_data_path": args.dataset_data_path,
        "scene_root": args.scene_root,
        "split": args.split,
        "policy": args.policy,
        "max_episodes": args.max_episodes,
        "max_steps": args.max_steps,
        "seed": args.seed,
        "validate_habitat": args.validate_habitat,
        "memory_prior_path": args.memory_prior_path,
        "memory_stop_radius_m": args.memory_stop_radius_m,
        "memory_bearing_tolerance_deg": args.memory_bearing_tolerance_deg,
        "memory_min_confidence": args.memory_min_confidence,
        "pathfinder_suffix_goal_radius_m": args.pathfinder_suffix_goal_radius_m,
        "targetnav_backend": args.targetnav_backend,
        "targetnav_ddppo_checkpoint_path": args.targetnav_ddppo_checkpoint_path,
        "targetnav_ddppo_device": args.targetnav_ddppo_device,
        "detector_center_direction_sign": args.detector_center_direction_sign,
        "local_action_model_path": args.local_action_model_path,
        "candidate_viewpoint_ranker_model_path": (
            args.candidate_viewpoint_ranker_model_path
        ),
    }
    if not args.preflight_only:
        categories = _parse_categories(args.categories, parser=parser)
        kwargs["target_detector_adapter"] = _build_detector(
            args,
            categories,
            detector_factory,
        )
        kwargs["target_detector_min_confidence"] = (
            args.target_detector_min_confidence
        )
    summary = run(args.output, **kwargs)
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
) -> Any | None:
    if args.detector == "none":
        return None
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


def resolve_detector_weights(detector: str, detector_weights: str | None) -> str:
    if detector_weights:
        return detector_weights
    if detector == "grounding_dino":
        return DEFAULT_GROUNDING_DINO_MODEL
    return DEFAULT_YOLO_WORLD_WEIGHTS


if __name__ == "__main__":
    raise SystemExit(main())
