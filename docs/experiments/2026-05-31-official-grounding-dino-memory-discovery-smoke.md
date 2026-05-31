# Experiment Report: Official Grounding-DINO Memory Discovery Smoke

Date: 2026-05-31
Owner: Codex
Status: Completed, diagnostic only

## Question

After switching the official detector-backed memory-discovery line from
YOLO-World to Grounding-DINO defaults, can the real Habitat run load DINO,
export a memory prior, and produce a query diagnostic through the existing
official evaluator?

## Hypothesis

Grounding-DINO should run with the previously qualified tiny model and avoid the
old YOLO default-weight trap. Because the current discovery loop only collects
opportunistic single-view detections during frontier exploration, anchor quality
may still be too weak for official query success.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, dirty research worktree |
| Machine | `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini` |
| Simulator / robot | Habitat-Lab / Habitat-Sim in conda env `habitat` |
| Detector | `grounding_dino`, `IDEA-Research/grounding-dino-tiny` |
| Key parameters | `max_episodes=4`, `max_steps=100`, `conf=0.25`, `text_threshold=0.25`, `max_image_side=384`, discovery policy `occupancy_frontier` |

## Command

Remote focused tests:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_comparison.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_grounding_dino_adapter.py -q
```

Discovery smoke:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_official_memory_discovery \
  --output runs/habitat_official_objectnav/grounding_dino_discovery_prior_4ep_100steps_20260531_v1 \
  --max-episodes 4 \
  --max-steps 100 \
  --grounding-dino-max-image-side 384 \
  --min-detection-confidence 0.25
```

Query diagnostic:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --output runs/habitat_official_objectnav/grounding_dino_memory_oracle_backend_4ep_100steps_20260531_v1 \
  --policy memory_active_perception_frontier_targetnav \
  --memory-prior-path runs/habitat_official_objectnav/grounding_dino_discovery_prior_4ep_100steps_20260531_v1/memory_prior.json \
  --targetnav-backend oracle_follower \
  --max-episodes 4 \
  --max-steps 100 \
  --pathfinder-suffix-goal-radius-m 0.05
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Remote focused tests | `62 passed` | CLI/default regression plus Grounding-DINO adapter tests |
| Discovery episodes | `4` | First `val_mini` episodes |
| Discovery observations | `400` | `100` steps per episode |
| Raw DINO detections | `590` | Before target-label filtering |
| Label-filtered detections | `589` | Most detections were non-target categories for the current episode |
| Exported anchors | `1` | Single `chair` anchor |
| Anchor confidence | `0.277648` | From episode `5`, step `0`, detection `2` |
| Anchor x/z error to oracle chair anchor | `5.648712 m` | DINO anchor `(-0.168527, 4.731492)`, oracle `(-4.403496, 0.993446)` |
| Query success rate | `0/4` | DINO prior with `oracle_follower` backend |
| Query SPL | `0.0` | Diagnostic-only run |
| Query SoftSPL | `0.0917306745160412` | Diagnostic-only run |
| Query mean distance-to-goal | `5.14483118057251` | Official Habitat measure |

Artifacts:

- `runs/habitat_official_objectnav/grounding_dino_discovery_prior_4ep_100steps_20260531_v1/memory_prior.json`
- `runs/habitat_official_objectnav/grounding_dino_discovery_prior_4ep_100steps_20260531_v1/detections.csv`
- `runs/habitat_official_objectnav/grounding_dino_discovery_prior_4ep_100steps_20260531_v1/summary.json`
- `runs/habitat_official_objectnav/grounding_dino_memory_oracle_backend_4ep_100steps_20260531_v1/summary.json`
- `runs/habitat_official_objectnav/grounding_dino_memory_oracle_backend_4ep_100steps_20260531_v1/policy_trace.json`

## Observations

- The official discovery CLI now defaults to `grounding_dino` and resolves
  omitted DINO weights to `IDEA-Research/grounding-dino-tiny`.
- Query, comparison, and candidate-label CLIs keep their existing detector
  defaults, but explicit `--detector grounding_dino` now resolves the correct
  model id when `--detector-weights` is omitted.
- The single DINO memory anchor was not close enough to the oracle target
  anchor to support query success, even with an oracle backend.
- The result is not an executor-only failure. The oracle backend reached the
  DINO anchor, but official distance-to-goal stayed large.

## Result

The DINO engineering path is now reproducible, and the old YOLO-default weight
trap is fixed across the official detector CLIs touched by the memory pipeline.
The first smoke is intentionally not a positive performance result: it shows
that single-view detector projection is not yet a paper-quality memory anchor.

## Follow-up

- Add multi-view DINO evidence fusion or candidate-viewpoint scoring before
  treating detector-discovered anchors as real memory.
- Add episode/category visibility diagnostics to discovery so target absence is
  separated from detector miss and projection error.
- Debug the vertical oracle chair failure before using oracle memory as a clean
  ceiling.
