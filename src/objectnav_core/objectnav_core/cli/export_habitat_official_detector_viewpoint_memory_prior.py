from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Sequence

from objectnav_core.cli.run_habitat_official_memory_discovery import (
    DEFAULT_OBJECTNAV_CATEGORIES,
    SUPPORTED_DISCOVERY_DETECTORS,
    _parse_categories,
)
from objectnav_core.cli.run_habitat_official_objectnav_eval import (
    resolve_detector_weights,
)
from objectnav_core.evaluation.habitat_official_detector_viewpoint_memory_prior import (
    export_habitat_official_detector_viewpoint_memory_prior,
)
from objectnav_core.perception.grounding_dino_adapter import GroundingDinoDetector
from objectnav_core.perception.yolo_world_adapter import YoloWorldDetector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export a diagnostic official Habitat memory prior from target "
            "viewpoints that are confirmed by an object detector."
        )
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
    )
    parser.add_argument("--split", default="val_mini")
    parser.add_argument("--max-episodes", type=int, default=None)
    parser.add_argument("--max-viewpoints-per-episode", type=int, default=None)
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
    parser.add_argument(
        "--viewpoint-trace-output",
        default=None,
        help="Optional JSON trace path recording every restored candidate viewpoint.",
    )
    parser.add_argument(
        "--viewpoint-image-dir",
        default=None,
        help="Optional directory for annotated restored viewpoint RGB PNGs.",
    )
    parser.add_argument(
        "--validate-habitat",
        action="store_true",
        help="Import Habitat-Lab and inspect the official config in the summary.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    detector_factory: Callable[..., Any] | None = None,
    exporter: Callable[..., dict[str, Any]] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    categories = _parse_categories(args.categories, parser=parser)
    detector_weights = resolve_detector_weights(args.detector, args.detector_weights)
    detector_adapter = _build_detector(args, categories, detector_factory)
    run = exporter or export_habitat_official_detector_viewpoint_memory_prior
    summary = run(
        Path(args.output),
        detector_adapter=detector_adapter,
        detector_name=f"{args.detector}:{detector_weights}",
        config_path=args.config_path,
        dataset_data_path=args.dataset_data_path,
        scene_root=args.scene_root,
        split=args.split,
        max_episodes=args.max_episodes,
        max_viewpoints_per_episode=args.max_viewpoints_per_episode,
        seed=args.seed,
        min_detection_confidence=args.min_detection_confidence,
        validate_habitat=args.validate_habitat,
        viewpoint_trace_path=(
            Path(args.viewpoint_trace_output)
            if args.viewpoint_trace_output
            else None
        ),
        viewpoint_image_dir=(
            Path(args.viewpoint_image_dir) if args.viewpoint_image_dir else None
        ),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


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
