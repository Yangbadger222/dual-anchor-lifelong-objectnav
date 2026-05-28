# Habitat Memory-Lifecycle ObjectNav Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Habitat-backed lifecycle evaluation that measures whether remembered object verification poses reduce later ObjectNav query cost before fallback search.

**Architecture:** Add a focused evaluator module under `objectnav_core.evaluation` that reuses existing Habitat episode loading, detector evidence helpers, and geodesic path helpers. Keep planning and summary logic testable without importing Habitat by using small dataclasses and fake path costs in unit tests.

**Tech Stack:** Python 3.9-compatible `objectnav_core`, Habitat-Sim/Lab on Linux, Grounding-DINO adapter, CSV/JSON/HTML artifacts, pytest.

---

## Chunk 1: Testable Lifecycle Planner

### Task 1: Add lifecycle planning tests

**Files:**
- Create: `src/objectnav_core/tests/test_habitat_memory_lifecycle_objectnav.py`
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_lifecycle_objectnav.py`

- [ ] **Step 1: Write failing tests**

Write tests for:
- `plan_lifecycle_query()` chooses memory-first when the remembered pose is verified.
- failed memory verification falls back and includes both memory path and fallback path.
- `no_memory` skips memory path entirely.
- `naive_count` trusts only after two positive observations and ignores non-confirmation.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_memory_lifecycle_objectnav.py -q
```

Expected: tests fail because the module/API does not exist.

- [ ] **Step 3: Implement minimal planner**

Add dataclasses for lifecycle modes, verification outcome, plan result, and a pure `plan_lifecycle_query()`.

- [ ] **Step 4: Run tests to verify GREEN**

Run the same focused pytest command. Expected: all new tests pass.

## Chunk 2: Preflight, CLI, and Artifacts

### Task 2: Add preflight and CLI tests

**Files:**
- Modify: `src/objectnav_core/tests/test_cli_runner.py`
- Create/modify: `src/objectnav_core/objectnav_core/cli/run_habitat_memory_lifecycle_objectnav.py`
- Modify: `src/objectnav_core/setup.py`

- [ ] **Step 1: Write failing CLI/preflight tests**

Assert the CLI writes a `summary.json` with lifecycle task name, modes, detector config, noise levels, and geodesic scope warnings.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_memory_lifecycle_objectnav.py src/objectnav_core/tests/test_cli_runner.py -q
```

Expected: CLI import/entrypoint fails.

- [ ] **Step 3: Implement preflight and CLI**

Add `run_habitat_memory_lifecycle_preflight()` and CLI argument parsing. Add console script entrypoint.

- [ ] **Step 4: Run focused tests to verify GREEN**

Run the same focused pytest command. Expected: tests pass.

## Chunk 3: Habitat Runner Bridge

### Task 3: Add Linux-capable Habitat lifecycle runner

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_lifecycle_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_lifecycle_objectnav.py`

- [ ] **Step 1: Add tests around summary aggregation with fake lifecycle rows**

Ensure summaries include selected groups, per-mode success, path length, memory reuse, fallback count, and detector miss count.

- [ ] **Step 2: Run tests to verify RED**

Run the focused lifecycle tests.

- [ ] **Step 3: Implement real runner skeleton**

Use existing helpers from `habitat_objectnav_rgb_noise_stress.py` for detector masks, shortest paths, goal candidates, and evidence classification. The full runner should import Habitat lazily.

- [ ] **Step 4: Verify locally without Habitat**

Run focused lifecycle and CLI tests plus compile checks.

## Chunk 4: Docs and Linux Experiment

### Task 4: Record reports and run Linux smoke

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Create: `docs/experiments/2026-05-28-habitat-memory-lifecycle-objectnav.md`
- Create/update: `docs/handoff/2026-05-28-habitat-memory-lifecycle-objectnav.md`

- [ ] **Step 1: Run local verification**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_memory_lifecycle_objectnav.py src/objectnav_core/tests/test_cli_runner.py -q
python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
```

- [ ] **Step 2: Push branch**

Commit and push `codex/habitat-memory-lifecycle`.

- [ ] **Step 3: Run Linux smoke**

Run first with `oracle_bbox`, then Grounding-DINO if smoke passes.

- [ ] **Step 4: Update docs with exact metrics and risks**

Record commands, paths, pass/fail status, and what remains before paper-grade validation.
