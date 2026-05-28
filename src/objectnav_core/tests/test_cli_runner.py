import json
from html.parser import HTMLParser
from pathlib import Path

from objectnav_core.cli.run_phase1a import run_phase1a
from objectnav_core.cli.run_lifelong_objectnav_benchmark import main as lifelong_main


def test_phase1a_cli_runner_writes_experiment_artifacts(tmp_path: Path) -> None:
    output_dir = tmp_path / "phase1a"

    summary = run_phase1a(output_dir)

    assert summary["scene_id"] == "straight_corridor_one_water_dispenser_unknown"
    assert summary["target_class"] == "water_dispenser"
    assert summary["artifact_files"] == {
        "memory": "memory.sqlite",
        "summary": "summary.json",
        "memory_snapshot": "memory_snapshot.json",
        "events": "events.jsonl",
        "report": "report.html",
    }
    assert [run["trial_id"] for run in summary["runs"]] == [
        "discover_and_verify",
        "reuse_same_start",
        "reuse_different_start",
        "missing_and_relocation",
    ]
    assert all(run["metrics"]["success"] for run in summary["runs"])

    memory_db = output_dir / "memory.sqlite"
    summary_path = output_dir / "summary.json"
    snapshot_path = output_dir / "memory_snapshot.json"
    events_path = output_dir / "events.jsonl"
    report_path = output_dir / "report.html"

    assert memory_db.exists()
    assert summary_path.exists()
    assert snapshot_path.exists()
    assert events_path.exists()
    assert report_path.exists()

    saved_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert saved_summary == summary

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    object_states = {obj["object_id"]: obj["state"] for obj in snapshot["objects"]}
    assert object_states["water_dispenser_001"] == "missing"
    assert object_states["water_dispenser_002"] == "reusable"
    assert snapshot["relations"][0]["relation_type"] == "possible_relocation_of"

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {event["trial_id"] for event in events} >= {
        "discover_and_verify",
        "reuse_same_start",
        "reuse_different_start",
        "missing_and_relocation",
    }

    report_html = report_path.read_text(encoding="utf-8")
    for trial_id in (
        "discover_and_verify",
        "reuse_same_start",
        "reuse_different_start",
        "missing_and_relocation",
    ):
        assert trial_id in report_html
    assert "water_dispenser_001" in report_html
    assert "missing" in report_html
    assert "water_dispenser_002" in report_html
    assert "reusable" in report_html
    assert "possible_relocation_of" in report_html
    assert "frontier_selected" in report_html
    assert "path_cost_m" in report_html
    assert "final_candidate_score" in report_html

    parser = AnchorParser()
    parser.feed(report_html)
    missing_anchors = {
        href[1:]
        for href in parser.hrefs
        if href.startswith("#") and href[1:] not in parser.ids
    }
    assert missing_anchors == set()


def test_lifelong_objectnav_benchmark_cli_writes_summary_and_report(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "lifelong"

    assert lifelong_main(["--output", str(output_dir)]) == 0

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["task"] == "lifelong_objectnav_active_benchmark"
    assert summary["policy_summaries"]["memory_guided"]["aggregate"]["success_episodes"] == 3
    assert summary["comparison"]["memory_guided_path_reduction_ratio"] > 0.2
    assert (output_dir / "report.html").exists()
    assert (output_dir / "memory_guided" / "memory.sqlite").exists()
    assert (output_dir / "frontier_only" / "events.csv").exists()


class AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if "id" in attributes and attributes["id"] is not None:
            self.ids.add(attributes["id"])
        if tag == "a" and attributes.get("href"):
            href = attributes["href"]
            assert href is not None
            self.hrefs.append(href)
