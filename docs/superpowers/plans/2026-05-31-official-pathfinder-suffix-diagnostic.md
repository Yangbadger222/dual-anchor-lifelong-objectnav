# Official Pathfinder Suffix Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a diagnostic ObjectNav policy that switches from memory-active-perception exploration to a Habitat pathfinder follower after target detection.

**Architecture:** Keep existing exploration behavior intact. Add one new policy name that reuses the current detector check, activates a suffix controller on target match, and records explicit oracle/debug fields. The controller is injectable for local tests and backed by Habitat's follower in Linux runs.

**Tech Stack:** Python, pytest, Habitat-Lab ObjectNav, Habitat `ShortestPathFollower`/Habitat-Sim follower, existing official evaluator CLI.

---

## Chunk 1: Local Diagnostic Policy

### Task 1: Registration and Manifest

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write the failing policy registration test**

Add a test that builds `OfficialObjectNavRunConfig(policy="memory_active_perception_frontier_pathfinder_suffix")`, calls `make_protocol_manifest`, and asserts the policy is in `SUPPORTED_OFFICIAL_POLICIES`, the policy kind is diagnostic, and `invalid_for_benchmark_claim_reason` is pathfinder/oracle-specific.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_pathfinder_suffix_policy_is_diagnostic -q
```

Expected: fail because the policy is not registered.

- [ ] **Step 3: Register the policy minimally**

Add the policy to `SUPPORTED_OFFICIAL_POLICIES`, `_policy_kind`, and benchmark-invalid manifest handling.

- [ ] **Step 4: Re-run the test and verify it passes**

Run the same pytest command. Expected: pass.

### Task 2: Suffix Activation and Action Selection

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write the failing activation test**

Use `_FakeDepthOfficialObjectNavEnv`, a `_StaticDetector` target match, and an injected fake suffix controller returning `("move_forward", "stop")`. Assert actions are `["move_forward", "stop"]`, detector is called once before suffix activation, and debug records `pathfinder_suffix_active`.

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_pathfinder_suffix_activates_after_target_detection -q
```

Expected: fail because suffix controller plumbing does not exist.

- [ ] **Step 3: Implement suffix state and selector**

Add injectable controller support to `run_official_objectnav_episode_loop`, fields on `OfficialPolicyState`, and a selector that activates after a detector match.

- [ ] **Step 4: Re-run the activation test**

Expected: pass.

### Task 3: Follower Action Mapping and Goal Failure

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write failing unit tests**

Add tests for `_follower_action_name(0..3)`, one-hot action arrays, `None`, and a missing-goal fake controller that falls back to the old detector-guided action.

- [ ] **Step 2: Run tests and verify failure**

Run the specific new tests with pytest.

- [ ] **Step 3: Implement action mapping and fallback behavior**

Map `0/1/2/3` to `stop/move_forward/turn_left/turn_right`; support strings and one-hot arrays; record debug reasons for unavailable suffixes.

- [ ] **Step 4: Re-run focused tests**

Expected: pass.

## Chunk 2: CLI, Verification, and Real Smoke

### Task 4: CLI Radius Plumbing

**Files:**
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`

- [ ] **Step 1: Write failing CLI forwarding test**

Assert `--pathfinder-suffix-goal-radius-m 1.0` is parsed and forwarded to the runner.

- [ ] **Step 2: Run CLI test and verify failure**

Run the specific CLI test.

- [ ] **Step 3: Add parser and runner argument**

Thread `pathfinder_suffix_goal_radius_m` through preflight/eval config and manifest.

- [ ] **Step 4: Re-run CLI test**

Expected: pass.

### Task 5: Focused Local Gate

**Files:**
- Verify touched Python files and docs.

- [ ] **Step 1: Run focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

- [ ] **Step 2: Run compileall**

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py
```

- [ ] **Step 3: Check CLI help and diff whitespace**

```bash
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_official_objectnav_eval --help
git diff --check
```

### Task 6: Linux Habitat Smoke and Docs

**Files:**
- Create: `docs/experiments/2026-05-31-official-pathfinder-suffix-diagnostic.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Sync touched files to Linux mirror**

Use `rsync -R` for touched source/test/doc files only.

- [ ] **Step 2: Run Linux focused tests in `conda habitat`**

Run the same focused pytest and compileall commands under `/home/badger/anaconda3/bin/conda run -n habitat`.

- [ ] **Step 3: Run bounded YOLO smoke**

Run the new policy on the same four-episode YOLO configuration and record official metrics plus suffix activation counts.

- [ ] **Step 4: Document results**

Create experiment report, update devlog and handoff. State clearly whether success is nonzero and that this policy is oracle/diagnostic only.
