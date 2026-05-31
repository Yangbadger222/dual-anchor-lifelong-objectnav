# Experiment Report: Official Active-Perception Viewpoint Scan YOLO Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed diagnostic; negative official result

## Question

Does adding a bounded orient/scan phase at selected active-perception
viewpoints improve the four-episode detector-backed official Habitat ObjectNav
smoke?

## Hypothesis

If the path-aware selector reaches a free viewpoint, turning toward the
remembered anchor should create better detector views on subsequent steps. This
may recover the path-aware viewpoint regression, but a hand-built scan primitive
is unlikely to be a final paper-quality controller.

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
  --output runs/habitat_official_objectnav/memory_active_perception_frontier_viewpoint_scan_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1 \
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

| Run | Official success | SPL | SoftSPL | Mean distance-to-goal | Target-match calls | Active/scan decisions |
|---|---:|---:|---:|---:|---:|---:|
| Rotation-aware frontier-cell scorer | `0/4` | `0.0` | `0.03315001996589104` | `5.637647747993469` | `30` | `29` active |
| Path-aware free-viewpoint scorer | `0/4` | `0.0` | `0.0009902771347611306` | `6.065265536308289` | `13` | `24` active |
| Viewpoint scan phase | `0/4` | `0.0` | `0.02518699682786324` | `5.697803378105164` | `4` | `20` orient, `20` scan, `4` active turn |

Trace summary for the scan run:

| Trace field | Value |
|---|---:|
| Detector calls | `196` |
| Detector detections | `277` |
| Target-match detections | `4` |
| `orient_memory_anchor_from_active_viewpoint` | `20` |
| `scan_memory_anchor_from_active_viewpoint` | `20` |
| `turn_toward_memory_active_perception_frontier` | `4` |
| `fallback_occupancy_frontier` | `147` |
| `center_detector_target` | `1` |
| `approach_detector_target_after_center_loss` | `3` |

## Observations

- The scan phase fires and records the expected fields:
  `active_perception_phase`, `anchor_bearing_error_rad`, and
  `active_perception_scan_steps_remaining`.
- It recovers from the path-aware viewpoint smoke's severe SoftSPL regression,
  but does not beat the simpler rotation-aware frontier-cell scorer.
- Target-match calls dropped to `4`, which is worse than both the
  rotation-aware run (`30`) and the path-aware viewpoint run (`13`).
- The policy spends many steps orienting/scanning around the only episode with
  a matching memory anchor, while the other three episodes still fall back due
  `no_matching_memory`.

## Result

The scan phase is a useful diagnostic and makes the active-perception option
more explicit, but it is not the right final algorithm. The evidence points
away from more hand-authored scan rules and toward learned view-value or
detector-recall prediction plus better memory-prior coverage.

## Follow-up

- Preserve the trace fields for analysis, but do not scale this policy as a
  benchmark candidate.
- Mine detector traces into a view-recall dataset: pose relative to memory
  anchor, selected viewpoint, scan action, and target-match outcome.
- Use that dataset to learn an expected evidence value or policy, then compare
  against the current hand-authored active-perception ablations with official
  metrics.
