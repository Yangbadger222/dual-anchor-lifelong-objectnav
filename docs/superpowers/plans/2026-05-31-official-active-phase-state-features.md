# Official Active-Phase State Features Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add numeric active-viewpoint phase features to candidate-rollout state features.

**Architecture:** Extend the existing `STATE_FEATURE_FIELDS` and `_predecision_state_features` path. Reuse the exporter’s active-phase ranking helper so sampling and feature extraction agree.

**Tech Stack:** Python, pytest, existing ObjectNav rollout exporter and CSV writers.

---

### Task 1: Rollout State Feature Schema

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write the failing test**

Extend the predecision state-feature test to assert active-frontier phase rank,
one-hot flags, `at_viewpoint`, scan steps, and CSV headers. Extend the
phase-sampling test to assert orient/at-viewpoint features on an orient state.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_records_predecision_state_features src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_sample_active_viewpoint_phases_across_episodes -q
```

Expected: FAIL with missing phase feature keys.

- [ ] **Step 3: Implement minimal feature extraction**

Add the new fields to `STATE_FEATURE_FIELDS`; derive rank and one-hot booleans
from `active_perception_phase`/decision; set `at_viewpoint` when orient/scan or
path distance is zero; preserve scan steps.

- [ ] **Step 4: Run focused tests**

Run the same pytest command and expect PASS.

### Task 2: Verification and Docs

**Files:**
- Modify: `docs/design/2026-05-31-official-active-phase-state-features.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Run local gates**

Run exporter tests, full objectnav core tests, `compileall`, `git diff --check`,
and touched-file whitespace scan.

- [ ] **Step 2: Sync and verify on Linux**

Sync touched files to `/home/badger/Desktop/dual-anchor-lifelong-objectnav` and
run the focused exporter tests inside `conda activate habitat`.

- [ ] **Step 3: Update docs**

Record exactly what changed, the verification evidence, and the next step:
collect more phase-diverse matrices before utility-model claims.
