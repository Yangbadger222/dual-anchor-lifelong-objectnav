# Official Local Action-Effect Learning Dataset Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export self-supervised local action-effect examples from official Habitat ObjectNav policy and detector traces.

**Architecture:** Add a pure-Python trace exporter module with a small CLI wrapper. The exporter joins policy steps to detector matches by episode/step and emits benchmark-safe features plus next-observation labels for later learned local action scoring.

**Tech Stack:** Python standard library, existing objectnav_core CLI/test patterns, pytest.

---

## Chunk 1: Dataset Exporter

### Task 1: API Tests

**Files:**
- Create: `src/objectnav_core/tests/test_habitat_official_local_action_dataset.py`
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_dataset.py`

- [ ] **Step 1: Write the failing API test**

Create synthetic `policy_trace.json` and `detector_trace.json` fixtures in a
temporary directory. Assert that the exporter creates examples for consecutive
same-episode steps, records current/next target visibility, and marks retained,
lost, and acquired transitions.

- [ ] **Step 2: Run the API test to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_local_action_dataset.py -q
```

Expected: import/module failure because the exporter does not exist yet.

- [ ] **Step 3: Implement the minimal exporter**

Add:

- `export_official_local_action_dataset(...)`
- detector primary-match indexing by `(episode_index, step_index)`
- stable example dictionaries
- report summary counts

- [ ] **Step 4: Run the API test to verify GREEN**

Run the same pytest command. Expected: all tests in the new file pass.

### Task 2: CSV and CLI

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_local_action_dataset.py`
- Create: `src/objectnav_core/tests/test_habitat_official_local_action_dataset_cli.py`
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_local_action_dataset.py`
- Modify: `src/objectnav_core/setup.py`

- [ ] **Step 1: Write failing CSV and CLI tests**

Add assertions that CSV output has stable headers, the CLI writes JSON/CSV, and
the JSON report records source trace paths.

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_dataset_cli.py -q
```

Expected: CSV/CLI helpers missing.

- [ ] **Step 3: Implement CSV writer and CLI**

Add:

- `write_official_local_action_dataset_csv(dataset, path)`
- CLI argument parser
- console script entry point

- [ ] **Step 4: Run focused tests to verify GREEN**

Run the same focused pytest command. Expected: pass.

### Task 3: Verification and Trail

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Run compile and diff checks**

```bash
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_dataset.py src/objectnav_core/objectnav_core/cli/export_habitat_official_local_action_dataset.py
git diff --check
```

- [ ] **Step 2: Optionally export the latest Linux YOLO trace**

If SSH is reachable:

```bash
ssh badger@100.88.131.52 '/home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.export_habitat_official_local_action_dataset <policy_trace> --detector-trace <detector_trace> --output <dataset.json> --csv-output <examples.csv>'
```

- [ ] **Step 3: Update devlog and handoff**

Record files changed, verification commands, summary counts, risks, and the next
recommended step: train/evaluate the first local action scorer.
