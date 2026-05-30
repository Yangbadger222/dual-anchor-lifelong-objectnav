# Habitat Learned Memory Validity Online Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Habitat runner option that applies a trained memory-validity model to online memory-vs-frontier decisions.

**Architecture:** The runner keeps the current reliability modes as base estimators. When a model JSON is supplied, it builds an exporter-compatible pre-decision feature dictionary, predicts memory validity with the existing logistic model helper, replaces the expected-utility probability, and records both learned and base reliability in the row payload.

**Tech Stack:** Python, pytest, existing `objectnav_core` Habitat runner and memory-validity model modules.

---

### Task 1: Model Override Helper

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [x] **Step 1: Write the failing test**

Add a test that creates a tiny model dict with a strong negative bias, passes a positive base reliability estimate plus memory evidence into a learned helper, and asserts the output mode is `learned_model`, the value is near zero, and the base estimate is preserved in components.

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_learned_memory_validity_model_overrides_base_reliability -q
```

Expected: failure because the helper does not exist yet.

- [x] **Step 3: Implement minimal helper**

Import `predict_memory_validity`, build features from memory route counts,
current memory evidence, base reliability components, and optional relocation
distance, then return a `MemoryReliabilityEstimate` with mode `learned_model`.

- [x] **Step 4: Verify focused test passes**

Run the same focused pytest command and expect `1 passed`.

### Task 2: Runner and CLI Wiring

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py`

- [x] **Step 1: Write failing CLI/API tests**

Add coverage that `--memory-validity-model` is accepted by preflight and that
the summary records the model path.

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py::test_habitat_closed_loop_cli_preflight_accepts_memory_validity_model -q
```

Expected: parser rejects the unknown argument.

- [x] **Step 3: Add CLI/API parameter**

Thread `memory_validity_model_path` through preflight and full runner calls,
load JSON once, apply the helper after base reliability estimation, and include
the path in summary metadata.

- [x] **Step 4: Verify focused tests pass**

Run the focused CLI test and the helper test.

### Task 3: Verification and Linux Replay

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-30-habitat-learned-memory-validity-online-replay.md`

- [x] **Step 1: Run local verification**

Run focused Habitat/CLI tests, model/pipeline tests, `py_compile`, full core
tests, and `git diff --check`.

- [x] **Step 2: Push and rerun on Linux**

Pull the branch on Linux and run the selected relocated `sofa` group with
`--memory-validity-model` pointing at the evidence-only pipeline model.

- [x] **Step 3: Document result**

Record whether the learned online run changes `memory_decision` from
`memory_first` to `frontier_first`, plus all limitations.
