# Habitat Decision-Sensitivity Broad Mining and Balanced6 Event-Posterior Check

Date: 2026-05-29
Owner: Codex
Status: Analysis and targeted smoke, not benchmark evidence

## Question

After adding boundary-region diagnostics, do existing Habitat summaries or a
targeted balanced6 Grounding-DINO run contain rows where detector-event
posterior reliability actually changes memory-vs-frontier decisions?

## Analyzer Update

The first broad mining pass showed that "close expected costs" can be
misleading. A row can have a small action margin while still being impossible
to flip because memory always dominates frontier, or frontier requires perfect
memory reliability.

The miner now records:

- `decision_boundary_reliability_raw`
- `decision_boundary_region`
- `reliability_sensitive_boundary`

Only rows with `0 < decision_boundary_reliability_raw < 1` are genuinely
reliability-sensitive.

## Broad Existing-Artifact Mining

Command output:

- Report:
  `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_broad_existing_v3_all/report.json`
- CSV:
  `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_broad_existing_v3_all/candidates.csv`

| Metric | Value |
|---|---:|
| summaries mined | 50 |
| memory-guided rows scanned | 206 |
| candidate rows | 144 |
| warnings | 0 |
| counterfactual flips | 0 |

Boundary regions:

| Region | Count |
|---|---:|
| reliability-sensitive | 95 |
| frontier requires perfect memory | 27 |
| memory always no worse | 18 |
| no post-memory fallback | 4 |

Detector-event rows remained non-flipping. The 10 rows with mixed detector
events or reliability deltas were all outside the flippable boundary region:
stable event-posterior rows mostly had `memory_always_no_worse`; stale chair
rows had `frontier_requires_perfect_memory`.

## Targeted Balanced6 Per-Action Event-Posterior Run

Run:

- `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced6_event_posterior_v1/summary.json`
- Detector: Grounding-DINO
- Frontier: `navmesh_frontier`
- Route observation: `per_action`
- Confirmation: `multiview`
- Reliability mode: `event_posterior`

Policy summary:

| Policy | Success | Actions | Hindsight regret | Buckets |
|---|---:|---:|---:|---|
| memory_guided | 6/6 | 473 | 0 | `memory_shorter_reused=2`, `memory_rescued_frontier_failure=2`, `frontier_shorter_selected=2` |
| naive_count | 6/6 | 473 | 0 | `naive_memory_reuse=6` |
| frontier_only | 4/6 | 1064 | 582 | `frontier_only=6` |

Mining result:

- Report:
  `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_balanced6_event_posterior_v1/report.json`
- Candidate rows: 6
- Counterfactual flips: 0
- Boundary regions: `memory_always_no_worse=4`,
  `frontier_requires_perfect_memory=2`

Interpretation: this stronger per-action run validates that memory remains much
better than frontier-only, but it still does not beat naive-count and does not
produce a reliability-sensitive event-posterior decision.

## Matched Option-End Balanced6 Evidence/Event-Posterior Runs

Runs:

- Evidence:
  `runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_evidence_multiview_option_end_v1/summary.json`
- Event posterior:
  `runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_event_posterior_option_end_v2/summary.json`

Both runs used:

- `route_observation_mode=option_end`
- `detector_confirmation_mode=multiview`
- the same six categories and navmesh settings

One excluded command attempted the event-posterior option-end run with an
incorrect depth-noise path and failed before producing metrics.

Matched result:

| Policy | Evidence actions | Event-posterior actions | Evidence success | Event-posterior success |
|---|---:|---:|---:|---:|
| memory_guided | 773 | 773 | 5/6 | 5/6 |
| naive_count | 573 | 573 | 5/6 | 5/6 |
| frontier_only | 2079 | 2079 | 1/6 | 1/6 |

The row decisions and buckets were identical:

| Category | Evidence decision | Event-posterior decision | Event-posterior reliability |
|---|---|---|---:|
| bed | memory_first | memory_first | 0.851508 |
| chair | memory_first | memory_first | 0.652413 |
| plant | memory_first | memory_first | 0.850697 |
| sofa | memory_first | memory_first | 0.852554 |
| toilet | memory_first | memory_first | 0.851003 |
| tv_monitor | frontier_first | frontier_first | 0.242777 |

Mining result for event posterior:

- Candidate rows: 6
- Reliability-sensitive boundaries: 3
- Counterfactual flips: 0

Mining result for matched evidence:

- Candidate rows: 3
- Reliability-sensitive boundaries: 3
- Counterfactual flips: 0

Interpretation: event posterior lowered reliability, but not enough to cross a
decision boundary. The poorer option-end aggregate compared with the older
single-frame evidence run is due to the multiview confirmation setting changing
verification behavior, not to the event-posterior reliability rule by itself.

## Conclusion

The current evidence says:

- The miner can now identify genuine reliability-sensitive boundaries.
- Existing detector-event posterior rows still do not cross those boundaries.
- Balanced6 per-action event posterior confirms memory beats frontier-only but
  still ties naive-count.
- Matched option-end evidence/event-posterior runs make identical decisions.

This is a useful negative result. It means the project should stop expecting
broad balanced slices to accidentally reveal the reliability benefit. The next
experiment should deliberately construct or select rows with all three
ingredients at once:

1. interior reliability boundary;
2. mixed confirmed/suppressed detector-event evidence;
3. enough posterior shift to cross the boundary.

## Next Step

Create a targeted decision-boundary slice from mined rows, likely by selecting
specific category/scene rows and adjusting only evaluation selection parameters
that are already part of the benchmark harness. Do not hand-tune the posterior
weights to force a win.
