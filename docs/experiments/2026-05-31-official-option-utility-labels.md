# Experiment Report: Official Option-Utility Label Smoke

Date: 2026-05-31
Owner: Codex
Status: Completed; schema/boundary verification and tiny YOLO support check

## Question

Do the enriched option-utility fields populate correctly against real Habitat
official metrics, without using a detector or claiming policy performance?

## Hypothesis

The option-value exporter should be able to record `distance_to_goal` deltas and
STOP-probe official metrics through Habitat's `env.get_metrics()` boundary for
each candidate branch.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `0f14893` plus uncommitted research changes |
| Machine | Linux mirror `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | Habitat ObjectNav HM3D `val_mini` |
| Source trace | `runs/habitat_official_objectnav/memory_active_perception_frontier_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1/policy_trace.json` |
| Detector | `none` |
| State cap | `1` state, `2` candidates |

## Command

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset \
    runs/habitat_official_objectnav/memory_active_perception_frontier_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1/policy_trace.json \
    --output runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_nodetector_1state_20260531_v1/dataset.json \
    --csv-output runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_nodetector_1state_20260531_v1/labels.csv \
    --detector none \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-states 1 \
    --state-sampling active_phase_path \
    --candidates-per-state 2 \
    --option-horizon-steps 4 \
    --option-scan-steps 2 \
    --option-progress-threshold-m 0.05 \
    --seed 313
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Candidate states | `1` | active-phase sampled |
| Candidate options | `2` | top `2` candidates |
| Invalid options | `0` | replay and option pose valid |
| Positive detector options | `0` | detector disabled |
| Initial distance | `6.82320690155` | both rows |
| Final distance | `6.82320690155` | both rows |
| Best distance delta | `0.0` | no progress in this tiny smoke |
| STOP-probe success | `0.0` | both rows |

## Observations

- New fields were present in JSON for both rows:
  `initial_distance_to_goal_m`, `final_distance_to_goal_m`,
  `min_distance_to_goal_m`, `distance_to_goal_delta_m`,
  `best_distance_to_goal_delta_m`, and `stop_probe_success`.
- `option_rollout_actions` did not include `stop`; the STOP probe is recorded
  separately.
- Official progress and STOP-success labels were both false for this state.

## Result

The enriched option-utility schema works against real Habitat official metrics.
This does not demonstrate policy improvement; it only verifies the data boundary
needed for future training labels.

## YOLO Label-Support Follow-Up

After the schema smoke, the same bounded four-episode YOLO trace was re-exported
with the enriched utility labels:

`runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_yolo_4ep_20260531_v1`

The run used the fixed sticky plus blocked-scan controller trace,
`active_phase_path` state sampling, `8` states, `5` candidates per state,
`8` option-horizon steps, `4` option-scan steps, and an official progress
threshold of `0.05` m. A support summary was written at:

`runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_yolo_4ep_20260531_v1/label_support.json`

| Label / field | Positive support | State support | Notes |
|---|---:|---:|---|
| `hidden_to_visible_within_option_rollout` | `16/40` | `8/8` | Positives at candidate ranks `2` and `3`. |
| `detector_confidence_gain_within_option_rollout` | `16/40` | `8/8` | Exactly matched hidden-to-visible positives on this artifact. |
| `official_progress_within_option_rollout` | `0/40` | `0/8` | No positive training support in this slice. |
| `official_stop_success_after_option_rollout` | `0/40` | `0/8` | No positive training support in this slice. |

The maximum `best_distance_to_goal_delta_m`, `distance_to_goal_delta_m`, and
`stop_probe_success` values were all `0.0`. The detector-confidence gain field
was populated on the `16` detector-positive rows, with gain `0.748715` in this
artifact.

Training selectors on official progress or STOP-success labels from this
artifact should be deferred because both targets are zero-support. The only
supported signal here is detector/evidence gain, which is equivalent to the
prior hidden-to-visible option label on this tiny slice.

## Follow-Up

- Scale the YOLO enriched export beyond this `8`-state diagnostic before using
  progress or STOP-success labels.
- Keep source/state separation when checking support counts for detector gain,
  official progress, and STOP success.
- Do not train candidate selectors on zero-support progress or STOP labels from
  this artifact.
