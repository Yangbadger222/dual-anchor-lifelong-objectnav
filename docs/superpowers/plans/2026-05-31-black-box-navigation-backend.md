# Black-Box Navigation Backend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a hardware-independent navigation backend boundary plus a Habitat oracle follower backend for memory upper-bound experiments.

**Architecture:** Keep the core `NavigationBackend` protocol small: pose, go-to, explore, status, cancel. Add an optional Habitat-specific backend that implements the protocol and exposes `next_action()` so the official Habitat action loop can execute privileged shortest-path actions without changing memory selection logic.

**Tech Stack:** Python, Pydantic models, pytest fake Habitat environments, optional Habitat-Lab `ShortestPathFollower` import.

---

## File Structure

- Modify `src/objectnav_core/objectnav_core/navigation/backend.py`: shared request/status models and legacy client adapter.
- Create `src/objectnav_core/objectnav_core/navigation/habitat_oracle.py`: Habitat shortest-path follower backend.
- Modify `src/objectnav_core/objectnav_core/navigation/__init__.py`: public exports.
- Modify `src/objectnav_core/tests/test_navigation_backend.py`: focused fake-client and fake-Habitat tests.
- Modify `docs/design/2026-05-31-black-box-navigation-backend.md`: design boundary and oracle caveats.
- Modify `docs/devlog/2026-05.md`: dated implementation record.
- Modify `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`: current state and next steps.

## Chunk 1: Existing Backend Boundary

- [x] **Step 1: Write failing tests for core model validation and legacy client wrapping**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_navigation_backend.py -q`

Expected: fail before `objectnav_core.navigation.backend` exists.

- [x] **Step 2: Implement shared backend models and legacy adapter**

Add `NavigationGoal`, `ExplorationRequest`, `NavigationBackendStatus`, `NavigationBackend`, and `LegacyNavigationClientBackend`.

- [x] **Step 3: Verify focused tests pass**

Run the same pytest command.

Expected: pass.

## Chunk 2: Habitat Oracle Follower Backend

- [x] **Step 1: Write failing fake-Habitat tests**

Cover metadata goal extraction, `habitat_world` pose fallback, follower-unavailable failure, follower action mapping to official action names, stop handling, and cancel.

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_navigation_backend.py -q
```

Expected: fail because `HabitatOracleFollowerBackend` does not exist.

- [x] **Step 2: Implement minimal Habitat oracle backend**

Create `objectnav_core.navigation.habitat_oracle.HabitatOracleFollowerBackend` with injected follower factory for tests and lazy Habitat import for real runs.

- [x] **Step 3: Verify focused tests pass**

Run the same pytest command.

Expected: all navigation backend tests pass.

## Chunk 3: Documentation and Verification

- [x] **Step 1: Update devlog and handoff**

Record files changed, commands run, verification, risks, and next action.

- [x] **Step 2: Run syntax and diff checks**

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/navigation \
  src/objectnav_core/tests/test_navigation_backend.py

git diff --check
```

- [x] **Step 3: Optional Linux verification**

If reachable without blocking local work, sync the navigation files and run the focused tests in the remote `habitat` environment.

## Chunk 4: Official Pathfinder Suffix Backend Wiring

- [x] **Step 1: Write failing official-controller test**

Cover that `OfficialPathfinderSuffixController` accepts a backend factory,
selects an episode goal, sends it as `habitat_goal_position`, emits official
action names, and exposes privileged backend status.

- [x] **Step 2: Implement minimal evaluator integration**

Route `OfficialPathfinderSuffixController` through
`HabitatOracleFollowerBackend` while preserving the existing
`memory_active_perception_frontier_pathfinder_suffix` diagnostic policy name and
invalid-for-benchmark manifest caveat.

- [x] **Step 3: Verify pathfinder suffix regressions**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_pathfinder_suffix_activates_after_target_detection \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_pathfinder_suffix_missing_goal_falls_back_to_detector_action \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_follower_action_name_maps_habitat_actions \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_episode_goal_positions_prefers_viewpoints_before_object_centers \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_official_pathfinder_suffix_controller_uses_oracle_backend_boundary -q
```

Expected: all selected tests pass.
