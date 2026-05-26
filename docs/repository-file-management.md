# Repository File Management

Date: 2026-05-26  
Owner: Codex  
Status: Active

This repository is a research workspace, so files should make the project easier to resume, not just easier to run once.

## Canonical Layout

| Path | Purpose | Commit? |
|---|---|---|
| `src/objectnav_core/` | ROS-free algorithm core, tests, CLIs, offline replay and reports | Yes |
| `src/objectnav_ros/` | ROS 2 adapter, Nav2 boundary, replay nodes, RViz configs | Yes |
| `docs/design/` | Architecture, algorithm, interface, and protocol designs | Yes |
| `docs/simulation/` | Simulator operation guides and simulation-specific protocols | Yes |
| `docs/experiments/` | Completed experiment reports with commands and metrics | Yes |
| `docs/handoff/` | Continuation notes for unfinished or risky work | Yes |
| `docs/devlog/` | Chronological development trail | Yes |
| `docs/templates/` | Required reusable documentation templates | Yes |
| `runs/` | Generated experiment outputs | Usually no |
| `runtime-data/`, `logs/`, `outputs/` | Robot/runtime/generated data | No |
| `datasets/`, `scene_datasets/`, `object_datasets/` | Habitat, ROS, or ML datasets | No |
| `third_party/`, `external/` | Local clones of Habitat or other upstream repos | No |

## Current Research Threads

| Thread | Main Docs | Main Code |
|---|---|---|
| Phase 1A deterministic ObjectNav | `docs/design/2026-05-24-system-architecture.md` | `src/objectnav_core/objectnav_core/simulation/` |
| Usability-centered memory | `docs/design/2026-05-26-usability-centered-lifelong-object-memory.md` | `src/objectnav_core/objectnav_core/memory/usability.py` |
| 2D grid trace stress test | `docs/design/2026-05-26-2d-grid-trace-generator.md` | `src/objectnav_core/objectnav_core/evaluation/grid_trace_experiment.py` |
| Localization-only bag audit | `docs/design/2026-05-26-localization-only-bag-audit.md` | `src/objectnav_core/objectnav_core/evaluation/localization_bag_audit.py` |
| Habitat-Sim next step | `docs/simulation/2026-05-26-habitat-sim-usability-memory.zh.html` | Not implemented yet |

## Artifact Policy

Commit small, reproducible summaries when they are part of the research record. Do not commit large generated files, raw bags, scene datasets, model weights, videos, or private credentials.

Good to commit:

- design docs
- experiment reports
- small JSON summaries when explicitly curated
- tests and deterministic fixtures
- config templates without secrets

Keep ignored:

- `runs/**` generated outputs except explicit curated exceptions
- Habitat scene datasets and object datasets
- ROS bag files, MCAP files, SQLite bag shards
- rendered videos and screenshots from long simulation sweeps
- local conda/venv/cache folders
- model weights and TensorRT engines

## Habitat File Placement

Use this shape when Habitat work starts:

```text
third_party/
  habitat-lab/          # local clone, ignored
  habitat-sim/          # local clone, ignored
datasets/
  habitat/
    scene_datasets/     # HM3D / Replica / MP3D, ignored
    object_datasets/    # YCB / ReplicaCAD objects, ignored
runs/
  habitat_usability/
    smoke/
    latest/
```

The algorithm repository should store only the adapter code, configs, and reports. Raw assets stay outside git.

## Cleanup Rule

Generated caches can be deleted at any time:

```bash
find . -name '.DS_Store' -delete
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
rm -rf .pytest_cache
```

