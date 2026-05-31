# Experiment Report: Official Temporal Learned-Local Model Comparison YOLO Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed diagnostic; negative official online result

## Question

Which temporal local-action model is most credible for the official
`memory_learned_local_frontier` query policy, and does it improve a small
official Habitat ObjectNav YOLO smoke?

## Hypothesis

Training an action-conditioned temporal model on the current-visible slice
should better match online use, while the full-trace interaction model may
retain healthier left/right/forward ranking diversity. Either should outperform
the older one-frame learned-local model if local detector recovery is the main
failure.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini` |
| Simulator | Habitat-Lab official `ObjectNav-v1` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Offline dataset | `runs/habitat_official_objectnav/local_action_effect_dataset_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/dataset.json` |
| Query memory prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |
| Key online parameters | `memory_learned_local_frontier`, `max_episodes=4`, `max_steps=50`, `seed=313`, `memory_min_confidence=0.25` |

## Commands

Focused Linux gate:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
/home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core pytest -q \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_local_action_dataset.py \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
  src/objectnav_core/tests/test_ros_packaging.py
```

Model comparison:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python - <<'PY'
# Trained additive/interaction temporal models across:
# label in {next_target_visible, target_visible_at_horizon}
# training slice in {full, current-visible-only}.
# For each model, called:
#   python -m objectnav_core.cli.train_habitat_official_local_action_model ...
#   python -m objectnav_core.cli.score_habitat_official_local_action_model ...
# Wrote summary.json and common_slice_metrics.json under the artifact root.
PY
```

Online YOLO smoke:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
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

for model_path, output in [
    (
        "runs/habitat_official_objectnav/local_action_model_comparison_temporal_yolo_20ep_80steps_20260530_v1/models/interaction_next_target_visible_full.json",
        "runs/habitat_official_objectnav/memory_learned_local_frontier_interaction_next_full_yolo_detector_trace_4ep_50steps_20260530_v1",
    ),
    (
        "runs/habitat_official_objectnav/local_action_model_comparison_temporal_yolo_20ep_80steps_20260530_v1/models/interaction_next_target_visible_visible.json",
        "runs/habitat_official_objectnav/memory_learned_local_frontier_interaction_next_visible_yolo_detector_trace_4ep_50steps_20260530_v1",
    ),
]:
    run_habitat_official_objectnav_eval(
        Path(output),
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
        local_action_model_path=model_path,
    )
PY
```

## Artifacts

- Offline comparison root:
  `runs/habitat_official_objectnav/local_action_model_comparison_temporal_yolo_20ep_80steps_20260530_v1`
- Offline summaries:
  `summary.json`, `common_slice_metrics.json`, model JSON files, and
  candidate-score JSON/CSV reports under `candidate_reports/`
- Online full-trace interaction smoke:
  `runs/habitat_official_objectnav/memory_learned_local_frontier_interaction_next_full_yolo_detector_trace_4ep_50steps_20260530_v1`
- Online visible-trained interaction smoke:
  `runs/habitat_official_objectnav/memory_learned_local_frontier_interaction_next_visible_yolo_detector_trace_4ep_50steps_20260530_v1`
- Invalid no-detector trial, retained only as a caution:
  `runs/habitat_official_objectnav/memory_learned_local_frontier_interaction_next_full_yolo_discovery_prior_4ep_50steps_20260530_v1`

## Offline Metrics

Common visible slice means the same `500` examples where
`features.current_target_visible=True`.

| Model | Label | Train slice | Common visible log loss | Common visible Brier | Visible best-action counts |
|---|---|---|---:|---:|---|
| Additive temporal | `next_target_visible` | full | `0.090218` | `0.018158` | `turn_right=500` |
| Additive temporal | `next_target_visible` | visible | `0.077386` | `0.015278` | `move_forward=500` |
| Additive temporal | `target_visible_at_horizon` | full | `0.180315` | `0.041425` | `turn_right=500` |
| Additive temporal | `target_visible_at_horizon` | visible | `0.163354` | `0.037907` | `move_forward=500` |
| Interaction temporal | `next_target_visible` | full | `0.086042` | `0.017490` | `move_forward=78`, `turn_left=149`, `turn_right=273` |
| Interaction temporal | `next_target_visible` | visible | `0.074327` | `0.014401` | `move_forward=156`, `turn_right=344` |
| Interaction temporal | `target_visible_at_horizon` | full | `0.176657` | `0.040850` | `move_forward=116`, `turn_right=384` |
| Interaction temporal | `target_visible_at_horizon` | visible | `0.160333` | `0.037033` | `move_forward=117`, `turn_right=383` |

## Online Metrics

| Policy / model | Official success | SPL | SoftSPL | Mean distance | Detector target matches | Learned-local decisions |
|---|---:|---:|---:|---:|---:|---:|
| Previous fixed learned-local one-frame model | `0/4` | `0.0` | `0.02518699682786324` | `5.697803378105164` | `5` | `4` |
| Interaction temporal, `next_target_visible`, full trace | `0/4` | `0.0` | `0.02518699682786324` | `5.697803378105164` | `5` | `4` |
| Interaction temporal, `next_target_visible`, visible slice | `0/4` | `0.0` | `0.02518699682786324` | `5.697803378105164` | `4` | `3` |

## Observations

- The new candidate-score CLI made the offline comparison auditable. Additive
  temporal models still collapsed to one best action on the visible slice,
  while interaction models produced action-dependent rankings.
- The visible-trained interaction model had the best common visible-slice
  calibration, but it never chose `turn_left` in the offline visible-slice
  candidate report.
- The full-trace interaction model had slightly worse visible calibration but
  healthier candidate diversity.
- In online YOLO smoke, both temporal interaction models changed local learned
  choices relative to the old one-frame model, but the branch fired only
  `3` to `4` times out of `200` steps.
- Official metrics did not improve: success remained `0/4`, SPL remained
  `0.0`, and SoftSPL matched the previous fixed learned-local smoke.
- A first run through the console CLI produced no detector trace because the
  CLI does not inject a detector adapter. That artifact is invalid for YOLO
  learned-local conclusions.

## Result

The local-action model machinery is now reproducible and the temporal
interaction model is active online, but this algorithmic layer is too narrow to
move ObjectNav performance by itself. The limiting issue is sparse and brittle
current-view detector evidence along the memory/frontier trajectory, not just
the local candidate-action scorer.

## Follow-up

- Treat the temporal learned-local controller as a diagnostic component, not a
  benchmark contribution yet.
- Move from a one-step local scorer to a broader active perception/search
  policy that can decide when to seek detector evidence, not only how to react
  after detector-centering failure.
- Use the newly added detector-injecting official eval CLI path for future
  YOLO smokes, so runs cannot accidentally omit a detector adapter.
