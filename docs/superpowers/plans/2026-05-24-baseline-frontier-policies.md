# Baseline Frontier Policy Switches Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit nearest-frontier and information-gain frontier policy switches for ROS-free Phase 1A and later replay baselines.

**Architecture:** Add a focused `objectnav_core.planning.frontier_policies` module that evaluates frontier clusters into candidates using known-side viewpoints, A* path cost, information gain, and revisit penalty. Keep `Phase1ATrialRunner` default behavior stable by defaulting to `first_frontier`, while allowing callers to request `nearest_frontier` or `information_gain`.

**Tech Stack:** Python 3.13, pytest, dataclasses/enums, `OccupancyGrid`, `FrontierCluster`, `Pose2D`, `AStarGridNavigationClient`.

---

## Chunk 1: Frontier Policy Selector

### Task 1: Candidate Evaluation And Policy Selection

**Files:**
- Create: `src/objectnav_core/objectnav_core/planning/frontier_policies.py`
- Modify: `src/objectnav_core/tests/test_simulation.py`

- [x] Write failing tests proving `nearest_frontier` selects the lowest A* path-cost candidate and `information_gain` can select a farther higher-gain candidate.
- [x] Run `python3 -m pytest src/objectnav_core/tests/test_simulation.py -v` and confirm failure because `frontier_policies` is missing.
- [x] Implement `FrontierPolicyName`, `FrontierPolicyCandidate`, `estimate_astar_path_cost_m`, and `select_frontier_candidate`.
- [x] Re-run `python3 -m pytest src/objectnav_core/tests/test_simulation.py -v` and confirm pass.

## Chunk 2: Phase 1A Runner Switch

### Task 2: Optional Runner Policy

**Files:**
- Modify: `src/objectnav_core/objectnav_core/simulation/trials.py`
- Modify: `src/objectnav_core/tests/test_trials.py`

- [x] Write a failing test proving `Phase1ATrialRunner(frontier_policy="information_gain")` succeeds and records `information_gain_frontier`.
- [x] Run `python3 -m pytest src/objectnav_core/tests/test_trials.py -v` and confirm failure.
- [x] Update the runner constructor and discovery loop to use the selector.
- [x] Re-run `python3 -m pytest src/objectnav_core/tests/test_trials.py -v` and confirm pass.

## Chunk 3: Documentation And Verification

### Task 3: Project Trail And Full Checks

**Files:**
- Create: `docs/design/2026-05-24-baseline-frontier-policies.md`
- Modify: `docs/superpowers/plans/2026-05-24-baseline-frontier-policies.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-24-phase1a-objectnav-core.md`

- [x] Record the design boundary and verification plan.
- [x] Update the devlog with files changed, reason, verification, and follow-up.
- [x] Update the Phase 1A handoff so baseline policy switches are no longer the first unfinished next step.
- [x] Run `python3 -m pytest src/objectnav_core/tests -v`.
- [x] Run `python3 -m compileall -q src/objectnav_core/objectnav_core`.
- [x] Run the Phase 1A CLI and confirm artifact metrics still persist.
- [x] Run a core-only ROS-coupling scan.
