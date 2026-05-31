# Experiment Report: Official Adaptive Detector Servo YOLO Query Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Does a one-step adaptive detector servo reduce the detector/fallback
oscillation observed in the policy-step trace and improve official ObjectNav
metrics?

## Hypothesis

If the target disappears immediately after a detector-centering turn, flipping
the centering direction and performing one reacquisition turn should avoid
handing control back to frontier fallback and may reduce the two-step
oscillation.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini`, first four episodes |
| Simulator | Habitat-Lab official `ObjectNav-v1` environment |
| Key parameters | `memory_belief_frontier`, `max_episodes=4`, `max_steps=50`, `seed=313`, YOLO-World `yolov8s-worldv2.pt`, detector confidence `0.25`, generated YOLO memory prior |

## Artifacts

- `runs/habitat_official_objectnav/memory_belief_frontier_adaptive_servo_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_belief_frontier_adaptive_servo_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/detector_trace.json`
- `runs/habitat_official_objectnav/memory_belief_frontier_adaptive_servo_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/policy_trace.json`

## Metrics

| Metric | Previous trace run | Adaptive servo run |
|---|---:|---:|
| Official success | `0/4` | `0/4` |
| SPL | `0.0` | `0.0` |
| SoftSPL | `0.0009902771347611306` | `0.0009902771347611306` |
| Detector calls | `196` | `196` |
| Detector detections | `257` | `224` |
| Target-match detections | `23` | `23` |
| `center_detector_target` decisions | `23` | `23` |
| `fallback_occupancy_frontier` decisions | `170` | `148` |
| `reacquire_detector_target` decisions | `0` | `22` |

## Observations

- The adaptive servo replaced the odd-step fallback reversals with explicit
  `reacquire_detector_target` decisions.
- It did not change the action-count distribution:
  `move_forward=49`, `turn_left=87`, `turn_right=60`, `stop=4`.
- In the target episode, the policy still cycled around the same headings:
  detector centering at approximately `-2.094`, reacquire at the neighboring
  heading, then detector centering again at approximately `-2.094`.
- Official metrics did not improve.

## Result

This is negative evidence for the one-step hard-flip servo. The trace confirms
that the policy needs persistent evidence accumulation or a stronger local
controller, not another immediate action reversal.

## Follow-up

- Replace single-step flipping with a local detector evidence state over
  multiple frames, including last-seen bbox, age, action history, and a bounded
  search pattern.
- Consider learning a local visual-servo value model from detector traces
  rather than encoding more single-step rules.
- Keep official metric claims negative until SR/SPL move.
