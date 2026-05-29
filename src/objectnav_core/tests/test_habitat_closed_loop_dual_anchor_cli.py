from __future__ import annotations

import json

from objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav import main


def test_habitat_closed_loop_dual_anchor_cli_preflight(tmp_path) -> None:
    exit_code = main(
        [
            "--output",
            str(tmp_path),
            "--dataset-dir",
            "datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val",
            "--scene-root",
            "datasets/habitat/scene_datasets/hm3d",
            "--target-categories",
            "plant,toilet",
            "--max-groups",
            "2",
            "--challenge",
            "ambiguous",
            "--preflight-only",
        ]
    )

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert summary["task"] == "habitat_closed_loop_dual_anchor_objectnav_preflight"
    assert summary["target_categories"] == ["plant", "toilet"]
    assert summary["challenge"] == "ambiguous"
