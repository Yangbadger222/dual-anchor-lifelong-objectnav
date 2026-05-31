# Experiment Report: Official Detector-Confirmed Memory Stop YOLO Query Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

When the official `memory_guided_frontier` query policy receives both a
generated YOLO memory prior and an injected YOLO current-view detector, does the
new detector-confirmed STOP hook fire and improve official Habitat ObjectNav
metrics on the same four-episode val-mini diagnostic slice?

## Hypothesis

If the memory-guided policy brings the agent into a view where YOLO detects the
episode target category, the policy should emit `stop_on_detector` before
coordinate-only memory steering. If the agent never sees the target category,
official metrics should remain unchanged and the trace should show no target
matches.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini`, `00802-wcojb4TFT35` first four episodes |
| Simulator / robot | Habitat-Lab official `ObjectNav-v1` environment |
| Key parameters | `memory_guided_frontier`, `max_episodes=4`, `max_steps=50`, `seed=313`, YOLO-World `yolov8s-worldv2.pt`, detector confidence `0.25`, memory prior from `discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |

## Command

Original query smoke:

```bash
ssh badger@100.88.131.52
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTHONPATH=src/objectnav_core python - <<'PY'
# Built YoloWorldDetector(weights="yolov8s-worldv2.pt",
# categories=["bed", "chair", "plant", "sofa", "toilet", "tv_monitor"],
# conf=0.25), then injected it into run_habitat_official_objectnav_eval
# with policy="memory_guided_frontier" and the generated discovery prior.
PY
```

Trace rerun used the same parameters plus a wrapper around `detect(rgb)` that
recorded per-call episode id, target category, labels, confidences, and whether
each detection matched the current target.

Artifacts:

- `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_stop_4ep_50steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_stop_trace_4ep_50steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_stop_trace_4ep_50steps_20260530_v1/detector_trace.json`
- `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_trace_builtin_4ep_50steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_trace_builtin_4ep_50steps_20260530_v1/detector_trace.json`

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Success rate | `0.0` | Official `habitat.Env.get_metrics()` summary, `0/4` episodes |
| SPL | `0.0` | Official metric |
| SoftSPL | `0.0009902771347611306` | Same as prior generated-memory smoke |
| Mean distance to goal | `5.880594372749329` | Official summary |
| Detector calls | `196` | Built-in trace artifact |
| Detections | `234` | Built-in trace artifact |
| Target-match detector calls | `0` | Built-in trace artifact |
| Target-match detections | `0` | Built-in trace artifact |

Same-budget context from the prior discovery report:

| Policy | Success | SPL | SoftSPL |
|---|---:|---:|---:|
| `memory_guided_frontier` + generated prior + detector stop | `0/4` | `0.0` | `0.0009902771347611306` |
| `memory_guided_frontier` + generated prior, no detector stop | `0/4` | `0.0` | `0.0009902771347611306` |
| `occupancy_frontier` | `0/4` | `0.0` | `0.03315005152623973` |

## Observations

- The detector STOP hook was exercised: the traced run recorded `196`
  detector calls from the official action loop.
- The built-in evaluator trace reproduced the ad hoc wrapper diagnosis without
  custom detector wrapping.
- No call produced a detection whose normalized label matched the current
  episode target category at confidence `>=0.25`.
- Episode-level trace summary:
  - target `chair`: YOLO repeatedly detected `bed`, never `chair`;
  - target `toilet`: YOLO detected `bed` and `tv_monitor`, never `toilet`;
  - target `tv_monitor`: YOLO detected `bed`, `chair`, and `sofa`, never
    `tv_monitor`;
  - target `bed`: YOLO produced no detections during the query path.
- The matching generated memory prior was still selected on the `tv_monitor`
  episode, but the final decision remained `turn_toward_memory`, not
  `stop_on_detector`.

## Result

Detector-confirmed STOP is wired correctly, but it did not help this diagnostic
query slice because the policy did not navigate into a target-visible detector
state. This is negative evidence for the current nearest-anchor steering
consumer, not evidence against the detector-stop interface itself.

No benchmark-facing improvement should be claimed from this run.

## Follow-up

- Add query-time detector trace logging to the reusable evaluator or CLI so
  future failures do not require an ad hoc wrapper.
- Replace nearest-anchor steering with a stronger memory-conditioned local
  search objective that actively increases target-view evidence near remembered
  anchors.
- Add memory fusion/deduplication before broad benchmark comparisons.
- Consider a fair discovery/query protocol where generated memories are
  episode-compatible but query paths are evaluated under official metrics only.
