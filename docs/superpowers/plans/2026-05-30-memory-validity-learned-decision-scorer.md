# Memory-Validity Learned Decision Scorer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an offline scorer that applies learned validity probabilities to exported Habitat rows and reports learned memory-vs-frontier decisions.

**Architecture:** Extend `objectnav_core.evaluation.habitat_memory_validity_model` with a scoring API that consumes the existing dataset/model JSON structures. Add a CLI beside the trainer CLI for JSON/CSV output, with no online runner integration.

**Tech Stack:** Python standard library, existing pytest suite, existing `objectnav_core` CLI/module layout.

---

## Chunk 1: Scoring API

### Task 1: Learned Decision Rows

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_model.py`

- [ ] **Step 1: Write failing test for learned memory/frontier decisions**

Add a test that builds a deterministic model and two dataset examples. One row should have high predicted validity and choose `memory_first`; one row should have low predicted validity and choose `frontier_first`.

- [ ] **Step 2: Run focused test and verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_memory_validity_model.py -q
```

Expected: fail because `score_memory_validity_decisions` does not exist.

- [ ] **Step 3: Implement scoring API**

Implement `score_memory_validity_decisions(dataset, model)` with per-row predicted probability, expected memory-first action count, expected frontier-first action count, learned decision, raw/clamped decision boundary, boundary region, and optional flip against `aux_memory_decision`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the focused model test file again.

### Task 2: CSV Writer

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_model.py`

- [ ] **Step 1: Write failing test for CSV output**

Add a test that writes scored rows to CSV and asserts key fields appear.

- [ ] **Step 2: Implement `write_memory_validity_decision_scores_csv`**

Use a stable field list and existing style from dataset exporter CSV helpers.

## Chunk 2: CLI

### Task 3: Score CLI

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/score_habitat_memory_validity_model.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_model.py`

- [ ] **Step 1: Write failing CLI test**

Write dataset/model JSON files, call `main([dataset, "--model", model, "--output", scores, "--csv-output", csv])`, and assert JSON/CSV outputs exist with aggregate counts.

- [ ] **Step 2: Run focused test and verify RED**

Expected: fail because the CLI does not exist.

- [ ] **Step 3: Implement CLI**

Load JSON files, call scorer, write sorted/indented JSON, optionally write CSV, print report, and return `0`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the focused model test file again.

## Chunk 3: Documentation and Verification

### Task 4: Research Trace

**Files:**
- Modify: `docs/design/2026-05-30-memory-validity-learned-decision-scorer.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Mark design implemented locally**

Record that Linux artifact scoring is still pending.

- [ ] **Step 2: Add devlog entry**

Record changed files, reason, verification, and remaining risk.

- [ ] **Step 3: Update handoff**

Document scorer API/CLI and the exact next Linux command shape.

### Task 5: Verification

- [ ] **Step 1: Focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_memory_validity_model.py src/objectnav_core/tests/test_habitat_memory_validity_dataset.py -q
```

- [ ] **Step 2: Compile touched modules**

```bash
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py src/objectnav_core/objectnav_core/cli/train_habitat_memory_validity_model.py src/objectnav_core/objectnav_core/cli/score_habitat_memory_validity_model.py
```

- [ ] **Step 3: Full local core suite**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
```

- [ ] **Step 4: Whitespace check**

```bash
git diff --check
```
