from __future__ import annotations

import json

from objectnav_core.cli.run_dual_anchor_pressure import main


def test_dual_anchor_pressure_cli_writes_summary(tmp_path) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--gate-threshold",
            "5.991",
            "--ambiguity-margin",
            "0.5",
        ]
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert summary["task"] == "dual_anchor_matching_pressure"
    assert summary["case_count"] >= 3
    assert summary["ambiguous_count"] >= 1
