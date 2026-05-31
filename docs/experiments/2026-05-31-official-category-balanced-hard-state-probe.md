# Experiment Report: Official Category-Balanced Hard-State Probe

Date: 2026-05-31
Owner: Codex
Status: Completed diagnostic; no benchmark claim

## Question

Can a broader 20-episode detector-memory prior and a category-balanced
candidate-rollout export produce hard action-matrix states beyond the previous
all-`tv_monitor` slice?

## Hypothesis

The existing 20-episode YOLO discovery prior has anchors for multiple target
categories. Running `memory_active_perception_frontier` against that prior
should produce category-diverse active states. A per-category exporter cap
should keep the branch rollout probe tractable while avoiding the old first-N
category skew.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | HM3D ObjectNav `val_mini` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Discovery prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_20ep_80steps_20260530_v1/memory_prior.json` |
| Query policy | `memory_active_perception_frontier` |
| Rollout labels | Repeat-first action matrix, horizon `5`, actions `turn_left,turn_right,move_forward` |

## Command

Active-perception trace:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core
export HABITAT_SIM_LOG=quiet
export MAGNUM_LOG=quiet
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --output runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1 \
  --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
  --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --split val_mini \
  --policy memory_active_perception_frontier \
  --max-episodes 20 \
  --max-steps 80 \
  --seed 313 \
  --validate-habitat \
  --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_20ep_80steps_20260530_v1/memory_prior.json \
  --memory-min-confidence 0.25 \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor
```

Category-balanced branch rollout:

```bash
python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/rollouts.csv \
  --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
  --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --split val_mini \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor \
  --branch-actions turn_left,turn_right,move_forward \
  --branch-followup-policy repeat_first_action \
  --rollout-horizon-steps 5 \
  --max-states-per-category 12
```

Report and hard-state mining:

```bash
python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/dataset.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/report.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/states.csv

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/report.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/hard_states.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/hard_states.csv
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| 20-episode prior anchors | `65` | `sofa 24`, `chair 17`, `tv_monitor 16`, `bed 8` |
| Active-perception trace steps | `1600` | 20 episodes x 80 steps |
| Active trace official success/SPL | `0/20`, SPL `0.0` | Negative policy result; not benchmark progress |
| Active trace SoftSPL | `0.02824322412933835` | Official Habitat metric |
| Active candidate states | `805` | `chair 477`, `bed 238`, `tv_monitor 85`, `sofa 5` |
| Category-balanced rollout dataset | `41` states, `123` rollouts | Per-category cap `12`; `0` invalid |
| Dataset categories | `chair 12`, `bed 12`, `tv_monitor 12`, `sofa 5` | Rollouts are 3 actions per selected state |
| Positive branch rollouts | `32/123` | Repeat-first horizon `5` |
| Current-hidden report | `40` states, `120` rollouts | One selected state was current-visible and skipped |
| Report categories | `chair 12`, `bed 12`, `tv_monitor 12`, `sofa 4` | Current-hidden states only |
| Positive actions by category | `sofa 8`, `tv_monitor 24` | `chair` and `bed` had no repeat-first recovery |
| Strict fastest actions | `turn_right 6`, `move_forward 1`, `turn_left 1` | `8` fastest-action ties; `24` unrecovered |
| Always-left-not-fastest hard states | `8/40` | `tv_monitor 5`, `sofa 3` |
| Hard-or-tie states | `15/40` | `tv_monitor 11`, `sofa 4` |

## Observations

- The new per-category cap prevented the branch rollout from collapsing to the
  earliest `chair` states and produced a tractable multi-category probe.
- This probe breaks the previous hard-state category lock: true always-left
  failures now include `sofa`, not only `tv_monitor`.
- The repeat-first label is still weak for several categories. All `chair` and
  `bed` current-hidden states were unrecovered within horizon `5`, so they
  cannot yet teach a fastest-action preference.
- The active-perception policy itself remains an official-metric negative
  result. It produced `0/20` success and should not be framed as a benchmark
  improvement.
- The exporter is slow because it creates a fresh Habitat env per branch. This
  is tolerable for capped probes but should be replaced by exact state restore
  or env reuse before large-scale dataset generation.

## Result

The category-balanced export control works and produces a more useful hard
state probe than the earlier 4-episode slice. It does not solve the learning
problem yet: the current repeat-first labels still recover only `sofa` and
`tv_monitor` in this sample, while `chair` and `bed` remain unrecovered.

The next data-design step should move beyond first-N per category toward
score/phase-aware sampling or exact candidate-viewpoint state-restore labels.

## Follow-up

- Add a sampling mode that can select candidate states by category plus
  decision phase, expected evidence, or selected-viewpoint score.
- Investigate why `chair` and `bed` active states do not recover under the
  repeat-first horizon before treating them as negatives.
- Prototype exact state-restore/candidate-viewpoint labels to avoid scan-biased
  macro-action supervision.
