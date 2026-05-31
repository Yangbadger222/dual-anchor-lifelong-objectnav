# Experiment Report: Official Detector-Positive Viewpoint Memory Prior

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Does the earlier Grounding-DINO detector-positive viewpoint anchor idea survive
when ported into the official Habitat memory-prior interface?

## Hypothesis

Using official target `view_points` as privileged candidate viewpoints and
requiring a Grounding-DINO positive should produce memory anchors that are much
more useful than the current opportunistic single-frame bbox-depth projection.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, dirty research worktree |
| Machine | Linux Habitat host `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini`, first 4 episodes |
| Simulator / robot | Habitat-Lab/Habitat-Sim in conda env `habitat` |
| Key parameters | Grounding-DINO tiny, image side `384`, confidence `0.25`, viewpoint caps `8` and `32`, oracle TargetNav query radius `0.05` |

## Command

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py \
  src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

python3 -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_detector_viewpoint_memory_prior.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_detector_viewpoint_memory_prior.py

git diff --check

rsync -avR \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_detector_viewpoint_memory_prior.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_detector_viewpoint_memory_prior.py \
  src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py \
  src/objectnav_core/tests/test_ros_packaging.py \
  src/objectnav_core/setup.py \
  docs/design/2026-05-31-official-detector-positive-viewpoint-memory-prior.md \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m pytest src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/envs/habitat/bin/python -m compileall -q src/objectnav_core/objectnav_core/evaluation/habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/objectnav_core/cli/export_habitat_official_detector_viewpoint_memory_prior.py'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior --output runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_prior_4ep_8vp_20260531_v1/memory_prior.json --max-episodes 4 --max-viewpoints-per-episode 8 --grounding-dino-max-image-side 384 --min-detection-confidence 0.25'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.run_habitat_official_objectnav_eval --output runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_prior_oracle_backend_4ep_100steps_20260531_v1 --policy memory_active_perception_frontier_targetnav --memory-prior-path runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_prior_4ep_8vp_20260531_v1/memory_prior.json --targetnav-backend oracle_follower --max-episodes 4 --max-steps 100 --pathfinder-suffix-goal-radius-m 0.05'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior --output runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_prior_4ep_32vp_20260531_v1/memory_prior.json --max-episodes 4 --max-viewpoints-per-episode 32 --grounding-dino-max-image-side 384 --min-detection-confidence 0.25'
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Local focused tests | `27 passed` | Detector-viewpoint, oracle-memory, DINO CLI, official eval CLI, packaging |
| Remote focused tests | `27 passed` | Same slice in conda env `habitat` |
| 8-viewpoint export anchors | `3/4` | 13 restored viewpoints, 9 detections, 4 label-filtered |
| 32-viewpoint export anchors | `3/4` | 37 restored viewpoints, 27 detections, 22 label-filtered |
| Query success rate | `0.75` | 8-viewpoint prior + oracle TargetNav backend |
| Query SPL | `0.5891520577351606` | Diagnostic only |
| Query SoftSPL | `0.615534292748382` | Diagnostic only |
| Query mean distance-to-goal | `1.6792370742186904` | tv-monitor miss dominates |
| Failures | `1` skipped episode | Episode `0`, category `tv_monitor`, reason `no_detector_positive_viewpoint` |
| Alias-trace export anchors | `4/4` | 6 restored viewpoints, 12 detections, no skipped episodes |
| Alias-trace query success rate | `1.0` | Privileged viewpoint prior + oracle TargetNav backend |
| Alias-trace query SPL | `0.8134277193790571` | Diagnostic only |
| Alias-trace query SoftSPL | `0.8060506098824843` | Diagnostic only |
| Opportunistic alias discovery anchors | `17` | 400 observations, 666 detections, 620 label-filtered |
| Opportunistic alias discovery query SR | `0/4` | Projected anchors still poor despite more detections |

## Observations

- Detector-positive viewpoint anchors are much better than the first official
  opportunistic DINO discovery prior, which produced one poor chair anchor and
  `0/4` oracle-backend success.
- The diagnostic now succeeds on chair, toilet, and bed because the remembered
  anchor is a target-visible navigable viewpoint rather than a projected object
  center.
- Grounding-DINO still missed `tv_monitor` even after scanning up to 32 official
  target viewpoints, so the remaining failure is detector/category evidence,
  not the memory-coordinate transform.
- A follow-up per-viewpoint trace showed the `tv_monitor` miss was specifically
  a category prompt/alias issue: the detector produced `plant` and `bed` labels
  but no target match when prompted with the raw `tv_monitor` category.
- After adding ObjectNav category aliases to the Grounding-DINO adapter,
  `tv_monitor` was detected at viewpoint `0` with confidence `0.553856`; the
  privileged viewpoint prior exported `4/4` anchors and reached `4/4` official
  success with the oracle backend.
- The same alias fix improved opportunistic discovery coverage from `1` anchor
  to `17` anchors, but the projected-anchor prior still produced `0/4` with
  the oracle backend. More detections alone do not fix memory localization.
- The query uses an oracle TargetNav backend and the exporter uses privileged
  Habitat target viewpoints. These numbers are invalid as benchmark claims.

## Result

The old `detector_positive` idea does transfer into the official memory-prior
interface as a diagnostic. It upgrades the official DINO memory line from
`0/4` with opportunistic projected anchors to `4/4` when detector-positive
viewpoint anchors are supplied and ObjectNav detector aliases are handled. The
next paper-relevant task is to replace the privileged viewpoint source with a
non-oracle online viewpoint proposer and a learned/multi-view anchor generator;
the single-frame bbox-depth projection remains the bottleneck.

## Follow-up

- Build a non-privileged candidate-viewpoint proposer that can approximate
  target-visible viewpoints from exploration observations.
- Replace single-frame bbox-depth anchors with detector-positive viewpoint or
  multi-view memory anchors.
- Keep this exporter as an ablation/upper-bound bridge, not as a benchmark
  result.
