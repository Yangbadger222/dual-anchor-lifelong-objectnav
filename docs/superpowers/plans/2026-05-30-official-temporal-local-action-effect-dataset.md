# Official Temporal Local Action-Effect Dataset Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the official local action-effect dataset with temporal evidence and short-horizon labels for learned local ObjectNav control.

**Architecture:** Keep the exporter pure-Python and trace-driven. Add history/horizon arguments, compute past-only temporal features, compute future-only labels, and keep JSON/CSV schemas explicit.

**Tech Stack:** Python stdlib JSON/CSV, pytest, existing `objectnav_core.evaluation.habitat_official_local_action_dataset` module.

---

## Chunk 1: Dataset Temporal Features

### Task 1: Add RED temporal feature test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_dataset.py`

- [ ] **Step 1: Write failing test**

Add `test_official_local_action_dataset_exports_temporal_features_and_horizon_labels`.
Use a synthetic trace with visible evidence at steps `0`, `1`, and `2`, then
target loss at step `3`. Export with `history_steps=2` and `horizon_steps=2`.
Assert the step `2` example has:

```python
features["history_observed_step_count"] == 2
features["previous_target_visible"] is True
features["recent_target_visible_count"] == 3
features["steps_since_last_target_visible"] == 0
features["previous_action"] == "move_forward"
features["previous_decision"] == "approach_detector_target_after_center_loss"
features["current_bbox_area_minus_previous"] < 0.0
features["current_abs_center_offset_minus_previous"] > 0.0
features["recent_move_forward_count"] == 2
labels["horizon_observed_step_count"] == 1
labels["target_visible_within_horizon"] is False
labels["target_lost_within_horizon"] is True
labels["first_target_loss_step_delta"] == 1
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest -q \
  src/objectnav_core/tests/test_habitat_official_local_action_dataset.py::test_official_local_action_dataset_exports_temporal_features_and_horizon_labels
```

Expected: fail because `history_steps` / `horizon_steps` and temporal fields do
not exist.

### Task 2: Implement temporal dataset fields

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_dataset.py`

- [ ] **Step 1: Add API parameters**

Extend `export_official_local_action_dataset` with:

```python
history_steps: int = 1
horizon_steps: int = 1
```

Clamp both to at least `1`.

- [ ] **Step 2: Add schema constants**

Add temporal feature fields:

```python
"history_observed_step_count",
"previous_target_visible",
"recent_target_visible_count",
"steps_since_last_target_visible",
"previous_action",
"previous_decision",
"recent_move_forward_count",
"recent_turn_left_count",
"recent_turn_right_count",
"recent_reacquire_count",
"current_confidence_minus_previous",
"current_bbox_area_minus_previous",
"current_depth_minus_previous",
"current_abs_center_offset_minus_previous",
"suppressed_turn_left",
"suppressed_turn_right",
```

Add short-horizon label fields:

```python
"horizon_observed_step_count",
"target_visible_within_horizon",
"target_visible_at_horizon",
"target_lost_within_horizon",
"first_target_loss_step_delta",
"best_future_detector_confidence",
"best_future_bbox_area_fraction",
"best_future_abs_center_offset_fraction",
"best_future_depth_median",
"best_future_bbox_area_delta",
"best_future_abs_center_offset_delta",
"best_future_depth_delta",
```

- [ ] **Step 3: Compute past-only temporal features**

Precompute evidence for every policy step. Pass current history window into
`_features`. Use only current and previous steps from the same episode.

- [ ] **Step 4: Compute future-only horizon labels**

Pass future horizon steps/evidence into `_labels`. Stop at episode boundary.

- [ ] **Step 5: Run RED test to verify GREEN**

Run the test from Task 1. Expected: pass.

### Task 3: Add CLI support

**Files:**
- Modify: `src/objectnav_core/objectnav_core/cli/export_habitat_official_local_action_dataset.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_dataset.py`

- [ ] **Step 1: Add RED CLI assertions**

Extend the CLI test to pass `--history-steps 2 --horizon-steps 2` and assert the
written JSON has:

```python
report["history_steps"] == 2
report["horizon_steps"] == 2
```

- [ ] **Step 2: Run CLI test to verify RED**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest -q \
  src/objectnav_core/tests/test_habitat_official_local_action_dataset.py::test_official_local_action_dataset_cli_writes_json_and_csv
```

Expected: fail because CLI arguments are missing.

- [ ] **Step 3: Implement CLI arguments**

Add parser args and forward them into `export_official_local_action_dataset`.

- [ ] **Step 4: Run dataset tests**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest -q \
  src/objectnav_core/tests/test_habitat_official_local_action_dataset.py
```

Expected: all pass.

## Chunk 2: Verification and Trace Export

### Task 4: Run focused verification

**Files:**
- No new files.

- [ ] **Step 1: Run focused official gate**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest -q \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_local_action_dataset.py \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_ros_packaging.py
```

- [ ] **Step 2: Run compile/check**

Run:

```bash
python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

### Task 5: Linux export smoke

**Files:**
- Create: `docs/experiments/2026-05-30-official-temporal-local-action-effect-dataset-yolo-trace.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Sync touched files to Linux**

Rsync the exporter, CLI, and test file to
`/home/badger/Desktop/dual-anchor-lifelong-objectnav`.

- [ ] **Step 2: Run Linux focused gate**

Use `/home/badger/anaconda3/envs/habitat/bin/python -m pytest` with the focused
gate from Task 4.

- [ ] **Step 3: Export temporal dataset**

Run the CLI on the fixed learned-local YOLO trace:

```bash
PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.export_habitat_official_local_action_dataset \
  runs/habitat_official_objectnav/memory_learned_local_frontier_suppressed_failed_turns_yolo_discovery_prior_local_action_model_trace_4ep_50steps_20260530_v1/policy_trace.json \
  --detector-trace runs/habitat_official_objectnav/memory_learned_local_frontier_suppressed_failed_turns_yolo_discovery_prior_local_action_model_trace_4ep_50steps_20260530_v1/detector_trace.json \
  --output runs/habitat_official_objectnav/local_action_effect_dataset_temporal_learned_local_suppressed_yolo_4ep_50steps_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/local_action_effect_dataset_temporal_learned_local_suppressed_yolo_4ep_50steps_20260530_v1/examples.csv \
  --source-run-id memory_learned_local_frontier_suppressed_failed_turns_yolo_4ep_50steps_20260530_v1 \
  --history-steps 3 \
  --horizon-steps 3
```

- [ ] **Step 4: Record summary**

Document example counts, visible counts, transition counts, and a few target
episode temporal rows. Do not claim benchmark improvement.
