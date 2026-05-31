# Experiment Report: Official Memory Anchor Quality Diagnostic

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Can an offline prior-quality report explain why the non-privileged
Grounding-DINO discovery prior remains `0/4` even after category aliasing?

## Hypothesis

The opportunistic projected-anchor prior fails because its anchor geometry is
poor, not because the detector-positive viewpoint diagnostic is using a
different query backend.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, dirty research worktree |
| Machine | Local Mac for tests; Linux Habitat host `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini`, first 4 episodes |
| Simulator / robot | Habitat-Lab/Habitat-Sim in conda env `habitat` |
| Key parameters | Grounding-DINO tiny, image side `384`, max episodes `4`, max steps `100`, max good anchor error `1.0 m` |

## Command

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py \
  src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py \
  src/objectnav_core/tests/test_grounding_dino_adapter.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

python3 -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/official_episode_memory.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_discovery.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_anchor_quality.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_discovery.py \
  src/objectnav_core/objectnav_core/cli/report_habitat_official_memory_anchor_quality.py

git diff --check

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py src/objectnav_core/tests/test_ros_packaging.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.run_habitat_official_memory_discovery --output runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_episode_ids_4ep_100steps_20260531_v1 --max-episodes 4 --max-steps 100 --detector grounding_dino --grounding-dino-max-image-side 384 --min-detection-confidence 0.25'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.run_habitat_official_memory_discovery --output runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_prior_4ep_100steps_20260531_v1 --max-episodes 4 --max-steps 100 --detector grounding_dino --grounding-dino-max-image-side 384 --min-detection-confidence 0.25 --anchor-mode robot_viewpoint'
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Local focused tests | `36 passed` | Discovery, CLI, quality report, DINO adapter, detector-viewpoint, packaging |
| Remote focused tests | `25 passed` | Same core slice in conda env `habitat` |
| Fixed projected prior anchors | `17` | Now includes structured episode ids |
| Fixed projected vs viewpoint nearest mean error | `5.050678 m` | `0/4` good under `1.0 m` |
| Fixed projected vs viewpoint selected mean error | `5.197824 m` | `0/4` good under `1.0 m` |
| Fixed projected vs oracle nearest mean error | `5.657046 m` | `1/4` good under `1.0 m` |
| Robot-viewpoint prior anchors | `17` | Same detections, anchor mode stores robot pose |
| Robot-viewpoint vs viewpoint nearest mean error | `6.378549 m` | `0/4` good under `1.0 m` |
| Robot-viewpoint vs oracle nearest mean error | `5.049185 m` | `0/4` good under `1.0 m` |
| Robot-viewpoint oracle-backend query SR | `0/4` | No local servo/reacquisition yet |

## Observations

- The legacy alias discovery prior omitted structured `episode_id` fields; the
  source string had episode ids, but the memory selector treated the anchors as
  wildcard episode candidates.
- After fixing discovery export, the same projected prior has exact episode
  matches, but the anchor-quality errors are unchanged.
- Projected anchors are still meters away from useful detector-positive
  viewpoints.
- Storing the raw robot pose at first detector-positive observation is also not
  enough. Many selected robot-viewpoint anchors are near the start pose because
  the current exploration policy often detects while rotating rather than after
  approaching a useful viewpoint.
- The user-proposed direction is still the right representation: store a
  navigable robot/viewpoint pose, but commit the memory after detector-guided
  approach or visual confirmation, not at the first raw detection.

## Result

The report confirms the current bottleneck is memory anchor generation. The
best next method is a detector-confirmed approach/servo stage that moves from
the first detection to a better viewing pose, then stores that reached robot
pose as the memory anchor. Single-frame projected object centers and raw
first-detection robot poses are both insufficient.

## Follow-up

- Add a discovery-time detector-guided approach phase before committing
  `robot_viewpoint` anchors.
- Preserve bbox/depth evidence as metadata for local servoing and future SLAM
  alignment.
- Add a later Habitat-backed quality report for navigability, visibility, and
  floor correctness.
