# Design Doc: Official Category-Balanced Rollout Export

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Add a category-balanced state cap to the official Habitat candidate-rollout
exporter so broad policy traces can seed counterfactual rollouts across target
categories instead of taking only the earliest active states.

## Non-Goals

- Do not change the rollout label semantics.
- Do not alter Habitat replay, branch actions, detector labeling, or official
  metric collection.
- Do not claim a policy improvement from the selected slice.
- Do not replace future dataset balancing; this is only a narrow collection
  control.

## Background

The first repeat-first action-matrix report was built from four 4-episode active
traces and produced a true always-left-failure slice of only `12/103` states,
all `tv_monitor`. A broader 20-episode discovery prior already exists on Linux
with `chair`, `sofa`, `tv_monitor`, and `bed` anchors. A fresh 20-episode
active-perception trace over that prior produced `805` active candidate states,
but the exporter only supports a global first-N `--max-states` cap. On ordered
Habitat traces, that can still over-sample whichever target appears first.

## System Boundary

The change belongs to the candidate-rollout exporter selection layer. It reads
existing policy-trace step fields and decides which candidate-bearing states to
branch. It does not inspect images, call detectors, change action policies, or
alter branch rollout execution.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | JSON | Existing official policy trace with `steps`. |
| Parameter | `max_states_per_category` | optional int | Maximum selected candidate states for each `target_category`. |
| Existing parameter | `max_states` | optional int | Still caps total selected states after per-category filtering. |
| Output | Rollout dataset | JSON/CSV | Existing schema plus `candidate_state_limit_per_category` metadata. |

## Interfaces

- Python API:
  `export_official_candidate_rollout_dataset(..., max_states_per_category=None)`
- CLI:
  `python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset <trace> --max-states-per-category 10 ...`

## Data Flow

1. Load policy trace steps.
2. Keep only steps with non-empty `memory_prior.top_candidates`.
3. If `max_states_per_category` is set, skip candidate states once their
   `target_category` reaches the cap.
4. Continue scanning in trace order until the optional global `max_states` cap
   is reached.
5. Replay and branch the selected states using the existing exporter path.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Category field missing | Empty `target_category` during selection | Bucket as an empty string; still deterministic. |
| Cap is zero or negative | CLI/API value normalizes to no per-category cap | Preserve current behavior unless a positive cap is supplied. |
| Early categories still dominate due global cap | `candidate_state_limit_per_category` and rollout categories reveal it | Prefer per-category cap without global cap for hard-state probes. |

## Verification Plan

- Add RED unit coverage showing the exporter keeps at most N candidate states
  per target category.
- Add RED CLI coverage for `--max-states-per-category`.
- Run focused rollout/exporter tests.
- Run the new control on the Linux 20-episode active-perception trace with a
  small per-category cap, then report and mine hard states.

## Research Relevance

This supports the paper-facing data story by making hard-state collection less
source/category skewed. It is not a final algorithmic contribution, but it
creates a cleaner substrate for evaluating learned local active-memory
controllers against simple global action baselines.

## Open Questions

- Should a future exporter use round-robin category selection when both
  per-category and global caps are set?
- Should balancing also account for scene id, source policy family, or selected
  memory-anchor category?
