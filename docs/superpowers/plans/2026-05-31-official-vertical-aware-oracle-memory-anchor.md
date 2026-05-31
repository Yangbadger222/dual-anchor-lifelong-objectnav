# Official Vertical-Aware Oracle Memory Anchor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve optional vertical/floor offset in official oracle memory anchors so reconstructed Habitat oracle goals do not land on the wrong floor.

**Architecture:** Extend the existing memory anchor schema with optional `y_m`, export it as `goal_y - start_y`, and use it only in the oracle world-goal reconstruction path. Existing x/z-only memory priors keep their current behavior.

**Tech Stack:** Python, pytest, Habitat official evaluator helpers, JSON memory-prior artifacts.

---

## Chunk 1: Schema and Transform Tests

### Task 1: Add Failing Vertical-Aware Anchor Tests

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_official_episode_memory.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py`

- [ ] **Step 1: Write failing tests**

Add tests that:

- parse `y_m` from official memory-prior JSON;
- round-trip `y_m` through `make_official_memory_prior_payload`;
- reconstruct oracle backend goal y as `start_y + y_m`;
- preserve old start-height fallback when `y_m` is missing;
- export an oracle anchor with a non-zero vertical offset.

- [ ] **Step 2: Verify RED**

Run:

```bash
PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_anchor_oracle_goal_position_uses_anchor_vertical_offset \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_anchor_oracle_goal_position_without_vertical_offset_uses_start_height \
  src/objectnav_core/tests/test_official_episode_memory.py::test_official_memory_prior_payload_round_trips_vertical_offset \
  src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py::test_make_official_oracle_memory_anchor_preserves_vertical_offset -q
```

Expected: fail because `OfficialMemoryAnchor` has no `y_m` field yet.

## Chunk 2: Minimal Implementation

### Task 2: Implement Optional `y_m`

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/official_episode_memory.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_oracle_memory_prior.py`

- [ ] **Step 1: Add schema field**

Add `y_m: float | None = None` to `OfficialMemoryAnchor`, parse it when present,
validate it is finite, and include it in TargetNav/debug payloads.

- [ ] **Step 2: Update exporter transform**

Add a helper that returns `x_m`, `y_m`, and `z_m` from a Habitat world goal and
episode start pose. Use it in `make_official_oracle_memory_anchor`.

- [ ] **Step 3: Update oracle reconstruction**

When `anchor.y_m` is present, reconstruct world y as
`state.episode_start_position[1] + anchor.y_m`; otherwise preserve the previous
start-height behavior.

- [ ] **Step 4: Verify GREEN**

Run the same focused tests. Expected: pass.

## Chunk 3: Verification and Docs

### Task 3: Verify Locally and Remotely

**Files:**
- Modify: `docs/design/2026-05-31-official-vertical-aware-oracle-memory-anchor.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-31-official-vertical-aware-oracle-memory-anchor-smoke.md`

- [ ] **Step 1: Run local regression**

```bash
PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/evaluation/official_episode_memory.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_oracle_memory_prior.py

git diff --check
```

- [ ] **Step 2: Run remote Habitat smoke**

Re-export the 4-episode oracle memory prior on the Linux Habitat host, then run
oracle memory + oracle backend with `--pathfinder-suffix-goal-radius-m 0.05` or
`0.1`, record official metrics and whether chair/toilet improve.

- [ ] **Step 3: Update docs**

Record local verification, remote metrics, remaining risk, and next action.
