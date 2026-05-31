# Official Habitat ObjectNav Measure Adapter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first official Habitat-Lab ObjectNav evaluation adapter so future Dual-Anchor policies can report Habitat-provided `success`, `spl`, `soft_spl`, and `distance_to_goal` metrics.

**Architecture:** Add a small adapter module beside the existing Habitat replay runners. The first slice must be protocol-first: preflight the official config/dataset, run trivial smoke policies through `habitat.Env`, and persist metrics only from `env.get_metrics()`. Memory and frontier policies are intentionally deferred until the official metric path is proven.

**Tech Stack:** Python, Habitat-Lab `0.3.3` on Linux, local pytest with fake envs, JSON/CSV artifacts.

---

## Chunk 1: Local Adapter Contract

### Task 1: Define manifest and aggregation behavior

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write failing tests**

Add tests for:

```python
def test_official_metric_summary_aggregates_habitat_metric_keys():
    rows = [
        {"metrics": {"success": 1.0, "spl": 0.5, "soft_spl": 0.7, "distance_to_goal": 0.0}},
        {"metrics": {"success": 0.0, "spl": 0.0, "soft_spl": 0.2, "distance_to_goal": 2.0}},
    ]
    summary = summarize_official_objectnav_metrics(rows)
    assert summary["official_metrics"]["success_rate"] == 0.5
    assert summary["official_metrics"]["spl"] == 0.25
```

Also test that official metric fields are namespaced separately from policy debug fields.

- [x] **Step 2: Run tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py -q
```

Expected: import failure because the module does not exist.

- [x] **Step 3: Implement minimal data helpers**

Implement:

- `OFFICIAL_OBJECTNAV_MEASURE_KEYS`
- `OfficialObjectNavRunConfig`
- `summarize_official_objectnav_metrics(rows)`
- `write_json(path, payload)`
- `write_csv(path, rows)`
- `make_protocol_manifest(...)`

- [x] **Step 4: Run tests to verify GREEN**

Run the same focused test command. Expected: tests pass.

### Task 2: Add preflight command behavior

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Create: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/setup.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`

- [x] **Step 1: Write failing tests**

Test preflight writes `summary.json` and `protocol_manifest.json` without importing Habitat when `validate_habitat=False`.

Test CLI parses:

```bash
--config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml
--dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz
--scene-root datasets/habitat/scene_datasets/hm3d
--output <tmp>
--policy noop
--max-episodes 1
--preflight-only
```

- [x] **Step 2: Run tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

Expected: missing CLI/module functions.

- [x] **Step 3: Implement preflight**

Implement `run_habitat_official_objectnav_preflight(...)` that:

- records config path, dataset data path, split, scene root, policy, seed, max episodes;
- records required official measure keys;
- optionally imports Habitat and reads official config when `validate_habitat=True`;
- writes `protocol_manifest.json` and `summary.json`;
- never reports locally recomputed SR/SPL as official metrics.

- [x] **Step 4: Run focused tests**

Run the same focused command. Expected: tests pass.

## Chunk 2: Habitat Smoke Loop

### Task 3: Add fake-env tested smoke loop

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write failing fake-env tests**

Create a tiny fake env with `reset`, `step`, `get_metrics`, `episode_over`, `current_episode`, and `close`.

Test that `run_official_objectnav_episode_loop(...)`:

- calls `env.get_metrics()` for each episode;
- writes one row per episode;
- keeps metrics under `habitat_official`;
- stops on `STOP` or max steps depending on policy.

- [x] **Step 2: Verify RED**

Run focused tests and confirm failure due to missing loop.

- [x] **Step 3: Implement loop and trivial policies**

Implement policies:

- `noop`: immediately calls `stop`;
- `random`: samples from `move_forward`, `turn_left`, `turn_right`, then stops by budget.

Implement `run_habitat_official_objectnav_eval(...)` with injectable env factory for tests and real Habitat factory for Linux.

- [x] **Step 4: Verify GREEN**

Run focused tests.

## Chunk 3: Documentation and Linux Verification

### Task 4: Update project documentation

**Files:**
- Modify: `docs/design/2026-05-30-official-habitat-objectnav-measure-alignment.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create if Linux smoke runs: `docs/experiments/2026-05-30-habitat-official-objectnav-measure-adapter-smoke.md`

- [x] **Step 1: Record adapter boundary**

Document that first slice supports official preflight/noop/random smoke only, and does not yet prove memory policy performance.

- [x] **Step 2: Record verification**

Document local tests, `py_compile`, `git diff --check`, and Linux Habitat command results.

### Task 5: Run verification

**Files:** no intended edits unless failures expose missing docs/tests.

- [x] **Step 1: Local focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

- [x] **Step 2: Local broader checks**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py
git diff --check
```

- [x] **Step 3: Linux official Habitat preflight**

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_official_objectnav_eval --output runs/habitat_official_objectnav/preflight_valmini_20260530_v1 --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz --scene-root datasets/habitat/scene_datasets/hm3d --split val_mini --policy noop --max-episodes 1 --preflight-only --validate-habitat'
```

- [x] **Step 4: Linux one-episode smoke**

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_official_objectnav_eval --output runs/habitat_official_objectnav/noop_valmini_1ep_20260530_v1 --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz --scene-root datasets/habitat/scene_datasets/hm3d --split val_mini --policy noop --max-episodes 1 --validate-habitat'
```

Expected: `summary.json` contains `habitat_official.success`, `habitat_official.spl`, `habitat_official.soft_spl`, and `habitat_official.distance_to_goal` values read from Habitat-Lab.

## Chunk 4: Target-Agnostic Frontier Baseline

### Task 6: Add `frontier_only` as an official step-loop baseline

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`

- [x] **Step 1: Write failing tests**

Add tests that `frontier_only`:

- is accepted by the CLI;
- is recorded in the protocol manifest as a target-agnostic baseline;
- moves forward when the center depth window is clear;
- turns when the center depth window is blocked;
- stops on the final budgeted step;
- never receives target pose, geodesic route, semantic oracle, or detector-positive shortcuts.

- [x] **Step 2: Verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

Expected: failures because `frontier_only` is not a supported policy and the loop is still precomputed-action based.

- [x] **Step 3: Implement minimal target-agnostic baseline**

Refactor the official loop from precomputed action lists to policy-step
selection. Add a depth-reactive `frontier_only` policy:

- use only current observation depth;
- inspect the center third of the image;
- choose `move_forward` when enough center depth is clear;
- choose alternating turns when blocked or depth is absent;
- choose `stop` on the final action budget step.

Record the baseline as `target_agnostic_depth_frontier_baseline` in
`policy_debug`.

- [x] **Step 4: Verify GREEN locally**

Run focused tests, `py_compile`, and `git diff --check`.

- [x] **Step 5: Linux official smoke**

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_official_objectnav_eval --output runs/habitat_official_objectnav/frontier_only_valmini_3ep_20260530_v1 --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz --scene-root datasets/habitat/scene_datasets/hm3d --split val_mini --policy frontier_only --max-episodes 3 --max-steps 200 --validate-habitat'
```

Expected: official metrics are present for each episode. Do not claim a strong
baseline unless SR/SPL evidence actually supports it.

## Chunk 5: Occupancy Frontier Baseline

### Task 7: Add map-backed `occupancy_frontier`

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Modify: `docs/design/2026-05-30-official-habitat-objectnav-measure-alignment.md`
- Modify: `docs/experiments/2026-05-30-habitat-official-objectnav-measure-adapter-smoke.md`

- [x] **Step 1: Write failing tests**

Add tests for:

- normalized depth converting to metric ray endpoints;
- occupancy update marking free and occupied cells;
- frontier extraction from unknown cells adjacent to free cells;
- `occupancy_frontier` choosing a sustained turn toward frontier cells when
  blocked;
- `occupancy_frontier` moving forward when center depth is clear.

- [x] **Step 2: Verify RED**

Run focused adapter tests and confirm failures from missing helper/API support.

- [x] **Step 3: Implement pure helpers**

Implement small-grid helpers in the official adapter module first:

- occupancy constants;
- `OccupancyFrontierMap`;
- `create_occupancy_frontier_map`;
- `update_occupancy_frontier_map`;
- `occupancy_frontier_counts`;
- `select_occupancy_frontier_action`.

- [x] **Step 4: Wire policy**

Add `occupancy_frontier` to supported policies and store map debug fields in
`policy_debug`.

- [x] **Step 5: Verify locally and on Linux**

Run focused tests, full local tests, `py_compile`, `git diff --check`, then a
small Linux official smoke. Treat the result as a baseline probe, not a paper
claim.
