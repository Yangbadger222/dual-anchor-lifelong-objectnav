# Experiment Report: Official View-Quality Memory Selection

Date: 2026-05-31
Owner: Codex
Status: Completed; negative diagnostic result

## Question

Does selecting robot-viewpoint memory anchors by target view quality, rather
than detector confidence alone, produce better non-privileged memory targets
for targetnav-equated ObjectNav recall?

## Hypothesis

Larger, more centered target detections should be better memory-write
viewpoints than the highest-confidence detections. This may improve anchor
quality, but it can still fail if the exploration policy never reaches useful
target-visible poses.

## Environment

| Item | Value |
|---|---|
| Machine | Linux workstation `badger@100.88.131.52` |
| Repo path | `/home/badger/Desktop/dual-anchor-lifelong-objectnav` |
| Python | `/home/badger/anaconda3/envs/habitat/bin/python` |
| Dataset | HM3D ObjectNav `val_mini` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Discovery policy | `occupancy_frontier` |
| Memory anchor mode | `robot_viewpoint` |
| Selection policy | `view_quality` |
| Episode / step cap | `4` episodes, `100` steps |

## Commands

Export view-quality robot-viewpoint memory:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_memory_discovery \
    --output runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_view_quality_prior_4ep_100steps_20260531_v1 \
    --max-episodes 4 \
    --max-steps 100 \
    --detector grounding_dino \
    --grounding-dino-max-image-side 384 \
    --min-detection-confidence 0.25 \
    --anchor-mode robot_viewpoint \
    --anchor-selection-policy view_quality \
    --max-anchors-per-episode 1
```

Anchor-quality diagnostics:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.report_habitat_official_memory_anchor_quality \
    --candidate-prior runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_view_quality_prior_4ep_100steps_20260531_v1/memory_prior.json \
    --reference-prior runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_trace_alias_4ep_32vp_20260531_v1/memory_prior.json \
    --output-dir runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_view_quality_quality_vs_viewpoint_4ep_20260531_v1

HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.report_habitat_official_memory_anchor_quality \
    --candidate-prior runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_view_quality_prior_4ep_100steps_20260531_v1/memory_prior.json \
    --reference-prior runs/habitat_official_objectnav/oracle_memory_prior_valmini_4ep_20260531_v1/memory_prior.json \
    --output-dir runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_view_quality_quality_vs_oracle_4ep_20260531_v1
```

Oracle-backend query:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_view_quality_oracle_backend_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav \
    --memory-prior-path runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_view_quality_prior_4ep_100steps_20260531_v1/memory_prior.json \
    --targetnav-backend oracle_follower \
    --max-episodes 4 \
    --max-steps 100 \
    --pathfinder-suffix-goal-radius-m 0.05
```

## Metrics

Discovery:

| Metric | Value |
|---|---:|
| Observations | 400 |
| Detector detections | 666 |
| Label-filtered detections | 620 |
| Exported anchors | 3 |
| Anchor-cap filtered candidates | 43 |
| Missing RGB | 0 |
| Projection failures | 0 |

Selected anchors:

| Episode | Category | Step | Confidence | Bbox Area | Center Offset | Anchor x/z |
|---|---|---:|---:|---:|---:|---|
| `5` | `chair` | 0 | 0.302422 | 0.0046875 | -0.0250000 | `0.0, -0.0` |
| `6` | `toilet` | 38 | 0.251333 | 0.0065137 | 0.0007813 | `0.0, -0.0` |
| `0` | `tv_monitor` | 21 | 0.522018 | 0.0465820 | 0.3945313 | `0.649519, 0.375` |

Anchor quality:

| Reference | Covered | Missing | Selected Mean Error | Nearest Mean Error | Good |
|---|---:|---:|---:|---:|---:|
| detector-positive viewpoints | 3/4 | 1 | 6.891912 m | 6.891912 m | 0 |
| oracle object anchors | 3/4 | 1 | 5.543938 m | 5.543938 m | 0 |

Official query:

| Metric | Value |
|---|---:|
| Success rate | 0/4 |
| SPL | 0.0 |
| SoftSPL | 0.0 |
| Mean DistanceToGoal | 6.0735965967178345 |
| Action count | 108 |

## Result

The view-quality selector is implemented and verified, but the four-episode
smoke is negative. It does not improve anchor quality or official recall. The
query is worse than the previous targetnav-equated no-memory row and also does
not improve over the earlier raw robot-viewpoint diagnostic.

## Interpretation

Ranking passive detections by bbox area and centering is not sufficient because
the exploration policy often detects from weak poses. Two selected anchors are
still at the episode origin with tiny target boxes, and the bed episode has no
selected memory anchor. This suggests the next publishable direction should be
an online memory-write option that actively approaches/scans before commit, or
a learned option-value label that scores memory writes by downstream detector
evidence and official progress.

## Verification

- RED tests failed before implementation on unsupported
  `anchor_selection_policy`.
- GREEN focused tests passed locally: `17 passed`.
- GREEN focused tests passed on Linux in conda env `habitat`: `17 passed`.
- Local and Linux `compileall` over touched discovery modules was clean.
- The remote discovery, anchor-quality, and oracle-backend query artifacts were
  generated successfully.

## Follow-up

- Keep `view_quality` as a transparent diagnostic baseline, not as the default
  paper method.
- Generate online option/write labels from actual detector approach rollouts.
- Train or derive a write policy that only commits memory after evidence of
  target approach, scan recovery, or official progress improves.
