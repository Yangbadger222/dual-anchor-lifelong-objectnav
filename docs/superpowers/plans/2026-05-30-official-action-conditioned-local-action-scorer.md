# Official Action-Conditioned Local Action Scorer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add action-state interaction features so the local action scorer can rank candidates differently in different temporal/evidence states.

**Architecture:** Extend the existing deterministic logistic feature builder. Keep the dataset unchanged; generate interaction feature values when requested feature names contain `__`.

**Tech Stack:** Python stdlib, existing logistic scorer, pytest.

---

## Chunk 1: Interaction Feature Support

### Task 1: RED candidate-ranking test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_model.py`

- [ ] **Step 1: Write failing test**

Add `test_official_local_action_model_scores_state_action_interactions`.
Create a manual model with feature names:

```python
[
    "action_move_forward",
    "action_turn_left__current_abs_center_offset_fraction",
    "action_move_forward__current_abs_center_offset_fraction",
]
```

Weights should make low offset prefer `move_forward` and high offset prefer
`turn_left`.

- [ ] **Step 2: Run RED**

```bash
PYTHONPATH=src/objectnav_core pytest -q \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py::test_official_local_action_model_scores_state_action_interactions
```

Expected: fail because interaction features are not generated.

### Task 2: GREEN feature builder

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py`

- [ ] **Step 1: Add interaction generation**

After base feature values are built, scan the requested feature names for
`__`. For each feature, compute product of left and right base values when both
are finite.

- [ ] **Step 2: Make prediction path pass feature names**

Ensure `_feature_values` receives the requested feature names from both
training and prediction.

- [ ] **Step 3: Run RED test**

Expected: pass.

- [ ] **Step 4: Run model tests**

```bash
PYTHONPATH=src/objectnav_core pytest -q \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py
```

## Chunk 2: Offline Interaction Smoke

### Task 3: Verification and artifact

**Files:**
- Create: `docs/experiments/2026-05-30-official-action-conditioned-local-action-scorer-yolo-smoke.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Run focused local gate**

Run the standard focused official-memory/exporter/model/evaluator test set.

- [ ] **Step 2: Sync to Linux and run focused gate**

Use `/home/badger/anaconda3/envs/habitat/bin/python -m pytest`.

- [ ] **Step 3: Train interaction model**

Train from:

`runs/habitat_official_objectnav/local_action_effect_dataset_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/dataset.json`

with an explicit feature list containing action one-hots, temporal features, and
action-state interactions.

- [ ] **Step 4: Document metrics**

Compare default, additive temporal, and interaction temporal offline metrics.
Do not claim ObjectNav benchmark improvement.
