from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from objectnav_core.evaluation.habitat_memory_validity_dataset import (
    DEFAULT_POLICIES,
    export_habitat_memory_validity_dataset,
    write_memory_validity_dataset_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export Habitat closed-loop summary rows as supervised "
            "memory-validity learning examples."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="summary.json files or directories recursively containing summary.json",
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output")
    parser.add_argument("--policies", default=",".join(DEFAULT_POLICIES))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = export_habitat_memory_validity_dataset(
        args.inputs,
        policies=_split_csv(args.policies),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.csv_output:
        write_memory_validity_dataset_csv(args.csv_output, report["examples"])
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
