# Design Doc: Targeted Decision-Boundary Replay Slice

Date: 2026-05-29  
Owner: Codex  
Status: Draft

## Goal

Add an explicit replay-selection interface to the Habitat closed-loop runner so
exact mined `group_id` rows can be rerun without broad balanced-category
sweeps. This is a research-control feature, not a policy change.

## Non-Goals

- Do not change the memory-vs-frontier decision logic.
- Do not add learned selection or ranking inside the runner.
- Do not make the miner depend on Habitat runtime execution.
- Do not replace the existing balanced category selection path.

## Background

The decision-sensitivity miner can now identify rows that are close to a
reliability boundary or actually flip under counterfactual reliability. The
current Habitat runner can select balanced categories, but it cannot yet replay
the exact mined `group_id` rows that are needed for a targeted follow-up slice.

## System Boundary

This feature owns only episode/group selection for the closed-loop Habitat
smoke runner and its CLI. It depends on the existing episode loader, lifecycle
group builder, and summary writer. It must not alter detector logic, route
observation, or reliability estimation.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Target categories | CSV list | Existing balanced-selection path |
| Input | Selected group ids | CSV list of exact `group_id` strings | Optional explicit replay slice |
| Input | Dataset / scene root | Paths | Existing runner inputs |
| Output | Selected groups | Ordered `group_id` list | Either balanced or explicit |
| Output | Summary metadata | JSON | Record requested and selected group ids |

## Interfaces

- `run_habitat_closed_loop_dual_anchor_preflight(..., selected_group_ids=...)`
- `run_habitat_closed_loop_dual_anchor_objectnav(..., selected_group_ids=...)`
- `python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --selected-group-ids ...`

## Data Flow

1. Load candidate episodes for the requested categories.
2. Build lifecycle groups as before.
3. If `selected_group_ids` is provided, filter to those exact groups in the
   requested order and bypass balanced max-group sampling.
4. Otherwise, keep the current balanced category selection path.
5. Write the run summary with both requested and selected group ids.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Requested group id is missing | Validation error before Habitat work starts | Tell the user which ids were not found |
| Duplicate requested group ids | Validation error | Reject the slice as ambiguous |
| Empty explicit slice | Validation error | Require at least one requested group |
| Requested ids exceed current category filter | Validation error | Ask the user to widen categories or adjust the slice |

## Verification Plan

- Unit test the explicit group-id selection helper with synthetic groups.
- Unit test that the CLI forwards `--selected-group-ids`.
- Run the focused Habitat runner test file and the CLI test file.
- Run `python -m py_compile` on touched Python modules.

## Research Relevance

This makes it possible to rerun exact mined boundary rows instead of broad
stable sweeps. That is the missing experiment-control piece for testing whether
event-posterior reliability can actually cross a decision boundary in Habitat.

## Open Questions

- Whether we later need a file-based slice manifest, or whether CSV group ids
  are enough for the first targeted reruns.
