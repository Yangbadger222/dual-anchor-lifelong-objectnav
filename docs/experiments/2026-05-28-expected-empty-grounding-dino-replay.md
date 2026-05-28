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
| Branch / commit | `main`, `c34e87f` for smokes; `cb22187` for the larger matrix before geometry-gate prototype |
| Machine | `badger-linux` |
| Environment | `conda habitat` |
| Dataset / scene root | HM3D ObjectNav `val_mini`, `datasets/habitat/scene_datasets/hm3d` |
| Replay protocol | `expected_empty_challenge` |
| Selection | `structured_visibility`, `bed,toilet,plant` |
| Memory modes | `on,naive_count,off` |
| Oracle output | `runs/habitat_usability/expected_empty_oracle_bbox_smoke` |
| Grounding-DINO output | `runs/habitat_usability/expected_empty_grounding_dino_smoke_1280x720_cap384` |
| Larger matrix output | `runs/habitat_usability/expected_empty_grounding_dino_matrix_1280x720_epc2_cap384` |
| Bed debug output | `runs/habitat_usability/expected_empty_bed_positive_debug_1280x720_epc2_cap384` |

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

Larger Grounding-DINO matrix:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav && \
source ~/anaconda3/etc/profile.d/conda.sh && \
conda activate habitat && \
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --output runs/habitat_usability/expected_empty_grounding_dino_matrix_1280x720_epc2_cap384 \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --rgb-noise-profile configs/noise/rgb_published_v1.yaml \
  --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml \
  --noise-levels clean,mild,heavy \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --grounding-dino-max-image-side 384 \
  --memory-ablation on,naive_count,off \
  --target-categories bed,toilet,plant \
  --episodes-per-category 2 \
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

### Larger Grounding-DINO Matrix

| Metric | Value |
|---|---:|
| Selected episodes | `3,33,55,39,62,84` |
| Selected categories | `bed=2`, `toilet=2`, `plant=2` |
| Episodes completed | `54` |
| Trace rows | `594` |
| Phase counts | `confirm=162`, `expected_empty=216`, `revisit=216` |
| Expected-empty evidence | `144 non_confirmation`, `72 positive` |

Memory comparison:

| Memory mode | Successful episodes | Success rows | Raw trust rows | Gate rejections | Mean first success step | Mean final `p_valid` |
|---|---:|---:|---:|---:|---:|---:|
| `on` | `18/18` | `77` | `115` | `38` | `1.277778` | `0.963567` |
| `naive_count` | `18/18` | `87` | `161` | `74` | `2.333333` | `0.941192` |
| `off` | `0/18` | `0` | `0` | `0` | n/a | `0.793014` |

Category detail:

| Category | Memory | Success rows | Raw trust rows | Gate rejections | Expected-empty positives | Expected-empty non-confirmations |
|---|---|---:|---:|---:|---:|---:|
| `bed` | `on` | `31` | `59` | `28` | `24` | `0` |
| `bed` | `naive_count` | `27` | `53` | `26` | `24` | `0` |
| `plant` | `on` | `23` | `28` | `5` | `0` | `24` |
| `plant` | `naive_count` | `30` | `54` | `24` | `0` | `24` |
| `toilet` | `on` | `23` | `28` | `5` | `0` | `24` |
| `toilet` | `naive_count` | `30` | `54` | `24` | `0` | `24` |

Noise detail:

| Noise | Memory | Success rows | Raw trust rows | Gate rejections | Expected-empty positives | Expected-empty non-confirmations |
|---|---|---:|---:|---:|---:|---:|
| `clean` | `on` | `24` | `34` | `10` | `8` | `16` |
| `clean` | `naive_count` | `30` | `54` | `24` | `8` | `16` |
| `mild` | `on` | `28` | `42` | `14` | `8` | `16` |
| `mild` | `naive_count` | `30` | `54` | `24` | `8` | `16` |
| `heavy` | `on` | `25` | `39` | `14` | `8` | `16` |
| `heavy` | `naive_count` | `27` | `53` | `26` | `8` | `16` |

### Bed Expected-Empty Debug

Debug export:

```bash
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --output runs/habitat_usability/expected_empty_bed_positive_debug_1280x720_epc2_cap384 \
  ... \
  --memory-ablation off \
  --target-categories bed \
  --episodes-per-category 2 \
  --replay-protocol expected_empty_challenge \
  --debug-export-categories bed \
  --debug-export-replay-phases expected_empty \
  --debug-export-evidence-types positive \
  --debug-export-limit-per-category 64
```

Artifacts:

- Remote debug PNGs:
  `runs/habitat_usability/expected_empty_bed_positive_debug_1280x720_epc2_cap384/debug_rows/`
- Local contact sheet:
  `/tmp/dual_anchor_expected_empty_bed_positive_debug/contact_sheet.png`

Trace evidence:

- `24/24` expected-empty bed positives had `target_visible=False`,
  `oracle_target_pixels=0`, and `overlap_pixels=0`.
- Episode `3` expected-empty positives produced detector masks around
  `352k` pixels on a `1280x720` frame, boxing a red dresser/wall region as
  `bed`.
- Episode `33` expected-empty positives boxed door/furniture-edge regions as
  `bed`.
- This supports the interpretation that the bed issue is mostly
  Grounding-DINO false positives, not Habitat GT being too strict around a
  visible bed.

Threshold ablation on the same bed diagnostic:

| Detector conf | Confirm positives | Expected-empty positives | Revisit positives | Read |
|---:|---:|---:|---:|---|
| `0.25` | `11/18` | `24/24` | `22/24` | default; many false positives |
| `0.35` | `6/18` | `19/24` | `12/24` | reduces false positives but kills recall |
| `0.45` | `5/18` | `12/24` | `12/24` | still false-positive, recall too low |
| `0.55` | `5/18` | `8/24` | `10/24` | still false-positive, recall too low |

## Observations

- The protocol works mechanically. Oracle-bbox turns all expected-empty rows into `NON_CONFIRMATION`.
- Grounding-DINO preserves real detector pressure: 12 expected-empty rows remain positive because the detector fires even when the oracle target is absent.
- `memory=on` sharply reduces stale raw trust and gate rejections in the expected-empty interval.
- `naive_count` keeps trusting through expected-empty because it never consumes non-confirmation, which is the intended fair baseline behavior.
- `memory=on` has fewer total success rows than `naive_count` because it becomes conservative after the empty verification interval; this is useful for stale-memory safety but not yet an ObjectNav efficiency win.
- The larger matrix keeps the same pattern for `plant` and `toilet`: memory
  cuts raw trust and gate rejections when expected-empty views generate real
  non-confirmation.
- `bed` is a detector bottleneck: expected-empty views are all positive, so
  memory cannot use negative evidence. Raising Grounding-DINO confidence is
  not a clean fix because it also removes many true visible bed positives.
- The current Habitat memory harness still stores compact category-scene
  belief rather than object-instance pose anchors. A geometry-consistency
  prototype is the next algorithmic refinement, but it must be reported
  separately because it is part of the memory contribution.

## Result

This is the first Habitat real-detector replay in this sequence that directly shows the intended negative-evidence contribution: under an expected-empty challenge, memory reduces stale trust relative to positive-only counting.

This is still a diagnostic replay, not a full ObjectNav result. It teleports between measured viewpoints and does not include long-distance path execution or SPL.

## Follow-up

- Run the optional `memory=on` geometry gate on the same expected-empty matrix
  to test whether spatial candidate consistency rejects bed false positives.
- Keep `naive_count` positive-only and geometry-free.
- Persist object-instance anchors across episodes if the geometry-gate smoke is
  promising.
- Combine expected-empty semantics with a long-range approach protocol or action-level Habitat follower before making a paper-level navigation claim.
