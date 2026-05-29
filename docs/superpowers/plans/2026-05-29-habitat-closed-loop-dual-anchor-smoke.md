# Habitat Closed-Loop Dual-Anchor Smoke Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first Habitat-backed smoke runner that uses real HM3D episode selection and GreedyGeodesic action execution while preserving the closed-loop dual-anchor summary schema from the grid harness.

**Architecture:** Build a small `habitat_closed_loop_dual_anchor_objectnav.py` evaluation module that reuses existing lifecycle utilities for loading ObjectNav episodes, selecting lifecycle groups, making Habitat simulators, sampling goal viewpoints, and following action routes. The first slice is oracle/action-level smoke: it records memory-vs-frontier decisions and action counts, but clearly marks detector/per-step frontier mapping as future work.

**Tech Stack:** Python, Habitat-Sim on Linux, existing lifecycle utilities, pytest, JSON artifacts.

---

## Chunk 1: Tests and Preflight

### Task 1: Red tests

**Files:**
- Create: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [ ] Test `run_habitat_closed_loop_dual_anchor_preflight` writes a summary with task `habitat_closed_loop_dual_anchor_objectnav_preflight`, policies, frame drift, and artifact files.
- [ ] Test a pure helper plans one row with `selected_candidate_types`, `matching_reason`, `frame_transform`, and action metrics.
- [ ] Run the test and confirm it fails because module does not exist.

### Task 2: Minimal module

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`

- [ ] Implement preflight with no Habitat import.
- [ ] Implement helper for deterministic option-row planning with memory/fallback action route values supplied by tests.
- [ ] Run focused test and make it pass.

## Chunk 2: CLI and Linux Smoke

### Task 3: CLI test and implementation

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`
- Create/modify CLI test.

- [ ] Add `--preflight-only`, dataset/scene-root/output, categories, max-groups, sensor dimensions, gate threshold, ambiguity margin.
- [ ] Test preflight CLI writes summary.

### Task 4: Habitat smoke implementation

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`

- [ ] Reuse `_load_valmini_episodes`, `_select_episodes`, `_build_lifecycle_groups`, `_make_simulator`, `_sample_replay_view_candidates`, `_rank_lifecycle_anchor_candidates`, `_choose_lifecycle_anchor_candidate`, `_choose_lifecycle_fallback_candidate`, `_cached_action_route_sequence`.
- [ ] For each selected group, execute memory route and fallback route with GreedyGeodesic action follower.
- [ ] Write `summary.json` with selected episode ids, per-policy aggregates, action counts, and limits.
- [ ] Keep detector mode as `oracle` for this slice.

## Chunk 3: Verification

- [ ] Run focused tests.
- [ ] Run full local tests.
- [ ] Commit/push.
- [ ] On Linux, run preflight and `--max-groups 1 --target-categories plant,toilet --detector oracle` smoke in `conda habitat`.
