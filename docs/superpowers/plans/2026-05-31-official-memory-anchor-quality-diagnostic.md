# Official Memory Anchor Quality Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline report that compares candidate official memory anchors against a reference prior and identifies localization, ranking, and coverage failures.

**Architecture:** Add one focused evaluation module plus one thin CLI. The module owns loading priors, grouping by `(episode_id, object_category)`, computing selected and nearest anchor errors, and writing JSON/CSV/Markdown artifacts.

**Tech Stack:** Python standard library, existing `OfficialMemoryAnchor`, existing official memory-prior loader, pytest.

---

## Chunk 1: Prior Quality Report

### Task 1: Report Module

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_anchor_quality.py`
- Test: `src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py`

- [ ] **Step 1: Write failing tests**

Cover candidate selection by confidence, nearest-candidate error, nearest rank, missing candidate coverage, and artifact writing.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py -q
```

Expected: fail because the module does not exist.

- [ ] **Step 3: Implement minimal report code**

Load candidate/reference priors, group by episode/category, compute x/z errors, write JSON/CSV/Markdown.

- [ ] **Step 4: Run tests to verify GREEN**

Run the same focused pytest command.

### Task 2: CLI and Packaging

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/report_habitat_official_memory_anchor_quality.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`
- Test: `src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py`

- [ ] **Step 1: Write failing CLI/packaging assertions**

Assert the CLI forwards paths/threshold and setup exposes
`objectnav_habitat_official_memory_anchor_quality`.

- [ ] **Step 2: Run focused tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py src/objectnav_core/tests/test_ros_packaging.py -q
```

Expected: CLI module or console script assertion fails.

- [ ] **Step 3: Implement minimal CLI and entry point**

Parse `--candidate-prior`, `--reference-prior`, `--output-dir`, and
`--max-good-error-m`; print the returned summary JSON.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run the same focused pytest command.

### Task 3: Verification and Documentation

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Create or modify: `docs/experiments/2026-05-31-official-memory-anchor-quality-diagnostic.md`
- Modify: `docs/handoff/2026-05-31-official-detector-positive-viewpoint-memory-prior.md`

- [ ] **Step 1: Run local verification**

Run focused tests, compileall, and `git diff --check`.

- [ ] **Step 2: Run remote artifact diagnostic**

Sync touched files to Linux, run focused tests there, then run the CLI against
the opportunistic alias prior and a reference prior.

- [ ] **Step 3: Record evidence**

Update devlog, experiment report, and handoff with commands, metrics, and
remaining risks.
