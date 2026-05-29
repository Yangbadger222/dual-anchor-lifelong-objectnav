# Design Doc: Memory-Validity Learning Pipeline

Date: 2026-05-30
Owner: Codex
Status: Implemented locally

## Goal

Add one offline command that exports Habitat memory-validity examples, trains a
learned validity model with optional held-out evaluation, scores learned
memory-vs-frontier decisions, and writes all artifacts into a reproducible
output directory.

## Non-Goals

- Do not run Habitat-Sim or detectors.
- Do not change online policy behavior.
- Do not introduce a new model family or dependency.
- Do not hide train/holdout details behind a single score.
- Do not claim benchmark improvement until run on real Habitat artifacts.

## Background

The repo now has separate tools for dataset export, logistic training, held-out
evaluation, and learned decision scoring. Running them by hand on the Linux
machine would be easy to get wrong and hard to reproduce. A single pipeline
command makes the next artifact run auditable: the exact inputs, outputs,
feature list, holdout split, model metrics, and learned decision counts live
together.

## System Boundary

The pipeline is an offline orchestration layer. It depends on:

- `export_habitat_memory_validity_dataset`;
- `train_memory_validity_logistic_model`;
- optional `split_memory_validity_dataset` and `evaluate_memory_validity_model`;
- `score_memory_validity_decisions`.

It does not import Habitat-Sim, detectors, or the online runner.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Summary inputs | Files/directories | Same discovery as the dataset exporter |
| Input | Output directory | Directory | Pipeline writes all artifacts here |
| Input | Policies/features/training params | CLI options | Optional, deterministic defaults |
| Input | Holdout field/values | CLI options | Optional metadata split |
| Output | `dataset.json` | JSON | Exported examples |
| Output | `examples.csv` | CSV | Flat dataset table |
| Output | `model.json` | JSON | Learned model report |
| Output | `scores.json` | JSON | Learned decision scores |
| Output | `scores.csv` | CSV | Flat score table |
| Output | `pipeline_report.json` | JSON | Paths, counts, metrics, score aggregate |

## Interfaces

- Python API:
  - `run_memory_validity_learning_pipeline(inputs, output_dir, ...)`
- CLI:
  - `python -m objectnav_core.cli.run_habitat_memory_validity_learning_pipeline <inputs...> --output-dir <dir>`

Implementation plan:
- `docs/superpowers/plans/2026-05-30-memory-validity-learning-pipeline.md`

## Data Flow

1. Export examples from summary inputs.
2. Write `dataset.json` and `examples.csv`.
3. Train the logistic model on all examples or on the non-holdout split.
4. If holdout options are present, attach train/holdout evaluation to the model
   report.
5. Write `model.json`.
6. Score learned decisions for the exported examples.
7. Write `scores.json`, `scores.csv`, and `pipeline_report.json`.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No examples exported | Trainer raises `ValueError` | Run broader summaries or inspect exporter warnings |
| Empty holdout/train split | Split helper raises `ValueError` | Adjust holdout values |
| Missing action-count features | Scorer skips rows with warnings | Inspect `scores.json` warnings |
| Train-only run mistaken as paper evidence | Pipeline report records holdout metadata or absence | Require held-out run for claims |
| Linux host unreachable | Local pipeline remains ready | Run when SSH returns |

## Verification Plan

- Unit test the pipeline API on synthetic summary files.
- CLI test that writes all five artifact files plus `pipeline_report.json`.
- Focused pipeline/model/dataset tests.
- Full local core suite.
- Later Linux run on ranked relocation summaries.

## Research Relevance

This turns learned memory validity into a reproducible experiment slice. The
paper path needs evidence that can be rerun and audited: which summaries were
exported, what features were used, what split was held out, how well validity
generalized, and whether learned probabilities crossed decision boundaries.

## Open Questions

- Which real split should be the first paper-facing run: category, scene/run,
  or both?
- Should pipeline reports later include fixed/evidence/event-posterior
  comparison tables?
- Should the pipeline emit notebook-ready plots once real artifacts exist?

## Implementation Notes

The local implementation adds both the Python API and CLI. It writes
`dataset.json`, `examples.csv`, `model.json`, `scores.json`, `scores.csv`, and
`pipeline_report.json` under the requested output directory. The next required
step is to run this command on the real ranked relocation summaries once the
Linux Habitat host is reachable.
