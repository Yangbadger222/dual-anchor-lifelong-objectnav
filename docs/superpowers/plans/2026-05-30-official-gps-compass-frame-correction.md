# Official GPS/Compass Frame Correction Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct official ObjectNav policy geometry so Habitat `gps` and
`compass` observations map into the adapter's internal `x=right, z=forward`
policy frame.

**Architecture:** Keep the existing policy and prior schema, but fix the
observation boundary helpers. `_observation_xz` converts Habitat
`[forward, right]` GPS into internal `(right, forward)`, and
`_observation_heading` converts raw compass into positive-right heading by
negating it.

**Tech Stack:** Python, NumPy, pytest, Habitat-Lab focused smoke on Linux.

---

## Chunk 1: Regression Tests

### Task 1: Capture Habitat GPS and compass conventions

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Add failing GPS-order regression**

Add a memory-policy test where:

- memory anchor is straight ahead in the internal policy frame:
  `x_m=0.0`, `z_m=2.0`;
- observation uses Habitat GPS after moving forward:
  `gps=[1.0, 0.0]`;
- compass is `[0.0]`;
- center depth is clear.

Expected action: `move_forward`. The current broken code turns right because
it treats `gps[0]` as lateral `x`.

- [x] **Step 2: Add failing compass-sign regression**

Add a memory-policy test where:

- memory anchor is straight ahead from the episode start:
  `x_m=0.0`, `z_m=2.0`;
- observation is still at origin: `gps=[0.0, 0.0]`;
- compass is `[-0.5235987756]`, matching a right turn in Habitat;
- center depth is clear.

Expected action: `turn_left`. The current broken code turns right because it
uses raw compass instead of `-compass`.

- [x] **Step 3: Verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_guided_frontier_interprets_habitat_gps_forward_right_order \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_guided_frontier_inverts_habitat_compass_heading_sign -q
```

Result: both tests failed against the current production code. The GPS-order
test got `turn_left` instead of `move_forward`, and the compass-sign test got
`turn_right` instead of `turn_left`.

## Chunk 2: Boundary Fix

### Task 2: Fix observation-frame conversion

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Patch `_observation_xz`**

Return `(gps[1], gps[0])` for two-dimensional Habitat GPS, preserving `(0, 0)`
fallbacks for missing or malformed observations.

- [x] **Step 2: Patch `_observation_heading`**

Return `-float(compass[0])` so internal positive heading means a rightward turn
in the policy's `x=right, z=forward` frame.

- [x] **Step 3: Verify GREEN**

Run the two new regression tests and the full official evaluator test file.

Result: the two regression tests passed, and the focused
official/exporter set produced `33` passed locally.

## Chunk 3: Documentation and Verification

### Task 3: Record the correction

**Files:**
- Modify: `docs/design/2026-05-30-official-gps-compass-frame-correction.md`
- Modify: `docs/design/2026-05-30-official-memory-prior-objectnav-policy.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] **Step 1: Update docs with verification results**

Record the root cause, fixed files, commands run, and remaining risk.

- [x] **Step 2: Run local verification**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

Result: local full suite produced `324` passed. `compileall` and
`git diff --check` returned cleanly.

- [x] **Step 3: Run Linux verification**

Sync the touched files to
`/home/badger/Desktop/dual-anchor-lifelong-objectnav`, then run focused tests
in conda env `habitat`:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q
```

Result: Linux focused tests produced `33` passed. The official
episode-frame forward-anchor smoke emitted five `move_forward` actions then
`stop`, with near-zero bearing error.
