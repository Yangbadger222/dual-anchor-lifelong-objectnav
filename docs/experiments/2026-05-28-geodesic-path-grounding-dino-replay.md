# Experiment Report: Long-Range Geodesic Grounding-DINO Replay

Date: 2026-05-28  
Owner: Codex  
Status: Completed smoke, not a paper claim

## Question

Can the RGB-noise ObjectNav harness replay official episode-start to goal-viewpoint paths with Grounding-DINO, and does `memory=on` outperform positive-only `naive_count` on a small long-range smoke?

## Hypothesis

`geodesic_path` should produce plausible long-range approach distances from official ObjectNav starts. `memory=on` may reduce false raw trust compared with `naive_count`, but a one-episode-per-category smoke may still mostly reward repeated positives and therefore may not prove a memory advantage.

## Environment

| Item | Value |
|---|---|
| Branch / commits | `main`, `1a96500`, `07ef48b`, `2e67295` |
| Machine | `badger-linux` |
| Environment | `conda habitat` |
| Dataset / scene root | HM3D ObjectNav `val_mini`, `datasets/habitat/scene_datasets/hm3d` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny`, image-side cap `384` |
| Resolution | `1280x720` |
| Noise | `clean` |
| Memory modes | `on,naive_count,off` |
| Selection | `structured_visibility`, `bed,toilet,plant`, 1 episode/category |
| Replay | `geodesic_path`, `episode_start`, max 12 approach waypoints |
| Outputs | `runs/habitat_usability/geodesic_path_grounding_dino_smoke_1280x720_cap384`, `runs/habitat_usability/geodesic_path_grounding_dino_smoke_1280x720_cap384_current_positive`, `runs/habitat_usability/geodesic_path_grounding_dino_smoke_1280x720_cap384_delayed_birth` |

## Command

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav && \
source ~/anaconda3/etc/profile.d/conda.sh && \
conda activate habitat && \
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --output runs/habitat_usability/geodesic_path_grounding_dino_smoke_1280x720_cap384_delayed_birth \
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
  --replay-protocol geodesic_path \
  --geodesic-path-max-steps 12 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --no-stop-on-trust \
  --seed 313
```

## Metrics

### Episode Selection

| Metric | Value |
|---|---:|
| Selected episode IDs | `3, 55, 62` |
| Selected category counts | `bed=1`, `toilet=1`, `plant=1` |
| Candidate episodes after structured filter | `9` |
| Zero structured candidate categories | none |

Per selected episode:

| Category | Episode | Geodesic distance | Euclidean distance | Replay path translation |
|---|---:|---:|---:|---:|
| `bed` | `3` | `5.76461` | `3.83493` | `6.338411` |
| `toilet` | `55` | `17.11442` | `5.57042` | `17.653137` |
| `plant` | `62` | `14.71760` | `4.07095` | `15.187949` |

### Overall Result

| Run | Commit | Raw trust | Gated success rows | Gate rejections | Notes |
|---|---|---:|---:|---:|---|
| baseline geodesic | `1a96500` | `49` | `23` | `26` | first Grounding-DINO long-range smoke |
| current-positive trust | `07ef48b` | `52` | `24` | `28` | `bed` memory catches up by one row |
| delayed birth | `2e67295` | `52` | `24` | `28` | no metric change from current-positive run |

The delayed-birth run produced `114` trace rows, with phase counts `approach=87` and `confirm=27`.

### Memory Comparison After Delayed Birth

| Memory mode | Rows | Raw trust | Gated success | Gate rejections | Final `p_valid` by category |
|---|---:|---:|---:|---:|---|
| `on` | `38` | `24` | `11` | `13` | bed `0.980614`, toilet `0.997939`, plant `0.968501` |
| `naive_count` | `38` | `28` | `13` | `15` | all `0.941192` |
| `off` | `38` | `0` | `0` | `0` | all `0.811041` |

Category detail:

| Category | Memory | Visible rows | Positive rows | Raw trust | Gated success | Gate rejections | First positive step |
|---|---|---:|---:|---:|---:|---:|---:|
| `bed` | `on` | `5` | `5` | `4` | `4` | `0` | `3` |
| `bed` | `naive_count` | `5` | `5` | `4` | `4` | `0` | `3` |
| `toilet` | `on` | `5` | `10` | `11` | `5` | `6` | `3` |
| `toilet` | `naive_count` | `5` | `10` | `11` | `5` | `6` | `3` |
| `plant` | `on` | `6` | `9` | `9` | `2` | `7` | `1` |
| `plant` | `naive_count` | `6` | `9` | `13` | `4` | `9` | `1` |

## Observations

- The long-range replay bridge works mechanically: replay path translation is close to the official geodesic distance and is much longer than the earlier local visibility challenge.
- `memory=off` remains a strict single-frame sanity baseline and produces zero successes.
- `memory=on` reduces raw trust relative to `naive_count`, but in this small smoke it also has fewer gated success rows because the task mostly rewards repeated positive detections.
- The current-positive trust change improved the smoke by one success row, making `bed` match `naive_count`.
- Delayed birth fixed the algorithm boundary but did not change this smoke because the first positive evidence appears early, especially for `plant` at step 1.
- `plant` remains the blocking category: `memory=on` is more conservative and gets `2` gated successes versus `4` for `naive_count`.

## Result

`geodesic_path` is a useful long-range replay bridge, but this smoke does not prove that the memory algorithm is better than `naive_count`. The right conclusion is narrower:

1. The harness can run official episode-start to goal-viewpoint long-range replay with Grounding-DINO at `1280x720`.
2. The current memory policy is conservative and can reduce raw trust, but it does not yet dominate positive-only counting on this repeated-positive smoke.
3. Delayed birth is correct to keep, but it is not the main bottleneck for these selected episodes.
4. The next larger run needs timing metrics and a stronger lifelong/expected-empty challenge before any paper claim.

## Follow-up

- Rerun this smoke after adding per-episode first-success and path-to-success metrics.
- Scale to a larger `clean,mild,heavy` geodesic matrix only after the metrics can show both reliability and efficiency.
- Add an expected-location-empty verification context before claiming stale-memory handling from Habitat replay.
- Connect to an action-level Habitat follower after the replay metrics are stable.
