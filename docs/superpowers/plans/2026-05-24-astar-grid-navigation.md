# A* Grid Navigation Backend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic ROS-free A* navigation backend for offline ObjectNav verification.

**Architecture:** Implement `AStarGridNavigationClient` beside the existing discrete client in `objectnav_core.simulation.navigation`. The client plans over known free cells in `OccupancyGrid`, exposes the same `send_goal/cancel_goal/tick/status` behavior shape, and leaves the Phase 1A trial runner default unchanged.

**Tech Stack:** Python 3.13, pytest, NumPy-backed `OccupancyGrid`, Pydantic `Pose2D` and `NavigationStatus`.

---

## Chunk 1: A* Client Behavior

### Task 1: Tests For Reachability, Blocking, And Cancellation

**Files:**
- Modify: `src/objectnav_core/tests/test_simulation.py`
- Modify: `src/objectnav_core/objectnav_core/simulation/navigation.py`

- [x] Write failing tests for A* detouring around an occupied obstacle, refusing unknown gaps, and canceling active goals.
- [x] Run `python3 -m pytest src/objectnav_core/tests/test_simulation.py -v` and confirm the new tests fail because `AStarGridNavigationClient` is missing.
- [x] Implement minimal A* search over 4-connected free cells in `navigation.py`.
- [x] Implement path ticking with the same status and reason semantics as `DiscreteStepNavigationClient`.
- [x] Re-run `python3 -m pytest src/objectnav_core/tests/test_simulation.py -v` and confirm pass.

## Chunk 2: Documentation And Verification

### Task 2: Project Trail And Full Checks

**Files:**
- Create: `docs/design/2026-05-24-astar-grid-navigation.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-24-phase1a-objectnav-core.md`

- [x] Record the design boundary and verification plan.
- [x] Update the devlog with files changed, reason, verification, and follow-up.
- [x] Update the Phase 1A handoff so A* is no longer the first unfinished next step.
- [x] Run `python3 -m pytest src/objectnav_core/tests -v`.
- [x] Run `python3 -m compileall -q src/objectnav_core/objectnav_core`.
- [x] Run a core-only ROS-coupling scan.
