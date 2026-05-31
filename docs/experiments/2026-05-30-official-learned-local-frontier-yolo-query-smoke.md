# Experiment Report: Official Learned Local Frontier YOLO Query Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed; diagnostic negative result

## Question

Does the `memory_learned_local_frontier` policy improve official Habitat
ObjectNav metrics by using the learned local action-effect scorer online?

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini`, first four episodes |
| Simulator | Habitat-Lab official `ObjectNav-v1` environment |
| Policy | `memory_learned_local_frontier` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Memory prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |
| Local action model | `runs/habitat_official_objectnav/local_action_effect_model_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/model.json` |
| Key parameters | `max_episodes=4`, `max_steps=50`, `seed=313`, `memory_min_confidence=0.25` |

## Commands

Focused local and Linux gates:

```bash
PYTHONPATH=src/objectnav_core pytest -q \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_local_action_dataset.py \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_ros_packaging.py
```

Fixed YOLO smoke:

```bash
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
    Path("runs/habitat_official_objectnav/memory_learned_local_frontier_suppressed_failed_turns_yolo_discovery_prior_local_action_model_trace_4ep_50steps_20260530_v1"),
    config_path="third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml",
    dataset_data_path="datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz",
    scene_root="datasets/habitat/scene_datasets/hm3d",
    split="val_mini",
    policy="memory_learned_local_frontier",
    max_episodes=4,
    max_steps=50,
    seed=313,
    validate_habitat=True,
    memory_prior_path="runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json",
    memory_min_confidence=0.25,
    target_detector_adapter=detector,
    target_detector_min_confidence=0.25,
    local_action_model_path="runs/habitat_official_objectnav/local_action_effect_model_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/model.json",
)
PY
```

## Artifacts

- Initial learned-local smoke:
  `runs/habitat_official_objectnav/memory_learned_local_frontier_yolo_discovery_prior_local_action_model_trace_4ep_50steps_20260530_v1`
- Fixed learned-local smoke:
  `runs/habitat_official_objectnav/memory_learned_local_frontier_suppressed_failed_turns_yolo_discovery_prior_local_action_model_trace_4ep_50steps_20260530_v1`
- Comparison baseline:
  `runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`

## Metrics

| Metric | Evidence frontier | Learned local, initial | Learned local, failed-turn suppression |
|---|---:|---:|---:|
| Official success | `0/4` | `0/4` | `0/4` |
| SPL | `0.0` | `0.0` | `0.0` |
| SoftSPL | `0.02518699682786324` | `0.0009902771347611306` | `0.02518699682786324` |
| Mean distance to goal | `5.697803378105164` | `5.880594372749329` | `5.697803378105164` |
| Detector calls | `196` | `196` | `196` |
| Detector detections | `276` | `194` | `272` |
| Target-match detections | `4` | `23` | `5` |
| `center_detector_target` decisions | `1` | `1` | `1` |
| `reacquire_detector_target` decisions | `1` | `22` | `2` |
| `learned_local_action_score` decisions | `0` | `22` | `4` |
| `approach_detector_target_after_center_loss` decisions | `3` | `0` | `0` |
| `fallback_occupancy_frontier` decisions | `167` | `148` | `166` |
| `turn_toward_memory_belief_frontier` decisions | `24` | `3` | `23` |

## Trace Findings

The first learned-local run exposed a policy-boundary bug. In the target
`tv_monitor` episode, after the policy had recorded `turn_left` as a failed
detector-centering action for the current bbox offset sign, the scorer was
still allowed to choose `turn_left`. That recreated the old
center/reacquire loop: `22` learned-local turns paired with `22` reacquisition
turns.

The fixed policy suppresses failed turn candidates before scoring. In the
target episode:

- step `4`: `center_detector_target` chose `turn_right` and lost the target;
- step `5`: `reacquire_detector_target` returned with `turn_left`;
- step `6`: learned scorer chose `turn_left` while suppressing failed
  `turn_right`;
- step `7`: reacquisition recorded `turn_left` as failed too;
- steps `8` through `10`: both failed turns were suppressed, so only
  `move_forward` remained and the policy moved forward.

The forward moves reduced detector depth from about `0.403` to `0.312`, but
bbox area fell and center offset grew from about `0.432` to `0.479`; target
evidence then disappeared and the policy fell back to memory-belief frontier.

## Interpretation

This is not a benchmark win. Failed-turn candidate suppression fixes the online
loop regression and restores the action-effect baseline's SoftSPL and
distance-to-goal, but it does not improve official success or SPL. The result
supports the broader diagnosis: a one-step next-visibility scorer is too weak
for the local target-control problem. The next serious policy should use
multi-frame evidence trends, short-horizon action sequences, or a controller
trained on substantially larger official traces.

## Verification

- Local focused official gate: `80` passed.
- Local `compileall`: passed.
- Local `git diff --check`: clean.
- Linux focused official gate in env `habitat`: `80` passed.
- Linux `compileall`: passed.
- Linux `git diff --check`: clean.
- Linux four-episode YOLO smoke completed and wrote the fixed learned-local
  artifact above.
