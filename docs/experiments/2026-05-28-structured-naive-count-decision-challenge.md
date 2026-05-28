# Experiment Report: Structured Naive-Count Decision Challenge

Date: 2026-05-28  
Owner: Codex  
Status: Completed

## Question

When the replay contains room/corridor-style structure, scene changes, negative
evidence, path-cost refreshes, and multi-object association ambiguity, does the
usability-memory policy avoid failures that a positive-only `naive_count`
baseline cannot avoid?

## Hypothesis

The previous Habitat fixed replay was too favorable to `naive_count`: repeated
visible positives are enough for a positive-count baseline to look competitive.
In a structured trace where targets can disappear, become unusable, or collide
with nearby same-class memories, `naive_count` should accumulate stale or ghost
trust while `usability_memory` should use negative evidence and association
guards to reduce those failures.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, base `f0ed6c3` with this report's implementation changes |
| Machine | macOS Darwin arm64 |
| Dataset / bag / map | Synthetic 2D grid trace |
| Simulator / robot | None |
| Key parameters | seed `17`, episodes `900`, steps per episode `8`, `naive_count` threshold `2` positives |
| Output | `runs/grid_trace/structured_naive_count_decision_challenge_seed17_ep900` |

## Command

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_grid_trace_experiment \
  --output runs/grid_trace/structured_naive_count_decision_challenge_seed17_ep900 \
  --seed 17 \
  --episodes 900 \
  --steps-per-episode 8
```

## Metrics

| Metric | `usability_memory` | `naive_count` | Notes |
|---|---:|---:|---|
| Events | `7200` | `7200` | Same trace for both policies |
| Raw trust decisions | `2011` | `2186` | Before shared current-positive gate |
| Gated trust decisions | `1129` | `945` | After the same decision-side gate |
| Gate rejections | `882` | `1241` | Raw trust rejected by missing valid current positive |
| Unsafe raw trust | `882` | `1241` | Raw trust while current evidence was not a valid positive |
| False-positive write pressure | `0` | `200` | Positive-only baseline would write ambiguous false positives |

### Scenario Highlights

| Scenario | `usability_memory` | `naive_count` | Interpretation |
|---|---:|---:|---|
| `removed_or_moved` unsafe raw trust | `7` | `600` | `naive_count` keeps trusting after two early positives; memory decays and retires |
| `removed_or_moved` final decision | `retire` | raw `trust`, gated `verify` | The shared gate prevents bad stops, but does not fix the baseline's stale belief |
| `multi_object_association` false-positive write pressure | `0` | `200` | JPDA-style rejection blocks ghost writes that a positive counter would accept |
| `multi_object_association` unsafe raw trust | `397` | `500` | Both policies remain stressed, but naive counting is worse |
| `stale_path_cost` decision flips after refresh | `700` | n/a | Fresh path-cost refresh is still required before trusting navigation cost |

Shared trace metrics:

| Metric | Value |
|---|---:|
| Total events | `7200` |
| Positive evidence | `1733` |
| Non-confirmation evidence | `1250` |
| Access-blocked evidence | `1080` |
| Unknown evidence | `1537` |
| Scene-change evidence | `100` |
| Association events | `1600` |
| Nearest-neighbor wrong associations | `200` |
| JPDA rejected ambiguous events | `400` |
| Ghost positive writes prevented | `200` |
| Stale-cost events | `800` |
| Decision flips after cost refresh | `1200` |

## Observations

- The trace now makes `removed_or_moved` start with two positive observations
  before non-confirmation and scene-change evidence. This is the critical case:
  `naive_count` reaches its trust threshold honestly, then cannot recover when
  the memory becomes stale.
- The shared gate is doing its job for both policies. It converts bad raw trust
  into `verify`, so this experiment measures decision pressure rather than
  pretending raw trust is a successful stop.
- `naive_count` remains intentionally simple and fair to the user's constraint:
  it only counts positives, does not distinguish non-confirmation/unknown, does
  not delay birth, and does not use JPDA or geometry.
- The result supports a narrow algorithm claim: in structured replay, the
  memory updater and association guard reduce stale/ghost trust pressure beyond
  what positive-count accumulation can explain.
- This is not a Habitat navigation benchmark and should not be reported as SPL,
  success rate, or sim-to-real perception validation.

## Result

The structured decision challenge finally separates the memory algorithm from
the positive-count baseline. `naive_count` produces more raw trust
(`2186` vs `2011`) but less gated trust (`945` vs `1129`) and many more unsafe
raw-trust rows (`1241` vs `882`). The clearest failure is
`removed_or_moved`, where `naive_count` produces `600` unsafe raw-trust rows
after early positives, while `usability_memory` produces `7` and retires.

This means the next paper-facing task should not be another single-room fixed
replay. It should be a Habitat or logged replay with explicit structural
events: revisit after disappearance, blocked access, refreshed path cost, and
nearby same-class association ambiguity.

## Follow-up

- Port the structured challenge to Habitat by selecting episodes or scripted
  routes that contain room/corridor revisits, disappear/reobserve intervals,
  and nearby same-class distractors.
- Use `--episode-selection-strategy structured_visibility` as the first
  Habitat bridge. It is only a metadata prefilter, so inspect the selected
  episode IDs before making a paper claim.
- Keep the shared current-positive gate for all policies.
- Keep `naive_count` positive-only with threshold `2`; do not add negative
  evidence, delayed birth, JPDA, or geometry to the baseline.
- Add a navigation/follower layer only after the structured replay can be
  reproduced with real RGB/depth observations.
