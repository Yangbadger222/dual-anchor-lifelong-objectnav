from __future__ import annotations

import json
from pathlib import Path

from objectnav_core.evaluation.habitat_memory_validity_pipeline import (
    run_memory_validity_learning_pipeline,
)


def test_memory_validity_learning_pipeline_writes_all_artifacts(
    tmp_path: Path,
) -> None:
    summary_path = _write_summary(tmp_path / "run" / "summary.json")
    output_dir = tmp_path / "pipeline"

    report = run_memory_validity_learning_pipeline(
        [summary_path],
        output_dir=output_dir,
        feature_names=("memory_evidence_detector_precision",),
        epochs=200,
        learning_rate=0.2,
        l2=0.0,
        holdout_field="category",
        holdout_values=("toilet",),
    )

    assert report["task"] == "habitat_memory_validity_learning_pipeline"
    assert report["dataset"]["example_count"] == 4
    assert report["model"]["split"]["holdout_field"] == "category"
    assert report["model"]["split"]["holdout_example_count"] == 2
    assert report["model"]["evaluation"]["holdout"]["accuracy"] == 1.0
    assert report["scores"]["example_count"] == 4
    assert report["decision_sensitivity"]["candidate_count"] == 4
    assert report["decision_sensitivity"]["aggregate"]["by_boundary_region"] == {
        "reliability_sensitive": 4
    }
    for artifact_path in report["artifacts"].values():
        assert Path(artifact_path).exists()
    model = json.loads((output_dir / "model.json").read_text(encoding="utf-8"))
    assert model["split"]["holdout_values"] == ["toilet"]
    scores = json.loads((output_dir / "scores.json").read_text(encoding="utf-8"))
    assert scores["aggregate"]["boundary_region_counts"] == {
        "reliability_sensitive": 4
    }
    sensitivity = json.loads(
        (output_dir / "decision_sensitivity.json").read_text(encoding="utf-8")
    )
    assert sensitivity["candidate_count"] == 4


def test_memory_validity_learning_pipeline_cli(tmp_path: Path) -> None:
    from objectnav_core.cli.run_habitat_memory_validity_learning_pipeline import main

    summary_path = _write_summary(tmp_path / "run" / "summary.json")
    output_dir = tmp_path / "pipeline_cli"

    assert (
        main(
            [
                str(summary_path),
                "--output-dir",
                str(output_dir),
                "--features",
                "memory_evidence_detector_precision",
                "--epochs",
                "200",
                "--learning-rate",
                "0.2",
                "--l2",
                "0",
                "--holdout-field",
                "category",
                "--holdout-values",
                "toilet",
            ]
        )
        == 0
    )

    report = json.loads(
        (output_dir / "pipeline_report.json").read_text(encoding="utf-8")
    )
    assert report["dataset"]["example_count"] == 4
    assert report["model"]["evaluation"]["holdout"]["example_count"] == 2
    assert report["scores"]["aggregate"]["learned_memory_first_count"] == 2
    assert report["decision_sensitivity"]["candidate_count"] == 4


def test_memory_validity_learning_pipeline_cli_can_skip_sensitivity(
    tmp_path: Path,
) -> None:
    from objectnav_core.cli.run_habitat_memory_validity_learning_pipeline import main

    summary_path = _write_summary(tmp_path / "run" / "summary.json")
    output_dir = tmp_path / "pipeline_skip"

    assert (
        main(
            [
                str(summary_path),
                "--output-dir",
                str(output_dir),
                "--features",
                "memory_evidence_detector_precision",
                "--skip-decision-sensitivity",
            ]
        )
        == 0
    )

    report = json.loads(
        (output_dir / "pipeline_report.json").read_text(encoding="utf-8")
    )
    assert report["decision_sensitivity"] is None
    assert "decision_sensitivity_json" not in report["artifacts"]
    assert not (output_dir / "decision_sensitivity.json").exists()


def _write_summary(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "task": "habitat_closed_loop_dual_anchor_objectnav",
        "challenge": "goal_object_relocation",
        "detector": "grounding_dino",
        "frontier_mode": "navmesh_frontier",
        "route_observation_mode": "option_end",
        "rows": [
            _row(category="chair", valid=False, precision=0.0, group_id="chair:0"),
            _row(category="chair", valid=True, precision=1.0, group_id="chair:1"),
            _row(category="toilet", valid=False, precision=0.0, group_id="toilet:0"),
            _row(category="toilet", valid=True, precision=1.0, group_id="toilet:1"),
        ],
    }
    path.write_text(json.dumps(summary), encoding="utf-8")
    return path


def _row(
    *,
    category: str,
    valid: bool,
    precision: float,
    group_id: str,
) -> dict[str, object]:
    return {
        "group_id": group_id,
        "category": category,
        "policy": "memory_guided",
        "query_repeat_index": 0,
        "memory_decision": "frontier_first",
        "memory_action_count": 10,
        "fallback_action_count": 30,
        "fallback_from_memory_action_count": 50,
        "memory_valid_prior": 0.5,
        "memory_evidence": {
            "shared_gate_success": valid,
            "detector_precision": precision,
            "detector_pixels": 100 if precision > 0.0 else 0,
            "overlap_pixels": 100 if valid else 0,
            "oracle_recall": precision,
        },
        "memory_reliability": {
            "components": {
                "base_prior": 0.5,
                "current_evidence": precision,
                "matching": 1.0,
                "recency": 1.0,
                "transform_covariance": 1.0,
            }
        },
    }
