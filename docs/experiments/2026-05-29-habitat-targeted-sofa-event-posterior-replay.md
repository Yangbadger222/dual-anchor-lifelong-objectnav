# Experiment Report: Targeted Sofa Event-Posterior Replay

Date: 2026-05-29  
Owner: Codex  
Status: Completed diagnostic, not benchmark evidence

## Question

Can the new explicit `selected_group_ids` replay interface create a small
Habitat slice where detector-event posterior reliability crosses a genuine
memory-vs-frontier decision boundary?

## Candidate Rationale

The broad full miner report
`runs/habitat_closed_loop_dual_anchor/decision_sensitivity_broad_existing_v4_full/report.json`
showed that existing broad slices had no counterfactual flips. The most
promising event-posterior near-boundary candidate was the `sofa` group from the
per-action balanced6 run:

- Group:
  `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|sofa|goal_object:275`
- Existing balanced6 row: mixed detector events, `reliability_delta=0.140084`,
  `decision_margin_actions=0.360168`
- Missing ingredient: the boundary was exactly at / above the upper reliability
  range, so both `evidence` and `event_posterior` chose `frontier_first`

This was therefore a useful replay-control test: if targeted selection or
frontier probe settings changed route accounting slightly, the row might move
from `frontier_requires_perfect_memory` into an interior reliability boundary.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `94abb2d` |
| Machine | Linux `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | HM3D ObjectNav `val` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Detector confirmation | `multiview`, 2 frames, 0.05 m / 5 deg / 0.05 IoU |
| Frontier | `navmesh_frontier` |
| Route observation | `per_action` |
| Reliability mode | `event_posterior` |
| Challenge | `stable` |

## Commands

Baseline selected-group replay:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_sofa_event_posterior_selected_group_v1 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 6 \
  --selected-group-ids "hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|sofa|goal_object:275" \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stable \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode event_posterior \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 5 \
  --frontier-probe-heading-count 4 \
  --route-observation-mode per_action \
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
  --detector-confirmation-mode multiview \
  --detector-confirmation-frames 2 \
  --detector-confirmation-min-translation 0.05 \
  --detector-confirmation-min-rotation-deg 5.0 \
  --detector-confirmation-min-mask-iou 0.05
```

Probe sweep used the same command with:

| Output suffix | `--frontier-probe-count` | `--frontier-probe-heading-count` |
|---|---:|---:|
| `probe3_heading4_v1` | 3 | 4 |
| `probe5_heading8_v1` | 5 | 8 |
| `probe8_heading4_v1` | 8 | 4 |
| `probe8_heading8_v1` | 8 | 8 |

Consolidated mining:

```bash
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.mine_habitat_decision_sensitivity \
  runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_sofa_event_posterior_selected_group_v1 \
  runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_sofa_event_posterior_selected_group_probe3_heading4_v1 \
  runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_sofa_event_posterior_selected_group_probe5_heading8_v1 \
  runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_sofa_event_posterior_selected_group_probe8_heading4_v1 \
  runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_sofa_event_posterior_selected_group_probe8_heading8_v1 \
  --output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_sofa_selected_group_event_posterior_sweep_v1/report.json \
  --csv-output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_sofa_selected_group_event_posterior_sweep_v1/candidates.csv
```

## Results

The explicit replay interface selected exactly one group:

| Field | Value |
|---|---|
| `selection_mode` | `explicit_group_ids` |
| `selected_group_count` | `1` |
| `selected_group_ids` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb\|sofa\|goal_object:275` |

All five targeted runs produced the same mined decision row:

| Metric | Value |
|---|---:|
| `memory_action_count` | 63 |
| `fallback_action_count` | 63 |
| `fallback_from_memory_action_count` | 2 |
| `evidence_reliability` | 0.960000 |
| `event_posterior_reliability` | 0.819916 |
| `detector_event_count` | 6 |
| `detector_event_confirmed_weight` | 7.517547 |
| `detector_event_suppressed_weight` | 2.850000 |
| `detector_event_posterior` | 0.705301 |
| `reliability_delta` | 0.140084 |
| `decision_boundary_reliability_raw` | 1.000000 |
| `decision_boundary_region` | `frontier_requires_perfect_memory` |
| `evidence_decision` | `frontier_first` |
| `event_posterior_decision` | `frontier_first` |
| `counterfactual_decision_flip` | false |

Policy aggregates for the baseline selected run were also tied:

| Policy | Success | Actions | Bucket |
|---|---:|---:|---|
| `memory_guided` | 1/1 | 63 | `frontier_shorter_selected` |
| `frontier_only` | 1/1 | 63 | `frontier_only` |
| `naive_count` | 1/1 | 63 | `naive_memory_reuse` |

The consolidated miner report found:

| Metric | Value |
|---|---:|
| summaries mined | 5 |
| candidates | 5 |
| `frontier_requires_perfect_memory` | 5 |
| `counterfactual_flip_count` | 0 |

## Interpretation

The new replay interface works: the runner selected the exact mined group and
preserved it in `episode_selection`.

The experiment also produced the desired detector-event signal: mixed confirmed
and suppressed event weights lowered reliability from `0.96` to `0.819916`.

However, the decision boundary remained non-flippable. Because memory and
frontier both cost `63` actions and the post-memory fallback costs only `2`
actions, the boundary sits at exactly `1.0`. Any reliability below perfect
memory validity chooses `frontier_first`, so neither `evidence` nor
`event_posterior` can change the policy decision.

## Conclusion

This is a useful negative diagnostic. The bottleneck is now sharper:

- exact group replay is available and verified;
- detector-event posterior can move reliability on the targeted row;
- but route accounting still does not place that reliability change inside an
  interior decision boundary.

The next selector should rank candidates by the distance between the
reliability interval and the decision boundary, not only by action margin,
mixed detector events, or boundary region.
