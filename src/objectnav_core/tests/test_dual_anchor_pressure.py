from __future__ import annotations

from objectnav_core.evaluation.dual_anchor_pressure import (
    DualAnchorPressureCase,
    run_dual_anchor_matching_pressure_report,
    run_dual_anchor_matching_pressure,
)


def test_pressure_run_reports_accept_reject_and_ambiguity_counts() -> None:
    cases = (
        DualAnchorPressureCase(
            name="clear_match",
            observed_xy=(0.2, 0.0),
            candidate_xy={"target": (0.0, 0.0), "distractor": (3.0, 0.0)},
            covariance_scale=0.2,
        ),
        DualAnchorPressureCase(
            name="ambiguous_match",
            observed_xy=(1.0, 0.0),
            candidate_xy={"left": (0.9, 0.0), "right": (1.1, 0.0)},
            covariance_scale=0.2,
        ),
        DualAnchorPressureCase(
            name="outside_gate",
            observed_xy=(5.0, 0.0),
            candidate_xy={"target": (0.0, 0.0)},
            covariance_scale=0.1,
        ),
    )

    summary = run_dual_anchor_matching_pressure(
        cases=cases,
        gate_threshold=5.991,
        ambiguity_margin=0.5,
    )

    assert summary["case_count"] == 3
    assert summary["accepted_count"] == 1
    assert summary["ambiguous_count"] == 1
    assert summary["outside_gate_count"] == 1
    assert summary["rows"][0]["accepted"] is True
    assert summary["rows"][1]["reason"] == "ambiguous"
    assert summary["rows"][2]["reason"] == "outside_gate"


def test_pressure_report_writes_summary_artifact(tmp_path) -> None:
    summary = run_dual_anchor_matching_pressure_report(
        tmp_path,
        cases=(
            DualAnchorPressureCase(
                name="clear_match",
                observed_xy=(0.2, 0.0),
                candidate_xy={"target": (0.0, 0.0), "distractor": (3.0, 0.0)},
                covariance_scale=0.2,
            ),
        ),
        gate_threshold=5.991,
        ambiguity_margin=0.5,
    )

    assert summary["task"] == "dual_anchor_matching_pressure"
    assert summary["artifact_files"]["summary"] == "summary.json"
    assert (tmp_path / "summary.json").exists()
