# Design Doc: Memory-Conditioned Local Active Search

Date: 2026-05-30
Owner: Codex
Status: First deterministic implementation tested; needs redesign

## Goal

Turn a remembered object pose into a local active-search prior instead of only a
terminal navigation goal. When current evidence says the memory is stale,
uncertain, or not directly confirmed, the robot should search nearby high-value
viewpoints before falling back to broad target-agnostic frontier exploration.

The immediate Habitat target is to improve goal-object relocation recovery
without simply increasing random navmesh probe count.

## Non-Goals

- Do not claim official ObjectNav SPL from this intermediate runner.
- Do not use the relocated target pose, semantic instance id, or oracle target
  visibility to choose search viewpoints.
- Do not hard-code one scene, category, campus, robot, camera, or route.
- Do not replace learned memory validity; use it as one input to deciding
  whether to stop at memory, search locally, or go global.
- Do not tune thresholds around the current `toilet`, `tv_monitor`, or `sofa`
  rows as final paper settings.

## Background

The 2026-05-30 per-action matrix showed that route-level observation is the
first current-code mechanism to improve success:

- Stable `per_action` reaches memory-guided `6/6` after the unavailable
  frontier fix.
- Relocation `per_action` reaches memory-guided `3/6`, compared with
  frontier-only `2/6`.
- The relocated `sofa` row succeeds only when stale memory seeds a
  post-memory local frontier route.

High-budget relocation probes add the next constraint:

- `tv_monitor` can be recovered with `8x4` probes, but memory-guided still
  needs `684` actions.
- One reverse `chair` relocation can be recovered in `190` actions.
- `toilet` still fails after `8x4` probes.

This says the remaining problem is not just "more probes." The search policy
needs to use memory geometry and observations to choose better local probes.

## System Boundary

The new policy belongs in the Habitat closed-loop evaluation layer. It may use:

- transformed memory pose and covariance;
- memory-validity probability and reliability components;
- current memory-route evidence;
- route observations already collected during per-action execution;
- navmesh reachability and action-route costs;
- detector confirmation events.

It must not use ground-truth target pose or oracle target pixels to choose
where to search. Oracle overlap remains audit-only for simulation reports.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Memory anchor | pose, rotation, covariance, source | Center of local search prior. |
| Input | Validity estimate | event-posterior or learned probability | Decides stop/search/global preference. |
| Input | Route observations | per-action evidence payloads | Updates local belief and stopping. |
| Input | Navmesh sampler | Habitat pathfinder / route follower | Provides reachable candidate viewpoints. |
| Input | Detector events | confirmed/suppressed observations | Updates target likelihood. |
| Output | Local search candidate list | ordered route goals / headings | Candidate viewpoints chosen without target oracle. |
| Output | Search trace | JSON row payload | Candidate scores, selected probes, evidence, stop reason. |
| Output | Policy decision | `memory_first`, `local_search_first`, `frontier_first` | Auditable decision mode. |

## Interfaces

Implemented CLI additions:

```bash
--post-memory-search-mode frontier_mode|navmesh_frontier|memory_local_active
--local-search-radii-m 1.0,2.0,4.0
--local-search-probe-count 8
--local-search-heading-count 4
--local-search-score-mode distance_prior|belief_gain
```

Implemented Python helpers:

- `LocalSearchCandidate`
- `MemoryLocalSearchConfig`
- `_memory_local_probe_goals(...)`
- `_memory_local_active_result(...)`
- `_habitat_memory_local_active_result(...)`
- `_effective_post_memory_search_mode(...)`

The default `--post-memory-search-mode frontier_mode` preserves the current
behavior: post-memory repair uses the selected global `--frontier-mode`.
`memory_local_active` changes only the post-memory repair route, leaving the
query-start frontier baseline matched.

First-pass limitation: the current local policy is deterministic radial search
around the memory anchor. It records source labels and selected evidence, but it
does not yet persist the full candidate-score list into row JSON and it is not
yet a learned active-search policy.

## Data Flow

1. The runner computes memory evidence and validity as it does today.
2. If memory evidence is confirmed and expected utility favors direct memory,
   the agent can stop at memory as before.
3. If memory is unconfirmed, stale, or low-validity, the policy builds a local
   belief around the transformed memory anchor.
4. Candidate local probes are generated from reachable navmesh points near the
   memory anchor, using expanding radial rings. The first local implementation
   snaps radial samples to the navmesh when Habitat exposes `snap_point`.
5. Candidates receive a simple distance-prior or belief-gain score and are
   executed through the same route follower and detector-confirmation path as
   `navmesh_frontier`.
6. The selected route is executed with per-action observation.
7. Confirmed detector evidence stops the search and records a repaired anchor.
8. If the local budget expires without confirmation, the row records a local
   miss. The matched query-start frontier baseline remains available for
   comparison; a second sequential global fallback after local miss is future
   work.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Local search overfits current rows | Held-out category/scene success drops | Keep configs explicit and rerun broader slices. |
| Search becomes hand-tuned radii | Sensitivity table shows fragile radius wins | Compare radius schedules and learn scoring weights from row traces. |
| Detector false positives stop search | `detector_false_confirmation_counts` rises | Require multiview confirmation and keep oracle overlap as audit only. |
| Memory anchor is far from relocated target | Local budget expires repeatedly | Fall back to global frontier and record local miss. |
| Probe generation is unreachable or degenerate | zero-action or no-route candidates | Reuse unavailable-frontier guard and log rejected probes. |
| Learned validity rejects useful local prior | local search skipped despite nearby target | Separate "memory valid for stop" from "memory useful as search prior." |

## Verification Plan

1. Unit-test candidate generation:
   - deterministic for the same group id and memory pose;
   - excludes unreachable/zero-action failed probes;
   - respects radius and probe-count limits.
2. Unit-test scoring:
   - lower action cost wins when evidence likelihood ties;
   - suppressed detector history lowers candidate score;
   - memory-validity affects stop-vs-search, not whether memory can seed local
     search.
3. Run selected replays:
   - relocated `sofa` should remain successful and not regress;
   - relocated `tv_monitor` should improve over `684` high-budget actions;
   - relocated `toilet` is the stress case.
4. Run matched balanced6 stable and relocation matrices.
5. Only after balanced6 improves, scale to larger category/scene slices with
   confidence intervals.

Local verification completed on 2026-05-30:

- deterministic radial candidate generation;
- custom `memory_local_active_probe:*` source labels;
- pure local-active route composition;
- CLI and preflight config recording;
- unavailable post-memory repair does not act like a zero-cost option;
- `python3 -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q`.

Selected Habitat replay result on 2026-05-30:

- `memory_local_active` radial search: `0/4` selected relocation successes,
  `767` memory-guided actions.
- Matched navmesh post-memory repair: `1/4` selected relocation successes,
  `1195` memory-guided actions.
- Conclusion: deterministic radial local search is cheaper on misses but
  regresses the known `sofa` repair. The next design iteration should use
  occupancy/depth visibility or learned candidate scoring rather than scaling
  this radial policy.

## Research Relevance

This design makes the contribution more than a calibrated memory-validity
classifier. The paper story becomes:

> dual-anchor memory supplies a persistent spatial prior; learned validity
> decides whether to trust that prior as a stop target; local active search
> uses the same prior to recover relocated objects when direct memory is stale.

That is closer to the intended robot setting: a remembered object may be gone
from its exact pose but still strongly constrains where the robot should search.

## Open Questions

- Should candidate scoring be a fixed information-gain formula first, then a
  learned scorer, or should the next step go directly to learned scoring from
  route traces?
- How should local search radius depend on category, room geometry, or observed
  relocation distance without becoming a hand-tuned benchmark trick?
- Should local search run before or after visiting the stale memory endpoint
  when learned validity is very low?
- Which representation should survive to the real robot: local occupancy
  frontiers, topological room regions, or memory-centered route proposals?
