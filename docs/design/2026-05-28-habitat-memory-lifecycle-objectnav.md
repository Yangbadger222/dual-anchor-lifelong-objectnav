# Design Doc: Habitat Memory-Lifecycle ObjectNav Evaluation

Date: 2026-05-28  
Owner: Codex  
Status: Draft

## Goal

Create the first Habitat-backed lifecycle evaluation for lifelong ObjectNav
memory. The protocol should test whether an agent that has previously verified
an object can answer a later ObjectNav query by navigating to the remembered
verification pose before falling back to ordinary goal search.

The immediate target is a reproducible geodesic evaluation on HM3D ObjectNav
`val_mini` with Grounding-DINO, RGB/depth noise, and shared decision gates. This
is a bridge between replay evidence rows and future closed-loop action-level
ObjectNav.

## Non-Goals

- Do not claim official Habitat Challenge SPL.
- Do not train a learned policy in this slice.
- Do not add ROS 2, Nav2, real robot topics, GPT language input, or vehicle
  assumptions.
- Do not give the `naive_count` baseline non-confirmation handling, delayed
  birth, geometry repair, or object-instance reasoning.
- Do not tune thresholds around one category failure.

## Background

The project now has two useful but incomplete validation layers:

1. Grounding-DINO replay stress tests show that detector-backed evidence can
   populate memory and survive expected-empty checks better than a raw trust
   signal.
2. A synthetic active benchmark shows that memory can reduce repeated
   exploration in a multi-room fixture.

The missing bridge is a Habitat lifecycle query metric: after a discovery
episode stores a verification pose, later starts in the same scene should first
try that remembered pose. If verification succeeds, repeated search was
avoided; if it fails, the policy must fall back to goal search and record stale
memory repair cost.

## System Boundary

The new layer lives in `objectnav_core.evaluation` and remains
hardware-independent. It owns:

- lifecycle episode pairing within HM3D ObjectNav `val_mini`;
- memory-anchor candidate extraction from earlier verified views;
- geodesic cost accounting for memory-first and fallback routes;
- summary metrics for memory-guided, positive-only count, and no-memory
  baselines.

It depends on:

- existing Habitat episode loading and scene resolution helpers;
- existing Grounding-DINO / oracle detector adapters and RGB/depth noise
  profiles;
- existing replay measurement helpers for target pixels, path points, and
  detector evidence classification;
- `LifelongMemoryHarness` for persistent belief and anchor storage.

It must not depend on ROS 2, robot-specific maps, private credentials, or
committed Habitat datasets.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Dataset directory | HM3D ObjectNav `val_mini` path | Ignored local dataset |
| Input | Scene root | HM3D scene assets | Ignored local dataset |
| Input | Detector config | CLI flags | `grounding_dino` or `oracle_bbox` |
| Input | Memory modes | CLI list | `memory_guided`, `naive_count`, `no_memory` |
| Input | Noise levels | CLI list | `clean,mild,heavy` |
| Output | Summary | `summary.json` | Lifecycle metrics and episode selection |
| Output | Trace | `lifecycle_trace.csv` | Candidate decisions and path costs |
| Output | Memory DB | `lifecycle_memory.sqlite` | Stored beliefs and anchors |
| Output | Report | `report.html` | Human-readable experiment status |

## Interfaces

- CLI:
  - `python -m objectnav_core.cli.run_habitat_memory_lifecycle_objectnav --output ...`
- Core API:
  - `run_habitat_memory_lifecycle_objectnav(...)`
  - `run_habitat_memory_lifecycle_preflight(...)`
  - `plan_lifecycle_query(...)`
- Artifacts:
  - `summary.json`
  - `lifecycle_trace.csv`
  - `lifecycle_memory.sqlite`
  - `report.html`

## Data Flow

1. Load HM3D ObjectNav episodes and select structured long-distance episodes
   with at least two goal viewpoints.
2. Group candidate episodes by scene, category, and target instance when
   available.
3. For each lifecycle group, choose one discovery view as the remembered
   verification pose and one or more later query starts.
4. For `memory_guided`, navigate geodesically from query start to the remembered
   verification pose and run detector-backed verification.
5. If verification succeeds, stop and count memory reuse.
6. If verification fails, mark the memory attempt stale and fall back to the
   official goal viewpoint path.
7. For `naive_count`, allow only positive-count trust at the current target
   view. It does not receive stale-memory repair, geometry gating, or delayed
   birth.
8. For `no_memory`, always use the fallback goal path.
9. Summarize path length, success, memory reuse, fallback count, stale check
   count, detector evidence, and per-category failures.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No lifecycle pairs selected | `selected_groups=0` | Lower structured filters or report dataset limitation |
| Remembered pose unreachable | Habitat pathfinder returns no path | Suppress memory candidate and fall back to goal |
| Detector misses visible target | Target pixels pass oracle threshold but detector evidence is not positive | Record detector miss; do not count memory success |
| Detector false-positive at stale pose | Detector positive but oracle target not visible | Shared current-view gate rejects stop success |
| Baseline gets unfair helper state | Mode-specific trace fields show non-baseline signals | Tests assert baseline mode does not use geometry/stale repair |
| Geodesic metric mistaken for SPL | Report limit section labels scope | Later action-level follower required |

## Verification Plan

- Unit tests for preflight config and lifecycle policy planning without Habitat.
- Unit tests with fake path costs proving:
  - `memory_guided` uses the remembered pose before fallback;
  - failed memory verification adds fallback path cost;
  - `no_memory` never receives memory path credit;
  - `naive_count` stays positive-only.
- CLI preflight test.
- Local focused test run and compile check.
- Linux `conda habitat` smoke with `oracle_bbox` first.
- Linux Grounding-DINO small matrix on structured episodes after the smoke.

## Research Relevance

This layer moves the paper story toward the real claim:

> Lifelong object-instance memory reduces repeated long-range ObjectNav search
> while staying recoverable when memory becomes stale or perception fails.

It is still not enough for a top-tier claim, but it is a necessary bridge. It
turns replay trust rows into query-level path and stop metrics, gives baselines
a fair shared stop gate, and identifies whether remaining failures are memory,
detector, or episode-selection problems.

## Open Questions

- Should the first official closed-loop port use Habitat `ShortestPathFollower`
  or a Nav2-like local planner abstraction?
- How should object-instance identity be maintained across different official
  episodes when HM3D metadata lacks stable instance IDs?
- Can a learned utility model replace the v1 expected-utility score after this
  geodesic protocol produces enough traces?
- Which public ObjectNav baselines are realistic to reproduce on the available
  Linux GPU before a paper deadline?
