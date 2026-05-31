# Design Doc: Official Online Option-Value Labels

Date: 2026-05-31
Owner: Codex
Status: Implemented; smoke complete; not benchmark-valid

## Goal

Create a supervision artifact that labels each active-perception candidate by
the detector evidence it produces under the same short-horizon option controller
used online: commit to the selected viewpoint, move or turn using live
GPS/compass/depth, scan at the reached or blocked viewpoint, and record whether
the target category becomes visible.

This replaces the current direct transfer target for learned reranking. The
model should learn online option utility, not just teleport/restore visibility.

## Non-Goals

- Do not claim official ObjectNav success or SPL improvement from this labeler.
- Do not use oracle target pose, semantic ground truth, persistent
  `habitat_world` memory, or a prior map at action time.
- Do not replace official Habitat metrics or leaderboard protocols.
- Do not tune the controller to the four-episode smoke.
- Do not add GPT/language control in this slice.

## Background

The candidate-viewpoint restore dataset showed strong offline signal:
candidate viewpoints often revealed the target when the current view did not.
The online learned ranker did not transfer. A controller-mismatch diagnostic
then showed that adding short-lived commitment and a blocked-target scan
recovered partial detector evidence, but the no-ranker hand-score policy matched
the learned no-rank policy exactly on the same smoke.

The next supervision target must therefore execute the same option semantics
that the policy will use online. The label should answer: if we choose this
candidate now and let the active-perception option run for a short horizon,
does it create target detector evidence or official progress?

Approaches considered:

| Approach | Pros | Cons | Decision |
|---|---|---|---|
| Keep teleport/heading-sweep labels and add more features | Cheap and already implemented | Proven mismatch with online controller | Reject as direct policy target |
| Roll out fixed first actions only | Tests local action effects | Does not represent candidate viewpoint commitment | Keep as action ablation, not candidate value |
| Roll out candidate options with live pose/depth updates | Matches the policy option more closely and remains simulator-first | More complex labels and slower export | Use for next supervision slice |

## System Boundary

Modify the official candidate-rollout evaluation layer:

- `objectnav_core.evaluation.habitat_official_candidate_rollout_dataset`
- new CLI wrapper for option-value export
- focused candidate-rollout tests
- docs/devlog/handoff/experiment notes after a smoke

The exporter owns candidate-state selection, top-K candidate expansion,
short-horizon candidate-option execution, detector evidence labels, JSON output,
and CSV output. It depends on existing policy traces, official Habitat replay,
detector adapters, and the same episode-relative coordinate conventions already
used by active-perception candidates.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | JSON | Must include `memory_prior.top_candidates`. |
| Input | Habitat env | Habitat env or fake test env | Replayed to the logged decision state. |
| Input | Detector adapter | Python object | Same `detect(rgb)` contract as existing exporters. |
| Input | Option horizon | integer | Short rollout budget, default planned as `8` steps. |
| Input | Scan steps | integer | Bounded local scan at reached/blocked option target. |
| Output | Option-value dataset | JSON | One row per candidate option. |
| Output | CSV | CSV | Stable schema for audits and model training. |

Each candidate row should record:

- source trace, episode, scene, target category, step, and decision metadata
- candidate rank/count, score, geometry, and state features
- episode-relative candidate `x/z` derived from candidate fields or
  `viewpoint_cell`
- option rollout actions and option phase counts
- current-view detector evidence
- target evidence within the option rollout
- hidden-to-visible option label

## Interfaces

New API:

- `export_official_candidate_option_value_dataset(...)`
- `write_official_candidate_option_value_dataset_csv(...)`

New CLI:

```bash
python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset \
  <policy_trace.json> \
  --output <dataset.json> \
  --csv-output <labels.csv> \
  --candidates-per-state 5 \
  --option-horizon-steps 8 \
  --option-scan-steps 4 \
  --state-sampling active_phase_path
```

The dataset should use `candidate_viewpoints` as its row key so the existing
candidate-viewpoint ranker can train on it by passing:

```bash
python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
  <option_dataset.json> \
  --label hidden_to_visible_within_option_rollout \
  --output <model.json>
```

## Data Flow

1. Load the policy trace and select candidate-bearing states with existing
   sampling logic.
2. Replay official Habitat actions to the logged state.
3. Measure current target detector evidence at the replayed state.
4. For each top-K candidate, derive episode-relative candidate `x/z` from
   `candidate_x_m`/`candidate_z_m` when present, otherwise from
   `viewpoint_cell` or `frontier_cell`.
5. Start a short option rollout from the replayed state.
6. At each option step, use the current observation GPS/compass/depth to choose
   an action:
   - if not within one grid cell of the candidate, turn toward the candidate or
     move forward when aligned and clear;
   - if aligned but blocked, run a bounded local scan before fallback;
   - if at the candidate, orient toward the remembered anchor if possible and
     run a bounded scan;
   - stop the option when target evidence appears, the horizon is exhausted, or
     the episode ends.
7. Record action sequence, option phases, detector evidence, and labels.
8. Write JSON and CSV outputs.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Replay fails before state | `valid_option_rollout=false` | Keep row with label unavailable and invalid reason. |
| Candidate pose unavailable | no `candidate_x/z`, invalid cell | Mark row invalid, not negative. |
| Observation lacks GPS/compass | pose fields unavailable | Fall back to candidate bearing for first action, then scan. |
| Detector unavailable | no adapter or missing RGB | Keep row with `label_available=false`. |
| Option cannot reach candidate due blocked depth | blocked phase count rises | Scan once, then mark no target evidence if still hidden. |
| Labeler drifts from online policy | focused tests compare action decisions | Keep controller constants shared or explicitly documented. |
| Labels become too expensive | runtime grows with states/candidates/horizon | Keep caps by state/category/episode and start with small smoke. |

## Verification Plan

1. RED test: option-value export emits `candidate_viewpoints` rows with
   `hidden_to_visible_within_option_rollout` labels and current-hidden status.
2. RED test: dynamic option actions turn toward a candidate using live
   GPS/compass, then move forward when aligned and clear.
3. RED test: blocked candidate approach performs bounded local scan before
   declaring no evidence.
4. RED test: invalid replay or invalid candidate pose keeps the row auditable
   and not a false negative.
5. RED test: CLI writes JSON and CSV and passes option horizon/scan arguments.
6. Run focused candidate-rollout tests, compileall, `git diff --check`, and a
   touched-file whitespace scan.
7. Sync touched files to Linux and run the focused tests in conda env
   `habitat`.
8. Export a bounded YOLO option-value smoke from the matched four-episode
   policy trace and compare oracle-recoverable candidate states against the
   teleport/restore labels.

## Implementation Notes

The implementation adds the separate option-value API and CLI:

- `export_official_candidate_option_value_dataset(...)`
- `write_official_candidate_option_value_dataset_csv(...)`
- `python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset`

Rows are emitted under `candidate_viewpoints` for compatibility with the
candidate-viewpoint ranker trainer. The trainer can use the new target through:

```bash
--label hidden_to_visible_within_option_rollout
```

The trainer's state-fold and leave-one-source evaluation paths now also receive
the custom label name. This matters because the first implementation trained on
the option label but silently evaluated folds against the older restore label.

The option-value rollout controller is intentionally local to the exporter. It
uses live observation GPS/compass/depth during each branch rollout and preserves
the project coordinate convention:

- Habitat GPS is `[forward, right]`.
- Candidate coordinates use `x=right, z=forward`.
- Labels are episode-relative and do not use persistent `habitat_world`.

## Smoke Results

Linux artifact:

`runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1`

Dataset summary:

- states: `8`
- candidate options: `40`
- invalid options: `0`
- hidden-to-visible option positives: `16`
- oracle-recoverable states: `8/8`
- top-rank recovered states: `0/8`
- top-score recovered states: `0/8`
- positive candidate ranks: rank `2` on `8` rows, rank `3` on `8` rows

Tiny same-trace ranker artifact:

`runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2`

The model uses `44` features and the label
`hidden_to_visible_within_option_rollout`. Training metrics on the tiny artifact
are accuracy `1.0` and ROC-AUC `1.0`; state-fold diagnostics report model
`8/8`, oracle `8/8`, top-rank `0/8`, and top-score `0/8`. This is useful only as
a learnability and plumbing check, not independent evidence.

Matched online diagnostic artifact:

`runs/habitat_official_objectnav/option_value_ranker_guided_active_perception_yolo_4ep_50steps_20260531_v1`

Matched online comparison under the sticky plus blocked-scan controller:

| Run | Success | SPL | SoftSPL | Target-Match Calls | Target-Match Detections |
|---|---:|---:|---:|---:|---:|
| Hand-score selector | `0/4` | `0.0` | `0.02518699682786324` | `4` | `4` |
| No-`candidate_rank` ranker | `0/4` | `0.0` | `0.02518699682786324` | `4` | `4` |
| Option-value ranker | `0/4` | `0.0` | `0.02518699682786324` | `4` | `4` |

The option-value ranker did change online candidate choice: over `44`
ranker-active steps it selected hand-score rank `3` on `40` steps, rank `2` on
`2` steps, and rank `4` on `2` steps. The policy outcome nevertheless matched
the hand-score controller exactly on official metrics and target detector
evidence.

Interpretation:

- The option-value label is a sharper supervision substrate than top-rank
  hand-score on this tiny trace.
- The same-trace ranker is not enough to produce an online policy win.
- The active online bottleneck is now downstream of candidate rank choice for
  this four-episode smoke: local continuation, detector reacquisition, and
  success stopping still dominate.
- This result is not benchmark-valid because the memory prior and tiny training
  artifact are diagnostic smokes, not independent official evaluation inputs.

## Research Relevance

This is the bridge from a hand-scored memory search option to a learned
candidate-value policy that can plausibly support a robotics paper. It keeps the
memory story tied to lifelong ObjectNav: the robot stores episode-relative
object anchors, generates reachable inspection options, and learns which option
is likely to produce real downstream evidence under its own controller. If this
label family yields a selector that beats hand-score under official action
execution, it becomes a credible algorithmic contribution. If it does not, the
negative result will still clarify whether the bottleneck is memory anchoring,
candidate generation, detector reliability, or local control.

## Open Questions

- Should the primary utility be binary target evidence, time-discounted target
  evidence, official distance progress, or a weighted mixture?
- How large should the option horizon be before the label starts to reward
  general exploration rather than candidate inspection?
- Should blocked-scan labels be separated from reached-viewpoint labels so the
  model can learn different uncertainty modes?
