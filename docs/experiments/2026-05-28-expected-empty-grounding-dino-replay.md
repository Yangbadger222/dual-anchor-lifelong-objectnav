# Experiment Report: Expected-Empty Grounding-DINO Replay

Date: 2026-05-28  
Owner: Codex  
Status: Completed smoke, diagnostic result

## Question

Can `replay_protocol=expected_empty_challenge` create true expected-location-empty `NON_CONFIRMATION` evidence, and does `memory=on` reduce stale trust compared with positive-only `naive_count`?

## Hypothesis

With `oracle_bbox`, all expected-empty rows should become `NON_CONFIRMATION`. With Grounding-DINO, some expected-empty rows may remain positive because of detector false positives, but memory should still reduce raw trust and gate rejections relative to `naive_count`.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `c34e87f` |
| Machine | `badger-linux` |
| Environment | `conda habitat` |
| Dataset / scene root | HM3D ObjectNav `val_mini`, `datasets/habitat/scene_datasets/hm3d` |
| Replay protocol | `expected_empty_challenge` |
| Selection | `structured_visibility`, `bed,toilet,plant`, 1 episode/category |
| Memory modes | `on,naive_count,off` |
| Oracle output | `runs/habitat_usability/expected_empty_oracle_bbox_smoke` |
| Grounding-DINO output | `runs/habitat_usability/expected_empty_grounding_dino_smoke_1280x720_cap384` |

## Command

Grounding-DINO smoke:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav && \
source ~/anaconda3/etc/profile.d/conda.sh && \
conda activate habitat && \
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --output runs/habitat_usability/expected_empty_grounding_dino_smoke_1280x720_cap384 \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --rgb-noise-profile configs/noise/rgb_published_v1.yaml \
  --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml \
  --noise-levels clean \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --grounding-dino-max-image-side 384 \
  --memory-ablation on,naive_count,off \
  --target-categories bed,toilet,plant \
  --episodes-per-category 1 \
  --episode-selection-strategy structured_visibility \
  --structured-min-goal-viewpoints 2 \
  --structured-min-geodesic-distance 2.0 \
  --structured-min-path-complexity-ratio 1.2 \
  --start-source episode_start \
  --replay-protocol expected_empty_challenge \
  --sensor-width 1280 \
  --sensor-height 720 \
  --no-stop-on-trust \
  --seed 313
```

## Metrics

### Oracle-Bbox Smoke

| Metric | Value |
|---|---:|
| Trace rows | `99` |
| Phase counts | `confirm=27`, `expected_empty=36`, `revisit=36` |
| Expected-empty evidence | `36 non_confirmation`, `0 positive` |
| Total oracle-stop success rows | `24` |

Memory comparison:

| Memory mode | Successful episodes | Success rows | Raw trust rows | Gate rejections | Mean final `p_valid` |
|---|---:|---:|---:|---:|---:|
| `on` | `3/3` | `9` | `9` | `0` | `0.961053` |
| `naive_count` | `3/3` | `15` | `27` | `12` | `0.941192` |
| `off` | `0/3` | `0` | `0` | `0` | `0.811041` |

Phase detail:

| Memory | Phase | Rows | Expected-empty rows | Positive | Non-confirmation | Raw trust | Gated success | Gate rejections |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `on` | `expected_empty` | `12` | `12` | `0` | `12` | `0` | `0` | `0` |
| `naive_count` | `expected_empty` | `12` | `12` | `0` | `12` | `12` | `0` | `12` |

### Grounding-DINO Smoke

| Metric | Value |
|---|---:|
| Trace rows | `99` |
| Phase counts | `confirm=27`, `expected_empty=36`, `revisit=36` |
| Expected-empty evidence | `24 non_confirmation`, `12 positive` |
| Total oracle-stop success rows | `26` |
| Detector filtered count | `0` |

Memory comparison:

| Memory mode | Successful episodes | Success rows | Raw trust rows | Gate rejections | Mean final `p_valid` |
|---|---:|---:|---:|---:|---:|
| `on` | `3/3` | `11` | `15` | `4` | `0.973380` |
| `naive_count` | `3/3` | `15` | `27` | `12` | `0.941192` |
| `off` | `0/3` | `0` | `0` | `0` | `0.811041` |

Phase detail:

| Memory | Phase | Rows | Expected-empty rows | Positive | Non-confirmation | Raw trust | Gated success | Gate rejections |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `on` | `confirm` | `9` | `0` | `6` | `0` | `3` | `3` | `0` |
| `on` | `expected_empty` | `12` | `12` | `4` | `8` | `4` | `0` | `4` |
| `on` | `revisit` | `12` | `0` | `12` | `0` | `8` | `8` | `0` |
| `naive_count` | `confirm` | `9` | `0` | `6` | `0` | `3` | `3` | `0` |
| `naive_count` | `expected_empty` | `12` | `12` | `4` | `8` | `12` | `0` | `12` |
| `naive_count` | `revisit` | `12` | `0` | `12` | `0` | `12` | `12` | `0` |

## Observations

- The protocol works mechanically. Oracle-bbox turns all expected-empty rows into `NON_CONFIRMATION`.
- Grounding-DINO preserves real detector pressure: 12 expected-empty rows remain positive because the detector fires even when the oracle target is absent.
- `memory=on` sharply reduces stale raw trust and gate rejections in the expected-empty interval.
- `naive_count` keeps trusting through expected-empty because it never consumes non-confirmation, which is the intended fair baseline behavior.
- `memory=on` has fewer total success rows than `naive_count` because it becomes conservative after the empty verification interval; this is useful for stale-memory safety but not yet an ObjectNav efficiency win.

## Result

This is the first Habitat real-detector replay in this sequence that directly shows the intended negative-evidence contribution: under an expected-empty challenge, memory reduces stale trust relative to positive-only counting.

This is still a diagnostic replay, not a full ObjectNav result. It teleports between measured viewpoints and does not include long-distance path execution or SPL.

## Follow-up

- Scale `expected_empty_challenge` to `clean,mild,heavy` and more episodes/categories.
- Add debug PNG export for expected-empty detector-positive rows to identify which categories produce false positives.
- Combine expected-empty semantics with a long-range approach protocol or action-level Habitat follower before making a paper-level navigation claim.
