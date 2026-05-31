# Design Doc: Official State-Restore Label Dataset

Date: 2026-05-31
Owner: Codex
Status: Implemented and smoke-tested

## Goal

Export detector labels measured at the exact restored policy state for
candidate-bearing memory-query steps, without applying branch actions. This
creates a clean current-view label artifact for debugging memory-query states
and for bootstrapping later candidate-viewpoint teleport labels.

## Non-Goals

- Do not claim an online ObjectNav policy improvement.
- Do not teleport to unvisited candidate viewpoints in this slice.
- Do not replace official Habitat metrics.
- Do not train a new online controller from this dataset.

## Background

Repeat-first action-matrix labels are useful diagnostics, but the utility model
still does not robustly beat trivial constant-action baselines under held-out
validation. The next label-design step should separate state restoration from
action choice. The current exporter already replays the logged episode prefix
to the exact policy decision state; this slice records the detector label at
that restored state directly.

## System Boundary

The change belongs to the official candidate-rollout evaluation layer. It uses
existing policy traces, the existing replay-to-state machinery, and the same
detector adapter path as branch rollouts. It emits a separate dataset task so
downstream tools cannot confuse current-view state labels with action-matrix
rollout labels.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | JSON | Candidate-bearing memory-query trace steps. |
| Input | Detector adapter | Python object | Same adapter contract as rollout export. |
| Input | Habitat env | Habitat env or fake test env | Replays exact episode prefix. |
| Output | State-restore dataset | JSON | One row per selected candidate-bearing state. |
| Output | CSV | CSV | Stable schema for audits. |

Each row records:

- source trace and episode metadata
- action/decision at the restored state
- selected/top candidate geometry fields
- existing numeric `state_features`
- restore validity and replay actions
- detector labels measured before any branch action

## Interfaces

- New API:
  `export_official_candidate_state_restore_dataset(...)`
- New CSV writer:
  `write_official_candidate_state_restore_dataset_csv(...)`
- New CLI:
  `python -m objectnav_core.cli.export_habitat_official_candidate_state_restore_dataset`

The exporter reuses existing candidate-state sampling knobs:

- `max_states`
- `max_states_per_category`
- `max_states_per_category_episode`
- `state_sampling`

## Data Flow

1. Load policy trace and select candidate-bearing states.
2. For each selected state, create a Habitat env and replay logged actions up to
   the exact target step.
3. Extract predecision state features from the restored observation.
4. Run the detector on that restored observation.
5. Write one label row for the restored state.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Replay fails before target state | `valid_restore=false` and `invalid_reason` set | Keep row for audit; mark label unavailable. |
| Detector unavailable or no RGB | `label_available=false` | Do not treat as negative supervision. |
| State is already target-visible | `current_target_visible=true` | Useful for filtering current-visible states before action labels. |
| Dataset mistaken for candidate-viewpoint labels | Separate task/schema and docs | Name explicitly says state-restore current-view. |

## Verification Plan

- Add RED tests showing state-restore export writes one row per state and does
  not step branch actions after replay.
- Add RED tests for invalid replay and CSV schema.
- Add CLI tests for JSON/CSV output.
- Run focused exporter tests, full objectnav tests, compileall, diff check, and
  trailing-whitespace scan.
- Sync to Linux and run targeted tests in conda env `habitat`.

## Research Relevance

This dataset answers a narrower but important question: when the memory system
selects a candidate-bearing state, was the target already visible at the exact
restored observation? It removes the repeat-first action confound and prepares
the exporter boundary for the next, stronger candidate-viewpoint teleport label
dataset.

## Open Questions

- How should candidate grid cells be converted back to Habitat world poses for
  teleport labels without reintroducing frame bugs?
- Should current-visible state-restore positives be excluded from future
  action-utility training, or retained as a separate calibration class?

## Evaluation Note

Linux smoke artifact:

- `runs/habitat_official_objectnav/candidate_state_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1`

The bounded 20-episode phase/path sample restored `24/24` states with `0`
invalid restores. Only `1/24` states was target-visible at the restored current
view, a `sofa` orient-at-viewpoint state. This confirms that exact state restore
is useful for filtering current-visible states, but most memory-query
supervision still requires candidate-viewpoint or action-conditioned labels.
