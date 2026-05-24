# Design Doc: A* Grid Navigation Backend

Date: 2026-05-24  
Owner: Codex  
Status: Implemented

## Goal

Add a ROS-free A* grid navigation backend for offline ObjectNav verification.

The backend should make path cost and reachability explicit before the project connects the same core interfaces to ROS 2 Nav2.

## Non-Goals

- This design does not replace Nav2 for real robot execution.
- This design does not add ROS 2, TF, costmap, controller, or action-client code.
- This design does not change the default Phase 1A trial runner behavior.
- This design does not model robot footprint inflation, dynamic obstacles, recovery behaviors, or local control.

## Background

Phase 1A currently has `DiscreteStepNavigationClient`, which moves in a straight line toward a goal. That is useful for a tiny deterministic slice but too optimistic for frontier and memory-goal evaluation.

The architecture document already names A* as the next offline navigation backend before a Nav2 `NavigateToPose` adapter. A* gives the core a deterministic way to answer:

- is this grid goal reachable through known free space?
- what is the path length cost?
- does a planner avoid occupied and unknown cells?

## System Boundary

Owned by this backend:

- A* search over `OccupancyGrid`
- conversion between world poses and grid cells
- deterministic path execution with the existing navigation-client shape
- failure reporting for blocked starts, blocked goals, and no path

Outside this backend:

- ROS 2 Nav2 execution
- map inflation and footprint collision checking
- replanning on map updates
- recovery behaviors
- ObjectNav policy changes

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Grid | `OccupancyGrid` | Only free cells are traversable. Unknown and occupied cells block planning. |
| Input | Start pose | `Pose2D` | Converted to the nearest grid cell through `world_to_cell`. |
| Input | Goal pose | `Pose2D` | Must land in a free cell. Final yaw comes from the requested goal. |
| Output | Navigation status | `NavigationStatus` | `SUCCEEDED`, `FAILED`, or `CANCELED` through the same style as the discrete client. |
| Output | Path length | meters | Accumulated while ticking along the planned path. |
| Output | Result reason | string | Examples: `goal_reached`, `start_not_free`, `goal_not_free`, `no_path`, `canceled`. |

## Interfaces

Add `AStarGridNavigationClient` under `objectnav_core.simulation.navigation`.

Expected public methods and fields:

- `send_goal(goal_pose: Pose2D) -> None`
- `cancel_goal() -> None`
- `tick(dt: float) -> NavigationStatus`
- `status: NavigationStatus`
- `current_pose: Pose2D`
- `goal_pose: Pose2D | None`
- `path_length_m: float`
- `result_reason: str | None`
- `planned_path: list[Pose2D]`

The interface intentionally resembles `DiscreteStepNavigationClient` so later code can select a backend without changing ObjectNav manager logic.

## Data Flow

1. The caller creates the client with a grid and start pose.
2. `send_goal` validates that start and goal cells are free.
3. The client runs A* over 4-connected grid neighbors.
4. If no path exists, status becomes `FAILED`.
5. If a path exists, status becomes `ACTIVE` and `planned_path` stores cell-center poses.
6. Each `tick(dt)` advances along the path by `step_size_m * dt`.
7. Reaching the final waypoint sets the exact requested goal pose and returns `SUCCEEDED`.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Start is unknown or occupied | `grid.is_free_cell(start_col, start_row)` is false | Fail immediately with `start_not_free`. |
| Goal is unknown or occupied | `grid.is_free_cell(goal_col, goal_row)` is false | Fail immediately with `goal_not_free`. |
| No path through known free cells | A* exhausts the open set | Fail with `no_path`. |
| Tick called while idle, failed, succeeded, or canceled | Status is not `ACTIVE` | Return current status without side effects. |
| Oversized tick step | Step is larger than remaining waypoint distance | Consume waypoints until the step is spent or the goal is reached. |

## Verification Plan

- Add a failing test that A* detours around an occupied obstacle and produces a longer-than-straight path.
- Add a failing test that an unknown gap blocks planning until the gap is revealed as free.
- Add a failing test that `cancel_goal` preserves the expected canceled status and reason.
- Run the full `src/objectnav_core/tests` suite.
- Run `python3 -m compileall -q src/objectnav_core/objectnav_core`.
- Run a core-only ROS-coupling scan.

## Research Relevance

A* gives the project a deterministic path-cost backend for offline baseline and ablation work. It helps separate ObjectNav policy behavior from real-robot Nav2 integration issues while preserving the later adapter boundary.

## Open Questions

- Should path planning use 8-connected neighbors after Phase 1A?
- Should obstacle inflation be added before or after baseline policy switches?
- Should future reports include A* path visualizations next to frontier and memory decisions?
