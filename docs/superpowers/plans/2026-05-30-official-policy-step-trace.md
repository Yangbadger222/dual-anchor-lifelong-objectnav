# Official Policy Step Trace Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a compact per-step `policy_trace.json` artifact for official ObjectNav eval runs without changing policy behavior or official metrics.

**Architecture:** Keep trace collection outside action selection. The episode loop records a step snapshot immediately after selecting an action and before `env.step`; the full eval wrapper writes the trace artifact and summary counts when enabled.

**Tech Stack:** Python, NumPy, pytest, Habitat official evaluator.

---

## Chunk 1: Trace Tests

### Task 1: Specify policy trace artifact behavior

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write failing artifact test**

Run `run_habitat_official_objectnav_eval` with `policy="memory_belief_frontier"`,
a detector that causes `approach_detector_target`, and `max_steps=2`.

Assert:

- `summary["artifact_files"]["policy_trace"] == "policy_trace.json"`;
- `summary["policy_trace"]["step_count"] == 2`;
- `policy_trace.json` has two steps;
- step 0 action is `move_forward`;
- step 0 `memory_prior.decision` is `approach_detector_target`.

- [x] **Step 2: Write failing budget-stop guard**

Using the same trace, assert step 1 action is `stop` and
`memory_prior.decision == "budget_stop"`.

- [x] **Step 3: Write failing disabled-trace test**

Run the same eval with `write_policy_trace=False` and assert no
`policy_trace.json`, no `artifact_files.policy_trace`, and no
`summary["policy_trace"]`.

- [x] **Step 4: Run RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_official_eval_writes_policy_step_trace_artifact \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_official_eval_skips_policy_step_trace_when_disabled -q
```

Expected: fail because `policy_trace.json` and `write_policy_trace` do not
exist.

## Chunk 2: Trace Implementation

### Task 2: Add compact trace collection

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Add public eval parameter**

Add `write_policy_trace: bool = True` to
`run_habitat_official_objectnav_eval(...)`.

- [x] **Step 2: Pass mutable trace list into episode loop**

Add `policy_trace: list[dict[str, Any]] | None = None` to
`run_official_objectnav_episode_loop(...)`.

- [x] **Step 3: Record one step after action selection**

Add a helper that appends compact records:

- episode metadata;
- `step_index`;
- `action`;
- corrected `x_m`, `z_m`, and `heading_rad`;
- copied `memory_prior` debug;
- occupancy counts and selected frontier bearing when available.

- [x] **Step 4: Guard budget STOP stale debug**

If `step_index >= max_steps - 1 and action == "stop"`, record
`memory_prior={"decision": "budget_stop"}` unless the action already came from
an actual policy STOP path.

- [x] **Step 5: Write artifact and summary**

Write `policy_trace.json` with:

- `task`;
- summary counts;
- `steps`.

Add `summary["artifact_files"]["policy_trace"]` and
`summary["policy_trace"]`.

- [x] **Step 6: Run GREEN**

Run the RED command again. Expected: pass.

## Chunk 3: Verification And Diagnostics

### Task 3: Verify and document

**Files:**
- Modify: `docs/design/2026-05-30-official-policy-step-trace.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Optionally create: `docs/experiments/2026-05-30-official-policy-step-trace-yolo-query-smoke.md`

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

- [x] **Step 3: Sync and run Linux focused verification**

Sync touched files to `/home/badger/Desktop/dual-anchor-lifelong-objectnav`,
then run the focused test command in conda env `habitat`.

- [x] **Step 4: Rerun diagnostic smoke**

Rerun the same four-episode YOLO query and inspect `policy_trace.json` against
`detector_trace.json`. Record whether target-match steps are consecutive,
interleaved with memory/frontier decisions, or dominated by one local action.

Result: implemented and verified. The live trace showed an explicit two-step
oscillation in the `tv_monitor` episode: detector centering turns right on
even steps, then blocked fallback turns left on odd steps.
