# Experiment Report: Habitat Detector Confirmation Event Probe

Date: 2026-05-29
Owner: Codex
Status: Completed

## Question

Does the runtime Habitat `summary.json` now expose suppressed detector
confirmation events, not only selected confirmed evidence?

## Hypothesis

The new `detector_confirmation_events` interface should count both confirmed
and suppressed Grounding-DINO positives during candidate, route, and navmesh
probe verification. These counts should appear in per-policy summaries and
remain diagnostic-only.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` at `16b3372` |
| Machine | Linux host `badger@100.88.131.52`, conda env `habitat` |
| Dataset | HM3D ObjectNav val, `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val` |
| Scene root | `datasets/habitat/scene_datasets/hm3d` |
| Simulator | Habitat-Sim via project CLI |
| Detector | `grounding_dino`, `IDEA-Research/grounding-dino-tiny` |
| Key parameters | `--target-categories plant,toilet`, `--max-groups 1`, `--frontier-mode navmesh_frontier`, `--route-observation-mode per_action`, `--detector-confirmation-mode multiview`, clean noise |

## Command

Successful artifact:

```text
runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_event_probe_1group_v1/summary.json
```

Equivalent run command reconstructed from the artifact configuration:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_event_probe_1group_v1 \
  --target-categories plant,toilet \
  --max-groups 1 \
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

The shell history did not retain the original invocation, so the command above
should be treated as the reproducible equivalent confirmed from `summary.json`.

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Selected groups | 1 | Selected category was `plant` |
| `memory_guided` success / actions | 1 / 1, `127` | Memory reused, zero hindsight action regret |
| `frontier_only` success / actions | 0 / 1, `354` | Navmesh frontier failed to confirm before budget exhaustion |
| `naive_count` success / actions | 1 / 1, `127` | Same memory route as `memory_guided` |
| Selected-evidence confirmation counts | `{'confirmed': 2}` | Same for all three policies |
| Runtime event counts per policy | `{'confirmed': 8, 'suppressed': 8}` | Confirms suppressed events reach summary output |
| Runtime event counts by context per policy | `memory={'confirmed': 4, 'suppressed': 5}`, `fallback={'confirmed': 3, 'suppressed': 2}`, `fallback_from_memory={'confirmed': 1, 'suppressed': 1}` | Same for all three policies because each row audits memory, fallback, and post-memory fallback evidence |
| Detector false confirmations | `{}` | No overlap-audited false confirmation in the selected row evidence |

## Observations

- The completed runtime artifact contains `detector_confirmation_event_counts`
  and `detector_confirmation_event_counts_by_context` in every policy summary.
- The row-level `detector_confirmation_events` list includes suppressed route
  positives that do not become selected evidence. One memory-route event had
  `detector_pixels=8150`, `detector_precision=0.0`, `oracle_recall=0.0`, and
  `outcome='suppressed'`.
- The selected memory and post-memory fallback evidence remained confirmed:
  memory confirmation used `pending_count=3`, `translation_m=0.519657`, and
  `mask_iou=0.139673`; post-memory fallback confirmation used
  `pending_count=2`, `rotation_deg=9.999999`, and `mask_iou=0.439372`.
- This run is intentionally tiny. The useful result is the diagnostic event
  surface, not the policy action comparison.

## Result

The event interface is now verified in a real Grounding-DINO Habitat runtime
artifact. Suppressed positives are no longer visible only in unit tests: the
per-policy summary reports both `confirmed` and `suppressed` event counts, and
row payloads preserve the raw event context needed for reliability calibration.

This supports the next research slice: use suppressed and confirmed event
features as training or calibration signal for adaptive detector reliability.
It does not justify claiming that fixed multiview confirmation is generally
better.

## Follow-up

- Build an adaptive or learned detector reliability model using runtime event
  features such as pending count, view change, mask consistency, detector
  precision proxies, and route context.
- Scale the event diagnostic to more categories and scenes before using it in
  any paper-facing detector claim.
- Keep reporting selected-evidence confirmation counts separately from runtime
  event counts so policy behavior and diagnostic coverage do not get conflated.
