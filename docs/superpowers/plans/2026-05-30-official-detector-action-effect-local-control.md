# Official Detector Action-Effect Local Control Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an official `memory_evidence_frontier` policy variant that uses recent detector action-effect evidence to suppress centering turns that immediately lose target detections.

**Architecture:** Keep official metrics and action space unchanged. Reuse `memory_belief_frontier` for memory-conditioned frontier selection, but add a detector-local-control path that records failed centering turns and edge-tracks forward when repeating the same turn would likely recreate the loss/reacquire loop.

**Tech Stack:** Python, pytest, Habitat official ObjectNav evaluator, YOLO detector adapter injection, JSON trace artifacts.

---

## File Structure

- Modify `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
  - Register `memory_evidence_frontier`.
  - Add per-episode failed detector centering action-effect state.
  - Add a detector local-control selector for the new policy.
  - Reuse memory-belief frontier fallback when detector evidence is absent.
- Modify `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
  - No new flags expected; policy registration should make the existing `--policy` choices include the new policy.
- Modify `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
  - Add RED/GREEN behavior tests for policy registration and action-effect local control.
- Modify `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
  - Add CLI/preflight manifest coverage for the new policy.
- Update docs:
  - `docs/design/2026-05-30-official-detector-action-effect-local-control.md`
  - `docs/devlog/2026-05.md`
  - `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
  - new experiment report after live smoke

## Task 1: Register The Policy

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write the failing evaluator registration test**

Add a test that creates a `OfficialObjectNavRunConfig` with
`policy="memory_evidence_frontier"`, calls `make_protocol_manifest(...)`, and
expects:

```python
assert "memory_evidence_frontier" in SUPPORTED_OFFICIAL_POLICIES
assert manifest["policy_kind"] == "memory_evidence_frontier_active_search"
assert manifest["invalid_for_benchmark_claim_reason"] == (
    "memory_prior_source_not_benchmark_validated"
)
```

- [ ] **Step 2: Write the failing CLI preflight test**

Call the CLI with `--policy memory_evidence_frontier`, an empty memory prior,
and `--preflight-only`. Expect `summary.json` and `protocol_manifest.json` to
record the policy and policy kind.

- [ ] **Step 3: Run RED tests**

Run:

```bash
pytest -q \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_evidence_frontier_policy_is_registered_with_memory_boundary \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py::test_official_objectnav_cli_preflight_accepts_memory_evidence_frontier
```

Expected: FAIL because the policy is not supported.

- [ ] **Step 4: Implement minimal registration**

Add the policy to `SUPPORTED_OFFICIAL_POLICIES`, `_policy_kind(...)`, manifest
invalid-reason memory-policy handling, and `_select_policy_action(...)` branch.
The first branch can delegate to `_select_memory_belief_frontier_action(...)`
until Task 2 adds distinct behavior.

- [ ] **Step 5: Run GREEN registration tests**

Run the two targeted tests and confirm they pass.

## Task 2: Add Action-Effect Detector Local Control

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write the failing action-effect test**

Use `_SequenceDetector` with:

1. a right-edge target detection;
2. no target detection;
3. the same right-edge target detection.

Run `policy="memory_evidence_frontier"` with clear depth and a matching memory
anchor. Expect:

```python
assert trace["steps"][0]["action"] == "turn_right"
assert trace["steps"][1]["action"] == "turn_left"
assert trace["steps"][2]["action"] == "move_forward"
assert trace["steps"][2]["memory_prior"]["decision"] == (
    "approach_detector_target_after_center_loss"
)
assert trace["steps"][2]["memory_prior"]["suppressed_detector_center_action"] == (
    "turn_right"
)
```

- [ ] **Step 2: Run RED action-effect test**

Expected: FAIL because the new policy still repeats centering after
reacquisition.

- [ ] **Step 3: Implement minimal state**

Add per-episode state fields:

```python
failed_detector_center_effects: set[tuple[str, int]]
last_detector_center_offset_sign: int | None
last_detector_center_failed: bool
```

On immediate target loss after centering, record
`(last_detector_center_action, last_detector_center_offset_sign)`.

- [ ] **Step 4: Implement edge-tracking suppression**

For `memory_evidence_frontier`, when a target is off-center and the nominal
centering action plus current offset sign has a recorded failed effect, choose
`move_forward` if `_center_depth_is_clear(...)`; record debug fields:

```python
decision = "approach_detector_target_after_center_loss"
suppressed_detector_center_action = action
detector_center_offset_sign = offset_sign
failed_detector_center_effect_count = ...
```

If forward is not clear, fall back to the existing blocked detector target
behavior.

- [ ] **Step 5: Run GREEN action-effect test**

Run the targeted test and confirm it passes.

## Task 3: Preserve Existing Behavior

**Files:**
- Modify only if tests expose regressions:
  `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [ ] **Step 1: Run focused official evaluator tests**

```bash
pytest -q src/objectnav_core/tests/test_habitat_official_objectnav_eval.py
```

Expected: all tests pass, including existing `memory_belief_frontier`
adaptive-servo and sign-ablation tests.

- [ ] **Step 2: Run local focused official-memory set**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core pytest -q \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
  src/objectnav_core/tests/test_ros_packaging.py
```

## Task 4: Linux Habitat Verification And Smoke

**Files:**
- Update docs after results.

- [ ] **Step 1: Sync touched files to Linux mirror**

Use `rsync -avR` for the touched evaluator, CLI/test files, design, plan, and
docs. Avoid root-level basename sync.

- [ ] **Step 2: Run Linux focused tests**

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_ros_packaging.py -q'
```

- [ ] **Step 3: Run compile and whitespace checks locally and on Linux**

Run `python -m compileall -q ...` and `git diff --check` in both environments.

- [ ] **Step 4: Run YOLO diagnostic**

Run the same four-episode diagnostic as previous smokes, changing only:

```python
policy="memory_evidence_frontier"
```

Use output:

```text
runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1
```

Compare against adaptive-servo and inverted-sign artifacts.

## Task 5: Documentation Trail

**Files:**
- Modify: `docs/design/2026-05-30-official-detector-action-effect-local-control.md`
- Add: `docs/experiments/2026-05-30-official-detector-action-effect-local-control-yolo-query-smoke.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Update design verification result**

Record RED/GREEN tests, local/Linux verification, and live-smoke metrics.

- [ ] **Step 2: Add experiment report**

Include command, artifact paths, official metrics, detector trace counts, policy
trace decision counts, and a clear negative/positive conclusion.

- [ ] **Step 3: Add devlog entry**

Include files changed, reason, verification, effect, and follow-up.

- [ ] **Step 4: Update handoff**

Record current state, commands run, what passed, what failed, risks, and next
recommended action.
