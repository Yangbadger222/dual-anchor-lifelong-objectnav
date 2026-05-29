# Design Doc: Closed-Loop Dual-Anchor Habitat ObjectNav

Date: 2026-05-29  
Owner: Codex  
Status: Draft

## Goal

Replace the current teleport/search-proxy lifecycle evaluation with a Habitat
simulation that measures the actual paper claim: lifelong ObjectNav memory
under closed-loop exploration, map-frame restarts, localization uncertainty,
instance ambiguity, and natural object staleness.

The new simulator must make the memory system choose between remembered object
poses and frontier exploration while the agent moves, senses, verifies, repairs
stale memory, and carries memory across session-specific map frames.

## Non-Goals

- Do not present the existing lifecycle proxy as the main benchmark.
- Do not claim official Habitat Challenge SPL until the loop uses an official
  task wrapper or reports clearly separated SPL-like metrics.
- Do not give memory-only access to privileged ground truth that frontier or
  no-memory baselines cannot use.
- Do not hard-code robot or FAST-LIO topics into the core algorithm.
- Do not hide detector failures by switching to oracle for headline results.

## Background

The current HM3D results are useful but insufficient. They show that
detector-qualified memory and stale repair can reduce route cost in a controlled
lifecycle protocol, but they still rely on fixed candidate viewpoints and
search-proxy accounting. That is not enough for a top-tier robotics claim.

The project needs a simulator whose failure modes match the intended robot:

- the robot explores without a prior map;
- session-local map frames can reset or drift;
- object memories must be transformed and matched across anchors;
- stale objects are physically absent or relocated, not just marked stale by
  protocol;
- baselines perform real exploration, not strawman direct fallback.

## System Boundary

The new stack has three layers:

1. `objectnav_core.geometry.dual_anchor`: hardware-independent math for
   session-frame transforms, pose covariance propagation, and Mahalanobis
   instance matching.
2. Closed-loop policy/evaluation layer: chooses between memory candidates and
   frontier candidates, executes Habitat actions, updates observations, and
   decides whether to stop, repair memory, or continue exploration.
3. Habitat scenario layer: builds multi-session HM3D episodes with frame
   restarts, localization noise, instance ambiguity, and object relocation.

The dual-anchor math must not import Habitat. Habitat adapters may depend on
Grounding-DINO, Habitat-Sim, and HM3D assets.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | HM3D scene / ObjectNav episodes | Habitat dataset paths | Full `val` first, larger splits later |
| Input | Detector | Grounding-DINO or oracle smoke | Oracle only for plumbing/debug |
| Input | Session transform | 2D SE(2) transform plus covariance | Simulates map-frame restart/drift |
| Input | Memory observations | Pose estimate plus covariance | Produced from detector/depth/session pose |
| Input | Staleness event | Object relocation/removal config | Natural object change across sessions |
| Output | Action trace | CSV/JSON | Per-step or per-option action, pose, decision, observation |
| Output | Matching trace | CSV/JSON | Mahalanobis distance, gate, ambiguity margin |
| Output | Summary | JSON | Success, SPL-like metrics, action count, exploration count, repair metrics |
| Output | Report | HTML/Markdown | Human-readable run status and caveats |

## Interfaces

- Core geometry API:
  - `PoseEstimate2D`
  - `FrameTransform2D`
  - `transform_pose_estimate(...)`
  - `mahalanobis_squared(...)`
  - `match_instance_by_mahalanobis(...)`
- Future Habitat CLI:
  - `python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav ...`
- Artifacts:
  - `summary.json`
  - `action_trace.csv`
  - `matching_trace.csv`
  - `memory.sqlite`
  - `report.html`

## Current Implementation Slice

As of 2026-05-29, the repository contains an oracle/action-level Habitat smoke
runner:

```bash
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav ...
```

The current slice is deliberately labeled as a smoke, not the final benchmark.
It executes GreedyGeodesic Habitat action routes and records dual-anchor session
restart metadata, but still uses oracle semantic visibility and a deterministic
search-proxy frontier.

Implemented in this slice:

- stable, ambiguous, and stale-proxy challenge modes;
- repeated stale queries where `memory_guided` can reuse a repaired anchor and
  `naive_count` remains positive-only;
- direct repaired-memory route accounting;
- expected-utility memory-vs-frontier selection through `memory_valid_prior`;
- balanced group selection that covers categories before taking duplicates.

Latest balanced oracle/action smoke:

| Scenario | `memory_guided` | `frontier_only` | `naive_count` | Notes |
|---|---:|---:|---:|---|
| stable balanced6 | 575 actions | 1311 actions | 575 actions | Memory and naive tie when memory is correct |
| stale balanced6, 2 repeats | 2020 actions | 3074 actions | 4148 actions | Memory-guided repairs and later reuses anchors |

This is useful evidence for the direction, but it is not a paper-ready result
until Grounding-DINO, true frontier exploration, natural staleness, and larger
run statistics are added.

## Data Flow

1. Session 1 starts in Habitat with an empty local map.
2. The agent explores frontiers until it detects and verifies a target object.
3. The memory system stores an object pose in session-1 map frame with
   covariance and detector evidence.
4. Session 2 restarts in the same scene with a new map origin, yaw offset, and
   localization covariance.
5. Stored memories are transformed into the session-2 frame through a
   dual-anchor transform.
6. At each decision point, the policy scores memory candidates and frontier
   candidates using expected utility, Mahalanobis compatibility, uncertainty,
   and stale risk.
7. The selected option is executed by Habitat actions. The agent renders
   RGB/depth/semantic observations after movement and decides whether current
   evidence supports stop, stale repair, or continued exploration.
8. In relocation scenarios, the old object is removed or moved before session 2;
   stale repair must emerge from failed verification and rediscovery, not from a
   synthetic label.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Memory beats weak baseline only | Compare against frontier-only and nearest-frontier baselines | Keep lifecycle proxy as diagnostic only |
| Coordinate transform overconfident | Matching trace shows high false accepts under drift | Propagate covariance and gate by chi-square distance |
| Instance ambiguity hidden | Multiple candidates within gate and small margin | Report ambiguity, defer to exploration or verification |
| Natural relocation unavailable in Habitat asset | Object mesh cannot be moved cleanly | Start with semantic-object hide/replace protocol and label as such |
| Detector dominates all outcomes | Detector miss counts exceed memory decision effects | Run oracle plumbing, then Grounding-DINO, then report detector-limited cells separately |
| Action loop still option-level | Trace lacks per-action observations | Label as option-level closed loop and add per-step perception before paper claims |

## Verification Plan

- Unit tests for SE(2) frame transform, covariance propagation, Mahalanobis
  acceptance/rejection, and ambiguity detection.
- Deterministic pressure tests with two same-class instances under increasing
  drift and covariance.
- Closed-loop grid smoke that chooses memory pose vs frontier exploration using
  the same interfaces.
- Habitat oracle smoke for session restart and natural stale repair.
- Habitat Grounding-DINO smoke on six categories.
- Full clean/mild/heavy matrix with frontier-only, nearest-frontier, no-memory,
  naive-count, and memory-guided baselines.

## Research Relevance

This design restores alignment between the implementation and the paper thesis.
The core contribution is not merely "remember an object pose." It is:

> dual-anchor lifelong ObjectNav memory that remains useful across local-map
> restarts, exposes uncertainty-aware instance matching, detects stale memories,
> and reduces closed-loop exploration compared with real exploration baselines.

The Mahalanobis matching and covariance propagation become measured variables,
not decorative equations. Natural relocation removes the circularity of
synthetic stale labels. Closed-loop frontier baselines make the comparison
credible.

## Open Questions

- Should the first Habitat closed-loop layer be option-level or per-action
  observation-level?
- What object relocation mechanism is safest in HM3D without corrupting semantic
  annotations?
- Which public ObjectNav baseline can be reproduced on the available 8GB GPU?
- How many repeats/sessions are needed before memory-vs-no-memory amortization
  is a meaningful claim?
