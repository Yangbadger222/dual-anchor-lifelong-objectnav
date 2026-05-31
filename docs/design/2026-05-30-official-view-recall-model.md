# Design Doc: Official View-Recall Model

Date: 2026-05-30
Owner: Codex
Status: Implemented with offline scoring

## Goal

Train and score a deterministic baseline model that predicts whether an
official ObjectNav state will recover target detector evidence within a short
future horizon, with the default target focused on hidden-to-visible recovery
rather than detector-continuity rows.

## Non-Goals

- Do not claim official ObjectNav benchmark improvement from the offline model.
- Do not add neural training infrastructure or external dependencies in this
  slice.
- Do not use Habitat target pose, semantic oracle masks, prior maps, or route
  followers.
- Do not connect the model back into the online policy until offline ranking
  quality is measured.

## Background

The active-perception scan experiments produced negative official metrics, and
the view-recall dataset comparison showed that `orient_anchor` and
`scan_anchor` phases had zero hidden-to-visible positives. The useful positive
examples came from memory-frontier turn/move decisions. The next research move
is therefore not another hand-authored scan rule; it is a learnable value model
for which memory-relative states and actions are likely to produce detector
evidence.

## System Boundary

Create:

- `objectnav_core.evaluation.habitat_official_view_recall_model`
- `objectnav_core.cli.train_habitat_official_view_recall_model`
- `objectnav_core.cli.score_habitat_official_view_recall_model`
- focused tests for training, scoring, CLI output, and packaging

Modify:

- `src/objectnav_core/setup.py` console scripts
- `src/objectnav_core/tests/test_ros_packaging.py`
- docs/devlog/handoff and an experiment report after scoring real exported
  datasets

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | View-recall dataset | JSON | Produced by `export_habitat_official_view_recall_dataset`. |
| Input | Feature list | comma-separated strings | Defaults to safe numeric and one-hot fields. |
| Input | Label | string | Defaults to derived `hidden_to_visible_within_horizon`. |
| Output | Model JSON | JSON | Weights, bias, preprocessing, metrics, dataset counts. |
| Output | Score report JSON | JSON | Per-example predictions, ranking metrics, grouped summaries. |
| Output | Score CSV | CSV | Flat rows for audit and plotting. |

## Interfaces

Python API:

```python
train_official_view_recall_logistic_model(dataset, ...)
predict_official_view_recall(model, example, action=None)
score_official_view_recall_dataset(dataset, model, ...)
write_official_view_recall_scores_csv(path, rows)
```

CLI:

```bash
python -m objectnav_core.cli.train_habitat_official_view_recall_model \
  <dataset.json> --output <model.json>

python -m objectnav_core.cli.score_habitat_official_view_recall_model \
  <dataset.json> --model <model.json> --output <scores.json> \
  --csv-output <scores.csv>
```

Console scripts:

```bash
objectnav_habitat_official_view_recall_model ...
objectnav_habitat_official_view_recall_score ...
```

## Data Flow

1. Load examples from a view-recall dataset.
2. Filter examples. The default training slice is current-hidden examples so
   detector-continuity rows do not dominate the model.
3. Derive label `hidden_to_visible_within_horizon` as
   `not current_target_visible and target_visible_within_horizon`.
4. Extract portable features:
   - memory-relative geometry and expected-evidence fields;
   - action one-hot features;
   - decision and active-perception phase one-hot features;
   - selected scalar fields already present in the dataset.
5. Standardize finite numeric features and impute missing values from training
   means.
6. Train deterministic logistic regression with L2 regularization.
7. Score examples and report log loss, Brier score, accuracy, ROC AUC,
   precision at top-k, and grouped prediction/label counts by action, decision,
   and active-perception phase.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Dataset has no examples | Loader raises `ValueError` | Fix export path or source run. |
| Hidden slice has no positives or negatives | Model warning and degraded metrics | Aggregate more runs before online use. |
| Feature missing in some trace versions | Missing-value count and warnings | Impute from training mean; keep report explicit. |
| Model ranks scan rows high despite zero positives | Score report grouped summaries | Reject policy integration until offline ranking improves. |
| Raw future-visible labels dominate continuity rows | Training filter and derived hidden label | Default to current-hidden examples. |

## Verification Plan

1. RED test: synthetic hidden-to-visible examples train a model that scores a
   positive recovery example above a negative one.
2. RED test: candidate action overrides change scores and can rank a useful
   turn above a forward action.
3. RED CLI tests: train and score commands write JSON/CSV reports.
4. Packaging test covers both new console scripts.
5. Local focused tests, compileall, and `git diff --check`.
6. Sync to Linux, rerun focused tests in conda env `habitat`, and score the
   real comparison datasets.

## Implementation Notes

- Added deterministic logistic training and scoring in
  `habitat_official_view_recall_model`.
- Added train/score CLIs and console scripts:
  `objectnav_habitat_official_view_recall_model` and
  `objectnav_habitat_official_view_recall_score`.
- Default training uses only current-hidden examples with derived label
  `hidden_to_visible_within_horizon`.
- Linux offline scoring found strong hidden-recovery ranking signal, but also
  showed that candidate-action overrides collapse to a global turn preference
  and models without scan-negative coverage can over-score scan phases.

## Research Relevance

This is the first explicit learned view-value layer for the map-free lifelong
memory story. It lets the project measure whether memory-relative detector
recovery has a trainable signal before changing the online policy. If the
offline ranking is weak, we avoid a low-value benchmark smoke; if it is strong,
the learned scorer becomes the algorithmic candidate for memory-conditioned
active sensing on the robot.

## Open Questions

- Whether one cross-policy model is enough, or active-perception and
  memory-belief traces need separate calibration.
- Whether later labels should include detector quality, depth support, or bbox
  stability in addition to binary target visibility.
