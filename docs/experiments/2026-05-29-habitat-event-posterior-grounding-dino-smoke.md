# Experiment Report: Habitat Event-Posterior Grounding-DINO Smoke

Date: 2026-05-29
Owner: Codex
Status: Completed

## Question

Does `--memory-reliability-mode event_posterior` run end-to-end in the
Grounding-DINO per-action Habitat smoke, and does the runtime row record the
posterior components needed for later calibration?

## Hypothesis

On the previously verified 1-group `plant` smoke, `event_posterior` should keep
the run executable while lowering the memory-valid estimate relative to
`evidence` mode when confirmed and suppressed memory-context detector events
are both present.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` at `1419a5e` |
| Machine | Linux host `badger@100.88.131.52`, conda env `habitat` |
| Dataset | HM3D ObjectNav val, `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val` |
| Scene root | `datasets/habitat/scene_datasets/hm3d` |
| Simulator | Habitat-Sim via project CLI |
| Detector | `grounding_dino`, `IDEA-Research/grounding-dino-tiny` |
| Key parameters | `--target-categories plant,toilet`, `--max-groups 1`, `--frontier-mode navmesh_frontier`, `--route-observation-mode per_action`, `--detector-confirmation-mode multiview`, `--memory-reliability-mode event_posterior`, clean noise |

## Command

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_event_posterior_1group_v1 \
  --target-categories plant,toilet \
  --max-groups 1 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stable \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode event_posterior \
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

Comparison baseline from the earlier event-interface smoke:

```text
runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_event_probe_1group_v1
```

## Metrics

| Metric | `evidence` baseline | `event_posterior` | Notes |
|---|---:|---:|---|
| Selected groups | 1 | 1 | Selected category was `plant` |
| `memory_guided` success / actions | 1 / 1, `127` | 1 / 1, `127` | Same option chosen in this tiny case |
| `frontier_only` success / actions | 0 / 1, `354` | 0 / 1, `354` | Frontier still fails before budget exhaustion |
| `naive_count` success / actions | 1 / 1, `127` | 1 / 1, `127` | Naive reuse unchanged |
| `memory_guided` reliability value | `0.96` | `0.710654` | Event posterior lowers confidence below the strong-positive floor |
| `memory_guided` reliability reason | `strong_current_evidence_floor` | `event_posterior_weighted` | Confirms new mode controls the row estimate |
| Memory-context event posterior | n/a | `0.506644` | Confirmed and suppressed weights are similar |
| Memory-context event weights | n/a | confirmed `7.423337`, suppressed `7.215538` | Uses detector-event fields, not oracle overlap |
| Runtime event counts per policy | `{'confirmed': 8, 'suppressed': 8}` | `{'confirmed': 8, 'suppressed': 8}` | Diagnostic event interface unchanged |

## Observations

- The run completed with `memory_reliability_mode=event_posterior`,
  `detector=grounding_dino`, and `detector_confirmation_mode=multiview`.
- Every policy row retained the runtime event counts:
  `detector_confirmation_event_counts={'confirmed': 8, 'suppressed': 8}`.
- `memory_guided` still selected memory for this 1-group case because even the
  lowered reliability estimate made memory-first cheaper than frontier-first.
- The important result is the row trace: `memory_reliability.components`
  includes `detector_event_count=9`, confirmed/suppressed weights, and
  `detector_event_posterior=0.506644`.

## Result

`event_posterior` is now verified beyond unit tests in a real
Grounding-DINO/Habitat runtime artifact. It does not change the action outcome
in this 1-group smoke, but it does change the policy-facing reliability value
in the intended direction when detector events are mixed.

This is an interface and calibration smoke, not a benchmark result. The next
useful experiment is a paired balanced3 or balanced6 comparison where the
lowered reliability can actually affect memory-vs-frontier decisions.

## Follow-up

- Run paired `evidence` versus `event_posterior` Grounding-DINO smokes on
  balanced3 and balanced6.
- Inspect rows where `event_posterior` flips decisions; report bucket changes
  and hindsight regret, not only aggregate action count.
- Use these traces as seed data for learned reliability calibration.
