# Experiment Report: Official Active-Perception Rotation-Aware YOLO Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed diagnostic; negative official success result

## Question

Does removing the approach-heading cosine from the active-perception frontier
scorer preserve positive expected evidence for side/standoff viewpoints and
change online official Habitat ObjectNav behavior under a detector-backed
YOLO query smoke?

## Hypothesis

If a frontier is treated as a prospective viewpoint where the agent can rotate
before sensing, then side and standoff frontiers near a remembered anchor should
retain positive expected evidence. The active-perception branch should fire
more often than the flawed scorer, but a four-episode smoke is still only a
diagnostic and should not be treated as a benchmark claim.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini` |
| Simulator / robot | Habitat-Lab official `ObjectNav-v1` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Query memory prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |
| Key parameters | `memory_active_perception_frontier`, `max_episodes=4`, `max_steps=50`, `seed=313`, `memory_min_confidence=0.25` |

## Command

Local and Linux verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_local_action_dataset.py \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

Detector-backed smoke:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --output runs/habitat_official_objectnav/memory_active_perception_frontier_rotation_aware_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1 \
  --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
  --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --split val_mini \
  --policy memory_active_perception_frontier \
  --max-episodes 4 \
  --max-steps 50 \
  --seed 313 \
  --validate-habitat \
  --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
  --memory-min-confidence 0.25 \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor
```

## Metrics

| Run | Official success | SPL | SoftSPL | Mean distance-to-goal | Active-perception decisions | Selected expected evidence | Zero-evidence top candidates |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original approach-heading scorer | `0/4` | `0.0` | `0.02518699682786324` | `5.697803378105164` | `8` | `0.0..0.5177555778603277` | `21/40` |
| Rotation-aware scorer | `0/4` | `0.0` | `0.03315001996589104` | `5.637647747993469` | `29` | `0.4498654945233323..0.519892411627075` | `0/145` |

Detector and decision trace summary for the rotation-aware run:

| Trace field | Value |
|---|---:|
| Detector calls | `196` |
| Detector detections | `173` |
| Target-match detector calls | `30` |
| Target-match detections | `30` |
| `turn_toward_memory_active_perception_frontier` | `28` |
| `move_toward_memory_active_perception_frontier` | `1` |
| `fallback_occupancy_frontier` | `147` |
| `center_detector_target` | `15` |
| `approach_detector_target_after_center_loss` | `3` |
| `reacquire_detector_target` | `2` |

## Observations

- The regression target was confirmed: with rotation-aware scoring,
  `view_bearing_quality` is `1.0` for selected active-perception candidates and
  no inspected top candidates have zero expected evidence.
- The selected candidate changed on the first `tv_monitor` active step from
  the closest nearly approach-aligned cell `[40, 39]` to a stronger standoff
  cell `[39, 38]`, with expected evidence `0.5165662157613107`.
- The active-perception branch now fires often enough to matter in the trace,
  but only one of the four smoke episodes has a matching memory anchor. The
  other episodes fall back with `fallback_reason=no_matching_memory`.
- Official success remains `0/4`. The small SoftSPL and distance improvements
  are diagnostic only and are not sufficient for a paper claim.

## Result

The scorer bug is fixed at the intended mechanism level: active-perception
candidate evidence no longer collapses because of approach heading. The online
policy now chooses and traces nonzero-evidence viewpoints, but this bounded
smoke still does not demonstrate a successful ObjectNav improvement.

## Follow-up

- Improve memory-prior coverage for query categories before larger active
  perception sweeps.
- Replace the lightweight standoff prior with a path-aware or learned
  evidence-acquisition value that reasons about reaching a viewpoint and then
  rotating/scanning from it.
- Keep reporting official Habitat `success`, `spl`, `soft_spl`, and
  `distance_to_goal` as the benchmark-facing metrics.
