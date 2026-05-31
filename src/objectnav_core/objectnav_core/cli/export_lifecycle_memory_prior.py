from __future__ import annotations

import argparse
import json
from typing import Sequence

from objectnav_core.evaluation.lifecycle_memory_prior_export import (
    LifecycleMemoryPriorExportConfig,
    export_lifecycle_memory_prior,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export lifecycle SQLite memory anchors to official memory-prior JSON."
    )
    parser.add_argument("--memory-db", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-tag", default="lifecycle_memory")
    parser.add_argument("--min-confidence", type=float, default=0.0)
    parser.add_argument(
        "--coordinate-frame",
        default="habitat_world",
        help=(
            "Coordinate frame for exported anchors. Lifecycle DB anchors are "
            "Habitat world coordinates by default, not official GPS-relative."
        ),
    )
    parser.add_argument("--dataset-version", default=None)
    parser.add_argument("--scene-id", default=None)
    parser.add_argument(
        "--categories",
        default="",
        help="Optional comma-separated category filter.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    categories = tuple(
        category.strip()
        for category in str(args.categories).split(",")
        if category.strip()
    )
    summary = export_lifecycle_memory_prior(
        LifecycleMemoryPriorExportConfig(
            memory_db_path=args.memory_db,
            output_path=args.output,
            source_tag=args.source_tag,
            min_confidence=args.min_confidence,
            coordinate_frame=args.coordinate_frame,
            dataset_version=args.dataset_version,
            scene_id=args.scene_id,
            categories=categories,
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
