# Design Doc: Memory-Validity Logistic Baseline

Date: 2026-05-30
Owner: Codex
Status: Implemented locally

## Goal

Add a deterministic learned baseline that trains a small logistic model on the
exported Habitat memory-validity dataset. The model predicts whether a remembered
object pose is valid for the current query using only pre-decision features.

## Non-Goals

- Do not claim this is the final paper model.
- Do not use fallback evidence, final success, or hindsight labels as features.
- Do not add a neural network dependency or training framework.
- Do not change online runner behavior yet.
- Do not tune category-specific thresholds.

## Background

The relocation challenge now exposes stale-memory rows and near decision
boundaries, but the hand-designed event posterior cannot move reliability when
there are no memory-context detector events. The dataset exporter creates the
right supervised examples. A simple logistic model is the next baseline because
it is transparent, easy to audit, and can later be compared against fixed,
evidence, event-posterior, and richer learned models.

## System Boundary

This module is an offline trainer/evaluator. It reads dataset JSON reports from
`export_habitat_memory_validity_dataset`, trains on numeric feature fields, and
writes a model artifact with weights, feature names, preprocessing defaults,
and training metrics.

The runner will not consume this model in this step.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Dataset report | JSON | Output from memory-validity exporter |
| Input | Feature names | Optional CSV | Defaults to the dataset feature schema |
| Output | Model report | JSON | Weights, bias, feature means, metrics |

## Interfaces

- Python API:
  - `train_memory_validity_logistic_model(dataset, feature_names=None, epochs=..., learning_rate=..., l2=...)`
  - `predict_memory_validity(model, features)`
- CLI:
  - `python -m objectnav_core.cli.train_habitat_memory_validity_model <dataset.json> --output <model.json>`

Implementation plan:
- `docs/superpowers/plans/2026-05-30-memory-validity-logistic-baseline.md`

## Data Flow

1. Load dataset report and examples.
2. Select numeric feature names from `feature_schema`.
3. Convert missing values to per-feature means computed on training examples.
4. Standardize features with mean and scale.
5. Train logistic regression with deterministic batch gradient descent and L2.
6. Report accuracy, log loss, Brier score, positive count, and negative count.
7. Write weights and preprocessing stats for later replay or online integration.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Dataset has no examples | Raise `ValueError` | Export more artifacts |
| Dataset has only one label class | Report metrics but mark `single_class_warning` | Use as smoke only, not a claim |
| Non-numeric feature value | Treat as missing and impute | Keep warnings count |
| Overfitting tiny artifacts | Metrics reported on train split only | Later add held-out scene/category split |

## Verification Plan

- Unit test that the model separates a tiny synthetic dataset.
- Unit test prediction uses persisted feature means/scales.
- CLI test writes a JSON model report.
- Local focused and full test suite.
- Later Linux run on ranked relocation artifacts once SSH is reachable.

## Research Relevance

This creates the first learned reliability baseline for the lifelong memory
system. It is intentionally modest, but it turns memory reuse into an auditable
prediction problem and gives the paper a path beyond hand-tuned priors:

- fixed prior versus evidence heuristic;
- event-posterior heuristic versus learned validity;
- held-out scene/category calibration;
- stale-memory relocation challenge as supervision.

## Open Questions

- Should the first held-out split be by scene, category, or run id?
- Should a future model predict validity only, or expected regret directly?
- How should online probing features be separated from pre-decision features?

## Implementation Notes

The local implementation is intentionally offline-only. The model report stores
feature names, weights, bias, imputation means, scales, missing-value counts,
training hyperparameters, and train-set metrics. Online Habitat policy
integration is deferred until the Linux artifacts can export a real dataset and
the learned reliability can be audited against ranked relocation rows.
