# Experiment Report: Visibility-Challenge Replay Smoke

Date: 2026-05-28  
Owner: Codex  
Status: Completed, diagnostic result, not a paper claim

## Question

Does `replay_protocol=visibility_challenge` actually create a target-visible
`confirm/revisit` interval and a target-hidden `depart/non_confirm` interval in
Habitat?

## Hypothesis

The protocol should make the hidden phases target-not-visible under
`oracle_bbox`. With Grounding-DINO, hidden phases may still contain detector
false positives, but the oracle target visibility should remain zero.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `df8cf45` |
| Machine | `badger-linux` |
| Environment | `conda habitat` |
| Dataset / scene root | HM3D ObjectNav `val_mini`, HM3D scene root on Linux |
| Replay protocol | `visibility_challenge` |
| Selection | `structured_visibility`, `bed,toilet,plant`, 1 episode/category |
| Resolution | `640x480` |
| Noise | `clean` |
| Memory modes | `on,naive_count,off` |
| Outputs | `runs/habitat_usability/visibility_challenge_oracle_bbox_smoke`, `runs/habitat_usability/visibility_challenge_grounding_dino_smoke_clean` |

Follow-up larger replay:

| Item | Value |
|---|---|
| Branch / commit | `main`, `7ba97fa` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny`, image-side cap `384` |
| Resolution | `1280x720` |
| Noise | `clean,mild,heavy` |
| Selection | `structured_visibility`, `bed,toilet,plant`, 2 episodes/category |
| Output | `runs/habitat_usability/visibility_challenge_grounding_dino_replay_1280x720_epc2_cap384` |
| Debug output | `runs/habitat_usability/visibility_challenge_hidden_bed_debug_1280x720_cap384` |

## Command

Oracle smoke:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav && \
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_usability/visibility_challenge_oracle_bbox_smoke \
  --noise-levels clean \
  --detector oracle_bbox \
  --detector-weights unused \
  --memory-ablation on,naive_count,off \
  --episodes-per-category 1 \
  --episode-selection-strategy structured_visibility \
  --target-categories bed,toilet,plant \
  --sensor-width 640 \
  --sensor-height 480 \
  --no-stop-on-trust \
  --replay-protocol visibility_challenge \
  --seed 313
```

Grounding-DINO smoke used the same parameters, replacing the detector with
`grounding_dino`, `IDEA-Research/grounding-dino-tiny`,
`--grounding-dino-text-threshold 0.25`, and
`--grounding-dino-max-image-side 384`.

## Metrics

### Oracle-Bbox Smoke

| Phase | Rows | Target-visible rows | Positive | Unknown | Raw trust | Gated trust / success | Gate rejections |
|---|---:|---:|---:|---:|---:|---:|---:|
| `confirm` | `27` | `27` | `18` | `9` | `3` | `3` | `0` |
| `depart` | `18` | `0` | `0` | `18` | `12` | `0` | `12` |
| `non_confirm` | `36` | `0` | `0` | `36` | `24` | `0` | `24` |
| `revisit` | `36` | `36` | `36` | `0` | `24` | `24` | `0` |

Memory comparison:

| Memory | Rows | Raw trust | Gated trust / success | Gate rejections | Positive | Unknown |
|---|---:|---:|---:|---:|---:|---:|
| `on` | `39` | `30` | `12` | `18` | `18` | `21` |
| `naive_count` | `39` | `33` | `15` | `18` | `18` | `21` |
| `off` | `39` | `0` | `0` | `0` | `18` | `21` |

### Grounding-DINO Smoke

| Phase | Rows | Target-visible rows | Positive | Unknown | Raw trust | Gated trust / success | Gate rejections |
|---|---:|---:|---:|---:|---:|---:|---:|
| `confirm` | `27` | `27` | `18` | `9` | `3` | `3` | `0` |
| `depart` | `18` | `0` | `6` | `12` | `12` | `0` | `12` |
| `non_confirm` | `36` | `0` | `12` | `24` | `24` | `0` | `24` |
| `revisit` | `36` | `36` | `36` | `0` | `24` | `24` | `0` |

Memory comparison:

| Memory | Rows | Raw trust | Gated trust / success | Gate rejections | Positive | Unknown |
|---|---:|---:|---:|---:|---:|---:|
| `on` | `39` | `30` | `12` | `18` | `24` | `15` |
| `naive_count` | `39` | `33` | `15` | `18` | `24` | `15` |
| `off` | `39` | `0` | `0` | `0` | `24` | `15` |

### 1280x720 Grounding-DINO Replay

This replay used the same visibility-challenge protocol with
`bed,toilet,plant`, two structured episodes per category, and all three noise
levels.

| Metric | Value |
|---|---:|
| Trace rows | `702` |
| Replay summaries | `54` |
| Selected episodes | `3, 33, 55, 39, 62, 84` |
| Selected categories | `bed=2`, `toilet=2`, `plant=2` |
| Detector filtered count | `63` |
| Mean detector precision | `0.291810` |
| Mean oracle recall | `0.496160` |

Phase audit:

| Phase | Rows | Target-visible rows | Positive | Unknown | Non-confirmation | Raw trust | Gated trust / success | Gate rejections |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `confirm` | `162` | `162` | `105` | `54` | `3` | `57` | `43` | `14` |
| `depart` | `108` | `0` | `36` | `72` | `0` | `72` | `0` | `72` |
| `non_confirm` | `216` | `0` | `72` | `144` | `0` | `144` | `0` | `144` |
| `revisit` | `216` | `216` | `207` | `0` | `9` | `139` | `136` | `3` |

Memory comparison:

| Memory | Rows | Raw trust | Gated trust / success | Gate rejections | Positive | Unknown | Non-confirmation |
|---|---:|---:|---:|---:|---:|---:|---:|
| `on` | `234` | `215` | `93` | `122` | `140` | `90` | `4` |
| `naive_count` | `234` | `197` | `86` | `111` | `140` | `90` | `4` |
| `off` | `234` | `0` | `0` | `0` | `140` | `90` | `4` |

Category comparison:

| Category | Rows | Visible | Positive | Success | Gate rejections |
|---|---:|---:|---:|---:|---:|
| `bed` | `234` | `126` | `204` | `51` | `79` |
| `plant` | `234` | `126` | `108` | `64` | `77` |
| `toilet` | `234` | `126` | `108` | `64` | `77` |

Hidden-phase detector positives:

| Category | Hidden rows | Hidden visible rows | Hidden positives | Hidden raw trust | Hidden gate rejections |
|---|---:|---:|---:|---:|---:|
| `bed` | `108` | `0` | `108` | `72` | `72` |
| `plant` | `108` | `0` | `0` | `72` | `72` |
| `toilet` | `108` | `0` | `0` | `72` | `72` |

### Hidden-Bed Debug Export

The bed-only debug run wrote:

`runs/habitat_usability/visibility_challenge_hidden_bed_debug_1280x720_cap384`

It exported `79` bed gate-rejection PNGs, including all `72` hidden-phase
rows. A local contact sheet was generated at:

`/tmp/dual_anchor_hidden_bed_debug/contact_sheet.png`

Visual inspection of 12 sampled hidden-phase PNGs shows Grounding-DINO
repeatedly boxing door/furniture regions in the turned-around view while the
Habitat target mask is absent. This looks like detector false positive behavior
under the `bed` prompt, not simply strict Habitat GT on a visible bed.

## Observations

- The visibility protocol works at the oracle-visibility level: both smokes
  have zero target-visible rows in `depart` and `non_confirm`, and all revisit
  rows are target-visible.
- With `oracle_bbox`, hidden phases produce `unknown`, not
  `non_confirmation`, because the current evidence classifier treats
  target-out-of-current-view as unknown. This is expected under the current
  classifier but means the protocol is a hidden-view challenge, not yet a
  verified-location failure challenge.
- Grounding-DINO produced positive detector evidence in hidden phases
  (`6` depart rows, `12` non-confirm rows), while oracle visibility stayed
  zero. This is useful: the protocol now exposes detector false-positive /
  false-trust pressure after leaving the target.
- `naive_count` still slightly exceeds memory `on` in this small smoke
  (`15` vs `12` gated successes). This is not a memory result; it is only a
  protocol smoke.
- In the larger `1280x720` run, memory `on` now exceeds `naive_count` on gated
  success rows (`93` vs `86`) but also has more raw trust and gate rejections
  (`122` vs `111`). This is promising but still not clean evidence because
  hidden-phase detector false positives dominate `bed`.
- Hidden-phase Grounding-DINO positives are category-specific in this run:
  all `108` hidden positives are `bed`; `plant` and `toilet` have zero hidden
  positives.

## Result

`visibility_challenge` should replace plain `out_and_back` for the next memory
comparison. It creates the intended visible-hidden-revisit structure and makes
the memory comparison more meaningful. The 1280x720 result is the first Habitat
run in this line where memory `on` beats `naive_count` on gated success rows
under a real detector, but the result is still diagnostic because the hidden
interval mainly exposes `bed` false positives and the evidence classifier still
treats target-hidden views as `unknown`, not true `NON_CONFIRMATION`.

## Follow-up

- Run the same visibility-challenge comparison with hidden-phase positive PNG
  export enabled for all categories at a controlled cap, or add trace filters
  that export only hidden-phase positives.
- Consider a new replay subphase or evidence context for "expected location is
  in view and empty" so the hidden interval can produce true
  `NON_CONFIRMATION` without borrowing algorithm contributions for
  `naive_count`.
- Reintroduce `sofa`, `tv_monitor`, and `chair` through a fallback or
  visibility-aware selector before treating the category set as complete.
