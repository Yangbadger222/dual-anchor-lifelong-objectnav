# Design Doc: Official Candidate-Viewpoint Ranker

Date: 2026-05-31
Owner: Codex
Status: Implemented source-diverse offline validation

## Goal

Train and evaluate a deterministic candidate-viewpoint ranker from the new
candidate-viewpoint restore labels. The ranker should answer: among top-K
memory-policy candidate viewpoints for a restored state, which candidate should
the memory system inspect first?

## Non-Goals

- Do not claim online ObjectNav success or SPL improvement.
- Do not tune against official benchmark metrics in this slice.
- Do not use detector-derived label fields as model features.
- Do not replace the active-perception policy yet.
- Do not hide simple baselines; always compare against top-rank/top-score
  candidate selection and oracle recoverability.

## Background

The candidate-viewpoint restore smoke produced `120` candidate rows from `24`
states. It found `69` hidden-to-visible candidate rows and `15/24` states with
at least one hidden-to-visible candidate, compared with `1/24` current-view
state-restore positives. This label richness is useful only if a model or
ranking rule can choose the positive candidates under held-out evaluation.

Existing official model utilities already use deterministic logistic/linear
models with JSON artifacts, CSV score reports, and explicit baselines. The new
ranker should follow that style, but rank candidates within a state rather than
actions within a state.

## System Boundary

The change belongs to the official Habitat evaluation/model layer. It consumes
candidate-viewpoint restore datasets and emits offline model/score artifacts.
It does not touch online policy execution.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Candidate-viewpoint restore dataset | JSON | Rows from `export_official_candidate_viewpoint_restore_dataset`. |
| Input | Training options | CLI/API | Epochs, learning rate, L2, current-hidden filtering, fold count. |
| Output | Ranker model | JSON | Deterministic logistic classifier over pre-label features. |
| Output | Score report | JSON | State-level model/top-rank/top-score/oracle comparison. |
| Output | CSV | CSV | Candidate/state scores for audits. |

## Interfaces

New API:

- `train_official_candidate_viewpoint_ranker_model(dataset, ...)`
- `score_official_candidate_viewpoint_ranker_dataset(dataset, model, ...)`
- `evaluate_candidate_viewpoint_ranker_state_folds(dataset, ...)`
- `evaluate_candidate_viewpoint_ranker_leave_one_source(dataset, ...)`
- `write_official_candidate_viewpoint_ranker_scores_csv(report, path)`

New CLI:

```bash
python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
  <candidate_viewpoint_dataset.json> [more_dataset.json ...] \
  --output <model.json> \
  --scores-output <scores.json> \
  --csv-output <scores.csv> \
  --state-fold-output <folds.json> \
  --leave-one-source-output <leave_one_source.json>
```

## Data Flow

1. Load candidate-viewpoint restore rows.
2. Filter to label-available rows; by default keep only rows where the current
   restored state was target-hidden.
3. Build candidate examples from pre-label fields:
   candidate rank, score, expected evidence, view quality, path distance,
   bearing error, candidate episode-relative pose, action/decision/category
   tokens, and numeric `state_features`.
4. Train a deterministic logistic classifier for
   `hidden_to_visible_from_candidate_viewpoint`.
5. Score candidates within each restored state and select the highest model
   probability.
6. Compare selected candidate success against:
   top-rank baseline, top-score baseline, and oracle state recoverability.
7. Optionally run state-fold evaluation so train and holdout states are
   disjoint even when only one source artifact is available.
8. For multiple source artifacts, tag each row with `source_dataset` and run
   leave-one-source validation so all candidates from one exported dataset are
   held out together.

## Implementation Status

Implemented first slice:

- deterministic logistic training with standardized numeric features;
- safe feature extraction from pre-label candidate fields and numeric
  `state_features`;
- explicit exclusion of detector-label fields such as visible heading count,
  detector confidence, and candidate visibility labels;
- state-level model/top-rank/top-score/oracle score reports;
- deterministic state-fold evaluation with disjoint train/holdout states;
- CLI:
  `python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker`.

Real artifact result:

- source dataset:
  `runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1/dataset.json`;
- output:
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_phase_path_features_max8cat_max2episode_yolo_20260531_v1`;
- current-hidden filtered rows: `115` candidates from `23` states;
- label split: `69` positive, `46` negative;
- train-set candidate ROC-AUC: `0.959042`;
- state recovery: oracle `15/23`, model `14/23`, top-rank `13/23`,
  top-score `13/23`;
- 4-fold state-holdout aggregate: oracle `15/23`, model `14/23`,
  top-rank `13/23`, top-score `13/23`.

This is a small offline improvement over simple candidate-order baselines, not
an online ObjectNav or official benchmark result.

Next source-diverse slice:

- CLI accepts multiple candidate-viewpoint restore datasets.
- Rows loaded by the CLI carry `source_dataset` so source splits are auditable
  even if two artifacts share the same `source_policy_trace`.
- Leave-one-source evaluation trains on all but one source artifact and scores
  candidates only from the held-out source.
- The report aggregates oracle/model/top-rank/top-score recovery counts across
  held-out sources.
- This split is the minimum gate before treating candidate-viewpoint ranking as
  a learned memory component rather than a one-trace diagnostic.

Source-diverse artifact result:

- source-diverse output:
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v2`;
- source artifacts: five candidate-viewpoint restore datasets;
- two auxiliary 4-episode artifacts had all `10/10` candidate restores invalid
  before the `frontier_cell` fallback fix;
- after the fallback fix, current-hidden filtered rows: `155` candidates from
  `31` states;
- label split: `102` positive, `53` negative;
- state recovery: oracle `23/31`, model `22/31`, top-rank `18/31`,
  top-score `18/31`;
- leave-one-source aggregate: oracle `23/31`, model `22/31`, top-rank `18/31`,
  top-score `18/31`;
- among oracle-recoverable states, leave-one-source recovery is `22/23` for the
  model and `18/23` for both simple baselines.

The result is stronger than the one-source state-fold check but still offline
and source-limited. The largest held-out source improves by one state
(`14/23` all held-out states, or `14/15` oracle-recoverable states, for the
model vs `13/23` and `13/15` for top-rank/top-score), so online integration
should still be gated by direct policy tests rather than offline labels alone.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Dataset has no label-available rows | explicit `ValueError` | Do not train. |
| Dataset has only one label class | model warning | Still score baselines, but do not claim learning robustness. |
| Current-visible rows inflate success | default current-hidden filter | Optional flag can include them for audit only. |
| Model overfits one artifact | state-fold report | Treat train-set metrics as diagnostic only. |
| Source-specific artifacts leak across split | `source_dataset` holdout report | Hold out complete source artifacts, not random rows. |
| Label leakage via detector fields | fixed feature extractor excludes labels, visible heading count, detector confidence | Tests assert label names are not features. |
| Top-rank baseline already matches oracle | aggregate reports baseline gap | Do not claim model value without held-out improvement. |

## Verification Plan

- RED test: model trains on synthetic candidate-viewpoint rows and excludes
  label/leakage fields from feature names.
- RED test: score report groups candidates by state and compares model,
  top-rank, top-score, and oracle recovery.
- RED test: state-fold evaluation holds out states and reports aggregate
  recovery counts.
- RED test: CLI writes model, score JSON/CSV, and fold JSON.
- RED test: leave-one-source evaluation holds out whole source artifacts and
  reports model/top-rank/top-score/oracle counts.
- RED test: CLI accepts multiple datasets and writes leave-one-source JSON.
- Run focused tests, full local suite, compileall, diff check, and whitespace
  scan.
- Sync to Linux, generate source-diverse candidate-viewpoint artifacts, and
  train/score with leave-one-source validation.

## Research Relevance

This is the first check of whether memory candidate-viewpoint labels become a
learnable ranking signal. If held-out state folds improve over top-rank/top-score
baselines, this supports a memory-driven viewpoint-selection contribution. If
they do not, the project should use the labels diagnostically and improve the
memory representation or trace features before claiming a learned policy.

## Open Questions

- The current state-fold result beats top-rank/top-score by one state, but it
  still comes from one source trace. Multi-source leave-one-run validation is
  required before any model claim.
- Should future labels include anchor-facing heading visibility alongside
  uniform-scan visibility?
- Which learned ranker family is worth trying after this deterministic logistic
  baseline: pairwise ranking loss, calibrated gradient boosting, or a compact
  neural ranker with source holdouts?
