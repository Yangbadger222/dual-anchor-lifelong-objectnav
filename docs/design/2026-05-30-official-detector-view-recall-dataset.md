# Design Doc: Official Detector View-Recall Dataset

Date: 2026-05-30
Owner: Codex
Status: Implemented with first real trace export

## Goal

Export a supervised dataset for learning expected detector evidence from
official Habitat policy and detector traces. Each example should describe the
agent pose, memory-relative geometry, active-perception viewpoint/debug fields,
current detector evidence, and action/decision phase, with labels indicating
whether the target is reacquired within a short future horizon.

## Non-Goals

- Do not train the model in this slice.
- Do not use Habitat target pose, semantic oracle masks, route followers, or
  prior maps.
- Do not replace official ObjectNav metrics with the learned dataset metrics.
- Do not add language/GPT control in this slice.

## Background

The hand-authored active-perception variants produced useful negative smokes:
rotation-aware scoring fixed candidate evidence, path-aware viewpoints created
reachable candidates, and viewpoint scan made the option semantics explicit,
but none improved official success. Continuing to tune rules is unlikely to
produce a top-tier result. The next paper-relevant step is a data path for a
learned view-value model: from a memory hypothesis and current view/action
context, predict whether detector evidence will appear soon.

## System Boundary

Create:

- `objectnav_core.evaluation.habitat_official_view_recall_dataset`
- `objectnav_core.cli.export_habitat_official_view_recall_dataset`
- focused tests for pure export and CLI output

Modify:

- `src/objectnav_core/setup.py` for a console script
- `src/objectnav_core/tests/test_ros_packaging.py` for packaging coverage
- docs/devlog/handoff and an experiment report after exporting real Linux
  traces

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | `policy_trace.json` | Official evaluator step trace. |
| Input | Detector trace | `detector_trace.json` | Query detector calls from same run. |
| Input | Horizon steps | integer | Future window for target reacquisition labels. |
| Output | Dataset JSON | JSON object | Schema, counts, examples, feature/label names. |
| Output | Optional CSV | Flat table | For quick analysis and model prototyping. |

## Interfaces

Python API:

```python
export_official_view_recall_dataset(
    policy_trace_path,
    detector_trace_path=...,
    source_run_id=None,
    horizon_steps=5,
)

write_official_view_recall_dataset_csv(dataset, path)
```

CLI:

```bash
python -m objectnav_core.cli.export_habitat_official_view_recall_dataset \
  <policy_trace.json> \
  --detector-trace <detector_trace.json> \
  --output <dataset.json> \
  --csv-output <examples.csv> \
  --horizon-steps 5
```

Console script:

```bash
objectnav_habitat_official_view_recall_dataset ...
```

## Data Flow

1. Load and sort policy steps by episode and step index.
2. Load detector calls and keep target-match evidence per episode/step.
3. For each policy step with a consecutive future horizon in the same episode,
   build features:
   - pose: `x_m`, `z_m`, `heading_rad`;
   - detector state: current target visibility, confidence, match count;
   - memory/action phase: policy decision, active-perception phase;
   - memory-relative geometry when available:
     `distance_to_anchor_m`, `anchor_bearing_error_rad`;
   - selected viewpoint evidence when available:
     `expected_evidence`, `path_distance_m`, `travel_distance_m`,
     `selected_viewpoint_row`, `selected_viewpoint_col`,
     `selected_frontier_row`, `selected_frontier_col`.
4. Build labels over the future horizon:
   - `target_visible_next`;
   - `target_visible_within_horizon`;
   - `first_target_visible_step_delta`;
   - `best_future_detector_confidence`;
   - `future_target_match_count`.
5. Write JSON and optional CSV with stable schemas.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Policy/detector traces from different runs | Mismatched step coverage/counts | Record source paths and missing detector evidence count. |
| Detector not injected | Zero detector calls or no target matches | Dataset still exports but summary marks zero positive labels. |
| Missing active-perception fields | `None` feature values | Keep schema stable; models can impute. |
| Horizon crosses episode boundary | Non-consecutive step indices or episode mismatch | Skip and count `skipped_horizon_count`. |

## Verification Plan

1. RED API test with synthetic policy/detector traces: active-perception
   memory fields become features and a target match two steps later sets
   `target_visible_within_horizon=True`.
2. RED CSV test for stable headers including active-perception fields.
3. RED CLI/packaging tests for module and console script registration.
4. GREEN implementation with deterministic JSON/CSV output.
5. Local focused tests, compileall, and `git diff --check`.
6. Sync to Linux and export the real view-recall dataset from recent YOLO
   active-perception traces.

## Implementation Notes

- Added `habitat_official_view_recall_dataset` with stable feature and label
  schemas.
- Added CLI
  `objectnav_core.cli.export_habitat_official_view_recall_dataset` and console
  script `objectnav_habitat_official_view_recall_dataset`.
- Local and Linux focused gates passed with `99` tests, plus compileall and
  `git diff --check`.
- First Linux export wrote
  `runs/habitat_official_objectnav/view_recall_dataset_active_perception_viewpoint_scan_yolo_4ep_50steps_20260530_v1`.
- The first dataset has `196` examples, `8` positive
  `target_visible_within_horizon` labels, and `44` active-perception examples.
  Positive labels by phase were `0/20` for `orient_anchor`, `0/20` for
  `scan_anchor`, and `8/156` for non-scan phases.
- The summary `active_perception_example_count` treats an example as active
  when it has an active-perception phase, a selected viewpoint, or an explicit
  `active_perception` decision. This keeps older rotation-aware traces from
  being miscounted as inactive simply because they predate the phase field.
- A comparison export across active-perception variants found hidden-to-visible
  active positives in memory-frontier turn/move decisions, not in the
  hand-authored `orient_anchor` or `scan_anchor` phases.

This confirms the negative scan smoke in data form: the hand-authored scan
phase did not generate target reacquisition in this run. The next step should
train or score a learned view-recall model from this dataset family and avoid
scaling scan rules that have no positive labels.

## Research Relevance

This creates the bridge from rule-based active perception to a learned
expected-evidence model. A learned view-recall predictor can become the
algorithmic contribution: memory-conditioned, map-free view selection that
learns detector observability from experience and can later transfer to a real
robot with the same pose/memory/detector trace interface.

## Open Questions

- Whether to train one model across all policy variants or separate models by
  policy/action phase.
- Whether future labels should include object-centered quality such as bbox
  area and depth, beyond binary target reacquisition.
