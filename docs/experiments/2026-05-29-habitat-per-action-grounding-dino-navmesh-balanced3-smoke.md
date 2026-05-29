# Experiment Report: Habitat Per-Action Grounding-DINO Navmesh Balanced3 Smoke

Date: 2026-05-29  
Owner: Codex  
Status: Completed

## Question

Can the Habitat closed-loop runner execute the new `per_action` route
observation mode with Grounding-DINO and a target-agnostic navmesh frontier over
multiple categories, and what failure modes appear before scaling?

## Hypothesis

Memory-guided navigation should remain competitive with `frontier_only` when
the remembered object is still valid and detector evidence is positive. The run
should also reveal whether detector-positive route observations are clean enough
to trust for larger experiments.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` at `b6667d9` |
| Machine | Linux host `badger@100.88.131.52`, conda env `habitat` |
| Dataset | HM3D ObjectNav val, `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val` |
| Scene root | `datasets/habitat/scene_datasets/hm3d` |
| Simulator | Habitat-Sim via project CLI |
| Detector | `grounding_dino`, `IDEA-Research/grounding-dino-tiny` |
| Key parameters | `--max-groups 3`, `--target-categories chair,plant,toilet`, `--frontier-mode navmesh_frontier`, `--route-observation-mode per_action`, `--memory-reliability-mode evidence`, clean noise |

## Command

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_v1 \
  --target-categories chair,plant,toilet \
  --max-groups 3 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stable \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode evidence \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 5 \
  --frontier-probe-heading-count 4 \
  --route-observation-mode per_action \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --grounding-dino-max-image-side 384 \
  --rgb-noise-profile configs/noise/rgb_published_v1.yaml \
  --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml \
  --noise-level clean \
  --min-target-pixels 24 \
  --min-detector-pixels 20 \
  --max-detection-area-ratio 0.7 \
  --detector-prompt-mode target
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Selected groups | 3 | Chair, plant, toilet from HM3D scene `00800-TEEsavR23oF` |
| Success episodes, `memory_guided` | 3 / 3 | All selected memory routes verified positive |
| Success episodes, `frontier_only` | 3 / 3 | Navmesh frontier found positive evidence for all groups |
| Success episodes, `naive_count` | 3 / 3 | All selected memories were valid in this stable run |
| Total actions, `memory_guided` | 347 | Memory selected for all three groups |
| Total actions, `frontier_only` | 357 | 10 more actions than `memory_guided` |
| Total actions, `naive_count` | 347 | Tied `memory_guided` because stable memory was valid |
| Memory-guided hindsight regret | 0 | On this tiny run only |
| Frontier-only hindsight regret | 7 | Frontier was slightly longer than memory |
| Detector false confirmations | At least 1 memory row | Plant memory was detector-positive with `overlap_pixels=0` |

## Row Audit

| Category | Memory actions | Frontier actions | Memory evidence | Route observation | Notes |
|---|---:|---:|---|---|---|
| chair | 59 | 62 | detector-positive, overlap `18390`, precision `0.621809` | `goal_viewpoint:1:route:step:58` | Clean detector overlap |
| plant | 122 | 128 | detector-positive, overlap `0`, precision `0.0` | `goal_viewpoint:10:route:step:121` | Detector false confirmation audit case |
| toilet | 166 | 167 | detector-positive, overlap `5057`, precision `0.352699` | `goal_viewpoint:1:route:step:165` | Clean detector overlap |

The `plant` row is important: the detector mask was large enough to pass the
detector-positive gate (`detector_pixels=8150`), but it had no overlap with the
oracle target mask. This should not be used as a policy signal on a real robot,
but in simulation it must be counted as an audit failure rather than hidden by
aggregate action totals.

## Result

The run validates that the per-action route-observation path can execute with
Grounding-DINO across multiple categories and that the row-level route trace is
useful for diagnosing where evidence was accepted. It does not support a paper
claim yet: the action delta is small, `memory_guided` ties `naive_count`, and
one memory success is detector-positive without target overlap.

The immediate research value is diagnostic. Before scaling to benchmark-style
runs, detector false confirmations need explicit summary counts and reports
must separate detector-positive success from oracle-overlap-audited success.

## Follow-up

- Add audit-only `detector_false_confirmation` fields to row evidence payloads
  and per-policy summary counts.
- Rerun this balanced3 smoke after the audit fields are pushed so the
  false-confirmation count appears directly in `summary.json`.
- Increase category/scene coverage only after false confirmations are visible
  in summaries.
- Do not tune detector thresholds around this single `plant` row; treat it as
  evidence that the final algorithm needs detector calibration or multi-view
  confirmation.
