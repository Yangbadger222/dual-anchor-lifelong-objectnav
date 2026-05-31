# Official State-Restore Label Dataset Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a current-view state-restore label dataset for candidate-bearing official ObjectNav memory-query states.

**Architecture:** Extend the existing official candidate-rollout module with a separate state-restore exporter and CSV writer. Reuse candidate-state sampling, replay-to-policy-state, detector evidence, and predecision feature extraction so the label boundary is consistent with rollout artifacts but not confused with action-matrix labels.

**Tech Stack:** Python, pytest, Habitat fake-env tests, existing YOLO detector adapter interface.

---

## Chunk 1: State-Restore Export API

### Task 1: Add RED API test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify later: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write failing test**

Add `test_candidate_state_restore_dataset_labels_exact_replayed_state`.

The test should:
- import `export_official_candidate_state_restore_dataset`
- use `_write_policy_trace`
- use `_PixelDetector`
- pass an env factory that records actions
- assert one row is emitted for `max_states=1`
- assert replay actions are `["move_forward"]`
- assert no branch action is applied after replay
- assert labels are measured at the replayed observation

- [ ] **Step 2: Run RED test**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_labels_exact_replayed_state -q
```

Expected: fail because `export_official_candidate_state_restore_dataset` does
not exist.

- [ ] **Step 3: Implement minimal API**

Add:

```python
def export_official_candidate_state_restore_dataset(...): ...
```

Use existing helpers:
- `_load_object`
- `_policy_steps`
- `_candidate_states`
- `_make_habitat_env`
- `_replay_to_policy_state`
- `_predecision_state_features`
- `_detect_target_evidence`

- [ ] **Step 4: Run GREEN test**

Run the same focused test. Expected: pass.

## Chunk 2: CSV and CLI

### Task 2: Add CSV and CLI tests

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_state_restore_dataset.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`

- [ ] **Step 1: Write failing CSV test**

Add `test_candidate_state_restore_dataset_writes_csv`.

- [ ] **Step 2: Write failing CLI test**

Add `test_candidate_state_restore_dataset_cli_writes_json_and_csv`.

- [ ] **Step 3: Run RED tests**

Run the new tests and confirm failure on missing writer/CLI.

- [ ] **Step 4: Implement writer and CLI**

Use argparse style from `export_habitat_official_candidate_rollout_dataset.py`.
Expose detector and sampling flags.

- [ ] **Step 5: Register console script**

Add `export-habitat-official-candidate-state-restore-dataset` to setup entry
points and packaging test expectations.

## Chunk 3: Verification and Documentation

### Task 3: Verify and record evidence

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-31-official-state-restore-label-dataset.md`

- [ ] **Step 1: Run focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

- [ ] **Step 2: Run full tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q
```

- [ ] **Step 3: Run syntax and whitespace gates**

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

- [ ] **Step 4: Run Linux targeted tests**

```bash
ssh badger-linux 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_labels_exact_replayed_state \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_cli_writes_json_and_csv -q'
```

- [ ] **Step 5: Record result**

Document exact commands, pass/fail counts, artifact paths, and the limitation
that this is current-view state restore, not candidate-viewpoint teleport.
