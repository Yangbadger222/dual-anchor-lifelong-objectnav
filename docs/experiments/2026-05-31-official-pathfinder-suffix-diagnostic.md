# Experiment Report: Official Pathfinder Suffix Diagnostic

Date: 2026-05-31
Owner: Codex
Status: Completed diagnostic; oracle-only

## Question

If memory-active-perception exploration produces a target detector match, can a
temporary Habitat pathfinder suffix convert that sighting into official ObjectNav
success?

## Hypothesis

The current `0/4` learned/hand-score online smokes may be limited by terminal
approach and STOP behavior. A pathfinder suffix should improve the matched
diagnostic if exploration plus memory has already reacquired a recoverable
target.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / uncommitted research changes |
| Machine | Linux mirror `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | Habitat ObjectNav HM3D `val_mini` |
| Policy | `memory_active_perception_frontier_pathfinder_suffix` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Memory prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |

## Commands

Local verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py
```

Linux radius-`1.0` smoke:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/pathfinder_suffix_active_perception_yolo_4ep_50steps_20260531_v1 \
    --policy memory_active_perception_frontier_pathfinder_suffix \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --pathfinder-suffix-goal-radius-m 1.0 \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313
```

Linux radius-`0.05` smoke:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/pathfinder_suffix_active_perception_yolo_4ep_100steps_radius005_20260531_v1 \
    --policy memory_active_perception_frontier_pathfinder_suffix \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --pathfinder-suffix-goal-radius-m 0.05 \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313
```

Linux backend-wired radius-`0.05` rerun:

```bash
ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/pathfinder_suffix_oracle_backend_yolo_4ep_100steps_radius005_20260531_v1 \
    --policy memory_active_perception_frontier_pathfinder_suffix \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --pathfinder-suffix-goal-radius-m 0.05 \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313'
```

## Metrics

| Run | Success | SPL | SoftSPL | Distance | Target-match calls | Suffix episodes |
|---|---:|---:|---:|---:|---:|---:|
| Fixed controller hand-score baseline | `0/4` | `0.0` | `0.02518699682786324` | not summarized here | `4` | `0` |
| Pathfinder suffix radius `1.0`, 50 steps | `0/4` | `0.0` | `0.226293450183814` | `4.17857064306736` | `1` | `1` |
| Pathfinder suffix radius `0.05`, 100 steps | `1/4` | `0.24261777449152924` | `0.24163039972246855` | `4.007396151311696` | `1` | `1` |
| Backend-wired suffix radius `0.05`, 100 steps | `1/4` | `0.24261777449152924` | `0.24163039972246855` | `4.007396151311696` | `1` | `1` |

Successful suffix episode in the radius-`0.05` run:

| Field | Value |
|---|---|
| Episode index / id | `2` / `0` |
| Category | `tv_monitor` |
| Suffix activation step | `4` |
| Final step | `47` |
| Final distance to goal | `0.061577994376420975` |
| Success / SPL / SoftSPL | `1.0` / `0.970471097966117` / `0.9625604903508297` |

## Observations

- The ObjectNav config uses `distance_to: VIEW_POINTS` and
  `success_distance: 0.1`, so the initial `1.0` m suffix radius was too loose
  for official success.
- Tightening the diagnostic suffix radius to `0.05` produced the first nonzero
  official success in this sequence.
- Only one of four episodes had a target detector match and suffix activation.
  The other three still fell back to occupancy frontier with no matching memory
  for their target category/scene.
- The successful run is not benchmark-valid: after target detection, the suffix
  uses Habitat episode goal/viewpoint positions.
- The backend-wired rerun reproduced the radius-`0.05` metrics and records the
  suffix backend explicitly in the successful episode trace:
  `backend_id=pathfinder_suffix_oracle`, `status=SUCCEEDED`,
  `reason=oracle_follower_stop`, `privileged_oracle=true`, and
  `benchmark_valid=false`.

## Result

The diagnostic supports the terminal-control-bottleneck hypothesis. At least one
episode can be solved by the existing exploration/memory/detector stack once an
oracle Habitat follower handles the final approach and STOP. The 2026-05-31
backend-wired rerun confirms this diagnostic now goes through the shared
`HabitatOracleFollowerBackend` boundary and exposes its privileged status in
the artifacts. This is useful failure decomposition, not a publishable policy
result.

## Follow-Up

- Replace the oracle suffix with detector-depth target projection plus a
  Habitat-compatible PointNav/VLFM-style local navigation suffix.
- Improve memory/source coverage so more than one of four episodes activates the
  suffix.
- Keep reporting this suffix separately from benchmark-valid policies.
