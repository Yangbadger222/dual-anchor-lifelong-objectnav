# Official Online Option-Value Labels Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline exporter that labels active-perception candidates by short-horizon detector evidence under the same sticky plus blocked-scan option controller used online.

**Architecture:** Extend the existing official candidate-rollout dataset module with a separate option-value dataset API and CSV writer. Reuse policy-trace sampling, replay, detector evidence, state-feature extraction, and episode-relative candidate pose conversion. Add a small dynamic option controller that uses current observation pose/depth at each rollout step instead of the older static left-scan continuation.

**Tech Stack:** Python, Habitat official evaluator wrappers, existing detector adapters, pytest, JSON/CSV artifacts.

---

## File Structure

- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`
  - Add schema constants, CSV fields, option rollout state, dynamic option action selection, dataset export, and CSV writer.
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py`
  - CLI wrapper mirroring the candidate-viewpoint restore exporter with option horizon/scan flags.
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
  - Add focused RED/GREEN tests using fake replay envs and detectors.
- Modify: `src/objectnav_core/setup.py`
  - Add console-script entry if this package's current pattern requires it.
- Modify docs after verification:
  - `docs/devlog/2026-05.md`
  - `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
  - `docs/experiments/2026-05-31-official-online-option-value-labels.md` if a Linux smoke is run.

## Chunk 1: Dataset API and RED Tests

### Task 1: Option-value dataset emits candidate rows

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write failing test**

Add `test_candidate_option_value_dataset_labels_hidden_to_visible_option_rollouts`.

The test should:

- write the existing fake policy trace;
- use a fake env whose first candidate option produces target pixels after an option scan;
- call `export_official_candidate_option_value_dataset(...)`;
- assert:
  - `task == "habitat_official_candidate_option_value_dataset"`
  - `schema_version == "official-candidate-option-value-v1"`
  - rows live under `candidate_viewpoints`
  - `labels.current_target_visible_at_restore is False`
  - `labels.hidden_to_visible_within_option_rollout is True` for the positive candidate
  - the row records `option_rollout_actions`.

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_option_value_dataset_labels_hidden_to_visible_option_rollouts -q
```

Expected: fails because `export_official_candidate_option_value_dataset` is missing.

- [ ] **Step 3: Implement minimal API shell**

Add:

- `CANDIDATE_OPTION_VALUE_SCHEMA_VERSION`
- `export_official_candidate_option_value_dataset(...)`
- an option row builder that reuses `_candidate_viewpoint_pose_from_cell`,
  `_predecision_state_features`, `_current_restore_evidence`, and
  `_detect_target_evidence`.

- [ ] **Step 4: Run test to verify GREEN**

Run the same focused test. Expected: pass.

### Task 2: Dynamic option controller uses live pose and depth

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write failing test**

Add `test_candidate_option_value_rollout_turns_then_moves_using_live_pose`.

The fake env should expose observations with `gps=[forward, right]`,
`compass=[heading]`, clear depth, and a candidate at episode-relative
`x=0.25,z=0.25`. Assert the option actions include a turn toward the candidate
followed by `move_forward` after the fake env updates heading.

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_option_value_rollout_turns_then_moves_using_live_pose -q
```

Expected: fails until dynamic pose-based action selection exists.

- [ ] **Step 3: Implement option action selection**

Add helpers:

- `_candidate_option_rollout_action(...)`
- `_observation_episode_xz(...)`
- `_observation_heading_rad(...)`
- `_candidate_option_pose(...)`

Rules:

- Convert Habitat GPS `[forward, right]` to `x=right,z=forward`.
- Bearing to candidate is `atan2(candidate_x - x, candidate_z - z)`.
- Turn right for positive wrapped bearing error, left for negative.
- Move forward only when aligned and center depth is clear.
- Preserve episode-relative coordinates.

- [ ] **Step 4: Run test to verify GREEN**

Run the focused test. Expected: pass.

## Chunk 2: Blocked Scan, CSV, and CLI

### Task 3: Blocked option scans before fallback

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write failing test**

Add `test_candidate_option_value_rollout_scans_when_candidate_corridor_blocked`.

The fake env should start aligned to the candidate with blocked center depth.
Assert:

- the option emits bounded `turn_left` scan actions;
- `option_blocked_scan_step_count` is recorded;
- target evidence can become positive during the scan;
- no immediate occupancy fallback action is recorded.

- [ ] **Step 2: Run test to verify RED**

Expected: fails until blocked scan state exists.

- [ ] **Step 3: Implement scan state**

Add an internal dataclass with:

- `scan_steps_remaining`
- `blocked_scan_started`
- `reached_scan_started`

Keep this local to the exporter so online policy state is not mutated.

- [ ] **Step 4: Run focused test**

Expected: pass.

### Task 4: CSV writer and CLI

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/setup.py` if needed.

- [ ] **Step 1: Write failing tests**

Add:

- `test_candidate_option_value_dataset_writes_csv`
- `test_candidate_option_value_dataset_cli_writes_json_and_csv`

Assert CLI forwards:

- `candidates_per_state`
- `option_horizon_steps`
- `option_scan_steps`
- state sampling caps
- detector config

- [ ] **Step 2: Run tests to verify RED**

Run the two focused tests. Expected: fail due missing writer/CLI.

- [ ] **Step 3: Implement writer and CLI**

Mirror the existing candidate-viewpoint restore CLI style. Summary JSON should
include:

- task
- schema_version
- state_count
- candidate_option_count
- positive_option_count
- invalid_option_count

- [ ] **Step 4: Run tests to verify GREEN**

Run the focused tests. Expected: pass.

## Chunk 3: Verification and Linux Smoke

### Task 5: Local gates

- [ ] **Run focused candidate-rollout tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py -q
```

- [ ] **Run compileall**

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py
```

- [ ] **Run diff checks**

```bash
git diff --check
rg -n "[ \t]+$" <touched files>
```

### Task 6: Linux sync and smoke

- [ ] **Sync touched files to Linux mirror**

Use `rsync` for only touched files to
`badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/`.

- [ ] **Run focused Linux tests**

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py -q'
```

- [ ] **Export bounded option-value smoke**

Use a small known trace first, for example:

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset \
    runs/habitat_official_objectnav/memory_active_perception_frontier_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1/policy_trace.json \
    --output runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1/dataset.json \
    --csv-output runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1/labels.csv \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --candidates-per-state 5 \
    --option-horizon-steps 8 \
    --option-scan-steps 4 \
    --state-sampling active_phase_path \
    --max-states 8 \
    --seed 313'
```

### Task 7: Documentation

- [ ] **Add experiment report if smoke runs**

Create `docs/experiments/2026-05-31-official-online-option-value-labels.md`
with commands, metrics, and interpretation.

- [ ] **Update devlog and handoff**

Append to:

- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Final verification**

Run focused tests again after docs and report any commands that could not be
run.
