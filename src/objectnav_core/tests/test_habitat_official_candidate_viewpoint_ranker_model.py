from __future__ import annotations

import json
from pathlib import Path


def test_candidate_viewpoint_ranker_trains_without_label_leakage() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_viewpoint_ranker_model import (
        predict_official_candidate_viewpoint_ranker,
        train_official_candidate_viewpoint_ranker_model,
    )

    dataset = _candidate_viewpoint_dataset()

    model = train_official_candidate_viewpoint_ranker_model(
        dataset,
        epochs=800,
        learning_rate=0.25,
        l2=0.0,
    )
    positive_score = predict_official_candidate_viewpoint_ranker(
        model,
        dataset["candidate_viewpoints"][1],
    )
    negative_score = predict_official_candidate_viewpoint_ranker(
        model,
        dataset["candidate_viewpoints"][0],
    )

    assert model["task"] == "habitat_official_candidate_viewpoint_ranker_model"
    assert model["label_name"] == "hidden_to_visible_from_candidate_viewpoint"
    assert model["dataset"]["source_candidate_count"] == 7
    assert model["dataset"]["candidate_count"] == 6
    assert model["dataset"]["positive_count"] == 3
    assert model["dataset"]["negative_count"] == 3
    assert "candidate_x_m" in model["feature_names"]
    assert "state_feature=memory_active_perception_phase_rank" in model["feature_names"]
    assert not any("visible_heading_count" in name for name in model["feature_names"])
    assert not any("best_detector_confidence" in name for name in model["feature_names"])
    assert not any("target_visible_from_candidate" in name for name in model["feature_names"])
    assert model["metrics"]["roc_auc"] == 1.0
    assert positive_score > negative_score


def test_candidate_viewpoint_ranker_can_exclude_candidate_rank_feature() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_viewpoint_ranker_model import (
        train_official_candidate_viewpoint_ranker_model,
    )

    model = train_official_candidate_viewpoint_ranker_model(
        _candidate_viewpoint_dataset(),
        epochs=10,
        excluded_feature_names=["candidate_rank"],
    )

    assert "candidate_rank" not in model["feature_names"]
    assert "candidate_score" in model["feature_names"]
    assert model["dataset"]["training_filter"]["excluded_feature_names"] == [
        "candidate_rank"
    ]


def test_candidate_viewpoint_ranker_excludes_option_outcome_fields_from_features() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_viewpoint_ranker_model import (
        train_official_candidate_viewpoint_ranker_model,
    )

    dataset = _candidate_viewpoint_dataset()
    for row in dataset["candidate_viewpoints"]:
        if not isinstance(row, dict):
            continue
        positive = bool(row["labels"]["hidden_to_visible_from_candidate_viewpoint"])
        row["detector_confidence_gain"] = 0.91 if positive else 0.0
        row["distance_to_goal_delta_m"] = 0.4 if positive else -0.1
        row["best_distance_to_goal_delta_m"] = 0.5 if positive else 0.0
        row["stop_probe_success"] = 1.0 if positive else 0.0
        row["labels"]["official_progress_within_option_rollout"] = positive

    model = train_official_candidate_viewpoint_ranker_model(
        dataset,
        label_name="official_progress_within_option_rollout",
        epochs=10,
    )

    assert "detector_confidence_gain" not in model["feature_names"]
    assert "distance_to_goal_delta_m" not in model["feature_names"]
    assert "best_distance_to_goal_delta_m" not in model["feature_names"]
    assert "stop_probe_success" not in model["feature_names"]
    assert model["dataset"]["positive_count"] == 3


def test_candidate_viewpoint_ranker_scores_states_against_baselines(
    tmp_path: Path,
) -> None:
    from objectnav_core.evaluation.habitat_official_candidate_viewpoint_ranker_model import (
        score_official_candidate_viewpoint_ranker_dataset,
        write_official_candidate_viewpoint_ranker_scores_csv,
    )

    dataset = _candidate_viewpoint_dataset()
    model = _manual_model(["candidate_x_m"], [5.0])
    csv_path = tmp_path / "ranker_scores.csv"

    report = score_official_candidate_viewpoint_ranker_dataset(dataset, model)
    write_official_candidate_viewpoint_ranker_scores_csv(report, csv_path)

    assert report["task"] == "habitat_official_candidate_viewpoint_ranker_scores"
    assert report["candidate_count"] == 6
    assert report["state_count"] == 3
    assert report["aggregate"]["oracle_recoverable_state_count"] == 3
    assert report["aggregate"]["model_recovered_state_count"] == 3
    assert report["aggregate"]["top_rank_recovered_state_count"] == 1
    assert report["aggregate"]["top_score_recovered_state_count"] == 0
    assert report["states"][0]["model_candidate_rank"] == 1
    assert report["states"][0]["top_rank_candidate_rank"] == 0
    csv_text = csv_path.read_text(encoding="utf-8")
    assert "model_candidate_rank" in csv_text
    assert "top_score_candidate_rank" in csv_text


def test_candidate_viewpoint_ranker_state_folds_hold_out_states() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_viewpoint_ranker_model import (
        evaluate_candidate_viewpoint_ranker_state_folds,
    )

    evaluation = evaluate_candidate_viewpoint_ranker_state_folds(
        _candidate_viewpoint_dataset(state_count=4),
        fold_count=2,
        epochs=100,
        learning_rate=0.2,
        l2=0.001,
    )

    assert evaluation["task"] == "habitat_official_candidate_viewpoint_ranker_state_folds"
    assert evaluation["aggregate"]["fold_count"] == 2
    assert evaluation["aggregate"]["state_count"] == 4
    assert all(split["train_state_count"] == 2 for split in evaluation["folds"])
    assert all(split["holdout_state_count"] == 2 for split in evaluation["folds"])
    assert all(
        not set(split["train_state_keys"]) & set(split["holdout_state_keys"])
        for split in evaluation["folds"]
    )


def test_candidate_viewpoint_ranker_state_folds_use_custom_label() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_viewpoint_ranker_model import (
        evaluate_candidate_viewpoint_ranker_state_folds,
    )

    dataset = _candidate_viewpoint_dataset(state_count=4)
    for row in dataset["candidate_viewpoints"]:
        if not isinstance(row, dict):
            continue
        labels = row["labels"]
        if not isinstance(labels, dict):
            continue
        option_positive = labels.pop("hidden_to_visible_from_candidate_viewpoint")
        labels["target_visible_within_option_rollout"] = option_positive
        labels["hidden_to_visible_within_option_rollout"] = option_positive

    evaluation = evaluate_candidate_viewpoint_ranker_state_folds(
        dataset,
        label_name="hidden_to_visible_within_option_rollout",
        fold_count=2,
        epochs=100,
        learning_rate=0.2,
        l2=0.001,
    )

    assert evaluation["aggregate"]["oracle_recoverable_state_count"] == 4


def test_candidate_viewpoint_ranker_leave_one_source_holds_out_sources() -> None:
    from objectnav_core.evaluation.habitat_official_candidate_viewpoint_ranker_model import (
        evaluate_candidate_viewpoint_ranker_leave_one_source,
    )

    dataset = _merged_candidate_viewpoint_dataset(
        _candidate_viewpoint_dataset(
            state_count=2,
            source_dataset="source-a.json",
            source_policy_trace="source-a/policy_trace.json",
        ),
        _candidate_viewpoint_dataset(
            state_count=2,
            source_dataset="source-b.json",
            source_policy_trace="source-b/policy_trace.json",
        ),
    )

    evaluation = evaluate_candidate_viewpoint_ranker_leave_one_source(
        dataset,
        epochs=100,
        learning_rate=0.2,
        l2=0.001,
    )

    assert (
        evaluation["task"]
        == "habitat_official_candidate_viewpoint_ranker_leave_one_source"
    )
    assert evaluation["split_field"] == "source_dataset"
    assert evaluation["aggregate"]["split_count"] == 2
    assert evaluation["aggregate"]["state_count"] == 4
    assert sorted(split["holdout_source"] for split in evaluation["splits"]) == [
        "source-a.json",
        "source-b.json",
    ]
    assert all(
        split["holdout_source"] not in split["train_sources"]
        for split in evaluation["splits"]
    )
    assert all(split["holdout_state_count"] == 2 for split in evaluation["splits"])


def test_candidate_viewpoint_ranker_cli_writes_outputs(tmp_path: Path) -> None:
    from objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker import (
        main,
    )

    dataset_path = tmp_path / "candidate_viewpoints.json"
    model_path = tmp_path / "model.json"
    scores_path = tmp_path / "scores.json"
    csv_path = tmp_path / "scores.csv"
    folds_path = tmp_path / "folds.json"
    dataset_path.write_text(
        json.dumps(_candidate_viewpoint_dataset(state_count=4)),
        encoding="utf-8",
    )

    exit_code = main(
        [
            str(dataset_path),
            "--output",
            str(model_path),
            "--scores-output",
            str(scores_path),
            "--csv-output",
            str(csv_path),
            "--state-fold-output",
            str(folds_path),
            "--fold-count",
            "2",
            "--epochs",
            "100",
            "--learning-rate",
            "0.2",
        ]
    )

    assert exit_code == 0
    model = json.loads(model_path.read_text(encoding="utf-8"))
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    folds = json.loads(folds_path.read_text(encoding="utf-8"))
    assert model["task"] == "habitat_official_candidate_viewpoint_ranker_model"
    assert scores["task"] == "habitat_official_candidate_viewpoint_ranker_scores"
    assert folds["aggregate"]["fold_count"] == 2
    assert "model_candidate_rank" in csv_path.read_text(encoding="utf-8")


def test_candidate_viewpoint_ranker_cli_merges_multiple_source_datasets(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker import (
        main,
    )

    first_dataset_path = tmp_path / "source_a.json"
    second_dataset_path = tmp_path / "source_b.json"
    model_path = tmp_path / "model.json"
    leave_one_source_path = tmp_path / "leave_one_source.json"
    first_dataset_path.write_text(
        json.dumps(
            _candidate_viewpoint_dataset(
                state_count=2,
                source_policy_trace="source-a/policy_trace.json",
            )
        ),
        encoding="utf-8",
    )
    second_dataset_path.write_text(
        json.dumps(
            _candidate_viewpoint_dataset(
                state_count=2,
                source_policy_trace="source-b/policy_trace.json",
            )
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            str(first_dataset_path),
            str(second_dataset_path),
            "--output",
            str(model_path),
            "--leave-one-source-output",
            str(leave_one_source_path),
            "--epochs",
            "100",
        ]
    )

    assert exit_code == 0
    model = json.loads(model_path.read_text(encoding="utf-8"))
    leave_one_source = json.loads(leave_one_source_path.read_text(encoding="utf-8"))
    assert model["dataset"]["source_candidate_count"] == 10
    assert model["dataset"]["candidate_count"] == 8
    assert leave_one_source["aggregate"]["split_count"] == 2
    assert sorted(split["holdout_source"] for split in leave_one_source["splits"]) == [
        str(first_dataset_path),
        str(second_dataset_path),
    ]


def test_candidate_viewpoint_ranker_cli_excludes_requested_features(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker import (
        main,
    )

    dataset_path = tmp_path / "candidate_viewpoints.json"
    model_path = tmp_path / "model.json"
    dataset_path.write_text(
        json.dumps(_candidate_viewpoint_dataset()),
        encoding="utf-8",
    )

    exit_code = main(
        [
            str(dataset_path),
            "--output",
            str(model_path),
            "--exclude-feature",
            "candidate_rank",
            "--exclude-feature",
            "state_feature=memory_active_perception_phase_rank",
            "--epochs",
            "10",
        ]
    )

    assert exit_code == 0
    model = json.loads(model_path.read_text(encoding="utf-8"))
    assert "candidate_rank" not in model["feature_names"]
    assert (
        "state_feature=memory_active_perception_phase_rank"
        not in model["feature_names"]
    )
    assert model["dataset"]["training_filter"]["excluded_feature_names"] == [
        "candidate_rank",
        "state_feature=memory_active_perception_phase_rank",
    ]


def _candidate_viewpoint_dataset(
    *,
    state_count: int = 3,
    source_dataset: str = "synthetic.json",
    source_policy_trace: str = "synthetic/policy_trace.json",
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for state_index in range(state_count):
        positive_rank = 1 if state_index % 2 == 0 else 0
        for rank in range(2):
            positive = rank == positive_rank
            rows.append(
                _candidate_row(
                    state_index=state_index,
                    rank=rank,
                    candidate_x_m=1.0 if positive else 0.0,
                    candidate_score=0.1 if positive else 0.9,
                    positive=positive,
                    source_dataset=source_dataset,
                    source_policy_trace=source_policy_trace,
                )
            )
    rows.append(
        _candidate_row(
            state_index=99,
            rank=0,
            candidate_x_m=1.0,
            candidate_score=1.0,
            positive=True,
            current_visible=True,
            source_dataset=source_dataset,
            source_policy_trace=source_policy_trace,
        )
    )
    return {
        "task": "habitat_official_candidate_viewpoint_restore_dataset",
        "schema_version": "official-candidate-viewpoint-restore-v1",
        "candidate_viewpoint_count": len(rows),
        "candidate_viewpoints": rows,
    }


def _candidate_row(
    *,
    state_index: int,
    rank: int,
    candidate_x_m: float,
    candidate_score: float,
    positive: bool,
    current_visible: bool = False,
    source_dataset: str = "synthetic.json",
    source_policy_trace: str = "synthetic/policy_trace.json",
) -> dict[str, object]:
    return {
        "source_dataset": source_dataset,
        "source_policy_trace": source_policy_trace,
        "state_index": state_index,
        "episode_index": state_index,
        "episode_id": f"episode-{state_index}",
        "scene_id": "scene.glb",
        "target_category": "chair" if state_index % 2 == 0 else "sofa",
        "step_index": 10 + state_index,
        "state_action": "turn_left",
        "state_decision": "turn_toward_memory_active_perception_frontier",
        "candidate_rank": rank,
        "candidate_count": 2,
        "candidate_score": candidate_score,
        "expected_evidence": 0.2 + candidate_x_m,
        "belief_mass": 0.5 + 0.1 * candidate_x_m,
        "distance_to_anchor_m": 1.5 - 0.5 * candidate_x_m,
        "bearing_error_rad": -0.2 + 0.1 * rank,
        "view_quality": 0.5 + 0.4 * candidate_x_m,
        "path_distance_m": 1.0 + rank,
        "travel_distance_m": 1.0 + rank,
        "candidate_x_m": candidate_x_m,
        "candidate_z_m": 0.25 * rank,
        "visible_heading_count": 2 if positive else 0,
        "best_detector_confidence": 0.91 if positive else None,
        "valid_state_restore": True,
        "valid_candidate_restore": True,
        "state_features": {
            "memory_active_perception_phase_rank": 2,
            "memory_anchor_bearing_error_rad": -0.2,
            "local_center_depth_clear": True,
        },
        "labels": {
            "label_available": True,
            "current_target_visible_at_restore": current_visible,
            "target_visible_from_candidate_viewpoint": positive,
            "hidden_to_visible_from_candidate_viewpoint": (
                positive and not current_visible
            ),
        },
    }


def _merged_candidate_viewpoint_dataset(
    *datasets: dict[str, object],
) -> dict[str, object]:
    rows = [
        row
        for dataset in datasets
        for row in dataset["candidate_viewpoints"]
        if isinstance(row, dict)
    ]
    return {
        "task": "habitat_official_candidate_viewpoint_restore_dataset",
        "schema_version": "official-candidate-viewpoint-restore-v1",
        "candidate_viewpoint_count": len(rows),
        "candidate_viewpoints": rows,
    }


def _manual_model(
    feature_names: list[str],
    weights: list[float],
) -> dict[str, object]:
    return {
        "task": "habitat_official_candidate_viewpoint_ranker_model",
        "model_type": "logistic_regression",
        "label_name": "hidden_to_visible_from_candidate_viewpoint",
        "feature_names": feature_names,
        "weights": weights,
        "bias": -2.5,
        "preprocessing": {
            "feature_means": {name: 0.0 for name in feature_names},
            "feature_scales": {name: 1.0 for name in feature_names},
            "missing_value_count": 0,
            "warnings": [],
        },
    }
