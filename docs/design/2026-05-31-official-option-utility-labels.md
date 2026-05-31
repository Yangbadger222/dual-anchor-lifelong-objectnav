# Design Doc: Official Option-Utility Labels

Date: 2026-05-31
Owner: Codex
Status: Implemented; focused verification complete

## Goal

Extend the official candidate option-value dataset beyond binary detector
visibility. Each candidate option should also record whether it improves
official Habitat distance-to-goal, whether detector confidence increases, and
whether a supervision-only STOP probe after the option would satisfy Habitat
success.

The target is better learning signal for a memory-guided ObjectNav policy that
can eventually beat hand-score candidate selection by a meaningful margin.

## Non-Goals

- Do not use official target metrics or STOP-probe results online.
- Do not alter the active-perception controller in this slice.
- Do not claim benchmark performance from offline labels or tiny smokes.
- Do not add persistent `habitat_world` assumptions.
- Do not train a new default policy until the labels are validated on broader
  held-out sources.

## System Boundary

The change stays inside the official candidate-rollout dataset/export layer and
its CLI:

- `objectnav_core.evaluation.habitat_official_candidate_rollout_dataset`
- `objectnav_core.cli.export_habitat_official_candidate_option_value_dataset`
- focused candidate-rollout tests
- docs/devlog/handoff/experiment notes after verification

The candidate-viewpoint ranker can train on the new boolean labels by passing
`--label <label_name>`, but outcome fields are not online features.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Option progress threshold | float meters | Default `0.05`; turns distance deltas into a boolean label. |
| Input | Habitat metrics | `env.get_metrics()` | Offline supervision only. |
| Output | Utility fields | JSON/CSV | Initial/final/min distance, distance deltas, detector confidence gain, STOP-probe metrics. |
| Output | Utility labels | JSON/CSV | Boolean labels suitable for existing ranker training. |

New per-row fields:

- `initial_detector_confidence`
- `detector_confidence_gain`
- `initial_distance_to_goal_m`
- `final_distance_to_goal_m`
- `min_distance_to_goal_m`
- `distance_to_goal_delta_m`
- `best_distance_to_goal_delta_m`
- `stop_probe_success`
- `stop_probe_spl`
- `stop_probe_softspl`
- `stop_probe_distance_to_goal_m`

New labels:

- `detector_confidence_gain_within_option_rollout`
- `official_progress_within_option_rollout`
- `official_stop_success_after_option_rollout`

## Interfaces

API extension:

```python
export_official_candidate_option_value_dataset(
    ...,
    option_progress_threshold_m=0.05,
)
```

CLI extension:

```bash
python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset \
  <policy_trace.json> \
  --option-progress-threshold-m 0.05
```

Training examples:

```bash
python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
  <dataset.json> \
  --label official_progress_within_option_rollout \
  --output <model.json>
```

```bash
python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
  <dataset.json> \
  --label official_stop_success_after_option_rollout \
  --output <model.json>
```

## Data Flow

1. Replay to a candidate-bearing state as before.
2. Record current detector evidence and current official metrics.
3. Roll out the candidate option using live GPS/compass/depth.
4. After each option action, update:
   - best detector confidence;
   - final and minimum official `distance_to_goal`.
5. After the option horizon or early detector success, issue one offline-only
   `stop` action in that candidate branch and record official success/SPL/
   SoftSPL/distance.
6. Emit utility fields and labels in JSON and CSV.

The STOP probe is not part of `option_rollout_actions`; it is a separate
supervision measurement. It is allowed because each candidate already owns a
fresh branch environment.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| `env.get_metrics()` unavailable | metrics fields are `null` | Keep detector labels; mark official labels false. |
| Official distance missing | `initial_distance_to_goal_m is None` | Mark progress label false. |
| STOP probe raises or env already ended | `stop_probe_*` fields remain `null` | Keep row valid if option rollout itself was valid. |
| STOP probe changes detector trace | no detector call during STOP probe | Record only official metrics after STOP. |
| Outcome fields leak online | ranker feature list remains unchanged | Tests assert outcome fields are not model features. |

## Verification Plan

1. RED test: option-value rows record detector confidence gain and the matching
   gain label.
2. RED test: option-value rows record official distance progress and set
   `official_progress_within_option_rollout` when the best distance improves by
   at least the threshold.
3. RED test: STOP-probe success is recorded separately from
   `option_rollout_actions`.
4. RED test: CLI forwards `--option-progress-threshold-m`.
5. RED test: the candidate-viewpoint ranker does not include option outcome
   fields as features when trained on the enriched dataset.
6. Run focused candidate-rollout and ranker tests, compileall, CLI help,
   `git diff --check`, touched-file whitespace scan, and Linux focused tests.

## Implementation Notes

The option-value exporter now records detector confidence gain, official
distance-to-goal deltas, and a separate offline STOP probe for each valid
candidate option branch. The STOP probe calls `stop` after the option rollout
but does not append that action to `option_rollout_actions`; it is a privileged
labeling measurement only.

The implementation deliberately keeps ranker feature extraction on the existing
explicit allowlist. Outcome fields such as `distance_to_goal_delta_m` and
`stop_probe_success` are not available as online features.

Focused fake-env tests cover:

- detector confidence gain;
- official distance progress;
- STOP-probe success;
- CLI threshold pass-through;
- ranker feature-leak guard.

Linux no-detector Habitat smoke:

`runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_nodetector_1state_20260531_v1`

The smoke exported `1` state, `2` candidate options, `0` invalid options, and
confirmed the new official metric fields are populated against Habitat's
`get_metrics()` interface. Both candidates had `0.0` distance progress and
STOP-probe success `0.0`, so this is a schema/boundary check, not a policy
result.

## Research Relevance

Binary target visibility is too weak for the long-term paper goal. A candidate
that briefly sees the target but cannot improve official progress or support a
valid STOP is not enough for ObjectNav. These labels move supervision closer to
the official benchmark while preserving the boundary between offline privileged
labels and online sensor-only policy execution.
