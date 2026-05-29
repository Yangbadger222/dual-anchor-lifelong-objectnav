# Design Doc: Memory-Validity Held-Out Evaluation

Date: 2026-05-30
Owner: Codex
Status: Implemented locally

## Goal

Add held-out evaluation support for the learned memory-validity baseline so
model reports can distinguish train-set fit from category/run/scene
generalization.

## Non-Goals

- Do not add a neural model or external ML framework.
- Do not claim benchmark improvement from local synthetic tests.
- Do not change online Habitat runner behavior.
- Do not pick paper splits from tiny artifacts automatically.
- Do not use fallback evidence, final success, or hindsight labels as features.

## Background

The current logistic baseline reports train metrics only. That is useful for
smoke testing but too weak for a robotics-paper claim. The exporter already
preserves metadata such as category, run id, group id, challenge, detector, and
source summary. A simple metadata holdout is enough to make the next Linux run
audit whether learned memory validity generalizes beyond the rows used for
fitting.

## System Boundary

This is offline research tooling. It owns dataset splitting and model
evaluation metrics for exported memory-validity examples. It depends on the
existing dataset exporter and logistic model report format. It does not import
Habitat-Sim, detectors, or navigation code.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Dataset report | JSON | Output from memory-validity exporter |
| Input | Holdout field | String | Example metadata field such as `category` or `run_id` |
| Input | Holdout values | CSV string | Exact metadata values reserved for evaluation |
| Output | Split datasets | In-memory dicts | Train and holdout subsets preserve schema/metadata |
| Output | Model report | JSON | Existing trainer report plus optional split/evaluation sections |

## Interfaces

- Python API:
  - `split_memory_validity_dataset(dataset, holdout_field, holdout_values)`
  - `evaluate_memory_validity_model(dataset, model)`
- CLI extension:
  - `python -m objectnav_core.cli.train_habitat_memory_validity_model <dataset.json> --output <model.json> --holdout-field category --holdout-values toilet,chair`

Implementation plan:
- `docs/superpowers/plans/2026-05-30-memory-validity-heldout-evaluation.md`

## Data Flow

1. Load the exported dataset.
2. Split examples by exact string match on the selected metadata field.
3. Train the model only on non-holdout examples.
4. Evaluate train and holdout examples with the fitted model.
5. Write split metadata and evaluation metrics into the model report.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Empty train split | Raise `ValueError` | Use broader training data or fewer holdout values |
| Empty holdout split | Raise `ValueError` | Check field/value spelling |
| Missing metadata field | Row stays in train unless it matches no holdout value | Report split counts |
| Tiny holdout split | Metrics show example counts | Treat as smoke only |
| Class imbalance | Metrics include positive/negative counts | Later use stratified scene/category splits |

## Verification Plan

- Unit test splitting by category produces expected train/holdout counts.
- Unit test evaluator reports accuracy, log loss, and Brier score on a synthetic
  holdout set.
- CLI test writes split metadata and train/holdout metrics.
- Focused model/dataset tests.
- Full local core suite.
- Later Linux run on real ranked relocation artifacts.

## Research Relevance

This makes learned memory validity harder to fool. Instead of reporting only
train-set fit, the next experiment can explicitly state whether the model was
evaluated on held-out categories, scenes, or runs. That is the minimum standard
before comparing against fixed, evidence, and event-posterior baselines.

## Open Questions

- Should the first paper-facing split be category holdout, scene/run holdout, or
  both?
- Should future splits stratify by valid/invalid label balance?
- Should decision-flip scoring report train and holdout splits separately?

## Implementation Notes

The local implementation adds metadata split helpers, model evaluation metrics,
and trainer CLI flags. When holdout flags are provided, the CLI trains only on
the non-holdout examples and writes `split`, `evaluation.train`, and
`evaluation.holdout` sections to the model report. Real held-out results still
depend on exporting ranked relocation artifacts on the Linux Habitat host.
