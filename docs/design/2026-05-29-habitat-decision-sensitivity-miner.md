# Design Doc: Habitat Decision Sensitivity Miner

Date: 2026-05-29
Owner: Codex
Status: Draft

## Goal

Create an offline analysis tool that mines existing Habitat closed-loop
`summary.json` artifacts for rows where memory reliability calibration is likely
to change ObjectNav decisions.

The tool should help choose targeted follow-up simulations instead of scaling
balanced slices that already proved to be too stable for `event_posterior` to
show a policy effect.

## Non-Goals

- Do not change runtime policy behavior.
- Do not claim benchmark improvement from mined candidates alone.
- Do not depend on Habitat, Grounding-DINO, GPU access, or robot hardware.
- Do not use oracle semantic overlap to compute policy-facing counterfactual
  reliability.
- Do not tune the reliability model from mined rows in this slice.

## Background

Recent Grounding-DINO per-action navmesh runs showed that
`event_posterior` changes memory-valid confidence but did not flip decisions in
balanced3 stable or stale slices. The next research bottleneck is selection:
we need rows where expected memory-first and frontier-first costs are close, the
current evidence is weak or stale, and detector confirmation events contain
enough mixed signal to matter.

Runtime summaries already contain the necessary row fields:

- memory, frontier, and post-memory frontier action counts;
- actual memory decision and decision bucket;
- evidence reliability components;
- detector event posterior components;
- hindsight best candidate and regret diagnostics.

An offline miner can use those fields without rerunning Habitat.

## System Boundary

The miner owns read-only parsing and scoring of closed-loop Habitat summaries.
It depends only on JSON/CSV files and pure Python arithmetic. It does not import
Habitat adapters, detector models, simulator state, or image assets.

The Habitat runner remains the source of truth for row semantics. The miner
should reproduce only the small expected-utility and reliability arithmetic
needed for counterfactual ranking.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Summary paths | `summary.json` files or directories | Directories are searched recursively for `summary.json` |
| Input | Filters | CLI options | Policies, top-k, close-margin threshold, minimum event count |
| Output | Mining report | JSON | Aggregate counts and ranked candidate rows |
| Output | Candidate table | CSV | Optional flat table for spreadsheet review |

## Interfaces

- Python API:
  - `mine_habitat_decision_sensitivity(inputs, ...) -> dict`
- CLI:
  - `python -m objectnav_core.cli.mine_habitat_decision_sensitivity <inputs...> --output <report.json>`
  - Optional `--csv-output <candidates.csv>`

Each candidate row should include:

- source summary path and run id;
- group id, category, policy, repeat index, challenge, detector, frontier mode,
  and route observation mode;
- actual reliability, actual decision, expected-memory and frontier costs;
- evidence-mode and event-posterior counterfactual reliability and decisions;
- decision margin to the expected-utility boundary;
- unclamped decision-boundary reliability and boundary region
  (`reliability_sensitive`, `memory_always_no_worse`,
  `frontier_requires_perfect_memory`, or `no_post_memory_fallback`);
- distance from the evidence/event-posterior reliability interval to the
  decision boundary, so rows just outside the flippable region can be targeted
  deliberately;
- detector event counts, event posterior, confirmed/suppressed weights;
- hindsight regret fields;
- a ranking score and short sensitivity reasons.

## Data Flow

1. Resolve each input into one or more `summary.json` paths.
2. Load each summary and iterate rows for the selected policies.
3. Read action counts, saved reliability components, actual decisions, event
   posterior components, and hindsight diagnostics.
4. Recompute:
   - evidence-style reliability from saved non-oracle components;
   - event-posterior reliability from saved event posterior components;
   - fixed-prior reliability from the saved base prior;
   - memory-first versus frontier-first decisions for each reliability.
5. Compute the raw reliability decision boundary. Rows with boundaries inside
   `(0, 1)` are genuinely reliability-sensitive; boundaries at or outside the
   interval mean one side dominates for all valid reliability estimates.
6. Score rows using reliability-sensitive boundaries, close expected costs,
   reliability deltas, mixed detector events, counterfactual decision flips,
   boundary-to-reliability-interval gap, and hindsight regret.
7. Write a sorted JSON report and optional CSV table.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Input path has no summaries | Report `summary_count=0` and no candidates | Keep CLI successful so batch scripts can inspect empty results |
| Summary uses older schema | Missing row fields during parsing | Skip invalid row and count a parse warning |
| Reliability components are absent | Candidate lacks counterfactual values | Fall back to row value where possible and record a warning |
| Counterfactual formula drifts from runtime | Focused tests comparing known row arithmetic | Keep formulas small and documented; runtime remains authoritative |
| Candidate is close but not actually useful | Report hindsight/regret and reasons instead of claiming improvement | Use miner output only to choose follow-up runs |

## Verification Plan

- Unit tests with synthetic summaries for:
  - close expected-cost row ranking;
  - evidence-versus-event-posterior counterfactual decision flips;
  - recursive directory input discovery;
  - JSON and CSV CLI output.
- Focused test command:
  `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py -q`
- Import/syntax check for the analyzer and CLI modules.
- `git diff --check`.

## Research Relevance

This tool directly supports the paper path by finding decision-sensitive
evaluation slices before expensive detector/Habitat runs. It helps distinguish
three cases that matter for a top-tier robotics claim:

- reliability signals that only calibrate confidence;
- reliability signals that flip decisions without improving regret;
- reliability signals that avoid harmful memory reuse or recover useful memory
  under stale, noisy, or drifted conditions.

The miner is not a result by itself. It is a reproducibility aid for selecting
the next experiment slice and later building a learned reliability model from
held-out row traces.

## Open Questions

- Should future mining include paired-run matching across `evidence` and
  `event_posterior` artifacts, or is single-summary counterfactual ranking
  sufficient for the next experiment?
- What threshold should define "close" once larger balanced runs are available?
