# Experiment Report: Habitat Closed-Loop Grounding-DINO Candidate Gate

Date: 2026-05-29  
Owner: Codex  
Status: Completed smoke, not paper-ready

## Question

Can the Habitat closed-loop runner replace oracle semantic visibility with
Grounding-DINO candidate verification while preserving a fair shared gate across
`memory_guided`, `frontier_only`, and `naive_count`?

This experiment asks a narrower question than full ObjectNav: it verifies
selected memory/fallback candidate views with a real detector, then executes
Habitat GreedyGeodesic action routes. It does not yet observe every action step
or build a real frontier map.

## Hypothesis

If Grounding-DINO can produce positive evidence for the selected candidate
views, then:

- in `stable`, `memory_guided` should tie the positive-only `naive_count`
  baseline and both should beat `frontier_only`;
- in repeated `stale_proxy`, `memory_guided` should repair once and reuse the
  repaired anchor, while `naive_count` should keep attempting the stale old
  positive memory and pay memory-plus-frontier cost every repeat;
- all policies must see the same detector evidence and gate thresholds.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `aa2b562` |
| Machine | Linux `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset / map | HM3D ObjectNav `val`, HM3D v0.2 scene root |
| Simulator | Habitat-Sim GreedyGeodesic action routes |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Detector thresholds | `detector_conf=0.25`, `grounding_dino_text_threshold=0.25` |
| Image cap | `grounding_dino_max_image_side=384` |
| Sensor resolution | `1280x720` |
| Noise | `clean`, with configured RGB/depth noise profiles |
| Gate | `min_target_pixels=24`, `min_detector_pixels=20`, `max_detection_area_ratio=0.7` |
| Policies | `memory_guided`, `frontier_only`, `naive_count` |

## Commands

Focused Linux tests:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
git pull --ff-only
/home/badger/anaconda3/bin/conda run -n habitat \
  env PYTHONPATH=src/objectnav_core PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py \
    src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
```

Six-category stale repeat:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
/home/badger/anaconda3/bin/conda run -n habitat \
env PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/grounding_dino_candidate_gate_6cat_stale_repeats2_v1 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 6 \
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
  --challenge stale_proxy \
  --query-repeats 2
```

Six-category stable sanity:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
/home/badger/anaconda3/bin/conda run -n habitat \
env PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/grounding_dino_candidate_gate_6cat_stable_v1 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 6 \
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
  --challenge stable \
  --query-repeats 1
```

## Selected Episodes

The balanced six-category runs selected one group per ObjectNav category:

| Category | Group |
|---|---|
| `chair` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|chair|goal_object:445` |
| `plant` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|plant|goal_object:183` |
| `sofa` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|sofa|goal_object:275` |
| `toilet` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|toilet|goal_object:51` |
| `bed` | `hm3d/val/00802-wcojb4TFT35/wcojb4TFT35.basis.glb|bed|goal_object:17` |
| `tv_monitor` | `hm3d/val/00813-svBbv1Pavdk/svBbv1Pavdk.basis.glb|tv_monitor|goal_object:287` |

Candidate episode count was `652`; selected group count was `6`.

## Results

### Stable Balanced6 Sanity

Run:
`runs/habitat_closed_loop_dual_anchor/grounding_dino_candidate_gate_6cat_stable_v1`

| Policy | Episodes | Success | Actions | Distance | Memory reuse | Frontier selections |
|---|---:|---:|---:|---:|---:|---:|
| `memory_guided` | 6 | 6/6 | 575 | 86.391888 m | 6 | 0 |
| `naive_count` | 6 | 6/6 | 575 | 86.391888 m | 6 | 0 |
| `frontier_only` | 6 | 6/6 | 1313 | 184.143982 m | 0 | 6 |

Stable sanity interpretation: this is the expected tie. When all remembered
anchors are valid and detector-positive, the proposed stale-repair machinery
does not beat a positive-only count baseline; both memory policies save `738`
actions versus `frontier_only`.

All selected memory and fallback candidate gates were Grounding-DINO positive:

| Category | Memory evidence | Fallback evidence |
|---|---|---|
| `bed` | 3 positive | 3 positive |
| `chair` | 3 positive | 3 positive |
| `plant` | 3 positive | 3 positive |
| `sofa` | 3 positive | 3 positive |
| `toilet` | 3 positive | 3 positive |
| `tv_monitor` | 3 positive | 3 positive |

### Repeated Stale Balanced6

Run:
`runs/habitat_closed_loop_dual_anchor/grounding_dino_candidate_gate_6cat_stale_repeats2_v1`

| Policy | Episodes | Success | Actions | Distance | Memory reuse | Frontier selections |
|---|---:|---:|---:|---:|---:|---:|
| `memory_guided` | 12 | 12/12 | 2018 | 280.653296 m | 6 | 6 |
| `frontier_only` | 12 | 12/12 | 3072 | 424.352192 m | 0 | 12 |
| `naive_count` | 12 | 12/12 | 4144 | 580.836436 m | 0 | 12 |

Memory-guided deltas:

| Comparison | Action delta | Distance delta |
|---|---:|---:|
| vs `frontier_only` | +1054 | +143.698896 m |
| vs `naive_count` | +2126 | +300.183140 m |

Category action totals:

| Category | `memory_guided` | `frontier_only` | `naive_count` |
|---|---:|---:|---:|
| `bed` | 88 | 88 | 188 |
| `chair` | 509 | 710 | 880 |
| `plant` | 341 | 404 | 1094 |
| `sofa` | 365 | 936 | 534 |
| `toilet` | 488 | 618 | 1086 |
| `tv_monitor` | 227 | 316 | 362 |

Stale evidence behavior:

| Category | Old memory evidence | Fallback evidence | Repaired memory evidence |
|---|---|---|---|
| `bed` | stale `non_confirmation` | positive | positive on repeat 1 |
| `chair` | stale `non_confirmation` | positive | positive on repeat 1 |
| `plant` | stale `non_confirmation` | positive | positive on repeat 1 |
| `sofa` | stale `non_confirmation` | positive | positive on repeat 1 |
| `toilet` | stale `non_confirmation` | positive | positive on repeat 1 |
| `tv_monitor` | stale `non_confirmation` | positive | positive on repeat 1 |

The key fairness check passed: stale old memory is reported as
`non_confirmation/shared_gate_success=false`; rediscovered fallback candidates
are Grounding-DINO positive; `memory_guided` can reuse the repaired anchor on
repeat 1; `naive_count` remains positive-only and receives no repair state.

## Smaller Smoke Runs

These were used as debugging/sanity steps:

| Run | Result |
|---|---|
| `grounding_dino_candidate_gate_bed_smoke_v1` | Stable bed single group: `memory_guided=44`, `naive_count=44`, `frontier_only=46`; detector positive. |
| `grounding_dino_candidate_gate_bed_stale_repeats2_v1` | Exposed a reporting bug: stale old memory still showed detector-positive evidence while trust was blocked by `matching_reason`. |
| `grounding_dino_candidate_gate_bed_stale_repeats2_v2` | After fix: old memory `non_confirmation`, fallback positive, `memory_guided=90`, `frontier_only=92`, `naive_count=324`. |
| `grounding_dino_candidate_gate_3cat_stale_repeats2_v1` | `bed,sofa,toilet`: `memory_guided=1020`, `frontier_only=1298`, `naive_count=2214`; all fallback gates positive. |

## Result

The detector-backed option-level smoke is now working. The strongest current
Grounding-DINO result is:

- stable: `memory_guided` ties `naive_count` and beats `frontier_only`;
- repeated stale: `memory_guided` beats both `frontier_only` and `naive_count`;
- all six ObjectNav categories in the selected balanced run produced positive
  fallback detector gates at `1280x720`;
- stale old-memory evidence is explicit `non_confirmation`, not a hidden oracle
  label.

This is a real improvement over the previous oracle/action smoke because the
memory and fallback decisions now depend on real Grounding-DINO candidate
evidence.

## Limitations

- This is still option-level: Grounding-DINO verifies selected memory/fallback
  candidate views, not every action step.
- Frontier remains a deterministic search proxy, not occupancy/frontier
  exploration.
- `stale_proxy` is protocol-level stale simulation, not natural object
  relocation or removal in Habitat.
- The selected six groups are useful smoke coverage but not enough for paper
  statistics.
- `memory_valid_prior=0.5` is hand-set; a paper system should estimate it from
  evidence, uncertainty, object class, and session age.
- The stable run shows no advantage over `naive_count`; this is expected and
  should be reported honestly.

## Follow-Up

1. Add a true occupancy/frontier baseline that actually explores in Habitat.
2. Move Grounding-DINO from candidate-view verification to per-action
   observation/stopping decisions.
3. Replace `stale_proxy` with natural object hide/move/relocation experiments.
4. Scale beyond six groups and report uncertainty over scenes/categories.
5. Learn or estimate memory validity instead of using a fixed
   `memory_valid_prior`.
6. Start preparing an official ObjectNav/SPL-compatible wrapper only after the
   above pieces are no longer proxy evaluations.
