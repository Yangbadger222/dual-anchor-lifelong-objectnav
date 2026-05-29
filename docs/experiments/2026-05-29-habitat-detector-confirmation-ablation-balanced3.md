# Experiment Report: Habitat Detector Confirmation Ablation Balanced3

Date: 2026-05-29  
Owner: Codex  
Status: Completed

## Question

Does the new detector confirmation interface change Grounding-DINO per-action
closed-loop behavior in a way that reduces false confirmations without hiding
new failure modes?

## Hypothesis

`multiview` confirmation should reduce single-frame detector false
confirmations, but it may also make `frontier_only` and fallback routes more
conservative because they need repeated detector evidence before the shared gate
can stop.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` at `ddadcbd` |
| Machine | Linux host `badger@100.88.131.52`, conda env `habitat` |
| Dataset | HM3D ObjectNav val, `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val` |
| Scene root | `datasets/habitat/scene_datasets/hm3d` |
| Simulator | Habitat-Sim via project CLI |
| Detector | `grounding_dino`, `IDEA-Research/grounding-dino-tiny` |
| Key parameters | `--target-categories chair,plant,toilet`, `--max-groups 3`, `--frontier-mode navmesh_frontier`, `--route-observation-mode per_action`, clean noise |

## Command

Successful `single_frame` run:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_single_frame_confirm_v1 \
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
  --detector-confirmation-mode single_frame
```

Successful `multiview` run used the same command and output
`runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_multiview_confirm_v1`,
with:

```bash
  --detector-confirmation-mode multiview \
  --detector-confirmation-frames 2 \
  --detector-confirmation-min-translation 0.05 \
  --detector-confirmation-min-rotation-deg 5.0 \
  --detector-confirmation-min-mask-iou 0.05
```

Two invalid command attempts happened before the successful multiview run:
one used a wrong depth-noise path, and one used an invalid PyTorch allocator
option. Both failed before producing a valid run and are not included in the
metrics.

## Metrics

| Metric | `single_frame` | `multiview` | Notes |
|---|---:|---:|---|
| Selected groups | 3 | 3 | Chair, plant, toilet |
| `memory_guided` success | 3 / 3 | 3 / 3 | Stable memory remains useful |
| `frontier_only` success | 3 / 3 | 1 / 3 | Multiview makes frontier stopping stricter |
| `naive_count` success | 3 / 3 | 3 / 3 | Stable valid memories reused |
| `memory_guided` actions | 347 | 354 | Multiview adds 7 actions |
| `frontier_only` actions | 357 | 1016 | Multiview fails plant/toilet frontier discovery |
| `naive_count` actions | 347 | 354 | Same memory routes as memory-guided |
| `memory_guided` false confirmations | `{'memory': 1}` | `{}` | Plant memory false confirmation is removed |
| `frontier_only` false confirmations | `{'memory': 1}` | `{}` | Memory audit is present in all rows |
| `naive_count` false confirmations | `{'memory': 1}` | `{}` | Same plant memory audit |
| `memory_guided` confirmation counts | `{}` | `{'confirmed': 7}` | Multiview row evidence has confirmed positives |
| `frontier_only` hindsight regret | 7 | 655 | Frontier becomes much less reliable under strict confirmation |

## Observations

- `single_frame` reproduces the earlier balanced3 result: memory-guided and
  naive-count tie at `347` actions, frontier-only uses `357` actions, and the
  `plant` memory row is a detector false confirmation.
- `multiview` removes the audited false confirmation. The `plant` memory row
  becomes `confirmed_detector_positive_mask` with semantic overlap in the audit
  payload.
- `multiview` is not simply better. It makes `frontier_only` fail for `plant`
  and `toilet`, increasing frontier-only actions from `357` to `1016` and
  hindsight action regret from `7` to `655`.
- The first successful multiview balanced3 run produced confirmed-positive
  counts but no suppressed-positive counts in the summaries. Suppression exists
  in unit coverage, but a targeted runtime case is still needed.

## Result

The detector confirmation interface is useful as an ablation and diagnostic
tool, not as a headline algorithm yet. It removes the observed detector false
confirmation in this small balanced3 smoke, but the same stricter evidence
requirement can make memoryless frontier exploration fail. This is the right
kind of pressure test: it exposes a real precision/recall tradeoff instead of
claiming a shallow action-count win.

The current publishable direction should be an adaptive or learned confirmation
and reliability model that uses multiview evidence when detector confidence is
ambiguous, while avoiding unnecessary strictness when frontier exploration is
already expensive.

## Follow-up

- Add a targeted weak-positive runtime case so suppressed-positive summary
  counts are exercised outside unit tests.
- Run the paired ablation across more scenes and categories before claiming a
  detector-backed gain.
- Use this report to motivate learned/adaptive detector reliability rather than
  a fixed global multiview gate.
