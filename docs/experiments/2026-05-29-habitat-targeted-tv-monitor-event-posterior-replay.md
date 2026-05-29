# Experiment Report: Targeted Tv Monitor Event-Posterior Replay

Date: 2026-05-29
Owner: Codex
Status: Completed diagnostic and control verification, not benchmark evidence

## Question

Does the next interval-gap candidate, `tv_monitor`, replay as a flippable
detector-event posterior decision boundary under the explicit `selected_group_ids`
interface?

## Candidate Rationale

The interval-gap broad mining report
`runs/habitat_closed_loop_dual_anchor/decision_sensitivity_broad_existing_v5_interval_gap_full/report.json`
left one untried event-signal candidate near the reliability interval boundary:

- Group:
  `hm3d/val/00813-svBbv1Pavdk/svBbv1Pavdk.basis.glb|tv_monitor|goal_object:287`
- Source run:
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced6_event_posterior_v1/summary.json`
- Mined broad row:
  `memory_action_count=24`, `fallback_action_count=24`,
  `fallback_from_memory_action_count=2`,
  `decision_boundary_reliability_raw=1.0`,
  `reliability_interval=[0.6078, 0.96]`,
  `boundary_reliability_interval_gap=0.04`, and
  `detector_event_count=4`.

This looked similar to the targeted `sofa` edge case, but was worth replaying
because it had a larger event-posterior reliability delta.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `f68fbd4` |
| Machine | Linux `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | HM3D ObjectNav `val` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Detector confirmation | `multiview`, 2 frames, 0.05 m / 5 deg / 0.05 IoU |
| Frontier | `navmesh_frontier` |
| Route observation | `per_action` |
| Reliability mode | `event_posterior` |
| Challenge | `stable` |

## Commands

Selected-group replay:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_tv_monitor_event_posterior_selected_group_v1 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 6 \
  --selected-group-ids "hm3d/val/00813-svBbv1Pavdk/svBbv1Pavdk.basis.glb|tv_monitor|goal_object:287" \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stable \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode event_posterior \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 5 \
  --frontier-probe-heading-count 4 \
  --route-observation-mode per_action \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --grounding-dino-max-image-side 384 \
  --rgb-noise-profile configs/noise/rgb_published_v1.yaml \
  --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml \
  --noise-level clean \
  --min-target-pixels 24 \
  --min-detector-pixels 20 \
  --max-detection-area-ratio 0.7 \
  --detector-prompt-mode target \
  --detector-confirmation-mode multiview \
  --detector-confirmation-frames 2 \
  --detector-confirmation-min-translation 0.05 \
  --detector-confirmation-min-rotation-deg 5.0 \
  --detector-confirmation-min-mask-iou 0.05
```

Decision-sensitivity mining:

```bash
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.mine_habitat_decision_sensitivity \
  runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_tv_monitor_event_posterior_selected_group_v1 \
  --output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_tv_monitor_selected_group_event_posterior_v1/report.json \
  --csv-output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_tv_monitor_selected_group_event_posterior_v1/candidates.csv
```

## Results

The explicit replay selected exactly one group:

| Field | Value |
|---|---|
| `selection_mode` | `explicit_group_ids` |
| `selected_group_count` | `1` |
| `selected_group_ids` | `hm3d/val/00813-svBbv1Pavdk/svBbv1Pavdk.basis.glb\|tv_monitor\|goal_object:287` |

Policy aggregates:

| Policy | Success | Actions | Distance (m) | Bucket |
|---|---:|---:|---:|---|
| `memory_guided` | 1/1 | 24 | 3.255062 | `memory_shorter_reused` |
| `frontier_only` | 1/1 | 236 | 33.093483 | `frontier_only` |
| `naive_count` | 1/1 | 24 | 3.255062 | `naive_memory_reuse` |

Mined decision row:

| Metric | Value |
|---|---:|
| `memory_action_count` | 24 |
| `fallback_action_count` | 236 |
| `fallback_from_memory_action_count` | 2 |
| `evidence_reliability` | 0.960000 |
| `event_posterior_reliability` | 0.607800 |
| `detector_event_count` | 4 |
| `detector_event_confirmed_weight` | 1.778550 |
| `detector_event_suppressed_weight` | 4.350000 |
| `detector_event_posterior` | 0.319637 |
| `reliability_delta` | 0.352200 |
| `decision_boundary_reliability_raw` | -105.000000 |
| `decision_boundary_region` | `memory_always_no_worse` |
| `boundary_reliability_interval_gap` | 105.607800 |
| `evidence_decision` | `memory_first` |
| `event_posterior_decision` | `memory_first` |
| `counterfactual_decision_flip` | false |

## Replay-Control Diagnostic

This selected replay did not reproduce the mined broad row's frontier route
accounting. The broad row used:

| Run | `memory_action_count` | `fallback_action_count` | Fallback source |
|---|---:|---:|---|
| Balanced6 broad source | 24 | 24 | `navmesh_frontier_probe:0:step:23` |
| Selected one-group replay | 24 | 236 | `navmesh_frontier_probe:4:step:21` |

The memory route evidence was unchanged (`goal_viewpoint:0:route:step:23`), but
the frontier route changed. Code inspection found the cause: navmesh frontier
probe seeds and detector frame-index bases were derived from `len(rows)`. In a
balanced6 run, the `tv_monitor` group is evaluated after earlier groups; in a
one-group explicit replay, it is evaluated first. Therefore the selected replay
changed the target-agnostic frontier probes while trying to isolate only the
group selection.

## Stable Replay-Control Rerun

The runner was updated in commit `d963151` so navmesh frontier seeds are derived
from `group_id` plus route context, and detector frame-index bases are derived
from `group_id`.

Two Linux reruns then verified the fix:

| Artifact | Purpose |
|---|---|
| `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_tv_monitor_event_posterior_selected_group_stable_replay_controls_v1/summary.json` | One-group `tv_monitor` replay under stable controls |
| `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_tv_monitor_selected_group_stable_replay_controls_v1/report.json` | One-group mined decision report |
| `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_sofa_tv_monitor_event_posterior_selected_groups_stable_replay_controls_v1/summary.json` | Two-group `sofa,tv_monitor` replay under stable controls |
| `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_sofa_tv_monitor_selected_groups_stable_replay_controls_v1/report.json` | Two-group mined decision report |

The stable one-group replay now reproduces the broad-row route accounting:

| Run | `memory_action_count` | `fallback_action_count` | Fallback source |
|---|---:|---:|---|
| Balanced6 broad source | 24 | 24 | `navmesh_frontier_probe:0:step:23` |
| Stable one-group replay | 24 | 24 | `navmesh_frontier_probe:0:step:23` |
| Stable `sofa,tv_monitor` replay | 24 | 24 | `navmesh_frontier_probe:0:step:23` |

The mined `tv_monitor` row is therefore a confirmed boundary-edge negative:

| Metric | Stable Value |
|---|---:|
| `memory_action_count` | 24 |
| `fallback_action_count` | 24 |
| `fallback_from_memory_action_count` | 2 |
| `event_posterior_reliability` | 0.607800 |
| `detector_event_count` | 4 |
| `reliability_delta` | 0.352200 |
| `decision_boundary_reliability_raw` | 1.000000 |
| `decision_boundary_region` | `frontier_requires_perfect_memory` |
| `boundary_reliability_interval_gap` | 0.040000 |
| `evidence_decision` | `frontier_first` |
| `event_posterior_decision` | `frontier_first` |
| `counterfactual_decision_flip` | false |

The two-group stable replay also reproduced the `sofa` negative:
`memory_action_count=63`, `fallback_action_count=63`,
`fallback_from_memory_action_count=2`, and
`decision_boundary_reliability_raw=1.0`.

## Interpretation

The `tv_monitor` replay confirms detector-event signal:

- Event posterior lowered reliability from `0.96` to `0.6078`.
- The runtime event history included confirmed and suppressed detector
  confirmations.

It does not provide policy-improvement evidence. Under stable replay controls,
the row is a `frontier_requires_perfect_memory` boundary edge: evidence and
event-posterior reliability both choose frontier, and neither can flip the
policy without perfect reliability.

## Conclusion

The immediate result is a reproducibility/control finding, not a policy result:

- `tv_monitor` did not demonstrate an event-posterior policy flip;
- stable replay controls now reproduce the mined route accounting in one-group
  and two-group selected replays;
- the currently tested `sofa` and `tv_monitor` rows both have event signal but
  sit on the `boundary=1.0` edge, so they are not flippable posterior cases.
