# Experiment Report: Official Detector Centering Sign Ablation YOLO Query Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Does inverting the detector bbox-center-to-turn sign break the
`memory_belief_frontier` detector centering/reacquisition loop observed in the
official Habitat YOLO diagnostic?

## Hypothesis

If the live Habitat camera/action convention is opposite the current local
controller assumption, initializing `detector_center_direction_sign=-1` should
reduce target loss after detector-centering actions, reduce reacquisition
oscillation, and possibly improve official success or SoftSPL.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini`, first four episodes |
| Simulator | Habitat-Lab official `ObjectNav-v1` environment |
| Key parameters | `memory_belief_frontier`, `max_episodes=4`, `max_steps=50`, `seed=313`, YOLO-World `yolov8s-worldv2.pt`, detector confidence `0.25`, generated YOLO memory prior, `detector_center_direction_sign=-1` |

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
    Path("runs/habitat_official_objectnav/memory_belief_frontier_inverted_center_sign_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1"),
    config_path="third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
    dataset_data_path="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
    scene_root="datasets/habitat/scene_datasets/hm3d",
    split="val_mini",
    policy="memory_belief_frontier",
    max_episodes=4,
    max_steps=50,
    seed=313,
    validate_habitat=True,
    memory_prior_path="runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json",
    memory_min_confidence=0.25,
    target_detector_adapter=detector,
    target_detector_min_confidence=0.25,
    detector_center_direction_sign=-1,
)
PY
```

## Artifacts

- `runs/habitat_official_objectnav/memory_belief_frontier_inverted_center_sign_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_belief_frontier_inverted_center_sign_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/detector_trace.json`
- `runs/habitat_official_objectnav/memory_belief_frontier_inverted_center_sign_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/policy_trace.json`

## Metrics

| Metric | Adaptive-servo default sign | Inverted sign |
|---|---:|---:|
| Official success | `0/4` | `0/4` |
| SPL | `0.0` | `0.0` |
| SoftSPL | `0.0009902771347611306` | `0.0009902771347611306` |
| Mean distance to goal | `5.880594372749329` | `5.880594372749329` |
| Detector calls | `196` | `196` |
| Detector detections | `224` | `224` |
| Target-match detections | `23` | `23` |
| `center_detector_target` decisions | `23` | `23` |
| `reacquire_detector_target` decisions | `22` | `22` |
| `fallback_occupancy_frontier` decisions | `148` | `148` |
| Action counts | `move_forward=49`, `turn_left=87`, `turn_right=60`, `stop=4` | `move_forward=49`, `turn_left=88`, `turn_right=59`, `stop=4` |

## Observations

- The manifest and summary recorded
  `detector_center_direction_sign=-1`, so the ablation was active.
- The first target-control action in the `tv_monitor` episode changed from
  `turn_right` to `turn_left`.
- The loop did not disappear. The policy still alternated between
  `center_detector_target` at heading about `-2.094` and
  `reacquire_detector_target` at the neighboring headings.
- The inverted run merely mirrored the default-sign sequence:
  detector-centering and reacquisition swapped left/right order, while target
  evidence and official metrics stayed unchanged.

## Result

This is negative evidence for the simple centering-sign hypothesis. The live
failure is not explained by a single inverted image-offset convention. The next
policy slice should stop spending effort on one-step sign and flip rules and
move to multi-frame detector evidence accumulation or learned local visual
servoing.

## Follow-up

- Keep `--detector-center-direction-sign` as an auditable ablation knob.
- Do not claim benchmark improvement from this run.
- Design a multi-frame detector evidence controller that owns local search
  across brief target dropouts and scores short action sequences instead of
  flipping one step at a time.
