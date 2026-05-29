# Design Doc: Habitat Goal-Object Relocation Challenge

Date: 2026-05-30
Owner: Codex
Status: Draft

## Goal

Add a Habitat closed-loop challenge that creates a stronger lifelong ObjectNav
memory test without editing HM3D meshes: the robot discovers one object
instance, then the query targets a different same-category instance in the same
scene. This makes the stored memory stale at the instance level while preserving
category semantics and real Habitat geometry.

## Non-Goals

- Do not claim official Habitat ObjectNav benchmark performance from this
  proxy.
- Do not physically remove or move HM3D objects in this slice.
- Do not tune detector thresholds or reliability constants for a selected
  category.
- Do not change the existing `stable`, `ambiguous`, or `stale_proxy` semantics.
- Do not make category-level ObjectNav claims from instance-scoped success.

## Background

Current per-action event-posterior runs found useful detector-event signal, but
the decision boundary often sits at the non-flippable edge because the
post-memory fallback route can rediscover the same object almost immediately.
Option-end rows have healthier interior boundaries, but some are dominated by
detector endpoint misses rather than memory reliability.

HM3D ObjectNav `val` contains many same-scene, same-category groups with
different `closest_goal_object_id` values. Pairing those groups gives a
controlled relocation proxy:

- discovery memory comes from object instance A;
- query/fallback target is object instance B;
- verification uses query instance B, so routeing to instance A is no longer a
  valid stop;
- no simulator mesh editing is required.

## System Boundary

This challenge belongs to the Habitat closed-loop runner and its selection
helpers. It depends on the existing lifecycle group builder, explicit replay
selection, Grounding-DINO/oracle evidence verifier, and decision-sensitivity
miner.

The core dual-anchor geometry and planner utilities remain Habitat-independent.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Challenge | `goal_object_relocation` | New Habitat runner challenge |
| Input | Base lifecycle groups | Existing `LifecycleGroup` list | Pairs must share scene and category |
| Input | Semantic scope | Goal-object id for relocation | Falls back to category scope for existing challenges |
| Input | Selected group ids | CSV of relocated group ids | Optional explicit replay |
| Output | Relocated group ids | `scene|category|relocated:<old>-><new>` | Stable and auditable |
| Output | Summary rows | Existing row schema | Include challenge and selected group ids |
| Output | Decision-sensitivity reports | Existing miner outputs | Should expose interior-boundary rows |

## Interfaces

- CLI:
  - `--challenge goal_object_relocation`
  - existing `--selected-group-ids` for explicit relocated pair replay
- Runner helpers:
  - build relocated lifecycle groups from base groups;
  - resolve discovery target semantic ids separately from query target semantic
    ids;
  - use discovery ids only when selecting the memory anchor;
  - use query ids for memory verification, fallback verification, route
    observation, and navmesh probe verification.

## Data Flow

1. Load ObjectNav episodes and build normal lifecycle groups by scene,
   category, and `goal_object:<id>`.
2. If `challenge == goal_object_relocation`, pair groups within each
   `(scene, category)` bucket where old and new goal-object ids differ.
3. Each relocated group uses the old group's discovery episode for memory and
   the new group's query episode for current task/fallback.
4. Memory anchor candidate generation uses the old goal-object semantic id.
5. Query-time memory, fallback, post-memory fallback, and route observations use
   the new goal-object semantic id.
6. The existing expected-utility decision and reliability modes consume the
   resulting action counts and evidence payloads unchanged.
7. The miner ranks the generated rows using existing boundary and event fields.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Episode lacks instance id | Relocation builder skips non-`goal_object` ids | Keep category-scope behavior for other challenges |
| Semantic id not present in simulator category map | Helper falls back to category ids and records tests for valid ids | Start with groups whose ids resolve cleanly |
| Old and new instances are visually adjacent | Low post-memory fallback cost / boundary edge | Miner reports boundary region and post-memory fallback horizon |
| Instance-scoped task is confused with official category ObjectNav | Report challenge name and caveat in docs | Keep official/category benchmark claims separate |
| Detector misses new target | Summary shows detector miss and failure bucket | Treat as detector-limited, not memory improvement |

## Verification Plan

- Unit tests for relocated group pairing and group-id format.
- Unit tests for goal-object semantic id resolution and category fallback.
- Unit tests that relocation uses old semantic ids for memory anchor generation
  and new semantic ids for query verification.
- CLI/preflight test accepting `goal_object_relocation`.
- Local focused Habitat closed-loop/CLI tests and `py_compile`.
- Linux preflight with `--challenge goal_object_relocation`.
- A small Linux selected-pair run, first oracle if needed, then Grounding-DINO
  if the oracle geometry is meaningful.
- Mine the resulting summary and report whether it creates interior reliability
  boundaries with nontrivial post-memory fallback.

## Research Relevance

This moves the project toward the paper claim more directly than another
posterior tweak. It creates an instance-level stale-memory challenge where a
remembered object pose can be geometrically correct for the past but wrong for
the current goal. That is the real lifelong ObjectNav problem the robot must
solve before language goals and real-robot deployment.

If successful, this challenge can support stronger ablations:

- category-level frontier search versus instance-scoped memory;
- naive memory reuse versus uncertainty-aware memory deferral;
- detector-event reliability versus fixed/evidence reliability;
- repaired memory reuse across repeated queries.

## Open Questions

- Should the final benchmark include both category-scope ObjectNav and
  instance-scope remembered-object queries?
- Should relocated pairs be chosen by geodesic separation, semantic ambiguity,
  or detector observability once the first smoke works?
- How should language prompts later distinguish "a chair" from "the chair I
  saw before"?
