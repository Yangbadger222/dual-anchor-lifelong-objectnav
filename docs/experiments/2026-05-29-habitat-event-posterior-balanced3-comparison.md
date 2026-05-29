# Experiment Report: Habitat Event-Posterior Balanced3 Comparison

Date: 2026-05-29
Owner: Codex
Status: Completed

## Question

Does `event_posterior` change memory-vs-frontier decisions on the balanced3
Grounding-DINO per-action navmesh smoke compared with `evidence` mode?

## Hypothesis

`event_posterior` should lower memory reliability when memory-context
suppressed detector events are present. It may flip memory-guided decisions only
when memory and frontier expected costs are close; otherwise it should preserve
successful memory reuse while exposing lower confidence.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` at `d47c184` |
| Machine | Linux host `badger@100.88.131.52`, conda env `habitat` |
| Dataset | HM3D ObjectNav val, `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val` |
| Scene root | `datasets/habitat/scene_datasets/hm3d` |
| Simulator | Habitat-Sim via project CLI |
| Detector | `grounding_dino`, `IDEA-Research/grounding-dino-tiny` |
| Key parameters | `--target-categories chair,plant,toilet`, `--max-groups 3`, `--frontier-mode navmesh_frontier`, `--route-observation-mode per_action`, `--detector-confirmation-mode multiview`, clean noise |

## Command

Evidence baseline:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_evidence_events_v2 \
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
  --detector-prompt-mode target \
  --detector-confirmation-mode multiview \
  --detector-confirmation-frames 2 \
  --detector-confirmation-min-translation 0.05 \
  --detector-confirmation-min-rotation-deg 5.0 \
  --detector-confirmation-min-mask-iou 0.05
```

Event-posterior run used the same command with:

```bash
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_event_posterior_v1 \
  --memory-reliability-mode event_posterior
```

## Metrics

| Metric | `evidence` | `event_posterior` | Notes |
|---|---:|---:|---|
| Selected groups | 3 | 3 | Chair, plant, toilet |
| `memory_guided` success / actions | 3 / 3, `354` | 3 / 3, `354` | No policy flip |
| `frontier_only` success / actions | 1 / 3, `1016` | 1 / 3, `1016` | Same detector/frontier failures |
| `naive_count` success / actions | 3 / 3, `354` | 3 / 3, `354` | Same memory routes |
| `memory_guided` hindsight regret | `0` | `0` | Memory remains best in this slice |
| Runtime event counts per policy | `{'confirmed': 21, 'suppressed': 29}` | `{'confirmed': 21, 'suppressed': 29}` | Event surface stable across modes |
| Detector false confirmations | `{}` | `{}` | Multiview removes the earlier audited false confirmation |

Memory-guided row-level reliability:

| Category | `evidence` value / reason | `event_posterior` value / posterior | Decision change |
|---|---:|---:|---|
| `chair` | `0.96` / `strong_current_evidence_floor` | `0.683481` / `0.457238` | none |
| `plant` | `0.96` / `strong_current_evidence_floor` | `0.710654` / `0.506644` | none |
| `toilet` | `0.96` / `strong_current_evidence_floor` | `0.81947` / `0.70449` | none |

## Observations

- `event_posterior` moved all three memory reliability values below the
  strong-positive floor, proving the event stream affects policy-facing
  confidence.
- It did not change decisions because stable memory routes were still much
  cheaper than the failed or expensive frontier routes.
- The `chair` row had the lowest event posterior (`0.457238`) because
  suppressed event weight exceeded confirmed event weight, but its memory route
  remained shortest.
- This run reproduces the earlier multiview balanced3 action profile while now
  adding runtime event counts and event-posterior traces.

## Result

The balanced3 comparison is a calibration result, not a win/loss benchmark.
`event_posterior` changes the reliability signal in the intended direction, but
the stable balanced3 task is not decision-sensitive enough to test whether this
improves memory-vs-frontier selection. The next useful test should deliberately
include cost-close or stale/weak-evidence rows where lower detector-event
confidence can change the selected option.

## Follow-up

- Run stale or weak-evidence Grounding-DINO comparisons where `event_posterior`
  can plausibly flip memory-guided decisions.
- Report decision flips with bucket counts and hindsight regret, not just
  aggregate action totals.
- Treat this posterior as a calibration baseline for a learned reliability
  model, not the final algorithm.
