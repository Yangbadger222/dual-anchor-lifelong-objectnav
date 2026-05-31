# Official Episode Detection Memory Anchor Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a non-oracle observation-only projection from detector boxes in
official Habitat RGB-D observations to `episode_start_relative` memory anchors.

**Architecture:** Add a small `official_episode_memory` module beside the
official evaluator. It consumes an observation mapping plus a detector bbox,
uses the corrected official GPS/compass frame helpers and depth conversion,
and emits `OfficialMemoryAnchor` records plus JSON-compatible prior payloads.

**Tech Stack:** Python, NumPy, pytest.

---

## Chunk 1: Projection Tests

### Task 1: Capture desired detector-to-anchor geometry

**Files:**
- Create: `src/objectnav_core/tests/test_official_episode_memory.py`

- [x] **Step 1: Write centered-forward projection test**

Use a 4x4 depth frame with depth `2.0`, centered bbox `(1, 1, 3, 3)`,
observation `gps=[1.0, 0.0]`, and `compass=[0.0]`. Assert the anchor is
`x_m=0.0`, `z_m=3.0`, `coordinate_frame="episode_start_relative"`.

- [x] **Step 2: Write compass-sign projection test**

Use the same centered bbox and depth, but observation `gps=[0.0, 0.0]` and
`compass=[-1.57079632679]`. Assert the anchor is approximately `x_m=2.0`,
`z_m=0.0`.

- [x] **Step 3: Write normalized-depth and invalid-input tests**

Add tests for normalized depth conversion and for returning `None` when the
bbox/depth patch is unusable.

- [x] **Step 4: Write payload round-trip test**

Create one anchor, call the payload builder, and assert
`load_official_memory_prior_from_payload` accepts it.

- [x] **Step 5: Verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_official_episode_memory.py -q
```

Result: import/module missing failure for
`objectnav_core.evaluation.official_episode_memory`.

## Chunk 2: Projection Implementation

### Task 2: Add official episode memory projection module

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/official_episode_memory.py`

- [x] **Step 1: Implement bbox/depth validation**

Convert depth to 2D, clip bbox to image bounds, and return `None` for empty
boxes or patches with no positive finite depth.

- [x] **Step 2: Implement depth and bearing projection**

Use median patch depth, normalized-depth conversion, bbox center, and HFOV to
compute detection range and horizontal bearing.

- [x] **Step 3: Implement episode-frame anchor output**

Use corrected official observation helpers to get current internal `x,z` and
heading, then project:

```python
x_m = current_x + depth_m * sin(heading + bearing)
z_m = current_z + depth_m * cos(heading + bearing)
```

Return `OfficialMemoryAnchor(..., coordinate_frame="episode_start_relative")`.

- [x] **Step 4: Implement prior payload builder**

Serialize anchors into `{"anchors": [...]}` with optional metadata.

- [x] **Step 5: Verify GREEN**

Run the new focused test file.

Result: `src/objectnav_core/tests/test_official_episode_memory.py` produced
`6` passed locally. The focused official-memory set produced `39` passed.

## Chunk 3: Integration Verification And Docs

### Task 3: Verify and record the bridge

**Files:**
- Modify: `docs/design/2026-05-30-official-episode-detection-memory-anchor.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] **Step 1: Run local verification**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

Result: local full suite produced `330` passed. `compileall` and
`git diff --check` returned cleanly.

- [x] **Step 2: Run Linux focused verification**

Sync touched files to Linux and run focused tests in conda env `habitat`:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_official_episode_memory.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q
```

Result: Linux focused official-memory set produced `39` passed. Linux
`git diff --check` returned cleanly.

- [x] **Step 3: Update docs**

Record files changed, verification, and the next step: plug this projection
into detector-backed official memory discovery.
