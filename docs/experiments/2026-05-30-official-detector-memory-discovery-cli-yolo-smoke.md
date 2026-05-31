# Experiment Report: Official Detector Memory Discovery CLI YOLO Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Can the official detector memory discovery CLI run a real YOLO-World detector
inside Habitat, write `episode_start_relative` priors, and feed those generated
priors into the official `memory_guided_frontier` policy?

## Hypothesis

The CLI should produce detector-backed memory-prior artifacts on at least one
episode where the target appears in the official RGB stream. The query policy
should select those priors on matching category/scene episodes, but this smoke
is not expected to be a benchmark win because the consumer policy is still a
simple nearest-anchor steering rule.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted working tree |
| Machine | Linux `100.88.131.52`, user `badger` |
| Conda env | `habitat` |
| Dataset | `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz` |
| Scene root | `datasets/habitat/scene_datasets/hm3d` |
| Detector | YOLO-World, `yolov8s-worldv2.pt`, confidence `0.25` |
| Policy | Discovery: `occupancy_frontier`; query: `memory_guided_frontier`; context: `occupancy_frontier` |

## Command

Dependency probe:

```bash
/home/badger/anaconda3/bin/conda run -n habitat python -c \
  "import importlib.util; print({name: bool(importlib.util.find_spec(name)) for name in ['habitat', 'ultralytics', 'transformers', 'torch']})"
```

Focused verification:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
    src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
    src/objectnav_core/tests/test_official_episode_memory.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
    src/objectnav_core/tests/test_ros_packaging.py -q
```

Discovery smoke:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_memory_discovery \
    --output runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1 \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --policy occupancy_frontier \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313 \
    --min-detection-confidence 0.25 \
    --max-anchors-per-episode 8
```

Generated-prior query:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_4ep_50steps_20260530_v1 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy memory_guided_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --memory-min-confidence 0.25 \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313
```

Same-budget no-memory context:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/occupancy_frontier_valmini_4ep_50steps_20260530_v1 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy occupancy_frontier \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Linux focused tests | 49 passed | Conda env `habitat` |
| Linux whitespace check | 0 failures | `git diff --check` clean |
| Discovery episodes | 4 | YOLO-World smoke |
| Discovery observations | 200 | 50 steps x 4 episodes |
| Detector outputs | 189 | Before category filtering |
| Label-filtered detections | 169 | Non-target labels |
| Projection failures | 0 | Valid depth for kept detections |
| Exported memory anchors | 8 | All `episode_start_relative` |
| Generated-prior query success | 0/4 | Official Habitat metric |
| Generated-prior query SPL | 0.0 | Official Habitat metric |
| Generated-prior query SoftSPL | 0.0009902771347611306 | Official Habitat metric |
| Same-budget occupancy success | 0/4 | Official Habitat metric |
| Same-budget occupancy SPL | 0.0 | Official Habitat metric |
| Same-budget occupancy SoftSPL | 0.03315005152623973 | Official Habitat metric |

## Observations

- The one-episode/20-step smoke ran but exported `0` anchors. A probe showed
  the first episode target was `chair`, while YOLO detected `bed` in the first
  frame.
- The four-episode smoke exported `8` `tv_monitor` anchors from episode index
  `2`, scene `00802-wcojb4TFT35`.
- The generated-prior query selected the YOLO memory in the matching
  `tv_monitor` episode with `decision=turn_toward_memory`, confidence
  `0.80616`, range `2.319314510754417`, and bearing error
  `-0.5186404837529035`.
- The generated memory changed behavior but did not improve official metrics.
  It reduced SoftSPL relative to same-budget `occupancy_frontier`.

## Result

The CLI and real-detector discovery path work as infrastructure: YOLO-World can
run inside the official Habitat loop, write actionable episode-relative memory
priors, and those priors can be consumed by `memory_guided_frontier`.

The policy result is negative. This should not be described as benchmark
progress. It shows that the current memory consumer is too brittle for paper
claims and needs a stronger memory-conditioned policy plus detector-confirmed
stopping.

## Follow-up

- Add detector-backed STOP confirmation to avoid coordinate-only stopping.
- Log all detector rows, including filtered labels and filter reasons.
- Deduplicate/fuse repeated anchors before query.
- Replace nearest-anchor steering with a memory-conditioned exploration score
  over the occupancy/frontier map.
