# Official Detector Memory Discovery CLI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible CLI that runs official Habitat memory discovery with YOLO-World or Grounding-DINO detectors.

**Architecture:** Add a thin argparse module that builds an existing detector adapter, forwards official Habitat/discovery parameters into `run_habitat_official_memory_discovery`, and prints the returned JSON summary. Keep Habitat stepping and artifact writing in the existing discovery core.

**Tech Stack:** Python argparse/JSON, existing detector adapters, pytest, setuptools console scripts.

---

## Chunk 1: CLI Tests

### Task 1: Specify official detector discovery CLI behavior

**Files:**
- Create: `src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`

- [x] **Step 1: Write parser defaults test**

Import `build_parser` from the new CLI module and assert defaults include:

- `detector == "yolo_world"`;
- `detector_weights == "yolov8s-worldv2.pt"`;
- `policy == "occupancy_frontier"`;
- ObjectNav default categories include `chair` and `tv_monitor`.

- [x] **Step 2: Write runner forwarding test**

Call `main(argv, detector_factory=..., runner=...)` with a fake detector
factory and fake runner. Assert:

- detector backend, weights/model id, categories, confidence, and device are
  forwarded;
- the runner receives `detector_adapter`, `detector_name`, Habitat paths,
  policy, max episodes/steps, and projection/depth parameters;
- the runner summary is printed and returned with exit code `0`.

- [x] **Step 3: Write Grounding-DINO forwarding test**

Call `main` with `--detector grounding_dino`, `--detector-weights
IDEA-Research/grounding-dino-tiny`, `--grounding-dino-text-threshold`, and
`--grounding-dino-max-image-side`. Assert those arguments reach the detector
factory as `model_id`, `text_threshold`, and `max_image_side`.

- [x] **Step 4: Write category validation test**

Assert empty/whitespace-only `--categories` raises `SystemExit`.

- [x] **Step 5: Update packaging test**

Assert `setup.py` contains the new console script
`objectnav_habitat_official_memory_discovery`.

- [x] **Step 6: Verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

Expected: fail with missing module
`objectnav_core.cli.run_habitat_official_memory_discovery` or missing console
script.

Result: failed during collection with missing module
`objectnav_core.cli.run_habitat_official_memory_discovery`.

## Chunk 2: CLI Implementation

### Task 2: Add CLI module and entry point

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_discovery.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py`

- [x] **Step 1: Add parser**

Expose official Habitat arguments, discovery arguments, and detector arguments.

- [x] **Step 2: Add category parser**

Parse comma-separated categories and call `parser.error` for empty input.

- [x] **Step 3: Add detector factory helper**

Build `YoloWorldDetector` with `weights/categories/conf/device`, or
`GroundingDinoDetector` with
`model_id/categories/conf/text_threshold/max_image_side/device`.

- [x] **Step 4: Add injectable main**

Let tests pass a fake detector factory and fake runner while the production
default uses real adapters and `run_habitat_official_memory_discovery`.

- [x] **Step 5: Register console script**

Add `objectnav_habitat_official_memory_discovery` to `setup.py`.

- [x] **Step 6: Verify GREEN**

Run the RED command again and confirm the CLI/packaging tests pass.

Result: CLI/packaging tests produced `5` passed locally.

## Chunk 3: Verification And Documentation

### Task 3: Verify and document

**Files:**
- Modify: `docs/design/2026-05-30-official-detector-memory-discovery-cli.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Add or modify an experiment report if a live Linux smoke runs.

- [x] **Step 1: Run local verification**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

Result:

- Local focused CLI/official-memory/packaging set: `49` passed.
- Local full suite: `339` passed.
- Local `compileall` returned cleanly.
- Local `git diff --check` returned cleanly.

- [x] **Step 2: Sync and run Linux focused verification**

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
    src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
    src/objectnav_core/tests/test_official_episode_memory.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
    src/objectnav_core/tests/test_ros_packaging.py -q
```

Result:

- Linux focused CLI/official-memory/packaging set in conda env `habitat`:
  `49` passed.
- Linux `git diff --check` returned cleanly.

- [x] **Step 3: Try a live Linux smoke**

If detector/Habitat dependencies are available, run one short discovery command
with `--max-episodes 1 --max-steps 20`. Record artifact paths and anchor count.
If dependencies fail, record the exact error as a blocker for live detector
validation.

Result:

- YOLO-World one-episode/20-step smoke ran but exported `0` anchors because the
  chair episode only produced a high-confidence `bed` detection in the probed
  first frame.
- YOLO-World four-episode/50-step discovery smoke exported `8`
  `episode_start_relative` anchors from `189` detections.
- A query smoke loaded those generated priors and selected a `tv_monitor`
  memory in episode index `2`, but still produced `0/4` success and worse
  SoftSPL than same-budget `occupancy_frontier`.

- [x] **Step 4: Update docs**

Record that the CLI is operational plumbing and still not a benchmark claim.
