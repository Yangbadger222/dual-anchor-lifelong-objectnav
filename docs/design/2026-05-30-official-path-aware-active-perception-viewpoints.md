# Design Doc: Official Path-Aware Active-Perception Viewpoints

Date: 2026-05-30
Owner: Codex
Status: Implemented; negative diagnostic smoke

## Goal

Make `memory_active_perception_frontier` score physically reachable
viewpoints, not unknown frontier cells. The policy should choose a free cell
from which the remembered anchor can plausibly be scanned, then navigate toward
that cell using online occupancy evidence and official Habitat actions.

## Non-Goals

- Do not use a prior map, target pose, Habitat oracle route follower, semantic
  oracle mask, or lifecycle `habitat_world` anchor for official query actions.
- Do not claim benchmark improvement from the small diagnostic smoke.
- Do not add language/GPT control in this slice.
- Do not train a learned recall model yet; keep the interface ready for one.
- Do not replace official Habitat `success`, `spl`, `soft_spl`, or
  `distance_to_goal` metrics.

## Background

The rotation-aware active-perception fix removed an invalid approach-heading
cosine and made expected evidence positive in traces. The next exposed problem
is deeper: `_select_memory_active_perception_frontier` enumerates unknown
frontier cells and treats them as prospective viewpoints. Unknown cells are
not guaranteed to be traversable, and the current travel penalty is Euclidean
rather than path distance through known free space. This mismatches the paper
story: a robot should actively seek a reachable sensing pose, then rotate or
scan from that pose to confirm remembered evidence.

## System Boundary

Modify the official Habitat evaluator only:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`
- focused official ObjectNav evaluator tests
- docs/devlog/handoff and a smoke report after Linux execution

This remains map-free in the benchmark sense: the occupancy grid is built only
from online depth, GPS, and compass observations inside the current episode.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Occupancy map | `OccupancyFrontierMap` | Online depth-derived free/occupied/unknown grid. |
| Input | Memory anchor | `OfficialMemoryAnchor` | Episode-relative x/right, z/forward anchor. |
| Input | Observation | Mapping with Habitat `gps`, `compass`, `depth` | Used for current cell and heading. |
| Output | Selected candidate | JSON-safe dict | Includes free `viewpoint_cell`, adjacent `frontier_cell`, path/travel cost, and evidence score. |
| Output | Policy action | Habitat discrete action string | Turn or move toward the selected free viewpoint. |

## Interfaces

- Add or update a pure helper that enumerates active-perception candidates as
  `(viewpoint_cell, frontier_cell)` pairs where `viewpoint_cell` is known free
  and adjacent to an unknown frontier cell.
- Add a grid shortest-path helper over known free cells. The selected
  viewpoint should be skipped or heavily penalized when it is unreachable from
  the current free cell.
- Extend selector debug fields:
  `viewpoint_cell`, `frontier_cell`, `path_distance_m`,
  `travel_distance_m`, `expected_evidence`, `score`, and `top_candidates`.
- Preserve existing fields where possible so previous trace consumers do not
  break; `selected_frontier_cell` can remain, with `selected_viewpoint_cell`
  added.

## Data Flow

1. Update the online occupancy map from the current depth observation.
2. Select the matching episode-relative memory anchor.
3. Enumerate unknown frontier cells with at least one free 4-neighbor.
4. For each frontier, enumerate each adjacent free neighbor as a candidate
   viewpoint and deduplicate exact `(viewpoint_cell, frontier_cell)` pairs.
5. Compute shortest path distance from the current cell to the free viewpoint
   through known free cells.
6. Score expected detector evidence from the viewpoint center:

```text
belief = anchor.confidence * exp(-||viewpoint - anchor||^2 / (2 * sigma^2))
view_distance_quality = exp(-((||viewpoint - anchor|| - preferred_view_distance)^2) / (2 * view_sigma^2))
view_bearing_quality = 1.0
expected_evidence = belief * view_distance_quality * view_bearing_quality
score = expected_evidence - travel_distance_weight * path_distance
```

7. Navigate toward the selected free viewpoint using the viewpoint bearing and
   existing center-depth corridor check.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No frontier cells | Selector returns `None` | Fall back to occupancy frontier. |
| Frontier has no free viewpoint neighbor | Candidate enumeration omits it | Continue with other frontiers. |
| Free viewpoint is disconnected from current free space | Shortest path missing | Skip candidate and record lower candidate count. |
| Path-distance tie causes oscillation | Policy trace repeated turn/move pattern | Keep deterministic score tie-breakers and existing blocked fallback. |
| Viewpoint reached but target still absent | Detector trace and policy trace | Future slice should add explicit rotate/scan-at-viewpoint behavior. |
| Small smoke remains negative | Official metrics | Record diagnostic result without overclaiming. |

## Verification Plan

1. RED pure selector test: an unknown frontier cell adjacent to a free
   standoff cell should return the free `viewpoint_cell`, while preserving the
   adjacent `frontier_cell` for audit.
2. RED pure selector test: a Euclidean-near but disconnected free viewpoint is
   rejected or loses to a farther reachable viewpoint because path distance is
   computed through free cells.
3. GREEN implementation for viewpoint enumeration, free-space BFS distance,
   selector debug fields, and policy debug propagation.
4. Local focused official gate, `compileall`, and `git diff --check`.
5. Sync to Linux, rerun the focused gate and hygiene checks in the `habitat`
   conda environment.
6. Run a small detector-backed YOLO smoke only if the online action trace
   changes, and compare official metrics plus active-perception trace counts
   against the rotation-aware frontier-cell smoke.

## Implementation Notes

- Added reachable active-perception candidate enumeration as free
  `viewpoint_cell` plus adjacent unknown `frontier_cell` pairs.
- Added a 4-connected BFS path-distance helper over known free cells.
- Updated `_select_memory_active_perception_frontier` so belief, standoff
  distance, bearing, and travel penalty are computed from the free viewpoint.
- Policy traces now include `selected_viewpoint_cell`, `selected_frontier_cell`,
  `path_distance_m`, and top candidates with viewpoint/frontier pairs.
- Local and Linux focused gates both passed with `96` tests after the change,
  plus compileall and `git diff --check`.
- The four-episode YOLO smoke was negative: official success `0/4`, SPL
  `0.0`, SoftSPL `0.0009902771347611306`, and mean distance-to-goal
  `6.065265536308289`. The previous rotation-aware frontier-cell smoke had
  SoftSPL `0.03315001996589104`.

The result suggests that reachable viewpoint scoring is a better interface but
not sufficient by itself. The policy still chooses a viewpoint every step
without a persistent commitment or explicit rotate/scan behavior once the
viewpoint is reached, so it can trade detector reacquisition for cleaner but
less effective waypoint turns.

## Research Relevance

This turns active perception from a frontier-cell heuristic into a more
robotic formulation: choose a reachable sensing pose under online map
uncertainty, then acquire evidence about a remembered object. It is still a
lightweight model, but its interface is compatible with learned detector
recall, value learning, and later real-robot Nav2 or ROS 2 boundaries because
it separates reachable viewpoint selection from object-memory scoring.

## Open Questions

- Whether the path-distance helper should use only 4-connected free cells or
  allow 8-connected moves for smoother approximate travel cost.
- How to add explicit rotate/scan actions after selecting or reaching a
  viewpoint without turning the policy into brittle hand-authored rules.
