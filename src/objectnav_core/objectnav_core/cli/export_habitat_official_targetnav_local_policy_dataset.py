from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from objectnav_core.evaluation.habitat_official_targetnav_local_policy_dataset import (
    export_official_targetnav_local_policy_dataset,
    write_official_targetnav_local_policy_dataset_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export oracle TargetNav local policy labels under the official "
            "Habitat ObjectNav action and sensor contract."
        )
    )
    parser.add_argument("--output", required=True, help="Output dataset JSON path")
    parser.add_argument("--csv-output", help="Optional flat examples CSV path")
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
    parser.add_argument("--max-episodes", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument(
        "--goal-radius",
        type=float,
        default=0.2,
        help="ShortestPathFollower goal radius in meters.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: Callable[..., dict[str, Any]] | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    run = runner or export_official_targetnav_local_policy_dataset
    dataset = run(
        config_path=args.config_path,
        dataset_data_path=args.dataset_data_path,
        scene_root=args.scene_root,
        split=args.split,
        max_episodes=args.max_episodes,
        max_steps=args.max_steps,
        seed=args.seed,
        goal_radius_m=args.goal_radius,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.csv_output:
        write_official_targetnav_local_policy_dataset_csv(dataset, args.csv_output)
    print(json.dumps(_summary(dataset), ensure_ascii=False, sort_keys=True))
    return 0


def _summary(dataset: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task": dataset.get("task"),
        "schema_version": dataset.get("schema_version"),
        "source_validity": dataset.get("source_validity"),
        "episode_count": dataset.get("episode_count"),
        "example_count": dataset.get("example_count"),
        "skipped_no_goal_episode_count": dataset.get(
            "skipped_no_goal_episode_count"
        ),
        "skipped_teacher_unavailable_episode_count": dataset.get(
            "skipped_teacher_unavailable_episode_count"
        ),
        "invalid_teacher_action_count": dataset.get("invalid_teacher_action_count"),
        "action_distribution": dataset.get("action_distribution"),
    }


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
