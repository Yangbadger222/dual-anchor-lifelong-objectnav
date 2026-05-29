# Design Doc: Memory-Validity Learned Decision Scorer

Date: 2026-05-30
Owner: Codex
Status: Implemented locally

## Goal

Add an offline scorer that applies a learned memory-validity model to exported
Habitat memory-validity examples and recomputes whether the learned validity
probability would choose memory-first or frontier-first.

## Non-Goals

- Do not change the online Habitat runner.
- Do not train the model in this scorer; consume an existing model report.
- Do not claim benchmark improvement from synthetic or train-set scores.
- Do not use fallback evidence, final success, or hindsight labels as model
  features.
- Do not tune category-specific thresholds or action-count constants.

## Background

The logistic baseline can now predict whether a remembered object pose is valid,
but the paper-critical question is whether that probability changes the
pre-decision memory-vs-frontier policy. Existing decision-sensitivity mining
already computes the expected-utility boundary from saved action counts. This
scorer connects the learned model to that same boundary offline, so real
ranked-relocation artifacts can be audited immediately once the Linux Habitat
host is reachable again.

## System Boundary

The scorer owns offline analysis only. It depends on:

- exported dataset JSON from `export_habitat_memory_validity_dataset`;
- model JSON from `train_habitat_memory_validity_model`;
- pre-decision action-count features already present in the exporter schema.

The online runner, detector, Habitat-Sim, and navigation code remain outside
this step.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Dataset report | JSON | Output from memory-validity exporter |
| Input | Model report | JSON | Output from logistic baseline trainer |
| Output | Score report | JSON | Per-example predictions, decisions, boundaries, aggregate counts |
| Output | Score table | Optional CSV | Flat rows for notebook sorting |

## Interfaces

- Python API:
  - `score_memory_validity_decisions(dataset, model)`
  - `write_memory_validity_decision_scores_csv(path, rows)`
- CLI:
  - `python -m objectnav_core.cli.score_habitat_memory_validity_model <dataset.json> --model <model.json> --output <scores.json> --csv-output <scores.csv>`

Implementation plan:
- `docs/superpowers/plans/2026-05-30-memory-validity-learned-decision-scorer.md`

## Data Flow

1. Load dataset examples and model report.
2. Predict `learned_memory_valid_probability` from each example's feature dict.
3. Read pre-decision action-count features:
   `memory_action_count`, `fallback_action_count`, and
   `fallback_from_memory_action_count`.
4. Compute expected memory-first cost:
   `memory_action_count + (1 - p_valid) * fallback_from_memory_action_count`.
5. Compare against frontier-first cost `fallback_action_count`.
6. Compute the raw reliability boundary and boundary region.
7. Mark learned decision flips against `aux_memory_decision` when that field is
   present.
8. Aggregate memory/frontier counts, flip counts, and boundary-region counts.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Missing dataset examples | Raise `ValueError` | Export a dataset first |
| Missing model features or weights | Prediction falls back to stored defaults and zero weights | Keep model report self-contained |
| Missing action-count feature | Skip row with warning | Preserve other rows |
| No post-memory fallback count | Mark boundary as `no_post_memory_fallback` | Do not force a flip claim |
| Scores computed on train split | Report is descriptive only | Later add held-out scene/category split |

## Verification Plan

- Unit test that a high learned validity probability chooses memory-first while
  a low probability chooses frontier-first on synthetic rows.
- Unit test boundary-region and flip accounting.
- CLI test writes JSON and optional CSV score reports.
- Focused model/dataset/scorer tests.
- Full local core suite.
- Later Linux run on ranked relocation artifacts once SSH is reachable.

## Research Relevance

This scorer is the bridge from "we can train a validity model" to "the learned
model would change ObjectNav behavior before acting." It keeps the evidence
auditable: every claimed learned flip must have a predicted validity,
action-count boundary, expected memory cost, frontier cost, and source example.

## Open Questions

- Should the first paper table report learned flips on train artifacts, held-out
  categories, held-out scenes, or all three?
- Should future scorers compare against fixed/evidence/event-posterior modes in
  the same report?
- Should online probing collect extra pre-decision features before applying the
  learned model?

## Implementation Notes

The local implementation adds the scoring API, CSV writer, and CLI. It reports
per-row learned validity, expected memory-first cost, frontier-first cost,
learned decision, decision boundary, and flip status against the auxiliary saved
decision when available. Real-artifact scoring is still pending Linux Habitat
host reachability.
