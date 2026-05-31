# Official Ranker-Guided Active Perception Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the learned candidate-viewpoint ranker into the official online `memory_active_perception_frontier` policy as an optional, auditable candidate reranker.

**Architecture:** Load a JSON candidate-viewpoint ranker model through the official evaluator config, attach it to `OfficialPolicyState`, and let `_select_memory_active_perception_frontier(...)` rerank already-computed online candidate viewpoints. Preserve existing hand-score behavior when no ranker model is supplied.

**Tech Stack:** Python, deterministic JSON model artifact, existing Habitat official evaluator, pytest, no online oracle/teleport labels.

---

## File Structure

- Modify `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
  - model loading/validation
  - config/manifest plumbing
  - policy-state model storage
  - online candidate feature row + reranking
- Modify `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
  - CLI flag and runner kwarg
- Modify `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
  - RED/GREEN selector and episode-loop tests
- Modify `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
  - CLI/preflight plumbing test
- Modify `docs/devlog/2026-05.md`
  - final task entry after verification
- Modify `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
  - handoff state and next action
- Create `docs/experiments/2026-05-31-official-ranker-guided-active-perception.md`
  - local/Linux verification and smoke results

## Chunk 1: Model Loading And Config Plumbing

### Task 1: Add ranker model loader and manifest field

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write the failing loader test**

Add a test that imports `load_official_candidate_viewpoint_ranker_model`, writes
a valid minimal model JSON, asserts it loads, then writes a wrong-task JSON and
asserts `ValueError`.

- [ ] **Step 2: Run RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_candidate_viewpoint_ranker_model_loader_validates_task -q
```

Expected: fail because the loader does not exist.

- [ ] **Step 3: Implement the loader**

Add `load_official_candidate_viewpoint_ranker_model(path)` that reads a JSON
object, requires `task == "habitat_official_candidate_viewpoint_ranker_model"`,
and requires a list-valued `feature_names`.

- [ ] **Step 4: Run GREEN**

Run the same focused test. Expected: pass.

### Task 2: Thread model path through config, preflight, eval, and CLI

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`

- [ ] **Step 1: Write the failing CLI plumbing test**

Use the CLI test runner injection to pass
`--candidate-viewpoint-ranker-model-path ranker.json` and assert the runner gets
`candidate_viewpoint_ranker_model_path="ranker.json"`.

- [ ] **Step 2: Run RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py::test_official_objectnav_cli_passes_candidate_viewpoint_ranker_model_path -q
```

Expected: fail because the CLI flag is unsupported.

- [ ] **Step 3: Implement config/CLI plumbing**

Add `candidate_viewpoint_ranker_model_path` to `OfficialObjectNavRunConfig`,
preflight/eval signatures, config creation, validation, manifest, CLI parser,
and CLI `kwargs`.

- [ ] **Step 4: Run GREEN**

Run the same focused CLI test. Expected: pass.

## Chunk 2: Online Candidate Reranking

### Task 3: Preserve hand-score behavior when no model is supplied

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write the no-model preservation test**

Call `_select_memory_active_perception_frontier(...)` on a synthetic map and
assert the selected candidate remains the existing hand-score winner and has no
`ranker_prediction`.

- [ ] **Step 2: Run RED/GREEN**

If this passes immediately, keep it as a characterization test. It protects the
baseline path before adding model behavior.

### Task 4: Add model-backed candidate reranking

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write the failing rerank test**

Create a synthetic ranker model whose feature list contains `candidate_rank` and
whose weight prefers rank `1` over rank `0`. Call
`_select_memory_active_perception_frontier(..., candidate_viewpoint_ranker_model=model)`
and assert the selected candidate changes, `ranker_prediction` is present, and
`ranker_selected_candidate_rank` is recorded.

- [ ] **Step 2: Run RED**

Run the new focused test. Expected: fail because the selector does not accept a
model.

- [ ] **Step 3: Implement minimal reranking**

Import `predict_official_candidate_viewpoint_ranker`, build an online candidate
row from pre-label candidate fields, set `candidate_rank`, `candidate_count`,
`candidate_score`, `target_category`, and any available state features, compute
prediction per candidate, and sort by `(ranker_prediction, score,
expected_evidence, -travel_distance_m)`.

- [ ] **Step 4: Run GREEN**

Run the new focused selector test. Expected: pass.

### Task 5: Thread model through episode state

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write the failing episode-loop test**

Run `run_official_objectnav_episode_loop(...)` with
`policy="memory_active_perception_frontier"` and a synthetic model. Assert
`policy_debug.memory_prior` contains `candidate_viewpoint_ranker_model` and
`ranker_prediction`.

- [ ] **Step 2: Run RED**

Expected: fail because episode state cannot receive the model yet.

- [ ] **Step 3: Implement state plumbing**

Add `candidate_viewpoint_ranker_model` to `OfficialPolicyState`, pass the loaded
model through `run_official_objectnav_episode_loop`, and pass it into
`_select_memory_active_perception_frontier(...)`.

- [ ] **Step 4: Run GREEN**

Run the focused episode-loop test. Expected: pass.

## Chunk 3: Verification And Research Trail

### Task 6: Run verification gates

**Files:**
- No production edits unless failures reveal a bug.

- [ ] Run focused official evaluator/CLI tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q
```

- [ ] Run full local suite:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
```

- [ ] Run compile/hygiene:

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

### Task 7: Linux focused verification and smoke

**Files:**
- Create: `docs/experiments/2026-05-31-official-ranker-guided-active-perception.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] Run Linux focused tests in conda env `habitat`.
- [ ] If focused tests pass, run a small official Habitat/Yolo smoke using the
      source-diverse v2 ranker model.
- [ ] Compare against the prior hand-score active-perception smoke. Record
      official metrics, detector trace counts, policy trace decision counts, and
      whether the ranker changed selected candidate ranks.
- [ ] Update experiment report, devlog, and handoff with commands, outcomes,
      risks, and next action.
