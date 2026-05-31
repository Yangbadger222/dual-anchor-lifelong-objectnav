# Official Learned Local Frontier Policy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a separate official ObjectNav policy variant that uses a persisted local action-effect scorer for detector-local action selection.

**Architecture:** Extend official evaluator config/manifest/CLI with a local action model path, load the model into policy state, and add `memory_learned_local_frontier` as an ablation policy that reuses memory-evidence search but scores detector-local candidate actions with the learned model.

**Tech Stack:** Python, existing official ObjectNav evaluator, existing local action model API, pytest.

---

## Chunk 1: Registration and Preflight

### Task 1: Policy/Manifest Tests

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write failing registration/preflight test**

Assert `memory_learned_local_frontier` is supported, requires memory prior plus
local action model, and writes model metadata to `protocol_manifest.json`.

- [ ] **Step 2: Run test to verify RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_learned_local_frontier_policy_records_model_boundary -q
```

- [ ] **Step 3: Implement config/manifest validation**

Add `local_action_model_path` to config, preflight/eval APIs, manifest, and
validation.

- [ ] **Step 4: Run test to verify GREEN**

Run the same test.

## Chunk 2: CLI and Behavior

### Task 2: CLI and Learned Action Selection

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write failing CLI test**

Assert `--local-action-model-path` is accepted for learned-local preflight.

- [ ] **Step 2: Write failing behavior test**

Use a synthetic model that scores `turn_left` above `move_forward`, then assert
the learned policy chooses `turn_left` after failed center/reacquire where
`memory_evidence_frontier` would move forward.

- [ ] **Step 3: Implement CLI and learned policy selection**

Load model once, store in `OfficialPolicyState`, construct action-score
examples from detector evidence, score candidates, and record debug.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run evaluator and CLI focused tests.

## Chunk 3: Verification and Experiment

### Task 3: Local/Linux Checks and YOLO Smoke

**Files:**
- Create: `docs/experiments/2026-05-30-official-learned-local-frontier-yolo-query-smoke.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Run local verification**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest <focused official tests> -q
python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

- [ ] **Step 2: Run Linux verification**

Copy the slice to Linux and run the same focused tests in conda env `habitat`.

- [ ] **Step 3: Run four-episode YOLO query smoke**

Compare `memory_learned_local_frontier` with the existing
`memory_evidence_frontier` artifact using official Habitat metrics only.

- [ ] **Step 4: Update docs**

Record changed files, commands, metrics, trace observations, and limitations.
