# Experiment Report: Official Path-Aware Active-Perception Viewpoint YOLO Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed diagnostic; negative official result

## Question

Does replacing unknown-frontier destinations with reachable free viewpoint
candidates improve the detector-backed official `memory_active_perception_frontier`
smoke?

## Hypothesis

Scoring reachable free viewpoints is more physically meaningful than scoring
unknown frontier cells. It should expose better audit fields and prevent
unreachable candidate selection, but may not improve official metrics unless
the policy also commits to scanning from the selected viewpoint.

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

Verification:

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
  --output runs/habitat_official_objectnav/memory_active_perception_frontier_path_aware_viewpoint_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1 \
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

| Run | Official success | SPL | SoftSPL | Mean distance-to-goal | Target-match calls | Active-perception decisions |
|---|---:|---:|---:|---:|---:|---:|
| Rotation-aware frontier-cell scorer | `0/4` | `0.0` | `0.03315001996589104` | `5.637647747993469` | `30` | `29` |
| Path-aware free-viewpoint scorer | `0/4` | `0.0` | `0.0009902771347611306` | `6.065265536308289` | `13` | `24` |

Trace summary for the path-aware run:

| Trace field | Value |
|---|---:|
| Detector calls | `196` |
| Detector detections | `189` |
| Target-match detections | `13` |
| `turn_toward_memory_active_perception_frontier` | `24` |
| `fallback_occupancy_frontier` | `158` |
| `center_detector_target` | `3` |
| `approach_detector_target_after_center_loss` | `9` |
| `reacquire_detector_target` | `2` |
| Selected expected evidence range | `0.5103327473937014..0.5200065629595595` |
| Selected path-distance range | `0.25..3.0` |

## Observations

- The implementation behaves mechanically as intended: active-perception trace
  entries now include `selected_viewpoint_cell`, `selected_frontier_cell`, and
  finite `path_distance_m`.
- The selected candidates are reachable free cells adjacent to unknown frontier
  cells. The first active step selected viewpoint `[38, 38]` next to frontier
  `[38, 37]`, with path distance `1.0`.
- Official performance regressed relative to the rotation-aware frontier-cell
  smoke. Target-match detector calls also dropped from `30` to `13`.
- This suggests the policy now has a cleaner candidate interface but still
  lacks temporal commitment and explicit rotate/scan behavior once a viewpoint
  is selected or reached.

## Result

Path-aware viewpoint scoring is useful infrastructure but not a performance
improvement by itself. It should be kept as an auditable boundary for stronger
active-perception algorithms, while the next algorithmic slice should add
stateful evidence acquisition at selected viewpoints rather than continuing to
tune one-step waypoint scores.

## Follow-up

- Add a bounded active scan/commit phase keyed by selected viewpoint and
  memory-anchor bearing.
- Record whether detector target matches improve during the scan phase before
  scaling beyond small smokes.
- Continue treating official Habitat `success`, `spl`, `soft_spl`, and
  `distance_to_goal` as the only benchmark-facing metrics.
