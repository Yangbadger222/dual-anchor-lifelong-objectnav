# Design Doc: Official Phase-Diverse Rollout Export

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Add phase/path-aware candidate-state sampling and an optional per-category
per-episode cap to the official Habitat candidate-rollout exporter so diagnostic
rollouts can include at-viewpoint orient/scan states without collapsing to a
single episode.

## Non-Goals

- Do not change rollout label semantics or branch action execution.
- Do not use future detector labels to choose states.
- Do not integrate a learned controller online.
- Do not claim official benchmark improvement from the resulting dataset.

## Background

The score-aware rollout probe showed that `top_score_desc` still misses useful
`chair` and `bed` states. A trace-supervised view-candidate export over the same
20-episode active-perception run found `879` selected active candidates but only
`10` selected-candidate hidden-to-visible positives. Those positives are mostly
low-score `orient_memory_anchor_from_active_viewpoint` states with
`path_distance_m == 0`. A pure score sort therefore selects the wrong slice.

The preview also showed episode collapse: sorting by active phase/path can pick
many repeated states from the same category and episode before reaching another
episode where a rare recovery occurs. A per-category-per-episode cap is a
non-label-leaking way to force broader diagnostic coverage.

## System Boundary

This change stays inside candidate-state selection for the candidate-rollout
exporter. It reads only policy trace fields already present in
`memory_prior`/`top_candidates`; it does not read detector traces, images, or
future labels. Habitat replay, detector labeling, action-matrix reporting, and
hard-state mining remain unchanged.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | JSON | Existing official policy trace with `steps`. |
| Parameter | `state_sampling` | enum string | Adds `active_phase_path` alongside existing modes. |
| Parameter | `max_states_per_category_episode` | optional int | Caps selected states for each `(target_category, episode_index)` pair. |
| Existing parameter | `max_states_per_category` | optional int | Still caps selected states per category. |
| Output | Rollout dataset | JSON/CSV | Existing schema plus `candidate_state_limit_per_category_episode` metadata. |

## Interfaces

- Python API:
  `export_official_candidate_rollout_dataset(..., state_sampling="active_phase_path", max_states_per_category_episode=2)`
- CLI:
  `python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset <trace> --state-sampling active_phase_path --max-states-per-category-episode 2 ...`

## Data Flow

1. Load candidate-bearing policy steps.
2. If `state_sampling=active_phase_path`, sort states by:
   - active-viewpoint phase priority:
     `orient_anchor`, then `scan_anchor`, then active-perception frontier
     movement/turning, then other states;
   - path distance to the selected viewpoint, ascending;
   - top candidate score, descending;
   - original trace order.
3. Apply optional per-category-per-episode cap.
4. Apply optional per-category and global caps.
5. Replay and branch selected states through the unchanged rollout exporter.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Phase metadata missing | Sort falls back to decision string and then non-active bucket | Keep state eligible but lower priority. |
| Path distance missing | Sort places state after states with known path distance in the same phase | Preserve deterministic trace-order tie-break. |
| Per-episode cap too strict | Dataset state count is below requested category cap | Treat as intentional diversity control and adjust cap in probe. |
| Phase-aware sample still unrecovered | Action-matrix positives remain absent | Move to exact state-restore/candidate-viewpoint labels. |

## Verification Plan

- Add RED unit coverage for `active_phase_path` ordering plus
  `max_states_per_category_episode`.
- Add RED CLI coverage for `--max-states-per-category-episode`.
- Run focused exporter tests and full objectnav core tests.
- Sync to Linux and run a bounded repeat-first action-matrix probe with
  phase/path sampling and per-episode caps.

## Research Relevance

This is a stricter diagnostic between data selection and label redesign. If
phase/path-diverse sampling recovers `chair`/`bed`, then useful supervision
exists but previous samplers missed it. If it still fails, then repeat-first
macro-action labels are not enough and exact state-restore/candidate-viewpoint
labels become the next necessary step.

## Open Questions

- Should future sampling use round-robin selection across episodes instead of a
  simple per-episode cap?
- Should `scan_anchor` be prioritized before `orient_anchor` for some detector
  classes?
- Should active-viewpoint phase features become part of the learned local
  action utility model only after this diagnostic proves useful labels exist?
