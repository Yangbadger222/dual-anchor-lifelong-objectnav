# Experiment Report: Official Local Action-Effect Dataset Export from YOLO Trace

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Can the latest official `memory_evidence_frontier` YOLO query trace be converted
into self-supervised local action-effect examples suitable for training a
detector-evidence local action scorer?

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Source machine | Linux mirror, `badger@100.88.131.52` |
| Local export machine | macOS workspace |
| Source run | `runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1` |
| Source policy | `memory_evidence_frontier` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, target-category matching |

## Command

The source trace files were copied from the Linux artifact:

```bash
scp badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/policy_trace.json /tmp/official_local_action_trace/policy_trace.json
scp badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/detector_trace.json /tmp/official_local_action_trace/detector_trace.json
```

Exporter command:

```bash
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.export_habitat_official_local_action_dataset \
  /tmp/official_local_action_trace/policy_trace.json \
  --detector-trace /tmp/official_local_action_trace/detector_trace.json \
  --output runs/habitat_official_objectnav/local_action_effect_dataset_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/local_action_effect_dataset_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/examples.csv \
  --source-run-id memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1
```

## Artifacts

- `runs/habitat_official_objectnav/local_action_effect_dataset_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/dataset.json`
- `runs/habitat_official_objectnav/local_action_effect_dataset_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/examples.csv`

## Result

| Count | Value |
|---|---:|
| Policy steps | `200` |
| Action-effect examples | `196` |
| Visible before action | `4` |
| Visible after action | `4` |
| Retained transitions | `2` |
| Lost transitions | `2` |
| Acquired transitions | `2` |
| Remained absent transitions | `190` |

The visible examples all came from the `tv_monitor` episode. The exported
action-effect rows capture the key local-control failure:

| Step | Action | Decision | Current visible | Next visible | Area delta | Abs-offset delta |
|---:|---|---|---|---|---:|---:|
| `3` | `turn_left` | `fallback_occupancy_frontier` | false | true | n/a | n/a |
| `4` | `turn_right` | `center_detector_target` | true | false | n/a | n/a |
| `5` | `turn_left` | `reacquire_detector_target` | false | true | n/a | n/a |
| `6` | `move_forward` | `approach_detector_target_after_center_loss` | true | true | `-0.006702473958` | `0.0203125` |
| `7` | `move_forward` | `approach_detector_target_after_center_loss` | true | true | `-0.011871744792` | `0.0265625` |
| `8` | `move_forward` | `approach_detector_target_after_center_loss` | true | false | n/a | n/a |

## Interpretation

This is not a benchmark result. It is a data substrate for the next policy.
The exported labels confirm that the current action-effect controller leaves a
learnable signature: the two retained forward steps both worsen bbox area and
edge offset before the third forward step loses the target. That is exactly the
kind of short-horizon evidence trend a learned local action scorer should use.

## Follow-up

- Train an initial local action-effect scorer over retained/acquired/lost
  labels and continuous bbox trend deltas.
- Integrate the scorer as a new official policy variant instead of changing
  `memory_evidence_frontier` in place.
- Generate larger official traces because this four-episode smoke is far too
  sparse for a publishable learned controller.
