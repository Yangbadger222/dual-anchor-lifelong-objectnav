# Design Doc: Official Active-Phase State Features

Date: 2026-05-31
Owner: Codex
Status: Implemented and evaluated

## Goal

Expose active-viewpoint phase information as numeric candidate-rollout
`state_features` so action-matrix reports and utility models can distinguish
at-viewpoint orient/scan states from generic active-frontier movement states.

## Non-Goals

- Do not change rollout labels or action-matrix scoring.
- Do not train or integrate a new action policy in this slice.
- Do not add string/categorical model plumbing.
- Do not claim benchmark improvement from richer features alone.

## Background

The phase-diverse rollout probe produced the first repeat-first action-matrix
slice with recovered and hard states across `chair`, `bed`, `sofa`, and
`tv_monitor`. Those states are concentrated around
`orient_memory_anchor_from_active_viewpoint` and active-frontier turn phases.
The current `state_features` schema preserves geometry and scores but does not
encode the active phase. The utility model only consumes numeric features, so
raw phase strings would be ignored.

## System Boundary

This change belongs to the candidate-rollout exporter feature extraction layer.
It reads `memory_prior.active_perception_phase`, `memory_prior.decision`, and
the current step decision, then emits numeric/boolean fields. CSV writers,
action-matrix reports, and the existing utility model consume those fields
through the current schema path.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace step | JSON mapping | Existing `memory_prior` and step `decision`. |
| Output | `memory_active_perception_phase_rank` | numeric | `0` orient, `1` scan, `2` active-frontier/other active phase, `3` no active phase. |
| Output | Phase one-hot flags | booleans | Orient, scan, and active-frontier flags. |
| Output | `memory_active_perception_at_viewpoint` | boolean | True for orient/scan or zero path-distance states. |
| Output | CSV/report fields | JSON/CSV | Added through `STATE_FEATURE_FIELDS`. |

## Interfaces

- `export_official_candidate_rollout_dataset(...)` rows gain these
  `state_features` fields:
  - `memory_active_perception_phase_rank`
  - `memory_active_perception_orient_anchor`
  - `memory_active_perception_scan_anchor`
  - `memory_active_perception_frontier`
  - `memory_active_perception_at_viewpoint`
  - `memory_active_perception_scan_steps_remaining`
- `write_official_candidate_rollout_dataset_csv(...)` and
  `write_official_candidate_rollout_action_matrix_report_csv(...)` include the
  same fields through `STATE_FEATURE_FIELDS`.

## Data Flow

1. During replay, `_predecision_state_features` reads the logged policy step and
   selected memory candidate.
2. It derives active phase from `memory_prior.active_perception_phase` and the
   logged decision string.
3. It emits numeric/boolean features.
4. Existing dataset/report CSV writers preserve the new fields.
5. Existing utility-model feature extraction treats booleans and numeric fields
   as model features without additional code changes.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Phase metadata missing | Rank becomes no-active unless decision identifies active state | Fall back to decision string. |
| Path distance missing | `at_viewpoint` relies on phase flags only | Keep deterministic and avoid false precision. |
| Learner overfits phase flags | Held-out source-family validation detects it | Do not integrate online until held-out evidence beats baselines. |

## Verification Plan

- Add RED coverage showing rollout rows and CSV include active-phase features.
- Add RED coverage that orient states get orient/at-viewpoint flags.
- Run focused exporter tests and full objectnav core tests.
- Sync to Linux and run targeted exporter tests in `conda habitat`.

## Research Relevance

This makes the phase-diverse hard-state slice usable for learned local action
models. Without phase features, the learner can see path distance and decision
tokens, but it cannot directly model the at-viewpoint orient/scan boundary that
appears to distinguish useful `chair`/`bed` supervision.

## Open Questions

- Should future models use richer categorical encoding rather than numeric
  one-hot feature fields?
- Should exact state-restore labels replace repeat-first labels before training
  a larger model?

## Evaluation Note

A bounded Linux artifact confirmed that the phase fields are present in real
rollout JSON, rollout CSV, action-matrix reports, and report CSV output:

- `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_max8cat_max2episode_yolo_20260531_v1`
- `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_report_all_sources_yolo_20260531_v1`
- `runs/habitat_official_objectnav/action_utility_model_repeat_first_phase_path_features_all_sources_yolo_20260531_v1`

The tuned utility model improved full-report fit on the multi-source
phase-feature report, but leave-one-source validation remained too small and
mixed for online integration. The largest 20-episode holdout was worse than an
always-`turn_right` constant-action baseline by regret, so this result should
be treated as a diagnostic feature-plumbing win, not a learned policy win.
