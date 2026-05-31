# Official TargetNav FMM Backend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a benchmark-valid FMM-style TargetNav backend that replans around live blocked depth instead of oscillating in the current occupancy TargetNav turn loop.

**Architecture:** Keep the existing `memory_active_perception_frontier_targetnav` occupancy backend as an ablation, and add `memory_active_perception_frontier_targetnav_fmm` as a new policy. The new policy reuses detector/depth target belief, updates the online occupancy map, computes a grid distance field over free cells, temporarily blocks the live forward cell when center depth contradicts the planned move, and returns official Habitat actions.

**Tech Stack:** Python, NumPy, existing official Habitat ObjectNav evaluator, pytest, Linux `conda habitat` verification.

---

## Chunk 1: Policy Boundary

### Task 1: Register FMM TargetNav Policy

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write the failing manifest test**

Add a test near `test_memory_active_perception_targetnav_policy_records_interface_boundary`:

```python
def test_memory_active_perception_targetnav_fmm_policy_records_backend_boundary() -> None:
    config = OfficialObjectNavRunConfig(
        config_path="official.yaml",
        dataset_data_path="val_mini.json.gz",
        scene_root="datasets/habitat/scene_datasets/hm3d",
        split="val_mini",
        policy="memory_active_perception_frontier_targetnav_fmm",
        max_episodes=3,
    )

    manifest = make_protocol_manifest(config, habitat_metadata={"version": "0.3.3"})

    assert "memory_active_perception_frontier_targetnav_fmm" in SUPPORTED_OFFICIAL_POLICIES
    assert manifest["policy_kind"] == "memory_active_perception_frontier_targetnav_fmm"
    assert manifest["targetnav"] == {
        "enabled": True,
        "target_estimator": "bbox_depth",
        "backend": "fmm_grid",
        "source_validity": "sensor_depth_local_planner",
    }
```

- [ ] **Step 2: Run the test to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_fmm_policy_records_backend_boundary -q
```

Expected: FAIL because the policy is not registered yet.

- [ ] **Step 3: Implement registration**

Update `SUPPORTED_OFFICIAL_POLICIES`, `_targetnav_manifest(...)`, `_policy_kind(...)`,
and budget-stop debug policy sets so the new policy records `fmm_grid`.

- [ ] **Step 4: Run the test to verify GREEN**

Run the same pytest command. Expected: PASS.

## Chunk 2: FMM Helper Behavior

### Task 2: Add Distance-Field and Blocked-Forward Tests

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Import the new helper in tests**

Add `_select_targetnav_fmm_action` to the private helper imports.

- [ ] **Step 2: Write the failing clear-path test**

Create a free straight-line map from the agent to the target. With heading
aligned to the next cell and clear/no depth, `_select_targetnav_fmm_action(...)`
should return `move_forward` and debug `backend == "fmm_grid"`.

- [ ] **Step 3: Run the clear-path test to verify RED**

Expected: FAIL because `_select_targetnav_fmm_action` does not exist.

- [ ] **Step 4: Write the failing blocked-forward replanning test**

Create a map where the direct left cell is free but the live depth frame is
blocked while the agent is facing that cell. Also create an alternate free path
through the upper neighbor. Expected action should be a turn toward the alternate
neighbor, and debug should include `blocked_forward_cell` and
`replanned_after_blocked_forward == True`.

- [ ] **Step 5: Implement minimal FMM helpers**

Implement:

```python
def _targetnav_distance_field(frontier_map, goal_cell, *, grid=None) -> np.ndarray: ...
def _targetnav_fmm_next_cell(frontier_map, start_cell, distance_field) -> tuple[int, int] | None: ...
def _forward_grid_cell(frontier_map, observation) -> tuple[int, int]: ...
def _select_targetnav_fmm_action(...): ...
```

Use Dijkstra/BFS over free cells for this slice. Keep occupied/unknown cells
non-traversable, and temporarily mark the forward cell occupied only inside the
current decision when center depth is blocked.

- [ ] **Step 6: Run helper tests to verify GREEN**

Run the two new tests. Expected: PASS.

## Chunk 3: Policy Loop Integration

### Task 3: Route the New Policy Through FMM

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write failing fake-env policy test**

Mirror `test_targetnav_policy_uses_detector_depth_occupancy_backend`, but run
`policy="memory_active_perception_frontier_targetnav_fmm"`. Assert the policy
uses backend `fmm_grid`, records a `pointgoal_with_gps_compass` or target belief
debug payload, and returns an official action.

- [ ] **Step 2: Run the fake-env test to verify RED**

Expected: FAIL because the policy dispatch still does not call FMM.

- [ ] **Step 3: Implement policy dispatch**

Refactor the existing TargetNav action selector to accept `backend="occupancy_grid"`
or `backend="fmm_grid"`, and dispatch:

- `memory_active_perception_frontier_targetnav` -> occupancy backend;
- `memory_active_perception_frontier_targetnav_fmm` -> FMM backend.

- [ ] **Step 4: Run the fake-env test to verify GREEN**

Expected: PASS.

## Chunk 4: Verification and Documentation

### Task 4: Run Gates, Sync, and Record Results

**Files:**
- Modify: `docs/design/2026-05-31-official-targetnav-fmm-backend.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Optional create: `docs/experiments/2026-05-31-official-targetnav-fmm-yolo-smoke.md`

- [ ] **Step 1: Run focused local tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

- [ ] **Step 2: Run compile and whitespace checks**

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py

git diff --check
```

- [ ] **Step 3: Sync touched files to Linux**

Use `rsync -avR` for only the touched source, tests, and docs.

- [ ] **Step 4: Run Linux focused tests and compile**

Use `/home/badger/anaconda3/bin/conda run -n habitat env` with the same pytest
and compile commands.

- [ ] **Step 5: Run a bounded YOLO smoke if unit gates pass**

Run the same four-episode protocol as the TargetNav belief smoke, changing only
the policy and output path:

```bash
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --output runs/habitat_official_objectnav/targetnav_fmm_active_perception_yolo_4ep_100steps_20260531_v1 \
  --policy memory_active_perception_frontier_targetnav_fmm \
  --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-episodes 4 \
  --max-steps 100 \
  --seed 313
```

- [ ] **Step 6: Record outcome without overclaiming**

Update devlog, handoff, and experiment report. If success remains `0/4`, record
the new failure mode and continue toward learned local policy or richer mapping.
