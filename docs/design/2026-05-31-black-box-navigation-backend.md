# Design Doc: Black-Box Navigation Backend Boundary

Date: 2026-05-31
Owner: Codex
Status: Draft

## Goal

Introduce a ROS-free navigation backend boundary so the paper contribution can
stay focused on lifelong object memory while lower-level navigation remains a
replaceable black box.

The memory/query layer should ask for:

- current pose;
- go to a candidate pose;
- explore a region;
- report/cancel status.

Habitat, FMM, learned local policies, Nav2, and the real FASTLIO2/Nav stack
should all live behind that boundary.

## Non-Goals

- Do not replace the existing official Habitat evaluator in this slice.
- Do not implement a new planner or controller.
- Do not add ROS 2 imports to `objectnav_core`.
- Do not claim navigation performance improvement from an interface-only slice.
- Do not hard-code the real robot, a campus map, a sensor topic, or a device
  path into the core.

## Background

The first official comparison table showed that the current memory-guided row
is dominated by low-level TargetNav/FMM failures:

- `memory_guided`: SR `0/4`, SPL `0.0`, SoftSPL `0.0172`;
- `no_memory`: SR `0/4`, SPL `0.0`, SoftSPL `0.0332`;
- `naive_count`: SR `0/4`, SPL `0.0`, SoftSPL `0.0010`.

This confirms the user's strategic point: lower-level navigation should be a
black box, not the paper's main claim. The repo already has core `Pose2D` and
`NavigationStatus`, a ROS Nav2 client, and simulation navigation clients, but
there is no single core interface that memory code can target.

## System Boundary

Owned by this slice:

- core navigation request/result models;
- a `NavigationBackend` protocol;
- a small adapter for existing `send_goal` / `cancel_goal` clients;
- a Habitat oracle shortest-path follower backend for simulation upper-bound
  memory experiments;
- wiring the existing official `pathfinder_suffix` diagnostic controller
  through that oracle backend boundary;
- tests proving the boundary works with the current discrete simulation client.

Outside this slice:

- Habitat official action stepping;
- Nav2 ROS action implementation;
- FASTLIO2/SLAM integration;
- learned local-policy training;
- language/GPT query parsing.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Navigation goal | `NavigationGoal` | Pose, frame, tolerance, source, metadata. |
| Input | Exploration request | `ExplorationRequest` | Optional center/radius/strategy for region exploration. |
| Input | Backend client | Python object | Existing client with `send_goal`, `cancel_goal`, `status`, and optional pose fields. |
| Input | Habitat oracle goal | `NavigationGoal.metadata["habitat_goal_position"]` | Privileged 3D simulator goal for upper-bound runs only. |
| Output | Backend status | `NavigationBackendStatus` | Status, pose, active goal id, reason, path length. |

## Interfaces

Core module:

```python
from objectnav_core.navigation.backend import (
    ExplorationRequest,
    LegacyNavigationClientBackend,
    NavigationBackend,
    NavigationBackendStatus,
    NavigationGoal,
)
```

Protocol:

```python
backend.get_pose() -> Pose2D | None
backend.go_to(goal: NavigationGoal) -> NavigationBackendStatus
backend.explore(request: ExplorationRequest) -> NavigationBackendStatus
backend.status() -> NavigationBackendStatus
backend.cancel() -> NavigationBackendStatus
```

Habitat oracle executor:

```python
from objectnav_core.navigation.habitat_oracle import HabitatOracleFollowerBackend

backend.go_to(
    NavigationGoal(
        goal_id="oracle-memory-goal",
        pose=Pose2D(x=0.0, y=0.0),
        frame_id="episode",
        source="memory_upper_bound",
        metadata={"habitat_goal_position": [1.0, 0.0, 2.0]},
    )
)
backend.next_action()  # "move_forward", "turn_left", "turn_right", or "stop"
```

This backend is explicitly privileged. It should be used to isolate memory
quality from local-control failures, not as benchmark-valid ObjectNav evidence.

## Data Flow

1. Memory query returns one or more candidate `Pose2D` goals.
2. The ObjectNav manager wraps the selected candidate as a `NavigationGoal`.
3. The configured backend receives `go_to(goal)`.
4. The backend executes with its own planner/controller.
5. The memory layer observes `NavigationBackendStatus` and decides whether to
   trust, verify, retry, explore, retire, or query another candidate.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Backend lacks required methods | protocol/adapter tests fail | Wrap through an explicit adapter. |
| Backend returns no pose | `pose=None` in status | Memory can still reason from goal/status; pose-dependent logic must wait. |
| Explore request lacks actionable region | failed status with reason | Caller falls back to no-memory search or another candidate. |
| Oracle follower receives non-Habitat frame | failed status with reason | Require explicit `habitat_goal_position` unless the goal is tagged `habitat_world`. |
| Oracle follower unavailable | failed status with reason | Fall back to non-oracle backend or skip upper-bound row. |
| Nav2/FASTLIO2 frame mismatch | frame id carried in `NavigationGoal` | Adapter owns transform/ROS frame handling outside core. |
| Interface hides useful diagnostics | metadata/reason fields are missing | Backends can attach structured metadata without changing the protocol. |

## Verification Plan

1. Unit-test validation of goal ids, frame ids, tolerances, and explore radius.
2. Unit-test that a legacy discrete simulation client can be wrapped and driven
   through `go_to`.
3. Unit-test that `explore` uses a region center when provided and fails clearly
   when no target region is available.
4. Unit-test cancel/status mapping.
5. Unit-test Habitat oracle follower goal validation, action mapping, stop
   handling, cancel handling, and explicit privileged metadata.
6. Unit-test that the official pathfinder suffix controller uses the oracle
   backend boundary while preserving diagnostic-only status.
7. Run focused local core/evaluator tests and syntax checks.
8. Sync to Linux and run the same focused tests in conda env `habitat`.

## Research Relevance

This boundary makes the paper claim cleaner:

- memory produces candidate goals and confidence;
- black-box navigation executes;
- evaluation compares memory value under the same backend.

It also keeps the real robot path sane. On the robot, FASTLIO2/SLAM and Nav2
can supply pose and goal execution through an adapter, while the core memory
system remains hardware-independent and testable in Habitat first.

## Open Questions

- Should the official memory/TargetNav policies receive a first-class backend
  selector, or should only diagnostic suffix policies use action backend
  wrappers?
- Should exploration be an explicit `ExplorationRequest` or a special
  `NavigationGoal` type?
- Which backend becomes the first paper primary: Nav2-like planner in sim,
  official-contract learned local policy, or a mature external ObjectNav stack?
