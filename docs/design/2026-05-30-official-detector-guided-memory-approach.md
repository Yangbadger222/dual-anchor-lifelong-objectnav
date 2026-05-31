# Design Doc: Official Detector-Guided Memory Approach

Date: 2026-05-30
Owner: Codex
Status: Implemented; diagnostic YOLO smoke completed

## Goal

Make `memory_belief_frontier` use current-view target detections as a local
approach signal before emitting STOP. A target-category detection should cause
centering or forward approach while the target appears far or off-center, and
STOP only when detector bbox geometry plus depth make official ObjectNav
success plausible.

## Non-Goals

- Do not change Habitat official metric handling; `habitat.Env.get_metrics()`
  remains the only benchmark-facing source.
- Do not use semantic oracle masks, target pose, Habitat pathfinder, route
  followers, teleportation, or success labels for action selection.
- Do not claim benchmark improvement from synthetic unit tests or tiny smokes.
- Do not redesign detector training, memory fusion, or learned validity scoring
  in this slice.
- Do not change `memory_guided_frontier` behavior beyond preserving existing
  detector-confirmed STOP compatibility.

## Background

The `memory_belief_frontier` YOLO smoke produced better evidence than nearest
memory steering: the detector trace reached one target-category match where the
previous policy reached zero. Official success still stayed `0/4`, and the
episode ended with `decision="stop_on_detector"`. That makes the current
failure mode clear: a label match can happen before the agent is close enough
or centered enough for Habitat to score success.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`

The new behavior belongs only to the official query policy path. It depends on:

- official `rgb` observations for detector input;
- official `depth` observations for target-range evidence inside the bbox;
- existing corrected `gps/compass` helpers and occupancy frontier map;
- existing external memory-prior anchors;
- an optional injected detector adapter with `detect(rgb)`.

The policy continues to output only Habitat discrete actions:

- `move_forward`
- `turn_left`
- `turn_right`
- `stop`

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | RGB | Habitat observation key `rgb` | Passed to injected detector adapter. |
| Input | Depth | Habitat observation key `depth` | Sampled inside target bbox for range evidence. |
| Input | Detection | object with `category`, `confidence`, `bbox` | Existing detector adapter shape. |
| Input | Memory anchor | `OfficialMemoryAnchor` | Used when no current-view target control is active. |
| Output | Action | Habitat discrete action string | No route follower or pose action. |
| Output | Debug | `policy_debug.memory_prior` | Records detector control decision and range evidence. |
| Output | Trace | `detector_trace.json` | Remains diagnostic and separate from official metrics. |

## Interfaces

- `run_habitat_official_objectnav_eval(... target_detector_adapter=...)`
- `run_official_objectnav_episode_loop(... target_detector_adapter=...)`
- `OfficialDetectorTrace`
- `memory_belief_frontier`

No CLI flags are required in this first slice. The controller constants are
recorded in debug payloads so diagnostic runs can be audited before deciding
whether they deserve a public configuration surface.

## Data Flow

1. `memory_belief_frontier` calls the detector on the current RGB frame, as it
   already does for detector-confirmed STOP.
2. The best target-category match above confidence threshold is converted into
   a target-evidence payload:
   - bbox center offset from image center;
   - bbox area fraction;
   - finite positive median depth inside the bbox, when available.
3. If the bbox is horizontally off-center, the policy turns toward the target.
4. If the bbox is centered but depth/area do not yet satisfy the STOP gate, the
   policy moves forward when the center depth corridor is clear.
5. If bbox center, bbox area, and bbox depth satisfy the STOP gate, the policy
   emits STOP with `decision="stop_on_detector_range_confirmed"`.
6. If no usable target detection exists, the existing memory-belief frontier
   scoring path runs unchanged.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| False-positive target label | Official success remains false; detector trace shows evidence | STOP requires centered bbox and close depth, reducing premature STOP. |
| Detector bbox lacks depth | Debug records missing depth | Do not range-confirm STOP; approach only if forward corridor is clear. |
| Target is off-center | Bbox center offset exceeds tolerance | Turn toward bbox center before advancing. |
| Target is centered but far | Bbox depth exceeds STOP range or bbox is too small | Move forward when safe; otherwise fall back to frontier behavior. |
| Depth scale is ambiguous | Debug records whether depth looks normalized | Use conservative normalized and metric gates; treat live results as diagnostic. |

## Verification Plan

1. Add RED tests showing `memory_belief_frontier` turns toward an off-center
   target detection instead of stopping immediately.
2. Add RED tests showing a centered far target detection causes approach
   (`move_forward`) rather than STOP.
3. Add RED tests showing STOP is emitted only for centered, sufficiently large,
   close-depth target detections.
4. Preserve existing `memory_guided_frontier` detector STOP behavior.
5. Run focused official evaluator tests.
6. Run `compileall` and `git diff --check`.
7. Sync to Linux and run the focused official-memory test set in conda env
   `habitat`.
8. Run the four-episode YOLO diagnostic smoke again and compare official
   metrics plus built-in detector trace counts against the previous
   `memory_belief_frontier` artifact.

## Verification Result

Completed on 2026-05-30.

- RED tests failed for the expected reason: `memory_belief_frontier` still
  stopped immediately on any matching detector label.
- GREEN targeted tests passed after adding detector local control:
  - off-axis target bbox causes `center_detector_target`;
  - centered far target bbox causes `approach_detector_target`;
  - centered close-depth target bbox causes
    `stop_on_detector_range_confirmed`;
  - `memory_guided_frontier` still preserves the older immediate
    detector-confirmed STOP behavior.
- Local official evaluator tests passed: `38` tests.
- Local focused official-memory/exporter set passed: `60` tests.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set passed in conda env `habitat`:
  `60` tests.
- Linux `compileall` and `git diff --check` returned cleanly.

Diagnostic YOLO query smoke:

- Artifact:
  `runs/habitat_official_objectnav/memory_belief_frontier_detector_guided_approach_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.
- Official success stayed `0/4`; SPL stayed `0.0`; SoftSPL stayed
  `0.0009902771347611306`.
- Built-in detector trace recorded `196` calls, `257` detections, `23`
  target-match calls, and `23` target-match detections.
- The target episode ended with `decision="center_detector_target"`, bbox
  `[553, 68, 640, 173]`, center offset `0.43203125`, normalized depth median
  `0.40283340215682983`, and bbox area fraction `0.029736328125`.

This is not a benchmark improvement. It is positive evidence that delaying
STOP keeps the detector active long enough to collect more target-view
evidence, and negative evidence that simple centering is not yet enough to
solve the official navigation episode.

## Research Relevance

This slice turns detector evidence from a binary STOP trigger into an online
active-search signal. That is still not the final publishable policy, but it
is closer to the paper story: memory proposes where to search, detector
evidence updates local control, and official Habitat metrics arbitrate whether
the behavior actually solves ObjectNav.

## Open Questions

- Whether the conservative bbox/depth STOP gate improves official success or
  merely prevents premature failure.
- Whether normalized Habitat depth thresholds should become explicit CLI
  parameters after live diagnostics.
- Whether local visual servoing should eventually be replaced by a learned
  search/approach module trained from detector traces.
