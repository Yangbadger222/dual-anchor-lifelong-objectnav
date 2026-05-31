# Official TargetNav Interface Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a non-oracle TargetNav interface for terminal ObjectNav approach after memory-guided target reacquisition.

**Architecture:** Register a new policy that reuses memory-active-perception exploration, projects target detections with depth into episode-relative coordinates, and sends the target to a pluggable TargetNav backend. The first backend is Habitat occupancy-grid local planning; later backends can use Mobile-SAM/depth and Nav2.

**Tech Stack:** Python, pytest, Habitat official ObjectNav evaluator, existing occupancy grid, YOLO/Grounding-DINO detector adapters.

---

## Chunk 1: Policy and Projection

### Task 1: Register TargetNav Policy Boundary

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] Write failing registration test for `memory_active_perception_frontier_targetnav`.
- [ ] Run the specific test and confirm failure.
- [ ] Add policy registration, policy kind, and TargetNav manifest fields.
- [ ] Re-run the test and confirm pass.

### Task 2: Project Detector Goal

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] Write failing test that a centered bbox with finite depth creates an episode-relative target coordinate.
- [ ] Run the specific test and confirm failure.
- [ ] Implement `_targetnav_goal_from_detector_match`.
- [ ] Re-run the test and confirm pass.

## Chunk 2: Occupancy Target Action

### Task 3: Navigate Toward Target Cell

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] Write failing test that a free grid path ahead selects `move_forward`.
- [ ] Write failing test that an off-axis target selects the correct turn.
- [ ] Implement nearest-free-cell and BFS path helpers.
- [ ] Implement `_select_detector_goal_occupancy_action`.
- [ ] Re-run the tests and confirm pass.

### Task 4: Fallback and Episode Loop

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] Write failing episode-loop test where detector match activates detector-goal occupancy debug.
- [ ] Write failing missing-depth test that falls back to existing detector action.
- [ ] Wire the policy into `_select_policy_action`.
- [ ] Record debug fields in policy trace and final episode debug.
- [ ] Re-run focused tests.

## Chunk 3: Verification and Habitat Smoke

### Task 5: Local Gate

- [ ] Run focused eval/CLI tests.
- [ ] Run compileall on touched files.
- [ ] Run CLI help and `git diff --check`.

### Task 6: Linux Smoke and Docs

- [ ] Sync touched files to Linux mirror with `rsync -R`.
- [ ] Run focused tests and compileall in `conda habitat`.
- [ ] Run four-episode YOLO smoke with the new policy.
- [ ] Create experiment report and update devlog/handoff with exact metrics and limitations.
