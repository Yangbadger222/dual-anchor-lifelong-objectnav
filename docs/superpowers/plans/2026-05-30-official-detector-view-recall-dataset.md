# Official Detector View-Recall Dataset Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export a supervised detector view-recall dataset from official Habitat policy and detector traces.

**Architecture:** Add a focused evaluator module that loads policy/detector traces, builds memory-relative active-perception features, and labels short-horizon target reacquisition. Add a thin CLI and console script following the existing local-action dataset exporter pattern.

**Tech Stack:** Python, JSON/CSV stdlib, pytest, existing official ObjectNav trace formats.

---

### Task 1: Pure Dataset Exporter

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_view_recall_dataset.py`
- Create: `src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py`

- [x] **Step 1: Write RED API test**

Create synthetic policy and detector traces where an active-perception step has
`distance_to_anchor_m`, `selected_viewpoint_cell`, `path_distance_m`, and
`active_perception_phase`, and a target detector match appears two steps later.
Assert the exported example has these feature fields and
`target_visible_within_horizon=True`.

- [x] **Step 2: Run RED API test**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py::test_official_view_recall_dataset_labels_future_target_recall -q
```

Expected: fail because the module does not exist.

- [x] **Step 3: Implement exporter**

Implement `export_official_view_recall_dataset(...)`, stable feature/label
schemas, JSON-safe examples, detector evidence by step, and horizon labels.

- [x] **Step 4: Verify API test GREEN**

Run the API test.

### Task 2: CSV And CLI

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_view_recall_dataset.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`
- Extend: `src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py`

- [x] **Step 1: Write RED CSV test**

Assert CSV output has stable source/id/action/decision columns plus feature and
label columns.

- [x] **Step 2: Write RED CLI test or packaging assertion**

Assert setup registers
`objectnav_habitat_official_view_recall_dataset` pointing at the new CLI.

- [x] **Step 3: Implement CSV writer and CLI**

Follow the existing local-action dataset CLI pattern: positional policy trace,
required `--detector-trace`, required `--output`, optional `--csv-output`,
optional `--source-run-id`, and `--horizon-steps`.

- [x] **Step 4: Verify CSV/CLI tests GREEN**

Run the new dataset tests and packaging test.

### Task 3: Verification And Real Trace Export

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-30-official-detector-view-recall-dataset.md`

- [x] **Step 1: Run local focused gate**

Run new tests, packaging test, focused official gate, compileall, and
`git diff --check`.

- [x] **Step 2: Sync to Linux**

Use `rsync -avR` for new code/tests/docs.

- [x] **Step 3: Run Linux focused gate**

Activate conda env `habitat` and rerun tests/compile/diff hygiene.

- [x] **Step 4: Export real dataset**

Run the CLI against at least the recent viewpoint-scan YOLO trace and write
JSON/CSV under `runs/habitat_official_objectnav/view_recall_dataset_...`.

- [x] **Step 5: Document counts**

Record example count, positive horizon labels, active-perception phase counts,
and limitations in devlog/handoff/experiment report.
