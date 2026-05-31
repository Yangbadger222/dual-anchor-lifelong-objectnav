# Official Query Detector Trace Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reusable query-time detector trace artifacts to official Habitat ObjectNav memory-policy runs.

**Architecture:** Add a small trace collector inside `habitat_official_objectnav_eval.py` and thread it through `OfficialPolicyState`. `_detector_confirmed_target` records detector calls while preserving its existing STOP/no-STOP behavior; the full evaluator writes `detector_trace.json` and summary counts when an injected detector is used.

**Tech Stack:** Python dataclasses, JSON/CSV artifact helpers, pytest.

---

## Chunk 1: Trace Collector Tests

### Task 1: Specify query detector trace artifacts

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write failing test for detector trace JSON**

Add a test that calls `run_habitat_official_objectnav_eval` with:

- a fake env factory returning `_FakeDepthOfficialObjectNavEnv`;
- `policy="memory_guided_frontier"`;
- a one-anchor memory prior;
- a fake detector returning one matching `Detection(category="chair", confidence=0.91, bbox=(1, 1, 3, 3), ...)`;
- `target_detector_min_confidence=0.5`.

Assert:

- `summary["artifact_files"]["detector_trace"] == "detector_trace.json"`;
- `summary["detector_trace"]["call_count"] == 1`;
- `summary["detector_trace"]["target_match_call_count"] == 1`;
- `detector_trace.json` exists;
- first trace call records `episode_id`, `target_category`, `detection_count`, and `matches_target=true`.

- [x] **Step 2: Run RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_official_eval_writes_detector_trace_artifact -q
```

Expected: fail because the evaluator has no trace artifact.

### Task 2: Specify no-detector behavior

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write failing/guard test for no-detector runs**

Add a test that calls `run_habitat_official_objectnav_eval` without
`target_detector_adapter`, using `policy="occupancy_frontier"` or a
memory-guided fake prior if simpler.

Assert:

- `"detector_trace" not in summary`;
- `"detector_trace" not in summary["artifact_files"]`;
- `detector_trace.json` does not exist.

- [x] **Step 2: Run guard test**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_official_eval_skips_detector_trace_without_detector -q
```

Expected after implementation: pass. If it already passes before implementation,
keep it as a regression guard.

## Chunk 2: Core Trace Implementation

### Task 3: Add trace data structures and recording

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Add trace dataclass**

Add `OfficialDetectorTrace` with:

- `calls: list[dict[str, Any]]`
- `record_missing_rgb(...)`
- `record_detections(...)`
- `summary() -> dict[str, int]`
- `payload() -> dict[str, Any]`

- [x] **Step 2: Add trace field to policy state**

Add `detector_trace: OfficialDetectorTrace | None = None` to
`OfficialPolicyState` and thread an optional `detector_trace` parameter through
`run_official_objectnav_episode_loop`.

- [x] **Step 3: Record inside detector helper**

In `_detector_confirmed_target`, record:

- episode index / episode id / scene id / target category;
- step index;
- missing RGB;
- detections with category, confidence, bbox, and `matches_target`;
- call-level target match count.

Keep STOP selection behavior unchanged.

- [x] **Step 4: Write full-eval artifact**

In `run_habitat_official_objectnav_eval`, create a trace when
`target_detector_adapter is not None and write_detector_trace is True`.
After rows are collected, write `detector_trace.json`, add
`summary["detector_trace"]`, and add
`summary["artifact_files"]["detector_trace"]`.

- [x] **Step 5: Run GREEN**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_official_eval_writes_detector_trace_artifact \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_official_eval_skips_detector_trace_without_detector -q
```

Expected: both tests pass.

## Chunk 3: Verification And Documentation

### Task 4: Verify focused official-memory surface

**Files:**
- Modify: `docs/design/2026-05-30-official-query-detector-trace.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] **Step 1: Run focused tests**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q
```

- [x] **Step 2: Run syntax and whitespace checks**

```bash
PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

- [x] **Step 3: Update docs**

Record files changed, verification commands, and the reason this trace matters:
future active-search policies must improve detector evidence, not only route
geometry.

Result: implemented and verified locally and on Linux. The built-in trace YOLO
query smoke wrote
`runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_trace_builtin_4ep_50steps_20260530_v1`
and reproduced the negative evidence profile without the ad hoc wrapper:
`196` detector calls, `234` detections, `0` target-match calls, and `0`
target-match detections.
