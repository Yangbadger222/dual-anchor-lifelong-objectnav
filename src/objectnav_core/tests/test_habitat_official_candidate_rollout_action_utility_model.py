from __future__ import annotations

import json
from pathlib import Path


def test_action_utility_model_learns_decision_conditioned_fastest_actions() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_action_utility_model import (
        score_official_candidate_rollout_action_utility_report,
        train_official_candidate_rollout_action_utility_model,
    )

    report = _utility_report()

    model = train_official_candidate_rollout_action_utility_model(
        report,
        epochs=500,
        learning_rate=0.3,
        l2=0.0,
    )
    scores = score_official_candidate_rollout_action_utility_report(report, model)

    assert model["task"] == "habitat_official_candidate_rollout_action_utility_model"
    assert model["dataset"]["example_count"] == 12
    assert scores["aggregate"]["chosen_in_fastest_count"] == 4
    assert scores["aggregate"]["chosen_success_count"] == 4
    assert scores["aggregate"]["mean_utility_regret"] < 0.01


def test_action_utility_model_learns_action_step_interactions() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_action_utility_model import (
        score_official_candidate_rollout_action_utility_report,
        train_official_candidate_rollout_action_utility_model,
    )

    report = {
        "task": "habitat_official_candidate_rollout_action_matrix_report",
        "actions": ["move_forward", "turn_left", "turn_right"],
        "states": [
            _state(0, "source-a.json", "turn_toward_memory", "turn_right", 1),
            _state(1, "source-a.json", "turn_toward_memory", "turn_right", 1),
            _state(20, "source-a.json", "turn_toward_memory", "turn_left", 1),
            _state(21, "source-a.json", "turn_toward_memory", "turn_left", 1),
        ],
    }

    model = train_official_candidate_rollout_action_utility_model(
        report,
        epochs=700,
        learning_rate=0.2,
        l2=0.0,
    )
    scores = score_official_candidate_rollout_action_utility_report(report, model)

    assert scores["aggregate"]["chosen_in_fastest_count"] == 4


def test_action_utility_model_uses_numeric_state_features() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_action_utility_model import (
        score_official_candidate_rollout_action_utility_report,
        train_official_candidate_rollout_action_utility_model,
    )

    report = {
        "task": "habitat_official_candidate_rollout_action_matrix_report",
        "actions": ["turn_left", "turn_right"],
        "states": [
            _state_with_features(-0.9, "turn_left"),
            _state_with_features(-0.6, "turn_left"),
            _state_with_features(-0.3, "turn_left"),
            _state_with_features(0.3, "turn_right"),
            _state_with_features(0.6, "turn_right"),
            _state_with_features(0.9, "turn_right"),
        ],
    }

    model = train_official_candidate_rollout_action_utility_model(
        report,
        epochs=1000,
        learning_rate=0.2,
        l2=0.0,
    )
    scores = score_official_candidate_rollout_action_utility_report(report, model)

    assert "state_feature=memory_anchor_bearing_error_rad" in model["feature_names"]
    assert (
        "action_state_feature=turn_right__memory_anchor_bearing_error_rad"
        in model["feature_names"]
    )
    assert scores["aggregate"]["chosen_in_fastest_count"] == 6


def test_action_utility_leave_one_source_evaluation_reports_holdouts() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_rollout_action_utility_model import (
        evaluate_action_utility_leave_one_source,
    )

    evaluation = evaluate_action_utility_leave_one_source(
        _utility_report(),
        epochs=200,
        learning_rate=0.2,
        l2=0.001,
    )

    assert evaluation["task"] == "habitat_official_candidate_rollout_action_utility_leave_one_source"
    assert sorted(split["holdout_source"] for split in evaluation["splits"]) == [
        "source-a.json",
        "source-b.json",
    ]
    assert evaluation["aggregate"]["split_count"] == 2


def test_action_utility_model_cli_writes_outputs(tmp_path: Path) -> None:
    from objectnav_core.cli.train_habitat_official_candidate_rollout_action_utility_model import (
        main,
    )

    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(_utility_report()), encoding="utf-8")
    model_path = tmp_path / "model.json"
    scores_path = tmp_path / "scores.json"
    leave_one_source_path = tmp_path / "leave_one_source.json"

    exit_code = main(
        [
            str(report_path),
            "--output",
            str(model_path),
            "--scores-output",
            str(scores_path),
            "--leave-one-source-output",
            str(leave_one_source_path),
            "--epochs",
            "300",
            "--learning-rate",
            "0.25",
        ]
    )

    assert exit_code == 0
    model = json.loads(model_path.read_text(encoding="utf-8"))
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    leave_one_source = json.loads(leave_one_source_path.read_text(encoding="utf-8"))
    assert model["task"] == "habitat_official_candidate_rollout_action_utility_model"
    assert scores["task"] == "habitat_official_candidate_rollout_action_utility_scores"
    assert leave_one_source["aggregate"]["split_count"] == 2


def _utility_report() -> dict[str, object]:
    actions = ["move_forward", "turn_left", "turn_right"]
    return {
        "task": "habitat_official_candidate_rollout_action_matrix_report",
        "actions": actions,
        "states": [
            _state(0, "source-a.json", "scan_memory_anchor", "move_forward", 1),
            _state(1, "source-a.json", "scan_memory_anchor", "move_forward", 1),
            _state(2, "source-b.json", "orient_memory_anchor", "turn_right", 1),
            _state(3, "source-b.json", "orient_memory_anchor", "turn_right", 1),
        ],
    }


def _state(
    state_index: int,
    source_dataset: str,
    decision: str,
    fastest_action: str,
    fastest_time: int,
) -> dict[str, object]:
    actions = {}
    for action in ("move_forward", "turn_left", "turn_right"):
        success = action == fastest_action
        actions[action] = {
            "success": success,
            "time_to_visible_steps": fastest_time if success else None,
            "rollout_action_count": fastest_time if success else 5,
        }
    return {
        "source_dataset": source_dataset,
        "source_policy_trace": source_dataset.replace(".json", "/policy_trace.json"),
        "state_index": state_index,
        "episode_index": 0,
        "episode_id": f"episode-{state_index}",
        "scene_id": "scene.glb",
        "target_category": "chair",
        "step_index": state_index,
        "state_action": "turn_left",
        "state_decision": decision,
        "positive_action_count": 1,
        "positive_actions": [fastest_action],
        "fastest_actions": [fastest_action],
        "strict_fastest_action": fastest_action,
        "oracle_recovered": True,
        "actions": actions,
    }


def _state_with_features(
    memory_anchor_bearing_error_rad: float,
    fastest_action: str,
) -> dict[str, object]:
    actions = {}
    for action in ("turn_left", "turn_right"):
        success = action == fastest_action
        actions[action] = {
            "success": success,
            "time_to_visible_steps": 1 if success else None,
            "rollout_action_count": 1 if success else 5,
        }
    return {
        "source_dataset": "source-geometry.json",
        "source_policy_trace": "source-geometry/policy_trace.json",
        "state_index": 0,
        "episode_index": 0,
        "episode_id": "episode-geometry",
        "scene_id": "scene.glb",
        "target_category": "chair",
        "step_index": 5,
        "state_action": "turn_left",
        "state_decision": "scan_memory_anchor",
        "state_features": {
            "memory_anchor_bearing_error_rad": memory_anchor_bearing_error_rad,
            "local_center_depth_clear": True,
        },
        "positive_action_count": 1,
        "positive_actions": [fastest_action],
        "fastest_actions": [fastest_action],
        "strict_fastest_action": fastest_action,
        "oracle_recovered": True,
        "actions": actions,
    }
