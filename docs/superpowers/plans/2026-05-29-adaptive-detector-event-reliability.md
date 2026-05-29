# Adaptive Detector Event Reliability Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `event_posterior` memory reliability mode that uses detector confirmation events to adapt memory-vs-frontier expected utility without oracle overlap.

**Architecture:** Extend the existing Habitat closed-loop reliability estimator rather than adding a parallel policy. The new mode reuses the current evidence estimate, computes a bounded detector-event posterior from context-filtered confirmation events, blends the two, and records all components in row summaries.

**Tech Stack:** Python `objectnav_core`, pytest, Habitat smoke CLI schema.

---

### Task 1: Design and CLI Surface

**Files:**
- Modify: `docs/design/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py`

- [x] **Step 1: Update the design doc**
  Record goal, non-goals, inputs, outputs, failure modes, and verification plan
  for `event_posterior`.

- [x] **Step 2: Write failing CLI/preflight test**
  Add a test invoking `--memory-reliability-mode event_posterior` in preflight
  and assert the summary records the mode.

- [x] **Step 3: Run test to verify it fails**
  Run:
  `PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py::test_habitat_closed_loop_cli_preflight_accepts_event_posterior_reliability_mode -q`
  Expected: fail because argparse choices do not include `event_posterior`.

- [x] **Step 4: Add the mode constant**
  Extend `SUPPORTED_MEMORY_RELIABILITY_MODES` to include `event_posterior`.

- [x] **Step 5: Run test to verify it passes**
  Same command as Step 3. Expected: pass.

### Task 2: Posterior Helper

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [x] **Step 1: Write failing helper tests**
  Add tests for confirmed-event boost, suppressed-dominant reduction, context
  filtering, and oracle-audit invariance.

- [x] **Step 2: Run tests to verify failure**
  Run the exact helper tests with `PYTHONPATH=src/objectnav_core pytest ... -q`.
  Expected: fail because `event_posterior` is unsupported or components are
  missing.

- [x] **Step 3: Implement minimal posterior helper**
  Filter events by context, compute confirmed/suppressed weights from event
  outcome and detector-only quality fields, and return a bounded posterior.

- [x] **Step 4: Integrate `_estimate_memory_valid_prior`**
  Add optional `detector_confirmation_events` and `detector_confirmation_context`
  arguments. `fixed` and `evidence` must stay behaviorally unchanged.

- [x] **Step 5: Run helper tests to green**
  Run the exact tests from Step 2.

### Task 3: Runtime Wiring and Summaries

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [x] **Step 1: Add runtime context coverage**
  The context-filtering helper test covers original-memory versus
  `fallback_from_memory` event selection. A full Habitat row artifact remains
  the Linux smoke follow-up.

- [x] **Step 2: Wire runtime call**
  Pass the per-group `detector_confirmation_events` and active memory context
  to `_estimate_memory_valid_prior`.

- [x] **Step 3: Run focused route/CLI suite**
  Run:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_action_follower.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q`

### Task 4: Documentation and Verification

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] **Step 1: Update devlog and handoff**
  Record files changed, reason, verification, risks, and next Linux smoke.

- [x] **Step 2: Run final local checks**
  Run focused tests, `py_compile`, `git diff --check`, and sensitive scan.

- [ ] **Step 3: Commit and push**
  Stage only relevant files, commit, push `codex/habitat-memory-lifecycle`.
