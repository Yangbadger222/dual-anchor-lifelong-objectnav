from __future__ import annotations

import argparse
import json
from pathlib import Path

from objectnav_core.evaluation.habitat_semantic_yolo_stress import (
    DEFAULT_ACTIONS,
    DEFAULT_BREAKER_MODES,
    run_habitat_semantic_yolo_stress,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Habitat semantic-mask YOLO-breaker stress against usability memory."
    )
    parser.add_argument("--scene", required=True, help="Habitat scene asset path.")
    parser.add_argument(
        "--scene-dataset-config",
        help="Optional Habitat scene dataset config JSON.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Directory for semantic_yolo_trace.csv, summary.json, and report.html.",
    )
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--seed", type=int, default=211)
    parser.add_argument("--sensor-size", type=int, default=96)
    parser.add_argument(
        "--actions",
        default=",".join(DEFAULT_ACTIONS),
        help="Comma-separated Habitat-Sim action names to run after reset.",
    )
    parser.add_argument(
        "--breaker-modes",
        default=",".join(DEFAULT_BREAKER_MODES),
        help="Comma-separated breaker modes: clean,miss,fly_point,edge_break,mixed.",
    )
    parser.add_argument("--min-target-pixels", type=int, default=24)
    parser.add_argument("--min-detector-pixels", type=int, default=20)
    args = parser.parse_args(argv)

    actions = [action.strip() for action in args.actions.split(",") if action.strip()]
    breaker_modes = [
        mode.strip() for mode in args.breaker_modes.split(",") if mode.strip()
    ]
    summary = run_habitat_semantic_yolo_stress(
        Path(args.output),
        scene_path=Path(args.scene),
        scene_dataset_config=Path(args.scene_dataset_config)
        if args.scene_dataset_config
        else None,
        episodes=args.episodes,
        seed=args.seed,
        sensor_size=args.sensor_size,
        actions=actions,
        breaker_modes=breaker_modes,
        min_target_pixels=args.min_target_pixels,
        min_detector_pixels=args.min_detector_pixels,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
