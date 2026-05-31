# Experiment Report: Official Candidate Rollout Labeling

Date: 2026-05-30
Owner: Codex
Status: Local and Linux smokes complete; action-matrix controls complete; repeat-first follow-up and hard-state mining validated

## Question

Can active-perception candidate sets be relabeled with real short-horizon
counterfactual detector outcomes by replaying the logged episode prefix and
branching each candidate from the same decision state?

## Hypothesis

Replay-based branch rollouts can fill the missing supervision from the
view-candidate dataset without treating unselected logged candidates as
negative examples. A fake-env smoke should prove the replay/branch boundary
before any expensive Habitat run.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Local macOS plus Linux mirror `badger@100.88.131.52` |
| Dataset / bag / map | Synthetic fake-env trace; active original, rotation-aware, path-aware, and viewpoint-scan YOLO official traces |
| Simulator / robot | Fake ObjectNav env locally; Habitat-Lab in Linux conda env `habitat` |
| Key parameters | Candidate smokes `5x3x5` and `10x3x5`; action matrix all active states with `turn_left,turn_right,move_forward` at horizons `5` and `1`; follow-up policies `left_scan` and `repeat_first_action` |

## Command

Local verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_recall_model.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py

git diff --check
```

Linux verification and smoke exports:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_recall_model.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/policy_trace.json \
  --output runs/habitat_official_objectnav/candidate_rollout_dataset_active_original_yolo_5states3cand_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/candidate_rollout_dataset_active_original_yolo_5states3cand_20260530_v1/rollouts.csv \
  --detector yolo_world \
  --max-states 5 \
  --candidates-per-state 3 \
  --rollout-horizon-steps 5

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/memory_active_perception_frontier_viewpoint_scan_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/policy_trace.json \
  --output runs/habitat_official_objectnav/candidate_rollout_dataset_active_scan_yolo_10states3cand_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/candidate_rollout_dataset_active_scan_yolo_10states3cand_20260530_v1/rollouts.csv \
  --detector yolo_world \
  --max-states 10 \
  --candidates-per-state 3 \
  --rollout-horizon-steps 5
```

Linux action-matrix controls:

```bash
# Run for active original, rotation-aware, path-aware, and viewpoint-scan traces.
# Horizon 5 measures short-horizon recovery after the forced first action and
# diagnostic follow-up controller.
python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/<trace>/policy_trace.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_<variant>_yolo_allstates_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_<variant>_yolo_allstates_20260530_v1/rollouts.csv \
  --detector yolo_world \
  --branch-actions turn_left,turn_right,move_forward \
  --candidates-per-state 3 \
  --rollout-horizon-steps 5

# Horizon 1 is the immediate first-action control.
python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/<trace>/policy_trace.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_h1_<variant>_yolo_allstates_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_h1_<variant>_yolo_allstates_20260530_v1/rollouts.csv \
  --detector yolo_world \
  --branch-actions turn_left,turn_right,move_forward \
  --candidates-per-state 3 \
  --rollout-horizon-steps 1

# Repeat-first follow-up repeats the explicit branch action for the whole
# horizon, producing symmetric macro-action labels.
python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/<trace>/policy_trace.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_<variant>_yolo_allstates_20260531_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_<variant>_yolo_allstates_20260531_v1/rollouts.csv \
  --detector yolo_world \
  --branch-actions turn_left,turn_right,move_forward \
  --branch-followup-policy repeat_first_action \
  --candidates-per-state 3 \
  --rollout-horizon-steps 5

# Cost-aware report over the four repeat-first datasets.
python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_active_original_yolo_allstates_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_active_rotation_yolo_allstates_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_active_path_yolo_allstates_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_active_scan_yolo_allstates_20260531_v1/dataset.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_report_all_active_yolo_20260531_v1/report.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_report_all_active_yolo_20260531_v1/states.csv

# First learned utility baseline. The step-interaction variant is the current
# best local model, but it still does not beat the simple always-left baseline.
python -m objectnav_core.cli.train_habitat_official_candidate_rollout_action_utility_model \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_report_all_active_yolo_20260531_v1/report.json \
  --output runs/habitat_official_objectnav/action_utility_model_repeat_first_all_active_step_interaction_yolo_20260531_v1/model.json \
  --scores-output runs/habitat_official_objectnav/action_utility_model_repeat_first_all_active_step_interaction_yolo_20260531_v1/scores.json \
  --leave-one-source-output runs/habitat_official_objectnav/action_utility_model_repeat_first_all_active_step_interaction_yolo_20260531_v1/leave_one_source.json \
  --epochs 1000 \
  --learning-rate 0.2 \
  --l2 0.001

# Primary hard-state slice: states where always-left is absent from the
# fastest-action set.
python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_state_features_report_all_active_yolo_20260531_v1/report.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_hard_states_all_active_yolo_20260531_v1/hard_states.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_hard_states_all_active_yolo_20260531_v1/hard_states.csv

# Diagnostic slice: also include states where always-left is tied fastest.
python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_state_features_report_all_active_yolo_20260531_v1/report.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_hard_or_tie_states_all_active_yolo_20260531_v1/hard_or_tie_states.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_hard_or_tie_states_all_active_yolo_20260531_v1/hard_or_tie_states.csv \
  --include-baseline-ties
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Local rollout tests | `5 passed` | New rollout dataset behavior and CLI module guard |
| Local focused gate | `13 passed` | Rollout, candidate export, view-recall model, packaging |
| Local compileall | exit `0` | New rollout module and CLI |
| Local `git diff --check` | exit `0` | No whitespace errors |
| Linux focused gate | `13 passed` | Same focused gate in conda env `habitat` |
| Linux compileall | exit `0` | New rollout module and CLI |
| Linux `git diff --check` | exit `0` | No whitespace errors |
| Linux active-original rollout | `15/15` positive, `0` invalid | `5` states, `3` candidates/state |
| Linux active-scan rollout | `30/30` positive, `0` invalid | `10` states, `3` candidates/state |
| Horizon-5 action matrix, original | `20/75` positive, `0` invalid | `25` states |
| Horizon-5 action matrix, rotation-aware | `29/87` positive, `0` invalid | `29` states |
| Horizon-5 action matrix, path-aware | `54/105` positive, `0` invalid | `35` states |
| Horizon-5 action matrix, viewpoint scan | `69/132` positive, `0` invalid | `44` states |
| Horizon-5 action matrix, aggregate | `172/399` positive, `0` invalid | `133` states |
| Horizon-5 current-hidden aggregate | `172/309` positive | Excludes `90` already-visible rows |
| Horizon-5 current-hidden by action | `move_forward 53/103`, `turn_left 96/103`, `turn_right 23/103` | Follow-up controller scans left after the first action |
| Horizon-1 action matrix, original | `2/75` positive, `0` invalid | Immediate first-action control |
| Horizon-1 action matrix, rotation-aware | `2/87` positive, `0` invalid | Immediate first-action control |
| Horizon-1 action matrix, path-aware | `3/105` positive, `0` invalid | Immediate first-action control |
| Horizon-1 action matrix, viewpoint scan | `1/132` positive, `0` invalid | Immediate first-action control |
| Horizon-1 action matrix, aggregate | `8/399` positive, `0` invalid | Too sparse for a useful scorer |
| Horizon-1 current-hidden aggregate | `8/309` positive | Excludes `90` already-visible rows |
| Repeat-first local focused gate | `15 passed` | Rollout, candidate export, view-recall model, packaging |
| Repeat-first Linux rollout tests | `6 passed` | Focused rollout tests in conda env `habitat` |
| Repeat-first action matrix, original | `13/75` positive, `0` invalid | `25` states |
| Repeat-first action matrix, rotation-aware | `29/87` positive, `0` invalid | `29` states |
| Repeat-first action matrix, path-aware | `51/105` positive, `0` invalid | `35` states |
| Repeat-first action matrix, viewpoint scan | `108/132` positive, `0` invalid | `44` states |
| Repeat-first action matrix, aggregate | `201/399` positive, `0` invalid | `133` states |
| Repeat-first current-hidden by action | `move_forward 49/103`, `turn_left 96/103`, `turn_right 56/103` | Symmetric macro-action horizon |
| Repeat-first fastest strict actions | `turn_left 29`, `turn_right 11`, `move_forward 1` | Other `62` current-hidden states had fastest-action ties |
| Action-matrix report local gate | `17 passed` | Rollout/report, candidate export, view-recall model, packaging |
| Action-matrix report Linux gate | `9 passed` | Report and packaging tests in conda env `habitat` |
| Action-matrix report artifact | `103` states, `309` rollouts | Current-hidden repeat-first rows only |
| Utility model local gate | `21 passed` | Utility model, rollout/report, candidate export, view-recall model, packaging |
| Utility model Linux gate | `5 passed` | Utility model and packaging tests in conda env `habitat` |
| Utility model full-score | `91/103` fastest, `96/103` success, regret `0.038835` | Matches always-left baseline |
| Utility model chosen actions | `turn_left 71`, `move_forward 25`, `turn_right 7` | Step-interaction model, full report |
| Utility model leave-one-source | `84/103` fastest, `89/103` success, regret `0.052427` | Worse than always-left; not policy-ready |
| Pre-decision feature RED gate | `3` expected failures | Missing rollout `state_features`, report preservation, and model feature terms |
| Pre-decision feature unit gate | `15 passed` | Rollout/report and utility model tests |
| Pre-decision feature focused gate | `24 passed` | Rollout/report, utility model, candidate export, view-recall model, packaging |
| Pre-decision feature full local suite | `413 passed` | Full `src/objectnav_core/tests` suite |
| Pre-decision feature compileall | exit `0` | Touched rollout/report/model modules and CLIs |
| Pre-decision feature `git diff --check` | exit `0` | No whitespace errors in tracked diff |
| Pre-decision feature trailing-whitespace scan | exit `0` | Explicit scan over touched tracked/untracked files |
| Pre-decision feature Linux focused gate | `16 passed` | Rollout/report, utility model, and packaging tests in conda env `habitat` |
| Pre-decision feature Linux compileall | exit `0` | Touched rollout/report/model modules and CLIs in conda env `habitat` |
| Pre-decision feature Linux diff/whitespace checks | exit `0` | Linux `git diff --check` and explicit trailing-whitespace scan |
| State-feature one-state smoke | `3` rollouts, `2` positives, `0` invalid | Real Habitat/Yolo smoke; `state_features` present |
| State-feature action matrix, original | `13/75` positive, `0` invalid | `25` states; `state_features` present |
| State-feature action matrix, rotation-aware | `29/87` positive, `0` invalid | `29` states; `state_features` present |
| State-feature action matrix, path-aware | `51/105` positive, `0` invalid | `35` states; `state_features` present |
| State-feature action matrix, viewpoint scan | `108/132` positive, `0` invalid | `44` states; `state_features` present |
| State-feature aggregate report | `103` states, `309` rollouts | Current-hidden rows; `25` feature keys |
| Feature model default full-score | `48/103` fastest, `49/103` success, regret `0.220388` | Old hyperparameters collapse to always-`move_forward` |
| Feature model tuned full-score | `95/103` fastest, `100/103` success, regret `0.018608` | Full-report improvement only |
| Feature model tuned leave-one-source | `91/103` fastest, `96/103` success, regret `0.038835` | Ties always-`turn_left`; not policy-ready |
| Pairwise-ranking scratch full-score | `99/103` fastest, `101/103` success, regret `0.008091` | Scratch probe, not committed model |
| Pairwise-ranking scratch leave-one-source | `85/103` fastest, `87/103` success, regret `0.057443` | Worse than always-left |
| Hard-state miner local gate | `5 passed` | Miner API/CLI and packaging tests |
| Hard-state miner Linux gate | `5 passed` | Same focused tests in conda env `habitat` |
| Always-left-not-fastest slice | `12/103` states | Strict fastest counts: `turn_right 11`, `move_forward 1`; baseline succeeded in `5` |
| Always-left-not-fastest by source | original `1`, rotation `5`, path `5`, scan `1` | All `12` states are `tv_monitor` |
| Always-left hard-or-tie slice | `74/103` states | `12` not-fastest plus `62` baseline-fastest ties |

## Observations

- The fake-env smoke verifies that each candidate branch starts after replaying
  the same logged action prefix.
- Candidate labels are detector-derived and candidate-specific; the positive
  branch is not copied from the logged selected candidate.
- A CLI execution regression was caught after the first Linux attempt:
  `python -m` did nothing before adding the `__main__` guard.
- The first Habitat export revealed a replay-budget bug:
  setting env `max_steps` to the rollout horizon caused later branch states to
  end during replay. The exporter now budgets for the trace prefix plus rollout
  horizon.
- Both Linux smokes are operational and produce valid rows, but they are
  all-positive. This makes them useful for pipeline validation, not for training
  a discriminative candidate ranker.
- The horizon-5 action matrix broke the all-positive pattern across full active
  traces, but it mostly measures delayed short-horizon recovery. In the
  current-hidden subset, `turn_left` recovered `96/103` branches, and a
  leave-one-trace action-rate baseline that always chooses `turn_left` was
  nearly oracle at the state level.
- The horizon-1 control collapsed to only `8/399` positives overall
  (`8/309` current-hidden rows). This shows that most horizon-5 positives were
  not immediate first-action effects; they appeared after the diagnostic
  follow-up scan.
- Some original and rotation-aware branch states were already target-visible:
  `90/399` action-matrix rows had `current_target_visible=true`. Those rows are
  not hidden-to-visible recovery examples and should be filtered for recovery
  training.
- `repeat_first_action` removes the hidden left-scan continuation from
  explicit action branches. It increases current-hidden `turn_right` recovery
  from `23/103` under `left_scan` to `56/103`, while keeping `0` invalid rows.
- Binary recovery is still too easy for a global `turn_left` baseline:
  `turn_left` recovers `96/103` current-hidden repeat-first branches. However,
  time-to-visible is richer. Among current-hidden states, `turn_right` is the
  strictly fastest action in `11` states, `turn_left` in `29`, and
  `move_forward` in `1`, with `62` fastest-action ties.
- The report artifact
  `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_report_all_active_yolo_20260531_v1/report.json`
  groups repeat-first rows back into `103` current-hidden replay states and
  stores per-action success plus fastest/time-to-visible labels.
- Local feature plumbing now carries a `state_features` object from rollout rows
  into action-matrix report states. The payload is extracted before branch
  actions from policy-trace pose/memory-prior fields and the replayed
  pre-branch depth observation, so it does not include branch outcomes.
- The regenerated full repeat-first datasets preserve the previous rollout
  counts while adding `state_features`: `399` rollouts, `201` positives, and
  `0` invalid. The aggregate report has the same current-hidden structure as
  before (`103` states, `309` action rows), now with `25` feature keys.
- The tuned feature-aware linear model improves the full-report score over the
  old step-interaction baseline, but leave-one-source validation only ties the
  always-left baseline. This means the apparent improvement is not yet evidence
  of source-invariant local control.
- A scratch pairwise-ranking objective made the full-report fit even stronger
  but generalized worse than always-left, which points toward data/label
  limitations rather than just the regression loss.
- The hard-state miner found only `12/103` states where always-`turn_left` is
  absent from the fastest-action set. All `12` are `tv_monitor`, with source
  split original `1`, rotation-aware `5`, path-aware `5`, and viewpoint-scan
  `1`. This is a stronger warning that the current active traces are
  category/source skewed, not a balanced hard dataset.
- Including baseline ties expands the diagnostic slice to `74/103` states, but
  `62` of those still allow always-left as a fastest action. Those states are
  useful for ambiguity analysis, not for proving a learned controller beats the
  always-left baseline.

## Result

The replay/branch implementation works locally and in Habitat. Action-matrix
mode creates real intervention evidence and valid negative labels, but the
current horizon-5 controller is best interpreted as short-horizon recovery
supervision, not immediate first-action supervision. The stricter horizon-1
control is too sparse for training a useful first-action scorer.

No candidate ranker or online policy should be trained from these labels yet.
The next algorithmic step should change the rollout semantics, not fit a model
to the current bias.

The `repeat_first_action` follow-up is the first usable macro-action
intervention setting. It is still not enough for an online claim by itself, but
it suggests the next supervised target should be cost-aware time-to-visible or
fastest-action ranking rather than binary recovery.

The first learned linear utility model is an honest negative baseline. It can
represent action-decision and action-step interactions and diversifies choices
on the training report, but its full-report metrics match the simple
always-`turn_left` baseline and its leave-one-source metrics are worse. This
means the current features/model are not sufficient for an online active-memory
policy claim.

The real Habitat feature-bearing artifacts are now regenerated and evaluated.
The result remains negative for policy integration: full-report improvements do
not survive leave-one-source validation. This is useful evidence for the paper
direction, because it shows that the current four active traces and
repeat-first macro-action labels are still too source-skewed for a credible
learned active-memory controller.

Hard-state mining makes the next data gap concrete: the current true
always-left-failure slice has only `12` states and no category diversity. The
right next step is broader hard-state collection or label redesign, not another
model fit on this slice.

## Follow-up

- Separate three label types explicitly: immediate first-action effect
  (`horizon=1`), short-horizon recovery (`horizon>1`), and exact candidate
  viewpoint utility.
- Treat the current feature-aware utility model as an offline negative result,
  not an online policy.
- Use the hard-state miner output to drive broader collection: the next
  counterfactual rollout set needs categories beyond `tv_monitor` and source
  families beyond the current left-dominated active traces.
- Filter current-visible branch states for hidden-to-visible training.
- Consider evaluating exact candidate viewpoint cells via simulator
  state-restore/teleport rather than scan-biased short action branches.
