from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Sequence

from objectnav_core.evaluation.habitat_official_memory_anchor_quality import (
    report_habitat_official_memory_anchor_quality,
)


def main(
    argv: Sequence[str] | None = None,
    *,
    reporter: Callable[..., dict[str, Any]] = (
        report_habitat_official_memory_anchor_quality
    ),
) -> int:
    parser = argparse.ArgumentParser(
        description="Compare official memory anchors against a reference prior.",
    )
    parser.add_argument("--candidate-prior", required=True)
    parser.add_argument("--reference-prior", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-good-error-m", type=float, default=1.0)
    args = parser.parse_args(argv)

    summary = reporter(
        Path(args.output_dir),
        candidate_prior_path=args.candidate_prior,
        reference_prior_path=args.reference_prior,
        max_good_error_m=args.max_good_error_m,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
