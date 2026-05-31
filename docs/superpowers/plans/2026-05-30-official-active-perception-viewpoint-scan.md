# Official Active-Perception Viewpoint Scan Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded orient/scan phase when `memory_active_perception_frontier` reaches a selected free viewpoint.

**Architecture:** Extend `OfficialPolicyState` with minimal scan bookkeeping. In `_select_memory_active_perception_frontier_fallback`, after selecting a reachable viewpoint and populating debug fields, run a scan decision when `path_distance_m` is within one occupancy cell: orient toward the memory anchor, then optionally sweep for a bounded number of steps.

**Tech Stack:** Python, NumPy, pytest, existing official Habitat ObjectNav evaluator.

---

### Task 1: Reached-Viewpoint Orient Test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Add imports for direct fallback testing**

Import `OfficialPolicyState` and
`_select_memory_active_perception_frontier_fallback` in the evaluator test file.

- [x] **Step 2: Write RED test**

Build a tiny occupancy map where the current origin cell is the free viewpoint
and an unknown frontier is adjacent. Use a memory anchor to the right. Assert
the fallback returns `turn_right`, records
`active_perception_phase=orient_anchor`, and records positive anchor bearing
error.

- [x] **Step 3: Run RED test**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_frontier_orients_to_anchor_from_reached_viewpoint -q
```

Expected: fail because the current policy moves or falls back instead of
orienting to the anchor from a reached viewpoint.

### Task 2: Scan State And Action

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Add bounded scan state**

Add fields to `OfficialPolicyState` for remaining scan steps and the scanned
viewpoint cell. Keep defaults inert so other policies are unaffected.

- [x] **Step 2: Implement reached-viewpoint orient action**

When selected `path_distance_m <= occupancy_map.cell_size_m`, compute anchor
bearing from current observation. If the anchor bearing error exceeds
`memory_bearing_tolerance_rad`, return the corresponding turn action and record
debug fields.

- [x] **Step 3: Add bounded aligned scan**

If already oriented and the viewpoint has not exhausted its scan budget, return
a deterministic turn sweep for a small bounded number of steps. Mark the
viewpoint scanned once exhausted.

- [x] **Step 4: Run focused tests**

Run the new test and existing active-perception tests.

### Task 3: Verification And Smoke

**Files:**
- Modify: `docs/design/2026-05-30-official-active-perception-viewpoint-scan.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: experiment report if the Linux smoke runs.

- [x] **Step 1: Run local focused gate**

Run focused official tests, compileall, and `git diff --check`.

- [x] **Step 2: Sync to Linux and rerun gate**

Use `rsync -avR`, activate conda env `habitat`, and rerun the focused gate.

- [x] **Step 3: Run YOLO smoke**

Run the same four-episode detector-backed official smoke with a fresh output
name containing `viewpoint_scan`.

- [x] **Step 4: Document result**

Record official metrics, detector target-match counts, scan/orient decision
counts, and whether the scan phase improves or regresses behavior.
