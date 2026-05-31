# Official Grounding-DINO Memory Line Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Grounding-DINO the first-class official memory-discovery detector while keeping YOLO-World available as an explicit ablation.

**Architecture:** Keep detector adapters unchanged. Add backend-specific default weight resolution in the official detector CLIs so DINO no longer inherits YOLO weights when `--detector-weights` is omitted, and switch discovery's default detector to Grounding-DINO.

**Tech Stack:** Python argparse, pytest, existing `GroundingDinoDetector` / `YoloWorldDetector` adapters, Habitat official CLI wrappers.

---

## Chunk 1: CLI Defaults And Tests

### Task 1: Discovery CLI DINO Defaults

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_discovery.py`

- [ ] **Step 1: Write the failing tests**

Add tests that assert parser defaults use `grounding_dino`, no explicit detector
weights, and that `main(..., detector_factory=...)` forwards
`model_id="IDEA-Research/grounding-dino-tiny"` when weights are omitted.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py -q
```

Expected: fail on old `yolo_world` / `yolov8s-worldv2.pt` defaults.

- [ ] **Step 3: Implement minimal CLI change**

Import `DEFAULT_GROUNDING_DINO_MODEL`, make discovery default detector
`grounding_dino`, make `--detector-weights` default `None`, and resolve weights
inside `_build_detector`.

- [ ] **Step 4: Verify GREEN**

Run the same focused test command and expect all tests in the file to pass.

### Task 2: Shared Query Detector Weight Resolution

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_memory_comparison.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_comparison.py`
- Modify: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_viewpoint_restore_dataset.py`

- [ ] **Step 1: Write failing tests**

Add focused tests proving `--detector grounding_dino` without weights forwards
`model_id="IDEA-Research/grounding-dino-tiny"` through query eval, comparison,
and candidate-viewpoint restore CLIs.

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_habitat_official_memory_comparison.py src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py -q
```

Expected: fail where omitted DINO weights still resolve to YOLO weights.

- [ ] **Step 3: Implement shared resolver**

Add constants and helper functions in `run_habitat_official_objectnav_eval.py`.
Reuse `_build_detector` from other official CLIs so all query-side detector
construction gets backend-specific defaults.

- [ ] **Step 4: Verify GREEN**

Run the same focused test command and expect pass.

## Chunk 2: Documentation, Local Verification, Remote Smoke

### Task 3: Documentation Trail

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Add: `docs/experiments/2026-05-31-official-grounding-dino-memory-discovery-smoke.md`
- Modify if needed: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Document the intended DINO smoke**

Create an experiment report with the planned local/remote commands before
claiming results.

- [ ] **Step 2: Add devlog entry**

Record changed files, reason, verification commands, and expected future impact.

### Task 4: Verification

- [ ] **Step 1: Run local focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_habitat_official_memory_comparison.py src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py src/objectnav_core/tests/test_grounding_dino_adapter.py -q
```

- [ ] **Step 2: Run compile/diff checks**

```bash
python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

- [ ] **Step 3: Sync to Linux and run focused remote tests**

Use the `badger@100.88.131.52` host and conda env `habitat`.

- [ ] **Step 4: Run DINO discovery smoke**

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_official_memory_discovery \
  --output runs/habitat_official_objectnav/grounding_dino_discovery_prior_4ep_100steps_20260531_v1 \
  --max-episodes 4 \
  --max-steps 100 \
  --grounding-dino-max-image-side 384 \
  --min-detection-confidence 0.25
```

Record summary/detection counts and do not present them as benchmark results.
