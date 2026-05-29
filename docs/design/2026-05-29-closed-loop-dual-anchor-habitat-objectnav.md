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

## Grounding-DINO Detector Slice

The second implementation slice replaces oracle semantic visibility in the
closed-loop action runner with detector-backed candidate verification while
keeping the action-route and search-proxy structure fixed. This is still an
option-level closed-loop smoke, not official ObjectNav SPL, but it removes the
largest privileged-perception shortcut from the previous oracle runner.

Scope for this slice:

- support `--detector oracle_semantic_visibility|grounding_dino`;
- render each selected memory and fallback candidate at `1280x720`;
- apply the existing RGB/depth noise profiles before evidence classification;
- reuse the lifecycle runner's Grounding-DINO adapter, detector-mask filtering,
  and shared evidence classifier;
- choose memory and fallback anchors with detector-positive evidence when
  available, then apply the same shared gate to `memory_guided`,
  `naive_count`, and `frontier_only`;
- record detector config, min-pixel thresholds, area filter, and selected-row
  evidence metrics in `summary.json`.

Non-scope for this slice:

- per-action visual servoing;
- learned frontier selection;
- natural object relocation;
- detector-threshold tuning to rescue a single class.

This keeps the comparison honest: if Grounding-DINO cannot produce usable
evidence for a category, the run should expose that as detector-limited rather
than silently falling back to Habitat ground truth.

Latest Grounding-DINO candidate-gate smoke:

| Scenario | `memory_guided` | `frontier_only` | `naive_count` | Notes |
|---|---:|---:|---:|---|
| stable balanced6 | 575 actions | 1313 actions | 575 actions | Memory-guided ties naive when every memory is valid |
| stale balanced6, 2 repeats | 2018 actions | 3072 actions | 4144 actions | Memory-guided repairs once, then reuses the repaired anchor |

All six selected categories produced positive Grounding-DINO fallback evidence
at `1280x720` in the clean run. In `stale_proxy`, old memory evidence is
reported as explicit `non_confirmation/shared_gate_success=false`; only the
rediscovered fallback/repaired anchor becomes detector-positive. This is stronger
than the oracle/action smoke, but it remains a proxy because the detector is not
run at every action step and frontier is still search-proxy based.

## Navmesh Frontier Slice

The next implementation slice should replace the target-aware search-proxy
frontier with a Habitat navmesh-frontier approximation. This is an intermediate
baseline, not the final occupancy-grid frontier. Its purpose is to remove the
most obvious unfairness: `frontier_only` should no longer receive the known
fallback target pose as its final route goal.

Local implementation status:

- `--frontier-mode search_proxy|navmesh_frontier` is wired through the CLI,
  preflight summary, and Habitat runner; `search_proxy` remains the default.
- `navmesh_frontier` samples deterministic navigable probes from Habitat
  `pathfinder.get_random_navigable_point()` using the requested seed, start
  pose, minimum spacing, and probe budget.
- The runner follows probes one at a time with the same GreedyGeodesic action
  follower used by the existing action smoke, verifies the reached probe pose,
  and stops on the first shared-gate positive.
- Each reached probe can run a deterministic fixed-heading scan before the
  next probe. This models a robot looking around from an exploration point
  without using target pose or target visibility to choose the route. Extra
  scan headings are counted as zero-translation scan actions so the fallback
  is not credited with free sensing.
- Query-start fallback and post-memory fallback use separate probe sequences.
  Repeated stale queries only reuse a repaired anchor if the post-memory probe
  route found a positive verification.
- `memory_guided` should treat an accepted memory as an option, not a command:
  if the expected memory-first action cost is higher than frontier-first,
  it should defer to frontier while `naive_count` remains the always-reuse
  memory baseline.
- Fixed `memory_valid_prior` is only the reproducibility baseline. The next
  policy mode should estimate per-memory reliability from current detector or
  oracle evidence, dual-anchor matching quality, transform covariance,
  category-level priors, and recent verification outcomes, and record the
  reliability trace in every row.

Scope for this slice:

- support `--frontier-mode search_proxy|navmesh_frontier`;
- keep `search_proxy` as the default for comparability with existing reports;
- in `navmesh_frontier`, sample navigable frontier probes from the Habitat
  pathfinder using only start pose, scene bounds, seed, and navigability;
- route to sampled probes in a deterministic order that does not use target
  pose or target visibility;
- verify each probe with the same oracle/Grounding-DINO shared gate already
  used for memory/fallback candidates;
- stop at the first positive probe, otherwise report failure after the probe
  budget is exhausted;
- use the same frontier procedure for `frontier_only`, memory fallback, and
  `naive_count` fallback.

Non-scope for this slice:

- building occupancy directly from depth;
- per-action mapping and detector decisions;
- learned frontier scoring;
- claiming official ObjectNav SPL.

This slice is expected to make `frontier_only` weaker and more realistic than
the current search proxy, because it must discover a positive target view rather
than routing to a target-derived fallback candidate. It is still not final paper
evidence; it is a pressure test that should reveal how much of the current gain
comes from repaired memory versus a target-aware fallback.

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
