# Experiment Report: Habitat Event-Posterior Stale Balanced3 Comparison

Date: 2026-05-29
Owner: Codex
Status: Completed

## Question

Does `event_posterior` change memory-guided stale repair behavior on a
Grounding-DINO per-action navmesh `stale_proxy` balanced3 run?

## Hypothesis

Stale rows should remain dominated by matching state: `no_current_observation`
should not become trusted just because detector events are present. Repaired
repeat rows may receive lower confidence than `evidence` mode, and may flip if
frontier-first is close in expected cost.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` at `e11df30` |
| Machine | Linux host `badger@100.88.131.52`, conda env `habitat` |
| Dataset | HM3D ObjectNav val, `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val` |
| Scene root | `datasets/habitat/scene_datasets/hm3d` |
| Simulator | Habitat-Sim via project CLI |
| Detector | `grounding_dino`, `IDEA-Research/grounding-dino-tiny` |
| Key parameters | `--target-categories chair,plant,toilet`, `--max-groups 3`, `--challenge stale_proxy`, `--query-repeats 2`, `--frontier-mode navmesh_frontier`, `--route-observation-mode per_action`, `--detector-confirmation-mode multiview`, clean noise |

## Command

Evidence baseline:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_stale_evidence_v1 \
  --target-categories chair,plant,toilet \
  --max-groups 3 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stale_proxy \
  --query-repeats 2 \
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
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_stale_event_posterior_v1 \
  --memory-reliability-mode event_posterior
```

## Metrics

| Metric | `evidence` | `event_posterior` | Notes |
|---|---:|---:|---|
| Selected groups / rows | 3 / 6 | 3 / 6 | Chair, plant, toilet, two repeats |
| `memory_guided` success / actions | 6 / 6, `766` | 6 / 6, `766` | No policy flip |
| `frontier_only` success / actions | 2 / 6, `1858` | 2 / 6, `1858` | Same frontier failures |
| `naive_count` success / actions | 6 / 6, `782` | 6 / 6, `782` | Naive remains slightly worse |
| `memory_guided` hindsight regret | `0` | `0` | Repair behavior remains optimal in this slice |
| Runtime event counts per policy | `{'confirmed': 36, 'suppressed': 24}` | `{'confirmed': 36, 'suppressed': 24}` | Event surface stable across modes |
| Detector false confirmations | `{}` | `{}` | Multiview confirmation avoids audited false positives |

Memory-guided repeat behavior:

| Category / repeat | `evidence` reliability | `event_posterior` reliability / posterior | Decision change |
|---|---:|---:|---|
| `chair` / 0 | `0.225` | `0.225` / `0.400751` | none, matching-limited frontier |
| `chair` / 1 | `0.96` | `0.730507` / `0.54274` | none, frontier remains shorter |
| `plant` / 0 | `0.225` | `0.225` / `0.761268` | none, matching-limited stale repair |
| `plant` / 1 | `0.96` | `0.734908` / `0.550742` | none, repaired memory reused |
| `toilet` / 0 | `0.225` | `0.225` / `0.761824` | none, matching-limited stale repair |
| `toilet` / 1 | `0.96` | `0.734741` / `0.550438` | none, repaired memory reused |

## Observations

- The matching gate correctly dominates stale repeat-0 rows. Even when
  detector-event posterior is high for `plant` and `toilet`, the reliability
  value remains `0.225` because the memory has `no_current_observation`.
- Repaired repeat-1 rows are confidence-calibrated downward from `0.96` to
  about `0.73`, but action decisions do not change because memory repair is
  still cheaper than frontier failure.
- `chair` is the closest decision-sensitive hint: repeat 1 has
  `event_posterior=0.54274` and still chooses frontier because frontier is
  shorter, matching the `evidence` decision.
- This is a useful negative result. The current stale balanced3 slice validates
  the safety gates, but it does not stress the posterior enough to prove policy
  advantage.

## Result

`event_posterior` is stable under stale repair and does not accidentally trust
stale memories with no current observation. It lowers repaired-memory confidence
without changing outcomes in this balanced3 stale slice. The next experiment
should create a truly decision-sensitive weak-evidence case, rather than simply
scaling this same stable/stale setup.

## Follow-up

- Build or select a weak-evidence row where memory-first and frontier-first
  expected costs are close and detector events are mixed.
- Evaluate whether `event_posterior` reduces hindsight regret on that row.
- Use the row traces as supervision targets for a learned reliability model.
