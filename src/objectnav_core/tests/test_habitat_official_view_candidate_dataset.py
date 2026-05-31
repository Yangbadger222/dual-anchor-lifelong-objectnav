from __future__ import annotations

import json
from pathlib import Path

from objectnav_core.evaluation.habitat_official_view_candidate_dataset import (
    export_official_view_candidate_dataset,
    write_official_view_candidate_dataset_csv,
)


def test_official_view_candidate_dataset_labels_only_selected_candidate(
    tmp_path: Path,
) -> None:
    policy_trace_path, detector_trace_path = _write_candidate_trace_pair(tmp_path)

    dataset = export_official_view_candidate_dataset(
        policy_trace_path,
        detector_trace_path=detector_trace_path,
        source_run_id="synthetic-candidate-recall",
        horizon_steps=2,
    )

    assert dataset["task"] == "habitat_official_view_candidate_dataset"
    assert dataset["schema_version"] == "official-view-candidate-recall-v1"
    assert dataset["state_count"] == 1
    assert dataset["candidate_count"] == 2
    assert dataset["selected_candidate_count"] == 1
    assert dataset["observed_positive_candidate_count"] == 1
    assert dataset["unobserved_candidate_count"] == 1

    selected = dataset["candidates"][0]
    unselected = dataset["candidates"][1]
    assert selected["candidate_rank"] == 0
    assert selected["is_selected_candidate"] is True
    assert selected["candidate_score"] == 0.42
    assert selected["viewpoint_row"] == 10
    assert selected["frontier_col"] == 12
    assert selected["labels"] == {
        "state_target_visible_within_horizon": True,
        "state_hidden_to_visible_within_horizon": True,
        "observed_candidate_label_available": True,
        "observed_candidate_hidden_to_visible_within_horizon": True,
    }
    assert unselected["candidate_rank"] == 1
    assert unselected["is_selected_candidate"] is False
    assert unselected["labels"]["state_hidden_to_visible_within_horizon"] is True
    assert unselected["labels"]["observed_candidate_label_available"] is False
    assert unselected["labels"]["observed_candidate_hidden_to_visible_within_horizon"] is None


def test_official_view_candidate_dataset_writes_stable_csv(tmp_path: Path) -> None:
    policy_trace_path, detector_trace_path = _write_candidate_trace_pair(tmp_path)
    dataset = export_official_view_candidate_dataset(
        policy_trace_path,
        detector_trace_path=detector_trace_path,
        source_run_id="synthetic-candidate-recall",
        horizon_steps=2,
    )
    csv_path = tmp_path / "candidate_recall.csv"

    write_official_view_candidate_dataset_csv(dataset, csv_path)

    rows = csv_path.read_text(encoding="utf-8").splitlines()
    header = rows[0].split(",")
    assert "candidate_rank" in header
    assert "is_selected_candidate" in header
    assert "observed_candidate_label_available" in header
    assert "observed_candidate_hidden_to_visible_within_horizon" in header
    assert "synthetic-candidate-recall" in rows[1]
    assert rows[2].endswith(",false,")


def test_official_view_candidate_dataset_cli_writes_json_and_csv(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.export_habitat_official_view_candidate_dataset import main

    policy_trace_path, detector_trace_path = _write_candidate_trace_pair(tmp_path)
    output_path = tmp_path / "dataset.json"
    csv_path = tmp_path / "candidates.csv"

    exit_code = main(
        [
            str(policy_trace_path),
            "--detector-trace",
            str(detector_trace_path),
            "--output",
            str(output_path),
            "--csv-output",
            str(csv_path),
            "--source-run-id",
            "synthetic-candidate-recall",
            "--horizon-steps",
            "2",
        ]
    )

    assert exit_code == 0
    dataset = json.loads(output_path.read_text(encoding="utf-8"))
    assert dataset["task"] == "habitat_official_view_candidate_dataset"
    assert dataset["candidate_count"] == 2
    assert "observed_candidate_label_available" in csv_path.read_text(
        encoding="utf-8"
    )


def _write_candidate_trace_pair(tmp_path: Path) -> tuple[Path, Path]:
    policy_trace_path = tmp_path / "policy_trace.json"
    detector_trace_path = tmp_path / "detector_trace.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=0,
                        action="turn_left",
                        decision="turn_toward_memory_active_perception_frontier",
                        memory_prior={
                            "decision": "turn_toward_memory_active_perception_frontier",
                            "selected_viewpoint_cell": [10, 11],
                            "selected_frontier_cell": [10, 12],
                            "active_perception_candidate_count": 2,
                            "top_candidates": [
                                _candidate(
                                    viewpoint_cell=[10, 11],
                                    frontier_cell=[10, 12],
                                    score=0.42,
                                    expected_evidence=0.5,
                                    travel_distance_m=0.75,
                                ),
                                _candidate(
                                    viewpoint_cell=[9, 11],
                                    frontier_cell=[9, 12],
                                    score=0.31,
                                    expected_evidence=0.48,
                                    travel_distance_m=1.25,
                                ),
                            ],
                        },
                    ),
                    _policy_step(step_index=1, action="turn_left", decision="scan"),
                    _policy_step(step_index=2, action="move_forward", decision="center"),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    detector_trace_path.write_text(
        json.dumps(
            {
                "task": "official_query_detector_trace",
                "calls": [
                    _detector_call(step_index=0, target_match_count=0),
                    _detector_call(step_index=1, target_match_count=0),
                    _detector_call(step_index=2, target_match_count=1),
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return policy_trace_path, detector_trace_path


def _policy_step(
    *,
    step_index: int,
    action: str,
    decision: str,
    memory_prior: dict[str, object] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "action": action,
        "decision": decision,
        "episode_id": "episode-0",
        "episode_index": 0,
        "heading_rad": 0.1 * step_index,
        "policy": "memory_active_perception_frontier",
        "policy_kind": "memory_active_perception_frontier_active_search",
        "scene_id": "scene.glb",
        "step_index": step_index,
        "target_category": "chair",
        "x_m": 0.2 * step_index,
        "z_m": 0.3 * step_index,
    }
    if memory_prior is not None:
        row["memory_prior"] = memory_prior
    return row


def _candidate(
    *,
    viewpoint_cell: list[int],
    frontier_cell: list[int],
    score: float,
    expected_evidence: float,
    travel_distance_m: float,
) -> dict[str, object]:
    return {
        "bearing_error_rad": -0.3,
        "bearing_rad": -0.5,
        "belief_mass": 0.6,
        "distance_to_anchor_m": 1.8,
        "expected_evidence": expected_evidence,
        "frontier_cell": frontier_cell,
        "path_distance_m": travel_distance_m,
        "score": score,
        "travel_distance_m": travel_distance_m,
        "view_bearing_quality": 1.0,
        "view_distance_quality": 0.9,
        "view_quality": 0.9,
        "viewpoint_cell": viewpoint_cell,
    }


def _detector_call(
    *,
    step_index: int,
    target_match_count: int,
) -> dict[str, object]:
    detections: list[dict[str, object]] = []
    if target_match_count:
        detections.append(
            {
                "bbox": [10, 20, 100, 160],
                "category": "chair",
                "confidence": 0.81,
                "matches_target": True,
            }
        )
    return {
        "call_index": step_index,
        "detections": detections,
        "episode_id": "episode-0",
        "episode_index": 0,
        "missing_rgb": False,
        "scene_id": "scene.glb",
        "step_index": step_index,
        "target_category": "chair",
        "target_match_count": target_match_count,
    }
