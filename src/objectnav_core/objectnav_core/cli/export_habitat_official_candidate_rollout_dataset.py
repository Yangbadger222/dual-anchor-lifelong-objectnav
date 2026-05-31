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
    BRANCH_FOLLOWUP_POLICIES,
    STATE_SAMPLING_MODES,
    export_official_candidate_rollout_dataset,
    write_official_candidate_rollout_dataset_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export official Habitat active-perception candidate rollout labels."
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
        help=(
            "Candidate-state sampling order. trace_order preserves existing "
            "behavior; top_score_desc prioritizes higher top-candidate scores."
        ),
    )
    parser.add_argument("--candidates-per-state", type=int, default=5)
    parser.add_argument("--rollout-horizon-steps", type=int, default=5)
    parser.add_argument(
        "--branch-actions",
        default=None,
        help=(
            "Optional comma-separated first-action interventions, e.g. "
            "turn_left,turn_right,move_forward. When set, the exporter emits "
            "action-matrix branches instead of candidate-viewpoint branches."
        ),
    )
    parser.add_argument(
        "--branch-followup-policy",
        choices=BRANCH_FOLLOWUP_POLICIES,
        default="left_scan",
        help=(
            "Follow-up controller after an explicit branch action. "
            "left_scan preserves previous diagnostics; repeat_first_action "
            "repeats the branch action for symmetric macro-action labels."
        ),
    )
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument(
        "--detector",
        choices=SUPPORTED_QUERY_DETECTORS,
        default="none",
        help="Detector used for branch rollout visibility labels.",
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
    run = runner or export_official_candidate_rollout_dataset
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
        candidates_per_state=args.candidates_per_state,
        rollout_horizon_steps=args.rollout_horizon_steps,
        branch_actions=_split_csv(args.branch_actions),
        branch_followup_policy=args.branch_followup_policy,
        seed=args.seed,
    )
    output_path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if args.csv_output:
        write_official_candidate_rollout_dataset_csv(dataset, args.csv_output)
    print(json.dumps(_summary(dataset), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _summary(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": dataset.get("task"),
        "schema_version": dataset.get("schema_version"),
        "state_count": dataset.get("state_count"),
        "branch_mode": dataset.get("branch_mode"),
        "branch_actions": dataset.get("branch_actions"),
        "branch_followup_policy": dataset.get("branch_followup_policy"),
        "rollout_count": dataset.get("rollout_count"),
        "positive_rollout_count": dataset.get("positive_rollout_count"),
        "invalid_rollout_count": dataset.get("invalid_rollout_count"),
    }


def _split_csv(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    return tuple(part.strip() for part in raw.split(",") if part.strip())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
