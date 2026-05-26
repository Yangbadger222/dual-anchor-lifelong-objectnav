import csv
import json
from pathlib import Path

from objectnav_core.evaluation.usability_stress import run_usability_stress


def test_usability_stress_runner_writes_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "usability_stress"

    summary = run_usability_stress(
        output_dir,
        seed=13,
        monte_carlo_runs=80,
    )

    assert summary["artifact_files"] == {
        "summary": "summary.json",
        "decision_boundary": "decision_boundary.csv",
        "report": "stress_report.html",
    }
    assert summary["scenarios"]["ghost_retirement"]["retired"] is True
    assert summary["scenarios"]["ghost_retirement"]["final_belief"]["p_usable"] < 0.2
    assert summary["scenarios"]["false_deletion_guard"]["final_belief"]["p_existence"] > 0.8
    assert summary["scenarios"]["ood_quarantine"]["final_belief"] == {
        "p_existence": 0.9,
        "p_location_valid": 0.9,
        "p_usable": 0.9,
    }
    assert sum(summary["decision_sweep"]["decision_counts"].values()) == 80

    summary_path = output_dir / "summary.json"
    boundary_path = output_dir / "decision_boundary.csv"
    report_path = output_dir / "stress_report.html"

    assert summary_path.exists()
    assert boundary_path.exists()
    assert report_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8")) == summary

    rows = list(csv.DictReader(boundary_path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) == 80
    assert {
        "p_existence",
        "p_location_valid",
        "p_usable",
        "p_valid",
        "d_nav",
        "d_verify",
        "c_search",
        "decision",
    }.issubset(rows[0])

    report_html = report_path.read_text(encoding="utf-8")
    assert "Usability Memory Stress Report" in report_html
    assert "ghost_retirement" in report_html
    assert "false_deletion_guard" in report_html
    assert "ood_quarantine" in report_html
