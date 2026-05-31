# Experiment Report: Official State-Restore Label Dataset

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Can we replay official Habitat policy traces to exact candidate-bearing memory
query states and label target visibility there without any branch-action
confound?

## Hypothesis

The existing replay machinery should restore the logged decision state reliably.
Most phase-diverse memory-query states should remain target-hidden at the exact
current view, which would confirm that repeat-first positives are mainly from
local movement/rotation and that the next stronger label needs candidate
viewpoint evaluation.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Local macOS plus Linux mirror `badger-linux` |
| Dataset / bag / map | HM3D ObjectNav `val_mini`, 20-episode active-perception YOLO trace |
| Simulator / robot | Habitat-Lab in conda env `habitat` |
| Key parameters | `active_phase_path`, `max_states_per_category=8`, `max_states_per_category_episode=2`, detector `yolo_world`, current-view state restore only |

## Command

Local TDD and verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_labels_exact_replayed_state \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_writes_csv \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_cli_writes_json_and_csv -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

Linux targeted tests:

```bash
ssh badger-linux 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_labels_exact_replayed_state \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_cli_writes_json_and_csv \
    src/objectnav_core/tests/test_ros_packaging.py -q'
```

Linux real Habitat/Yolo smoke:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
OUT=runs/habitat_official_objectnav/candidate_state_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1

/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_habitat_official_candidate_state_restore_dataset \
    runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json \
    --output "$OUT/dataset.json" \
    --csv-output "$OUT/states.csv" \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-states-per-category 8 \
    --max-states-per-category-episode 2 \
    --state-sampling active_phase_path
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| RED tests | `3` failures | Missing API/writer/CLI before implementation |
| Local new tests | `3 passed` | API, CSV, CLI |
| Local focused exporter/packaging | `17 passed` | Includes packaging entry point |
| Linux targeted tests | `3 passed` | Conda env `habitat` |
| Real restore dataset | `24` states, `24` restores | Bounded 20-episode phase/path sample |
| Valid restores | `24/24` | `0` invalid restore |
| Target-visible at restore | `1/24` | One `sofa` state |
| Hidden at restore | `23/24` | `chair 8`, `bed 7`, `tv_monitor 5`, `sofa 3` |
| CSV schema | present | `target_visible_at_restore`, phase feature fields, and replay actions present |

## Observations

- The exporter does not execute branch actions after replay. The fake-env test
  records only the logged replay action `move_forward`.
- The single visible restored state is an orient-at-viewpoint `sofa` state:
  `episode_index=15`, `step_index=0`, `candidate_rank=0`,
  `path_distance_m=0.0`.
- Most selected memory-query states are target-hidden at the restored current
  view. That is expected and useful: it confirms current-view labels alone are
  not enough to train candidate ranking or local control.

## Result

The exact state-restore label path is implemented and validated. It provides a
clean current-view audit dataset that can filter current-visible states and
separate replay failures from detector negatives. It does not solve candidate
viewpoint labeling yet.

## Follow-up

- Implement candidate-viewpoint teleport labels with careful conversion from
  episode-relative grid cells to Habitat world poses.
- Use state-restore labels to exclude current-visible states from future
  hidden-to-visible action/candidate training.
- Keep this dataset separate from action-matrix reports so no one mistakes
  current-view negatives for candidate-viewpoint negatives.
