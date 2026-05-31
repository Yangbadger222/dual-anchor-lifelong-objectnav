# Design Doc: Official GPS/Compass Frame Correction

Date: 2026-05-30
Owner: Codex
Status: Implemented first slice

## Goal

Correct the official Habitat ObjectNav policy geometry so memory and occupancy
actions interpret `gps` and `compass` in Habitat-Lab's actual episodic sensor
frame.

## Non-Goals

- Do not change Habitat-Lab sensors or task configuration.
- Do not change the lifecycle SQLite world-frame export format.
- Do not claim memory-policy performance from this correction alone.
- Do not introduce target-pose, pathfinder, semantic-mask, or route-follower
  shortcuts.

## Background

The official policy code currently treats the two-dimensional Habitat `gps`
observation as `(x, z)`, with the second component meaning forward. A live
Habitat probe and the Habitat-Lab `EpisodicGPSSensor` implementation show the
opposite convention for the task sensor:

```python
return np.array([-agent_position[2], agent_position[0]], dtype=np.float32)
```

In words, `gps[0]` is forward displacement from the episode start and `gps[1]`
is right/lateral displacement. A live turn probe also showed `turn_right`
changes `compass` by about `-0.5236`, so the policy's internal heading angle
must use `-compass` when using an `x=right, z=forward` local frame.

## System Boundary

The correction belongs inside
`objectnav_core.evaluation.habitat_official_objectnav_eval`, at the boundary
where observations become policy geometry:

- `_observation_xz` converts official Habitat `gps` into the adapter's internal
  local Cartesian frame, `x=right`, `z=forward`.
- `_observation_heading` converts official Habitat `compass` into the same
  positive-right heading convention used by memory bearing and occupancy rays.

All downstream policy code should continue to work in internal `x,z` geometry.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Habitat GPS | `observation["gps"]` | `gps[0]=forward`, `gps[1]=right`. |
| Input | Habitat compass | `observation["compass"]` | Right turns are negative. |
| Output | Internal position | `(x_m, z_m)` | `x=right`, `z=forward`. |
| Output | Internal heading | radians | Positive means right/clockwise in the policy frame. |

## Interfaces

No public CLI or JSON schema changes are required. For
`coordinate_frame="episode_start_relative"` memory priors, `x_m` remains the
right/lateral coordinate and `z_m` remains the forward coordinate in the
episode-start-relative policy frame.

## Data Flow

1. The official evaluator receives Habitat observations.
2. `_observation_xz` maps `[forward, right]` to `(right, forward)`.
3. `_observation_heading` maps raw compass to `-compass`.
4. Memory bearing, stop radius, occupancy grid updates, and frontier bearing
   selection all consume the corrected internal frame.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| GPS components interpreted directly | policy turns toward lateral phantom target | regression test with `gps=[1, 0]` and a forward memory anchor. |
| Compass sign interpreted directly | policy turns farther right when it should recover left | regression test with `compass=-30deg` and a forward memory anchor. |
| World-frame lifecycle anchors mistaken for fixed priors | coordinate-frame selector guard | keep `habitat_world` rejected by default. |

## Verification Plan

1. Add failing tests for the official memory policy with Habitat GPS ordering
   and compass sign.
2. Apply the minimal conversion in `_observation_xz` and
   `_observation_heading`.
3. Run focused official evaluator tests.
4. Run local full tests, `compileall`, and `git diff --check`.
5. Sync to Linux and rerun focused official tests in conda env `habitat`.
6. Run a tiny official smoke to confirm debug behavior still records
   Habitat-provided metrics.

Implemented verification:

- Live Linux Habitat probe showed one `move_forward` changes GPS from
  approximately `[0.0, 0.0]` to `[0.0444, 0.0]`, while one `turn_right` changes
  compass to approximately `-0.5236`.
- RED local regression tests failed before the fix:
  - GPS-order test got `turn_left` instead of `move_forward`.
  - Compass-sign test got `turn_right` instead of `turn_left`.
- GREEN local regression tests passed after the helper fix.
- Local focused official/exporter tests: `33` passed.
- Linux focused official/exporter tests in conda env `habitat`: `33` passed.
- Linux official forward-anchor smoke:
  `runs/habitat_official_objectnav/memory_guided_frontier_episode_frame_forward_probe_1ep_20260530_v1`.
  It emitted five `move_forward` actions then `stop`, with near-zero memory
  bearing error.

## Research Relevance

This is an evaluation-integrity fix. Without it, memory-conditioned official
actions are geometrically rotated relative to Habitat's true episodic sensor
frame. Correcting this is required before any fair memory-prior comparison,
episode-relative memory bridge, or learned memory policy can produce meaningful
official ObjectNav evidence.
