# Design Doc: Baseline Frontier Policy Switches

Date: 2026-05-24  
Owner: Codex  
Status: Implemented

## Goal

Add explicit ROS-free baseline frontier policy switches for Phase 1A and later replay experiments.

The first supported policies are `nearest_frontier` and `information_gain`, with A* path length used as the path-cost term when the grid goal is reachable.

## Non-Goals

- This design does not add semantic frontier scoring.
- This design does not add ROS 2 Nav2 integration.
- This design does not change detector, memory, or verifier behavior.
- This design does not claim any experiment result across baselines.
- This design does not add a full experiment matrix or plotting workflow.

## Background

The architecture document names repeatable baselines as a required step before paper claims. The code already has:

- frontier extraction
- known-side frontier viewpoint planning
- a simple frontier score formula
- A* grid navigation for offline path cost

The missing piece is a small selector that makes the baseline policy explicit and records which policy produced a candidate.

## System Boundary

Owned by this change:

- policy names for `first_frontier`, `nearest_frontier`, and `information_gain`
- deterministic evaluation of frontier candidates
- A* path-cost calculation for reachable frontier viewpoints
- selection output with score terms for logging and metrics
- optional Phase 1A runner policy configuration

Outside this change:

- semantic / learned frontier scoring
- memory-target scoring
- ROS 2 Nav2 adapter behavior
- experiment report generation

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Grid | `OccupancyGrid` | Candidate viewpoints must be reachable through known free cells. |
| Input | Robot pose | `Pose2D` | Used as A* start pose. |
| Input | Frontier clusters | `list[FrontierCluster]` | Usually from `extract_frontier_clusters`. |
| Input | Policy name | enum/string | `first_frontier`, `nearest_frontier`, or `information_gain`. |
| Output | Selected candidate | dataclass | Contains frontier, viewpoint, path cost, information gain, revisit penalty, score, and candidate type. |

## Interfaces

Add `objectnav_core.planning.frontier_policies`.

Public API:

- `FrontierPolicyName`
- `FrontierPolicyCandidate`
- `select_frontier_candidate(grid, start_pose, frontiers, policy, revisited_frontier_cells=None)`
- `estimate_astar_path_cost_m(grid, start_pose, goal_pose)`

Update `Phase1ATrialRunner`:

- add optional `frontier_policy` constructor parameter
- default to `first_frontier` so current Phase 1A behavior remains stable
- record candidate score terms in frontier-selection event payloads

## Data Flow

1. The runner extracts frontier clusters from the current grid.
2. The selector plans a known-side viewpoint for each cluster.
3. The selector estimates A* path cost from current pose to each viewpoint.
4. Unreachable candidates are ignored.
5. `first_frontier` returns the first reachable candidate in existing cluster order.
6. `nearest_frontier` returns the reachable candidate with lowest A* path cost.
7. `information_gain` returns the candidate with highest `information_gain - path_cost - revisit_penalty`.
8. The runner navigates to the selected viewpoint and logs score terms.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No frontier clusters | Empty input list | Preserve existing no-frontier failure behavior. |
| Viewpoint cannot be planned | `plan_frontier_viewpoint` raises `ValueError` | Skip that candidate. |
| A* cannot reach viewpoint | path-cost helper returns `None` | Skip that candidate. |
| Policy name is invalid | enum conversion raises `ValueError` | Let caller fail fast in tests or configuration validation. |
| All candidates are unreachable | selector raises `ValueError` | Runner treats the trial as unable to observe the target. |

## Verification Plan

- Add a failing test that `nearest_frontier` picks the lowest A* path-cost candidate.
- Add a failing test that `information_gain` can pick a farther frontier when information gain outweighs path cost.
- Add a failing test that the Phase 1A runner accepts the information-gain policy and records it in metrics.
- Run the targeted planning/trial tests.
- Run the full `src/objectnav_core/tests` suite.
- Run compile and core-only ROS-coupling scans.

## Research Relevance

These policy switches make future baseline comparisons reproducible. They separate deterministic geometry baselines from later semantic, memory-aware, and model-assisted policies.

## Open Questions

- Should `information_gain` estimate unknown area behind the frontier rather than frontier cell count?
- Should revisit penalties be persisted across trials or only within one run?
- Should the CLI expose baseline policy selection before the report generator exists?
