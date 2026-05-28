# Experiment Report: YOLO-World Detector Category Qualification At 1280x720

Date: 2026-05-28  
Owner: Codex  
Status: Completed, first pass

## Question

At a realistic RGB-D camera-like render resolution, which HM3D ObjectNav
categories can the current YOLO-World detector path support before running the
full noise-memory matrix?

## Hypothesis

The previous 320 px smoke proved the pipeline can work for `toilet`, but it was
still a low-resolution smoke. Rendering at `1280x720` should improve detector
input quality and reveal which categories are truly detector-ready under clean
RGB.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `18254e7` |
| Machine | `badger-linux`, via `ssh badger@100.88.131.52` |
| Dataset | HM3D ObjectNav `val_mini` |
| Simulator | Habitat-Sim 0.3.3 / Habitat-Lab 0.3.3 |
| Python / env | conda env `habitat`, Python 3.9.23 |
| Detector | YOLO-World `yolov8s-worldv2.pt`, Ultralytics `8.4.56` |
| Resolution | `1280x720`, matching the D435 depth stream maximum and a realistic RGB-D processing resolution |
| Prompt mode | `target` |
| Noise | `clean` |

## Commands

Preflight:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --output runs/habitat_usability/detector_category_qualification_1280x720_preflight --noise-levels clean --detector yolo_world --memory-ablation on --episodes-per-category 1 --sensor-width 1280 --sensor-height 720 --preflight-only'
```

One episode per category, with ObjectNav stop semantics:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/detector_category_qualification_1280x720_epc1 --noise-levels clean --detector yolo_world --memory-ablation on --episodes-per-category 1 --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --stop-on-trust --seed 313'
```

Two episodes per category, full trace without early stop:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/detector_category_qualification_1280x720_epc2_fulltrace --noise-levels clean --detector yolo_world --memory-ablation on --episodes-per-category 2 --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --seed 313'
```

Additional chair / tv-monitor visibility probe:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/detector_category_qualification_1280x720_chair_tv_probe --noise-levels clean --detector yolo_world --memory-ablation on --episodes-per-category 7 --target-categories chair,tv_monitor --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --seed 313'
```

## Metrics

### Stop-on-trust pass, 1 episode per category

| Category | Episodes | Oracle-stop successes | Final status |
|---|---:|---:|---|
| `bed` | 1 | 1 | Detector-ready first pass |
| `chair` | 1 | 0 | Not assessable; target-visible rows `0` |
| `plant` | 1 | 0 | Detector failure |
| `sofa` | 1 | 1 | Detector-ready first pass |
| `toilet` | 1 | 1 | Detector-ready first pass |
| `tv_monitor` | 1 | 0 | Detector failure / weak visibility |

Run summary:

| Metric | Value |
|---|---:|
| Episodes completed | 6 |
| Trace rows | 59 |
| Oracle-stop success rows | 3 |
| Evidence counts | `positive=10`, `non_confirmation=8`, `unknown=41` |
| Mean oracle recall | `0.188542` |
| Mean detector precision | `0.156807` |
| Mean final `p_valid` | `0.652526` |

### Full-trace pass, 2 episodes per category

| Category | Episodes | Visible rows | Positive rows | Trust rows | Success rows | Max conf | Mean visible recall | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `bed` | 2 | 30 | 28 | 27 | 27 | 0.6005 | 0.4272 | Detector-ready |
| `chair` | 2 | 0 | 0 | 0 | 0 | 0.0 | 0.0 | Not assessable from first two episodes |
| `plant` | 2 | 14 | 0 | 0 | 0 | 0.0 | 0.0 | Detector blocker |
| `sofa` | 2 | 30 | 27 | 23 | 23 | 0.9773 | 0.9585 | Detector-ready |
| `toilet` | 2 | 28 | 8 | 2 | 2 | 0.7709 | 0.3571 | Detector usable, view-sensitive |
| `tv_monitor` | 2 | 4 | 0 | 0 | 0 | 0.0 | 0.0 | Detector blocker / sparse visibility |

Run summary:

| Metric | Value |
|---|---:|
| Episodes completed | 12 |
| Trace rows | 180 |
| Oracle-stop success rows | 52 |
| Evidence counts | `positive=63`, `non_confirmation=33`, `unknown=84` |
| Mean oracle recall | `0.286505` |
| Mean detector precision | `0.211355` |
| Mean final `p_valid` | `0.486492` |

### Chair / tv-monitor probe

The first two chair episodes were not detector failures: they had
`target_visible_rows=0`. A larger probe selected 7 chair episodes and 3
tv-monitor episodes:

| Category | Episodes | Visible rows pattern | Positive rows | Mean oracle recall | Interpretation |
|---|---:|---|---:|---:|---|
| `chair` | 7 | first 3 had `0`; later four had only `1` visible row each | 0 | 0.0 | Current goal-viewpoint sampling does not provide usable chair views |
| `tv_monitor` | 3 | `2` visible rows per episode | 0 | 0.0 | Detector does not confirm sparse visible targets |

## Observations

- `1280x720` runs completed successfully in the Linux Habitat environment.
- The detector-ready categories in this first pass are `bed`, `sofa`, and
  `toilet`.
- `toilet` remains view-sensitive: it succeeds under stop-on-trust but full
  traces include later poor views that lower final belief if not stopped.
- `plant` remains a clean detector blocker even at `1280x720`.
- `tv_monitor` has too few visible rows in the sampled episodes and zero
  positive detections.
- `chair` cannot be qualified from the early `val_mini` goal viewpoints because
  the target is absent or barely visible in sampled views, despite chair
  semantic IDs existing in the scene.

## Result

The category qualification should gate the full noise-memory matrix:

- **Ready for main experiment:** `bed`, `sofa`, `toilet`
- **Detector blocker:** `plant`, `tv_monitor`
- **Sampling / visibility blocker:** `chair`

This is the right failure mode to expose before the full matrix. Running
`clean/mild/heavy x memory on/off` across all categories now would mix memory
behavior with detector and viewpoint failures.

## Follow-up

- Add a qualification mode that selects episodes by actual reset/goal-viewpoint
  oracle visibility, not only by dataset category order.
- Generate debug PNGs for `plant`, `tv_monitor`, and `chair` missed-visible rows.
- Try a stronger open-vocabulary detector or larger YOLO-World weights for
  `plant` and `tv_monitor`.
- Run the first noise-memory matrix only on detector-ready categories
  (`bed`, `sofa`, `toilet`) unless the detector blockers are fixed.
