# Design Doc: Phase 1A Report Generator

Date: 2026-05-24  
Owner: Codex  
Status: Implemented

## Goal

Turn the Phase 1A HTML report into a repeatable generator instead of a one-off static file.

The generator should read the Phase 1A artifact directory and write `report.html` with trial metrics, event summaries, memory states, relocation evidence, and frontier policy score terms.

## Non-Goals

- This design does not add ROS 2, Nav2, TF, detector, VLM, or robot adapter code.
- This design does not run experiments itself.
- This design does not create paper-ready plots or statistical comparisons.
- This design does not require a web server or frontend framework.

## Background

Phase 1A already writes deterministic artifacts:

- `memory.sqlite`
- `summary.json`
- `memory_snapshot.json`
- `events.jsonl`

A manually-created `report.html` exists under `runs/phase1a/latest`, but it can drift from the current schema and trial outputs. Recent work added persisted `trial_metrics` and frontier policy score terms, so the report should be generated from artifacts every time.

## System Boundary

Owned by this generator:

- reading Phase 1A JSON, JSONL, and SQLite artifacts
- rendering a static Chinese HTML report
- validating that internal report navigation anchors resolve
- writing `report.html` into the artifact directory

Outside this generator:

- trial execution
- memory mutation logic
- policy selection logic
- ROS 2 or real-robot visualization

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Summary | `summary.json` | Main run list, artifact manifest, scene and anchor metadata. |
| Input | Memory snapshot | `memory_snapshot.json` | Object states and relocation relations. |
| Input | Events | `events.jsonl` | Frontier score terms, object observations, verification, memory mutations. |
| Input | Trial metrics | `memory.sqlite` table `trial_metrics` | Used to confirm persisted metrics are present. |
| Output | Report | `report.html` | Static local HTML file. |

## Interfaces

Python API:

- `generate_phase1a_report(artifact_dir: str | Path) -> Path`

CLI:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.generate_phase1a_report --input runs/phase1a/latest
```

`run_phase1a(output_dir)` should call the generator after writing JSON, JSONL, and SQLite artifacts, then include `"report": "report.html"` in `summary["artifact_files"]`.

## Data Flow

1. The trial runner writes SQLite, summary, memory snapshot, and events.
2. The report generator reads the artifact files.
3. It loads persisted `trial_metrics` from SQLite for a consistency summary.
4. It groups events by `trial_id`.
5. It renders:
   - overview metrics
   - trial result table
   - path length bars
   - frontier score-term table
   - memory object and relation table
   - artifact manifest
   - limitations and next steps
6. It writes `report.html`.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Missing artifact file | `Path.exists()` check before rendering | Raise `FileNotFoundError` with the missing path. |
| Broken JSON or JSONL | JSON parser exception | Fail fast so the artifact can be regenerated. |
| Missing SQLite metrics | Empty or missing `trial_metrics` query | Render `0` persisted metrics and keep report generation deterministic. |
| Broken internal navigation | HTML parser verification in tests | Fix ids or links before claiming completion. |
| Report mistaken for real-robot result | Visible caveat in title and limits section | Keep deterministic/ROS-free wording in the generated HTML. |

## Verification Plan

- Add a failing test that `run_phase1a()` writes `report.html` and adds it to `artifact_files`.
- Verify the report contains all four trial ids, object memory states, relocation relation, and frontier score terms.
- Parse generated HTML and verify all internal navigation anchors resolve.
- Run full pytest, compileall, Phase 1A CLI, direct SQLite metrics query, and core-only ROS-coupling scan.

## Research Relevance

Generated reports make future baseline and ablation artifacts reproducible. They also reduce the chance that a visual result used in paper planning drifts from the actual JSON, JSONL, and SQLite evidence.

## Open Questions

- Should future report generation compare multiple policy runs side by side?
- Should the report include a small map/path diagram once path traces are persisted?
- Should the CLI expose report language or template variants?
