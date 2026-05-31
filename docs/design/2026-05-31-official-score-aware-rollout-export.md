# Design Doc: Official Score-Aware Rollout Export

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Add a score-aware candidate-state sampling mode to the official Habitat
candidate-rollout exporter so bounded probes can prioritize high-confidence
active-memory states instead of taking only the earliest states in trace order.

## Non-Goals

- Do not change rollout label semantics, branch actions, detector thresholds,
  or Habitat replay behavior.
- Do not integrate any new labels into the online policy.
- Do not claim benchmark or policy improvement from this diagnostic slice.
- Do not add learned sampling or phase balancing yet.

## Background

The category-balanced rollout probe showed that per-category caps prevent the
old all-`tv_monitor` collapse, but `chair` and `bed` still produced no recovery
under repeat-first labels. The current exporter selects candidate-bearing states
in trace order, so the selected `chair`/`bed` states may simply be weak or early
active-perception states. The policy trace already records ranked
`memory_prior.top_candidates` with `score`, `expected_evidence`, path distance,
and related metadata. A score-aware sampler can test whether higher-ranked trace
states make those categories recoverable before redesigning labels.

## System Boundary

This change belongs only to candidate-state selection inside the
candidate-rollout exporter. It consumes existing trace JSON and produces the
same rollout dataset schema with one added metadata field describing the
selection strategy. It does not alter environment setup, branch rollout actions,
detector evidence, or action-matrix reporting.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | JSON | Existing official policy trace with `steps`. |
| Parameter | `state_sampling` | enum string | `trace_order` keeps current behavior; `top_score_desc` sorts by top candidate score. |
| Parameter | `max_states_per_category` | optional int | Applies after sampling order is chosen. |
| Parameter | `max_states` | optional int | Applies after per-category filtering. |
| Output | Rollout dataset | JSON/CSV | Existing schema plus `candidate_state_sampling` metadata. |

## Interfaces

- Python API:
  `export_official_candidate_rollout_dataset(..., state_sampling="trace_order")`
- CLI:
  `python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset <trace> --state-sampling top_score_desc ...`

## Data Flow

1. Load policy trace steps.
2. Keep steps with non-empty `memory_prior.top_candidates`.
3. If `state_sampling=trace_order`, preserve existing step order.
4. If `state_sampling=top_score_desc`, sort candidate-bearing states by the
   first valid top-candidate score in descending order, with original trace
   order as the stable tie-breaker and missing scores last.
5. Apply the optional per-category cap and global cap.
6. Replay and branch selected states using the existing exporter path.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Candidate score missing or malformed | Sort key treats score as missing | Keep state eligible but place it after scored states. |
| Invalid sampling mode | API raises `ValueError`; CLI restricts choices | Fail before starting Habitat rollouts. |
| High-score mode over-selects one category | Dataset category counts reveal it | Use with `max_states_per_category` for bounded probes. |
| High-score states still unrecovered | Action-matrix positives remain absent | Treat as evidence for label/action redesign, not policy failure. |

## Verification Plan

- Add RED unit coverage showing `top_score_desc` selects higher-score states
  before per-category capping.
- Add RED CLI coverage for `--state-sampling`.
- Run focused exporter tests, the full objectnav core test suite, `compileall`,
  and `git diff --check`.
- Sync to Linux and run a bounded repeat-first action-matrix probe against the
  20-episode active-perception trace.

## Research Relevance

This is a diagnostic control for deciding whether the `chair`/`bed` failures in
the category-balanced probe came from poor state selection or from weak
repeat-first label semantics. A positive result would justify score-aware data
collection; a negative result would strengthen the case for exact state-restore
or candidate-viewpoint labels.

## Open Questions

- Should the next sampler combine score with active-perception phase?
- Should `top_score_desc` sort by top candidate score or by selected-candidate
  score when those diverge?
- Should future probes stratify by scene or source episode as well as category?
