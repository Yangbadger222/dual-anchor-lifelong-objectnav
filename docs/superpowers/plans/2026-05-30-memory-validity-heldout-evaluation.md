# Memory-Validity Held-Out Evaluation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add metadata holdout splits and held-out metrics for the offline memory-validity logistic baseline.

**Architecture:** Keep the split/evaluation logic in `objectnav_core.evaluation.habitat_memory_validity_model` beside training, prediction, and scoring. Extend the trainer CLI with optional holdout flags that train only on non-holdout examples and append split/evaluation metadata to the JSON model report.

**Tech Stack:** Python standard library, existing pytest suite, existing `objectnav_core` CLI/module layout.

---

## Chunk 1: Split and Evaluation API

### Task 1: Metadata Split Helper

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_model.py`

- [ ] **Step 1: Write failing split test**

Add a test that calls `split_memory_validity_dataset(dataset, holdout_field="category", holdout_values=("toilet",))` and asserts train/holdout counts and preserved examples.

- [ ] **Step 2: Run focused test and verify RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_memory_validity_model.py -q
```

Expected: fail because `split_memory_validity_dataset` does not exist.

- [ ] **Step 3: Implement split helper**

Return a dict with `train`, `holdout`, and `split` metadata. Raise `ValueError` if either split is empty.

### Task 2: Evaluation Metrics Helper

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_model.py`

- [ ] **Step 1: Write failing evaluator test**

Add a test that evaluates a deterministic model on a synthetic holdout set and asserts example count, label counts, accuracy, log loss, and Brier score.

- [ ] **Step 2: Implement evaluator**

Implement `evaluate_memory_validity_model(dataset, model)` using `predict_memory_validity` and existing metric arithmetic.

## Chunk 2: CLI Integration

### Task 3: Trainer CLI Holdout Flags

**Files:**
- Modify: `src/objectnav_core/objectnav_core/cli/train_habitat_memory_validity_model.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_model.py`

- [ ] **Step 1: Write failing CLI test**

Extend the CLI test to pass `--holdout-field category --holdout-values toilet` and assert the model report includes `split`, `evaluation.train`, and `evaluation.holdout`.

- [ ] **Step 2: Implement CLI flags**

Add `--holdout-field` and `--holdout-values`. When present, split the dataset, train on train only, and add evaluation metrics for train and holdout.

## Chunk 3: Documentation and Verification

### Task 4: Research Trace

**Files:**
- Modify: `docs/design/2026-05-30-memory-validity-heldout-evaluation.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Mark design implemented locally**

Record that real held-out evaluation still depends on Linux artifact export.

- [ ] **Step 2: Add devlog entry**

Record files changed, reason, verification, and remaining risk.

- [ ] **Step 3: Update handoff**

Document the CLI flags and recommended first Linux split.

### Task 5: Verification

- [ ] **Step 1: Focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_memory_validity_model.py src/objectnav_core/tests/test_habitat_memory_validity_dataset.py -q
```

- [ ] **Step 2: Compile touched modules**

```bash
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py src/objectnav_core/objectnav_core/cli/train_habitat_memory_validity_model.py
```

- [ ] **Step 3: Full local suite**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
```

- [ ] **Step 4: Whitespace check**

```bash
git diff --check
```
