# Official TargetNav DDPPO Backend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire TargetNav target belief into a Habitat-Baselines PointNav/DDPPO backend using the verified HM3D depth checkpoint.

**Architecture:** Add a new `memory_active_perception_frontier_targetnav_ddppo` policy that reuses the existing detector/depth target belief and PointGoal adapter, then delegates local action selection to an optional DDPPO backend. Unit tests use an injected fake backend; Linux verification uses the real `PointNavResNetPolicy` and checkpoint.

**Tech Stack:** Python, NumPy, PyTorch, Gym spaces, Habitat-Baselines 0.3.3, pytest, Linux `conda habitat`.

---

## Chunk 1: Config and Manifest Boundary

### Task 1: Register DDPPO TargetNav Policy

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`

- [ ] Write a failing manifest test for
  `memory_active_perception_frontier_targetnav_ddppo` with backend
  `ddppo_pointnav`.
- [ ] Write a failing validation/CLI test requiring
  `--targetnav-ddppo-checkpoint-path`.
- [ ] Add config field, CLI flag, policy registration, policy kind, validation,
  and manifest metadata.
- [ ] Run the targeted tests and confirm GREEN.

## Chunk 2: DDPPO Observation and Fake Backend

### Task 2: Prove TargetNav Calls a Backend

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] Add a fake backend class in tests with `act(depth, pointgoal) -> action_id`.
- [ ] Write a failing policy-loop test showing detector/depth target belief is
  converted to `[rho, -phi]` and sent to the fake backend.
- [ ] Implement `_select_targetnav_ddppo_action(...)` and backend injection via
  `OfficialPolicyState`.
- [ ] Map action ids `{0,1,2,3}` to official actions.
- [ ] Confirm targeted tests pass.

## Chunk 3: Real Backend Loader

### Task 3: Load Habitat-Baselines PointNavResNetPolicy

**Files:**
- Prefer create: `src/objectnav_core/objectnav_core/evaluation/habitat_pointnav_ddppo_backend.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] Add depth preprocessing tests for `H x W`, `H x W x 1`, normalized depth,
  and meter-valued depth.
- [ ] Implement `_prepare_ddppo_depth_observation(...)`.
- [ ] Implement lazy imports for `torch`, `gym.spaces`, and
  `PointNavResNetPolicy`.
- [ ] Implement trusted checkpoint compatibility shim for old
  `habitat.config.default.Config`.
- [ ] Load checkpoint state dict into `PointNavResNetPolicy` and reject nonzero
  missing/unexpected keys.
- [ ] Add a Linux-only manual probe command in docs; keep normal unit tests
  independent of GPU and downloaded models.

## Chunk 4: Runtime Verification

### Task 4: Run Gates and Smoke

**Files:**
- Modify: `docs/design/2026-05-31-official-targetnav-ddppo-backend.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Optional create: `docs/experiments/2026-05-31-official-targetnav-ddppo-yolo-smoke.md`

- [ ] Run local focused tests, compileall, and `git diff --check`.
- [ ] Sync touched files to Linux.
- [ ] Run Linux focused tests and compileall.
- [ ] Run a one-episode smoke with
  `memory_active_perception_frontier_targetnav_ddppo`.
- [ ] If one-episode smoke is mechanically sound, run the same four-episode
  YOLO protocol as previous TargetNav smokes.
- [ ] Record metrics and failure modes without claiming benchmark success unless
  official metrics improve substantially.
