# Design Doc: Official Memory-Belief Frontier Policy

Date: 2026-05-30
Owner: Codex
Status: Implemented; diagnostic YOLO smoke completed

## Goal

Add a first official-query policy that treats remembered object detections as a
spatial belief over target location and selects frontier/search actions that
increase expected target-view evidence near that belief, instead of only
turning toward a single nearest anchor.

## Non-Goals

- Do not use semantic oracle visibility, target pose, Habitat pathfinder, or
  non-official metrics.
- Do not claim a benchmark improvement from unit tests or tiny smokes.
- Do not add language/GPT control in this slice.
- Do not solve learned memory ranking or cross-session SLAM drift in this
  slice.
- Do not remove existing baselines or the existing `memory_guided_frontier`
  diagnostic policy.

## Background

The generated YOLO memory-prior query failed because nearest-anchor steering
did not bring the target into the detector evidence stream. Built-in query
traces now prove this directly: the four-episode YOLO smoke made `196`
detector calls and produced `0` target-category matches. The next policy must
make a stronger promise than "point at remembered coordinates": it should
choose exploratory frontiers according to a target belief around memory
anchors, then use detector evidence for STOP.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`

Add a new policy:

- `memory_belief_frontier`

The policy remains inside the official evaluator and uses only:

- official `rgb/depth/gps/compass` observations;
- external memory-prior anchors already accepted by the evaluator;
- optional injected detector adapter for current-view STOP and trace logging;
- Habitat discrete actions.

## Approach Options

| Option | Summary | Trade-off |
|---|---|---|
| Nearest-anchor steering | Existing `memory_guided_frontier` turns toward the best anchor. | Simple, already failed to create target-view evidence. |
| Memory-weighted frontier scoring | Score occupancy frontiers by target belief mass around selected memory anchors minus travel cost. | Good first algorithmic step; still heuristic but has a clear belief-search interpretation. |
| Learned active-search policy | Train a policy/value model using detector traces and official metrics. | More publishable long-term, but needs datasets and logging first. |

Chosen first slice: memory-weighted frontier scoring. It is small enough to
verify now and creates the interface for later learned scoring.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|
| Input | Memory anchors | `OfficialMemoryAnchor` | Filtered by category, scene, confidence, coordinate frame. |
| Input | Observation | official Habitat observation | Uses existing corrected `gps/compass/depth` helpers. |
| Input | Detector | optional `detect(rgb)` adapter | STOP and trace only. |
| Output | Action | Habitat discrete action | `stop`, `move_forward`, `turn_left`, or `turn_right`. |
| Output | Debug | `policy_debug.memory_prior` | Records selected anchor, selected frontier, belief score, and decision. |

## Data Flow

1. Run the existing detector-confirmed STOP check. A current target detection
   still emits `stop_on_detector`.
2. Select the highest-confidence matching memory anchor using the existing
   `select_official_memory_anchor` boundary.
3. Update the local occupancy frontier map from official depth.
4. Build a local target-belief score over frontier cells:
   `belief = anchor.confidence * exp(-distance_to_anchor^2 / (2 * sigma^2))`.
5. Penalize travel distance from the current cell to avoid far-away detours:
   `score = belief - distance_weight * distance_to_agent`.
6. Select the highest-scoring frontier, turn toward it, or move forward when
   aligned and depth is clear.
7. If no matching memory or no frontier exists, fall back to the existing
   occupancy frontier behavior.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No matching memory | Anchor selector returns `None` | Existing occupancy frontier fallback. |
| No frontier cells | Empty frontier set | Existing occupancy frontier fallback. |
| Detector false positive | Official success remains source of truth | Trace and debug record the STOP reason. |
| Bad memory anchor | Low belief frontiers may mislead | Official metrics expose this; future fusion/validity model should downweight bad memory. |
| Belief scoring overfits tiny tests | Live Habitat trace comparison required | Treat as algorithm slice, not a paper claim. |

## Verification Plan

1. Unit-test that memory-belief frontier scoring prefers a farther frontier
   near a high-confidence memory anchor over a nearer frontier away from memory.
2. Unit-test that `memory_belief_frontier` is listed as an official policy kind
   and requires a memory prior.
3. Unit-test that the policy records belief-frontier debug fields while still
   using detector-confirmed STOP before frontier scoring.
4. Run focused official-memory tests and `compileall`.
5. Sync to Linux and run the focused test set in conda env `habitat`.
6. Run a small YOLO query smoke with built-in detector trace and compare
   target-match evidence against the previous nearest-anchor policy. Treat the
   result as diagnostic until broad official comparisons exist.

## Verification Result

Completed on 2026-05-30.

- RED helper test failed because `_select_memory_belief_frontier` was missing.
- GREEN helper test passed after adding Gaussian memory-belief frontier scoring.
- RED policy tests failed because `memory_belief_frontier` was unsupported.
- GREEN policy registration/debug tests passed after wiring the official
  policy.
- Detector precedence guard passed: `memory_belief_frontier` stops on
  current-view target detection before scoring frontiers.
- Local official evaluator tests passed: `36` tests.
- Local focused official-memory/exporter set passed: `58` tests.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set passed in conda env `habitat`:
  `58` tests.
- Linux `compileall` and `git diff --check` returned cleanly.

Diagnostic YOLO query smoke:

- Artifact:
  `runs/habitat_official_objectnav/memory_belief_frontier_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.
- Official success stayed `0/4`; SPL stayed `0.0`; SoftSPL stayed
  `0.0009902771347611306`.
- Built-in detector trace recorded `152` detector calls, `81` detections, `1`
  target-match call, and `1` target-match detection.
- The `tv_monitor` episode ended with `decision="stop_on_detector"`, but
  Habitat still scored failure.

This is not a benchmark improvement. It is positive diagnostic evidence that
belief-guided search can reach target-view detector evidence where the previous
nearest-anchor policy recorded zero target matches. It also exposes the next
algorithmic bottleneck: current-view detection should trigger local approach or
range-aware confirmation, not immediate STOP whenever the label matches.

## Research Relevance

This is not yet the final publishable algorithm. It is the first step from
coordinate steering toward belief-driven active search: memory becomes a target
distribution over unexplored space, and detector traces become the evidence
signal for whether search near memory is actually improving target visibility.
