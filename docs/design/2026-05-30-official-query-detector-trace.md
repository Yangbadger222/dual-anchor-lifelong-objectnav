# Design Doc: Official Query Detector Trace

Date: 2026-05-30
Owner: Codex
Status: Implemented; Linux and live-smoke verification complete

## Goal

Make query-time detector evidence reproducible for official Habitat ObjectNav
memory-policy runs by writing a diagnostic detector trace artifact whenever an
injected target detector is used.

## Non-Goals

- Do not change official Habitat metrics or derive success from detector
  outputs.
- Do not add semantic oracle, target pose, pathfinder, or ground-truth
  visibility access.
- Do not make detector traces required for policies without a detector.
- Do not use detector traces as policy input beyond the existing
  detector-confirmed STOP check.
- Do not claim benchmark progress from trace logging.

## Background

The detector-confirmed STOP hook passed unit tests, but the first YOLO query
smoke stayed at `0/4` success. An ad hoc wrapper was needed to prove the hook
was exercised `196` times and that YOLO emitted `0` target-category matches on
the query frames. Future memory-policy research needs this evidence captured by
the evaluator itself, otherwise each negative run requires a one-off script and
is hard to audit.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`

The official evaluator owns:

- creating an optional detector trace collector for query runs;
- recording every detector call made by `memory_guided_frontier`;
- summarizing target-match counts in `summary.json`;
- writing a sidecar `detector_trace.json` artifact.

The trace is an artifact of the evaluator, not a new policy signal.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Observation RGB | official `observation["rgb"]` | Same stream already used by detector STOP. |
| Input | Target detector | object with `detect(rgb)` | Optional. |
| Input | Target category | Habitat episode object category | Used only for trace match labels and STOP filtering. |
| Output | Detector trace summary | `summary.json` fields | Counts calls, detections, target matches, missing RGB. |
| Output | Detector trace artifact | `detector_trace.json` | Per-call, per-detection diagnostic payload. |

## Interfaces

Programmatic evaluator call:

```python
run_habitat_official_objectnav_eval(
    output_dir,
    policy="memory_guided_frontier",
    memory_prior_path=prior_path,
    target_detector_adapter=detector,
    target_detector_min_confidence=0.25,
    write_detector_trace=True,
)
```

Episode loop call:

```python
trace = OfficialDetectorTrace()
rows = run_official_objectnav_episode_loop(
    env,
    policy="memory_guided_frontier",
    target_detector_adapter=detector,
    target_detector_min_confidence=0.25,
    detector_trace=trace,
)
```

Default behavior should be conservative:

- no detector means no trace artifact;
- detector plus full evaluator writes the trace by default;
- tests and custom callers can pass `write_detector_trace=False`.

## Data Flow

1. `run_habitat_official_objectnav_eval` creates a trace collector when a
   target detector is configured and trace writing is enabled.
2. `run_official_objectnav_episode_loop` stores the trace collector in
   `OfficialPolicyState`.
3. `_detector_confirmed_target` records a trace event before returning:
   missing RGB, detection count, all detection labels/confidences/bboxes, and
   target-match flags after applying the configured confidence threshold.
4. The policy continues exactly as before: STOP only when a target match exists;
   otherwise memory steering/fallback proceeds.
5. The full evaluator writes `detector_trace.json` and adds summary counts plus
   the artifact filename to `summary.json`.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Missing RGB | Trace event with `missing_rgb=true` | Continue old policy behavior. |
| Detector returns malformed bbox | Bbox payload is `null` | Still record category/confidence. |
| Detector raises | Run fails loudly | Do not hide detector/runtime failures. |
| Large traces | One compact JSON record per detector call | Acceptable for smoke/diagnostic runs; future large benchmarks can disable or sample traces. |
| Trace accidentally used as metric | Official metrics remain copied only from `env.get_metrics()` | Summary labels trace as diagnostic. |

## Verification Plan

1. Unit-test that a detector-backed query run records detector calls and writes
   `detector_trace.json`.
2. Unit-test that target-match counts are correct for matching, wrong-label,
   and low-confidence detections.
3. Unit-test that no detector does not write a detector trace artifact.
4. Run focused official-memory tests.
5. Run `compileall` and `git diff --check`.
6. Later live smoke: rerun the four-episode YOLO query without an ad hoc
   wrapper and confirm the built-in trace reproduces the `0` target-match
   diagnosis.

## Verification Result

Completed on 2026-05-30.

- RED trace-artifact test failed because `detector_trace.json` was missing.
- GREEN trace-artifact and no-detector guard tests passed: `2` tests.
- Nonmatching-detection trace guard passed: `1` test.
- Official evaluator test file passed: `32` tests.
- Focused official-memory/exporter set passed: `54` tests.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set passed in conda env `habitat`:
  `54` tests.
- Linux `compileall` and `git diff --check` returned cleanly.
- Built-in trace YOLO query smoke wrote
  `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_trace_builtin_4ep_50steps_20260530_v1`.
  It reproduced the prior diagnosis without an ad hoc wrapper: `196` detector
  calls, `234` detections, `0` target-match calls, and `0` target-match
  detections.

## Research Relevance

This is research infrastructure, not the algorithmic contribution. It makes the
next algorithmic step measurable: memory-conditioned active search must be able
to show whether it increases target-view detector evidence near remembered
anchors, not only whether it changes final success.
