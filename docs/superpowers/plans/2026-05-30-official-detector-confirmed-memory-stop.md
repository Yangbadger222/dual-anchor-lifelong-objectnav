# Official Detector-Confirmed Memory Stop Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional detector-confirmed STOP hook to the official `memory_guided_frontier` policy.

**Architecture:** Extend the official episode loop with an injected detector adapter and confidence threshold. The memory policy checks current-view detector outputs before coordinate-based memory steering; if the target category is detected, it emits STOP and records debug telemetry.

**Tech Stack:** Python, existing detector adapter interface, pytest, Habitat official evaluator.

---

## Chunk 1: Policy Tests

### Task 1: Specify detector-confirmed stop behavior

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write matching-detector STOP test**

Add a fake detector returning `Detection(category="chair", confidence=0.9, ...)`
on an observation with RGB. Run `run_official_objectnav_episode_loop` with
`policy="memory_guided_frontier"`, a far memory anchor that would otherwise turn,
`target_detector_adapter=fake_detector`, and
`target_detector_min_confidence=0.5`. Assert actions are `["stop"]` and
`policy_debug.memory_prior.decision == "stop_on_detector"`.

- [x] **Step 2: Write wrong/low detector test**

Use a fake detector returning a wrong category or confidence below threshold.
Assert the policy still turns toward the far memory anchor and records
`decision="turn_toward_memory"`.

- [x] **Step 3: Verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_guided_frontier_stops_on_detector_confirmed_target \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_guided_frontier_ignores_wrong_or_low_confidence_detector_stop -q
```

Expected: fail because `run_official_objectnav_episode_loop` does not accept
detector stop parameters.

## Chunk 2: Core Implementation

### Task 2: Add detector stop hook

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Extend loop signature and state**

Add optional `target_detector_adapter` and
`target_detector_min_confidence` arguments to `run_official_objectnav_episode_loop`.
Store them in `OfficialPolicyState`.

- [x] **Step 2: Add detector match helper**

Implement a helper that reads `observation["rgb"]`, calls `detect(rgb)`,
normalizes labels, filters by confidence, and returns debug metadata for the
first matching target detection.

- [x] **Step 3: Stop before memory steering**

At the top of `_select_memory_guided_frontier_action`, call the helper. If it
returns a match, set `state.memory_debug` with `decision="stop_on_detector"`
and return `stop`.

- [x] **Step 4: Forward through full eval API**

Add optional detector stop parameters to `run_habitat_official_objectnav_eval`
so programmatic live smokes can inject a real detector.

- [x] **Step 5: Verify GREEN**

Run the RED command again and confirm both tests pass.

## Chunk 3: Verification And Smoke

### Task 3: Verify and document

**Files:**
- Modify: `docs/design/2026-05-30-official-detector-confirmed-memory-stop.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Add experiment report if the live smoke runs.

- [x] **Step 1: Run local verification**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

- [x] **Step 2: Sync and run Linux focused verification**

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
    src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
    src/objectnav_core/tests/test_official_episode_memory.py \
    src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q
```

- [x] **Step 3: Run YOLO query smoke**

Use the existing generated prior:
`runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json`.

Run a Python smoke that injects `YoloWorldDetector` into
`run_habitat_official_objectnav_eval` with `memory_guided_frontier`,
`max_episodes=4`, `max_steps=50`, and `target_detector_min_confidence=0.25`.
Record official metrics and whether `stop_on_detector` appears.

- [x] **Step 4: Update docs**

Document whether detector-confirmed STOP helped or produced another negative
result. Do not describe it as a benchmark claim unless official metrics justify
that claim.

Result: negative diagnostic smoke. The detector hook was exercised in the
traced run (`196` calls), but YOLO produced `0` target-category detections on
the query frames, so `stop_on_detector` never fired and official success stayed
`0/4`.
