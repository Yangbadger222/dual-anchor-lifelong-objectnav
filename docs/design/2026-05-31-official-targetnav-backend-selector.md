# Design Doc: Official TargetNav Backend Selector

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Make the TargetNav executor backend a first-class official-evaluation
configuration axis for `memory_active_perception_frontier_targetnav`.

The same memory candidate and detector-derived target estimate should be able
to run through `occupancy_grid`, `fmm_grid`, `ddppo_pointnav`, or the privileged
`oracle_follower` diagnostic backend without changing the policy name.

## Non-Goals

- Do not remove the legacy convenience policy names
  `memory_active_perception_frontier_targetnav_fmm` or
  `memory_active_perception_frontier_targetnav_ddppo`.
- Do not claim oracle-backed results as benchmark-valid ObjectNav results.
- Do not change the memory candidate selection logic.
- Do not implement a new learned local controller in this slice.

## Background

The black-box navigation backend design separated the memory contribution from
the executor. The official evaluator already has multiple TargetNav executor
paths, but some are still encoded mostly as separate policy names. This makes
memory ablations harder to read because changing the executor also changes the
policy identifier.

The next paper-useful interface is a backend selector on the base TargetNav
policy. This lets experiments report one memory/query policy with an explicit
executor axis.

## System Boundary

Owned by this slice:

- CLI argument and runner plumbing for `targetnav_backend`;
- protocol manifest reporting for the selected backend;
- diagnostic invalidation when `oracle_follower` is selected;
- regression tests for the selector.

Outside this slice:

- actual Habitat oracle follower mechanics;
- FMM and DDPPO action-selection internals;
- real-robot Nav2 / FASTLIO2 adapters;
- benchmark-scale experiment runs.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | CLI backend selector | `--targetnav-backend` | Choices are the supported TargetNav backend ids. |
| Input | Config backend selector | `OfficialObjectNavRunConfig.targetnav_backend` | Applies to base `memory_active_perception_frontier_targetnav`. |
| Output | Protocol manifest | `manifest["targetnav"]` | Records enabled state, estimator, backend, and source validity. |
| Output | Invalidity reason | `invalid_for_benchmark_claim_reason` | Explicitly flags oracle diagnostic runs. |

## Interfaces

CLI:

```bash
objectnav_habitat_official_objectnav_eval \
  --policy memory_active_perception_frontier_targetnav \
  --targetnav-backend oracle_follower
```

Python:

```python
run_habitat_official_objectnav_eval(
    output_dir,
    policy="memory_active_perception_frontier_targetnav",
    targetnav_backend="fmm_grid",
)
```

Legacy policy aliases remain valid:

- `memory_active_perception_frontier_targetnav_fmm` maps to `fmm_grid`;
- `memory_active_perception_frontier_targetnav_ddppo` maps to `ddppo_pointnav`.

## Data Flow

1. The CLI parses `--targetnav-backend` and passes it to
   `run_habitat_official_objectnav_eval`.
2. The run config validates the backend id.
3. The protocol manifest records the effective backend.
4. The episode loop dispatches the base TargetNav policy to the selected
   backend.
5. If the backend is `oracle_follower`, the run is marked diagnostic-only.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Unsupported backend id | argparse choices or config validation | Fail fast before Habitat work starts. |
| Oracle backend accidentally treated as benchmark-valid | manifest invalidity test | Set source validity and invalid reason explicitly. |
| Legacy policy aliases disagree with selector behavior | manifest and dispatch tests | Keep alias mapping centralized. |
| DDPPO backend selected without checkpoint | config validation | Require checkpoint path before loading backend. |

## Verification Plan

1. Run the failing selector tests before implementation.
2. Add the CLI option and pass it through to the runner.
3. Make `_targetnav_manifest` report the effective backend for the base policy.
4. Run focused CLI/evaluator tests for the selector and existing TargetNav
   backend rows.
5. Run focused syntax/import checks for the modified package.

## Research Relevance

This selector makes executor choice an explicit ablation axis. That supports
the paper story that the contribution is memory quality and reuse, while the
executor can be diagnostic oracle, FMM, learned local policy, or later real
robot Nav2 without changing the memory policy itself.

## Open Questions

- Should future experiment tables collapse the legacy alias policies in favor
  of only the base policy plus `targetnav_backend`?
- Which non-oracle backend should become the main benchmark-valid executor once
  the local-control bottleneck is reduced?
