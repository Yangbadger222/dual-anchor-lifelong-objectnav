# Official Adaptive Detector Servo Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-episode adaptive detector-centering state so immediate target loss flips future centering direction and performs a one-step reacquire turn.

**Architecture:** Extend `OfficialPolicyState` with detector-servo fields. Keep the behavior inside `memory_belief_frontier`: target matches update servo state, immediate no-match after centering emits `reacquire_detector_target`, and all other no-match cases continue through memory-belief/frontier fallback.

**Tech Stack:** Python, NumPy, pytest, Habitat official evaluator.

---

## Chunk 1: Servo Tests

### Task 1: Specify action-effect adaptation

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Add sequence detector helper**

Add a small test detector that returns a different detection list on each call.

- [x] **Step 2: Write failing adaptive-centering test**

Use `memory_belief_frontier` with detector sequence:

1. right-edge target detection;
2. no target detection;
3. right-edge target detection again.

Assert actions are:

1. `turn_right` for the initial centering assumption;
2. `turn_left` with `decision="reacquire_detector_target"`;
3. `turn_left` because the center-direction sign flipped.

- [x] **Step 3: Run RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_belief_frontier_flips_detector_center_direction_after_immediate_target_loss -q
```

Expected: fail because no target-match steps currently fall back to occupancy
frontier instead of reacquiring.

## Chunk 2: Servo Implementation

### Task 2: Add adaptive detector state

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Extend policy state**

Add per-episode fields:

- `detector_center_direction_sign`;
- `last_detector_center_step`;
- `last_detector_center_action`;
- `last_detector_center_offset_fraction`.

- [x] **Step 2: Record detector centering action**

When `_select_detector_guided_target_action` chooses `center_detector_target`,
record the step/action/offset and include the direction sign in debug.

- [x] **Step 3: Add no-match reacquire path**

In `memory_belief_frontier`, when no target match follows a detector-centering
step immediately:

- flip the center direction sign;
- emit the opposite turn;
- set `memory_debug.decision="reacquire_detector_target"`;
- do not call memory-belief/frontier fallback for that one step.

- [x] **Step 4: Run GREEN**

Run the RED command again. Expected: pass.

## Chunk 3: Verification And Diagnostic Run

### Task 3: Verify and document

**Files:**
- Modify: `docs/design/2026-05-30-official-adaptive-detector-servo.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Optionally create: `docs/experiments/2026-05-30-official-adaptive-detector-servo-yolo-query-smoke.md`

- [x] **Step 1: Run focused local tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q
```

- [x] **Step 2: Run syntax and whitespace checks**

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

- [x] **Step 3: Run Linux verification**

Sync touched files and run the focused test command in conda env `habitat`.

- [x] **Step 4: Rerun diagnostic smoke**

Compare official metrics and `policy_trace.json` decision counts against
`memory_belief_frontier_policy_trace_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Result: implemented and verified. The live smoke did not improve official
metrics or action counts; it converted `22` fallback reversals into explicit
`reacquire_detector_target` steps, showing that a one-step flip is not enough.
