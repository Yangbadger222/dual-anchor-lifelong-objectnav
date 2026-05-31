# Experiment Report: Official Detector Action-Effect Local Control YOLO Query Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Does an online action-effect detector controller reduce the
`center_detector_target` / `reacquire_detector_target` loop and improve
official Habitat ObjectNav metrics on the same four-episode YOLO diagnostic?

## Hypothesis

If the target is visible at the image edge but a centering turn immediately
loses it, recording that failed action effect should prevent repeated
turn/reacquire oscillation. Edge-tracking forward may improve distance-to-goal,
but official success may still require a stronger short-horizon local action
scorer.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini`, first four episodes |
| Simulator | Habitat-Lab official `ObjectNav-v1` environment |
| Key parameters | `memory_evidence_frontier`, `max_episodes=4`, `max_steps=50`, `seed=313`, YOLO-World `yolov8s-worldv2.pt`, detector confidence `0.25`, generated YOLO memory prior |

## Command

```bash
ssh badger@100.88.131.52
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python - <<'PY'
from pathlib import Path

from objectnav_core.evaluation.habitat_official_objectnav_eval import (
    run_habitat_official_objectnav_eval,
)
from objectnav_core.perception.yolo_world_adapter import YoloWorldDetector

detector = YoloWorldDetector(
    weights="yolov8s-worldv2.pt",
    categories=["bed", "chair", "plant", "sofa", "toilet", "tv_monitor"],
    conf=0.25,
    device="auto",
)
run_habitat_official_objectnav_eval(
    Path("runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1"),
    config_path="third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
    dataset_data_path="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
    scene_root="datasets/habitat/scene_datasets/hm3d",
    split="val_mini",
    policy="memory_evidence_frontier",
    max_episodes=4,
    max_steps=50,
    seed=313,
    validate_habitat=True,
    memory_prior_path="runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json",
    memory_min_confidence=0.25,
    target_detector_adapter=detector,
    target_detector_min_confidence=0.25,
)
PY
```

## Artifacts

- `runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/detector_trace.json`
- `runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/policy_trace.json`

## Metrics

| Metric | Adaptive-servo baseline | Action-effect policy |
|---|---:|---:|
| Official success | `0/4` | `0/4` |
| SPL | `0.0` | `0.0` |
| SoftSPL | `0.0009902771347611306` | `0.02518699682786324` |
| Mean distance to goal | `5.880594372749329` | `5.697803378105164` |
| Detector calls | `196` | `196` |
| Detector detections | `224` | `276` |
| Target-match detections | `23` | `4` |
| `center_detector_target` decisions | `23` | `1` |
| `reacquire_detector_target` decisions | `22` | `1` |
| `approach_detector_target_after_center_loss` decisions | `0` | `3` |
| `fallback_occupancy_frontier` decisions | `148` | `167` |
| `turn_toward_memory_belief_frontier` decisions | `3` | `24` |

## Observations

- The new action-effect path fired in the target `tv_monitor` episode.
- The first center turn lost the target; reacquisition restored the edge view;
  the policy then suppressed the failed `turn_right` action and moved forward
  for three steps.
- The target became closer by bbox depth during those approach steps, but the
  bbox center offset grew and the target disappeared after step `8`.
- The policy then fell back to memory-belief frontier turning, which did not
  recover an official success before the step budget.
- The lower target-match count is expected: the previous policy stayed parked
  at the target-visible heading by oscillating, while the new policy moved away
  from that view and got closer.

## Result

This is a partial positive diagnostic result, not a benchmark win. The
action-effect controller removed the pathological center/reacquire loop and
improved SoftSPL and distance-to-goal, but it did not solve any of the four
official episodes. The next policy needs a short-horizon local action scorer
that reasons over target evidence trends after edge-tracking, not only a
single failed centering action.

## Follow-up

- Keep `memory_evidence_frontier` as an explicit ablation policy.
- Add trace features for local target evidence trends: depth delta, area delta,
  offset delta, and action outcome.
- Use those traces to design or learn a short-horizon local visual-servo value
  model before broader benchmark comparisons.
