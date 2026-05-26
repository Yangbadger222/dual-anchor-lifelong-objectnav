from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from objectnav_core.evaluation.localization_bag_audit import run_localization_bag_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a localization-only audit over ROS 2 SQLite bags.")
    parser.add_argument("--output", required=True, type=Path, help="Directory for JSON, CSV, and HTML artifacts.")
    parser.add_argument(
        "--bag",
        action="append",
        default=[],
        type=Path,
        help="Explicit bag directory containing metadata.yaml and bag_0.db3. Can be repeated.",
    )
    parser.add_argument("--data-root", type=Path, help="Optional root to scan for logs/*/bag/metadata.yaml.")
    parser.add_argument("--limit", type=int, help="Optional limit for discovered or explicit bags.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_localization_bag_audit(
        output_dir=args.output,
        bag_paths=args.bag,
        data_root=args.data_root,
        limit=args.limit,
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "bag_count": summary["bag_count"],
                "health_counts": summary["health_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
