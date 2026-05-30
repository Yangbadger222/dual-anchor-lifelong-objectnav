# Memory-Conditioned Local Active Search Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Habitat replay mode that uses a remembered object anchor as a local active-search prior after direct memory confirmation is uncertain or stale.

**Architecture:** Keep the first implementation inside the existing Habitat closed-loop runner so it can reuse current route following, per-action observation, detector confirmation, row payloads, and tests. Add a post-memory search mode that only changes the `fallback_from_memory` probe source; query-start frontier behavior remains the matched global baseline.

**Tech Stack:** Python, pytest, Habitat replay runner interfaces, deterministic pure helper tests.

---

## Chunk 1: Local Probe Generation And Route Source

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [x] Write a failing test for deterministic memory-local probe goals generated from radius rings around a memory anchor.
- [x] Run the focused test and confirm it fails because `_memory_local_probe_goals` does not exist.
- [x] Implement `LocalSearchCandidate`, `MemoryLocalSearchConfig`, and `_memory_local_probe_goals(...)`.
- [x] Run the focused test and confirm it passes.
- [x] Write a failing test that route execution records `memory_local_active_probe:*` sources when given a custom source prefix.
- [x] Run the focused test and confirm it fails because `_run_navmesh_frontier_probe_route` does not accept a source prefix.
- [x] Add a `source_prefix` parameter with default `navmesh_frontier_probe`.
- [x] Run the focused route-source tests and confirm existing navmesh source tests still pass.

## Chunk 2: CLI/Preflight Configuration

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [x] Write a failing preflight test for `post_memory_search_mode`, local radii, local probe count, local heading count, and score mode.
- [x] Run the focused preflight test and confirm it fails on missing summary keys or parameters.
- [x] Add constants, parsing, validation, summary payloads, and CLI arguments.
- [x] Run the focused preflight test and existing preflight tests.

## Chunk 3: Post-Memory Search Integration

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [x] Write a failing pure test for `_memory_local_active_result(...)` using fake pathfinder, route segment, and verifier inputs.
- [x] Run the focused test and confirm it fails because the helper does not exist.
- [x] Implement `_memory_local_active_result(...)` by composing local probe goals with the existing route runner.
- [x] Thread `post_memory_search_mode` into the Habitat run so only `fallback_from_memory` can use `memory_local_active`.
- [x] Run all closed-loop unit tests.

## Chunk 4: Research Trail And Replay Handoff

**Files:**
- Modify: `docs/design/2026-05-30-memory-conditioned-local-active-search.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] Update the design with exact implemented flags and first-pass limitations.
- [x] Add a devlog entry with files changed, reason, verification, and follow-up Linux replay commands.
- [x] Update handoff with selected relocation rows to rerun on Linux.
- [x] Run `git diff --check`.
