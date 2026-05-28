# Experiment Report: Gate-Rejection Debug PNGs For Plant And TV Monitor

Date: 2026-05-28  
Owner: Codex  
Status: Completed diagnostic export; manual visual review still required

## Question

For the rejected `plant` and `tv_monitor` raw-`TRUST` rows in the
Grounding-DINO replay matrix, are the failures mainly caused by Grounding-DINO
boxing the wrong visible region, or by Habitat semantic ground-truth masks being
small, clipped, or stricter than human visual judgment?

## Hypothesis

The two categories likely have different failure modes:

- `tv_monitor` should mostly show detector false positives when the Habitat GT
  target is not currently visible, because the previous trace had many
  `target_not_currently_visible` gate rejections.
- `plant` should mix detector false positives with edge/clipping or strict-GT
  cases, because visible plant GT rows were sparse and often near image edges.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `97754ab` |
| Machine | `badger-linux`, via `ssh badger@100.88.131.52` |
| Dataset | HM3D ObjectNav `val_mini` |
| Simulator | Habitat-Sim / Habitat-Lab in conda env `habitat` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Detector cap | `grounding_dino_max_image_side=384` |
| Habitat render resolution | `1280x720` |
| Noise levels | `clean,mild,heavy` |
| Memory modes | `on,naive_count` |
| Categories | `plant,tv_monitor` |
| Episodes per category | `2` |
| Seed | `313` |
| Output | `runs/habitat_usability/gate_rejection_debug_plant_tv_monitor_grounding_dino_1280x720_epc2_cap384` |

## Command

Preflight:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --output runs/habitat_usability/gate_rejection_debug_plant_tv_monitor_preflight --noise-levels clean,mild,heavy --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --memory-ablation on,naive_count --episodes-per-category 2 --target-categories plant,tv_monitor --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --debug-export-gate-rejections --debug-export-categories plant,tv_monitor --debug-export-limit-per-category 256 --preflight-only'
```

Main diagnostic replay:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/gate_rejection_debug_plant_tv_monitor_grounding_dino_1280x720_epc2_cap384 --noise-levels clean,mild,heavy --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --memory-ablation on,naive_count --episodes-per-category 2 --target-categories plant,tv_monitor --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --debug-export-gate-rejections --debug-export-categories plant,tv_monitor --debug-export-limit-per-category 256 --seed 313'
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Replay runs completed | `24` | 2 categories x 2 episodes x 3 noise levels x 2 memory modes |
| Trace rows | `360` | 15 rows per replay |
| Raw trust rows | `198` | Before the shared current-positive gate |
| Gated trust / success rows | `21` | After the shared gate |
| Gate rejections exported | `177` | All exported as PNG; no skipped rows |
| `plant` PNGs | `23` | `21` memory-on, `2` naive-count |
| `tv_monitor` PNGs | `154` | `82` memory-on, `72` naive-count |
| `target_not_currently_visible` rejections | `169` | Main rejection reason |
| `missing_current_positive_evidence` rejections | `8` | Target visible or detected, but gate rejects reset/unknown rows |
| Mean detector precision | `0.036006` | Low because many detector masks cover non-GT area in rejected rows |
| Mean oracle recall | `0.133645` | Low for the same rejected-row diagnostic subset |

## Rejection Breakdown

| Category | Total PNGs | `target_not_currently_visible` | `missing_current_positive_evidence` |
|---|---:|---:|---:|
| `plant` | `23` | `20` | `3` |
| `tv_monitor` | `154` | `149` | `5` |

| Category | Memory | PNGs | Notes |
|---|---|---:|---|
| `plant` | `on` | `21` | Most rejections are memory-on raw trust after target leaves view |
| `plant` | `naive_count` | `2` | Only a small number of naive false-trust rows |
| `tv_monitor` | `on` | `82` | Persistent memory trust plus sparse current GT visibility |
| `tv_monitor` | `naive_count` | `72` | Positive-only accumulation still trusts after broad DINO false positives |

Noise distribution:

| Category | Clean | Mild | Heavy |
|---|---:|---:|---:|
| `plant` | `4` | `16` | `3` |
| `tv_monitor` | `50` | `52` | `52` |

## Representative PNGs

Remote artifact directory:

```text
runs/habitat_usability/gate_rejection_debug_plant_tv_monitor_grounding_dino_1280x720_epc2_cap384/debug_gate_rejections/
```

Local sample copies for quick review:

```text
/tmp/dual_anchor_gate_debug_samples/contact_sheet.png
/tmp/dual_anchor_gate_debug_samples/000_tv_monitor_on_clean_ep2_step3_target_not_currently_visible.png
/tmp/dual_anchor_gate_debug_samples/024_tv_monitor_on_mild_ep2_step0_missing_current_positive_evidence.png
/tmp/dual_anchor_gate_debug_samples/001_plant_on_mild_ep0_step0_missing_current_positive_evidence.png
/tmp/dual_anchor_gate_debug_samples/000_plant_naive_count_clean_ep0_step12_target_not_currently_visible.png
```

Representative trace rows:

| PNG | Key metrics | Diagnostic meaning |
|---|---|---|
| `000_tv_monitor_on_clean_ep2_step3_target_not_currently_visible.png` | oracle `0`, detector `921600`, overlap `0`, precision `0.0`, max conf `0.420464` | DINO produced image-wide TV-monitor detections while Habitat says no target is visible. This is detector false-positive behavior, not strict GT. |
| `024_tv_monitor_on_mild_ep2_step0_missing_current_positive_evidence.png` | oracle `58842`, detector `56615`, overlap `53881`, precision `0.951709`, recall `0.915689`, GT bbox touches top edge | The visual detector/GT alignment is good, but the row is `reset`, so the evidence classifier marks it `unknown`. This is a gate/evidence-protocol artifact rather than a detector failure. |
| `001_plant_on_mild_ep0_step0_missing_current_positive_evidence.png` | oracle `4314`, detector `23744`, overlap `4314`, precision `0.181688`, recall `1.0`, GT bbox touches bottom edge | DINO covers the plant but the bbox is much larger than the GT mask. This supports the strict/clipped-GT-or-coarse-box explanation. |
| `000_plant_naive_count_clean_ep0_step12_target_not_currently_visible.png` | oracle `0`, detector `434880`, overlap `0`, precision `0.0`, max conf `0.28838` | DINO produced a large plant false positive after the oracle target left view. This is detector false-positive behavior. |

## Observations

- `tv_monitor` is dominated by detector false positives in out-of-view frames:
  `149/154` exported TV-monitor rows are `target_not_currently_visible`, and
  representative rows show detector masks covering most or all of the image
  while Habitat GT has zero target pixels.
- Manual inspection of the local contact sheet confirms this qualitative
  pattern: a representative TV-monitor rejection frames a fireplace / wall
  region as `tv_monitor` with no green GT mask present.
- Some `tv_monitor` rows with visible GT show high detector/GT agreement, but
  reset rows are currently classified as `unknown`, causing
  `missing_current_positive_evidence`. Those rows are not detector misses.
- `plant` has a mixed failure mode. Some rows are large detector false
  positives with zero GT visibility; other rows show the detector covering the
  object while Habitat GT is edge-clipped or much smaller than the detector box.
- Manual inspection of the representative plant row shows the detector box
  spans the visible plant at the bottom of the image while the Habitat GT mask
  is a much smaller bottom-edge region.
- The debug export itself does not change experiment metrics. It only adds
  `debug_png` paths to trace rows and writes the visual artifacts.

## Result

The diagnostic export confirms that `tv_monitor` rejections are mostly a real
Grounding-DINO false-positive / over-broad-box problem under the current
box-mask detector interface. Habitat GT strictness explains only a minority of
TV-monitor debug cases.

For `plant`, both mechanisms appear. The severe out-of-view false positives are
DINO-driven, but visible edge cases show Habitat GT masks that are small or
bottom-clipped relative to the detector box. Plant should therefore be treated
as a mixed detector-plus-GT-strictness risk, not as a pure detector failure.

The immediate algorithmic conclusion is unchanged: keep the shared current-view
gate. Without it, both memory `on` and `naive_count` would count many stale or
false-positive raw-trust rows as success.

## Detector Area Filter Follow-Up

After this diagnostic export, the runner added a detector-side area sanity
filter in commits `a146bf2` and `345429e`. The filter uses only detector
geometry and image size, not Habitat GT. Two thresholds were checked on the
same `plant,tv_monitor` subset:

| Run | Max area ratio | Filtered detections | Positive rows | Out-of-view positive rows | Visible positive rows | Oracle-stop success rows | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| Unfiltered | n/a | n/a | `194` | `158` | `36` | `21` | Baseline diagnostic export |
| Conservative filter | `0.70` | `190` | `164` | `128` | `36` | `21` | Reduces broad false positives without losing visible positives |
| Aggressive filter | `0.40` | `272` | `114` | `102` | `12` | `11` | Over-filters and removes all plant visible positives |

The project should keep the conservative `0.70` default for now. It removes
pathological full-frame / union-mask detections while preserving the visible
positive rows in this subset. The `0.40` sweep is useful evidence that area
thresholds alone cannot solve the detector problem without harming `plant`.
Remaining TV-monitor false positives need a better mask source, category
sanity check, or appearance/segmentation validation rather than a stricter
global area cutoff.

## Follow-up

1. Manually review more than the four representative PNGs before making a paper
   claim about detector-vs-GT responsibility.
2. For `tv_monitor`, add a segmentation-backed mask or appearance sanity check
   before trusting broad Grounding-DINO boxes.
3. For `plant`, add an annotation-aware review bucket for edge-clipped GT and
   consider relaxing mask precision only in diagnostics, not in the main gate.
4. Add visibility-aware episode selection so categories are evaluated on frames
   where Habitat actually exposes enough target pixels.
