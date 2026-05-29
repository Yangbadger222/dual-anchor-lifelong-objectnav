# Memory-Validity Learning Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one offline command that exports memory-validity data, trains a learned validity model, evaluates optional holdouts, and scores learned decisions.

**Architecture:** Create a small orchestration module in `objectnav_core.evaluation` that composes the existing exporter, trainer/evaluator, and scorer APIs. Add a CLI wrapper that writes deterministic JSON/CSV artifacts into an output directory.

**Tech Stack:** Python standard library, existing pytest suite, existing `objectnav_core` CLI/module layout.

---

## Chunk 1: Pipeline API

### Task 1: API Orchestration

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_pipeline.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_pipeline.py`

- [ ] **Step 1: Write failing pipeline API test**

Create a synthetic summary file with four memory-guided rows. Call `run_memory_validity_learning_pipeline(...)` with a category holdout and assert it writes `dataset.json`, `examples.csv`, `model.json`, `scores.json`, `scores.csv`, and `pipeline_report.json`.

- [ ] **Step 2: Run focused test and verify RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_memory_validity_pipeline.py -q
```

Expected: fail because the pipeline module does not exist.

- [ ] **Step 3: Implement pipeline API**

Compose the exporter, trainer, optional split/evaluation helpers, scorer, and CSV writers. Return the pipeline report.

## Chunk 2: CLI

### Task 2: CLI Wrapper

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/run_habitat_memory_validity_learning_pipeline.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_pipeline.py`

- [ ] **Step 1: Write failing CLI test**

Invoke `main([...])` with the synthetic summary and assert `pipeline_report.json` contains artifact paths and holdout metrics.

- [ ] **Step 2: Run focused test and verify RED**

Expected: fail because the CLI module does not exist.

- [ ] **Step 3: Implement CLI**

Parse input paths, `--output-dir`, `--policies`, `--features`, training parameters, and optional holdout flags. Print the pipeline report and return `0`.

## Chunk 3: Documentation and Verification

### Task 3: Research Trace

**Files:**
- Modify: `docs/design/2026-05-30-memory-validity-learning-pipeline.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Mark design implemented locally**

Record local implementation and Linux pending state.

- [ ] **Step 2: Add devlog entry**

Record files changed, reason, verification, and remaining risk.

- [ ] **Step 3: Update handoff**

Document the one-command Linux workflow.

### Task 4: Verification

- [ ] **Step 1: Focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_memory_validity_pipeline.py src/objectnav_core/tests/test_habitat_memory_validity_model.py src/objectnav_core/tests/test_habitat_memory_validity_dataset.py -q
```

- [ ] **Step 2: Compile touched modules**

```bash
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_pipeline.py src/objectnav_core/objectnav_core/cli/run_habitat_memory_validity_learning_pipeline.py
```

- [ ] **Step 3: Full local suite**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
```

- [ ] **Step 4: Whitespace check**

```bash
git diff --check
```
