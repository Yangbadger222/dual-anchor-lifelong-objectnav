# Official Detector Memory Discovery Loop Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate official memory-prior JSON artifacts from detector outputs
inside an official Habitat ObjectNav observation/action loop.

**Architecture:** Add a focused discovery module that accepts a Habitat-like
env and injected detector adapter. It filters detections by episode category,
projects boxes into `episode_start_relative` anchors with
`official_episode_memory`, steps using an existing official policy, and writes
prior/summary/trace artifacts.

**Tech Stack:** Python stdlib CSV/JSON, NumPy, pytest.

---

## Chunk 1: Discovery Loop Tests

### Task 1: Specify fake-env detector memory discovery

**Files:**
- Create: `src/objectnav_core/tests/test_habitat_official_memory_discovery.py`

- [x] **Step 1: Write successful discovery artifact test**

Use a fake env with one episode and an observation containing `rgb`, `depth`,
`gps`, and `compass`. Use a static detector returning one matching
`Detection`. Assert `run_habitat_official_memory_discovery(...)` writes:

- `memory_prior.json`;
- `summary.json`;
- `detections.csv`;
- one `episode_start_relative` anchor accepted by
  `load_official_memory_prior`.

- [x] **Step 2: Write wrong-category filtering test**

Static detector returns `sofa` while episode target is `chair`. Assert no anchor
is exported and summary counts the filtered detection.

- [x] **Step 3: Write projection-failure test**

Use matching detection but zero depth. Assert no anchor is exported and summary
counts projection failure.

- [x] **Step 4: Write confidence-cap regression test**

Use two matching projected detections with `max_anchors_per_episode=1`. Assert
the exported prior keeps the higher-confidence anchor and counts one cap-filtered
candidate.

- [x] **Step 5: Write artifact-to-policy integration test**

Generate a discovery `memory_prior.json`, load it through the official prior
parser, and feed it into `memory_guided_frontier`. Assert the query policy acts
on the generated `episode_start_relative` anchor without recording a fallback.

- [x] **Step 6: Verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py -q
```

Result: import/module missing failure for
`objectnav_core.evaluation.habitat_official_memory_discovery`.

Additional RED result: the confidence-cap regression initially failed because
the loop kept the first detection at confidence `0.2` instead of the later
candidate at confidence `0.9`.

## Chunk 2: Discovery Implementation

### Task 2: Add discovery module

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_discovery.py`

- [x] **Step 1: Add config dataclass and summary shape**

Include output path, policy, max episodes/steps, min confidence, and
max anchors per episode.

- [x] **Step 2: Add detection filtering and projection**

Normalize labels by replacing underscores with spaces and lowercasing. Project
matching detections with `estimate_episode_detection_anchor`.

- [x] **Step 3: Add official policy stepping**

Reuse `OfficialPolicyState` and `_select_policy_action` from the official eval
module so discovery explores with the same action semantics.

- [x] **Step 4: Sort and cap episode candidates**

Collect projected candidates per episode, sort by anchor confidence, export the
top `max_anchors_per_episode`, and count overflow as cap-filtered candidates.

- [x] **Step 5: Write artifacts**

Write `memory_prior.json`, `summary.json`, and `detections.csv`.

- [x] **Step 6: Verify GREEN**

Run the focused discovery tests.

Result: focused discovery tests produced `5` passed locally. The focused
official-memory set produced `44` passed locally after the integration test.

## Chunk 3: Verification And Paper Trail

### Task 3: Verify and document

**Files:**
- Modify: `docs/design/2026-05-30-official-detector-memory-discovery-loop.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] **Step 1: Run local verification**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

Result:

- Focused official-memory set: `44` passed locally.
- Full local suite: `335` passed.
- `compileall` returned cleanly.
- `git diff --check` returned cleanly.

- [x] **Step 2: Run Linux focused verification**

Sync touched files and run:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
    src/objectnav_core/tests/test_official_episode_memory.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q
```

Result:

- Linux focused official-memory set in conda env `habitat`: `44` passed.
- Linux `git diff --check` returned cleanly.

- [x] **Step 3: Update docs**

Record that this is detector-injected core-loop plumbing, not yet a live
Grounding-DINO official discovery/query benchmark.
