# Design Doc: Memory-Guided Active Lifelong ObjectNav Benchmark

Date: 2026-05-28  
Owner: Codex (implementation), badger (research direction)  
Status: Draft

## Goal

Move the project from replay-only evidence scoring toward an active lifelong
ObjectNav evaluation where a robot can:

- discover an object without a prior semantic map;
- persist object-instance memory after verification;
- answer a later object query by navigating to remembered verification poses;
- detect stale or moved objects instead of blindly trusting old memory;
- recover through search and update memory when the world changes.

The immediate goal is a reproducible offline benchmark that exposes the value
of memory in multi-room / corridor structure before running the same idea in
Habitat and then on the vehicle.

## Non-Goals

- This is not an official Habitat Challenge submission.
- This does not yet claim SOTA or SPL on public leaderboards.
- This does not train a learned policy in v1.
- This does not connect to ROS 2, Nav2, real cameras, or GPT language input in
  the first implementation slice.
- This does not tune detector thresholds to win one scene.

## Background

The current Grounding-DINO replay experiments prove that detector-backed
evidence can populate persistent object-instance belief and geometry anchors.
However, replay rows are not enough for a strong paper claim because:

- the agent is not choosing where to go;
- replay success rows are not navigation success;
- `naive_count` remains competitive on many visible-object rows;
- memory is most valuable when object queries occur across rooms, corridors,
  time, and changed scenes.

The next claim should therefore be about decision utility:

> A probabilistic object-instance memory can reduce repeated exploration in
> long-lived ObjectNav while staying auditable enough to repair stale memories.

## System Boundary

The v1 benchmark is owned by `objectnav_core` and remains hardware-independent.

It owns:

- synthetic multi-room / corridor grid scenes;
- deterministic object observations from scene truth;
- candidate scoring between remembered object poses and frontier exploration;
- per-episode metrics and artifact reports.

It depends on:

- `OccupancyGrid`, frontier extraction, A* path-cost estimation, and navigation
  clients already in `objectnav_core`;
- SQLite memory records and object states;
- deterministic scene configs.

It must not depend on ROS 2, Habitat, detector model weights, private robot
bags, or vehicle-specific topics.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Scene config | `SceneConfig` | Multi-room / corridor fixture with one or more ObjectNav targets |
| Input | Policy | CLI string | `memory_guided`, `frontier_only`, and later learned / language-conditioned policies |
| Input | Episode sequence | JSON-like internal spec | Discovery, reuse, stale-memory, relocation |
| Output | Summary | `summary.json` | Policy metrics, episode metrics, artifact manifest |
| Output | Trace | `events.csv` or `events.jsonl` | Candidate scores, navigation goals, observations, memory transitions |
| Output | Memory DB | `memory.sqlite` | Object memory and trial metrics |
| Output | Report | `report.html` | Human-readable Chinese/English experiment explanation |

## Interfaces

- CLI:
  - `python -m objectnav_core.cli.run_lifelong_objectnav_benchmark --output ...`
- Core API:
  - `run_lifelong_objectnav_benchmark(output_dir, policies=...)`
  - `select_memory_guided_candidate(...)`
- Artifacts:
  - `summary.json`
  - `events.csv`
  - `memory.sqlite`
  - `report.html`

## Data Flow

1. Build a multi-room / corridor occupancy fixture with a partially known start
   area and hidden rooms.
2. Run a discovery episode with no useful memory.
3. When the target is observed, navigate to a verification viewpoint, verify
   the object, and persist the object memory.
4. Run later object-query episodes from different starts.
5. `memory_guided` scores remembered verification poses against frontier
   exploration using expected utility:
   - success probability from memory state and confidence;
   - A* path cost to verification pose;
   - expected verification cost;
   - expected information gain from frontiers.
6. If memory verification fails, update the memory state to stale/missing and
   search again.
7. Compare with `frontier_only`, which must rediscover from scratch and cannot
   query persisted object memory.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Memory points to moved object | Verification pose has no matching observation | Mark memory suspect/missing, search frontiers, record relocation relation |
| Memory candidate unreachable | A* path-cost returns no path | Suppress that candidate and choose search |
| Frontier-only gets stuck | No reachable frontier candidates before observation | Mark episode failed with `no_reachable_frontier` |
| Memory over-trusts stale object | Raw memory candidate selected but verification fails | Count stale-check failure and require search before success |
| Synthetic scene too simple | Memory and frontier path lengths are similar | Add multi-room fixtures and Habitat long-range validation before paper claims |
| Rule-heavy tuning dominates | Metrics improve only through fixed thresholds | Prefer probabilistic scoring, explicit uncertainty, and shared baselines |

## Verification Plan

Local deterministic checks:

- unit tests for multi-room grid geometry and line-of-sight;
- unit tests for memory-guided candidate scoring;
- benchmark smoke test proving `memory_guided` succeeds and reduces repeated
  exploration versus `frontier_only`;
- compile checks for `objectnav_core`.

Linux / Habitat bridge:

- port the same memory-guided candidate interface to Habitat geodesic/action
  follower runs;
- run Grounding-DINO with RGB/depth noise and memory on/off;
- report path length, success, stale-memory repair, repeated-exploration ratio,
  first-success step, and detector failure diagnostics.

Paper-grade verification later:

- compare against no-memory frontier search, positive-count memory,
  category-only memory, and map-only semantic baselines;
- evaluate multiple HM3D scenes and long episode chains;
- run ablations for object-instance association, uncertainty, stale-memory
  repair, and language-conditioned query parsing.

## Research Relevance

This benchmark targets the claim that matters for a robotics venue:

- not merely "the detector sees the object";
- not merely "memory produces more trust rows";
- but "lifelong object-instance memory reduces costly repeated exploration
  while remaining recoverable when the world changes."

The algorithmic direction is a probabilistic memory-utility policy rather than
a pile of hand thresholds. The first offline implementation is intentionally
simple, but the same interfaces can absorb learned priors, graph memory,
language queries, uncertainty from localization, and real Nav2 costs.

## Open Questions

- Which Habitat action-level follower should be the first closed-loop bridge:
  Habitat-Lab `ShortestPathFollower`, a local geodesic controller, or a Nav2-like
  planner abstraction?
- How much uncertainty should be stored per object instance in v2: covariance,
  entropy, evidence counts, or learned reliability?
- Should GPT language input map directly to target category, object instance,
  room relation, or a ranked query over the memory graph?
- Which public baselines are realistic to reproduce on the available 4070
  Laptop GPU before a paper deadline?
