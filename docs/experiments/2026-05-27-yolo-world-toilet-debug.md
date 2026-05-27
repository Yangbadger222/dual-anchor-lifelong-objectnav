# Experiment Report: YOLO-World Toilet Miss Debug

Date: 2026-05-27  
Owner: Codex  
Status: Completed

## Question

Why did YOLO-World miss the visible `toilet` target in the clean Habitat
ObjectNav smoke, and what detector configuration is required before the
memory algorithm can be evaluated with real detector evidence?

## Hypothesis

The miss is not an environment-install failure. It is likely caused by a
combination of low RGB render resolution, open-vocabulary class competition,
and partial target views in the deterministic out-and-back sequence.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, starting from `4060f3f` |
| Machine | `badger-linux`, via `ssh badger@100.88.131.52` |
| Dataset / scene | HM3D ObjectNav `val_mini`, episode `39`, scene `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb` |
| Simulator | Habitat-Sim 0.3.3 / Habitat-Lab 0.3.3 |
| Python / env | conda env `habitat`, Python 3.9.23 |
| Detector stack | `torch==2.8.0+cu128`, `torchvision==0.23.0+cu128`, `ultralytics==8.4.56`, `clip==1.0`, `yolov8s-worldv2.pt` |
| Key parameters | `detector=yolo_world`, `noise_levels=clean`, `memory_ablation=on`, `max_episodes=1`, `seed=313`, sensor sizes `96`, `224`, `320` |

## Command

Run the 224 px and 320 px formal smokes:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/rgb_noise_yolo_world_clean_smoke_320 --noise-levels clean --detector yolo_world --memory-ablation on --max-episodes 1 --seed 313 --sensor-size 320'
```

Run raw low-threshold YOLO-World probes on the same 320 px trajectory using
prompt sets:

```text
all6 = bed, chair, plant, sofa, toilet, tv_monitor
toilet_only = toilet
toilet_aliases = toilet, bathroom toilet, toilet bowl, white toilet, commode
toilet_no_bed = chair, plant, sofa, toilet, tv_monitor
```

## Metrics

| Metric | 96 px all6 | 224 px all6 | 320 px all6 |
|---|---:|---:|---:|
| Episodes completed | 1 | 1 | 1 |
| Target-visible rows | 15 | 15 | 15 |
| Positive evidence rows | 0 | 0 | 2 |
| Mean detector precision | 0.0 | 0.0 | 0.122784 |
| Mean oracle recall | 0.0 | 0.0 | 0.199976 |
| Final `p_valid` | 0.011171 | 0.011171 | 0.027629 |

Prompt-set probe at 320 px, counting frames where the top target-like
detection reached confidence `>=0.25`:

| Prompt set | Target positives | Main observation |
|---|---:|---|
| `all6` | 2 / 15 | Early frames detect `toilet`; later visible regions are often labeled `bed` |
| `toilet_only` | 5 / 15 | Removes the `bed` competition and recovers frames 0, 1, 2, 4, 5 |
| `toilet_aliases` | 4 / 15 | Often prefers `white toilet`; frame 5 remains below 0.25 |
| `toilet_no_bed` | 3 / 15 | Removing only `bed` helps, but `sofa` then competes on some views |

## Observations

- A raw 320 px reset-frame probe detected the target strongly:
  `toilet` confidence `0.738678`, target semantic pixels `10909`, and bbox
  approximately `(39, 204, 211, 320)`.
- At 224 px the formal runner still produced zero detector positives, despite
  thousands of oracle target pixels per frame.
- At 320 px the formal all-category runner detected only the reset and first
  two action frames. Later frames still had oracle target pixels, but the
  detector either labeled the same region as `bed` or produced no target-like
  box above the threshold.
- Low-threshold probes showed concrete class competition: step 3 had a
  `bed` box with confidence `0.616843` covering the oracle `toilet` region,
  while no `toilet` box appeared even at confidence `0.001`.
- A contact sheet with the semantic overlay showed many later out-and-back
  frames place the target on the lower/right image edge. These are technically
  oracle-visible but visually partial, so they should not be treated as proof
  that YOLO-World is broken.

## Result

The root cause is a detector/input configuration problem, not a broken Linux
environment:

- `sensor_size=64` and `96` are too small for the YOLO-World validation path.
- `sensor_size=224` is still insufficient for the first `toilet` smoke.
- `sensor_size=320` is the first usable smoke resolution, but the legacy
  all-category prompt set causes open-vocabulary class competition.
- The ObjectNav goal category is known, so the harness should default to
  target-conditioned YOLO prompting and keep the all-category prompt set only
  as an ablation/debug mode.

## Follow-up

- Rerun the clean 1-episode smoke after changing the default to
  `--sensor-size 320 --yolo-prompt-mode target`.
- Add a category sweep before the full noise-memory matrix.
- Improve the revisit controller so detector validation samples full target
  views rather than many edge-clipped target fragments.
