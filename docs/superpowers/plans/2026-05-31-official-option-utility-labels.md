# Official Option-Utility Labels Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend candidate option-value labels with detector confidence gain, official distance progress, and offline STOP-probe success.

**Architecture:** Keep the implementation inside the existing option-value exporter. Each candidate already runs in a fresh replay environment, so official metrics and STOP probing can be measured after the option without changing online policy state. Outcome fields are emitted as labels/analysis data only and are not added to ranker online features.

**Tech Stack:** Python, pytest, Habitat official metric adapter, existing option-value dataset and ranker model.

---

## File Structure

- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`
  - Add utility metric helpers, row fields, labels, CSV fields, and the progress threshold argument.
- Modify: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py`
  - Add `--option-progress-threshold-m` and pass it through.
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
  - Add RED/GREEN tests for confidence gain, official progress, STOP probe, and CLI forwarding.
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py`
  - Add RED/GREEN coverage that outcome fields are not included as ranker features.
- Modify docs after verification:
  - `docs/devlog/2026-05.md`
  - `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
  - optional experiment report if a Linux export smoke is run.

## Task 1: Detector Confidence Gain Label

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write failing test**

Add `test_candidate_option_value_records_detector_confidence_gain`.

The test should use an env whose current view has no target and whose option
scan produces target confidence `0.91`. Assert row fields:

- `initial_detector_confidence is None`
- `best_detector_confidence == 0.91`
- `detector_confidence_gain == 0.91`
- label `detector_confidence_gain_within_option_rollout is True`

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_option_value_records_detector_confidence_gain -q
```

Expected: fail because the row/label fields are absent.

- [ ] **Step 3: Implement minimal production code**

Store initial detector confidence from current evidence, compute gain after the
rollout, add the JSON labels, and add the CSV fields.

- [ ] **Step 4: Verify GREEN**

Run the focused test. Expected: pass.

## Task 2: Official Progress and STOP-Probe Labels

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write failing test**

Add `test_candidate_option_value_records_official_progress_and_stop_probe`.

The fake env should expose `get_metrics()` values whose `distance_to_goal`
decreases during option rollout and whose `success` becomes `1.0` after a
separate `stop` action. Assert:

- `initial_distance_to_goal_m == 2.0`
- `final_distance_to_goal_m == 1.7`
- `min_distance_to_goal_m == 1.7`
- `distance_to_goal_delta_m == 0.3`
- `best_distance_to_goal_delta_m == 0.3`
- `stop_probe_success == 1.0`
- `labels.official_progress_within_option_rollout is True`
- `labels.official_stop_success_after_option_rollout is True`
- `option_rollout_actions` does not include `stop`

- [ ] **Step 2: Verify RED**

Run the focused test. Expected: fail because official utility fields are absent.

- [ ] **Step 3: Implement minimal production code**

Add metric helpers, record initial/final/min distance, compute deltas, run one
offline-only STOP probe after valid option rollout, and add labels.

- [ ] **Step 4: Verify GREEN**

Run the focused test. Expected: pass.

## Task 3: CLI Threshold and Feature-Leak Guard

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py`
- Modify: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py`

- [ ] **Step 1: Write failing CLI test**

Extend `test_candidate_option_value_dataset_cli_writes_json_and_csv` to pass
`--option-progress-threshold-m 0.2` and assert the runner receives
`option_progress_threshold_m == 0.2`.

- [ ] **Step 2: Write failing ranker feature test**

Add `test_candidate_viewpoint_ranker_excludes_option_outcome_fields_from_features`.
Train on enriched candidate rows and assert the model's `feature_names` do not
include:

- `detector_confidence_gain`
- `distance_to_goal_delta_m`
- `best_distance_to_goal_delta_m`
- `stop_probe_success`

- [ ] **Step 3: Verify RED**

Run the two focused tests. Expected: CLI test fails until the flag exists; the
feature test should protect against accidental feature leakage.

- [ ] **Step 4: Implement minimal code**

Add the parser argument and pass-through. Do not add outcome fields to ranker
feature generation.

- [ ] **Step 5: Verify GREEN**

Run the two focused tests. Expected: pass.

## Task 4: Verification and Documentation

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Run local focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q
```

- [ ] **Step 2: Run compileall**

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py
```

- [ ] **Step 3: Run CLI help**

```bash
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset --help
```

- [ ] **Step 4: Run diff hygiene**

```bash
git diff --check
rg -n "[ \t]+$" <touched files>
```

- [ ] **Step 5: Sync touched code/tests to Linux and run focused tests**

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q'
```

- [ ] **Step 6: Update documentation**

Append devlog and handoff notes that describe the new labels, verification, and
why they are offline supervision only.
