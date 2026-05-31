# Official Oracle Memory Prior Upper Bound Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export privileged Habitat goal/viewpoint anchors as official memory-prior JSON and route them through the existing memory backend path.

**Architecture:** Extend `OfficialMemoryAnchor` with optional `episode_id`, prefer episode-specific anchors during selection, add a small oracle-memory exporter module plus CLI, and mark oracle priors diagnostic-only in the protocol manifest.

**Tech Stack:** Python, Habitat official evaluator helpers, pytest, JSON artifacts.

---

## Chunk 1: Anchor Schema and Selection

### Task 1: Episode-Specific Anchor Metadata

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/official_episode_memory.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_official_episode_memory.py`

- [x] **Step 1: Write failing tests**

Add tests that load `episode_id` from a memory-prior payload, round-trip it
through payload serialization, and prefer an exact episode-specific anchor over
a generic same-scene/category anchor.

- [x] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_select_official_memory_anchor_prefers_exact_episode_anchor \
  src/objectnav_core/tests/test_official_episode_memory.py::test_official_memory_prior_payload_round_trips_episode_id -q
```

Expected: fail because `episode_id` is not parsed or emitted yet.

- [x] **Step 3: Implement schema support**

Add `episode_id: str | None = None` to `OfficialMemoryAnchor`, parse it from
JSON, include it in debug/TargetNav/payload helpers, and pass
`state.episode_id` into memory selection.

- [x] **Step 4: Verify GREEN**

Run the same focused tests. Expected: pass.

## Chunk 2: Oracle Exporter

### Task 2: Perfect Habitat Memory Prior Export

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_oracle_memory_prior.py`
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_oracle_memory_prior.py`
- Modify: `src/objectnav_core/setup.py`
- Test: `src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py`

- [x] **Step 1: Write failing tests**

Add tests for converting a Habitat world goal into episode-relative `x/z`, fake
env export metadata, skipped-episode accounting, and CLI writing JSON.

- [x] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py -q
```

Expected: fail because module/CLI do not exist.

- [x] **Step 3: Implement minimal exporter**

Iterate episodes with the official env config, select nearest episode
goal/viewpoint when possible, convert into `episode_start_relative`, write JSON
with `metadata.source=habitat_official_oracle_memory_prior` and
`source_validity=oracle_diagnostic_only`, then validate with
`load_official_memory_prior`.

- [x] **Step 4: Verify GREEN**

Run the same exporter tests. Expected: pass.

## Chunk 3: Manifest and Documentation

### Task 3: Diagnostic Boundary

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Modify: `docs/design/2026-05-31-official-oracle-memory-prior-upper-bound.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-31-official-oracle-memory-prior-upper-bound-smoke.md`

- [x] **Step 1: Write failing manifest test**

Add a test that a memory-prior JSON with oracle metadata appears in the
protocol manifest as `source_validity=oracle_diagnostic_only` and yields
`invalid_for_benchmark_claim_reason=oracle_memory_prior_diagnostic` when the
backend itself is non-oracle.

- [x] **Step 2: Verify RED**

Run the manifest test. Expected: fail with existing generic memory-prior
validity.

- [x] **Step 3: Implement manifest detection**

Read memory-prior metadata safely, preserve existing generic prior behavior, and
use a specific invalidity reason for oracle priors.

- [x] **Step 4: Verify locally**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_oracle_memory_prior.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_oracle_memory_prior.py
git diff --check
```

Expected: all pass cleanly.
