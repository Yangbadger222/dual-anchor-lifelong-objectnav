# Closed-Loop Dual-Anchor Grid Benchmark Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first closed-loop dual-session benchmark slice that executes memory-vs-frontier decisions with frame drift, Mahalanobis matching, ambiguity rejection, and natural stale relocation in a deterministic grid before wiring the same interfaces into Habitat.

**Architecture:** Add a small Habitat-independent runner under `objectnav_core.evaluation` with its own CLI. It reuses existing grid navigation, frontier extraction, `select_memory_guided_candidate`, and `geometry.dual_anchor`; it writes `summary.json` and traces so the later Habitat runner can match the same schema.

**Tech Stack:** Python, existing `objectnav_core` grid/navigation/planning models, pytest, JSON artifacts.

---

## Chunk 1: Benchmark Core

### Task 1: Failing tests for dual-session closed loop

**Files:**
- Create: `src/objectnav_core/tests/test_closed_loop_dual_anchor_benchmark.py`

- [ ] Write tests that import `run_closed_loop_dual_anchor_benchmark` and assert:
  - summary task is `closed_loop_dual_anchor_grid_benchmark`;
  - policies include `memory_guided`, `frontier_only`, and `naive_count`;
  - `session_2_reuse` for memory-guided selects a memory candidate and records an accepted match;
  - `session_2_ambiguous` for memory-guided selects frontier and records an ambiguous match;
  - `session_2_stale_repair` records stale repair/relocation and eventually succeeds;
  - memory-guided uses less path than frontier-only on the reuse case.

- [ ] Run:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_closed_loop_dual_anchor_benchmark.py -q`
  Expected: fail because module does not exist.

### Task 2: Minimal runner implementation

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/closed_loop_dual_anchor_benchmark.py`

- [ ] Implement deterministic scenarios:
  - session 1 discover stores `plant_001` in frame `map_session_1`;
  - session 2 uses a `FrameTransform2D` to project that memory into `map_session_2`;
  - observed candidates produce accepted / ambiguous / outside-gate evidence;
  - candidate selection is closed-loop at option level: choose memory or frontier, navigate, observe, verify/mark missing/repair.

- [ ] Use existing `TrialMetrics` where practical, plus per-episode rows containing `selected_candidate_types`, `matching_reason`, `match_distances`, `frame_transform`, `stale_repair_recorded`, and `path_length_m`.

- [ ] Write `summary.json` with policy aggregates and comparisons.

- [ ] Run the focused test and make it pass.

## Chunk 2: CLI and Artifact

### Task 3: Failing CLI test

**Files:**
- Create: `src/objectnav_core/tests/test_closed_loop_dual_anchor_cli.py`
- Create: `src/objectnav_core/objectnav_core/cli/run_closed_loop_dual_anchor_benchmark.py`

- [ ] Write CLI test invoking `main(["--output", str(tmp_path)])` and checking `summary.json` exists and has the expected task.
- [ ] Run focused CLI test; expected failure before implementation.

### Task 4: CLI implementation

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/run_closed_loop_dual_anchor_benchmark.py`

- [ ] Add argparse with required `--output`, optional `--gate-threshold`, optional `--ambiguity-margin`.
- [ ] Call `run_closed_loop_dual_anchor_benchmark` and return `0`.
- [ ] Run focused benchmark/CLI tests.

## Chunk 3: Documentation and Verification

### Task 5: Docs

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Create: `docs/experiments/2026-05-29-closed-loop-dual-anchor-grid-smoke.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] Record files changed, reason, verification, limitations.
- [ ] Make clear this is a grid closed-loop algorithm harness, not Habitat SPL.

### Task 6: Verification, commit, Linux smoke

- [ ] Run:
  `git diff --check`
- [ ] Run:
  `python -m py_compile src/objectnav_core/objectnav_core/evaluation/closed_loop_dual_anchor_benchmark.py src/objectnav_core/objectnav_core/cli/run_closed_loop_dual_anchor_benchmark.py`
- [ ] Run focused tests:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_closed_loop_dual_anchor_benchmark.py src/objectnav_core/tests/test_closed_loop_dual_anchor_cli.py -q`
- [ ] Run full local core tests:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q`
- [ ] Run CLI smoke:
  `PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_closed_loop_dual_anchor_benchmark --output /tmp/closed_loop_dual_anchor_grid_smoke`
- [ ] Commit and push.
- [ ] SSH Linux, pull, run focused tests and CLI smoke in `conda habitat`.
