# Experiment Report: Official Confirmed Detector-Approach Memory Write

Date: 2026-05-31
Owner: Codex
Status: Completed; negative diagnostic result

## Question

During memory discovery, should the robot approach a target-category detection
before writing memory, and does a confirmed detector-approach write produce
better official ObjectNav recall than passive robot-viewpoint writes?

## Hypothesis

A target-reactive write policy should avoid storing the first weak target
glimpse. It may improve memory quality if the detector local controller can
center and approach the target; if it exports no confirmed anchors, the
bottleneck is local detector servo/confirmation rather than memory ranking.

## Environment

| Item | Value |
|---|---|
| Machine | Linux workstation `badger@100.88.131.52` |
| Repo path | `/home/badger/Desktop/dual-anchor-lifelong-objectnav` |
| Python | `/home/badger/anaconda3/envs/habitat/bin/python` |
| Dataset | HM3D ObjectNav `val_mini` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Discovery policy | `occupancy_frontier` until target detection |
| Memory anchor mode | `robot_viewpoint` |
| Selection policy | `view_quality` |
| Episode / step cap | `4` episodes, `100` steps |

## Commands

Strict confirmed approach:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_memory_discovery \
    --output runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_confirmed_detector_approach_prior_4ep_100steps_20260531_v1 \
    --max-episodes 4 \
    --max-steps 100 \
    --detector grounding_dino \
    --grounding-dino-max-image-side 384 \
    --min-detection-confidence 0.25 \
    --anchor-mode robot_viewpoint \
    --anchor-selection-policy view_quality \
    --anchor-commit-policy confirmed_detector_approach \
    --detector-approach-max-steps 8 \
    --max-anchors-per-episode 1
```

Non-strict long-budget approach comparison:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_memory_discovery \
    --output runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_detector_approach8_prior_4ep_100steps_20260531_v1 \
    --max-episodes 4 \
    --max-steps 100 \
    --detector grounding_dino \
    --grounding-dino-max-image-side 384 \
    --min-detection-confidence 0.25 \
    --anchor-mode robot_viewpoint \
    --anchor-selection-policy view_quality \
    --anchor-commit-policy detector_approach \
    --detector-approach-max-steps 8 \
    --max-anchors-per-episode 1
```

Anchor quality and query for the non-strict comparison:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.report_habitat_official_memory_anchor_quality \
    --candidate-prior runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_detector_approach8_prior_4ep_100steps_20260531_v1/memory_prior.json \
    --reference-prior runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_trace_alias_4ep_32vp_20260531_v1/memory_prior.json \
    --output-dir runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_detector_approach8_quality_vs_viewpoint_4ep_20260531_v1

HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.report_habitat_official_memory_anchor_quality \
    --candidate-prior runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_detector_approach8_prior_4ep_100steps_20260531_v1/memory_prior.json \
    --reference-prior runs/habitat_official_objectnav/oracle_memory_prior_valmini_4ep_20260531_v1/memory_prior.json \
    --output-dir runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_detector_approach8_quality_vs_oracle_4ep_20260531_v1

HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_detector_approach8_oracle_backend_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav \
    --memory-prior-path runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_detector_approach8_prior_4ep_100steps_20260531_v1/memory_prior.json \
    --targetnav-backend oracle_follower \
    --max-episodes 4 \
    --max-steps 100 \
    --pathfinder-suffix-goal-radius-m 0.05
```

## Metrics

Discovery:

| Policy | Detections | Label-filtered | Deferred approach actions | Confirmed | Unconfirmed | Exported anchors |
|---|---:|---:|---:|---:|---:|---:|
| `confirmed_detector_approach` | `633` | `433` | `46` | `0` | `60` | `0` |
| `detector_approach` budget `8` | `633` | `433` | `46` | `0` | `0` | `2` |

Non-strict selected anchors:

| Episode | Category | Step | Confidence | Bbox area | Center offset | Anchor x/z |
|---|---|---:|---:|---:|---:|---|
| `6` | `toilet` | `38` | `0.251333` | `0.006513671875` | `0.00078125` | `0.0, -0.0` |
| `0` | `tv_monitor` | `29` | `0.549318` | `0.019254557291666665` | `-0.04140625` | `0.033494, -0.125` |

Anchor quality for non-strict approach:

| Reference | Covered | Missing | Selected Mean Error | Nearest Mean Error | Good |
|---|---:|---:|---:|---:|---:|
| detector-positive viewpoints | `2/4` | `2` | `6.262038 m` | `6.262038 m` | `0` |
| oracle object anchors | `2/4` | `2` | `5.752019 m` | `5.752019 m` | `0` |

Official query for non-strict approach with `oracle_follower`:

| Metric | Value |
|---|---:|
| Success rate | `0/4` |
| SPL | `0.0` |
| SoftSPL | `0.003394134213343364` |
| Mean DistanceToGoal | `5.8624347448349` |
| Action count | `301` |

## Result

The target-reactive write policy is implemented and verified, but the
four-episode Grounding-DINO diagnostic is negative.

The strict confirmed policy attempted detector-guided approach after target
detections, but it produced no range-confirmed memory anchors. The non-strict
long-budget approach exported two anchors, yet both remained near the episode
origin and failed the targetnav-equated oracle-backend query.

## Interpretation

The exploration phase should approach detected targets; the current system now
has a policy boundary that enforces that idea. However, the present local
detector controller is too weak in Habitat discrete action space. It can spend
actions reacting to detections without producing a confirmed useful viewpoint.

This result is especially relevant for real robot transfer. A real robot with
SLAM/Nav2 and continuous control should make target tracking and local approach
more natural, but the algorithm must not rely on a permanently stable global
map. The publishable memory system should use SLAM for local control and
return-to-memory execution while storing confirmed visual/geometric evidence
that can survive long-term map drift.

## Verification

- RED tests failed before implementation on unsupported
  `confirmed_detector_approach`.
- Local focused tests passed:
  `20 passed` for memory discovery, discovery CLI, and ROS packaging.
- Local `compileall` over touched discovery modules/tests was clean.
- Remote focused tests in conda env `habitat` passed: `20 passed`.
- Remote `compileall` over touched discovery modules/tests was clean.
- Local `git diff --check` and touched-file trailing-whitespace scan were clean.

## Follow-Up

- Add an approach-attempt trace artifact so unconfirmed target reactions expose
  per-step bbox, depth, pose, and chosen action.
- Replace the current weak detector servo with a stronger target-tracking
  option: keep target lock, rotate/search when lost, and approach until view
  quality improves.
- Use real-robot SLAM/Nav2 as a local execution substrate later, but keep the
  memory representation independent of a long-lived global map.
