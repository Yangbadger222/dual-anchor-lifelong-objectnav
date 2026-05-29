# Habitat Decision Sensitivity Miner Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pure-Python offline miner that ranks existing Habitat closed-loop `summary.json` rows by memory-vs-frontier decision sensitivity.

**Architecture:** Add a focused analyzer module that reads summary artifacts, recomputes fixed/evidence/event-posterior expected-utility counterfactuals from saved row fields, and writes a ranked JSON/CSV report. Add a thin CLI wrapper; do not modify the Habitat runtime policy.

**Tech Stack:** Python standard library, `objectnav_core`, pytest.

---

### Task 1: Analyzer Unit Tests

**Files:**
- Create: `src/objectnav_core/tests/test_habitat_decision_sensitivity.py`
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_decision_sensitivity.py`

- [x] **Step 1: Write a failing close-row ranking test**

  Create a synthetic `summary.json` with a `memory_guided`
  `event_posterior` row whose expected memory-first cost is within five
  actions of frontier-first and whose detector event components are mixed.
  Assert the miner returns one candidate with the expected category, margin,
  event count, evidence decision, event-posterior decision, and sensitivity
  reasons.

- [x] **Step 2: Run the test to verify it fails**

  Run:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py::test_miner_ranks_close_mixed_event_rows -q`

  Expected: fail because `objectnav_core.evaluation.habitat_decision_sensitivity`
  does not exist.

- [x] **Step 3: Write a failing counterfactual flip test**

  Add a synthetic row where evidence reliability chooses memory-first but the
  event posterior chooses frontier-first. Assert
  `counterfactual_decision_flip` is true and the row ranks ahead of a merely
  close non-flip row.

- [x] **Step 4: Run the flip test to verify it fails**

  Run:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py::test_miner_marks_evidence_to_event_posterior_decision_flips -q`

  Expected: fail because the analyzer is not implemented.

### Task 2: Analyzer Implementation

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_decision_sensitivity.py`
- Test: `src/objectnav_core/tests/test_habitat_decision_sensitivity.py`

- [x] **Step 1: Add path discovery and summary loading**

  Implement recursive `summary.json` discovery for directories and direct file
  input for explicit JSON paths.

- [x] **Step 2: Add expected-utility helpers**

  Implement:
  - `expected_memory_first = memory + (1 - reliability) * fallback_from_memory`
  - `memory_first` if expected memory-first cost is less than or equal to
    frontier-first cost;
  - decision-boundary reliability for row diagnostics.

- [x] **Step 3: Add reliability counterfactual helpers**

  Recompute evidence-style reliability from saved components using the same
  non-oracle component formula as the runtime. Recompute event-posterior
  reliability from saved detector-event posterior components and preserve the
  matching/current-evidence safety limits.

- [x] **Step 4: Add candidate scoring**

  Include a row when it is close to the decision boundary, has a
  counterfactual flip, has hindsight regret, or has enough detector-event
  signal and reliability delta. Score flips highest, then close rows with large
  reliability deltas and mixed confirmed/suppressed evidence.

- [x] **Step 4a: Add boundary-region diagnostics**

  After broad mining showed that cost-close rows may still be impossible to
  flip, add unclamped decision-boundary reliability and boundary-region fields
  so reports distinguish genuinely reliability-sensitive rows from rows where
  memory or frontier dominates for every valid reliability estimate.

- [x] **Step 5: Run analyzer tests to green**

  Run:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py -q`

### Task 3: CLI and Output Tests

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/mine_habitat_decision_sensitivity.py`
- Modify: `src/objectnav_core/tests/test_habitat_decision_sensitivity.py`

- [x] **Step 1: Write a failing CLI output test**

  Call the CLI `main(...)` with an input directory, `--output`, and
  `--csv-output`. Assert both files are written and contain the expected
  candidate count.

- [x] **Step 2: Run the CLI test to verify it fails**

  Run:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py::test_decision_sensitivity_cli_writes_json_and_csv -q`

  Expected: fail because the CLI module does not exist.

- [x] **Step 3: Implement the CLI**

  Add positional inputs and options:
  - `--output`
  - `--csv-output`
  - `--top-k`
  - `--max-margin-actions`
  - `--min-detector-event-count`
  - `--min-reliability-delta`
  - `--policies`

- [x] **Step 4: Run CLI tests to green**

  Run the command from Step 2 and then the full analyzer test file.

### Task 4: Documentation and Verification

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] **Step 1: Update devlog and handoff**

  Record the new analyzer, files changed, reason, verification commands, and
  the next experiment-selection action.

- [x] **Step 2: Run focused verification**

  Run:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py -q`

- [x] **Step 3: Run integration-adjacent verification**

  Run:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q`

- [x] **Step 4: Run syntax and whitespace checks**

  Run:
  `python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_decision_sensitivity.py src/objectnav_core/objectnav_core/cli/mine_habitat_decision_sensitivity.py`

  Then run:
  `git diff --check`

- [x] **Step 5: Optional artifact smoke**

  If summary artifacts are available locally or through an approved Linux
  command, run the CLI on existing balanced3 event-posterior summaries and
  inspect the top candidates. Record this as analysis smoke, not benchmark
  evidence.
