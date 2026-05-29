from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from objectnav_core.evaluation.habitat_memory_validity_model import (
    score_memory_validity_decisions,
    write_memory_validity_decision_scores_csv,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Apply a trained Habitat memory-validity model to exported examples "
            "and score learned memory-vs-frontier decisions."
        )
    )
    parser.add_argument("dataset", help="JSON report from the memory-validity exporter")
    parser.add_argument("--model", required=True, help="JSON model report")
    parser.add_argument("--output", required=True)
    parser.add_argument("--csv-output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset = _load_json_object(args.dataset, kind="dataset")
    model = _load_json_object(args.model, kind="model")
    report = score_memory_validity_decisions(dataset, model)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.csv_output:
        write_memory_validity_decision_scores_csv(args.csv_output, report["rows"])
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _load_json_object(path: str | Path, *, kind: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{kind} JSON root must be an object")
    return payload


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
