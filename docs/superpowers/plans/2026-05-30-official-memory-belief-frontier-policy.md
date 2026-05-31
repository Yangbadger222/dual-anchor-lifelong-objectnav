# Official Memory-Belief Frontier Policy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `memory_belief_frontier` official query policy that scores frontiers by memory-induced target belief instead of nearest-anchor steering.

**Architecture:** Extend the existing official evaluator policy switch with a new memory policy. Reuse `OfficialMemoryAnchor`, corrected GPS/compass geometry, occupancy frontier mapping, detector-confirmed STOP, and official Habitat metric handling; add a focused frontier scoring helper and debug payload.

**Tech Stack:** Python, NumPy, pytest, Habitat official evaluator.

---

## Chunk 1: Belief Frontier Scoring

### Task 1: Specify scoring helper behavior

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Import the scoring helper once it exists**

Add `_select_memory_belief_frontier` to the test imports from
`habitat_official_objectnav_eval`.

- [x] **Step 2: Write failing frontier preference test**

Create an `OccupancyFrontierMap(size_cells= nine or eleven, cell_size_m=1.0)`.
Mark current/free cells so there is:

- one near frontier away from memory;
- one farther frontier near a memory anchor.

Create an anchor at the farther frontier location with confidence `1.0`. Call
`_select_memory_belief_frontier(...)` and assert the selected cell is the
frontier near the memory anchor and that the returned debug score includes
positive `belief_mass`.

- [x] **Step 3: Run RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_belief_frontier_prefers_frontier_near_memory_anchor -q
```

Expected: fail because `_select_memory_belief_frontier` does not exist.

### Task 2: Implement scoring helper

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Add helper result shape**

Represent the helper result as a plain `dict[str, Any]` with:

- `frontier_cell`;
- `bearing_rad`;
- `bearing_error_rad`;
- `belief_mass`;
- `travel_distance_m`;
- `score`.

- [x] **Step 2: Implement Gaussian belief scoring**

For every `_frontier_cells(frontier_map)` cell:

```python
belief_mass = anchor.confidence * np.exp(
    -(distance_to_anchor_m ** 2) / (2.0 * sigma_m ** 2)
)
score = belief_mass - distance_weight * travel_distance_m
```

Select the highest score, breaking ties by shorter travel distance.

- [x] **Step 3: Run GREEN**

Run the RED command again. Expected: pass.

## Chunk 2: Policy Integration

### Task 3: Add official policy behavior

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write failing policy registration test**

Assert:

- `"memory_belief_frontier" in SUPPORTED_OFFICIAL_POLICIES`;
- `make_protocol_manifest(...).policy_kind == "memory_belief_frontier_active_search"`;
- `run_habitat_official_objectnav_preflight(... policy="memory_belief_frontier", memory_prior_path=...)` accepts a memory prior.

- [x] **Step 2: Write failing policy debug test**

Run `run_official_objectnav_episode_loop` with `policy="memory_belief_frontier"`,
a matching memory anchor, and observations with depth/gps/compass. Assert:

- actions are official discrete actions;
- `policy_debug.memory_prior.decision` is one of
  `turn_toward_memory_belief_frontier`, `move_toward_memory_belief_frontier`,
  or `fallback_occupancy_frontier`;
- debug includes `belief_mass` and `selected_frontier_cell` when a scored
  frontier exists.

- [x] **Step 3: Implement policy registration**

Add `memory_belief_frontier` to:

- `SUPPORTED_OFFICIAL_POLICIES`;
- `_validate_run_config` memory-prior requirement;
- `_policy_kind`;
- `_select_policy_action`.

- [x] **Step 4: Implement policy action selector**

Add `_select_memory_belief_frontier_action`:

1. call `_detector_confirmed_target` first;
2. select matching memory anchor;
3. update occupancy map;
4. score frontiers with `_select_memory_belief_frontier`;
5. turn/move according to bearing error and clear depth;
6. fallback to `_select_occupancy_frontier_action` when no memory/frontier exists.

- [x] **Step 5: Run GREEN**

Run the two policy tests. Expected: pass.

## Chunk 3: Verification And Docs

### Task 4: Verify and record

**Files:**
- Modify: `docs/design/2026-05-30-official-memory-belief-frontier-policy.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] **Step 1: Run focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q
```

- [x] **Step 2: Run syntax and whitespace checks**

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

- [x] **Step 3: Sync and run Linux focused verification**

Use `rsync --relative` for touched files, then run the focused test command in
the Linux conda env `habitat`.

- [x] **Step 4: Update docs**

Record test counts, any smoke result, and explicitly state that this is an
algorithmic policy slice, not a benchmark claim.

Result: implemented and verified. The live YOLO diagnostic improved detector
evidence from `0` to `1` target-match detections versus nearest-anchor memory
steering, but official success stayed `0/4`, so this is not a benchmark claim.
