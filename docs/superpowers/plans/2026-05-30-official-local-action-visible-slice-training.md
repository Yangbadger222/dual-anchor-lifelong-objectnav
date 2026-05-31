# Official Local Action Visible-Slice Training Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in current-visible-only training filter to the official local action model.

**Architecture:** Filter parsed dataset examples before label extraction/preprocessing, record source/training counts in the model artifact, and expose the option through the training CLI.

**Tech Stack:** Python stdlib, existing logistic scorer, argparse, pytest.

---

## Chunk 1: Visible-Only Trainer Filter

### Task 1: RED API filter test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_model.py`

- [ ] **Step 1: Write failing test**

Create mixed visible/absent examples and train with
`current_visible_only=True`. Assert `example_count` and positive/negative
counts come only from visible rows, and artifact metadata records the source
example count.

- [ ] **Step 2: Run RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest -q \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py::test_official_local_action_model_trains_current_visible_slice
```

Expected: fail because the trainer does not accept `current_visible_only`.

### Task 2: GREEN trainer filter

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py`

- [ ] **Step 1: Add filter parameter and helper**

Filter examples on `features.current_target_visible` when requested.

- [ ] **Step 2: Record artifact metadata**

Record source count, trained count, and filter setting under `dataset`.

- [ ] **Step 3: Run RED test**

Expected: pass.

## Chunk 2: CLI Filter

### Task 3: RED CLI filter test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_model.py`

- [ ] **Step 1: Add CLI test**

Pass `--current-visible-only` and assert output artifact counts.

- [ ] **Step 2: Run RED**

Expected: fail because CLI does not accept the flag.

### Task 4: GREEN CLI parser plumbing

**Files:**
- Modify: `src/objectnav_core/objectnav_core/cli/train_habitat_official_local_action_model.py`

- [ ] **Step 1: Add flag and pass through to trainer**

- [ ] **Step 2: Run model tests and focused official gate**
