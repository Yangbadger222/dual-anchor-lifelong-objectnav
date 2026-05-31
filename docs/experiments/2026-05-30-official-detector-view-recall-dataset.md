# Experiment Report: Official Detector View-Recall Dataset Export

Date: 2026-05-30
Owner: Codex
Status: Completed dataset export plus cross-run diagnostic comparison

## Question

Can official policy and detector traces be converted into supervised examples
for learning memory-conditioned detector view recall?

## Hypothesis

The recent active-perception traces should contain enough state/action/context
to label whether the target appears within a short horizon. The first dataset
will likely be small and imbalanced, but it should expose whether hand-authored
orient/scan phases actually produce target reacquisition.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Local macOS plus Linux mirror `badger@100.88.131.52` |
| Source run | `runs/habitat_official_objectnav/memory_active_perception_frontier_viewpoint_scan_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1` |
| Dataset / map | HM3D ObjectNav `val_mini` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Horizon | `5` future same-episode steps |

## Command

Verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_local_action_dataset.py \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py \
  src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

Export:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.export_habitat_official_view_recall_dataset \
  runs/habitat_official_objectnav/memory_active_perception_frontier_viewpoint_scan_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/policy_trace.json \
  --detector-trace runs/habitat_official_objectnav/memory_active_perception_frontier_viewpoint_scan_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/detector_trace.json \
  --output runs/habitat_official_objectnav/view_recall_dataset_active_perception_viewpoint_scan_yolo_4ep_50steps_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/view_recall_dataset_active_perception_viewpoint_scan_yolo_4ep_50steps_20260530_v1/examples.csv \
  --source-run-id memory_active_perception_frontier_viewpoint_scan_yolo_4ep_50steps_20260530_v1 \
  --horizon-steps 5
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Source policy steps | `200` | Four episodes, 50 steps each. |
| Exported examples | `196` | Last step of each episode skipped. |
| Positive within horizon | `8` | Target visible within five future steps. |
| Active-perception examples | `44` | Includes active turn/orient/scan rows. |
| `orient_anchor` positives | `0/20` | No target reacquisition in orient phase. |
| `scan_anchor` positives | `0/20` | No target reacquisition in scan phase. |
| Non-scan positives | `8/156` | All positives came outside scan phases. |

## Cross-Run Comparison

After the first export, the same CLI was run on compatible policy/detector
trace pairs from the active-perception, memory-evidence, learned-local, and
memory-belief smokes. The diagnostic split below separates ordinary future
positives from hidden-to-visible positives, where
`current_target_visible=False` and `target_visible_within_horizon=True`.

Comparison exports used this command pattern on the Linux mirror:

```bash
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.export_habitat_official_view_recall_dataset \
  runs/habitat_official_objectnav/<source-run>/policy_trace.json \
  --detector-trace runs/habitat_official_objectnav/<source-run>/detector_trace.json \
  --output runs/habitat_official_objectnav/<view-recall-output>/dataset.json \
  --csv-output runs/habitat_official_objectnav/<view-recall-output>/examples.csv \
  --source-run-id <source-run> \
  --horizon-steps 5
```

The generated comparison artifacts are named
`runs/habitat_official_objectnav/view_recall_dataset_*_20260530_v1`.

| Dataset | Examples | Future positives | Hidden-to-visible | Active examples | Active hidden-to-visible | Official SoftSPL |
|---|---:|---:|---:|---:|---:|---:|
| active original | `196` | `48` | `10` | `8` | `8` | `0.02518699682786324` |
| active rotation-aware | `196` | `39` | `11` | `29` | `9` | `0.03315001996589104` |
| active path-aware | `196` | `22` | `10` | `35` | `8` | `0.0009902771347611306` |
| active viewpoint scan | `196` | `8` | `5` | `44` | `4` | `0.02518699682786324` |
| memory evidence, 20 episodes | `1580` | `545` | `53` | `0` | `0` | `0.02945252626989075` |
| memory evidence action-effect | `196` | `8` | `5` | `0` | `0` | `0.02518699682786324` |
| learned local, interaction next full | `196` | `10` | `6` | `0` | `0` | `0.02518699682786324` |
| learned local, interaction next visible | `196` | `8` | `5` | `0` | `0` | `0.02518699682786324` |
| learned local, suppressed failed turns | `196` | `10` | `6` | `0` | `0` | `0.02518699682786324` |
| memory belief policy trace | `196` | `48` | `26` | `0` | `0` | `0.0009902771347611306` |

Active-perception phase and decision breakdown:

| Variant | Key hidden-to-visible source | Scan/orient contribution |
|---|---|---:|
| active original | `8/8` active positives from `turn_toward_memory_active_perception_frontier` | no phase fields |
| active rotation-aware | `8` turn positives plus `1` move positive from memory active-perception decisions | no phase fields |
| active path-aware | `8` turn positives from memory active-perception decisions | no phase fields |
| active viewpoint scan | `4` turn positives from memory active-perception decisions | `orient_anchor=0/20`, `scan_anchor=0/20` |

Across the four active-perception datasets, there were `116`
active-perception examples and `29` active hidden-to-visible positives. All
`29` came from memory-frontier turn/move decisions; none came from the
hand-authored anchor scan phase. The strongest lightweight numeric signals in
this small active slice were larger `distance_to_anchor_m` for hidden positives
(median `1.8898` vs `1.7443`, AUC-high `0.876`) and higher `view_quality`
(median `0.976` vs `0.9435`, AUC-high `0.704`). `expected_evidence` was
inverted in this slice (median `0.5103` for hidden positives vs `0.5199` for
negatives, AUC-low `0.895`), so the current handcrafted expected-evidence score
should not be used as a trusted policy value without learning/calibration.

## Observations

- The exporter produces stable JSON and CSV artifacts with active-perception
  fields such as `selected_viewpoint_row`, `path_distance_m`,
  `expected_evidence`, `active_perception_phase`, and
  `anchor_bearing_error_rad`.
- The first real dataset is small and imbalanced, but already explains the
  negative scan smoke: hand-authored orient/scan actions did not lead to target
  recall in the five-step horizon.
- The first positive example came from a normal active-perception turn, four
  steps before a target detector match.
- The larger memory-evidence export contains many positives, but most are
  detector-continuity rows where the target is already visible. The useful
  hidden-to-visible rows are much rarer (`53/1580`) and should be weighted or
  sampled explicitly when training a view-recall model.
- The active scan branch increased structured active examples but reduced
  hidden-to-visible active positives relative to the simpler rotation-aware
  variant. That makes the scan phase a poor candidate for further rule tuning.

## Result

The project now has the required data interface for learning expected detector
view recall from official traces. The comparison exports give an evidence-based
reason to stop adding scan rules and move to learned view-value estimation,
with training labels focused on hidden-to-visible reacquisition rather than raw
future visibility.

## Follow-up

- Train a deterministic baseline view-recall model and score whether it ranks
  hidden-to-visible states above scan dead ends.
- Use the 20-episode memory-evidence export for scale, but stratify or weight
  hidden-to-visible labels so detector-continuity rows do not dominate.
- Only return to official YOLO smokes after offline view-recall ranking shows a
  meaningful signal.
