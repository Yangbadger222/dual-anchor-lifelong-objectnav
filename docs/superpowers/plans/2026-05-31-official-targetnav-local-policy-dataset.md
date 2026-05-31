# Official TargetNav Local Policy Dataset Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export official-contract Habitat ObjectNav observations paired with oracle shortest-path TargetNav actions for later local policy training.

**Architecture:** Add a focused dataset module that builds/resets the official ObjectNav environment, selects episode goal/viewpoint positions, converts them to the existing internal TargetNav pointgoal convention, queries a shortest-path follower, and writes JSON/CSV examples with explicit oracle-teacher provenance. Add a thin CLI and package entry point while using fake environments for local tests.

**Tech Stack:** Python, pytest, NumPy, Habitat ObjectNav evaluator helpers, CSV/JSON artifacts.

---

## Chunk 1: Dataset Exporter

### Task 1: RED Schema And Teacher Rollout Test

**Files:**
- Create: `src/objectnav_core/tests/test_habitat_official_targetnav_local_policy_dataset.py`
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_targetnav_local_policy_dataset.py`

- [ ] Write a failing test that exports one fake episode with depth/GPS/compass, one goal viewpoint, and fake follower actions.
- [ ] Assert the dataset task, schema version, official config fields, oracle provenance, pointgoal `[distance, -relative_bearing]`, depth stats, teacher action names, and action distribution.
- [ ] Run the focused test and confirm it fails because the module is missing.
- [ ] Implement minimal exporter dataclasses/helpers and JSON-like return payload.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: RED Edge Cases And CSV Test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_targetnav_local_policy_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_targetnav_local_policy_dataset.py`

- [ ] Add failing tests for missing goals and unavailable shortest-path follower being counted instead of crashing.
- [ ] Add a failing test for stable CSV output containing flattened pointgoal, action, and depth-stat fields.
- [ ] Run the focused tests and confirm the expected failures.
- [ ] Implement skipped counters and CSV writer.
- [ ] Re-run focused tests and confirm pass.

## Chunk 2: CLI And Packaging

### Task 3: RED CLI Test

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_targetnav_local_policy_dataset.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_targetnav_local_policy_dataset.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`

- [ ] Add a failing CLI test using an injected runner and `--output` / `--csv-output`.
- [ ] Add a failing module `--help` test.
- [ ] Add a failing packaging assertion for `objectnav_habitat_official_targetnav_local_policy_dataset`.
- [ ] Implement CLI parser, JSON/CSV writes, console summary, main guard, and entry point.
- [ ] Re-run focused CLI/packaging tests and confirm pass.

## Chunk 3: Verification And Research Trail

### Task 4: Verification

**Files:**
- All touched Python files.

- [ ] Run focused pytest for the new dataset tests and packaging test.
- [ ] Run `python -m compileall` on touched package files.
- [ ] Run CLI `--help`.
- [ ] Run `git diff --check`.

### Task 5: Docs

**Files:**
- Modify: `docs/design/2026-05-31-official-targetnav-local-policy-dataset.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] Update design status/notes if implementation changes the schema.
- [ ] Add a devlog entry with files changed, reason, verification, and future impact.
- [ ] Update handoff with current state, commands run, remaining Linux Habitat smoke export, and risks.
