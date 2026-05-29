# Experiment Report: Habitat Navmesh Grounding-DINO Stale Detector-Pixels Smoke

Date: 2026-05-29  
Owner: Codex  
Status: Completed smoke, not paper-ready

## Question

After removing oracle-pixel leakage from detector-backed reliability, does
`stale_proxy` still suppress old stale memories and only restore high
reliability after a detector-positive repaired anchor is found?

This is a negative/control smoke for the strong-positive reliability floor. It
is still option-level, uses a synthetic stale-proxy challenge, and does not
replace natural object relocation or per-action detector perception.

## Hypothesis

- Repeat `0` stale old memories should have `shared_gate_success=false`,
  `current_evidence=0.15`, `memory_valid_prior=0.225`, and no
  `strong_current_evidence_floor`, even if their stored oracle/detector pixel
  counters are large.
- Repeat `1` repaired memories may return to `0.96` only when the repaired
  memory view has detector-positive evidence.
- `memory_guided` should keep zero hindsight regret on this smoke.

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
| Challenge | `stale_proxy` |
| Query repeats | `2` |
| Reliability mode | `evidence` |
| Memory valid prior fallback | `0.5` |
| Probe budget | `frontier_probe_count=5`, `frontier_probe_heading_count=4` |

## Command

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
rm -rf runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_stale_evidence_detector_pixels_v2
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_stale_evidence_detector_pixels_v2 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 6 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stale_proxy \
  --query-repeats 2 \
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

## Metrics

Run artifact:
`runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_stale_evidence_detector_pixels_v2`

| Policy | Episodes | Success | Actions | Distance | Memory reuse | Frontier selections | Hindsight action regret |
|---|---:|---:|---:|---:|---:|---:|---:|
| `memory_guided` | 12 | 12/12 | 1334 | 198.295274 m | 3 | 9 | 0 |
| `naive_count` | 12 | 10/12 | 1962 | 280.903082 m | 0 | 10 | 562 |
| `frontier_only` | 12 | 10/12 | 2038 | 295.107986 m | 0 | 12 | 626 |

Comparison fields:

| Comparison | Action delta | Distance delta |
|---|---:|---:|
| `memory_guided` vs `frontier_only` | 704 | 96.812712 m |
| `memory_guided` vs `naive_count` | 628 | 82.607808 m |

Memory-guided buckets:

| Bucket | Count |
|---|---:|
| `frontier_shorter_selected` | 8 |
| `memory_missed_then_frontier_repaired` | 1 |
| `memory_rescued_frontier_failure` | 1 |
| `memory_shorter_reused` | 2 |

Repeat-0 stale old-memory audit:

| Category | Selected | Actions | Bucket | Prior | Current evidence | Reason |
|---|---|---:|---|---:|---:|---|
| `chair` | `frontier` | 115 | `frontier_shorter_selected` | 0.225 | 0.15 | `matching_no_current_observation` |
| `plant` | `memory, frontier` | 169 | `memory_missed_then_frontier_repaired` | 0.225 | 0.15 | `matching_no_current_observation` |
| `sofa` | `frontier` | 104 | `frontier_shorter_selected` | 0.225 | 0.15 | `matching_no_current_observation` |
| `toilet` | `frontier` | 185 | `frontier_shorter_selected` | 0.225 | 0.15 | `matching_no_current_observation` |
| `bed` | `frontier` | 77 | `frontier_shorter_selected` | 0.225 | 0.15 | `matching_no_current_observation` |
| `tv_monitor` | `frontier` | 56 | `frontier_shorter_selected` | 0.225 | 0.15 | `matching_no_current_observation` |

Repeat-1 repaired-memory audit:

| Category | Selected | Actions | Bucket | Prior | Detector pixels | Current evidence |
|---|---|---:|---|---:|---:|---:|
| `chair` | `frontier` | 115 | `frontier_shorter_selected` | 0.96 | 4646 | 0.98 |
| `plant` | `memory` | 135 | `memory_rescued_frontier_failure` | 0.96 | 10046 | 0.98 |
| `sofa` | `frontier` | 104 | `frontier_shorter_selected` | 0.96 | 217269 | 0.98 |
| `toilet` | `frontier` | 185 | `frontier_shorter_selected` | 0.225 | 114453 old stale view, no repaired gate | 0.15 |
| `bed` | `memory` | 54 | `memory_shorter_reused` | 0.96 | 354618 | 0.98 |
| `tv_monitor` | `memory` | 35 | `memory_shorter_reused` | 0.96 | 15912 | 0.98 |

## Observations

- The strong-positive floor did not fire for repeat-0 stale old memories. Even
  rows with large stored detector/oracle pixel counters were forced to
  `shared_gate_success=false`, `current_evidence=0.15`, and prior `0.225`.
- Repaired memories regained high reliability only when the repaired memory
  view was detector-positive. `toilet` did not get repaired memory evidence and
  stayed at prior `0.225` on repeat 1.
- `memory_guided` kept zero hindsight action regret on this synthetic stale
  proxy smoke.
- `naive_count` and `frontier_only` both failed 2 of 12 episodes under this
  navmesh-probe detector setup. This should be treated as a stress/debug signal,
  not as benchmark evidence.

## Result

The detector-pixel reliability fix preserved the desired stale behavior:
negative stale evidence stays weak, and high reliability returns only after a
detector-positive repaired anchor. This reduces the risk that the
strong-positive floor hides stale or harmful memories.

The result is still not paper-ready because staleness is synthetic, frontier is
a navmesh-probe approximation, and detector evidence is evaluated at selected
candidate views rather than every action step.

## Follow-up

- Add unit tests for stale detector-backed reliability traces if this path
  changes again.
- Replace synthetic stale-proxy with object hide/move scenarios.
- Move detector evidence into per-action observations and stopping decisions.
- Evaluate held-out scenes and a real occupancy/frontier baseline before
  reporting paper-style metrics.
