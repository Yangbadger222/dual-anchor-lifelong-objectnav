# Design Doc: Official TargetNav Interface

Date: 2026-05-31
Owner: Codex
Status: Draft

## Goal

Add a TargetNav interface for the terminal ObjectNav stage. After memory-guided
exploration reacquires the queried object, the policy should estimate a 3D
target coordinate from detector evidence and hand that target to a pluggable
local-navigation backend.

The first Habitat backend is `bbox_depth + occupancy_grid`: project the detector
bbox and depth into the episode-relative frame, set that as a local occupancy
target, and navigate toward a reachable cell near the target before issuing
STOP. Later backends should use Mobile-SAM/depth for target estimation and Nav2
for real-robot execution.

## Non-Goals

- Do not use Habitat episode goal/viewpoint positions.
- Do not use Habitat pathfinder or shortest-path follower.
- Do not claim this is the final learned/local policy.
- Do not change the memory prior format or persistent coordinate frame.
- Do not add Mobile-SAM or Nav2 runtime dependencies in this slice.
- Do not make the occupancy backend the final algorithmic claim.

## Background

The oracle pathfinder suffix produced the first nonzero official success in the
current sequence, but it is benchmark-invalid because it routes to Habitat goal
viewpoints. The next step is to keep the same exploration and memory stack while
using only detector, depth, GPS/compass, and a local navigation backend for the
terminal approach.

This should be framed as a VLFM/Nav2-style interface from the start:

`target_estimator -> targetnav_backend`

The first estimator/backend pair is intentionally simple so it can run inside
Habitat without ROS 2:

`bbox_depth -> occupancy_grid`

## System Boundary

Owned by this slice:

- A new policy:
  `memory_active_perception_frontier_targetnav`.
- Detector bbox/depth target projection using the existing
  `estimate_episode_detection_anchor` logic.
- A small TargetNav backend interface with an occupancy-grid backend.
- Policy/debug traces that record projected target, selected grid cell, and
  fallback reasons.

Dependencies:

- Existing YOLO/Grounding-DINO detector adapters.
- Existing `OccupancyFrontierMap`, GPS/compass frame helpers, and depth update.
- Existing memory-active-perception frontier fallback when no detector target is
  available.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Detector match | bbox/confidence/category | Must match ObjectNav target category. |
| Input | Depth frame | Habitat observation | Used to project bbox to target coordinate. |
| Input | GPS/compass | Habitat observation | Episode-relative target coordinate frame. |
| Output | Occupancy target | `x_m`, `z_m`, grid cell | Stored only in episode-local policy state. |
| Output | Action | ObjectNav action string | `turn_left`, `turn_right`, `move_forward`, or `stop`. |
| Output | Trace/debug | JSON | Records non-oracle target projection and local planner decision. |

## Interfaces

New policy:

```bash
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --policy memory_active_perception_frontier_targetnav
```

Internal helpers:

- `_targetnav_goal_from_detector_match(...)`
- `_targetnav_pointgoal_with_gps_compass(...)`
- `_select_targetnav_occupancy_action(...)`
- `_nearest_free_cell_to_target(...)`
- `_shortest_occupancy_path(...)`
- `_turn_or_move_toward_grid_cell(...)`

## Data Flow

1. Run the existing memory-active-perception frontier policy.
2. On each target detector match, estimate a target coordinate from bbox/depth.
3. Update the occupancy map from the current depth observation.
4. Select the free cell nearest to the projected target.
5. Find a grid path from the agent cell to that selected target-adjacent cell.
6. Turn or move toward the next path cell.
7. Stop when the detector target is centered and range-confirmed, or when the
   agent reaches the selected target-adjacent cell.
8. If projection or path planning fails, fall back to the existing detector
   action/fallback policy.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No depth in bbox | projection returns `None` | Fall back to existing detector action. |
| Projected target outside local grid | no selected cell | Fall back and record reason. |
| No free path to target-adjacent cell | path missing | Fall back to detector action or frontier. |
| Detector false positive | official metrics stay low | Keep detector trace and do not overclaim. |
| Rule-like controller overfits small slice | held-out Habitat smoke fails | Treat as local-planner baseline, not main algorithm. |

## Verification Plan

1. RED/GREEN tests for policy registration and benchmark-valid manifest
   boundary.
2. RED/GREEN tests for bbox/depth target projection into occupancy target state.
3. RED/GREEN tests for local occupancy path action selection.
4. RED/GREEN tests for missing projection/path fallback.
5. Focused local eval/CLI tests and `compileall`.
6. Linux focused tests in `conda habitat`.
7. Linux YOLO smoke on the same four-episode slice, compared against:
   - fixed-controller hand-score baseline;
   - oracle pathfinder suffix diagnostic.

## Benchmark-Valid Backend Direction

The first occupancy-grid backend is a scaffold, not the paper backend. The
`2026-05-31` YOLO smoke showed that refreshing a multi-frame target belief
increased target-match calls from `1` to `48`, but official success and SPL
remained `0`. The failure mode was low-level action execution: the agent spent
`95` steps in `targetnav_occupancy_turn` instead of closing distance.

For benchmark and paper data, the TargetNav online backend must be sensor-only:

- the memory/vision layer outputs a target belief or long-term goal;
- the local navigation backend converts that goal into official Habitat actions;
- Habitat pathfinder may be used only as a teacher or diagnostic, never as the
  online benchmark policy.

Candidate benchmark-valid backends:

- FMM/A* over a depth-built local cost map, following the SemExp-style split
  between goal selection and local navigation;
- a Habitat-baselines PointNav/DDPPO-style local policy conditioned on a
  relative target coordinate;
- a learned TargetNav local policy trained from pathfinder teacher labels, with
  online inputs restricted to RGB-D, pose, target belief, and memory state.

### PointNav/DDPPO Adapter Boundary

The first integration bridge for a Habitat-baselines local policy is a pure
PointGoal adapter, `_targetnav_pointgoal_with_gps_compass(...)`. It converts
the TargetNav episode-local belief coordinate, where `x_m` is right and `z_m`
is forward, into Habitat's polar `pointgoal_with_gps_compass` convention:
`[rho, -phi]`.

The adapter uses only benchmark-valid online state:

- official Habitat GPS, converted from `[forward, right]` into internal
  `(x=right, z=forward)`;
- official Habitat compass, converted to the internal positive-right heading;
- the detector/depth TargetNav belief coordinate.

This helper is not wired into the online policy yet. The current online
`memory_active_perception_frontier_targetnav` behavior still uses the
occupancy-grid scaffold. The adapter exists to make the next backend
replacement explicit: target belief can now be passed to a standard local
PointNav/DDPPO-style controller without changing the memory layer or using a
Habitat goal oracle.

## Research Relevance

This is the first non-oracle terminal-control bridge after memory-guided target
reacquisition. It removes the Habitat goal oracle and introduces the same
architectural boundary needed on the robot: memory and perception produce a
target coordinate; a local navigation backend executes it. The first backend is
occupancy-grid planning inside Habitat, while the paper/robot path can replace
it with Mobile-SAM/depth plus Nav2.

## Open Questions

- Is the projected target coordinate accurate enough from bbox median depth
  without Mobile-SAM refinement?
- Should the planner stop at the target-adjacent free cell or keep approaching
  while detector evidence remains stable?
- How much of the remaining failure is sparse memory/source coverage versus
  terminal local planning?
