# Experiment Report: Lifecycle Memory Prior Export Frame Guard

Date: 2026-05-30
Owner: Codex
Status: Completed bridge/guard smoke, not a benchmark result

## Question

Can an existing lifecycle SQLite memory DB be exported into the official
memory-prior JSON format while preserving the fact that those anchors are in
Habitat world coordinates, and does the official policy refuse to act on them
by default?

## Hypothesis

The exporter should write all lifecycle anchors with
`coordinate_frame="habitat_world"`. The official selector should match the
scene/category only when `habitat_world` is explicitly allowed for inspection,
and the runtime `memory_guided_frontier` policy should otherwise fall back to
`occupancy_frontier`.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` at `0f14893` plus uncommitted official-eval/exporter slice |
| Machine | `badger-linux` |
| Conda env | `habitat` |
| Habitat-Lab | `0.3.3` |
| Source DB | `runs/habitat_usability/habitat_memory_lifecycle_val_grounding_dino_detector_anchor_matrix_v1/lifecycle_memory.sqlite` |
| Export artifact | `runs/habitat_official_objectnav/lifecycle_memory_prior_export_grounding_dino_detector_anchor_matrix_20260530_v1/official_memory_prior.json` |
| Guard smoke artifact | `runs/habitat_official_objectnav/memory_guided_frontier_world_prior_guard_1ep_20260530_v1` |

## Command

Export:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_lifecycle_memory_prior \
    --memory-db runs/habitat_usability/habitat_memory_lifecycle_val_grounding_dino_detector_anchor_matrix_v1/lifecycle_memory.sqlite \
    --output runs/habitat_official_objectnav/lifecycle_memory_prior_export_grounding_dino_detector_anchor_matrix_20260530_v1/official_memory_prior.json \
    --source-tag lifecycle_grounding_dino_detector_anchor_matrix \
    --min-confidence 0.5 \
    --dataset-version objectnav_hm3d_v1/val_mini
```

Runtime guard smoke:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/memory_guided_frontier_world_prior_guard_1ep_20260530_v1 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy memory_guided_frontier \
    --memory-prior-path runs/habitat_official_objectnav/lifecycle_memory_prior_export_grounding_dino_detector_anchor_matrix_20260530_v1/official_memory_prior.json \
    --memory-stop-radius-m 0.35 \
    --memory-bearing-tolerance-deg 20 \
    --memory-min-confidence 0.5 \
    --max-episodes 1 \
    --max-steps 20 \
    --validate-habitat
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Exported anchors | `12` | From detector-anchor lifecycle DB. |
| Filtered anchors | `0` | `min_confidence=0.5`; all anchors had confidence `0.903168`. |
| Coordinate frames | `12 habitat_world` | No anchor was marked episode-relative. |
| Guard-smoke success rate | `0.0` | Official Habitat metric. |
| Guard-smoke SPL | `0.0` | Official Habitat metric. |
| Guard-smoke SoftSPL | `0.003961108539044522` | Official Habitat metric. |
| Guard-smoke distance to goal | `8.379293441772461` | Official Habitat metric. |

## Observations

- Exported categories were balanced across six target categories:
  `bed`, `chair`, `plant`, `sofa`, `toilet`, and `tv_monitor`, with two anchors
  each.
- Exported scenes used compact lifecycle paths such as
  `hm3d/val/00802-wcojb4TFT35/wcojb4TFT35.basis.glb`, which match full Habitat
  episode scene paths through the official selector's scene-key compatibility
  logic.
- A direct selector probe returned `None` with default allowed frames, but
  returned `lifecycle_grounding_dino_detector_anchor_matrix:goal_object:445`
  when `allowed_coordinate_frames=("habitat_world",)` was explicitly provided.
- The official guard smoke loaded the prior, recorded `candidate_count=12`, and
  emitted `fallback_reason=no_matching_memory` because no
  `episode_start_relative` memory was available.

## Result

The exporter now produces an auditable real lifecycle-memory bridge artifact
without creating a fake official memory signal. The official runtime can load
the JSON, but the policy does not act on these world-frame anchors.

This result is not a memory-policy performance claim. It establishes that the
next benchmark-facing step must implement a valid world-to-episode transform or
an episode-relative discovery/memory logging pipeline before using lifecycle
anchors as official action priors.

## Follow-up

- Design and test a fair coordinate bridge from lifecycle Habitat world
  anchors to official episode-start-relative anchors.
- Alternatively, build the memory discovery artifact directly from official
  `gps`, `compass`, and detector observations so no transform is needed.
- Only after that bridge exists, rerun `memory_guided_frontier` against
  `occupancy_frontier` as a non-oracle official comparison.
