# Official Detector-Guided Memory Approach Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `memory_belief_frontier` center and approach current-view target detections before STOP, using bbox/depth evidence to avoid premature detector STOP.

**Architecture:** Refactor the existing detector-match helper into reusable target-evidence extraction while preserving detector trace output. Add a small local-control layer in `memory_belief_frontier`; `memory_guided_frontier` keeps its existing detector-confirmed STOP behavior for compatibility.

**Tech Stack:** Python, NumPy, pytest, Habitat official evaluator.

---

## Chunk 1: Detector Target Evidence Tests

### Task 1: Specify local detector control behavior

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Replace immediate STOP expectation for `memory_belief_frontier`**

Change the existing detector precedence test so a far/current target detection
does not STOP immediately. Assert the policy records detector local-control
debug and does not score frontiers in that step.

- [x] **Step 2: Add off-center target test**

Create a right-side target bbox and assert `memory_belief_frontier` chooses
`turn_right` with `decision="center_detector_target"`.

- [x] **Step 3: Add centered far target test**

Create a centered target bbox with far normalized depth and clear center
corridor. Assert the action is `move_forward` with
`decision="approach_detector_target"`.

- [x] **Step 4: Add range-confirmed STOP test**

Create a centered target bbox with sufficiently large area and close bbox
depth. Assert the action is `stop` with
`decision="stop_on_detector_range_confirmed"`.

- [x] **Step 5: Run RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_belief_frontier_centers_off_axis_detector_target_before_stop \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_belief_frontier_approaches_centered_far_detector_target_before_stop \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_belief_frontier_stops_only_when_detector_depth_is_close -q
```

Expected: fail because detector matches still emit immediate STOP.

## Chunk 2: Local Detector Approach Implementation

### Task 2: Add target-evidence extraction

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Extend detector match payload**

Include bbox center offset, bbox area fraction, depth median, and depth scale in
the returned target-match payload when bbox/depth are available.

- [x] **Step 2: Add STOP plausibility helper**

Return true only when bbox center is within tolerance, bbox area exceeds a
minimum fraction, and bbox depth is within a conservative metric or normalized
range.

- [x] **Step 3: Add local-control helper**

For `memory_belief_frontier`:

1. turn toward off-center bbox;
2. stop on range-confirmed centered bbox;
3. move forward toward centered far bbox when depth corridor is clear;
4. otherwise fall back to memory-belief frontier scoring.

- [x] **Step 4: Run GREEN**

Run the RED command again. Expected: pass.

## Chunk 3: Verification And Research Trail

### Task 3: Verify and document

**Files:**
- Modify: `docs/design/2026-05-30-official-detector-guided-memory-approach.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Optionally create: `docs/experiments/2026-05-30-official-detector-guided-memory-approach-yolo-query-smoke.md`

- [x] **Step 1: Run focused tests**

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

- [x] **Step 3: Run Linux focused verification**

Sync touched files to `/home/badger/Desktop/dual-anchor-lifelong-objectnav`,
then run the focused test command in conda env `habitat`.

- [x] **Step 4: Run live diagnostic smoke if dependencies are available**

Compare the new four-episode YOLO query artifact against
`memory_belief_frontier_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.
Record both official metrics and detector-trace evidence. Do not claim a
benchmark win unless official Habitat success/SPL actually improve.

Result: implemented and verified. The live diagnostic improved target-match
detections from `1` to `23`, but official success stayed `0/4` and SPL stayed
`0.0`, so this is not a benchmark win.
