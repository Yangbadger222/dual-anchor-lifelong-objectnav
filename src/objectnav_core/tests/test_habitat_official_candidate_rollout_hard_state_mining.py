from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def test_hard_state_miner_selects_states_where_baseline_is_not_fastest(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_hard_state_mining import (
        mine_official_candidate_rollout_hard_states,
        write_official_candidate_rollout_hard_states_csv,
    )

    report = _report(
        [
            _state(
                source_dataset="runs/action_rollout_matrix_active_original/dataset.json",
                target_category="chair",
                fastest_actions=["turn_right"],
                strict_fastest_action="turn_right",
                action_times={"turn_left": 4, "turn_right": 2},
            ),
            _state(
                source_dataset="runs/action_rollout_matrix_active_rotation/dataset.json",
                target_category="sofa",
                fastest_actions=["turn_left", "turn_right"],
                strict_fastest_action=None,
                action_times={"turn_left": 2, "turn_right": 2},
            ),
            _state(
                source_dataset="runs/action_rollout_matrix_active_path/dataset.json",
                target_category="plant",
                fastest_actions=["turn_left"],
                strict_fastest_action="turn_left",
                action_times={"turn_left": 1, "turn_right": 5},
            ),
            _state(
                source_dataset="runs/action_rollout_matrix_active_scan/dataset.json",
                target_category="bed",
                fastest_actions=[],
                strict_fastest_action=None,
                action_times={},
            ),
        ]
    )

    mined = mine_official_candidate_rollout_hard_states(
        report,
        baseline_action="turn_left",
    )

    assert mined["task"] == "habitat_official_candidate_rollout_hard_state_mining"
    assert mined["baseline_action"] == "turn_left"
    assert mined["include_baseline_ties"] is False
    assert mined["input_state_count"] == 4
    assert mined["hard_state_count"] == 1
    assert mined["skipped_no_fastest_count"] == 1
    assert mined["aggregate"]["strict_fastest_action_counts"] == {"turn_right": 1}
    assert mined["aggregate"]["source_family_counts"] == {
        "active_original": {
            "state_count": 1,
            "strict_fastest_action_counts": {"turn_right": 1},
            "target_category_counts": {"chair": 1},
        }
    }

    [hard_state] = mined["states"]
    assert hard_state["hard_state_reason"] == "baseline_not_fastest"
    assert hard_state["source_family"] == "active_original"
    assert hard_state["baseline_success"] is True
    assert hard_state["baseline_time_to_visible_steps"] == 4
    assert hard_state["best_time_to_visible_steps"] == 2
    assert hard_state["baseline_time_regret_steps"] == 2

    csv_path = tmp_path / "hard_states.csv"
    write_official_candidate_rollout_hard_states_csv(mined, csv_path)
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "baseline_time_regret_steps" in csv_text
    assert "active_original" in csv_text
    assert "turn_right" in csv_text


def test_hard_state_miner_can_include_baseline_ties() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_hard_state_mining import (
        mine_official_candidate_rollout_hard_states,
    )

    report = _report(
        [
            _state(
                source_dataset="runs/action_rollout_matrix_active_original/dataset.json",
                fastest_actions=["turn_right"],
                strict_fastest_action="turn_right",
                action_times={"turn_left": 4, "turn_right": 2},
            ),
            _state(
                source_dataset="runs/action_rollout_matrix_active_rotation/dataset.json",
                fastest_actions=["turn_left", "turn_right"],
                strict_fastest_action=None,
                action_times={"turn_left": 2, "turn_right": 2},
            ),
            _state(
                source_dataset="runs/action_rollout_matrix_active_path/dataset.json",
                fastest_actions=["turn_left"],
                strict_fastest_action="turn_left",
                action_times={"turn_left": 1, "turn_right": 5},
            ),
        ]
    )

    mined = mine_official_candidate_rollout_hard_states(
        report,
        baseline_action="turn_left",
        include_baseline_ties=True,
    )

    assert mined["hard_state_count"] == 2
    assert [state["hard_state_reason"] for state in mined["states"]] == [
        "baseline_not_fastest",
        "baseline_tied_fastest",
    ]
    assert mined["aggregate"]["source_family_counts"]["active_rotation"] == {
        "state_count": 1,
        "strict_fastest_action_counts": {"<tie>": 1},
        "target_category_counts": {"chair": 1},
    }


def test_hard_state_miner_cli_writes_json_and_csv(tmp_path: Path) -> None:
    from objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states import (
        main,
    )

    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            _report(
                [
                    _state(
                        source_dataset="runs/action_rollout_matrix_active_scan/dataset.json",
                        fastest_actions=["move_forward"],
                        strict_fastest_action="move_forward",
                        action_times={"turn_left": 5, "move_forward": 1},
                    ),
                    _state(
                        source_dataset="runs/action_rollout_matrix_active_original/dataset.json",
                        fastest_actions=["turn_left"],
                        strict_fastest_action="turn_left",
                        action_times={"turn_left": 1},
                    ),
                ]
            )
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "hard_states.json"
    csv_path = tmp_path / "hard_states.csv"

    exit_code = main(
        [
            str(report_path),
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_path),
            "--baseline-action",
            "turn_left",
        ]
    )

    assert exit_code == 0
    mined = json.loads(output_path.read_text(encoding="utf-8"))
    assert mined["hard_state_count"] == 1
    assert mined["states"][0]["source_family"] == "active_scan"
    assert "active_scan" in csv_path.read_text(encoding="utf-8")


def test_hard_state_miner_cli_module_has_main_guard() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states",
            "--help",
        ],
        check=False,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
    )

    assert completed.returncode == 0
    assert "Mine hard states" in completed.stdout


def _report(states: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "task": "habitat_official_candidate_rollout_action_matrix_report",
        "actions": ["move_forward", "turn_left", "turn_right"],
        "state_count": len(states),
        "states": states,
    }


def _state(
    *,
    source_dataset: str,
    fastest_actions: list[str],
    strict_fastest_action: str | None,
    action_times: dict[str, int],
    target_category: str = "chair",
) -> dict[str, Any]:
    actions: dict[str, dict[str, Any]] = {}
    for action in ("move_forward", "turn_left", "turn_right"):
        time_to_visible = action_times.get(action)
        actions[action] = {
            "success": time_to_visible is not None,
            "time_to_visible_steps": time_to_visible,
            "rollout_action_count": time_to_visible or 5,
        }
    return {
        "source_dataset": source_dataset,
        "source_dataset_index": 0,
        "source_policy_trace": source_dataset.replace("dataset.json", "policy_trace.json"),
        "state_index": len(source_dataset),
        "episode_index": 0,
        "episode_id": "0",
        "scene_id": "scene.glb",
        "target_category": target_category,
        "step_index": 3,
        "state_action": "turn_left",
        "state_decision": "turn_toward_memory_active_perception_frontier",
        "state_features": {"memory_anchor_bearing_error_rad": -0.25},
        "positive_action_count": len(action_times),
        "positive_actions": list(action_times),
        "fastest_actions": fastest_actions,
        "strict_fastest_action": strict_fastest_action,
        "oracle_recovered": bool(fastest_actions),
        "actions": actions,
    }
