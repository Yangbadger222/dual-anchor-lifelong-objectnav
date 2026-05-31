# Official Candidate-Viewpoint Restore Labels Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a candidate-viewpoint label exporter that restores official Habitat traces to memory-query states, evaluates top-K candidate viewpoints with a heading scan, and writes JSON/CSV labels.

**Architecture:** Extend `habitat_official_candidate_rollout_dataset.py` alongside the existing rollout and current-view state-restore exporters. Keep a separate schema and CLI so candidate-viewpoint scan labels cannot be mistaken for current-view or action-rollout labels.

**Tech Stack:** Python, pytest, existing official Habitat evaluation helpers, existing detector adapter CLI plumbing.

---

## Chunk 1: Dataset API and Tests

### Task 1: Candidate Pose Conversion

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`
- Test: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write the failing test**

Add a test that imports the candidate grid conversion helper and verifies the
default `81` cell grid with `0.25m` cells maps origin cell `[40, 40]` to
`x=0,z=0`, one column right to positive `x`, and one row up to positive `z`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_grid_cell_conversion_uses_episode_relative_xz -q
```

Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement minimal conversion helper**

Add a small helper that parses `viewpoint_cell` and returns episode-relative
`x_m,z_m` plus grid metadata.

- [ ] **Step 4: Run test to verify it passes**

Run the same focused pytest command. Expected: PASS.

### Task 2: Candidate Viewpoint Exporter

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`
- Test: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write failing exporter tests**

Add tests showing the exporter:

- replays the logged state once per selected state
- expands the top two candidates
- calls a fake env candidate restore hook with converted episode-relative poses
- reports current-view hidden, candidate-visible labels when any heading sees the target
- keeps invalid candidate restores as label-unavailable rows

- [ ] **Step 2: Run tests to verify they fail**

Run the new test names only. Expected: FAIL because the exporter does not
exist.

- [ ] **Step 3: Implement minimal exporter**

Add:

- schema constant
- CSV field list
- `export_official_candidate_viewpoint_restore_dataset`
- `_evaluate_candidate_viewpoint_restore`
- fake-env-first candidate pose restore hook
- heading-sweep evidence aggregation
- CSV writer

- [ ] **Step 4: Run focused tests to verify they pass**

Run the new focused tests. Expected: PASS.

## Chunk 2: CLI and Documentation

### Task 3: CLI Wrapper

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_viewpoint_restore_dataset.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`
- Test: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write failing CLI test**

Add a CLI test with injected runner that writes JSON/CSV and verifies key args:
`candidates_per_state`, `viewpoint_heading_count`, state sampling, and detector.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL because the CLI module is missing.

- [ ] **Step 3: Implement CLI and package entry point**

Reuse detector/category parser helpers from existing official exporter CLIs.

- [ ] **Step 4: Run CLI/packaging tests**

Expected: PASS.

### Task 4: Research Trail

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-31-official-candidate-viewpoint-restore-labels.md`
- Modify: `docs/design/2026-05-31-official-candidate-viewpoint-restore-labels.md`

- [ ] **Step 1: Update docs after implementation**

Record files changed, reason, verification commands, results, risks, and next
actions.

- [ ] **Step 2: Run documentation checks**

Run `git diff --check` and touched-file whitespace scan.

## Chunk 3: Verification and Linux Smoke

### Task 5: Local Verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

- [ ] **Step 2: Run full local suite**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
```

- [ ] **Step 3: Run compile/diff checks**

```bash
python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

### Task 6: Linux Targeted Verification and Smoke

**Files:**
- Sync touched files to `/home/badger/Desktop/dual-anchor-lifelong-objectnav`.

- [ ] **Step 1: Run targeted Linux tests**

Use conda env `habitat` and the focused candidate-rollout/packaging tests.

- [ ] **Step 2: Run bounded real Habitat/Yolo export**

Generate a candidate-viewpoint restore artifact from the 20-episode
phase/path trace with `active_phase_path`, category and per-episode caps, and
YOLO-World detector labels.

- [ ] **Step 3: Compare coverage**

Compare candidate-viewpoint visible/hidden counts against the existing
current-view state-restore artifact. Record whether labels are materially richer
before training any model.
