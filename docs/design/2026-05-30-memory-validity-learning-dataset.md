# Design Doc: Habitat Memory-Validity Learning Dataset

Date: 2026-05-30
Owner: Codex
Status: Draft

## Goal

Create a reproducible dataset exporter that converts Habitat closed-loop
`summary.json` artifacts into supervised examples for learning or calibrating
memory validity. The target label is whether the remembered object pose is
valid for the current query before choosing memory-first versus frontier-first.

## Non-Goals

- Do not train a final model in this step.
- Do not use future fallback success as a pre-decision feature.
- Do not tune a category-specific rule or threshold.
- Do not claim benchmark performance from the exported dataset alone.
- Do not change the existing `fixed`, `evidence`, or `event_posterior` policy
  behavior in the runner.

## Background

The ranked relocation sweep found better stale-memory geometry and near
decision boundaries, especially the `toilet` relocation row. However,
Grounding-DINO event posterior did not move reliability because runtime detector
events occurred in fallback contexts after choosing frontier, while
memory-validity event counts remained zero.

This is the point where another hand-weighted reliability tweak would be weak
paper material. The stronger direction is to export labeled examples and train
or calibrate a memory-validity model on held-out scenes/categories.

## System Boundary

The exporter is an offline research tool. It reads existing Habitat
closed-loop summaries and writes JSON/CSV examples. It depends on row payloads
already emitted by the runner and does not import Habitat-Sim, detectors, or
navigation code.

The online runner can later consume a learned model through a separate
reliability mode, but that is outside this first dataset step.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Habitat summaries | `summary.json` files or directories | Same discovery behavior as the decision-sensitivity miner |
| Input | Policy filter | CSV string | Default `memory_guided` |
| Output | Dataset report | JSON | Counts, feature schema, label balance, skipped rows |
| Output | Examples | JSON list in report | One example per usable row |
| Output | CSV | Optional CSV | Flat table for notebooks or training scripts |

## Interfaces

- Python API:
  - `export_habitat_memory_validity_dataset(inputs, policies=...)`
  - `write_memory_validity_dataset_csv(path, examples)`
- CLI:
  - `python -m objectnav_core.cli.export_habitat_memory_validity_dataset <inputs...> --output <report.json> --csv-output <examples.csv>`

## Data Flow

1. Resolve input paths to `summary.json` files.
2. Read rows matching selected policies.
3. Extract only pre-decision or planned-cost fields:
   `challenge`, `detector`, `category`, `relocation_pair_distance_m`,
   memory/fallback route costs, current memory evidence payload,
   memory-reliability components, and memory-context detector event features.
4. Label each example from `memory_evidence.shared_gate_success`.
5. Add auxiliary labels such as current row decision bucket and hindsight best
   candidate for analysis, but mark them as auxiliary rather than features.
6. Write JSON report and optional CSV.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Missing rows | Report `skipped_count` and warnings | Keep exporter non-fatal across mixed artifacts |
| Missing memory evidence | Skip row with warning | Do not fabricate labels |
| Future leakage | Feature schema excludes fallback evidence and selected outcome | Tests assert forbidden fields are absent |
| Class imbalance | Report positive/negative label counts | Use later stratified splits or active data collection |
| Mixed detector/oracle data | Include detector and challenge fields | Let training scripts filter or split explicitly |

## Verification Plan

- Unit test that a synthetic row becomes a labeled example with numeric
  planned-cost and evidence features.
- Unit test that fallback evidence and success are not exported as features.
- Unit test JSON/CSV writing through the CLI.
- Run local focused and full test suites.
- Export the dataset on Linux from ranked relocation and existing
  event-posterior artifacts; record label balance and feature coverage.

## Research Relevance

This is the bridge from transparent but hand-designed reliability estimates to
a learned memory-validity model. It supports the paper story by making memory
reuse a calibrated prediction problem: when should a lifelong robot trust a
remembered object pose after scene changes, detector uncertainty, and frame
drift?

The exported rows can support:

- learned reliability versus fixed/evidence/event-posterior ablations;
- held-out scene/category calibration;
- analysis of stale-memory failures and harmful reuse avoidance;
- future language-conditioned queries that distinguish "the object I saw" from
  "an object of this category".

## Open Questions

- Which held-out split is strongest: scene, category, or relocation scene?
- Should the first learned model predict validity, expected regret, or both?
- How much online probing is acceptable before a decision is no longer
  pre-decision?
