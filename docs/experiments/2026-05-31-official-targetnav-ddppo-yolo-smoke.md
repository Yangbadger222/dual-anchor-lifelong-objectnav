# Experiment Report: Official TargetNav DDPPO YOLO Smoke

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Can the benchmark-valid TargetNav policy hand detector-depth target beliefs to
the Habitat-Baselines HM3D depth PointNav/DDPPO backend inside the official
Habitat ObjectNav evaluation loop?

## Hypothesis

The DDPPO backend should load and execute without using pathfinder or episode
goal state online. If YOLO produces target-category detections, policy traces
should include `targetnav_ddppo_move` or `targetnav_ddppo_turn` decisions.
Success may still remain low because PointNav receives noisy detector-depth
target beliefs rather than oracle goal coordinates.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `0f14893` plus uncommitted DDPPO backend changes |
| Machine | `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini`, `objectnav_hm3d_v1/val_mini/val_mini.json.gz` |
| Simulator / robot | Habitat-Lab official `ObjectNav-v1` env |
| Key parameters | YOLO-World `yolov8s-worldv2.pt`, detector conf `0.25`, max episodes `4`, max steps `100`, seed `313`, DDPPO checkpoint `hm3d-depth/ckpt.60.pth`, DDPPO device `cuda` |

## Command

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_ddppo_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav_ddppo \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --targetnav-ddppo-checkpoint-path models/habitat/ddppo/hm3d_ddppo_pointnav_baselines_v1/hm3d-depth/ckpt.60.pth \
    --targetnav-ddppo-device cuda \
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
| Success rate | `0.0` | `0/4` official Habitat success |
| SPL | `0.0` | Official Habitat SPL |
| SoftSPL | `0.06665590634964569` | Higher than the prior occupancy TargetNav smoke, but not a success claim |
| Mean distance to goal | `5.384531855583191` | Official Habitat distance |
| Detector target-match calls | `16` | `18` target-match detections |
| DDPPO decisions | `95` | `56` move, `39` turn |
| Output | `runs/habitat_official_objectnav/targetnav_ddppo_yolo_4ep_100steps_20260531_v1` | Contains summary, episodes, detector trace, and policy trace |

## Observations

- Episode `tv_monitor` activated the DDPPO backend and ended with
  `targetnav_ddppo_move` as the last memory decision.
- The final DDPPO debug pointgoal was `[4.008624, 1.990981]`, with smoothed
  detector-depth target belief sample count `16`.
- The first one-episode smoke on `chair` was mechanically valid but did not
  activate DDPPO because there were zero target-category matches.
- The four-episode run used official Habitat metrics and did not use pathfinder
  or episode goal state online.

## Result

The integration is mechanically valid: the official ObjectNav loop can load the
HM3D depth DDPPO checkpoint, pass TargetNav pointgoal/depth observations into
the learned policy, and execute returned actions. Performance is not solved:
official success remains `0/4`.

## Follow-up

- Diagnose why DDPPO does not close the remaining distance on the matched
  `tv_monitor` episode.
- Compare the DDPPO episode trace against target-belief quality, depth scale,
  and PointNav action distribution.
- Consider a short adapter/fine-tune layer if raw detector-depth target beliefs
  are too noisy for an off-the-shelf PointNav policy.
