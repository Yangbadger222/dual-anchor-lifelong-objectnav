# Phase 1A ObjectNav Core Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build the first ROS-free Phase 1A indoor water-dispenser ObjectNav vertical slice.

**Architecture:** Implement a pure Python `objectnav_core` package with validated scene models, deterministic corridor mapping, frontier/viewpoint planning, fake observations, SQLite memory, a discrete navigator, and trial runners. Keep ROS, Nav2, RTK, detector, and VLM integration out of this phase.

**Tech Stack:** Python 3.13, Pydantic v2, PyYAML, NumPy, SQLite, pytest.

---

## Chunk 1: Project Skeleton And Core Models

### Task 1: Package Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/objectnav_core/objectnav_core/__init__.py`
- Create: `src/objectnav_core/objectnav_core/models/__init__.py`
- Test: `src/objectnav_core/tests/test_models.py`

- [x] Write tests proving scene configs validate anchor, map, target object, and fake detector settings.
- [x] Run `PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_models.py -v` and confirm failure before implementation.
- [x] Implement Pydantic models for pose, anchor, scene config, object config, map config, reveal config, fake detector config, memory state, navigation status, and trial metrics.
- [x] Re-run the model tests and confirm pass.

## Chunk 2: Mapping And Planning

### Task 2: Deterministic Corridor Grid

**Files:**
- Create: `src/objectnav_core/objectnav_core/mapping/grid.py`
- Create: `src/objectnav_core/objectnav_core/mapping/fixtures.py`
- Create: `src/objectnav_core/objectnav_core/mapping/frontiers.py`
- Create: `src/objectnav_core/objectnav_core/planning/viewpoints.py`
- Test: `src/objectnav_core/tests/test_mapping.py`

- [x] Write tests for the `straight_corridor_one_water_dispenser_unknown` fixture.
- [x] Verify tests fail before implementation.
- [x] Implement grid metadata, known-free start area, boundary walls, forward-sector reveal, frontier extraction, and known-side frontier viewpoints.
- [x] Re-run mapping tests and confirm pass.

## Chunk 3: Fake Perception And Navigation

### Task 3: Fake Observation Source And Discrete Navigator

**Files:**
- Create: `src/objectnav_core/objectnav_core/simulation/observations.py`
- Create: `src/objectnav_core/objectnav_core/simulation/navigation.py`
- Create: `src/objectnav_core/objectnav_core/planning/scoring.py`
- Test: `src/objectnav_core/tests/test_simulation.py`

- [x] Write tests proving the fake detector only emits `water_dispenser` inside range, camera FOV, and line of sight.
- [x] Write tests proving the discrete navigator reaches a goal and records path length.
- [x] Verify tests fail before implementation.
- [x] Implement observation geometry, line-of-sight checks, simple frontier scoring, and deterministic navigation.
- [x] Re-run simulation tests and confirm pass.

## Chunk 4: Memory, Verification, And Trial Runner

### Task 4: SQLite Memory And Deterministic Runs

**Files:**
- Create: `src/objectnav_core/objectnav_core/memory/sqlite_store.py`
- Create: `src/objectnav_core/objectnav_core/evaluation/logger.py`
- Create: `src/objectnav_core/objectnav_core/simulation/trials.py`
- Test: `src/objectnav_core/tests/test_trials.py`

- [x] Write tests for the SQLite schema, reusable object query, state transitions, and relocation relation.
- [x] Write tests for four runs: `discover_and_verify`, `reuse_same_start`, `reuse_different_start`, and `missing_and_relocation`.
- [x] Verify tests fail before implementation.
- [x] Implement SQLite tables/indexes, JSON snapshots, event logging, verification viewpoint behavior, two-check missing behavior, and trial metrics.
- [x] Re-run trial tests and confirm pass.

## Chunk 5: Documentation And Verification

### Task 5: Repo Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/devlog/2026-05.md`
- Create or modify: `docs/handoff/2026-05-24-phase1a-objectnav-core.md`

- [x] Add a quick-start command for running the Phase 1A unit tests.
- [x] Record files changed, reason, verification, and remaining risks in the devlog.
- [x] Add a handoff note with commands run and next recommended actions.
- [x] Run `PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests -v`.
- [x] Run placeholder and ROS-coupling scans.

## Chunk 6: Phase 1A Artifact Runner

### Task 6: CLI Runner And Artifact Contract

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/__init__.py`
- Create: `src/objectnav_core/objectnav_core/cli/run_phase1a.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `README.md`
- Modify: `docs/design/2026-05-24-system-architecture.md`
- Test: `src/objectnav_core/tests/test_cli_runner.py`
- Test: `src/objectnav_core/tests/test_ros_packaging.py`

- [x] Write a failing test proving the runner writes `memory.sqlite`, `summary.json`, `memory_snapshot.json`, and `events.jsonl`.
- [x] Implement `run_phase1a(output_dir)` and `python -m objectnav_core.cli.run_phase1a --output ...`.
- [x] Add the `objectnav_phase1a` console script for future ROS 2 `ament_python` installs.
- [x] Update README and architecture docs with the artifact contract.
- [x] Run targeted CLI and packaging tests.
- [x] Run the CLI manually into `runs/phase1a/latest`.
- [x] Run full pytest, compile, and ROS-coupling scans.
