# Official Active-Perception Memory Frontier Policy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an official Habitat query policy that selects memory-conditioned frontiers by expected detector evidence.

**Architecture:** Implement a pure active-perception frontier selector on top of the existing occupancy map and memory anchor types, then integrate it as a new official policy. Detector-first target handling remains unchanged; this policy changes the fallback search objective when target evidence is absent.

**Tech Stack:** Python, NumPy, pytest, existing Habitat official evaluator.

---

### Task 1: Pure Active-Perception Selector

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Write the failing selector test**

Add a test where two frontier candidates exist: the nearer one has weak view
quality for the memory anchor, and the farther one is selected because expected
detector evidence is higher.

- [x] **Step 2: Run the focused test to verify it fails**

Run:

```bash
pytest -q src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_active_perception_frontier_prefers_viewpoint_with_expected_evidence
```

Expected: fail because the selector does not exist.

- [x] **Step 3: Implement the selector**

Add `_select_memory_active_perception_frontier(...)` with JSON-safe candidate
debug fields:
`expected_evidence`, `belief_mass`, `view_quality`, `view_distance_quality`,
`view_bearing_quality`, `travel_distance_m`, and `score`.

- [x] **Step 4: Verify selector test passes**

Run the focused selector test and keep the output.

### Task 2: Policy Integration

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py` if CLI choice coverage needs updating.

- [x] **Step 1: Write failing policy registration/action test**

Assert `memory_active_perception_frontier` is supported, has policy kind
`memory_active_perception_frontier_active_search`, records active-perception
debug fields, and returns an action toward the selected frontier.

- [x] **Step 2: Run focused tests to verify failure**

Run the new policy test.

- [x] **Step 3: Integrate policy**

Add the policy to supported choices, validation memory-prior requirements,
manifest invalidity list, `_policy_kind`, `_policy_debug_payload` compatibility,
and `_select_policy_action`.

- [x] **Step 4: Verify policy tests pass**

Run focused ObjectNav evaluator and CLI tests.

### Task 3: Verification And Smoke

**Files:**
- Modify: docs/devlog/handoff
- Create: `docs/experiments/2026-05-30-official-active-perception-frontier-yolo-smoke.md`

- [x] **Step 1: Run local gate**

Run focused official gate, compileall, and `git diff --check`.

- [ ] **Step 2: Sync to Linux**

Rsync `src` and `docs` to `/home/badger/Desktop/dual-anchor-lifelong-objectnav`.

- [ ] **Step 3: Run Linux gate**

Run focused official gate in conda env `habitat`, compileall, and
`git diff --check`.

- [ ] **Step 4: Run detector-backed YOLO smoke**

Use `objectnav_core.cli.run_habitat_official_objectnav_eval` with
`--detector yolo_world`, the 4-episode YOLO memory prior, and
`--policy memory_active_perception_frontier`.

- [ ] **Step 5: Document result**

Record official metrics, detector trace summary, policy decision counts, and
whether active-perception candidate scores changed behavior relative to
`memory_belief_frontier`.
