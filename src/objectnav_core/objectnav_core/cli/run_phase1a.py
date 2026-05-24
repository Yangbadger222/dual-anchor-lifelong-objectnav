from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from objectnav_core.evaluation.report import generate_phase1a_report
from objectnav_core.models import TrialEvent, make_default_corridor_scene
from objectnav_core.simulation.trials import Phase1ATrialRunner


PHASE1A_TRIALS = [
    "discover_and_verify",
    "reuse_same_start",
    "reuse_different_start",
    "missing_and_relocation",
]


def run_phase1a(output_dir: str | Path) -> dict[str, Any]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    memory_path = output_path / "memory.sqlite"
    if memory_path.exists():
        memory_path.unlink()

    scene = make_default_corridor_scene()
    runner = Phase1ATrialRunner(memory_path=memory_path, scene=scene)

    results = [runner.run(trial_name) for trial_name in PHASE1A_TRIALS]
    events = [event for result in results for event in result.events]

    memory_snapshot = json.loads(runner.memory.export_json())
    summary: dict[str, Any] = {
        "scene_id": scene.scene_id,
        "target_class": scene.objects[0].class_name,
        "anchor": scene.anchor.model_dump(mode="json"),
        "runs": [
            {
                "trial_id": result.trial_id,
                "metrics": result.metrics.model_dump(mode="json"),
                "event_count": len(result.events),
            }
            for result in results
        ],
        "artifact_files": {
            "memory": "memory.sqlite",
            "summary": "summary.json",
            "memory_snapshot": "memory_snapshot.json",
            "events": "events.jsonl",
            "report": "report.html",
        },
    }

    _write_json(output_path / "summary.json", summary)
    _write_json(output_path / "memory_snapshot.json", memory_snapshot)
    _write_events(output_path / "events.jsonl", events)
    generate_phase1a_report(output_path)
    return summary


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_events(path: Path, events: list[TrialEvent]) -> None:
    lines = [json.dumps(event.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) for event in events]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Phase 1A ObjectNav trials.")
    parser.add_argument(
        "--output",
        required=True,
        help="Directory where memory.sqlite, summary.json, memory_snapshot.json, events.jsonl, and report.html will be written.",
    )
    args = parser.parse_args(argv)
    summary = run_phase1a(args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
