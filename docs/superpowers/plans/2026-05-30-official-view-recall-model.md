# Official View-Recall Model Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic logistic view-recall baseline that trains on exported official view-recall datasets and scores hidden-to-visible target reacquisition.

**Architecture:** Add a focused pure-Python model module mirroring the existing local-action logistic scorer pattern, with separate train and score CLIs. The default label is derived from view-recall examples as hidden-to-visible recovery, and reports include ranking metrics plus grouped summaries that expose scan dead ends.

**Tech Stack:** Python standard library, existing `objectnav_core` package, JSON/CSV artifacts, pytest.

---

### Task 1: Model API and Tests

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_view_recall_model.py`
- Create: `src/objectnav_core/tests/test_habitat_official_view_recall_model.py`

- [ ] **Step 1: Write failing training test**

Create a synthetic view-recall dataset with current-hidden positive and
negative examples plus visible continuity rows. Assert the default training
filter uses only current-hidden examples and learns a higher score for the
hidden positive state.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_model.py::test_official_view_recall_model_trains_hidden_to_visible_slice -q
```

Expected: import failure because the model module does not exist.

- [ ] **Step 3: Implement minimal logistic training and prediction**

Implement deterministic standardization, missing-value imputation,
`hidden_to_visible_within_horizon` label derivation, logistic training, and
prediction.

- [ ] **Step 4: Confirm GREEN for the training test**

Run the same focused test and expect `1 passed`.

### Task 2: Candidate Scoring and Reports

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_view_recall_model.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_view_recall_model.py`

- [ ] **Step 1: Write failing candidate/report tests**

Add tests for candidate action overrides, per-example score reports, top-k
metrics, grouped summaries, and CSV output.

- [ ] **Step 2: Run the new tests and confirm RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_model.py -q
```

Expected: failures for missing scoring/report functions.

- [ ] **Step 3: Implement scoring report and CSV writer**

Add `score_official_view_recall_dataset(...)` and
`write_official_view_recall_scores_csv(...)` with aggregate grouped summaries.

- [ ] **Step 4: Confirm GREEN for model tests**

Run the model test file and expect all tests to pass.

### Task 3: CLIs, Packaging, and Docs

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/train_habitat_official_view_recall_model.py`
- Create: `src/objectnav_core/objectnav_core/cli/score_habitat_official_view_recall_model.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-30-official-view-recall-model.md`

- [ ] **Step 1: Write failing CLI and packaging tests**

Test that train/score CLIs write JSON and CSV artifacts and that setup.py
contains both console scripts.

- [ ] **Step 2: Run the targeted tests and confirm RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_model.py src/objectnav_core/tests/test_ros_packaging.py -q
```

Expected: failures for missing CLI modules or setup entries.

- [ ] **Step 3: Implement CLIs and packaging**

Add the CLI wrappers and register console scripts.

- [ ] **Step 4: Update docs**

Record design, experiment command/results, devlog, and handoff.

### Task 4: Verification and Linux Scoring

**Files:**
- No new code files unless verification exposes a defect.

- [ ] **Step 1: Run local focused gate**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py src/objectnav_core/tests/test_habitat_official_view_recall_model.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

- [ ] **Step 2: Sync to Linux and rerun focused gate**

Run the same focused gate in conda env `habitat` on
`badger@100.88.131.52`.

- [ ] **Step 3: Train and score real view-recall datasets**

Train on the 20-episode memory-evidence dataset plus active comparison
datasets. Write reports under
`runs/habitat_official_objectnav/view_recall_model_*_20260530_v1`.

- [ ] **Step 4: Record results**

Update experiment report and handoff with metrics and the next online-policy
decision.
