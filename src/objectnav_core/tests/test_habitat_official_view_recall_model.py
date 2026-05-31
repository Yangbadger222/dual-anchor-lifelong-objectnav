from __future__ import annotations

import json

from objectnav_core.evaluation.habitat_official_view_recall_model import (
    predict_official_view_recall,
    score_official_view_recall_candidates,
    score_official_view_recall_dataset,
    train_official_view_recall_logistic_model,
    write_official_view_recall_scores_csv,
)


def test_official_view_recall_model_trains_hidden_to_visible_slice() -> None:
    dataset = _view_recall_dataset(
        [
            ("turn_left", "turn_toward_memory_active_perception_frontier", False, 1.8, 0.52, 0.98, 0.5, True),
            ("turn_left", "turn_toward_memory_active_perception_frontier", False, 1.9, 0.51, 0.97, 0.5, True),
            ("move_forward", "move_toward_memory_belief_frontier", False, 0.4, 0.78, 0.2, 3.0, False),
            ("turn_right", "fallback_occupancy_frontier", False, 0.6, 0.75, 0.3, 2.5, False),
            ("move_forward", "center_detector_target", True, 0.2, 0.9, 0.7, 0.25, True),
        ]
    )

    model = train_official_view_recall_logistic_model(
        dataset,
        epochs=600,
        learning_rate=0.25,
        l2=0.0,
    )
    positive_score = predict_official_view_recall(model, dataset["examples"][0])
    negative_score = predict_official_view_recall(model, dataset["examples"][2])

    assert model["task"] == "habitat_official_view_recall_logistic_model"
    assert model["label_name"] == "hidden_to_visible_within_horizon"
    assert model["dataset"]["source_example_count"] == 5
    assert model["dataset"]["example_count"] == 4
    assert model["dataset"]["positive_count"] == 2
    assert model["dataset"]["negative_count"] == 2
    assert model["dataset"]["training_filter"] == {"current_hidden_only": True}
    assert "target_visible_within_horizon" not in model["feature_names"]
    assert "current_target_visible" not in model["feature_names"]
    assert model["metrics"]["roc_auc"] == 1.0
    assert positive_score > negative_score
    assert positive_score > 0.75
    assert negative_score < 0.25


def test_official_view_recall_model_scores_candidate_action_overrides() -> None:
    model = _manual_model(
        ["action_turn_left", "action_move_forward"],
        [3.0, -3.0],
    )
    example = _view_recall_dataset(
        [
            ("move_forward", "turn_toward_memory_active_perception_frontier", False, 1.8, 0.52, 0.98, 0.5, True),
        ]
    )["examples"][0]

    move_forward_score = predict_official_view_recall(
        model,
        example,
        action="move_forward",
    )
    turn_left_score = predict_official_view_recall(
        model,
        example,
        action="turn_left",
    )
    scores = score_official_view_recall_candidates(
        model,
        example,
        actions=("move_forward", "turn_left"),
    )

    assert turn_left_score > move_forward_score
    assert scores["best_action"] == "turn_left"
    assert scores["scores"]["turn_left"] > scores["scores"]["move_forward"]


def test_official_view_recall_model_score_report_and_csv(
    tmp_path,
) -> None:
    dataset = _view_recall_dataset(
        [
            ("turn_left", "turn_toward_memory_active_perception_frontier", False, 1.8, 0.52, 0.98, 0.5, True),
            ("move_forward", "move_toward_memory_belief_frontier", False, 0.4, 0.78, 0.2, 3.0, False),
            ("move_forward", "center_detector_target", True, 0.2, 0.9, 0.7, 0.25, True),
        ]
    )
    model = _manual_model(
        ["action_turn_left", "action_move_forward"],
        [3.0, -3.0],
    )
    csv_path = tmp_path / "view_recall_scores.csv"

    report = score_official_view_recall_dataset(
        dataset,
        model,
        actions=("move_forward", "turn_left"),
    )
    write_official_view_recall_scores_csv(
        csv_path,
        report["rows"],
        candidate_actions=report["candidate_actions"],
    )

    assert report["task"] == "habitat_official_view_recall_score_report"
    assert report["label_name"] == "hidden_to_visible_within_horizon"
    assert report["source_example_count"] == 3
    assert report["example_count"] == 2
    assert report["filter"] == {"current_hidden_only": True}
    assert report["metrics"]["roc_auc"] == 1.0
    assert report["aggregate"]["label_positive_count"] == 1
    assert report["aggregate"]["label_negative_count"] == 1
    assert report["aggregate"]["top_1_positive_count"] == 1
    assert report["aggregate"]["best_action_counts"] == {
        "turn_left": 2,
    }
    assert report["groups"]["decision"]["turn_toward_memory_active_perception_frontier"][
        "positive_count"
    ] == 1
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "candidate_score_move_forward" in csv_text
    assert "candidate_score_turn_left" in csv_text


def test_official_view_recall_training_cli_writes_model(tmp_path) -> None:
    from objectnav_core.cli.train_habitat_official_view_recall_model import main

    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "model.json"
    dataset_path.write_text(
        json.dumps(
            _view_recall_dataset(
                [
                    ("turn_left", "turn_toward_memory_active_perception_frontier", False, 1.8, 0.52, 0.98, 0.5, True),
                    ("turn_left", "turn_toward_memory_active_perception_frontier", False, 1.9, 0.51, 0.97, 0.5, True),
                    ("move_forward", "move_toward_memory_belief_frontier", False, 0.4, 0.78, 0.2, 3.0, False),
                    ("turn_right", "fallback_occupancy_frontier", False, 0.6, 0.75, 0.3, 2.5, False),
                ]
            )
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            str(dataset_path),
            "--output",
            str(output_path),
            "--epochs",
            "300",
            "--learning-rate",
            "0.2",
            "--l2",
            "0",
        ]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["task"] == "habitat_official_view_recall_logistic_model"
    assert report["label_name"] == "hidden_to_visible_within_horizon"
    assert report["dataset"]["example_count"] == 4
    assert report["dataset"]["positive_count"] == 2
    assert report["dataset"]["negative_count"] == 2
    assert "distance_to_anchor_m" in report["feature_names"]
    assert "source_dataset" in report


def test_official_view_recall_score_cli_writes_report_and_csv(tmp_path) -> None:
    from objectnav_core.cli.score_habitat_official_view_recall_model import main

    dataset_path = tmp_path / "dataset.json"
    model_path = tmp_path / "model.json"
    output_path = tmp_path / "scores.json"
    csv_path = tmp_path / "scores.csv"
    dataset_path.write_text(
        json.dumps(
            _view_recall_dataset(
                [
                    ("turn_left", "turn_toward_memory_active_perception_frontier", False, 1.8, 0.52, 0.98, 0.5, True),
                    ("move_forward", "move_toward_memory_belief_frontier", False, 0.4, 0.78, 0.2, 3.0, False),
                ]
            )
        ),
        encoding="utf-8",
    )
    model_path.write_text(json.dumps(_manual_model(["action_turn_left"], [3.0])), encoding="utf-8")

    exit_code = main(
        [
            str(dataset_path),
            "--model",
            str(model_path),
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_path),
            "--actions",
            "move_forward,turn_left",
        ]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["task"] == "habitat_official_view_recall_score_report"
    assert report["candidate_actions"] == ["move_forward", "turn_left"]
    assert report["source_dataset"] == str(dataset_path)
    assert report["source_model"] == str(model_path)
    assert "candidate_score_turn_left" in csv_path.read_text(encoding="utf-8")


def _view_recall_dataset(
    rows: list[tuple[str, str, bool, float, float, float, float, bool]],
) -> dict[str, object]:
    examples = []
    for index, (
        action,
        decision,
        current_visible,
        distance_to_anchor,
        expected_evidence,
        view_quality,
        path_distance,
        future_visible,
    ) in enumerate(rows):
        examples.append(
            {
                "episode_index": 0,
                "episode_id": "synthetic",
                "scene_id": "hm3d/test.scene.glb",
                "target_category": "chair",
                "policy": "memory_active_perception_frontier",
                "policy_kind": "memory_active_perception_frontier_active_search",
                "step_index": index,
                "action": action,
                "decision": decision,
                "features": {
                    "current_target_visible": current_visible,
                    "current_target_match_count": 1 if current_visible else 0,
                    "current_detector_confidence": 0.8 if current_visible else None,
                    "x_m": 0.1 * index,
                    "z_m": 0.2 * index,
                    "heading_rad": -0.1 * index,
                    "distance_to_anchor_m": distance_to_anchor,
                    "anchor_bearing_error_rad": 0.2,
                    "expected_evidence": expected_evidence,
                    "view_quality": view_quality,
                    "path_distance_m": path_distance,
                    "travel_distance_m": path_distance,
                    "active_perception_phase": "",
                    "active_perception_scan_steps_remaining": None,
                },
                "labels": {
                    "target_visible_next": False,
                    "target_visible_within_horizon": future_visible,
                    "first_target_visible_step_delta": 2 if future_visible else None,
                    "future_target_match_count": 1 if future_visible else 0,
                    "best_future_detector_confidence": 0.82 if future_visible else None,
                },
            }
        )
    return {
        "task": "habitat_official_view_recall_dataset",
        "schema_version": "official-view-recall-v1",
        "feature_schema": [],
        "label_schema": [],
        "example_count": len(examples),
        "examples": examples,
    }


def _manual_model(
    feature_names: list[str],
    weights: list[float],
) -> dict[str, object]:
    return {
        "task": "habitat_official_view_recall_logistic_model",
        "model_type": "logistic_regression",
        "label_name": "hidden_to_visible_within_horizon",
        "feature_names": feature_names,
        "weights": weights,
        "bias": 0.0,
        "preprocessing": {
            "feature_means": {name: 0.0 for name in feature_names},
            "feature_scales": {name: 1.0 for name in feature_names},
            "missing_value_count": 0,
            "warnings": [],
        },
    }
