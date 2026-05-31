# Official Local Action-Effect Scorer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train and persist an initial learned scorer that predicts next-step target visibility for candidate official ObjectNav actions.

**Architecture:** Add a pure-Python logistic model module over exported local action-effect datasets, plus a CLI wrapper. The module owns feature extraction, preprocessing, training, prediction, and candidate-action scoring; policy integration remains a later slice.

**Tech Stack:** Python standard library, existing objectnav_core CLI/test patterns, pytest.

---

## Chunk 1: Model API

### Task 1: Training and Prediction

**Files:**
- Create: `src/objectnav_core/tests/test_habitat_official_local_action_model.py`
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py`

- [ ] **Step 1: Write failing training/prediction test**

Create a synthetic dataset with matched local evidence where `move_forward`
examples are labeled target-visible after action and `turn_right` examples are
not. Assert that the trained model scores `move_forward` higher than
`turn_right` for the same candidate state.

- [ ] **Step 2: Run test to verify RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_local_action_model.py -q
```

Expected: module import failure.

- [ ] **Step 3: Implement minimal model module**

Add deterministic logistic training, feature extraction, persisted
preprocessing stats, prediction, and candidate-action scoring.

- [ ] **Step 4: Run test to verify GREEN**

Run the same pytest command. Expected: pass.

## Chunk 2: CLI and Packaging

### Task 2: CLI

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_model.py`
- Create: `src/objectnav_core/objectnav_core/cli/train_habitat_official_local_action_model.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`

- [ ] **Step 1: Write failing CLI test**

Assert that the CLI writes `model.json` with task name, feature names, dataset
counts, metrics, and preprocessing stats.

- [ ] **Step 2: Run tests to verify RED**

Expected: CLI import failure.

- [ ] **Step 3: Implement CLI and console script**

Add parser options for output, feature selection, epochs, learning rate, and L2.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run model tests plus packaging test.

## Chunk 3: Artifact and Documentation

### Task 3: Smoke Train and Trail

**Files:**
- Create: `docs/experiments/2026-05-30-official-local-action-effect-scorer-yolo-smoke.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Run verification**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_ros_packaging.py -q
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py src/objectnav_core/objectnav_core/cli/train_habitat_official_local_action_model.py
git diff --check
```

- [ ] **Step 2: Train on current YOLO action-effect dataset**

Write `model.json` under a run directory and record the metrics. Treat this as
diagnostic only because the four-episode trace is sparse.

- [ ] **Step 3: Update docs**

Record changed files, verification, model metrics, limitations, and the next
step: integrate candidate scorer as a new official policy variant after larger
trace collection.
