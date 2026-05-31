# Official Local Action Configurable Label Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the official local action model train on selectable boolean labels from the v2 dataset.

**Architecture:** Add a `label_name` parameter to the existing deterministic trainer and a `--label` CLI flag. Preserve `next_target_visible` as the default and keep prediction/scoring artifact-compatible.

**Tech Stack:** Python stdlib, existing logistic scorer, argparse, pytest.

---

## Chunk 1: Trainer Label Selection

### Task 1: RED API label test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_model.py`

- [ ] **Step 1: Write failing test**

Add a synthetic dataset where `next_target_visible` and
`target_visible_at_horizon` disagree. Train with
`label_name="target_visible_at_horizon"` and assert the model artifact label
and positive count come from the requested label.

- [ ] **Step 2: Run RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest -q \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py::test_official_local_action_model_trains_requested_label
```

Expected: fail because the trainer does not accept `label_name`.

### Task 2: GREEN trainer plumbing

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py`

- [ ] **Step 1: Add `label_name` parameter**

Default to `LABEL_NAME`; pass it into `_label`.

- [ ] **Step 2: Run RED test**

Expected: pass.

## Chunk 2: CLI Label Selection

### Task 3: RED CLI flag test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_model.py`

- [ ] **Step 1: Extend CLI test**

Pass `--label target_visible_at_horizon` and assert the output artifact records
that label.

- [ ] **Step 2: Run RED**

Expected: fail because CLI does not accept `--label`.

### Task 4: GREEN CLI parser plumbing

**Files:**
- Modify: `src/objectnav_core/objectnav_core/cli/train_habitat_official_local_action_model.py`

- [ ] **Step 1: Add `--label` argument**

Pass it to `train_official_local_action_logistic_model`.

- [ ] **Step 2: Run model tests and focused gate**

Use the standard focused official gate.
