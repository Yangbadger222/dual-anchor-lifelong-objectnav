# Experiment Report: Official Temporal Local Action-Effect Dataset YOLO Trace

Date: 2026-05-30
Owner: Codex
Status: Completed; offline learning-substrate result

## Question

Can official ObjectNav traces produce a larger temporal action-effect dataset
that captures detector-evidence trends strongly enough to support a learned
short-horizon local controller?

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini` |
| Simulator | Habitat-Lab official `ObjectNav-v1` environment |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Export schema | `official-local-action-effect-v2` |
| History / horizon | `history_steps=3`, `horizon_steps=3` |

## Commands

20-episode discovery:

```bash
PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_memory_discovery \
  --output runs/habitat_official_objectnav/discovery_yolo_world_valmini_20ep_80steps_20260530_v1 \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --min-detection-confidence 0.25 \
  --max-episodes 20 \
  --max-steps 80 \
  --seed 313 \
  --policy occupancy_frontier
```

20-episode query used `run_habitat_official_objectnav_eval` with:

- output:
  `runs/habitat_official_objectnav/memory_evidence_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260530_v1`
- policy: `memory_evidence_frontier`
- memory prior:
  `runs/habitat_official_objectnav/discovery_yolo_world_valmini_20ep_80steps_20260530_v1/memory_prior.json`
- `max_episodes=20`, `max_steps=80`, `seed=313`
- YOLO-World target detector with the six ObjectNav labels.

Temporal export:

```bash
PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.export_habitat_official_local_action_dataset \
  runs/habitat_official_objectnav/memory_evidence_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260530_v1/policy_trace.json \
  --detector-trace runs/habitat_official_objectnav/memory_evidence_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260530_v1/detector_trace.json \
  --output runs/habitat_official_objectnav/local_action_effect_dataset_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/local_action_effect_dataset_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/examples.csv \
  --source-run-id memory_evidence_frontier_yolo_20ep_80steps_20260530_v1 \
  --history-steps 3 \
  --horizon-steps 3
```

Temporal model smoke:

```bash
PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.train_habitat_official_local_action_model \
  runs/habitat_official_objectnav/local_action_effect_dataset_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/dataset.json \
  --output runs/habitat_official_objectnav/local_action_effect_model_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/model.json \
  --epochs 500 \
  --learning-rate 0.1 \
  --l2 0.001 \
  --features current_target_visible,current_target_match_count,current_detector_confidence,current_bbox_area_fraction,current_abs_center_offset_fraction,current_depth_median,x_m,z_m,heading_rad,action_move_forward,action_turn_left,action_turn_right,action_stop,suppressed_action_none,suppressed_action_turn_left,suppressed_action_turn_right,suppressed_turn_left,suppressed_turn_right,history_observed_step_count,previous_target_visible,recent_target_visible_count,steps_since_last_target_visible,recent_move_forward_count,recent_turn_left_count,recent_turn_right_count,recent_reacquire_count,current_confidence_minus_previous,current_bbox_area_minus_previous,current_depth_minus_previous,current_abs_center_offset_minus_previous
```

## Artifacts

- `runs/habitat_official_objectnav/discovery_yolo_world_valmini_20ep_80steps_20260530_v1`
- `runs/habitat_official_objectnav/memory_evidence_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260530_v1`
- `runs/habitat_official_objectnav/local_action_effect_dataset_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1`
- `runs/habitat_official_objectnav/local_action_effect_model_default_memory_evidence_yolo_20ep_80steps_20260530_v1/model.json`
- `runs/habitat_official_objectnav/local_action_effect_model_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/model.json`

## Trace Metrics

| Metric | 4-episode fixed learned-local trace | 20-episode memory-evidence trace |
|---|---:|---:|
| Official success | `0/4` | `0/20` |
| SPL | `0.0` | `0.0` |
| SoftSPL | `0.02518699682786324` | `0.02945252626989075` |
| Detector calls | `196` | `1580` |
| Target-match calls | `5` | `500` |
| Target-match detections | `5` | `732` |
| Dataset examples | `196` | `1580` |
| Visible-before examples | `5` | `500` |
| Visible-after examples | `5` | `498` |
| Retained transitions | `2` | `454` |
| Lost transitions | `3` | `46` |
| Acquired transitions | `3` | `44` |
| Remained absent transitions | `188` | `1036` |

## Offline Model Smoke

Both models use the same 20-episode v2 dataset and the same
`next_target_visible` label.

| Model | Feature count | Accuracy | Log loss | Brier score | Mean prediction |
|---|---:|---:|---:|---:|---:|
| Default one-frame safe features | `15` | `0.955063` | `0.174072` | `0.039334` | `0.315358` |
| Temporal feature set | `30` | `0.987342` | `0.059308` | `0.011546` | `0.321754` |

Largest absolute temporal-model weights were:

- `previous_target_visible`: `1.6249`
- `recent_target_visible_count`: `1.1305`
- `current_target_visible`: `0.7033`
- `steps_since_last_target_visible`: `0.5409`
- `current_abs_center_offset_fraction`: `-0.2401`
- `recent_reacquire_count`: `-0.1992`

## Interpretation

This is not an ObjectNav benchmark improvement. The 20-episode query still
solved `0/20` official episodes, and the discovery/query protocol uses a
generated memory prior, so these artifacts are diagnostic/training data only.

The useful result is that temporal features materially improve the offline
next-visibility model on a larger official trace. The learned weights match the
qualitative failure mode: recent target visibility is predictive, while large
offset and reacquisition history indicate fragile local control. The next
online policy should carry these temporal features at runtime and score local
actions or short action sequences with them.

## Verification

- Local focused official gate: `81` passed.
- Local `compileall`: passed.
- Local `git diff --check`: clean.
- Linux focused official gate in env `habitat`: `81` passed.
- Linux `compileall`: passed.
- Linux `git diff --check`: clean.
- 20-episode discovery, query, temporal export, and model-training smokes
  completed on Linux.
