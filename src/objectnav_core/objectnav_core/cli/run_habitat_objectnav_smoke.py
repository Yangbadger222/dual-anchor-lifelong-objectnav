from __future__ import annotations

import argparse
import json
from pathlib import Path

from objectnav_core.evaluation.habitat_objectnav_smoke import (
    DEFAULT_ACTIONS,
    SyntheticObjectNavSpec,
    run_habitat_objectnav_smoke,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a minimal Habitat-Lab ObjectNav scene-load and trace-export smoke."
    )
    parser.add_argument(
        "--scene",
        required=True,
        help="Path to a Habitat-Sim scene asset, such as simple_room.glb.",
    )
    parser.add_argument(
        "--scene-dataset-config",
        help="Optional Habitat scene dataset config JSON, needed for semantic scene metadata.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Directory where habitat_trace.csv, summary.json, and report.html will be written.",
    )
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--sensor-size", type=int, default=64)
    parser.add_argument("--object-category", default="chair")
    parser.add_argument(
        "--target-position",
        nargs=3,
        type=float,
        metavar=("X", "Y", "Z"),
        default=(0.8, 0.0, -0.8),
        help="Synthetic target position used for trace distance fields.",
    )
    parser.add_argument(
        "--actions",
        default=",".join(DEFAULT_ACTIONS),
        help="Comma-separated Habitat action names to run before the optional stop action.",
    )
    parser.add_argument(
        "--no-stop-at-end",
        action="store_true",
        help="Do not append a final stop action to end the synthetic episode.",
    )
    parser.add_argument(
        "--sample-navigable",
        action="store_true",
        help="Sample synthetic start and target positions from the scene navmesh when available.",
    )
    parser.add_argument(
        "--sample-target-near-radius",
        type=float,
        help="When sampling from the navmesh, sample the synthetic target within this radius of the start.",
    )
    args = parser.parse_args(argv)

    actions = [action.strip() for action in args.actions.split(",") if action.strip()]
    spec = SyntheticObjectNavSpec(
        scene_path=str(Path(args.scene).expanduser()),
        object_category=args.object_category,
        target_position=tuple(args.target_position),
    )
    summary = run_habitat_objectnav_smoke(
        Path(args.output),
        scene_path=Path(args.scene),
        scene_dataset_config=Path(args.scene_dataset_config) if args.scene_dataset_config else None,
        seed=args.seed,
        sensor_size=args.sensor_size,
        actions=actions,
        stop_at_end=not args.no_stop_at_end,
        sample_navigable=args.sample_navigable,
        sample_target_near_radius=args.sample_target_near_radius,
        spec=spec,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
