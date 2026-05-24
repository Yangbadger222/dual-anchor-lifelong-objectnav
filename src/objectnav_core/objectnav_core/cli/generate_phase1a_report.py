from __future__ import annotations

import argparse
import json
from pathlib import Path

from objectnav_core.evaluation.report import generate_phase1a_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a static Phase 1A ObjectNav HTML report.")
    parser.add_argument(
        "--input",
        required=True,
        help="Directory containing memory.sqlite, summary.json, memory_snapshot.json, and events.jsonl.",
    )
    args = parser.parse_args(argv)
    report_path = generate_phase1a_report(Path(args.input))
    print(json.dumps({"report": str(report_path)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
