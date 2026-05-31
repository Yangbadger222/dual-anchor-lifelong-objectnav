from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Sequence

from objectnav_core.cli.run_habitat_official_objectnav_eval import (
    DEFAULT_OBJECTNAV_CATEGORIES,
    SUPPORTED_QUERY_DETECTORS,
    _build_detector,
    _parse_categories,
)
from objectnav_core.evaluation.habitat_official_candidate_rollout_dataset import (
    STATE_SAMPLING_MODES,
    export_official_candidate_state_restore_dataset,
    write_official_candidate_state_restore_dataset_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export detector labels at exact restored official Habitat "
            "candidate-bearing memory-query states."
        )
    )
    parser.add_argument("policy_trace")
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output", default=None)
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
    parser.add_argument("--max-states", type=int, default=None)
    parser.add_argument(
        "--max-states-per-category",
        type=int,
        default=None,
        help="Optional cap on selected candidate states for each target category.",
    )
    parser.add_argument(
        "--max-states-per-category-episode",
        type=int,
        default=None,
        help=(
            "Optional cap on selected candidate states for each "
            "(target category, episode) pair."
        ),
    )
    parser.add_argument(
        "--state-sampling",
        choices=STATE_SAMPLING_MODES,
        default="trace_order",
        help="Candidate-state sampling order.",
    )
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument(
        "--detector",
        choices=SUPPORTED_QUERY_DETECTORS,
        default="none",
        help="Detector used for restored-state visibility labels.",
    )
    parser.add_argument(
        "--detector-weights",
        default=None,
        help="Detector weights or model id. If omitted, the default is detector-specific.",
    )
    parser.add_argument("--detector-conf", type=float, default=0.25)
    parser.add_argument("--detector-device", default="auto")
    parser.add_argument(
        "--target-detector-min-confidence",
        type=float,
        default=0.25,
    )
    parser.add_argument(
        "--categories",
        default=",".join(DEFAULT_OBJECTNAV_CATEGORIES),
    )
    parser.add_argument("--grounding-dino-text-threshold", type=float, default=0.25)
    parser.add_argument("--grounding-dino-max-image-side", type=int, default=None)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    detector_factory: Callable[..., Any] | None = None,
    runner: Callable[..., dict[str, Any]] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    categories = _parse_categories(args.categories, parser=parser)
    detector = _build_detector(args, categories, detector_factory)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run = runner or export_official_candidate_state_restore_dataset
    dataset = run(
        args.policy_trace,
        output_dir=output_path.parent,
        config_path=args.config_path,
        dataset_data_path=args.dataset_data_path,
        scene_root=args.scene_root,
        split=args.split,
        target_detector_adapter=detector,
        target_detector_min_confidence=args.target_detector_min_confidence,
        max_states=args.max_states,
        max_states_per_category=args.max_states_per_category,
        max_states_per_category_episode=args.max_states_per_category_episode,
        state_sampling=args.state_sampling,
        seed=args.seed,
    )
    output_path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if args.csv_output:
        write_official_candidate_state_restore_dataset_csv(dataset, args.csv_output)
    print(json.dumps(_summary(dataset), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summary(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": dataset.get("task"),
        "schema_version": dataset.get("schema_version"),
        "state_count": dataset.get("state_count"),
        "restore_count": dataset.get("restore_count"),
        "valid_restore_count": dataset.get("valid_restore_count"),
        "target_visible_state_count": dataset.get("target_visible_state_count"),
        "invalid_restore_count": dataset.get("invalid_restore_count"),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
