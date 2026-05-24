import json
from pathlib import Path

from objectnav_core.cli.run_phase1a import run_phase1a


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

    assert memory_db.exists()
    assert summary_path.exists()
    assert snapshot_path.exists()
    assert events_path.exists()

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
