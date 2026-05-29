# Targeted Decision-Boundary Slice Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `selected_group_ids` replay path to the Habitat closed-loop runner and CLI so mined decision-boundary rows can be rerun exactly.

**Architecture:** Extend the existing group-selection stage in the closed-loop Habitat runner. Preserve the current balanced category behavior as the default, but let explicit `group_id` selection bypass balancing, preserve requested order, and record the replay slice in `summary.json`.

**Tech Stack:** Python standard library, `objectnav_core`, pytest.

---

### Task 1: Selection Helper Tests

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`

- [ ] **Step 1: Write the failing explicit-selection test**

  Add a synthetic group list test that requests two exact `group_id` values and
  asserts the helper returns them in request order, ignoring `max_groups`.

- [ ] **Step 2: Run the test to verify it fails**

  Run:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_select_requested_groups_preserves_explicit_order -q`

  Expected: fail because the explicit selection helper does not exist yet.

- [ ] **Step 3: Add the missing-id failure test**

  Add a test that requests a nonexistent `group_id` and expects a clear
  `ValueError`.

### Task 2: Runner and CLI Plumbing

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`
- Modify: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py`
- Modify: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [ ] **Step 1: Implement explicit group-id selection**

  Add a selection helper that accepts `selected_group_ids`, validates them,
  preserves order, and bypasses the balanced `max_groups` sampler when the
  explicit slice is present.

- [ ] **Step 2: Thread the new argument through the runner and CLI**

  Add `selected_group_ids` to the preflight and full-run function signatures,
  plus a `--selected-group-ids` CSV option on the CLI.

- [ ] **Step 3: Record the replay slice in summaries**

  Store the requested ids alongside the final selected ids in
  `episode_selection` so experiment reports can audit the slice precisely.

- [ ] **Step 4: Run focused tests**

  Run the explicit-selection helper test, the CLI forwarding test, and the
  existing closed-loop preflight tests.

### Task 3: Verification and Documentation

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Run syntax checks**

  Run:
  `python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`

- [ ] **Step 2: Run whitespace checks**

  Run:
  `git diff --check`

- [ ] **Step 3: Update docs**

  Add a devlog entry describing the replay slice and update the handoff with
  the new targeted-selection workflow.
