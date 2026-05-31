# Experiment Report: Official Phase-Diverse Hard-State Probe

Date: 2026-05-31
Owner: Codex
Status: Completed diagnostic; no benchmark claim

## Question

Can phase/path-aware state sampling with per-category-per-episode diversity
recover useful `chair` and `bed` repeat-first action labels that score-aware
sampling missed?

## Hypothesis

The previous score-aware sampler selected high-score states, but trace-supervised
view-candidate labels showed rare `chair` and `bed` recoveries in low-score
at-viewpoint `orient_anchor` states. Prioritizing active-viewpoint phases and
limiting repeated states from the same category/episode should surface those
states in the action-matrix rollout probe.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | HM3D ObjectNav `val_mini` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Source trace | `runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1` |
| Rollout labels | Repeat-first action matrix, horizon `5`, actions `turn_left,turn_right,move_forward` |
| State sampling | `active_phase_path`, cap `8` states per category, cap `2` states per category/episode |

## Command

Trace-supervised view-candidate and view-recall exports:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

TRACE=runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1
VC_OUT=runs/habitat_official_objectnav/view_candidate_dataset_active_perception_yolo_20ep_80steps_20260531_v1
VR_OUT=runs/habitat_official_objectnav/view_recall_dataset_active_perception_yolo_20ep_80steps_20260531_v1

python -m objectnav_core.cli.export_habitat_official_view_candidate_dataset \
  "$TRACE/policy_trace.json" \
  --detector-trace "$TRACE/detector_trace.json" \
  --output "$VC_OUT/dataset.json" \
  --csv-output "$VC_OUT/candidates.csv" \
  --source-run-id memory_active_perception_frontier_yolo_20ep_80steps_20260531_v1 \
  --horizon-steps 5

python -m objectnav_core.cli.export_habitat_official_view_recall_dataset \
  "$TRACE/policy_trace.json" \
  --detector-trace "$TRACE/detector_trace.json" \
  --output "$VR_OUT/dataset.json" \
  --csv-output "$VR_OUT/examples.csv" \
  --source-run-id memory_active_perception_frontier_yolo_20ep_80steps_20260531_v1 \
  --horizon-steps 5
```

Phase-diverse branch rollout:

```bash
OUT=runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_max8cat_max2episode_yolo_20260531_v1
mkdir -p "$OUT"

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  "$TRACE/policy_trace.json" \
  --output "$OUT/dataset.json" \
  --csv-output "$OUT/rollouts.csv" \
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

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  "$OUT/report.json" \
  --output "$OUT/hard_or_tie_states.json" \
  --csv-output "$OUT/hard_or_tie_states.csv" \
  --include-baseline-ties
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Trace selected active candidates | `879` | `chair 477`, `bed 238`, `tv_monitor 159`, `sofa 5` |
| Trace selected-candidate positives | `10/879` | `sofa 4`, `chair 4`, `tv_monitor 1`, `bed 1` |
| Trace positive decisions | `orient_anchor 6`, active-frontier turn `4` | All selected-candidate positives were orient/turn, none scan |
| Phase-diverse rollout dataset | `24` states, `72` rollouts | `21` positives, `0` invalid |
| Selected dataset categories | `chair 8`, `bed 7`, `tv_monitor 5`, `sofa 4` | Per-episode cap prevented single-episode collapse |
| Positive branch rollouts | `tv_monitor 7`, `sofa 6`, `bed 4`, `chair 4` | First repeat-first probe with all four categories positive |
| Current-hidden report | `23` states, `69` action rows | One selected state was current-visible and skipped |
| Oracle-recovered states | `14/23` | `tv_monitor 5`, `chair 4`, `sofa 3`, `bed 2` |
| Strict fastest actions | `turn_right 6`, `turn_left 3`, `move_forward 2` | Plus `3` fastest-action ties |
| Always-left-not-fastest hard states | `8/23` | `chair 3`, `sofa 2`, `tv_monitor 2`, `bed 1` |
| Hard-or-tie states | `11/23` | `chair 3`, `sofa 3`, `tv_monitor 3`, `bed 2` |

## Observations

- The trace-supervised view-candidate export explained why `top_score_desc`
  failed: the rare `chair`/`bed` positives are low-score at-viewpoint states,
  not high-score active-frontier states.
- The new per-category-per-episode cap mattered. Without it, phase/path sorting
  still over-selected repeated states from a single `bed` episode and missed the
  rare positive `bed` episode.
- Phase/path-diverse sampling is the first repeat-first probe in this series
  that produces recovered and hard states for all represented categories.
- This does not make the online policy good. The source 20-episode active run
  still has official success `0/20`; this result only says the offline label
  collector can now expose a less biased supervision slice.

## Result

Phase/path-aware sampling plus per-category-per-episode diversity is a useful
diagnostic improvement. It shows that `chair` and `bed` were not intrinsically
unrecoverable in the trace; prior samplers were choosing the wrong states. The
next label-design step should use this sampler as a bridge, then move to exact
state-restore or candidate-viewpoint labels so supervision is not tied to
repeat-first primitive actions.

## Follow-up

- Add active-viewpoint phase features to the action-matrix state feature schema
  before training another utility model.
- Run a held-out utility-model comparison only after collecting more
  phase-diverse action matrices from multiple source traces.
- Prototype exact state-restore/candidate-viewpoint labels to test target
  visibility from the selected viewpoint directly.
