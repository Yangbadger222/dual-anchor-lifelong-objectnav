# Experiment Report: Official TargetNav FMM YOLO Smoke

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Can the SemExp-style FMM/local-distance-field TargetNav backend, using only the
online depth-built occupancy map and detector-depth target belief, solve the
four-episode official ObjectNav smoke more reliably than the previous local
controllers?

## Hypothesis

FMM should avoid the fixed turn-loop behavior seen in the earlier occupancy
TargetNav backend. If the detector target belief and sparse depth-built map are
good enough, the policy should convert target reacquisition into at least one
successful official ObjectNav episode.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `0f14893` plus uncommitted FMM and dataset-export changes |
| Machine | `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini`, `objectnav_hm3d_v1/val_mini/val_mini.json.gz` |
| Simulator / robot | Habitat-Lab official `ObjectNav-v1` env |
| Key parameters | Policy `memory_active_perception_frontier_targetnav_fmm`, YOLO-World `yolov8s-worldv2.pt`, categories `bed,chair,plant,sofa,toilet,tv_monitor`, `max_episodes=4`, `max_steps=100`, seed `313` |

## Command

```bash
PYTHONPATH=src/objectnav_core /home/badger/anaconda3/bin/conda run -n habitat \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_fmm_active_perception_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav_fmm \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313

PYTHONPATH=src/objectnav_core /home/badger/anaconda3/bin/conda run -n habitat \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_fmm_no-false-stop_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav_fmm \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313
```

## Metrics

| Variant | Success | SPL | SoftSPL | Mean Distance | Target-match Calls | Notes |
|---|---:|---:|---:|---:|---:|---|
| Initial FMM smoke | `0/4` | `0.0` | `0.0009902771347611306` | `5.880594372749329` | `2` | `tv_monitor` stopped at step `13` while pointgoal was still `2.31275m`. |
| No-false-stop FMM smoke | `0/4` | `0.0` | `0.01716268349268174` | `5.758422017097473` | `77` | `tv_monitor` ran full budget; local behavior became oscillation/sparse-map fallback. |

## Observations

- FMM is implemented and unit-tested, and the Linux focused FMM tests passed.
- The initial smoke exposed a root-cause bug: when the sparse map had no
  reachable free cell nearer the target, `_nearest_reachable_free_cell_to_target`
  could return the current cell. FMM then interpreted a zero distance field as a
  TargetNav stop even though `pointgoal_with_gps_compass` was `[2.31275,
  -1.12022]`.
- A regression test now prevents this false stop. The backend returns fallback
  reason `selected_current_cell_far_from_target` when the selected reachable
  cell is the current cell but the target pointgoal remains outside the stop
  radius.
- The fixed smoke increased target-match calls from `2` to `77` and allowed
  `tv_monitor` to keep running, but it still did not reach success.
- Most episodes still fell back to occupancy frontier because no matching memory
  target was available or because the detector was not confidently reacquired.

## Result

FMM is a valid and useful classical local-planner baseline, and the premature
stop bug is fixed. It is not sufficient by itself on this four-episode smoke:
official success remains `0/4`. The remaining blocker is not DDPPO contract
mismatch; it is sparse online map coverage, detector/target-belief stability,
and oscillatory local control after TargetNav activation.

## Follow-up

- Keep FMM as the benchmark-valid non-learned baseline.
- Add a stronger local-control policy for sparse maps: either unknown-as-cost
  FMM/semantic exploration, or the official-contract oracle TargetNav dataset
  exporter plus learned local policy.
- Use the fixed FMM trace to mine hard local states, especially the
  `tv_monitor` oscillation after target reacquisition.
