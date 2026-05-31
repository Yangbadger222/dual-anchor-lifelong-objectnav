# Experiment Report: Official Policy Step Trace YOLO Query Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Can a per-step official policy trace explain why detector-guided
`memory_belief_frontier` increased target detections but did not improve
official ObjectNav success?

## Hypothesis

The policy is likely alternating between detector local control and fallback
frontier behavior. A compact per-step trace should identify whether target
matches are consecutive, whether fallback reverses detector control, and
whether STOP is still premature.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini`, first four episodes |
| Simulator | Habitat-Lab official `ObjectNav-v1` environment |
| Key parameters | `memory_belief_frontier`, `max_episodes=4`, `max_steps=50`, `seed=313`, YOLO-World `yolov8s-worldv2.pt`, detector confidence `0.25`, generated YOLO memory prior |

## Artifacts

- `runs/habitat_official_objectnav/memory_belief_frontier_policy_trace_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_belief_frontier_policy_trace_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/detector_trace.json`
- `runs/habitat_official_objectnav/memory_belief_frontier_policy_trace_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/policy_trace.json`

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Success rate | `0.0` | Official `habitat.Env.get_metrics()`, `0/4` episodes |
| SPL | `0.0` | Official metric |
| SoftSPL | `0.0009902771347611306` | No metric gain |
| Detector calls | `196` | Built-in detector trace |
| Target-match detections | `23` | Built-in detector trace |
| Policy-trace steps | `200` | `4` episodes x `50` actions |

Policy decision counts:

| Decision | Count |
|---|---:|
| `fallback_occupancy_frontier` | `170` |
| `center_detector_target` | `23` |
| `turn_toward_memory_belief_frontier` | `3` |
| `budget_stop` | `4` |

## Observations

- In episode 2, steps `0..2` were
  `turn_toward_memory_belief_frontier`/`turn_left`.
- Step `3` fell back to occupancy frontier because the memory-belief corridor
  was blocked.
- Every even step from `4` through `48` was
  `center_detector_target`/`turn_right` with the same right-edge target bbox
  `[553, 68, 640, 173]`.
- Every odd step from `5` through `47` was
  `fallback_occupancy_frontier`/`turn_left` with
  `fallback_reason="blocked_memory_belief_frontier_corridor"`.
- The final step was `budget_stop`, and official success remained false.

## Result

The trace explains the failure. The target is repeatedly detected, but the
policy only owns control on target-detection frames. When the target disappears
for one frame, blocked fallback reverses the detector centering turn, creating
a two-step oscillation.

## Follow-up

- Add a persistent detector-local-control state so recent target evidence keeps
  ownership for a short horizon instead of immediately handing control back to
  fallback.
- Record detector-evidence age and last center offset in policy debug.
- Evaluate whether this reduces oscillation before attempting a broader
  benchmark run.
