# Official Local Action Candidate Score Report Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a JSON/CSV diagnostic report for candidate action rankings from a trained local action model.

**Architecture:** Add a pure report function and CSV writer to the existing local action model module, plus a thin CLI that loads dataset/model JSON and writes artifacts.

**Tech Stack:** Python stdlib, existing scorer, argparse, pytest.

---

## Chunk 1: Report Function

### Task 1: RED API report test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_model.py`

- [ ] **Step 1: Write failing test**

Use the existing hand-authored interaction model over low/high offset examples.
Assert best-action counts include both `move_forward` and `turn_left`.

- [ ] **Step 2: Run RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest -q \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py::test_official_local_action_model_candidate_score_report_summarizes_rankings
```

Expected: fail because the report function does not exist.

### Task 2: GREEN report function and CSV writer

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py`

- [ ] **Step 1: Implement report rows and aggregate counts**
- [ ] **Step 2: Implement CSV writer**
- [ ] **Step 3: Run RED test**

## Chunk 2: CLI

### Task 3: RED CLI report test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_model.py`

- [ ] **Step 1: Add CLI test**

Write synthetic dataset/model JSON, run CLI, assert JSON and CSV outputs.

- [ ] **Step 2: Run RED**

Expected: fail because CLI module does not exist.

### Task 4: GREEN CLI

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/score_habitat_official_local_action_model.py`

- [ ] **Step 1: Add parser and JSON loading**
- [ ] **Step 2: Call report function and CSV writer**
- [ ] **Step 3: Run model tests and focused official gate**
