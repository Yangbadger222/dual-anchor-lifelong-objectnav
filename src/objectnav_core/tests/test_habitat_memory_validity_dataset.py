from __future__ import annotations

import csv
import json
from pathlib import Path

from objectnav_core.evaluation.habitat_memory_validity_dataset import (
    export_habitat_memory_validity_dataset,
)


def test_memory_validity_exporter_labels_rows_without_future_leakage(
    tmp_path: Path,
) -> None:
    summary_path = _write_summary(
        tmp_path / "run" / "summary.json",
        rows=[_memory_validity_row()],
    )

    report = export_habitat_memory_validity_dataset([summary_path])

    assert report["summary_count"] == 1
    assert report["row_count"] == 1
    assert report["example_count"] == 1
    assert report["label_counts"] == {"invalid": 1, "valid": 0}
    example = report["examples"][0]
    assert example["label_memory_valid"] is False
    assert example["group_id"] == "scene|toilet|relocated:goal_object:1->goal_object:2"
    assert example["features"]["relocation_pair_distance_m"] == 11.5
    assert example["features"]["memory_action_count"] == 171.0
    assert example["features"]["memory_evidence_detector_pixels"] == 23660.0
    assert example["features"]["memory_reliability_current_evidence"] == 0.15
    assert "fallback_evidence_shared_gate_success" not in example["features"]
    assert "success" not in example["features"]


def test_memory_validity_dataset_cli_writes_json_and_csv(tmp_path: Path) -> None:
    from objectnav_core.cli.export_habitat_memory_validity_dataset import main

    summary_path = _write_summary(
        tmp_path / "run" / "summary.json",
        rows=[_memory_validity_row()],
    )
    output_path = tmp_path / "dataset.json"
    csv_path = tmp_path / "examples.csv"

    assert (
        main(
            [
                str(summary_path),
                "--output",
                str(output_path),
                "--csv-output",
                str(csv_path),
            ]
        )
        == 0
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["example_count"] == 1
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["label_memory_valid"] == "False"
    assert rows[0]["relocation_pair_distance_m"] == "11.5"


def _write_summary(path: Path, *, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": "habitat_closed_loop_dual_anchor_objectnav",
        "challenge": "goal_object_relocation",
        "detector": "grounding_dino",
        "frontier_mode": "navmesh_frontier",
        "route_observation_mode": "option_end",
        "memory_reliability_mode": "event_posterior",
        "rows": rows,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _memory_validity_row() -> dict[str, object]:
    return {
        "group_id": "scene|toilet|relocated:goal_object:1->goal_object:2",
        "category": "toilet",
        "policy": "memory_guided",
        "query_repeat_index": 0,
        "success": True,
        "selected_candidate_types": ["frontier"],
        "memory_decision": "frontier_first",
        "memory_decision_bucket": "harmful_memory_reuse_avoided",
        "hindsight_best_candidate_type": "frontier",
        "memory_instance_id": "goal_object:1",
        "target_instance_id": "goal_object:2",
        "relocation_pair_distance_m": 11.5,
        "memory_action_count": 171,
        "fallback_action_count": 430,
        "fallback_from_memory_action_count": 390,
        "memory_valid_prior": 0.2875,
        "memory_evidence": {
            "shared_gate_success": False,
            "evidence_reason": "detector_positive_mask",
            "detector_pixels": 23660,
            "overlap_pixels": 0,
            "detector_precision": 0.0,
            "oracle_recall": 0.0,
        },
        "fallback_evidence": {
            "shared_gate_success": True,
            "detector_pixels": 18000,
        },
        "memory_reliability": {
            "mode": "event_posterior",
            "value": 0.2875,
            "components": {
                "base_prior": 0.5,
                "current_evidence": 0.15,
                "detector_event_confirmed_weight": 0.0,
                "detector_event_count": 0.0,
                "detector_event_posterior": 0.5,
                "detector_event_suppressed_weight": 0.0,
                "matching": 1.0,
                "recency": 1.0,
                "transform_covariance": 0.909091,
            },
        },
    }
