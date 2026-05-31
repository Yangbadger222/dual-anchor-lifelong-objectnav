# Official Memory-Prior ObjectNav Policy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an official Habitat-Lab step-loop policy that can consume remembered object anchors from a JSON prior and act without route followers or target-pose shortcuts.

**Architecture:** Extend the existing official adapter rather than creating a second runner. Add a tiny memory-prior schema/parser, pass parsed anchors through `OfficialObjectNavRunConfig`, and implement `memory_guided_frontier` as a policy that heads toward matching remembered anchors while falling back to the existing occupancy frontier when memory is absent or blocked.

**Tech Stack:** Python, argparse, JSON, NumPy, pytest, Habitat-Lab `0.3.3` on Linux.

---

## Chunk 1: Memory Prior Contract

### Task 1: Parse and validate memory prior artifacts

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write failing parser tests**

Add tests for:

```python
def test_memory_prior_parser_loads_anchor_records(tmp_path):
    path = tmp_path / "memory.json"
    path.write_text(json.dumps({"anchors": [{
        "object_category": "chair",
        "scene_id": "scene-a",
        "x_m": 1.25,
        "z_m": -0.5,
        "confidence": 0.8,
        "source": "detector_positive:previous_session",
    }]}), encoding="utf-8")

    anchors = load_official_memory_prior(path)

    assert anchors[0].object_category == "chair"
    assert anchors[0].x_m == 1.25
```

Also test malformed records fail clearly when `x_m`/`z_m` or category is missing.

- [x] **Step 2: Verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_prior_parser_loads_anchor_records -q
```

Expected: import failure for `load_official_memory_prior`.

- [x] **Step 3: Implement minimal parser**

Add:

- `OfficialMemoryAnchor`
- `load_official_memory_prior(path)`
- `select_official_memory_anchor(...)`

Keep parsing independent from Habitat imports.

- [x] **Step 4: Verify GREEN**

Run the focused parser tests.

## Chunk 2: CLI and Manifest Plumbing

### Task 2: Add memory-prior CLI/config fields

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`

- [x] **Step 1: Write failing CLI/manifest tests**

Add tests that:

- `memory_guided_frontier` is accepted by the parser;
- `--memory-prior-path` appears in `protocol_manifest.json`;
- `memory_min_confidence`, `memory_stop_radius_m`, and
  `memory_bearing_tolerance_deg` are recorded;
- preflight validates the JSON path without importing Habitat.

- [x] **Step 2: Verify RED**

Run focused CLI and eval tests. Expected: unsupported policy/arguments fail.

- [x] **Step 3: Implement config and CLI fields**

Extend `OfficialObjectNavRunConfig`, preflight/eval function signatures, CLI
parser, manifest generation, and validation. Add `memory_guided_frontier` to
`SUPPORTED_OFFICIAL_POLICIES`.

- [x] **Step 4: Verify GREEN**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

## Chunk 3: Memory-Guided Policy Behavior

### Task 3: Implement step-level remembered-anchor actions

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write failing policy tests**

Add fake-env tests that prove `memory_guided_frontier`:

- stops when the agent is within `memory_stop_radius_m` of a selected anchor;
- turns toward a remembered anchor when bearing error is outside tolerance;
- moves forward when aligned and depth is clear;
- falls back to occupancy frontier when no matching anchor exists;
- records `policy_debug.memory_prior` with selected anchor source, range, and
  bearing error.

- [x] **Step 2: Verify RED**

Run the new focused tests and confirm failures from missing behavior.

- [x] **Step 3: Implement minimal action selection**

Use official `gps`/`compass` only:

```text
range = hypot(anchor.x_m - gps_x, anchor.z_m - gps_z)
bearing = atan2(dx, dz)
delta = wrap_angle(bearing - heading)
if range <= stop_radius: stop
elif abs(delta) > tolerance: turn toward sign(delta)
elif center depth clear: move_forward
else: occupancy frontier fallback
```

Do not use Habitat pathfinder, target pose, semantic masks, or detector
positives.

- [x] **Step 4: Verify GREEN**

Run focused adapter/CLI tests.

## Chunk 4: Documentation and Verification

### Task 4: Record the mechanism slice

**Files:**
- Modify: `docs/design/2026-05-30-official-habitat-objectnav-measure-alignment.md`
- Modify: `docs/design/2026-05-30-official-memory-prior-objectnav-policy.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create or update: `docs/experiments/2026-05-30-habitat-official-memory-prior-smoke.md`

- [x] **Step 1: Update docs**

Record that the memory-prior run is a mechanism/protocol check unless the prior
is generated by a documented non-oracle discovery process.

- [x] **Step 2: Local verification**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py
git diff --check
```

- [x] **Step 3: Linux verification**

Sync the touched files to `/home/badger/Desktop/dual-anchor-lifelong-objectnav`,
then run:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

- [x] **Step 4: Optional Habitat smoke**

Run a tiny official smoke only with a clearly labeled synthetic memory prior.
Record the artifact and do not treat it as a benchmark claim.

Post-plan frame-safety note:

- The parser now records optional `coordinate_frame`.
- The selector only acts on `episode_start_relative` anchors by default.
- Lifecycle DB exports are labeled `habitat_world`, so they are ignored by the
  runtime policy until a valid frame bridge exists.
