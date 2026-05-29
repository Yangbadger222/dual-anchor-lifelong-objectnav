from __future__ import annotations

import json

from objectnav_core.cli.run_closed_loop_dual_anchor_benchmark import main


def test_closed_loop_dual_anchor_cli_writes_summary(tmp_path) -> None:
    exit_code = main(["--output", str(tmp_path)])

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert summary["task"] == "closed_loop_dual_anchor_grid_benchmark"
    assert "memory_guided" in summary["policy_summaries"]
