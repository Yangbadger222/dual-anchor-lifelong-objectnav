# Experiment Report: Habitat Navmesh Grounding-DINO Evidence Calibration Smoke

Date: 2026-05-29  
Owner: Codex  
Status: Completed smoke, not paper-ready

## Question

Does the strong-positive reliability calibration still behave correctly when
the current memory/fallback candidate evidence comes from Grounding-DINO instead
of oracle semantic visibility?

This is a candidate-view detector smoke. It still does not run Grounding-DINO at
every action step, does not build an occupancy frontier, and is not an official
ObjectNav benchmark.

## Hypothesis

If Grounding-DINO produces positive shared-gate evidence at the selected memory
and frontier candidate views, the calibrated policy should preserve the oracle
audit pattern:

- `sofa` should select the shorter valid memory;
- `plant` should select the shorter navmesh frontier;
- `memory_guided` should have zero hindsight action regret;
- any gain over `naive_count` should be reported as a smoke result, not a
  robust benchmark claim.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `ffcfd41` |
| Machine | Linux `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset / map | HM3D ObjectNav `val`, HM3D v0.2 scene root |
| Simulator | Habitat-Sim GreedyGeodesic option routes |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Detector thresholds | `detector_conf=0.25`, `grounding_dino_text_threshold=0.25` |
| Image cap | `grounding_dino_max_image_side=384` |
| Frontier | `navmesh_frontier` probes with fixed heading scan |
| Sensor resolution | `1280x720` |
| Noise | `clean`, with configured RGB/depth noise profiles |
| Challenge | `stable` |
| Reliability mode | `evidence` |
| Memory valid prior fallback | `0.5` |
| Probe budget | `frontier_probe_count=5`, `frontier_probe_heading_count=4` |

## Command

Focused Linux tests:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
git pull --ff-only origin codex/habitat-memory-lifecycle
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
```

Grounding-DINO balanced6 calibration smoke:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
rm -rf runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_evidence_detector_pixels_v2
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_evidence_detector_pixels_v2 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 6 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stable \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode evidence \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 5 \
  --frontier-probe-heading-count 4 \
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
  --detector-prompt-mode target
```

## Selected Episodes

Candidate episode count was `652`; selected group count was `6`, matching the
oracle calibration smoke.

| Category | Group |
|---|---|
| `chair` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|chair|goal_object:445` |
| `plant` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|plant|goal_object:183` |
| `sofa` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|sofa|goal_object:275` |
| `toilet` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|toilet|goal_object:51` |
| `bed` | `hm3d/val/00802-wcojb4TFT35/wcojb4TFT35.basis.glb|bed|goal_object:17` |
| `tv_monitor` | `hm3d/val/00813-svBbv1Pavdk/svBbv1Pavdk.basis.glb|tv_monitor|goal_object:287` |

## Metrics

Run artifact:
`runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_evidence_detector_pixels_v2`

| Policy | Episodes | Success | Actions | Distance | Memory reuse | Frontier selections | Hindsight action regret |
|---|---:|---:|---:|---:|---:|---:|---:|
| `memory_guided` | 6 | 6/6 | 564 | 83.772278 m | 5 | 1 | 0 |
| `naive_count` | 6 | 6/6 | 575 | 86.391888 m | 6 | 0 | 11 |
| `frontier_only` | 6 | 5/6 | 946 | 135.483215 m | 0 | 6 | 92 |

Comparison fields:

| Comparison | Action delta | Distance delta |
|---|---:|---:|
| `memory_guided` vs `frontier_only` | 382 | 51.710937 m |
| `memory_guided` vs `naive_count` | 11 | 2.619610 m |

Memory-guided buckets:

| Bucket | Count |
|---|---:|
| `memory_shorter_reused` | 4 |
| `memory_rescued_frontier_failure` | 1 |
| `frontier_shorter_selected` | 1 |

Memory-guided detector row audit:

| Category | Selected | Actions | Bucket | Detector pixels memory / fallback | Oracle pixels memory / fallback | Regret |
|---|---|---:|---|---:|---:|---:|
| `chair` | `memory` | 69 | `memory_shorter_reused` | 122265 / 13258 | 234649 / 8450 | 0 |
| `plant` | `frontier` | 128 | `frontier_shorter_selected` | 344250 / 2067 | 74268 / 1931 | 0 |
| `sofa` | `memory` | 98 | `memory_shorter_reused` | 438747 / 302670 | 411114 / 249914 | 0 |
| `toilet` | `memory` | 179 | `memory_rescued_frontier_failure` | 114453 / 0 | 72441 / 0 | 0 |
| `bed` | `memory` | 44 | `memory_shorter_reused` | 462080 / 61530 | 385005 / 5335 | 0 |
| `tv_monitor` | `memory` | 46 | `memory_shorter_reused` | 643314 / 21120 | 608274 / 16819 | 0 |

All memory-guided memory candidates had `shared_gate_success=true`. The
`toilet` navmesh fallback remained gate-negative, which is why the memory route
is bucketed as `memory_rescued_frontier_failure`.

## Observations

- The detector-backed candidate-view smoke preserved the targeted behavior:
  `sofa` reused memory and `plant` selected frontier.
- `memory_guided` hindsight action regret stayed at `0`.
- This v2 run happened after fixing the reliability helper so detector-backed
  current evidence uses `detector_pixels`, not `max(detector_pixels,
  oracle_target_pixels)`. All selected memory detections in this smoke were
  themselves above the strong-evidence pixel threshold, so aggregate metrics did
  not change from the earlier candidate-view run.
- `memory_guided` used 564 actions, compared with 561 in the oracle calibration
  smoke. The 3-action difference comes from detector-backed navmesh candidate
  accounting in this option-level runner.
- The same strong-positive floor fired on every memory-guided row, because
  selected memory views all had strong current detector evidence. This is
  expected for the candidate-view smoke, but it does not validate behavior under
  weak detections, stale memories, or per-action detector noise.
- A transformers `FutureWarning` was emitted about `labels` changing behavior in
  a future Grounding-DINO processor version. It did not stop the run, but should
  be tracked before dependency upgrades.

## Result

The calibration is still consistent when selected candidate-view evidence comes
from Grounding-DINO instead of oracle visibility. This strengthens the plumbing
story, but it remains a small detector candidate-view smoke with a small
11-action advantage over `naive_count`.

Do not present this as a benchmark claim. The useful next step is to move the
evidence source into per-action observations and test cases where detector
evidence is weak, stale, or ambiguous.

## Follow-up

- Add weak-evidence and stale-memory Grounding-DINO calibration cases.
- Move memory reliability evidence from selected candidate views to per-action
  detector observations.
- Replace or fit the strong-positive floor with held-out calibration data.
- Add a real occupancy/frontier baseline before reporting paper-style metrics.
