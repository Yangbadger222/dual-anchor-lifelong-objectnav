# Experiment Report: Official Candidate-Viewpoint Restore Labels

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Can candidate-viewpoint restore labels provide richer memory-query supervision
than exact current-view state restore labels?

## Hypothesis

The current-view state-restore artifact showed only `1/24` restored states with
the target already visible. If memory candidate viewpoints are meaningful, a
top-K candidate-viewpoint heading scan should recover more target-visible labels
from the same phase/path-selected states without changing official Habitat
benchmark metrics.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Local macOS plus Linux mirror `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini`, 20-episode active-perception YOLO trace |
| Simulator / robot | Habitat-Lab in conda env `habitat` |
| Key parameters | `active_phase_path`, top-K candidate viewpoint restore, fixed heading scan |

## Command

Initial local RED/GREEN tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_grid_cell_conversion_uses_episode_relative_xz \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_restore_dataset_labels_top_k_scan_viewpoints \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_restore_dataset_keeps_invalid_restore_auditable \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_restore_dataset_cli_writes_json_and_csv -q
```

Focused local implementation gate:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

Full local verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check

if rg -n "[ \t]+$" docs/design/2026-05-31-official-candidate-viewpoint-restore-labels.md \
  docs/experiments/2026-05-31-official-candidate-viewpoint-restore-labels.md \
  docs/superpowers/plans/2026-05-31-official-candidate-viewpoint-restore-labels.md \
  docs/devlog/2026-05.md \
  docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_viewpoint_restore_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/setup.py \
  src/objectnav_core/tests/test_ros_packaging.py; \
then exit 1; else exit 0; fi
```

Linux targeted tests:

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/tests/test_ros_packaging.py -q'
```

Linux real Habitat/Yolo smoke:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
OUT=runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1

/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_habitat_official_candidate_viewpoint_restore_dataset \
    runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json \
    --output "$OUT/dataset.json" \
    --csv-output "$OUT/candidate_viewpoints.csv" \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-states-per-category 8 \
    --max-states-per-category-episode 2 \
    --state-sampling active_phase_path \
    --candidates-per-state 5 \
    --viewpoint-heading-count 8
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| RED tests | `4` failures | Missing helper/API/CLI before implementation |
| New focused tests | `4 passed` | Initial RED/GREEN slice |
| RGBA regression test | `1` failure then `1 passed` | `sim.get_sensor_observations()` returned RGBA; exporter now strips alpha |
| Candidate exporter plus packaging | `23 passed` | Includes pose fallback, RGB normalization, and entry point |
| Full local suite | `428 passed` | After initial implementation; focused gate re-run after RGBA fix |
| Local compileall | passed | `python -m compileall -q ...` |
| Local diff check | passed | `git diff --check` |
| Local touched-file whitespace scan | passed | No trailing whitespace in touched files |
| Linux targeted tests | `23 passed` | Conda env `habitat` |
| Linux targeted compileall | passed | Touched modules/tests |
| Real candidate-viewpoint rows | `120` | `24` states x top-5 candidates |
| Valid candidate restores | `120/120` | `0` invalid restores |
| Candidate-viewpoint visible rows | `74/120` | Fixed 8-heading scan |
| Hidden-to-visible candidate rows | `69/120` | Current-view visible state excluded by label |
| States with any visible candidate | `16/24` | Current-view restore was `1/24` visible |
| States with any hidden-to-visible candidate | `15/24` | Stronger than current-view restore |
| Top-1 visible candidates | `14/24` | Candidate rank `0` only |
| Top-1 hidden-to-visible candidates | `13/24` | Candidate rank `0`, current hidden |

## Observations

- The candidate grid inverse preserves the existing episode-relative convention:
  row up is positive `z=forward`, column right is positive `x=right`.
- The exporter emits one row per top-K candidate rather than only the selected
  candidate, which is necessary for candidate-ranking supervision.
- The current implementation names the label as candidate-viewpoint scan
  visibility. It should not be compared directly to one-step action labels.
- The first Linux smoke failed because Habitat-Sim candidate restore observations
  returned `rgb` as RGBA while the official env observations and YOLO adapter use
  RGB. The exporter now normalizes candidate-restore RGB to the first three
  channels and maps `color_sensor` to `rgb` if needed.
- Positive candidate-viewpoint rows were spread across represented categories:
  `tv_monitor 25`, `sofa 20`, `chair 20`, `bed 9`.
- Hidden-to-visible rows by category were `tv_monitor 25`, `chair 20`,
  `sofa 15`, `bed 9`.
- Visible rows were not only rank-0: visible counts by rank were
  `{0: 14, 1: 14, 2: 15, 3: 16, 4: 15}`.

## Result

Candidate-viewpoint restore labels are materially richer than exact current-view
state-restore labels on the same bounded phase/path slice. The current-view
state-restore dataset saw the target in only `1/24` restored states, while the
candidate-viewpoint scan dataset found at least one hidden-to-visible candidate
for `15/24` states and `69/120` candidate rows.

This is not an online ObjectNav benchmark result. It is offline teleport/restore
supervision for candidate-viewpoint ranking and label redesign.

## Follow-up

- Use the candidate-viewpoint labels for the next held-out candidate-ranking
  model comparison.
- Keep constant baselines and source holdouts; do not claim policy success from
  label richness alone.
- Consider adding explicit memory-anchor coordinates to future policy traces so
  candidate labels can evaluate anchor-facing headings in addition to uniform
  scans.
