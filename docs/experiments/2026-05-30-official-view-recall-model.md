# Experiment Report: Official Hidden-to-Visible View-Recall Model

Date: 2026-05-30
Owner: Codex
Status: Offline scorer implemented; not yet an online policy result

## Question

Can a deterministic model trained from official view-recall datasets rank
hidden-to-visible detector recovery states well enough to justify replacing
hand-authored active-perception scan rules with learned view value?

## Hypothesis

The exported view-recall datasets contain a strong offline signal for
hidden-to-visible recovery. However, because the data are observational, naive
candidate-action overrides may learn global turn preferences rather than true
counterfactual action value.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Local macOS plus Linux mirror `badger@100.88.131.52` |
| Python env | Linux conda env `habitat` |
| Dataset family | `runs/habitat_official_objectnav/view_recall_dataset_*_20260530_v1` |
| Model | Deterministic logistic regression, pure Python |
| Default label | `hidden_to_visible_within_horizon` |
| Default filter | current-hidden examples only |

## Commands

Local verification during implementation:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_view_recall_model.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

Linux training and scoring pattern:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

python -m objectnav_core.cli.train_habitat_official_view_recall_model \
  runs/habitat_official_objectnav/view_recall_dataset_memory_evidence_yolo_20ep_80steps_20260530_v1/dataset.json \
  --output runs/habitat_official_objectnav/view_recall_model_hidden_to_visible_20260530_v1/memory_evidence_20ep_model.json \
  --epochs 800 \
  --learning-rate 0.15 \
  --l2 0.001

python -m objectnav_core.cli.score_habitat_official_view_recall_model \
  <dataset.json> \
  --model runs/habitat_official_objectnav/view_recall_model_hidden_to_visible_20260530_v1/memory_evidence_20ep_model.json \
  --output <score-report.json> \
  --csv-output <score-report.csv> \
  --actions move_forward,turn_left,turn_right
```

Additional artifacts:

- `runs/habitat_official_objectnav/view_recall_model_hidden_to_visible_20260530_v1/active_comparison_dataset.json`
- `runs/habitat_official_objectnav/view_recall_model_hidden_to_visible_20260530_v1/active_comparison_model.json`
- `runs/habitat_official_objectnav/view_recall_model_hidden_to_visible_20260530_v1/active_train_without_*_model.json`

## Metrics

### Memory-Evidence Model

Trained on the 20-episode memory-evidence export:

| Split | Hidden examples | Hidden positives | ROC AUC | Log loss | Top-5 positives | Top-10 positives | Candidate best-action collapse |
|---|---:|---:|---:|---:|---:|---:|---|
| train memory evidence | `1080` | `53` | `0.975262` | `0.060715` | `5/5` | `10/10` | all `turn_right` |
| active original | `157` | `10` | `1.0` | `0.151804` | `5/5` | `10/10` | all `turn_right` |
| active rotation-aware | `166` | `11` | `0.992962` | `0.170382` | `5/5` | `9/10` | all `turn_right` |
| active path-aware | `183` | `10` | `1.0` | `0.133239` | `5/5` | `10/10` | all `turn_right` |
| active viewpoint scan | `192` | `5` | `0.828877` | `0.081422` | `1/5` | `1/10` | all `turn_right` |

The memory-evidence model ranks non-scan active recovery states surprisingly
well, but it fails to reject the scan-policy trace: on the scan dataset it
assigns mean prediction `0.069377` to `orient_anchor` and `0.062987` to
`scan_anchor`, even though both groups have `0/20` positives.

### Active-Comparison Models

The combined active model was trained on all four active variants and therefore
is partly in-sample. It scores the scan trace cleanly only after seeing scan
negatives during training:

| Model / score target | Hidden examples | Hidden positives | ROC AUC | Log loss | Phase behavior on scan |
|---|---:|---:|---:|---:|---|
| combined active train set | `698` | `36` | `0.999496` | `0.022668` | in-sample |
| combined active model on scan | `192` | `5` | `1.0` | `0.013078` | `orient_anchor` mean `0.008669`, `scan_anchor` mean `0.009824` |
| train without original, score original | `157` | `10` | `1.0` | `0.12603` | held-out variant |
| train without rotation, score rotation | `166` | `11` | `0.992962` | `0.073331` | held-out variant |
| train without path, score path | `183` | `10` | `0.930636` | `0.29529` | held-out variant |
| train without scan, score scan | `192` | `5` | `1.0` | `0.131417` | over-scores unseen scan phases |

When the scan variant is held out, the model still ranks the five scan-trace
positives in the top five, but it also assigns high mean predictions to unseen
negative scan phases: `orient_anchor=0.26447` and `scan_anchor=0.578289`.
This is a warning that phase coverage matters before online use.

## Observations

- Hidden-to-visible recovery is learnable offline. The 20-episode model reaches
  ROC AUC `0.975262` on its training source and transfers well to the original,
  rotation-aware, and path-aware active traces.
- Candidate-action scoring is not yet policy-ready. The memory-evidence model
  chooses `turn_right` for every scored row, while the active-comparison model
  chooses `turn_left` for every scored row. This reflects observational action
  correlation, not true counterfactual action value.
- The scan phase is still the core negative example. A model trained with scan
  negatives can suppress scan rows, but a model that has never seen scan
  negatives can over-score them badly.
- The strongest current use is an offline state/value ranker and diagnostic
  filter, not a closed-loop controller.

## Result

The view-recall model slice is useful and aligned with the paper direction, but
it is not yet sufficient for an official benchmark run. It establishes a
trainable hidden-recovery signal and gives a concrete next algorithmic
requirement: learn action/viewpoint value from data that includes negative
scan/viewpoint candidates and avoids pure logged-action confounding.

## Follow-up

- Build a candidate-view/action dataset where each state has multiple scored
  candidate actions or viewpoints, not just the logged action.
- Train the next scorer to rank candidates directly and verify it does not
  over-score `orient_anchor` or `scan_anchor` negatives.
- Only integrate into the official policy after held-out candidate ranking is
  strong and candidate best-action counts do not collapse to one global turn.
