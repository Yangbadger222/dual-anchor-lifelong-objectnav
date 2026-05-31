# Official Phase-Diverse Rollout Export Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `active_phase_path` candidate-state sampling mode and a per-category-per-episode state cap to the official candidate-rollout exporter.

**Architecture:** Keep the change in the exporter selection layer. The sampler reads policy-trace memory/debug fields, orders candidate-bearing states before existing caps, and leaves Habitat replay plus rollout labels unchanged.

**Tech Stack:** Python, argparse, pytest, existing ObjectNav exporter helpers.

---

### Task 1: API Sampling Behavior

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write the failing test**

Add a test that creates candidate states across multiple episodes with mixed
active phases, path distances, and scores. Export with
`state_sampling="active_phase_path"`, `max_states_per_category=4`,
`max_states_per_category_episode=1`, and one branch action. Assert selected
states prioritize at-viewpoint orient/scan phases and do not take two states
from the same category/episode.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_sample_active_viewpoint_phases_across_episodes -q
```

Expected: FAIL because `active_phase_path` and
`max_states_per_category_episode` do not exist yet.

- [ ] **Step 3: Implement minimal API support**

Add `active_phase_path` to `STATE_SAMPLING_MODES`, add
`max_states_per_category_episode`, implement the sort key and cap in
`_candidate_states`, and record
`candidate_state_limit_per_category_episode` in dataset metadata.

- [ ] **Step 4: Run focused test to verify it passes**

Run the same pytest command and expect PASS.

### Task 2: CLI Flag

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Extend the CLI test**

Pass `--state-sampling active_phase_path` and
`--max-states-per-category-episode 1`; assert the runner receives both values.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_cli_writes_json_and_csv -q
```

Expected: FAIL because the parser does not know
`--max-states-per-category-episode` yet.

- [ ] **Step 3: Implement minimal CLI support**

Add the parser flag and pass the value to the exporter.

- [ ] **Step 4: Run focused test to verify it passes**

Run the same pytest command and expect PASS.

### Task 3: Probe and Documentation

**Files:**
- Create: `docs/experiments/2026-05-31-official-phase-diverse-hard-state-probe.md`
- Modify: `docs/design/2026-05-31-official-phase-diverse-rollout-export.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Run local verification**

Run focused tests, full objectnav core tests, `compileall`, `git diff --check`,
and touched-file trailing-whitespace scan.

- [ ] **Step 2: Run Linux bounded probe**

Sync changed files to the Linux mirror and run a bounded repeat-first
action-matrix export/report/mine sequence using
`--state-sampling active_phase_path`, `--max-states-per-category 8`, and
`--max-states-per-category-episode 2`.

- [ ] **Step 3: Update docs**

Record whether phase/path-diverse sampling recovers `chair` or `bed`, and keep
the conclusion framed as a diagnostic rather than a policy claim.
