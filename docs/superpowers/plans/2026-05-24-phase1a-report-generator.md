# Phase 1A Report Generator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate `report.html` from Phase 1A artifacts every time the deterministic trial suite runs.

**Architecture:** Add `objectnav_core.evaluation.report` to load `summary.json`, `memory_snapshot.json`, `events.jsonl`, and SQLite `trial_metrics`, then render static HTML. Add a small CLI wrapper and call the generator from `run_phase1a` after writing the machine-readable artifacts.

**Tech Stack:** Python 3.13, stdlib `json`, `sqlite3`, `html`, `pathlib`, pytest, static HTML/CSS.

---

## Chunk 1: Report Generation Contract

### Task 1: Failing Artifact Test

**Files:**
- Modify: `src/objectnav_core/tests/test_cli_runner.py`
- Create: `src/objectnav_core/objectnav_core/evaluation/report.py`
- Create: `src/objectnav_core/objectnav_core/cli/generate_phase1a_report.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_phase1a.py`

- [x] Write a failing test proving `run_phase1a()` writes `report.html`, adds it to `artifact_files`, and renders trial ids, memory states, relocation relation, and frontier score terms.
- [x] Run `python3 -m pytest src/objectnav_core/tests/test_cli_runner.py -v` and confirm failure.
- [x] Implement `generate_phase1a_report(artifact_dir)`.
- [x] Add `objectnav_core.cli.generate_phase1a_report`.
- [x] Call the generator from `run_phase1a()` and add `"report": "report.html"` to the artifact manifest.
- [x] Re-run `python3 -m pytest src/objectnav_core/tests/test_cli_runner.py -v` and confirm pass.

## Chunk 2: Packaging And Docs

### Task 2: Console Script And Project Trail

**Files:**
- Modify: `src/objectnav_core/setup.py`
- Modify: `README.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-24-phase1a-objectnav-core.md`
- Create: `docs/design/2026-05-24-phase1a-report-generator.md`

- [x] Record the design boundary and verification plan.
- [x] Add an `objectnav_phase1a_report` console script.
- [x] Update README artifact list and report command.
- [x] Update devlog and handoff.
- [x] Run `python3 -m pytest src/objectnav_core/tests -v`.
- [x] Run `python3 -m compileall -q src/objectnav_core/objectnav_core`.
- [x] Run `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`.
- [x] Verify generated HTML anchors resolve.
- [x] Run a core-only ROS-coupling scan.
