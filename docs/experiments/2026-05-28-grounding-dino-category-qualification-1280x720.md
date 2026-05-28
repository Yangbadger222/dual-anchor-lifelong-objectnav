# Experiment Report: Grounding-DINO Detector Category Qualification At 1280x720

Date: 2026-05-28  
Owner: Codex  
Status: Completed, first pass

## Question

If the ObjectNav detector backend is changed from YOLO-World to
Grounding-DINO, do all six HM3D ObjectNav categories become detector-ready under
the same clean `1280x720` qualification protocol?

## Short Answer

Grounding-DINO is a clear improvement over YOLO-World, but the raw first-N
category qualification is still not "all six ready" because the first selected
`chair` episodes contain zero target-visible rows.

With visibility-aware episode selection, all six categories have positive
evidence:

- `bed`, `sofa`, `toilet`, and `plant` are ready in the main 2-episode
  full-trace pass.
- `tv_monitor` has one successful episode out of the first two; it is usable
  but sparse-view sensitive.
- `chair` succeeds in later probe episodes once the target has any visible row,
  so the blocker is episode visibility, not a clean detector miss.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `35d4424` for cap support; Linux later pulled `d94d14e` for no-grad inference |
| Machine | `badger-linux`, via `ssh badger@100.88.131.52` |
| Dataset | HM3D ObjectNav `val_mini` |
| Simulator | Habitat-Sim 0.3.3 / Habitat-Lab 0.3.3 |
| Python / env | conda env `habitat`, Python 3.9.23 |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny`, Transformers `4.57.6` |
| Runtime dependencies added | `transformers`, `safetensors`, `huggingface_hub`, `accelerate` |
| Habitat render resolution | `1280x720` |
| Detector inference cap | `grounding_dino_max_image_side=384` |
| Prompt mode | `target` |
| Noise | `clean` |

## Implementation Notes

Grounding-DINO was added as a detector adapter with the same contract as
YOLO-World:

```text
Detection(category, bbox, confidence, mask)
```

The adapter uses Hugging Face Transformers'
`AutoProcessor` / `AutoModelForZeroShotObjectDetection` path. Habitat still
renders at `1280x720`, but Grounding-DINO inference is capped at image side
`384` to fit the RTX 4070 Laptop GPU. Boxes are scaled back to the original
Habitat frame before mask metrics are computed.

Two compatibility fixes were needed:

- Transformers `4.57.6` uses `threshold`, not `box_threshold`, in
  `post_process_grounded_object_detection`.
- Newer post-processing exposes string names through `text_labels`; the adapter
  reads `text_labels` first and falls back to `labels`.

The first `1280x720` uncapped and `cap=640/512` attempts failed with CUDA OOM,
so the reported results use `cap=384`.

## Commands

Focused Linux tests:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core pytest -q src/objectnav_core/tests/test_grounding_dino_adapter.py src/objectnav_core/tests/test_habitat_objectnav_rgb_noise_stress.py'
```

Preflight:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --output runs/habitat_usability/grounding_dino_category_qualification_1280x720_preflight --noise-levels clean --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --memory-ablation on --episodes-per-category 1 --sensor-width 1280 --sensor-height 720 --preflight-only'
```

One episode per category, with stop-on-trust:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/grounding_dino_category_qualification_1280x720_epc1_cap384 --noise-levels clean --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --memory-ablation on --episodes-per-category 1 --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --stop-on-trust --seed 313'
```

Two episodes per category, full trace:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/grounding_dino_category_qualification_1280x720_epc2_fulltrace_cap384 --noise-levels clean --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --memory-ablation on --episodes-per-category 2 --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --seed 313'
```

Chair visibility probe:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/grounding_dino_category_qualification_1280x720_chair_probe_cap384 --noise-levels clean --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --memory-ablation on --episodes-per-category 7 --target-categories chair --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --seed 313'
```

## Metrics

### Stop-on-trust pass, 1 episode per category

| Category | Episodes | Target-visible rows | Oracle-stop successes | Status |
|---|---:|---:|---:|---|
| `bed` | 1 | 4 | 1 | Ready |
| `chair` | 1 | 0 | 0 | Not assessable; no visible target rows |
| `plant` | 1 | 7 | 1 | Ready; improved over YOLO-World |
| `sofa` | 1 | 4 | 1 | Ready |
| `toilet` | 1 | 4 | 1 | Ready |
| `tv_monitor` | 1 | 2 | 0 | Sparse-view sensitive |

Run summary:

| Metric | Value |
|---|---:|
| Episodes completed | 6 |
| Trace rows | 57 |
| Oracle-stop success rows | 4 |
| Evidence counts | `positive=41`, `non_confirmation=3`, `unknown=13` |
| Mean oracle recall | `0.308681` |
| Mean detector precision | `0.153027` |
| Mean final `p_valid` | `0.960573` |

### Full-trace pass, 2 episodes per category

| Category | Episodes | Visible rows | Oracle-stop success rows | Interpretation |
|---|---:|---:|---:|---|
| `bed` | 2 | 30 | 27 | Ready |
| `chair` | 2 | 0 | 0 | Not assessable from first two episodes |
| `plant` | 2 | 14 | 4 | Ready; no longer a detector blocker |
| `sofa` | 2 | 30 | 24 | Ready |
| `toilet` | 2 | 28 | 25 | Ready |
| `tv_monitor` | 2 | 4 | 2 | Usable, but sparse-view sensitive |

Run summary:

| Metric | Value |
|---|---:|
| Episodes completed | 12 |
| Trace rows | 180 |
| Oracle-stop success rows | 82 |
| Evidence counts | `positive=148`, `non_confirmation=6`, `unknown=26` |
| Mean oracle recall | `0.551045` |
| Mean detector precision | `0.235613` |
| Mean final `p_valid` | `0.991109` |

### Chair visibility probe

| Episode pattern | Episodes | Visible rows | Oracle-stop successes | Interpretation |
|---|---:|---:|---:|---|
| First sampled chair episodes | 3 | 0 each | 0 | Not detector-evaluable |
| Later sparse-visible chair episodes | 4 | 1 each | 3 | Detector can support chair when any target row is visible |

Probe summary:

| Metric | Value |
|---|---:|
| Episodes completed | 7 |
| Trace rows | 105 |
| Oracle-stop success rows | 3 |
| Evidence counts | `positive=74`, `unknown=31` |
| Mean oracle recall | `0.037973` |
| Mean detector precision | `0.026026` |
| Mean final `p_valid` | `0.993889` |

## Comparison With YOLO-World

| Category | YOLO-World 1280x720 | Grounding-DINO 1280x720 cap384 |
|---|---|---|
| `bed` | Ready | Ready |
| `sofa` | Ready | Ready |
| `toilet` | Usable, view-sensitive | Ready |
| `plant` | Detector blocker | Ready |
| `tv_monitor` | Detector / sparse visibility blocker | Usable, sparse-view sensitive |
| `chair` | Sampling / visibility blocker | Sampling / visibility blocker, but succeeds in later sparse-visible probe |

## Result

Grounding-DINO should replace YOLO-World for the next detector-backed
qualification stage. It removes the `plant` blocker and provides positive
evidence for `tv_monitor` and sparse-visible `chair` samples.

The remaining blocker is not simply the detector. The qualification protocol
must select episodes/views by oracle target visibility before declaring a
category failed. Under the current first-N selection, the first `chair` samples
have no target-visible rows, so an all-six category-ready claim would be
misleading.

## Follow-up

- Implement visibility-aware category qualification.
- Re-run Grounding-DINO with at least one oracle-visible sample per category.
- Keep `grounding_dino_max_image_side=384` for the 4070 Laptop GPU unless a
  larger GPU is available.
- Then run the first `clean/mild/heavy x memory on/off` matrix on categories
  that pass visibility-aware qualification.
