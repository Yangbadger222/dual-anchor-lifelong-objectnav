from __future__ import annotations

import argparse
import json
from pathlib import Path

from objectnav_core.evaluation.habitat_usability_replay import (
    run_habitat_usability_replay,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run multi-episode Habitat replay through the usability-memory policy."
    )
    parser.add_argument(
        "--scene",
        action="append",
        required=True,
        help="Habitat scene asset path. Repeat to cycle through multiple scenes.",
    )
    parser.add_argument(
        "--scene-dataset-config",
        help="Optional Habitat scene dataset config JSON.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Directory for habitat_trace.csv, usability_replay.csv, summary.json, and report.html.",
    )
    parser.add_argument("--episodes", type=int, default=9)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--sensor-size", type=int, default=96)
    parser.add_argument(
        "--actions",
        help="Optional comma-separated Habitat action names. When omitted, replay cycles built-in action variants.",
    )
    parser.add_argument("--positive-radius", type=float, default=1.25)
    parser.add_argument("--free-radius", type=float, default=2.5)
    args = parser.parse_args(argv)

    actions = None
    if args.actions:
        actions = [action.strip() for action in args.actions.split(",") if action.strip()]

    summary = run_habitat_usability_replay(
        Path(args.output),
        scene_paths=[Path(scene) for scene in args.scene],
        scene_dataset_config=Path(args.scene_dataset_config)
        if args.scene_dataset_config
        else None,
        episodes=args.episodes,
        seed=args.seed,
        sensor_size=args.sensor_size,
        actions=actions,
        positive_radius=args.positive_radius,
        free_radius=args.free_radius,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
