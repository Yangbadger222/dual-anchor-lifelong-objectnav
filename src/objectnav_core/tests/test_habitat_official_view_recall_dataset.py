from __future__ import annotations

import json
from pathlib import Path

from objectnav_core.evaluation.habitat_official_view_recall_dataset import (
    export_official_view_recall_dataset,
    write_official_view_recall_dataset_csv,
)


def test_official_view_recall_dataset_labels_future_target_recall(
    tmp_path: Path,
) -> None:
    policy_trace_path, detector_trace_path = _write_view_recall_trace_pair(tmp_path)

    dataset = export_official_view_recall_dataset(
        policy_trace_path,
        detector_trace_path=detector_trace_path,
        source_run_id="synthetic-view-recall",
        horizon_steps=3,
    )

    assert dataset["task"] == "habitat_official_view_recall_dataset"
    assert dataset["schema_version"] == "official-view-recall-v1"
    assert dataset["source_run_id"] == "synthetic-view-recall"
    assert dataset["step_count"] == 4
    assert dataset["example_count"] == 3
    assert dataset["positive_within_horizon_count"] == 2
    assert dataset["active_perception_example_count"] == 2

    first = dataset["examples"][0]
    assert first["step_index"] == 0
    assert first["action"] == "turn_right"
    assert first["decision"] == "orient_memory_anchor_from_active_viewpoint"
    assert first["features"]["current_target_visible"] is False
    assert first["features"]["distance_to_anchor_m"] == 1.7
    assert first["features"]["expected_evidence"] == 0.52
    assert first["features"]["path_distance_m"] == 0.25
    assert first["features"]["active_perception_phase"] == "orient_anchor"
    assert first["features"]["selected_viewpoint_row"] == 43
    assert first["features"]["selected_viewpoint_col"] == 37
    assert first["labels"]["target_visible_next"] is False
    assert first["labels"]["target_visible_within_horizon"] is True
    assert first["labels"]["first_target_visible_step_delta"] == 2
    assert first["labels"]["future_target_match_count"] == 1
    assert first["labels"]["best_future_detector_confidence"] == 0.81


def test_official_view_recall_dataset_writes_stable_csv(tmp_path: Path) -> None:
    policy_trace_path, detector_trace_path = _write_view_recall_trace_pair(tmp_path)
    dataset = export_official_view_recall_dataset(
        policy_trace_path,
        detector_trace_path=detector_trace_path,
        source_run_id="synthetic-view-recall",
        horizon_steps=3,
    )
    csv_path = tmp_path / "view_recall.csv"

    write_official_view_recall_dataset_csv(dataset, csv_path)

    rows = csv_path.read_text(encoding="utf-8").splitlines()
    header = rows[0].split(",")
    assert header[:8] == [
        "source_policy_trace",
        "source_detector_trace",
        "source_run_id",
        "episode_index",
        "episode_id",
        "scene_id",
        "target_category",
        "policy",
    ]
    assert "active_perception_phase" in header
    assert "target_visible_within_horizon" in header
    assert "selected_viewpoint_row" in header
    assert "synthetic-view-recall" in rows[1]
    assert "orient_memory_anchor_from_active_viewpoint" in rows[1]


def test_official_view_recall_dataset_counts_decision_only_active_perception(
    tmp_path: Path,
) -> None:
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
                            "expected_evidence": 0.73,
                        },
                    ),
                    _policy_step(
                        step_index=1,
                        action="move_forward",
                        decision="fallback_occupancy_frontier",
                    ),
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
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    dataset = export_official_view_recall_dataset(
        policy_trace_path,
        detector_trace_path=detector_trace_path,
        source_run_id="decision-only-active-perception",
        horizon_steps=1,
    )

    assert dataset["example_count"] == 1
    assert dataset["active_perception_example_count"] == 1


def _write_view_recall_trace_pair(tmp_path: Path) -> tuple[Path, Path]:
    policy_trace_path = tmp_path / "policy_trace.json"
    detector_trace_path = tmp_path / "detector_trace.json"
    policy_trace_path.write_text(
        json.dumps(
            {
                "task": "official_policy_step_trace",
                "steps": [
                    _policy_step(
                        step_index=0,
                        action="turn_right",
                        decision="orient_memory_anchor_from_active_viewpoint",
                        memory_prior={
                            "decision": "orient_memory_anchor_from_active_viewpoint",
                            "active_perception_phase": "orient_anchor",
                            "distance_to_anchor_m": 1.7,
                            "expected_evidence": 0.52,
                            "view_quality": 0.94,
                            "path_distance_m": 0.25,
                            "travel_distance_m": 0.25,
                            "anchor_bearing_error_rad": 0.4,
                            "active_perception_scan_steps_remaining": 4,
                            "selected_viewpoint_cell": [43, 37],
                            "selected_frontier_cell": [43, 38],
                        },
                    ),
                    _policy_step(
                        step_index=1,
                        action="turn_left",
                        decision="scan_memory_anchor_from_active_viewpoint",
                        memory_prior={
                            "decision": "scan_memory_anchor_from_active_viewpoint",
                            "active_perception_phase": "scan_anchor",
                            "distance_to_anchor_m": 1.7,
                            "expected_evidence": 0.52,
                            "path_distance_m": 0.25,
                            "anchor_bearing_error_rad": 0.1,
                            "active_perception_scan_steps_remaining": 3,
                            "selected_viewpoint_cell": [43, 37],
                            "selected_frontier_cell": [43, 38],
                        },
                    ),
                    _policy_step(
                        step_index=2,
                        action="move_forward",
                        decision="center_detector_target",
                        memory_prior={
                            "decision": "center_detector_target",
                            "detector_confidence": 0.81,
                        },
                    ),
                    _policy_step(
                        step_index=3,
                        action="stop",
                        decision="budget_stop",
                    ),
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
                    _detector_call(step_index=3, target_match_count=0),
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
        "heading_rad": 0.2 * step_index,
        "policy": "memory_active_perception_frontier",
        "policy_kind": "memory_active_perception_frontier_active_search",
        "scene_id": "scene.glb",
        "step_index": step_index,
        "target_category": "chair",
        "x_m": 0.1 * step_index,
        "z_m": 0.2 * step_index,
    }
    if memory_prior is not None:
        row["memory_prior"] = memory_prior
    return row


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
        "detection_count": len(detections),
        "detections": detections,
        "episode_id": "episode-0",
        "episode_index": 0,
        "missing_rgb": False,
        "scene_id": "scene.glb",
        "step_index": step_index,
        "target_category": "chair",
        "target_match_count": target_match_count,
    }
