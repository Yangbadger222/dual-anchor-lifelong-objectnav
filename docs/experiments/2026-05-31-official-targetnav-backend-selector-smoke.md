# Experiment Report: Official TargetNav Backend Selector Smoke

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Does the base official TargetNav memory policy accept
`--targetnav-backend oracle_follower`, record the backend in the protocol
manifest, and activate the oracle backend when a target detector match appears?

## Hypothesis

The run should stay under the base policy name
`memory_active_perception_frontier_targetnav`, report
`targetnav.backend=oracle_follower`, mark the run as diagnostic-only, and expose
oracle backend status if the detector finds a current target view.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, base commit `0f14893` plus working-tree selector changes |
| Machine | Linux Habitat host `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini` |
| Simulator / robot | Habitat-Lab / Habitat-Sim |
| Key parameters | `policy=memory_active_perception_frontier_targetnav`, `targetnav_backend=oracle_follower`, YOLO-World `yolov8s-worldv2.pt`, categories `bed,chair,plant,sofa,toilet,tv_monitor`, `max_episodes=4`, `max_steps=100`, seed `313` |

## Command

```bash
ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_oracle_backend_selector_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav \
    --targetnav-backend oracle_follower \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313'
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Success rate | `0.0000` | Habitat official metric; diagnostic run is benchmark-invalid. |
| SPL | `0.0000` | Habitat official metric. |
| SoftSPL | `0.2263` | Mostly from the tv-monitor episode where oracle suffix stopped near the goal. |
| Mean distance to goal | `4.1786` | Habitat official metric. |
| Target-match calls | `1` | Detector trace. |
| Target-match detections | `1` | Detector trace. |
| Oracle-follow decisions | `38` | Policy trace `follow_pathfinder_suffix`. |
| Failures | `4` | No official successes. |

## Observations

- The protocol manifest reports
  `targetnav.backend=oracle_follower`,
  `targetnav.source_validity=oracle_diagnostic_only`, and
  `invalid_for_benchmark_claim_reason=targetnav_oracle_backend_diagnostic`.
- The tv-monitor episode activated the oracle backend at step `4`, followed it
  through step `41`, and stopped with backend status `SUCCEEDED`.
- The activated trace records `backend_id=pathfinder_suffix_oracle`,
  `reason=oracle_follower_stop`, `privileged_oracle=true`, and
  `benchmark_valid=false`.
- The run remains a diagnostic smoke. It demonstrates selector plumbing and
  backend activation, not benchmark-valid ObjectNav performance.

## Result

The first-class backend selector works in the real Habitat run path. The same
base memory TargetNav policy can now run with the oracle diagnostic executor and
records that fact clearly in both manifest and per-episode debug.

## Follow-up

- Use this selector to run paired oracle and non-oracle memory diagnostics under
  the same memory policy name.
- Do not use oracle-backed numbers as benchmark-facing results.
- Next benchmark-valid work should focus on a non-oracle executor that reduces
  the current low-level control bottleneck.
