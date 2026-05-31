# Official Detector-Positive Viewpoint Memory Prior Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a diagnostic official Habitat exporter that stores detector-confirmed target viewpoints as memory anchors.

**Architecture:** Reuse the official memory-prior schema and existing Habitat config/env construction. The exporter restores official episode goal `view_points`, runs the selected detector, writes one episode-relative viewpoint anchor per detector-positive episode, and marks the output as privileged diagnostic data.

**Tech Stack:** Python, pytest, Habitat-Lab/Habitat-Sim on Linux, Grounding-DINO adapter, existing official ObjectNav evaluator.

---

### Task 1: Failing Exporter Tests

**Files:**
- Test: `src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py`

- [x] **Step 1: Write fake-env exporter tests**

Cover a detector-positive official viewpoint exporting `x_m`, `y_m`, `z_m`,
`episode_id`, confidence, and diagnostic source metadata.

- [x] **Step 2: Run tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py -q
```

Expected before implementation: fail with missing
`habitat_official_detector_viewpoint_memory_prior` module and missing CLI.

### Task 2: Exporter Implementation

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_detector_viewpoint_memory_prior.py`
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_detector_viewpoint_memory_prior.py`

- [x] **Step 1: Implement exporter**

Use `OfficialObjectNavRunConfig`, `_make_habitat_env`, official episode
`goals[].view_points[].agent_state`, and the existing memory-prior payload
writer. Convert viewpoint world position to episode-start-relative coordinates,
including optional `y_m`.

- [x] **Step 2: Implement CLI**

Default to `grounding_dino`, reuse detector-specific default weight resolution,
and forward `--grounding-dino-max-image-side`, detector confidence, and
viewpoint caps.

- [x] **Step 3: Verify GREEN**

Run the focused test file again and expect `3 passed`.

### Task 3: Packaging Entry Point

**Files:**
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`

- [x] **Step 1: Add failing packaging assertion**

Require `objectnav_habitat_official_detector_viewpoint_memory_prior` in the
console script list.

- [x] **Step 2: Run packaging test to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_ros_packaging.py -q
```

Expected before setup change: fail because the entry point is absent.

- [x] **Step 3: Add setup entry point**

Map the console script to
`objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior:main`.

- [x] **Step 4: Verify GREEN**

Run the packaging test and focused exporter test.

### Task 4: Local And Remote Verification

**Files:**
- No code changes.

- [x] **Step 1: Run local focused regression**

Run official detector-viewpoint, oracle-memory, DINO discovery CLI,
official eval CLI, and packaging tests.

- [x] **Step 2: Run compile and whitespace checks**

Run `compileall` for the new modules and `git diff --check`.

- [x] **Step 3: Sync to Linux Habitat host**

Use `rsync -avR` for the new module, CLI, tests, setup, and design doc.

- [x] **Step 4: Run remote focused regression**

Run the same focused tests and compile checks in the `habitat` conda env.

- [x] **Step 5: Run diagnostic Habitat export/query**

Export Grounding-DINO detector-positive viewpoint priors for 4 episodes and
query the prior with the oracle TargetNav backend.

### Task 5: Documentation

**Files:**
- Modify: `docs/design/2026-05-31-official-detector-positive-viewpoint-memory-prior.md`
- Create: `docs/experiments/2026-05-31-official-detector-positive-viewpoint-memory-prior.md`
- Modify: `docs/devlog/2026-05.md`
- Create: `docs/handoff/2026-05-31-official-detector-positive-viewpoint-memory-prior.md`

- [x] **Step 1: Update design status and implementation notes**

- [x] **Step 2: Record experiment report with exact commands and metrics**

- [x] **Step 3: Append devlog entry**

- [x] **Step 4: Add handoff with risks and next steps**
