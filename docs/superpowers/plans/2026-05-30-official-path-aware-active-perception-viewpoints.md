# Official Path-Aware Active-Perception Viewpoints Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the official active-perception memory policy score reachable free viewpoints adjacent to frontiers instead of treating unknown frontier cells as destinations.

**Architecture:** Keep the policy inside the existing official Habitat evaluator. Add pure grid helpers for free viewpoint enumeration and shortest-path distance, then update `_select_memory_active_perception_frontier` to score from viewpoint centers while preserving frontier-cell debug fields.

**Tech Stack:** Python, NumPy, pytest, existing official Habitat ObjectNav evaluator.

---

### Task 1: Reachable Viewpoint Selector

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write the failing free-viewpoint regression**

Add a test where the unknown frontier cell is adjacent to a free standoff cell.
The selector should return the free `viewpoint_cell`, preserve the adjacent
`frontier_cell`, and compute evidence from the viewpoint center.

- [x] **Step 2: Run the test to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_active_perception_frontier_scores_reachable_free_viewpoint -q
```

Expected: fail because `viewpoint_cell` is not yet exposed and scoring still
uses the unknown frontier cell.

- [x] **Step 3: Write the failing path-distance regression**

Add a test where one free viewpoint is Euclidean-near but disconnected by
occupied cells, while a farther free viewpoint has a valid free-cell path. The
selector should choose the reachable viewpoint and report finite
`path_distance_m`.

- [x] **Step 4: Run the test to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_active_perception_frontier_uses_free_space_path_distance -q
```

Expected: fail because travel distance is still Euclidean and disconnected
viewpoints are not filtered.

- [x] **Step 5: Implement minimal helper code**

Add helpers near `_frontier_cells`:

- `_active_perception_viewpoint_candidates(frontier_map)` returning dicts with
  `viewpoint_cell` and `frontier_cell`.
- `_shortest_free_path_distance_cells(frontier_map, start, goal)` using BFS
  over 4-connected `OCCUPANCY_FREE` cells.

Update `_select_memory_active_perception_frontier` to score candidate
viewpoints, set `bearing_rad` toward `viewpoint_cell`, use path distance for
the travel penalty, and keep JSON-safe top-candidate fields.

- [x] **Step 6: Verify focused selector tests GREEN**

Run both new tests plus the existing active-perception selector tests.

### Task 2: Policy Debug Propagation

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write/update integration assertion**

Extend the active-perception policy debug test to assert
`selected_viewpoint_cell`, `selected_frontier_cell`, and `path_distance_m` are
recorded.

- [x] **Step 2: Run the integration test to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_frontier_records_expected_evidence_debug -q
```

Expected: fail until policy debug propagates the new fields.

- [x] **Step 3: Implement debug propagation**

Update `_select_memory_active_perception_frontier_fallback` so traces include
the selected free viewpoint and path-distance fields while preserving previous
frontier/evidence fields.

- [x] **Step 4: Verify integration GREEN**

Run the integration test and then the full ObjectNav evaluator test file.

### Task 3: Verification, Linux Sync, And Documentation

**Files:**
- Modify: `docs/design/2026-05-30-official-path-aware-active-perception-viewpoints.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: experiment report only if a Linux smoke is run.

- [x] **Step 1: Run local focused gate**

Run the focused official gate, `compileall`, and `git diff --check`.

- [x] **Step 2: Sync touched files to Linux**

Use `rsync -avR` to preserve paths into
`/home/badger/Desktop/dual-anchor-lifelong-objectnav`.

- [x] **Step 3: Run Linux focused gate**

Activate `/home/badger/anaconda3` env `habitat`, then run the same focused gate,
`compileall`, and `git diff --check`.

- [x] **Step 4: Run detector-backed smoke if online action trace changes**

Use the official eval CLI with `--detector yolo_world`, the four-episode
discovery memory prior, and a fresh output directory named with
`path_aware_viewpoint`.

- [x] **Step 5: Document evidence**

Record official metrics, active-perception decision counts, candidate debug
stats, and remaining risks in the devlog, handoff, and experiment report.
