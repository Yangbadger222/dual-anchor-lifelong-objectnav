# Design Doc: Official Detector-Confirmed Memory Stop

Date: 2026-05-30
Owner: Codex
Status: Implemented; negative YOLO query smoke completed

## Goal

Allow the official memory-guided ObjectNav policy to stop when the current RGB
observation contains a detector-confirmed target object, while preserving
Habitat-Lab official metrics and the existing memory-prior boundary.

## Non-Goals

- Do not replace Habitat official success/SPL metrics.
- Do not use semantic oracle visibility, target pose, route followers, or
  pathfinder shortcuts.
- Do not make lifecycle `habitat_world` anchors actionable.
- Do not claim a benchmark win from this slice alone.
- Do not solve learned memory ranking here; this is the current-view
  confirmation hook needed before stronger memory policies can be trusted.

## Background

The YOLO discovery/query smoke showed that generated episode-relative priors can
be consumed by `memory_guided_frontier`, but coordinate-only steering produced a
negative result. The policy selected a `tv_monitor` prior and repeatedly turned
toward memory, yet official success stayed `0/4` and SoftSPL regressed relative
to no-memory occupancy frontier.

ObjectNav policies need a current-view stop condition: if the target is visible
to a detector in the official RGB stream, STOP is a legitimate action candidate.
This should be optional and injected so tests can use fake detectors and live
smokes can use YOLO/Grounding-DINO.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`

The evaluator owns:

- accepting an optional target detector adapter in the episode loop;
- checking detector outputs against the current episode category;
- issuing STOP before memory steering/fallback when a high-confidence matching
  detection appears;
- recording detector-stop debug telemetry.

CLI detector wiring for query runs can follow after the core path is tested.
For the first live smoke, a Python command can inject `YoloWorldDetector`
directly.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Observation RGB | official `observation["rgb"]` | No semantic oracle. |
| Input | Target detector | object with `detect(rgb)` | Same adapter shape as discovery. |
| Input | Target category | Habitat episode object category | Normalized against detector labels. |
| Input | Min confidence | float | Defaults to `0.0` for API compatibility. |
| Output | Action | Habitat discrete action | STOP if detector confirms target. |
| Output | Debug | `policy_debug.memory_prior` | Includes detector category/confidence/source bbox. |

## Interfaces

```python
run_official_objectnav_episode_loop(
    env,
    policy="memory_guided_frontier",
    memory_anchors=anchors,
    target_detector_adapter=detector,
    target_detector_min_confidence=0.25,
)
```

`run_habitat_official_objectnav_eval(...)` forwards the same optional detector
adapter into the loop for programmatic smokes.

## Data Flow

1. At each `memory_guided_frontier` step, inspect current official RGB.
2. If a target detector is configured, call `detect(rgb)`.
3. Normalize detector label and episode object category.
4. If any detection matches and meets confidence threshold, record debug
   telemetry and return `stop`.
5. If no detector match exists, continue the existing memory anchor selection,
   bearing steering, corridor check, and occupancy fallback.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Missing RGB | `observation["rgb"]` absent | Skip detector stop and continue old policy. |
| Detector sees wrong category | normalized label mismatch | Do not stop; continue old policy. |
| Low confidence target | threshold check | Do not stop; continue old policy. |
| Detector false positive | official metric remains source of truth | Record detector debug; do not claim success unless Habitat says success. |
| Detector runtime failure | exception | Let smoke fail loudly; do not hide detector problems. |

## Verification Plan

1. Unit-test matching detector output stops before memory steering.
2. Unit-test low-confidence or wrong-category detector output does not stop.
3. Unit-test behavior remains unchanged without a detector.
4. Run focused official-memory tests and full suite locally.
5. Sync to Linux and run focused tests in conda env `habitat`.
6. Run a YOLO query smoke using the generated discovery prior and injected
   detector. Compare against the earlier generated-prior and occupancy context
   artifacts, but treat results as diagnostics only.

## Verification Result

Completed on 2026-05-30.

- Local detector-stop tests passed.
- Local focused official-memory set passed: `51` tests.
- Local full test suite passed: `342` tests.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory set passed in conda env `habitat`: `51` tests.
- Linux `git diff --check` returned cleanly.
- Linux YOLO query smoke wrote
  `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_stop_4ep_50steps_20260530_v1`.
- Traced rerun wrote
  `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_stop_trace_4ep_50steps_20260530_v1`.

The live smoke is negative evidence, not benchmark progress:

- Official success remained `0/4`.
- Official SPL remained `0.0`.
- Official SoftSPL remained `0.0009902771347611306`.
- The traced detector hook was called `196` times.
- YOLO produced `0` target-category detections across those calls, so
  `stop_on_detector` never had a legitimate match to use.

The root cause of this smoke's failure is therefore not missing policy wiring;
it is that the current memory-guided exploration path did not bring the target
into the detector's current-view evidence stream. This slice provides the
required stop interface, but a publishable system still needs stronger
memory-conditioned search, memory fusion/deduplication, and query-time
evidence accumulation.

## Research Relevance

Detector-confirmed STOP is not a novel algorithm by itself, but it is a
required interface for any publishable memory policy. Without it, the policy
can only stop on remembered coordinates, which is brittle under memory error,
duplicate anchors, and drift. This hook lets later learned or memory-scored
policies separate "go where memory predicts" from "stop because the object is
actually visible now."
