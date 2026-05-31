# Lifecycle Memory Prior Export Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Export lifecycle SQLite memory anchors into official memory-prior JSON
files without misrepresenting their coordinate frame.

**Architecture:** Add a focused exporter module beside the existing official
eval adapter. It reads lifecycle SQLite tables in read-only mode, joins anchors
with beliefs, computes a deterministic confidence, writes official
memory-prior JSON, and validates the result with the official parser. Exported
lifecycle anchors default to `coordinate_frame="habitat_world"`, while the
official policy selector only acts on `episode_start_relative` anchors. Add a
small CLI and tests.

**Tech Stack:** Python stdlib `sqlite3`, `json`, `argparse`, pytest.

---

## Chunk 1: Exporter API

### Task 1: Read lifecycle memory anchors and write official prior JSON

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/lifecycle_memory_prior_export.py`
- Test: `src/objectnav_core/tests/test_lifecycle_memory_prior_export.py`

- [x] **Step 1: Write failing exporter tests**

Add tests that create a temporary `LifelongMemoryHarness`, save one belief and
one object anchor, call `export_lifecycle_memory_prior(...)`, and assert:

- output JSON has one `anchors` record;
- `object_category`, `scene_id`, `x_m`, `z_m`, and `source` are correct;
- confidence is `p_existence * p_location_valid * p_usable`;
- exported lifecycle anchors include `coordinate_frame="habitat_world"`;
- `load_official_memory_prior(output)` accepts the file.

- [x] **Step 2: Verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q
```

Expected: import/module missing failure.

- [x] **Step 3: Implement minimal exporter**

Implement:

- `LifecycleMemoryPriorExportConfig`
- `export_lifecycle_memory_prior(config)`
- read-only SQLite open
- table existence checks
- anchor/belief join
- confidence filter
- coordinate-frame labeling
- deterministic JSON write

- [x] **Step 4: Verify GREEN**

Run the focused exporter tests.

## Chunk 2: CLI

### Task 2: Add command-line exporter

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/export_lifecycle_memory_prior.py`
- Modify: `src/objectnav_core/setup.py`
- Test: `src/objectnav_core/tests/test_lifecycle_memory_prior_export.py`

- [x] **Step 1: Write failing CLI test**

Call `main([...])` with `--memory-db`, `--output`, `--source-tag`, and
`--min-confidence`; assert it returns `0` and writes valid JSON.

- [x] **Step 2: Verify RED**

Run the focused exporter tests. Expected: CLI import missing.

- [x] **Step 3: Implement CLI and entry point**

Add parser, call `export_lifecycle_memory_prior`, print summary JSON, and add
`objectnav_export_lifecycle_memory_prior` console script.

- [x] **Step 4: Verify GREEN**

Run focused exporter tests and official adapter focused tests.

## Chunk 3: Docs and Verification

### Task 3: Record exporter bridge

**Files:**
- Modify: `docs/design/2026-05-30-lifecycle-memory-prior-export.md`
- Modify: `docs/design/2026-05-30-official-memory-prior-objectnav-policy.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] **Step 1: Update docs**

Record that exported priors inherit the validity of their source lifecycle run
and that lifecycle DB exports are `habitat_world` bridge artifacts, not direct
official policy inputs.

- [x] **Step 2: Local verification**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
python -m py_compile \
  src/objectnav_core/objectnav_core/evaluation/lifecycle_memory_prior_export.py \
  src/objectnav_core/objectnav_core/cli/export_lifecycle_memory_prior.py
git diff --check
```

- [x] **Step 3: Linux verification**

Sync files to Linux and run focused tests in conda env `habitat`:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest \
    src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

Result: Linux focused tests produced `31` passed. A real detector-anchor
lifecycle DB export produced `12` `habitat_world` anchors, and the official
one-episode guard smoke loaded those anchors but fell back with
`fallback_reason=no_matching_memory`.
