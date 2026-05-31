# Design Doc: Official Memory Anchor TargetNav Backend

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Let the official `memory_active_perception_frontier_targetnav` policy execute a
selected remembered object anchor through the configured TargetNav backend.

The previous backend selector made executor choice explicit, but
`oracle_follower` was only activated after a fresh detector target match. This
slice makes the remembered anchor itself executable so memory quality can be
evaluated separately from the sparse-map/FMM local-control bottleneck.

## Non-Goals

- Do not claim oracle-backed memory runs as benchmark-valid ObjectNav results.
- Do not change how memory priors are generated.
- Do not hard-code a scene, vehicle, sensor, or map into the core evaluator.
- Do not replace the active-perception fallback. It remains the fallback when no
  matching memory anchor exists or the selected backend cannot use the anchor.
- Do not solve stale-memory repair or language query parsing in this slice.

## Background

The official TargetNav backend selector can now run the base policy with
`occupancy_grid`, `fmm_grid`, `ddppo_pointnav`, or `oracle_follower`. A Linux
smoke showed that `oracle_follower` activates only when the detector sees the
target in the current episode. That does not isolate memory quality: the robot
is still not navigating to a remembered anchor through the backend.

Official memory priors use `episode_start_relative` anchors with internal
coordinates `x=right`, `z=forward`. Habitat oracle execution needs a 3D
simulator goal. We can invert the existing world-to-episode transform used by
the TargetNav dataset exporter when the episode exposes `start_position` and
`start_rotation`.

## System Boundary

Owned by this slice:

- selecting a matching official memory anchor inside the TargetNav policy when
  no fresh target detector action is available;
- converting that anchor into a TargetNav goal for sensor-depth backends;
- converting that anchor into a Habitat 3D goal for the oracle diagnostic
  backend when episode start pose is available;
- debug payloads that show the selected anchor, conversion, backend, and
  diagnostic-only status;
- regression tests for non-oracle and oracle memory-anchor execution.

Outside this slice:

- memory-prior discovery/training;
- object detector model quality;
- DDPPO checkpoint contract fixes;
- real robot Nav2/FASTLIO2 implementation;
- language/GPT API.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Memory anchor | `OfficialMemoryAnchor` | Must match target category, scene, confidence, and `episode_start_relative` frame. |
| Input | Episode start pose | Habitat episode `start_position`, `start_rotation` | Needed only for oracle world-goal conversion. |
| Input | Backend selector | `targetnav_backend` | Existing selector: `occupancy_grid`, `fmm_grid`, `ddppo_pointnav`, `oracle_follower`. |
| Output | TargetNav goal | dict with `x_m`, `z_m`, metadata | Used by occupancy/FMM/DDPPO TargetNav paths. |
| Output | Oracle goal position | `(x, y, z)` Habitat world tuple | Diagnostic-only privileged target for `HabitatOracleFollowerBackend`. |
| Output | Debug trace | `policy_debug.memory_prior`, `policy_debug.targetnav` | Must label oracle runs as non-benchmark-valid. |

## Interfaces

CLI stays the same:

```bash
objectnav_habitat_official_objectnav_eval \
  --policy memory_active_perception_frontier_targetnav \
  --targetnav-backend oracle_follower \
  --memory-prior-path path/to/memory_prior.json
```

Internal helpers:

- `_targetnav_goal_from_memory_anchor(anchor)`
- `_memory_anchor_oracle_goal_position(state, anchor)`
- `_episode_relative_xz_to_world_position(...)`
- `_activate_and_select_memory_anchor_oracle_action(...)`

## Data Flow

1. The policy first continues any active oracle/pathfinder goal.
2. A fresh detector target match still takes precedence because it is direct
   current evidence.
3. If no detector action applies, select the matching memory anchor.
4. For `oracle_follower`, transform the anchor from episode-relative `x/z` into
   a Habitat world goal and follow it through the oracle backend.
5. For non-oracle TargetNav backends, pass the anchor as the `target_goal`.
6. If no anchor exists or conversion/execution fails, fall back to the existing
   active-perception frontier policy.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No matching anchor | `select_official_memory_anchor` returns `None` | Existing active-perception/occupancy fallback. |
| Unsupported anchor frame | `coordinate_frame != episode_start_relative` | Fallback and debug reason. |
| Missing episode start pose for oracle | transform returns `None` | Fallback and debug reason. |
| Invalid quaternion/start pose | parse or finite checks fail | Fallback and debug reason. |
| Oracle backend unavailable | controller returns `None` or failed status | Fallback and debug reason. |
| Stale or wrong memory | Official metrics/detector trace show failure | Future stale-memory repair/evidence model, not this slice. |

## Verification Plan

1. Add unit tests that fail before implementation:
   - base TargetNav with `fmm_grid` uses a memory anchor as the TargetNav goal;
   - base TargetNav with `oracle_follower` converts a memory anchor into a
     Habitat world goal and follows it;
   - oracle conversion fails clearly when start pose is missing.
2. Implement the minimal helper path and debug payloads.
3. Run focused evaluator tests locally.
4. Run compile and whitespace checks locally.
5. Sync to the Linux Habitat host and run focused tests.
6. Run a small diagnostic Habitat smoke with the base policy and
   `--targetnav-backend oracle_follower`; label it diagnostic only.

## Research Relevance

This is the first clean experiment boundary for the paper story:

- memory chooses an old object anchor;
- a backend executes that anchor;
- official metrics and debug traces tell us whether memory, detector evidence,
  or local execution is the bottleneck.

It also prepares the real robot path: the memory layer can produce a goal while
the backend can later be Nav2/FASTLIO2 instead of Habitat oracle/FMM.

## Open Questions

- Should stale-memory repair be handled before backend execution or after a
  failed verification at the remembered location?
- Should future memory priors store an optional height/floor estimate to improve
  oracle and Nav2 goal construction?
- Which non-oracle backend should become the primary benchmark-valid executor?
