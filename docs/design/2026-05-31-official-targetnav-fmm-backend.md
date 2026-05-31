# Design Doc: Official TargetNav FMM Backend

Date: 2026-05-31
Owner: Codex
Status: Implemented and smoke-tested

## Goal

Add a benchmark-valid local-navigation backend for TargetNav that can consume a
detector/depth target belief and produce official Habitat ObjectNav actions
without Habitat goal poses, pathfinder, shortest-path follower, or persistent
world-frame assumptions.

## Non-Goals

- Do not use Habitat episode goals, view points, pathfinder, or teacher actions
  online.
- Do not remove the existing occupancy-grid TargetNav scaffold; keep it for
  ablation and failure comparison.
- Do not claim benchmark improvement until a Habitat smoke or broader run
  proves it with official metrics.
- Do not install or depend on `habitat_baselines` in this slice. The Linux
  mirror has PointNav configs but not the Python package or checkpoints.

## Background

The `targetnav_belief_active_perception_yolo_4ep_100steps_20260531_v1` smoke
showed that target belief is no longer the immediate bottleneck: target-match
calls increased from `1` to `48`, but official success remained `0/4`. The
tv-monitor episode spent `95` steps in `targetnav_occupancy_turn`.

Trace inspection isolated a concrete local-control failure. At step `5`, the
agent was nearly aligned to the target belief, but the center-depth safety check
reported the forward direction blocked. The current backend then emitted a fixed
blocked turn instead of marking that forward cell as temporarily blocked and
replanning. This produced a left/right turn loop at the same pose.

## System Boundary

Owned by this slice:

- New policy: `memory_active_perception_frontier_targetnav_fmm`.
- A grid distance-field local backend that uses the existing episode-relative
  occupancy map and target belief.
- Debug traces for distance-field planning, selected next cell, blocked-forward
  replanning, and fallback reasons.

Dependencies:

- Existing detector/depth target projection and target-belief smoothing.
- Existing Habitat GPS/compass frame conversion.
- Existing `OccupancyFrontierMap` updates from official depth observations.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Target belief | `x_m`, `z_m`, confidence/debug | Produced from detector bbox plus depth. |
| Input | Occupancy map | `OccupancyFrontierMap` | Built only from online depth and pose. |
| Input | Current observation | Habitat `rgb`, `depth`, `gps`, `compass` | Official online sensors only. |
| Output | Action | ObjectNav action string | `turn_left`, `turn_right`, `move_forward`, `stop`. |
| Output | Debug | JSON trace fields | Backend, selected cells, distance, fallback. |

## Interfaces

CLI:

```bash
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --policy memory_active_perception_frontier_targetnav_fmm
```

Internal helpers:

- `_select_targetnav_fmm_action(...)`
- `_targetnav_distance_field(...)`
- `_targetnav_fmm_next_cell(...)`
- `_forward_grid_cell(...)`
- `_temporarily_blocked_fmm_grid(...)`

## Data Flow

1. Run the same memory-active-perception and detector target reacquisition flow
   used by `memory_active_perception_frontier_targetnav`.
2. Smooth detector/depth target estimates into an episode-relative target
   belief.
3. Update the occupancy map from the current depth frame.
4. Select a reachable free cell nearest to the target belief.
5. Build a distance field from the selected target-adjacent cell over
   traversable free cells.
6. If the agent is aligned with the next forward cell but center depth is
   blocked, mark that forward cell blocked for this decision and recompute.
7. Select the neighbor with the lowest distance-field value and convert it to a
   Habitat action.
8. Fall back to the active-perception frontier policy when projection,
   reachability, or distance-field planning fails.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Target projection missing | No target belief | Existing active-perception fallback. |
| Target-adjacent cell unreachable | No finite distance to current cell | Fallback and trace `no_fmm_path`. |
| Forward cell blocked by live depth | Center depth not clear while selected next cell is forward | Temporarily block forward cell and replan once. |
| Sparse map cannot produce an alternate route | Replanned distance field still invalid | Fallback instead of turn-looping. |
| Detector false positive | Official metrics stay low | Keep detector/debug traces and avoid benchmark claims. |

## Verification Plan

1. RED/GREEN manifest test for the new policy and `fmm_grid` backend metadata.
2. RED/GREEN helper tests for distance-field neighbor selection.
3. RED/GREEN blocked-forward test proving the backend marks the forward cell
   blocked and replans to an alternate free neighbor instead of returning the
   fixed blocked-turn action.
4. RED/GREEN policy-loop test with fake detector/depth observations.
5. Local focused eval/CLI/packaging tests and `compileall`.
6. Linux focused tests in conda env `habitat` and `compileall`.
7. Linux YOLO smoke on the same four-episode slice only after local and Linux
   unit gates pass.

## Implementation Notes

- The FMM backend is implemented as
  `memory_active_perception_frontier_targetnav_fmm`.
- Focused local and Linux tests cover policy registration, clear distance-field
  moves, blocked-forward replanning, fake-env policy dispatch, and a regression
  where FMM must not stop if the only reachable free cell is the current cell
  while the target pointgoal remains outside the stop radius.
- Linux four-episode YOLO smokes were recorded in
  `docs/experiments/2026-05-31-official-targetnav-fmm-yolo-smoke.md`.
- The no-false-stop smoke improved target-match calls from `2` to `77`,
  SoftSPL from `0.0009902771347611306` to `0.01716268349268174`, and mean
  distance from `5.880594372749329` to `5.758422017097473`, but official
  success remained `0/4`.
- Current conclusion: FMM is the right benchmark-valid classical baseline, but
  sparse online map coverage and oscillatory local control still require either
  richer cost-map semantics or a learned local policy trained under the official
  ObjectNav contract.

## Research Relevance

This backend moves the project away from hand-tuned turn rules and toward the
standard ObjectNav decomposition used by stronger systems: semantic memory and
perception produce a target belief, while a local planner follows a sensor-built
cost map. It is still a classical baseline, not the final paper novelty, but it
is benchmark-valid and provides a stronger substrate for the lifelong memory
claim than the current occupancy-turn scaffold.

## Open Questions

- Does the sparse depth-built map have enough free-space coverage for FMM to
  outperform the existing occupancy scaffold on the four-episode smoke?
- Should unknown cells remain blocked for safety, or become high-cost
  traversable cells once exploration coverage improves?
- If FMM fails due sparse maps, should the next backend be a learned local
  policy trained from pathfinder teacher labels rather than more classical
  mapping?
