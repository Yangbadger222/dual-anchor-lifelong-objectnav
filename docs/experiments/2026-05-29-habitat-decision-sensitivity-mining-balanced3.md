# Habitat Decision-Sensitivity Mining on Balanced3 Event-Posterior Summaries

Date: 2026-05-29
Owner: Codex
Status: Analysis smoke, not benchmark evidence

## Question

Do the existing balanced3 Grounding-DINO `event_posterior` summaries contain
memory-vs-frontier rows where the detector-event posterior would flip the
decision relative to evidence-mode reliability?

## Inputs

Linux workspace:

- Branch: `codex/habitat-memory-lifecycle`
- Commit after fast-forward: `2476009`
- Environment: conda env `habitat`

Summaries mined:

- `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_event_posterior_v1/summary.json`
- `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_stale_event_posterior_v1/summary.json`

Output artifacts:

- `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_balanced3_event_posterior_mining_v1/report.json`
- `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_balanced3_event_posterior_mining_v1/candidates.csv`

## Command

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
git pull --ff-only origin codex/habitat-memory-lifecycle
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py -q
PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.mine_habitat_decision_sensitivity \
  runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_event_posterior_v1/summary.json \
  runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_stale_event_posterior_v1/summary.json \
  --output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_balanced3_event_posterior_mining_v1/report.json \
  --csv-output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_balanced3_event_posterior_mining_v1/candidates.csv \
  --top-k 20
```

## Result

The miner completed successfully.

| Metric | Value |
|---|---:|
| summaries mined | 2 |
| memory-guided rows scanned | 9 |
| candidate rows reported | 9 |
| counterfactual decision flips | 0 |
| warnings | 0 |

Candidate reasons:

| Reason | Count |
|---|---:|
| mixed detector events | 9 |
| reliability delta | 6 |
| close expected costs | 2 |

Top candidates:

| Rank | Run | Category | Repeat | Event reliability | Evidence reliability | Margin actions | Decision flip | Reason |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | stable balanced3 | chair | 0 | 0.683481 | 0.96 | 2.050443 | no | close costs, mixed events, reliability delta |
| 2 | stable balanced3 | plant | 0 | 0.710654 | 0.96 | 357.421308 | no | mixed events, reliability delta |
| 3 | stale balanced3 | chair | 1 | 0.730507 | 0.96 | 3.808479 | no | close costs, mixed events, reliability delta |

## Interpretation

The current balanced3 event-posterior artifacts do contain cost-close rows, but
they still do not contain a row where detector-event reliability flips the
memory-vs-frontier decision relative to evidence-mode reliability.

The strongest next targets are the chair rows:

- Stable chair repeat 0 is very close to the decision boundary
  (`2.050443` actions) and has the largest reliability drop
  (`0.96 -> 0.683481`), but memory remains cheaper.
- Stale chair repeat 1 is also close (`3.808479` actions), but both evidence
  and event posterior still choose frontier because the repaired memory route
  remains more expensive than direct frontier.

This confirms the previous interpretation: the current balanced3 slices are
good for validating confidence calibration and safety gates, but still too
stable to demonstrate policy improvement from `event_posterior`.

## Caveats

- This is offline summary mining, not a Habitat policy rerun.
- The mined report uses saved row components and expected-utility arithmetic;
  the Habitat runner remains the authority for actual policy outcomes.
- No benchmark or SOTA claim follows from this analysis.
- The miner currently compares counterfactual reliability modes within each
  summary. It does not yet pair rows across independent evidence and
  event-posterior runs.

## Next Step

Mine a larger set of existing balanced6/stale/per-action summaries, then use the
top cost-close weak-evidence rows to configure a targeted Grounding-DINO run
where frontier and memory costs are genuinely near the reliability boundary.
