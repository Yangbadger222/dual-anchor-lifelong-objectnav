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
- optional evidence-derived memory reliability through
  `--memory-reliability-mode evidence`;
- row-level decision buckets and hindsight regret diagnostics for calibration;
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
- Fixed `memory_valid_prior` remains the reproducibility baseline. Evidence
  reliability mode estimates a per-memory valid probability from current
  detector or oracle evidence, dual-anchor matching quality, transform
  covariance, category-level priors, and recent verification outcomes, then
  records the reliability trace in every row.
- Evidence reliability currently includes a conservative strong-positive floor:
  when current evidence is strong, matching is accepted, and transform
  covariance remains low, the estimator should not defer a slightly shorter
  valid memory simply because the post-memory fallback is expensive. This was
  calibrated from hindsight-regret rows and must be replaced or validated by a
  learned/evidence-derived calibration before paper claims.
- Detector-backed reliability must use detector-visible pixels for current
  evidence. Oracle semantic pixels may be recorded for auditing and gate
  diagnostics, but they must not inflate memory reliability in
  Grounding-DINO-backed policy decisions.

## Per-Action Observation Slice

The next slice moves the Habitat runner one step closer to real ObjectNav by
adding a route observation mode:

- `option_end` keeps the current behavior for reproducibility: selected memory,
  fallback, and navmesh probe options are verified at their candidate/probe
  endpoint or heading-scan pose.
- `per_action` records the agent pose after every GreedyGeodesic action,
  verifies those poses in execution order, and truncates the charged route when
  the shared gate first becomes positive.
- Route observations must use the same oracle or Grounding-DINO shared gate as
  candidate verification. Detector-backed route evidence must not borrow oracle
  pixels for reliability.
- In `stale_proxy`, old-memory observations remain non-confirmations by
  protocol; only rediscovered/repaired anchors may become positive memories on
  later repeats.

This is still not a full ObjectNav benchmark. It does not build an occupancy map
from depth and it does not learn a frontier scorer. Its value is to remove the
"only check the final candidate view" shortcut and expose whether memory or
frontier routes would have seen the target earlier during actual execution.

Scope for this slice:

- add `--route-observation-mode option_end|per_action`, with `option_end` as
  the default for comparability with existing reports;
- record per-action route observations from the GreedyGeodesic follower without
  changing the target-agnostic route goal sampler;
- in `per_action`, verify memory, fallback, and navmesh-probe route poses with
  the same oracle/Grounding-DINO shared gate used for candidate verification;
- truncate the charged route at the first positive observation, rather than
  charging to a later endpoint after the target was already visible;
- record row-level route-observation payloads for memory, fallback, and
  post-memory fallback so experiment reports can audit which route step or
  heading produced the selected evidence;
- keep stale-proxy initial memory attempts non-confirming and untruncated, so a
  synthetic old-object positive cannot make stale memory look cheaper;
- keep `search_proxy` and `navmesh_frontier` behavior comparable when
  `option_end` is selected.

## Detector Confirmation Slice

The latest Grounding-DINO per-action smoke exposed a detector-positive `plant`
memory with zero semantic overlap in simulation. The overlap metric is only an
audit signal because a real robot will not have oracle semantic masks, so the
next policy-facing step must not "fix" the result by requiring oracle overlap.
Instead, detector positives should be optionally confirmed by repeated evidence
across nearby but distinct views.

Scope for this slice:

- add a detector confirmation mode with `single_frame` as the default and
  `multiview` as an explicit experiment setting;
- reuse the existing val-mini temporal/multi-view/mask-consistency confirmation
  pattern: a detector positive starts as pending, then becomes positive only
  after enough positive frames, sufficient pose change, and mask consistency;
- apply the confirmation gate to detector-backed memory, fallback, and
  post-memory fallback evidence before reliability scoring and shared-gate
  policy decisions;
- keep oracle semantic visibility and default single-frame detector behavior
  unchanged for reproducibility;
- record confirmation diagnostics in evidence payloads and summaries so future
  reports can separate raw detector positives from confirmed positives;
- record runtime confirmation events for detector positives that are seen during
  candidate, route, and navmesh-probe verification, including positives that are
  suppressed before a later confirmed stop, so summary diagnostics do not depend
  only on the final selected evidence in each row;
- treat suppressed positives as `UNKNOWN`, not as negative evidence, because a
  single-view detector hit may still be useful but is not strong enough to
  refresh long-term memory.

Non-scope for this slice:

- no oracle-overlap policy gate;
- no category-specific threshold tuning from the one `plant` failure;
- no learned reliability model yet. This creates the ablation-ready interface
  and event diagnostics that a learned confirmer can replace later.

## Adaptive Detector Event Reliability Slice

The verified runtime event probe showed that selected evidence alone is too
thin for reliability: a row may end with confirmed evidence while earlier route
views contained suppressed detector positives. The next policy-facing step is
to turn this event stream into an adaptive memory-valid estimate without using
oracle semantic overlap.

Goal:

- add an explicit `event_posterior` memory reliability mode that estimates the
  probability that a remembered object is still worth trying from detector
  confirmation events plus the existing matching, covariance, category, and
  recency evidence;
- make the estimator conservative when suppressed detector positives dominate,
  but allow confirmed multiview evidence to raise confidence above the fixed
  prior;
- keep the estimator transparent and logged so it can be used as a calibration
  baseline before replacing it with a learned model.

Non-goals:

- no detector-threshold or category-specific tuning from one smoke;
- no privileged oracle overlap in policy decisions;
- no claim that `event_posterior` is a final learned reliability model;
- no change to `fixed` or `evidence` mode behavior.

System boundary:

- Inputs are the active memory verification payload, the row-level
  `detector_confirmation_events` list, a target event context (`memory` for an
  original memory and `fallback_from_memory` for a repaired memory), matching
  reason, category, repeat index, and dual-anchor transform covariance.
- Outputs are the same `MemoryReliabilityEstimate` payload already recorded in
  rows: scalar `value`, component trace, and reason. The expected-utility
  decision consumes only the scalar value.

Interface:

- extend `--memory-reliability-mode fixed|evidence` with
  `event_posterior`;
- extend `_estimate_memory_valid_prior(...)` with optional detector
  confirmation events and event context;
- report posterior components such as confirmed event weight, suppressed event
  weight, event count, and event posterior in `memory_reliability.components`;
- keep `detector_confirmation_event_counts` in summaries as diagnostics,
  separate from the policy-facing posterior.

Data flow:

1. Detector candidate, route, and navmesh-probe verification records confirmed
   or suppressed events.
2. For each policy row, the active memory context selects the relevant event
   subset.
3. Confirmed events add positive evidence to a bounded beta-style posterior.
   Suppressed events add weaker uncertainty evidence; they reduce confidence
   but do not become hard negatives because a real robot lacks semantic truth.
4. The posterior is blended with the existing evidence reliability estimate.
   If no relevant detector events exist, `event_posterior` falls back to
   `evidence` mode and records that reason.
5. The expected-utility memory-vs-frontier decision uses the resulting
   reliability value exactly as it already uses `fixed` and `evidence`.

Failure modes:

| Failure | Detection | Mitigation |
|---|---|---|
| Suppressed events treated as object absence | Rows with suppressed but later confirmed evidence are wrongly deferred | Use weak uncertainty weights, not hard negative labels |
| Event counts from fallback leak into original memory reliability | Context-filtering test disagrees with selected memory source | Pass an explicit context and test memory vs repaired-memory rows separately |
| Hand-designed posterior overfits tiny smoke | Held-out category/scenes regress versus `evidence` mode | Keep `event_posterior` as a transparent baseline and compare against learned calibration |
| Oracle audit accidentally influences policy | Changing oracle overlap changes reliability | Unit test identical posterior when oracle audit fields vary |

Verification plan:

- unit tests showing confirmed events raise posterior reliability;
- unit tests showing suppressed-dominant memory events lower reliability enough
  to choose frontier when the expected action costs are close;
- unit tests showing oracle audit fields do not change event posterior;
- CLI/preflight test showing `event_posterior` is accepted and recorded;
- local focused Habitat closed-loop tests before any Linux smoke;
- later Linux Grounding-DINO smoke comparing `evidence` and `event_posterior`
  on the same run configuration.

Paper/research relevance:

- This creates the first policy-facing bridge from raw detector-event traces to
  memory-vs-frontier decisions. It is stronger than a global multiview gate
  because it uses uncertainty accumulated along actual routes, but it is still
  an interpretable baseline. A paper-ready version should replace or calibrate
  this posterior with learned reliability on held-out scenes.

Remaining non-scope for the current closed-loop smoke:

- building occupancy directly from depth;
- learned frontier scoring or occupancy-map frontier selection;
- closed-loop replanning after every observation;
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
| Reliability estimator overfits tiny smokes | Hindsight regret improves on balanced6 but fails on held-out categories/scenes | Keep row-level reliability traces, run held-out Habitat splits, and compare against learned calibration |

## Verification Plan

- Unit tests for SE(2) frame transform, covariance propagation, Mahalanobis
  acceptance/rejection, and ambiguity detection.
- Deterministic pressure tests with two same-class instances under increasing
  drift and covariance.
- Closed-loop grid smoke that chooses memory pose vs frontier exploration using
  the same interfaces.
- Habitat oracle smoke for session restart and natural stale repair.
- Habitat Grounding-DINO smoke on six categories.
- Reliability calibration tests for valid-memory deferral and harmful-memory
  avoidance, using row-level hindsight regret as the diagnostic target.
- Full clean/mild/heavy matrix with frontier-only, nearest-frontier, no-memory,
  naive-count, and memory-guided baselines.

## Current Per-Action Matrix Finding

The current-code balanced6 per-action matrix on 2026-05-30 validates the
per-action observation slice as a real mechanism, not just a logging feature.
Compared with matched `option_end` runs, route-level observation improved:

| Slice | Route observation | Memory-guided success | Memory-guided actions | Frontier-only success |
|---|---|---:|---:|---:|
| Stable balanced6 | `option_end` | `5/6` | `573` | `0/6` |
| Stable balanced6 | `per_action` | `6/6` | `473` | `3/6` |
| Relocation balanced6 | `option_end` | `0/6` | `1446` | `0/6` |
| Relocation balanced6 | `per_action` | `3/6` | `1176` | `2/6` |

The key relocation result is the `sofa` row: query-start frontier remains a
failure, but memory-first followed by local post-memory frontier search finds a
multiview-confirmed detector positive along the route. This suggests the next
algorithm should treat memory as a spatial prior for active confirmation and
local search, not only as a stop-point.

The matched learned-validity per-action runs were neutral: learned probabilities
changed, but decisions, success, and action counts were identical to the
event-posterior per-action baseline. The learned-validity hook is therefore a
real policy mechanism under `option_end`, while per-action route observation is
the current source of success improvement.

The first diagnostic from this matrix was the stable `bed` row: memory evidence
was positive, but expected utility selected a zero-action failed frontier
option. Commit `033c8b8` fixed the targeted decision bug by treating failed
zero-action frontier options as unavailable. Selected-group verification chose
memory and succeeded in `32` actions for both event-posterior and learned
validity; post-fix stable balanced6 replays now reach `6/6` under `per_action`.

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
