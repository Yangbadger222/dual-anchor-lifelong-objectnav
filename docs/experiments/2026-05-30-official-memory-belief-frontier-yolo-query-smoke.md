# Experiment Report: Official Memory-Belief Frontier YOLO Query Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Does the first `memory_belief_frontier` policy produce more target-view detector
evidence than nearest-anchor `memory_guided_frontier` on the same generated
YOLO memory-prior diagnostic slice, while still using official Habitat metrics?

## Hypothesis

Scoring frontiers by spatial belief around the generated memory anchors should
change the query path enough to increase target-category detector matches near
memory. This may not improve official success yet, because a detector match can
occur while the agent is still outside Habitat's success radius or on a false
positive.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini`, `00802-wcojb4TFT35` first four episodes |
| Simulator | Habitat-Lab official `ObjectNav-v1` environment |
| Key parameters | `memory_belief_frontier`, `max_episodes=4`, `max_steps=50`, `seed=313`, YOLO-World `yolov8s-worldv2.pt`, detector confidence `0.25`, memory prior from `discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |

## Command

```bash
ssh badger@100.88.131.52
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTHONPATH=src/objectnav_core python - <<'PY'
# Built YoloWorldDetector with ObjectNav categories and called
# run_habitat_official_objectnav_eval(... policy="memory_belief_frontier",
# target_detector_adapter=detector, target_detector_min_confidence=0.25).
PY
```

Artifacts:

- `runs/habitat_official_objectnav/memory_belief_frontier_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_belief_frontier_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/detector_trace.json`

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Success rate | `0.0` | Official `habitat.Env.get_metrics()`, `0/4` episodes |
| SPL | `0.0` | Official metric |
| SoftSPL | `0.0009902771347611306` | Same as nearest-anchor memory smoke |
| Mean distance to goal | `5.880594372749329` | Official summary |
| Detector calls | `152` | Built-in detector trace |
| Detections | `81` | Built-in detector trace |
| Target-match calls | `1` | Built-in detector trace |
| Target-match detections | `1` | Built-in detector trace |

Context:

| Policy | Success | SoftSPL | Target-match detections |
|---|---:|---:|---:|
| `memory_guided_frontier` + generated YOLO prior + detector trace | `0/4` | `0.0009902771347611306` | `0` |
| `memory_belief_frontier` + generated YOLO prior + detector trace | `0/4` | `0.0009902771347611306` | `1` |
| `occupancy_frontier` same budget | `0/4` | `0.03315005152623973` | not run with detector trace |

## Observations

- `memory_belief_frontier` selected the generated `tv_monitor` memory and
  reached a frame where YOLO emitted a matching `tv_monitor` detection.
- The policy then recorded `decision="stop_on_detector"`.
- Habitat official success remained `0.0` for that episode, so the detector
  match was not sufficient evidence for a successful STOP.
- Compared with nearest-anchor steering, target-view detector evidence improved
  from `0` to `1` target-match detections, but official navigation quality did
  not improve.

## Result

This is a useful negative/diagnostic result, not a benchmark claim. The first
belief-frontier policy can increase target-view detector evidence, but immediate
STOP on any matching detector label is too weak for official ObjectNav success.

## Follow-up

- Replace immediate detector STOP with range-aware detector confirmation:
  approach or center the detected object until depth/range suggests Habitat
  success is plausible, then STOP.
- Add memory fusion/deduplication so generated anchors form a better target
  belief distribution.
- Scale beyond this four-episode smoke only after the stop/approach behavior is
  fixed and official metrics improve honestly.
