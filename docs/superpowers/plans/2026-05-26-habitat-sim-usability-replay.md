# Habitat-Sim Usability Replay Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first Habitat-Sim replay layer that converts RGB-D/oracle scene observations into the existing usability-memory trace interface.

**Architecture:** Keep Habitat integration optional and isolated. Start with trace schema and evidence extraction tests that do not import Habitat, then add a thin Habitat adapter and CLI once the data shape is stable.

**Tech Stack:** Python, pytest, PyYAML, optional Habitat-Sim/Habitat-Lab in a separate environment.

---

### Task 1: Trace Schema

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_trace_schema.py`
- Create: `src/objectnav_core/tests/test_habitat_trace_schema.py`

- [ ] Write tests for required trace fields and CSV roundtrip.
- [ ] Implement dataclasses or typed dict helpers for Habitat trace rows.
- [ ] Verify tests pass without Habitat installed.

### Task 2: Evidence Extraction Without Habitat Import

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_evidence.py`
- Create: `src/objectnav_core/tests/test_habitat_evidence.py`

- [ ] Write tests for POSITIVE, FREE, OCCLUDED, NON_CONFIRMATION, UNKNOWN, and quarantined depth failure.
- [ ] Implement evidence extraction from scalar depth/visibility statistics.
- [ ] Verify tests pass.

### Task 3: Optional Habitat Adapter

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_replay.py`
- Create: `src/objectnav_core/tests/test_habitat_replay_import_boundary.py`

- [ ] Ensure importing `objectnav_core` does not import Habitat.
- [ ] Implement adapter imports inside runtime functions only.
- [ ] Add a clear error message when Habitat is missing.

### Task 4: CLI And Config

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/run_habitat_usability_replay.py`
- Create: `configs/habitat/usability_smoke.yaml`
- Modify: `src/objectnav_core/setup.py`
- Modify: `README.md`

- [ ] Add CLI flags from the design doc.
- [ ] Write a smoke config template without dataset secrets.
- [ ] Add packaging tests for the console script.

### Task 5: Smoke Run And Report

**Files:**
- Create: `docs/experiments/YYYY-MM-DD-habitat-usability-smoke.md`
- Create or update: `docs/handoff/YYYY-MM-DD-habitat-sim-usability-replay.md`

- [ ] Run 20 episodes on one scene.
- [ ] Save summary under ignored `runs/habitat_usability/smoke`.
- [ ] Record evidence counts, decision counts, UNKNOWN ratio, and failure notes.

