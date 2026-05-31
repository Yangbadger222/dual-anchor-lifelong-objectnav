# Official Query Detector Injection CLI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose detector injection in the official ObjectNav eval CLI without changing default no-detector behavior.

**Architecture:** Reuse the detector-construction pattern from the official memory-discovery CLI, but keep detector creation optional and skipped for preflight. Add a test seam (`detector_factory`, `runner`) so unit tests never import or instantiate heavy detector backends.

**Tech Stack:** Python argparse, existing YOLO/Grounding-DINO adapters, pytest, Habitat official eval runner.

---

### Task 1: Add Detector CLI Seam

**Files:**
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`

- [x] **Step 1: Write the failing test**

Add a test that calls `main(..., detector_factory=fake, runner=fake_runner)` with
`--detector yolo_world` and verifies the fake detector plus target confidence
gate reach the runner.

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
pytest -q src/objectnav_core/tests/test_habitat_official_objectnav_cli.py::test_official_objectnav_cli_injects_query_detector_adapter
```

Expected: fail because `main()` does not accept `detector_factory`.

- [x] **Step 3: Implement minimal parser and detector builder**

Add `--detector`, detector backend args, category parsing, `_build_detector`,
and optional `runner`/`detector_factory` parameters to `main`.

- [x] **Step 4: Run the focused CLI tests**

Run:

```bash
pytest -q src/objectnav_core/tests/test_habitat_official_objectnav_cli.py
```

Expected: all CLI tests pass.

- [x] **Step 5: Run focused gate and hygiene**

Run the official focused gate, compileall, and `git diff --check`.

- [x] **Step 6: Sync and verify on Linux**

Sync docs/src to `/home/badger/Desktop/dual-anchor-lifelong-objectnav`, then run
the Linux focused gate, compileall, and `git diff --check`.
