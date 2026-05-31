# Design Doc: Official Temporal Local Action-Effect Dataset

Date: 2026-05-30
Owner: Codex
Status: Implemented; 20-episode YOLO trace export completed

## Goal

Extend the official local action-effect dataset with temporal evidence and
action-history features. The exporter should make it possible to train a
short-horizon local controller that notices when detector evidence is becoming
fragile, rather than only predicting next-frame target visibility from a single
frame.

## Non-Goals

- Do not change official Habitat metric handling.
- Do not add a new online policy in this slice.
- Do not use oracle semantics, geodesic distance, shortest paths, or future
  observations as online features.
- Do not claim benchmark improvement from offline dataset features.
- Do not make the exporter Habitat-dependent; it should continue consuming
  only official trace JSON artifacts.

## Background

The `memory_evidence_frontier` policy and the fixed
`memory_learned_local_frontier` policy both reach the same bottleneck: in the
target `tv_monitor` episode, the robot sees the object at the image edge, moves
forward, gets closer by depth, but bbox area shrinks and center offset grows
until target evidence disappears. The one-step logistic scorer cannot
distinguish this trend robustly because it sees only the current frame.

For a robotics-paper-quality controller, the next learning substrate should
encode short temporal context:

- how many recent frames contained target evidence;
- whether confidence, bbox area, depth, and center offset are improving;
- whether the recent action sequence has been turning, reacquiring, or moving
  forward;
- whether the target remains visible over a short horizon.

## System Boundary

Modify the existing official dataset exporter:

- `objectnav_core.evaluation.habitat_official_local_action_dataset`
- `objectnav_core.cli.export_habitat_official_local_action_dataset`
- focused dataset tests

The exporter still consumes `policy_trace.json` and `detector_trace.json`
only. It should remain pure Python and independent of Habitat, detectors, and
robot hardware.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | `policy_trace.json` | Official policy steps, action, decision, pose, debug evidence. |
| Input | Detector trace | `detector_trace.json` | Optional target-match evidence by step. |
| Output | Dataset JSON | schema `official-local-action-effect-v2` | Adds temporal features and short-horizon labels. |
| Output | CSV | flat table | Stable columns for temporal features and labels. |

## Interfaces

Python API:

```python
export_official_local_action_dataset(
    policy_trace_path,
    detector_trace_path=detector_trace_path,
    source_run_id="...",
    history_steps=3,
    horizon_steps=3,
)
```

CLI:

```bash
python -m objectnav_core.cli.export_habitat_official_local_action_dataset \
  <policy_trace.json> \
  --detector-trace <detector_trace.json> \
  --output <dataset.json> \
  --csv-output <examples.csv> \
  --history-steps 3 \
  --horizon-steps 3
```

## Data Flow

1. Load policy steps and detector evidence as before.
2. Merge policy-debug detector evidence into each step's evidence snapshot.
3. For each consecutive action step, collect up to `history_steps` previous
   steps in the same episode.
4. Compute pre-action temporal features only from current/past evidence:
   previous visibility, recent visible count, steps since last visible,
   previous action/decision, action counts, confidence/area/depth/offset
   deltas, and whether either turn direction is currently suppressed.
5. Collect up to `horizon_steps` future steps in the same episode for labels
   only.
6. Compute short-horizon labels: visible at any horizon step, visible at final
   horizon step, lost within horizon, first loss step, and evidence deltas to
   the best visible future frame.
7. Write JSON and CSV with explicit feature and label schemas.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Trace has episode boundary gaps | History/horizon lookup sees different episode keys | Stop context at boundaries; keep example if immediate next step is consecutive. |
| Detector evidence exists only in policy debug | Unit tests use official trace shape where detector trace lacks derived bbox fields | Merge debug evidence before temporal feature computation. |
| No future horizon steps available near budget stop | Horizon step count is shorter than requested | Record `horizon_observed_step_count`; do not fabricate labels. |
| Temporal features leak future observations | Code review/tests inspect feature values from past-only synthetic traces | Keep all future-derived values under `labels`, never `features`. |
| CSV schema drifts silently | Stable-header tests fail | Extend `_CSV_FIELDS` from schema constants. |

## Verification Plan

1. RED synthetic dataset test:
   - step `0` visible;
   - step `1` visible with lower area and higher offset;
   - step `2` visible with further degradation;
   - step `3` target lost.
   Assert temporal features on step `2` use only steps `0..2`, and horizon
   labels see the loss at step `3`.
2. RED CLI test for `--history-steps` and `--horizon-steps`.
3. GREEN exporter implementation.
4. Run focused local dataset/model/official tests.
5. Run `compileall` and `git diff --check`.
6. Mirror to Linux, run the same focused gate, and export v2 datasets from the
   latest official YOLO traces.

Completed verification:

- Local focused official-memory/exporter/model/evaluator gate: `81` passed.
- Local `compileall` and `git diff --check`: clean.
- Linux focused official gate in env `habitat`: `81` passed.
- Linux `compileall` and `git diff --check`: clean.
- Exported a four-episode temporal dataset from the fixed learned-local trace:
  `196` examples, `5` visible-before examples, `5` visible-after examples.
- Exported a 20-episode temporal dataset from a larger YOLO discovery/query
  trace: `1580` examples, `500` visible-before examples, `498` visible-after
  examples.

## Result Update

The v2 exporter exposes the trend that the one-frame scorer missed. In the
four-episode target slice, the forward approach gets closer by depth while bbox
area drops and absolute center offset grows before target loss. In the larger
20-episode trace, temporal features provide enough nontrivial signal for an
offline logistic smoke: a temporal feature set reduced log loss from `0.174072`
to `0.059308` compared with the previous default feature set on the same
`next_target_visible` label. This remains an offline diagnostic; online
benchmark progress still requires a policy that carries the same temporal state
at runtime and improves official Habitat success/SPL.

## Research Relevance

This is the data layer for a publishable local controller. It keeps benchmark
claims clean while giving the learned policy the minimum temporal substrate
needed to reason about detector evidence trends. The same trace schema can be
produced by a real robot, so the design remains connected to the car and not
just Habitat.

## Open Questions

- Whether the first short-horizon controller should score single actions with
  temporal features or score short action sequences directly.
- Whether horizon labels should optimize visibility retention, bbox quality, or
  downstream official distance-to-goal proxy.
- How much larger the official trace corpus must be before online learned
  control is credible.
