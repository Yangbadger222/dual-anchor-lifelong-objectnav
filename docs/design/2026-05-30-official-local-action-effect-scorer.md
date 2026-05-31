# Design Doc: Official Local Action-Effect Scorer

Date: 2026-05-30
Owner: Codex
Status: Implemented; initial YOLO scorer smoke completed

## Goal

Train and persist an initial learned local action-effect scorer from the
official local action dataset. The scorer should predict whether a candidate
discrete action is likely to produce target-visible evidence in the next
observation, using only pre-action trace features and the candidate action.

## Non-Goals

- Do not change official ObjectNav policy behavior in this slice.
- Do not claim benchmark improvement from offline training metrics.
- Do not use future labels, Habitat success, geodesic distance, oracle masks, or
  pathfinder information as model features.
- Do not treat the four-episode YOLO dataset as sufficient for a paper claim.
- Do not train a deep model yet; the first scorer should be deterministic and
  auditable so it can be used as a regression target for later learned models.

## Background

The new local action-effect dataset exporter produced `196` examples from the
latest four-episode YOLO official trace. The useful positive evidence is sparse
but informative: after a failed centering action, forward edge-tracking retained
the target twice while bbox area dropped and center offset worsened, then lost
the target on the third forward step.

This slice turns that exported dataset into a model artifact. It is deliberately
not the final controller. Its value is the interface: later policy code can ask
"from this local evidence state, how does the learned model score
`move_forward`, `turn_left`, and `turn_right`?" without hard-coding the answer.

## System Boundary

Add:

- `objectnav_core.evaluation.habitat_official_local_action_model`
- `objectnav_core.cli.train_habitat_official_local_action_model`
- focused tests under `src/objectnav_core/tests/`

Reuse existing project patterns from the memory-validity logistic baseline, but
keep the local-action feature extraction separate because action identity and
candidate-action overrides are specific to local control.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Local action dataset | JSON from `export_habitat_official_local_action_dataset` | Uses `examples[*].features`, action, decision, and labels. |
| Input | Candidate action override | `move_forward`, `turn_left`, `turn_right`, `stop` | Used for counterfactual scoring with the same current evidence. |
| Output | Model | JSON | Logistic weights, preprocessing stats, feature names, label name, metrics. |
| Output | Prediction | Probability | Probability that next observation has target-visible evidence. |

## Interfaces

Python API:

- `train_official_local_action_logistic_model(dataset, feature_names=None, epochs=..., learning_rate=..., l2=...)`
- `predict_official_local_action_success(model, example, action=None)`
- `score_official_local_action_candidates(model, example, actions=("move_forward", "turn_left", "turn_right"))`

CLI:

```bash
python -m objectnav_core.cli.train_habitat_official_local_action_model \
  <local_action_dataset.json> \
  --output <model.json> \
  --epochs 400 \
  --learning-rate 0.1 \
  --l2 0.001
```

## Data Flow

1. Load dataset examples.
2. Build labels from `labels.next_target_visible`.
3. Build numeric pre-action features:
   current target visibility, confidence, bbox area, absolute center offset,
   pose/heading, action one-hot, decision one-hot for detector-local-control
   decisions, and suppressed-centering-action one-hot.
4. Impute missing numeric fields with train-set means and standardize by
   train-set scales.
5. Train deterministic logistic regression.
6. Persist the model and preprocessing stats.
7. For candidate scoring, rebuild the same feature row while overriding the
   action one-hot for each candidate action.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Dataset has only one label class | Training report warning and metrics show zero positives/negatives | Persist model anyway for pipeline testing; do not use for policy claims. |
| Sparse positives dominate training | Metrics and label counts expose imbalance | Use this only as an initial scaffold; collect larger traces before policy use. |
| Future leakage enters features | Tests check label-only fields are absent from feature names | Keep default features generated from pre-action fields only. |
| Candidate override not respected | Unit test scores same example under different action overrides | Encode action one-hot from override, not original example action. |
| Model treated as benchmark evidence | Docs and artifact task name identify offline scorer | Official Habitat metrics remain separate. |

## Verification Plan

1. RED synthetic training test:
   - construct examples where `move_forward` with visible target is positive
     and `turn_right` with the same evidence is negative;
   - train the model;
   - assert `predict(..., action="move_forward")` is higher than
     `predict(..., action="turn_right")`.
2. RED candidate scoring test proving all requested action candidates are
   returned and ranked by learned probability.
3. RED CLI test proving `model.json` is written with feature names, metrics, and
   persisted preprocessing stats.
4. GREEN implementation without Habitat dependency.
5. Run focused local tests, compile checks, and `git diff --check`.
6. Train on the current four-episode YOLO dataset as a smoke artifact and record
   that it is diagnostic only.

## Research Relevance

This begins replacing local servo rules with an action-effect model. The model
can later be trained from larger simulation traces and real robot logs while
preserving the same online interface. That supports the paper story: lifelong
memory proposes where to search; grounded detector evidence and learned
action-effect control decide how to reacquire and approach objects under drift
and no-prior-map conditions.

## Open Questions

- Whether the online policy should optimize target retention, evidence-quality
  regression, or a multi-task score.
- Whether to balance examples by decision/action before training on larger
  traces.
- Whether to use this logistic scorer directly as an ablation or only as the
  baseline for a learned sequence model.
