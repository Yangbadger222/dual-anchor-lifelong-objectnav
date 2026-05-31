# Experiment Report: Official Active-Phase Feature Utility Comparison

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Do active-viewpoint phase features make the repeat-first action-utility model
beat simple constant-action baselines under held-out source-family validation?

## Hypothesis

Numeric phase-rank and phase-flag features should help the utility model
separate orient/scan-at-viewpoint states from active-frontier movement states.
If the earlier failure was mainly feature poverty, the tuned model should beat
always-left on leave-one-source validation and should not simply overfit the
single phase-diverse source trace.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror `badger-linux` |
| Dataset / bag / map | HM3D ObjectNav `val_mini`; active original, rotation, path, scan 4-episode traces plus 20-episode active-perception trace |
| Simulator / robot | Habitat-Lab in conda env `habitat` |
| Key parameters | `active_phase_path`, `max_states_per_category=8`, `max_states_per_category_episode=2`, actions `turn_left,turn_right,move_forward`, follow-up `repeat_first_action`, horizon `5`, detector `yolo_world` |

## Command

The 20-episode feature-bearing artifact was regenerated first:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

OUT=runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_max8cat_max2episode_yolo_20260531_v1

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json \
  --output "$OUT/dataset.json" \
  --csv-output "$OUT/rollouts.csv" \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor \
  --branch-actions turn_left,turn_right,move_forward \
  --branch-followup-policy repeat_first_action \
  --rollout-horizon-steps 5 \
  --max-states-per-category 8 \
  --max-states-per-category-episode 2 \
  --state-sampling active_phase_path

python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
  "$OUT/dataset.json" \
  --output "$OUT/report.json" \
  --csv-output "$OUT/states.csv"

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  "$OUT/report.json" \
  --output "$OUT/hard_states.json" \
  --csv-output "$OUT/hard_states.csv"
```

Then bounded phase-feature datasets were generated for the 4-episode original,
rotation, path, and scan traces with the same flags. Those four datasets and
the 20-episode dataset were combined into:

```bash
python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_active_original_max8cat_max2episode_yolo_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_active_rotation_max8cat_max2episode_yolo_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_active_path_max8cat_max2episode_yolo_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_active_scan_max8cat_max2episode_yolo_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_max8cat_max2episode_yolo_20260531_v1/dataset.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_report_all_sources_yolo_20260531_v1/report.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_report_all_sources_yolo_20260531_v1/states.csv

python -m objectnav_core.cli.train_habitat_official_candidate_rollout_action_utility_model \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_report_all_sources_yolo_20260531_v1/report.json \
  --output runs/habitat_official_objectnav/action_utility_model_repeat_first_phase_path_features_all_sources_yolo_20260531_v1/tuned_model.json \
  --scores-output runs/habitat_official_objectnav/action_utility_model_repeat_first_phase_path_features_all_sources_yolo_20260531_v1/tuned_scores.json \
  --leave-one-source-output runs/habitat_official_objectnav/action_utility_model_repeat_first_phase_path_features_all_sources_yolo_20260531_v1/tuned_leave_one_source.json \
  --epochs 2000 \
  --learning-rate 0.005 \
  --l2 0.1
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| 20-episode feature dataset | `24` states, `72` rollouts, `21` positives, `0` invalid | Feature-bearing replacement for the earlier phase-diverse probe |
| Multi-source report | `5` datasets, `31` current-hidden states, `93` action rows | Skipped `3` current-visible states |
| Phase feature presence | `31/31` states for all 6 phase fields | JSON and CSV schema path verified |
| Oracle recovered | `22/31` states | `9` states had no positive action |
| Always-left baseline | `12/31` fastest, `15/31` success, regret `0.154301` | Constant action |
| Always-right baseline | `13/31` fastest, `14/31` success, regret `0.132796` | Best constant-action regret |
| Default model full score | `7/31` fastest, `7/31` success, regret `0.206452` | Collapsed to `move_forward` |
| Default model leave-one-source | `7/31` fastest, `7/31` success, regret `0.206451` | Not useful |
| Tuned model full score | `19/31` fastest, `20/31` success, regret `0.030645` | Strong in-sample fit |
| Tuned model leave-one-source | `17/31` fastest, `17/31` success, regret `0.135484` | Beats always-left, but not robust |
| Tuned model on 20-episode holdout | `9/23` fastest, `9/23` success, regret `0.182609` | Worse regret than always-right on the same holdout |
| Always-right on 20-episode source | `9/23` fastest, `10/23` success, regret `0.131884` | Constant-action comparator |
| Hard states | `10/31` always-left-not-fastest | Split across `bed 1`, `chair 3`, `sofa 2`, `tv_monitor 4` |

## Observations

- The phase feature fields are now real artifact fields, not only unit-test
  scaffolding:
  `memory_active_perception_phase_rank`,
  `memory_active_perception_orient_anchor`,
  `memory_active_perception_scan_anchor`,
  `memory_active_perception_frontier`,
  `memory_active_perception_at_viewpoint`, and
  `memory_active_perception_scan_steps_remaining`.
- The 20-episode feature-bearing matrix reproduced the earlier phase-diverse
  hard-state structure: `23` current-hidden states, `14` oracle-recovered, and
  `8` strict always-left failures.
- The 4-episode phase-diverse exports were very small after current-visible
  filtering: only `2` held-out states per source. Their perfect tuned-model
  holdout scores are therefore not strong evidence.
- The largest held-out source, the 20-episode trace, remains difficult. The
  tuned model improved over always-left on fastest count but had worse success
  and regret than always-right.

## Result

Active-phase features are useful plumbing and diagnostics, but they do not yet
produce a robust learned action policy. The tuned model can fit the multi-source
phase-feature report and beats always-left in aggregate leave-one-source
metrics, but the evidence is not strong enough for online integration because
the largest holdout loses to a trivial always-right baseline by regret.

The bottleneck should now be treated as label/data design rather than another
small model-feature tweak.

## Follow-up

- Prototype exact state-restore or candidate-viewpoint labels so supervision is
  not tied to repeat-first primitive actions.
- Collect larger phase-diverse matrices from genuinely independent source
  traces before considering another utility-model integration.
- Keep constant-action baselines for all future utility-model reports, not just
  always-left.
