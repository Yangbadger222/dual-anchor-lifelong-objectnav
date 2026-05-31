# Official Score-Aware Rollout Export Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a diagnostic `top_score_desc` candidate-state sampling mode to the official candidate-rollout exporter.

**Architecture:** Keep all behavior localized to the exporter selection layer. Expose a small enum through the Python API and CLI, record the mode in dataset metadata, and leave Habitat replay and label generation unchanged.

**Tech Stack:** Python, argparse, pytest, existing ObjectNav evaluation helpers.

---

### Task 1: Score-Aware Selection API

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write the failing test**

Add a test that creates interleaved `chair` and `bed` candidate states with
different `top_candidates[0].score` values, runs
`export_official_candidate_rollout_dataset(..., state_sampling="top_score_desc",
max_states_per_category=2, branch_actions=("turn_left",))`, and asserts the
selected rollout `step_index` order follows descending score before category
capping.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_sample_states_by_top_candidate_score -q
```

Expected: FAIL because `state_sampling` is not accepted yet.

- [ ] **Step 3: Write minimal implementation**

Add `STATE_SAMPLING_MODES = ("trace_order", "top_score_desc")`, normalize the
API parameter, sort candidate-bearing states by descending top score when
requested, and record `candidate_state_sampling` in the dataset.

- [ ] **Step 4: Run focused test to verify it passes**

Run the same pytest command and expect PASS.

### Task 2: CLI Flag

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write the failing CLI assertion**

Extend the CLI test to pass `--state-sampling top_score_desc` and assert the
runner receives `state_sampling == "top_score_desc"`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_cli_writes_json_and_csv -q
```

Expected: FAIL because the parser does not accept `--state-sampling`.

- [ ] **Step 3: Write minimal CLI implementation**

Add the parser flag with choices from `STATE_SAMPLING_MODES` and pass it to the
exporter.

- [ ] **Step 4: Run focused test to verify it passes**

Run the same pytest command and expect PASS.

### Task 3: Documentation and Verification

**Files:**
- Modify: `docs/design/2026-05-31-official-score-aware-rollout-export.md`
- Modify: `docs/devlog/2026-05.md`
- Create or modify: `docs/experiments/2026-05-31-official-score-aware-hard-state-probe.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Run local verification**

Run focused tests, full objectnav core tests, `compileall`, and `git diff --check`.

- [ ] **Step 2: Run Linux bounded probe**

Sync changed files to `/home/badger/Desktop/dual-anchor-lifelong-objectnav`, run a
bounded `top_score_desc` repeat-first action-matrix export/report/mine sequence,
and record commands plus metrics.

- [ ] **Step 3: Update docs**

Record what changed, verification evidence, and whether `chair`/`bed` recovery
improved. Keep the result framed as a diagnostic, not an online policy claim.
