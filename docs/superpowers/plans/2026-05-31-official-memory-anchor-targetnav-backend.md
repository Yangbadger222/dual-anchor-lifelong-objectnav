# Official Memory Anchor TargetNav Backend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute selected official memory anchors through the configured TargetNav backend, including an explicit oracle diagnostic path.

**Architecture:** Extend the existing official evaluator only at the TargetNav policy boundary. Detector-confirmed target handling remains first, then matching memory anchors are converted to backend goals, and existing active-perception fallback remains the recovery path.

**Tech Stack:** Python, pytest, Habitat official evaluator helpers, existing navigation backend boundary.

---

## Chunk 1: Memory Anchor Backend Execution

### Task 1: Add Failing Tests

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Add FMM memory-anchor selector test**

Create a test where the base TargetNav policy runs with `targetnav_backend="fmm_grid"`,
a matching `OfficialMemoryAnchor`, and no detector. Expected behavior before
implementation: it falls back to active-perception/occupancy instead of
recording `targetnav_backend=fmm_grid` from a memory anchor.

- [x] **Step 2: Add oracle memory-anchor selector test**

Create a test where the base TargetNav policy runs with
`targetnav_backend="oracle_follower"`, a matching memory anchor, episode start
pose, and a fake pathfinder controller. Expected behavior before implementation:
the controller is not called with the memory anchor goal.

- [x] **Step 3: Add missing-start-pose fallback test**

Create a test where `oracle_follower` has a matching memory anchor but no
episode start pose. Expected behavior: it should not crash and should record a
clear fallback reason.

- [x] **Step 4: Run RED tests**

Run the three tests and confirm they fail for the intended missing behavior.

### Task 2: Implement Anchor Goal Helpers

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Store episode start pose in policy state**

Add parsed `episode_start_position` and `episode_start_rotation` fields to
`OfficialPolicyState`, filled from `env.current_episode`.

- [x] **Step 2: Add memory-anchor TargetNav goal helper**

Implement `_targetnav_goal_from_memory_anchor(anchor)` with `x_m`, `z_m`,
`targetnav_estimator="memory_anchor"`, confidence, source, category, and frame.

- [x] **Step 3: Add inverse pose transform**

Implement `_episode_relative_xz_to_world_position(...)` and quaternion parsing
for `xyzw` Habitat rotations.

### Task 3: Wire Backend Execution

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Add oracle memory-anchor activation helper**

Implement `_activate_and_select_memory_anchor_oracle_action(...)`, reusing the
existing pathfinder/oracle controller follow path.

- [x] **Step 2: Add non-oracle memory-anchor execution**

In `_select_memory_active_perception_frontier_targetnav_action`, after detector
handling and before active-perception fallback, use a matching memory anchor as
the selected backend goal.

- [x] **Step 3: Preserve fallback behavior**

If no anchor exists, conversion fails, or backend execution fails, fall back to
`_select_memory_active_perception_frontier_action_after_detector(...)`.

### Task 4: Verify and Document

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-31-official-memory-anchor-targetnav-backend-smoke.md`

- [x] **Step 1: Run local focused tests**

Run:

```bash
pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_navigation_backend.py -q
```

- [x] **Step 2: Run syntax and whitespace checks**

Run:

```bash
python -m compileall src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py
git diff --check
```

- [x] **Step 3: Sync and verify on Linux Habitat host**

Run the focused tests and a tiny diagnostic smoke with
`--targetnav-backend oracle_follower`.

- [x] **Step 4: Update docs**

Record changed files, commands, metrics, and risks in the devlog, handoff, and
experiment report.
