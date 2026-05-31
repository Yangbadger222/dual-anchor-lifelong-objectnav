# Design Doc: Official Action-Matrix Hard-State Mining

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Add an offline report that mines replay states from an official Habitat
candidate-rollout action-matrix report where a trivial always-left action
baseline is not one of the fastest recovering actions.

## Non-Goals

- Do not change online ObjectNav policy behavior.
- Do not train or select a new utility model.
- Do not claim benchmark improvement, SPL improvement, or paper-ready policy
  performance.
- Do not rerun Habitat simulation inside the miner; it consumes existing
  report JSON only.

## Background

The repeat-first candidate-rollout action matrix produced valid official
Habitat/Yolo artifacts with pre-decision `state_features`, but the four active
trace families are too left-dominated. Feature-aware utility models improved
full-report fit but did not beat always-`turn_left` under leave-one-source
validation. The next useful dataset should emphasize states where always-left
is actually wrong or ambiguous, rather than retuning on the same easy
distribution.

## System Boundary

The miner owns offline filtering and summarization of action-matrix report
states. It depends on the existing report schema:

- `states[*].actions`
- `states[*].fastest_actions`
- `states[*].strict_fastest_action`
- source metadata such as `source_dataset`, `source_policy_trace`, and
  `source_dataset_index`

It does not inspect Habitat datasets, detectors, RGB-D observations, or policy
trace prefixes directly.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Action-matrix report | JSON | Existing `habitat_official_candidate_rollout_action_matrix_report`. |
| Parameter | Baseline action | string | Defaults to `turn_left`. |
| Parameter | Include baseline ties | bool | Optional diagnostic mode for states where the baseline is fastest but not strictly fastest. |
| Output | Hard-state report | JSON | Contains mined states, source-family counts, baseline-action diagnostics, and action outcomes. |
| Output | Hard-state CSV | CSV | Flat state summary for sorting and dataset planning. |

## Interfaces

- Python API:
  `mine_official_candidate_rollout_hard_states(report, baseline_action="turn_left", include_baseline_ties=False)`
- Python API:
  `write_official_candidate_rollout_hard_states_csv(report, path)`
- CLI:
  `python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states <report.json> --output <hard_states.json> --csv-output <hard_states.csv>`
- Console script:
  `objectnav_habitat_official_candidate_rollout_hard_states`

## Data Flow

1. Load an existing action-matrix report.
2. Iterate report states and read their `fastest_actions`.
3. Select states where `fastest_actions` is non-empty and the baseline action
   is not in that fastest set.
4. Optionally include tie states where the baseline is fastest but not the
   strict fastest action.
5. Attach source-family labels inferred from existing source paths.
6. Summarize mined states by source family, target category, and strict fastest
   action.
7. Write JSON and optional CSV artifacts.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Input is not an action-matrix report | Missing task/schema fields or states list | Raise `ValueError` in the API/CLI. |
| State lacks fastest-action labels | Empty or malformed `fastest_actions` | Skip by default and count skipped states. |
| Source family cannot be inferred | No known active-trace token in source paths | Fall back to `source_dataset_index:<n>`. |
| Baseline action is absent from report actions | No matching action payloads | Still mine by `fastest_actions`, but report missing baseline payload fields as null. |

## Verification Plan

- Add RED tests for default always-left hard-state selection, source-family
  counts, CSV output, and CLI execution.
- Verify the tests fail before implementation.
- Run focused pytest for the new miner, rollout/report tests, and packaging.
- Run `python -m compileall` on the new module and CLI.
- Run `git diff --check`.
- On Linux/Habitat, run the CLI against the regenerated feature-bearing
  repeat-first report and record the mined counts.

## Research Relevance

This tool is a dataset-design diagnostic. It identifies where the current
repeat-first labels contain real alternatives to always-left, which can guide
hard-state balancing, source-family coverage checks, and future label redesign.
It deliberately preserves the negative conclusion from the latest model probe:
the current learned utility model is not ready for online integration.

## Open Questions

- Should future training oversample only states where the baseline is absent
  from `fastest_actions`, or also include baseline tie states as ambiguous hard
  cases?
- Should the next rollout dataset rebalance at export time or build a sampled
  view from mined report states first?
