# Experiment Report: Visibility-Challenge Replay Smoke

Date: 2026-05-28  
Owner: Codex  
Status: Completed, protocol smoke only

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

## Result

`visibility_challenge` should replace plain `out_and_back` for the next memory
comparison. It creates the intended visible-hidden-revisit structure. The next
algorithm question is whether hidden-view `unknown` is sufficient, or whether a
separate "expected target location verified empty" evidence path is needed to
produce true `non_confirmation`.

## Follow-up

- Run a larger Grounding-DINO visibility-challenge comparison at `1280x720`.
- Export hidden-phase Grounding-DINO positives, especially for `bed`, to inspect
  detector false positives.
- Consider a new replay subphase or evidence context for "expected location is
  in view and empty" so the hidden interval can produce true
  `NON_CONFIRMATION` without borrowing algorithm contributions for
  `naive_count`.
