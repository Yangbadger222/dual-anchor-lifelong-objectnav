from __future__ import annotations

import argparse
import json
from typing import Any, Callable, Sequence

from objectnav_core.evaluation.habitat_official_oracle_memory_prior import (
    export_habitat_official_oracle_memory_prior,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export privileged Habitat ObjectNav goal/viewpoint anchors as an "
            "official memory-prior JSON for diagnostic upper-bound runs."
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
    parser.add_argument("--seed", type=int, default=313)
    parser.add_argument(
        "--validate-habitat",
        action="store_true",
        help="Import Habitat-Lab and inspect the official config in the summary.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    exporter: Callable[..., dict[str, Any]] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run = exporter or export_habitat_official_oracle_memory_prior
    summary = run(
        args.output,
        config_path=args.config_path,
        dataset_data_path=args.dataset_data_path,
        scene_root=args.scene_root,
        split=args.split,
        max_episodes=args.max_episodes,
        seed=args.seed,
        validate_habitat=args.validate_habitat,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
