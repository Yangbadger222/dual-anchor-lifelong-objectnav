# Experiment Report: Official Detector-Guided Memory Approach YOLO Query Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Does range-aware detector centering/approach prevent premature detector STOP
and improve official ObjectNav metrics on the same generated YOLO memory-prior
diagnostic slice?

## Hypothesis

Replacing immediate STOP with detector-guided centering and range confirmation
should increase target-view detector evidence. It may not improve official
success yet if local centering oscillates or if the memory/search policy still
fails to reach a valid stopping pose.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini`, first four episodes |
| Simulator | Habitat-Lab official `ObjectNav-v1` environment |
| Key parameters | `memory_belief_frontier`, `max_episodes=4`, `max_steps=50`, `seed=313`, YOLO-World `yolov8s-worldv2.pt`, detector confidence `0.25`, memory prior from `discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |

## Command

```bash
ssh badger-linux
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python - <<'PY'
# Built YoloWorldDetector with ObjectNav categories and called
# run_habitat_official_objectnav_eval(... policy="memory_belief_frontier",
# target_detector_adapter=detector, target_detector_min_confidence=0.25).
PY
```

Artifacts:

- `runs/habitat_official_objectnav/memory_belief_frontier_detector_guided_approach_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_belief_frontier_detector_guided_approach_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/detector_trace.json`

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Success rate | `0.0` | Official `habitat.Env.get_metrics()`, `0/4` episodes |
| SPL | `0.0` | Official metric |
| SoftSPL | `0.0009902771347611306` | No improvement over previous memory-belief smoke |
| Mean distance to goal | `5.880594372749329` | Official summary |
| Detector calls | `196` | Built-in detector trace |
| Detections | `257` | Built-in detector trace |
| Target-match calls | `23` | Built-in detector trace |
| Target-match detections | `23` | Built-in detector trace |

Context:

| Policy | Success | SoftSPL | Target-match detections |
|---|---:|---:|---:|
| `memory_guided_frontier` + generated YOLO prior + detector trace | `0/4` | `0.0009902771347611306` | `0` |
| `memory_belief_frontier` immediate detector STOP | `0/4` | `0.0009902771347611306` | `1` |
| `memory_belief_frontier` detector-guided approach | `0/4` | `0.0009902771347611306` | `23` |

## Observations

- The new policy no longer ended the target episode with immediate
  `stop_on_detector`.
- The target episode ended with `decision="center_detector_target"`, bbox
  `[553, 68, 640, 173]`, center offset `0.43203125`, normalized bbox depth
  median `0.40283340215682983`, and bbox area fraction `0.029736328125`.
- Detector evidence improved substantially, but official success, SPL, SoftSPL,
  and mean distance-to-goal did not improve.
- The action trace still shows turn oscillation in later episodes, so this
  slice exposes a local-control/search coupling problem rather than solving the
  benchmark.

## Result

This is a useful diagnostic result, not a benchmark claim. Range-aware detector
gating prevents the most obvious premature STOP and greatly increases
target-match evidence, but it does not yet produce an official success.

## Follow-up

- Add step-level policy decision tracing so detector local-control behavior can
  be diagnosed across the full episode, not only in final episode debug.
- Replace single-frame centering with an evidence accumulator or local visual
  servo state that avoids turn oscillation.
- Fuse generated memory anchors into a stronger target belief before broader
  official comparisons.
