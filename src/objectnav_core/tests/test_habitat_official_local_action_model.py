from __future__ import annotations

import json
from pathlib import Path

from objectnav_core.evaluation.habitat_official_local_action_model import (
    predict_official_local_action_success,
    score_official_local_action_candidates,
    train_official_local_action_logistic_model,
)


def test_official_local_action_model_scores_candidate_action_overrides() -> None:
    dataset = _local_action_dataset(
        [
            ("move_forward", True, 0.78, 0.032, 0.18, True),
            ("move_forward", True, 0.74, 0.028, 0.20, True),
            ("move_forward", True, 0.81, 0.035, 0.16, True),
            ("turn_right", True, 0.78, 0.032, 0.18, False),
            ("turn_right", True, 0.74, 0.028, 0.20, False),
            ("turn_left", True, 0.81, 0.035, 0.16, False),
        ]
    )

    model = train_official_local_action_logistic_model(
        dataset,
        epochs=600,
        learning_rate=0.25,
        l2=0.0,
    )

    candidate = dataset["examples"][0]
    move_forward_score = predict_official_local_action_success(
        model,
        candidate,
        action="move_forward",
    )
    turn_right_score = predict_official_local_action_success(
        model,
        candidate,
        action="turn_right",
    )
    scores = score_official_local_action_candidates(
        model,
        candidate,
        actions=("turn_right", "move_forward", "turn_left"),
    )

    assert model["task"] == "habitat_official_local_action_logistic_model"
    assert model["label_name"] == "next_target_visible"
    assert model["dataset"]["example_count"] == 6
    assert model["dataset"]["positive_count"] == 3
    assert model["dataset"]["negative_count"] == 3
    assert model["metrics"]["accuracy"] == 1.0
    assert move_forward_score > turn_right_score
    assert move_forward_score > 0.75
    assert turn_right_score < 0.25
    assert scores["best_action"] == "move_forward"
    assert scores["scores"]["move_forward"] > scores["scores"]["turn_right"]
    assert scores["scores"]["move_forward"] > scores["scores"]["turn_left"]


def test_official_local_action_model_excludes_outcome_fields_from_features() -> None:
    model = train_official_local_action_logistic_model(
        _local_action_dataset(
            [
                ("move_forward", True, 0.8, 0.03, 0.2, True),
                ("turn_right", True, 0.8, 0.03, 0.2, False),
            ]
        ),
        epochs=50,
    )

    forbidden = {
        "next_target_visible",
        "target_retained",
        "target_lost",
        "target_acquired",
        "translation_delta_m",
        "bbox_area_fraction_delta",
        "abs_center_offset_fraction_delta",
    }
    assert forbidden.isdisjoint(set(model["feature_names"]))
    assert "action_move_forward" in model["feature_names"]
    assert "action_turn_right" in model["feature_names"]
    assert "current_abs_center_offset_fraction" in model["feature_names"]


def test_official_local_action_model_scores_state_action_interactions() -> None:
    model = _interaction_model(
        [
            "action_move_forward",
            "action_turn_left__current_abs_center_offset_fraction",
            "action_move_forward__current_abs_center_offset_fraction",
        ],
        [1.0, 4.0, -4.0],
    )
    low_offset_example = _candidate_example(abs_offset=0.1)
    high_offset_example = _candidate_example(abs_offset=0.5)

    low_scores = score_official_local_action_candidates(
        model,
        low_offset_example,
        actions=("move_forward", "turn_left", "turn_right"),
    )
    high_scores = score_official_local_action_candidates(
        model,
        high_offset_example,
        actions=("move_forward", "turn_left", "turn_right"),
    )

    assert low_scores["best_action"] == "move_forward"
    assert high_scores["best_action"] == "turn_left"
    assert low_scores["scores"]["move_forward"] > low_scores["scores"]["turn_left"]
    assert high_scores["scores"]["turn_left"] > high_scores["scores"]["move_forward"]


def test_official_local_action_model_candidate_score_report_summarizes_rankings() -> None:
    from objectnav_core.evaluation.habitat_official_local_action_model import (
        score_official_local_action_dataset_candidates,
    )

    dataset = _local_action_dataset(
        [
            ("move_forward", True, 0.8, 0.03, 0.1, True),
            ("turn_left", True, 0.8, 0.03, 0.5, True),
        ]
    )
    model = _interaction_model(
        [
            "action_move_forward",
            "action_turn_left__current_abs_center_offset_fraction",
            "action_move_forward__current_abs_center_offset_fraction",
        ],
        [1.0, 4.0, -4.0],
    )

    report = score_official_local_action_dataset_candidates(
        dataset,
        model,
        actions=("move_forward", "turn_left"),
    )

    assert report["task"] == "habitat_official_local_action_candidate_score_report"
    assert report["label_name"] == "next_target_visible"
    assert report["source_example_count"] == 2
    assert report["example_count"] == 2
    assert report["aggregate"]["best_action_counts"] == {
        "move_forward": 1,
        "turn_left": 1,
    }
    assert report["aggregate"]["best_matches_observed_action_count"] == 2
    assert report["rows"][0]["best_action"] == "move_forward"
    assert report["rows"][1]["best_action"] == "turn_left"
    assert report["rows"][0]["candidate_scores"]["move_forward"] > (
        report["rows"][0]["candidate_scores"]["turn_left"]
    )


def test_official_local_action_model_trains_requested_label() -> None:
    dataset = _local_action_dataset(
        [
            ("move_forward", True, 0.8, 0.03, 0.2, True),
            ("turn_left", True, 0.7, 0.02, 0.3, False),
            ("turn_right", True, 0.7, 0.02, 0.3, False),
        ]
    )
    dataset["examples"][0]["labels"]["target_visible_at_horizon"] = False
    dataset["examples"][1]["labels"]["target_visible_at_horizon"] = True
    dataset["examples"][2]["labels"]["target_visible_at_horizon"] = True

    model = train_official_local_action_logistic_model(
        dataset,
        label_name="target_visible_at_horizon",
        epochs=0,
    )

    assert model["label_name"] == "target_visible_at_horizon"
    assert model["dataset"]["positive_count"] == 2
    assert model["dataset"]["negative_count"] == 1


def test_official_local_action_model_trains_current_visible_slice() -> None:
    dataset = _local_action_dataset(
        [
            ("move_forward", True, 0.8, 0.03, 0.2, True),
            ("turn_left", False, None, None, None, True),
            ("turn_right", True, 0.7, 0.02, 0.3, False),
        ]
    )

    model = train_official_local_action_logistic_model(
        dataset,
        current_visible_only=True,
        epochs=0,
    )

    assert model["dataset"]["source_example_count"] == 3
    assert model["dataset"]["example_count"] == 2
    assert model["dataset"]["positive_count"] == 1
    assert model["dataset"]["negative_count"] == 1
    assert model["dataset"]["training_filter"] == {
        "current_visible_only": True,
    }


def test_official_local_action_training_cli_writes_model(tmp_path: Path) -> None:
    from objectnav_core.cli.train_habitat_official_local_action_model import main

    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "model.json"
    dataset_path.write_text(
        json.dumps(
            _local_action_dataset(
                [
                    ("move_forward", True, 0.8, 0.03, 0.2, True),
                    ("move_forward", True, 0.7, 0.02, 0.3, True),
                    ("turn_right", True, 0.8, 0.03, 0.2, False),
                    ("turn_left", True, 0.7, 0.02, 0.3, False),
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
            "200",
            "--learning-rate",
            "0.2",
            "--l2",
            "0",
        ]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["task"] == "habitat_official_local_action_logistic_model"
    assert report["label_name"] == "next_target_visible"
    assert report["dataset"]["example_count"] == 4
    assert report["dataset"]["positive_count"] == 2
    assert report["dataset"]["negative_count"] == 2
    assert "feature_means" in report["preprocessing"]
    assert "action_move_forward" in report["feature_names"]


def test_official_local_action_training_cli_accepts_label(tmp_path: Path) -> None:
    from objectnav_core.cli.train_habitat_official_local_action_model import main

    dataset = _local_action_dataset(
        [
            ("move_forward", True, 0.8, 0.03, 0.2, True),
            ("turn_right", True, 0.8, 0.03, 0.2, False),
            ("turn_left", True, 0.7, 0.02, 0.3, False),
        ]
    )
    dataset["examples"][0]["labels"]["target_visible_at_horizon"] = False
    dataset["examples"][1]["labels"]["target_visible_at_horizon"] = True
    dataset["examples"][2]["labels"]["target_visible_at_horizon"] = True
    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "model.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    exit_code = main(
        [
            str(dataset_path),
            "--output",
            str(output_path),
            "--label",
            "target_visible_at_horizon",
            "--epochs",
            "0",
        ]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["label_name"] == "target_visible_at_horizon"
    assert report["dataset"]["positive_count"] == 2
    assert report["dataset"]["negative_count"] == 1


def test_official_local_action_training_cli_filters_current_visible(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.train_habitat_official_local_action_model import main

    dataset = _local_action_dataset(
        [
            ("move_forward", True, 0.8, 0.03, 0.2, True),
            ("turn_left", False, None, None, None, True),
            ("turn_right", True, 0.7, 0.02, 0.3, False),
        ]
    )
    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "model.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    exit_code = main(
        [
            str(dataset_path),
            "--output",
            str(output_path),
            "--current-visible-only",
            "--epochs",
            "0",
        ]
    )

    assert exit_code == 0
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["dataset"]["source_example_count"] == 3
    assert report["dataset"]["example_count"] == 2
    assert report["dataset"]["positive_count"] == 1
    assert report["dataset"]["negative_count"] == 1
    assert report["dataset"]["training_filter"] == {
        "current_visible_only": True,
    }


def test_official_local_action_score_cli_writes_report_and_csv(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.score_habitat_official_local_action_model import main

    dataset = _local_action_dataset(
        [
            ("move_forward", True, 0.8, 0.03, 0.1, True),
            ("turn_left", True, 0.8, 0.03, 0.5, True),
        ]
    )
    model = _interaction_model(
        [
            "action_move_forward",
            "action_turn_left__current_abs_center_offset_fraction",
            "action_move_forward__current_abs_center_offset_fraction",
        ],
        [1.0, 4.0, -4.0],
    )
    dataset_path = tmp_path / "dataset.json"
    model_path = tmp_path / "model.json"
    output_path = tmp_path / "scores.json"
    csv_path = tmp_path / "scores.csv"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
    model_path.write_text(json.dumps(model), encoding="utf-8")

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
    assert report["task"] == "habitat_official_local_action_candidate_score_report"
    assert report["aggregate"]["best_action_counts"] == {
        "move_forward": 1,
        "turn_left": 1,
    }
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "best_action" in csv_text
    assert "candidate_score_move_forward" in csv_text
    assert "candidate_score_turn_left" in csv_text


def _local_action_dataset(
    rows: list[tuple[str, bool, float | None, float | None, float | None, bool]],
) -> dict[str, object]:
    examples = []
    for index, (
        action,
        current_visible,
        confidence,
        area,
        abs_offset,
        next_visible,
    ) in enumerate(rows):
        examples.append(
            {
                "episode_index": 0,
                "episode_id": "synthetic",
                "scene_id": "hm3d/test.scene.glb",
                "target_category": "tv_monitor",
                "policy": "memory_evidence_frontier",
                "policy_kind": "memory_evidence_frontier_active_search",
                "step_index": index,
                "next_step_index": index + 1,
                "action": action,
                "decision": (
                    "approach_detector_target_after_center_loss"
                    if action == "move_forward"
                    else "center_detector_target"
                ),
                "features": {
                    "current_target_visible": current_visible,
                    "current_target_match_count": 1 if current_visible else 0,
                    "current_detector_confidence": confidence,
                    "current_bbox_area_fraction": area,
                    "current_center_offset_fraction": abs_offset,
                    "current_abs_center_offset_fraction": abs_offset,
                    "x_m": 0.0,
                    "z_m": 0.0,
                    "heading_rad": -2.094,
                    "suppressed_detector_center_action": "turn_right",
                },
                "labels": {
                    "next_target_visible": next_visible,
                    "target_retained": current_visible and next_visible,
                    "target_lost": current_visible and not next_visible,
                    "target_acquired": (not current_visible) and next_visible,
                    "translation_delta_m": 0.25,
                    "bbox_area_fraction_delta": -0.01,
                    "abs_center_offset_fraction_delta": 0.02,
                },
            }
        )
    return {
        "task": "habitat_official_local_action_dataset",
        "schema_version": "official-local-action-effect-v1",
        "feature_schema": [],
        "label_schema": [],
        "example_count": len(examples),
        "examples": examples,
    }


def _candidate_example(*, abs_offset: float) -> dict[str, object]:
    return {
        "action": "move_forward",
        "decision": "learned_local_action_score",
        "features": {
            "current_target_visible": True,
            "current_abs_center_offset_fraction": abs_offset,
        },
        "labels": {"next_target_visible": True},
    }


def _interaction_model(
    feature_names: list[str],
    weights: list[float],
) -> dict[str, object]:
    return {
        "task": "habitat_official_local_action_logistic_model",
        "model_type": "logistic_regression",
        "label_name": "next_target_visible",
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
