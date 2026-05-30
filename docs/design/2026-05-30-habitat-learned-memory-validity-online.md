# Design Doc: Habitat Learned Memory Validity Online

Date: 2026-05-30  
Owner: Codex  
Status: Implemented

## Goal

Allow the Habitat closed-loop dual-anchor runner to consume a trained
memory-validity model JSON and use its pre-decision probability in the existing
memory-vs-frontier expected-utility decision. This closes the gap between the
offline learned scorer and an actual Habitat policy row.

## Non-Goals

- Do not retrain models inside the Habitat runner.
- Do not add a new navigation policy, frontier sampler, detector, or route
  observation mode.
- Do not use fallback evidence, final success, or oracle labels as learned
  model features.
- Do not claim benchmark performance from a single replay slice.

## Background

The offline memory-validity learning pipeline can now export rows, train a
deterministic logistic model, and score counterfactual decisions. The first
mixed stable-plus-relocation Grounding-DINO run produced one learned flip on an
invalid relocated `sofa` memory, while fixed/evidence/event-posterior heuristic
mining still produced zero flips. That flip must be rerun through the Habitat
runner before it can count as an online policy decision.

## System Boundary

The Habitat runner owns loading the model file, constructing an
exporter-compatible pre-decision feature vector, replacing the reliability
probability used by expected-utility selection, and recording audit payloads.
The model implementation remains in
`objectnav_core.evaluation.habitat_memory_validity_model`.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | `--memory-validity-model` | JSON path | Trained model report from the offline pipeline. |
| Input | Base reliability context | Existing runner state | Built from memory evidence, matching, transform, repeat, and detector events. |
| Output | `memory_valid_prior` | float | Learned probability used by the row decision. |
| Output | `memory_reliability` | JSON object | Records learned model mode, base estimate, selected model features, and prediction. |
| Output | `summary.json` | Habitat run artifact | Preserves existing row and summary fields. |

## Interfaces

- CLI:
  `python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav ... --memory-validity-model <model.json>`
- Python API:
  `run_habitat_closed_loop_dual_anchor_objectnav(..., memory_validity_model_path=...)`

## Data Flow

1. The CLI loads the model JSON path and passes it to the runner.
2. For each candidate memory row, the runner first computes the existing
   `fixed`, `evidence`, or `event_posterior` reliability estimate.
3. If a model is supplied, the runner creates a feature dict containing only
   route counts, current memory evidence, reliability components, detector-event
   components, and optional relocation metadata already present before the
   decision.
4. The model predicts `P(memory_valid)`.
5. The expected-utility decision uses that probability.
6. The row records the learned probability plus the base estimate for audit.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Model JSON missing or malformed | CLI/API raises before running Habitat | Fail fast with the path in the error. |
| Model expects unavailable features | Predictor imputes from training metadata | Record feature names and missing values remain auditable through the model file. |
| Learned probability flips a row for the wrong reason | Compare row payload, model features, and baseline miner output | Treat as diagnostic until replayed on broader held-out categories/scenes. |
| Model path used with incompatible artifacts | Summary records model path and base reliability mode | Keep experiment report explicit about inputs and feature set. |

## Verification Plan

- Add a unit test that a supplied model overrides an event-posterior estimate and
  changes `_memory_first_decision` inputs.
- Add a CLI preflight test showing `--memory-validity-model` is accepted and
  recorded.
- Run focused Habitat closed-loop tests, pipeline/model tests, `py_compile`,
  full local core tests, and `git diff --check`.
- Pull to Linux and rerun the relocated `sofa` slice with the evidence-only
  learned model to confirm the row changes from `memory_first` to
  `frontier_first`.

## Research Relevance

This is the first bridge from learned offline memory-validity calibration to a
Habitat policy decision. It does not prove benchmark superiority, but it can
demonstrate the missing mechanism: a detector-backed, learned, pre-decision
validity signal causing a memory-vs-frontier policy flip on a stale-memory
relocation row.

## Open Questions

- Which feature set should become the default paper baseline: evidence-only,
  route-aware without relocation metadata, or the full audit feature set?
- Should the next model train on more stable/stale categories before any broad
  learned-policy matrix run?
