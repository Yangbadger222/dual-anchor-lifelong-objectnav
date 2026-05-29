from __future__ import annotations

import csv
import json
from pathlib import Path

from objectnav_core.evaluation.habitat_decision_sensitivity import (
    mine_habitat_decision_sensitivity,
)


def test_miner_ranks_close_mixed_event_rows(tmp_path: Path) -> None:
    summary_path = _write_summary(
        tmp_path / "run" / "summary.json",
        rows=[_close_mixed_event_row()],
    )

    report = mine_habitat_decision_sensitivity(
        [summary_path],
        max_margin_actions=5.0,
    )

    assert report["summary_count"] == 1
    assert report["row_count"] == 1
    assert report["candidate_count"] == 1
    candidate = report["candidates"][0]
    assert candidate["category"] == "chair"
    assert candidate["policy"] == "memory_guided"
    assert candidate["decision_margin_actions"] == 2.050443
    assert candidate["detector_event_count"] == 5.0
    assert candidate["evidence_decision"] == "memory_first"
    assert candidate["event_posterior_decision"] == "memory_first"
    assert candidate["counterfactual_decision_flip"] is False
    assert candidate["sensitivity_reasons"] == [
        "close_expected_costs",
        "mixed_detector_events",
        "reliability_delta",
    ]


def test_miner_marks_evidence_to_event_posterior_decision_flips(
    tmp_path: Path,
) -> None:
    summary_path = _write_summary(
        tmp_path / "run" / "summary.json",
        rows=[
            _close_mixed_event_row(category="plant"),
            _counterfactual_flip_row(category="toilet"),
        ],
    )

    report = mine_habitat_decision_sensitivity(
        [summary_path],
        max_margin_actions=5.0,
    )

    assert report["candidate_count"] == 2
    flip = report["candidates"][0]
    assert flip["category"] == "toilet"
    assert flip["evidence_reliability"] == 0.96
    assert flip["event_posterior_reliability"] == 0.4595
    assert flip["evidence_decision"] == "memory_first"
    assert flip["event_posterior_decision"] == "frontier_first"
    assert flip["counterfactual_decision_flip"] is True
    assert "counterfactual_flip" in flip["sensitivity_reasons"]


def test_miner_uses_evidence_reliability_when_event_count_is_zero(
    tmp_path: Path,
) -> None:
    row = _close_mixed_event_row(category="bed")
    row["memory_valid_prior"] = 0.2
    row["expected_memory_first_action_count"] = 62.4
    reliability = row["memory_reliability"]
    assert isinstance(reliability, dict)
    components = reliability["components"]
    assert isinstance(components, dict)
    components["detector_event_count"] = 0.0
    components["detector_event_confirmed_weight"] = 0.0
    components["detector_event_suppressed_weight"] = 0.0
    summary_path = _write_summary(
        tmp_path / "run" / "summary.json",
        rows=[row],
    )

    report = mine_habitat_decision_sensitivity(
        [summary_path],
        max_margin_actions=5.0,
    )

    candidate = report["candidates"][0]
    assert candidate["evidence_reliability"] == 0.96
    assert candidate["event_posterior_reliability"] == 0.96
    assert candidate["event_posterior_decision"] == "memory_first"


def test_miner_marks_reliability_sensitive_decision_boundaries(
    tmp_path: Path,
) -> None:
    summary_path = _write_summary(
        tmp_path / "run" / "summary.json",
        rows=[
            _close_mixed_event_row(category="chair"),
            _reliability_sensitive_row(category="sofa"),
        ],
    )

    report = mine_habitat_decision_sensitivity(
        [summary_path],
        max_margin_actions=5.0,
    )

    sensitive, non_sensitive = report["candidates"][:2]
    assert sensitive["category"] == "sofa"
    assert sensitive["decision_boundary_reliability"] == 0.5
    assert sensitive["decision_boundary_reliability_raw"] == 0.5
    assert sensitive["decision_boundary_region"] == "reliability_sensitive"
    assert "reliability_sensitive_boundary" in sensitive["sensitivity_reasons"]
    assert sensitive["counterfactual_decision_flip"] is False

    assert non_sensitive["category"] == "chair"
    assert non_sensitive["decision_boundary_reliability"] == 0.0
    assert non_sensitive["decision_boundary_reliability_raw"] == 0.0
    assert non_sensitive["decision_boundary_region"] == "memory_always_no_worse"
    assert "reliability_sensitive_boundary" not in non_sensitive[
        "sensitivity_reasons"
    ]
    assert report["aggregate"]["by_boundary_region"] == {
        "memory_always_no_worse": 1,
        "reliability_sensitive": 1,
    }


def test_miner_records_boundary_reliability_interval_gap(
    tmp_path: Path,
) -> None:
    summary_path = _write_summary(
        tmp_path / "run" / "summary.json",
        rows=[_boundary_interval_gap_row()],
    )

    report = mine_habitat_decision_sensitivity(
        [summary_path],
        max_margin_actions=5.0,
    )

    candidate = report["candidates"][0]
    assert candidate["decision_boundary_reliability_raw"] == 1.0
    assert candidate["reliability_interval_min"] == 0.819916
    assert candidate["reliability_interval_max"] == 0.96
    assert candidate["boundary_reliability_interval_gap"] == 0.04
    assert candidate["boundary_reliability_interval_position"] == "above_interval"
    assert "near_reliability_interval_boundary" in candidate["sensitivity_reasons"]
    assert report["aggregate"]["by_reason"]["near_reliability_interval_boundary"] == 1


def test_miner_records_relocation_pair_distance(
    tmp_path: Path,
) -> None:
    row = _reliability_sensitive_row(category="chair")
    row["relocation_pair_distance_m"] = 8.25
    summary_path = _write_summary(
        tmp_path / "run" / "summary.json",
        rows=[row],
    )

    report = mine_habitat_decision_sensitivity(
        [summary_path],
        max_margin_actions=5.0,
    )

    candidate = report["candidates"][0]
    assert candidate["relocation_pair_distance_m"] == 8.25


def test_decision_sensitivity_cli_writes_json_and_csv(tmp_path: Path) -> None:
    from objectnav_core.cli.mine_habitat_decision_sensitivity import main

    input_dir = tmp_path / "inputs"
    _write_summary(
        input_dir / "run" / "summary.json",
        rows=[_close_mixed_event_row()],
    )
    output_path = tmp_path / "report.json"
    csv_path = tmp_path / "candidates.csv"

    assert (
        main(
            [
                str(input_dir),
                "--output",
                str(output_path),
                "--csv-output",
                str(csv_path),
            ]
        )
        == 0
    )

    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert report["candidate_count"] == 1
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["category"] == "chair"
    assert rows[0]["decision_margin_actions"] == "2.050443"


def _write_summary(path: Path, *, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "task": "habitat_closed_loop_dual_anchor_objectnav",
        "challenge": "stable",
        "detector": "grounding_dino",
        "frontier_mode": "navmesh_frontier",
        "route_observation_mode": "per_action",
        "memory_reliability_mode": "event_posterior",
        "memory_valid_prior": 0.5,
        "rows": rows,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _close_mixed_event_row(*, category: str = "chair") -> dict[str, object]:
    return {
        "group_id": f"scene|{category}|goal_object:1",
        "category": category,
        "policy": "memory_guided",
        "query_repeat_index": 0,
        "memory_decision": "memory_first",
        "memory_decision_bucket": "memory_shorter_reused",
        "memory_valid_prior": 0.683481,
        "memory_action_count": 60,
        "fallback_action_count": 63,
        "fallback_from_memory_action_count": 3,
        "expected_memory_first_action_count": 60.949557,
        "expected_frontier_first_action_count": 63.0,
        "hindsight_best_candidate_type": "memory",
        "hindsight_action_regret": 0,
        "hindsight_distance_regret_m": 0.0,
        "memory_reliability_mode": "event_posterior",
        "memory_reliability": {
            "mode": "event_posterior",
            "value": 0.683481,
            "reason": "event_posterior_weighted",
            "components": {
                "base_prior": 0.5,
                "category_prior": 0.82,
                "current_evidence": 0.98,
                "detector_event_confirmed_weight": 3.52259,
                "detector_event_count": 5.0,
                "detector_event_posterior": 0.457238,
                "detector_event_suppressed_weight": 4.275,
                "matching": 1.0,
                "recency": 1.0,
                "transform_covariance": 0.909091,
            },
        },
    }


def _counterfactual_flip_row(*, category: str = "toilet") -> dict[str, object]:
    row = _close_mixed_event_row(category=category)
    row.update(
        {
            "memory_decision": "frontier_first",
            "memory_decision_bucket": "frontier_shorter_selected",
            "memory_valid_prior": 0.4595,
            "memory_action_count": 10,
            "fallback_action_count": 20,
            "fallback_from_memory_action_count": 20,
            "expected_memory_first_action_count": 20.81,
            "expected_frontier_first_action_count": 20.0,
            "hindsight_best_candidate_type": "frontier",
            "memory_reliability": {
                "mode": "event_posterior",
                "value": 0.4595,
                "reason": "event_posterior_weighted",
                "components": {
                    "base_prior": 0.5,
                    "category_prior": 0.82,
                    "current_evidence": 0.98,
                    "detector_event_confirmed_weight": 0.05,
                    "detector_event_count": 4.0,
                    "detector_event_posterior": 0.05,
                    "detector_event_suppressed_weight": 8.0,
                    "matching": 1.0,
                    "recency": 1.0,
                    "transform_covariance": 0.909091,
                },
            },
        }
    )
    return row


def _reliability_sensitive_row(*, category: str = "sofa") -> dict[str, object]:
    row = _close_mixed_event_row(category=category)
    row.update(
        {
            "memory_valid_prior": 0.55,
            "memory_action_count": 10,
            "fallback_action_count": 20,
            "fallback_from_memory_action_count": 20,
            "expected_memory_first_action_count": 19.0,
            "expected_frontier_first_action_count": 20.0,
            "hindsight_best_candidate_type": "memory",
            "memory_reliability": {
                "mode": "event_posterior",
                "value": 0.55,
                "reason": "event_posterior_weighted",
                "components": {
                    "base_prior": 0.5,
                    "category_prior": 0.82,
                    "current_evidence": 0.98,
                    "detector_event_confirmed_weight": 0.6,
                    "detector_event_count": 4.0,
                    "detector_event_posterior": 0.214545,
                    "detector_event_suppressed_weight": 4.0,
                    "matching": 1.0,
                    "recency": 1.0,
                    "transform_covariance": 0.909091,
                },
            },
        }
    )
    return row


def _boundary_interval_gap_row(*, category: str = "sofa") -> dict[str, object]:
    row = _close_mixed_event_row(category=category)
    row.update(
        {
            "memory_decision": "frontier_first",
            "memory_decision_bucket": "frontier_shorter_selected",
            "memory_valid_prior": 0.819916,
            "memory_action_count": 63,
            "fallback_action_count": 63,
            "fallback_from_memory_action_count": 2,
            "expected_memory_first_action_count": 63.360168,
            "expected_frontier_first_action_count": 63.0,
            "hindsight_best_candidate_type": "frontier",
            "memory_reliability": {
                "mode": "event_posterior",
                "value": 0.819916,
                "reason": "event_posterior_weighted",
                "components": {
                    "base_prior": 0.5,
                    "category_prior": 0.82,
                    "current_evidence": 0.98,
                    "detector_event_confirmed_weight": 7.517547,
                    "detector_event_count": 6.0,
                    "detector_event_posterior": 0.705301,
                    "detector_event_suppressed_weight": 2.85,
                    "matching": 1.0,
                    "recency": 1.0,
                    "transform_covariance": 0.909091,
                },
            },
        }
    )
    return row
