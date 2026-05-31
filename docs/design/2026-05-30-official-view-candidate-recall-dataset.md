# Design Doc: Official View-Candidate Recall Dataset

Date: 2026-05-30
Owner: Codex
Status: Implemented with active-trace exports

## Goal

Export per-state active-perception candidate viewpoints from official policy
traces, preserving which candidate was actually selected and which candidates
remain counterfactual/unobserved. The dataset should support honest analysis of
candidate ranking without pretending unexecuted candidates have negative
labels.

## Non-Goals

- Do not train a candidate ranker in this slice.
- Do not label unexecuted candidate viewpoints as failures.
- Do not use Habitat target pose, semantic oracle masks, prior maps, or route
  followers.
- Do not claim official benchmark improvement from this diagnostic dataset.

## Background

The hidden-to-visible view-recall model found a real state-ranking signal, but
candidate-action overrides collapsed to one global turn. Existing active
policy traces already contain `memory_prior.top_candidates`, including
candidate viewpoint/frontier cells, expected evidence, travel distance, and
score. This is the right bridge toward candidate-value learning, but only the
selected/logged candidate has an observed future detector outcome. The dataset
must preserve that distinction.

## System Boundary

Create:

- `objectnav_core.evaluation.habitat_official_view_candidate_dataset`
- `objectnav_core.cli.export_habitat_official_view_candidate_dataset`
- tests for pure export, CSV writing, CLI output, and packaging

Modify:

- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- docs/devlog/handoff and an experiment report after Linux export

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | `policy_trace.json` | Must contain `memory_prior.top_candidates`. |
| Input | Detector trace | `detector_trace.json` | Same run, used for future target-visibility labels. |
| Input | Horizon steps | integer | Future same-episode window. |
| Output | Dataset JSON | JSON | Candidate rows plus source/run metadata. |
| Output | Optional CSV | CSV | Flat candidate rows for audit. |

## Interfaces

Python API:

```python
export_official_view_candidate_dataset(
    policy_trace_path,
    detector_trace_path=...,
    source_run_id=None,
    horizon_steps=5,
)

write_official_view_candidate_dataset_csv(dataset, path)
```

CLI:

```bash
python -m objectnav_core.cli.export_habitat_official_view_candidate_dataset \
  <policy_trace.json> \
  --detector-trace <detector_trace.json> \
  --output <dataset.json> \
  --csv-output <candidates.csv> \
  --horizon-steps 5
```

Console script:

```bash
objectnav_habitat_official_view_candidate_dataset ...
```

## Data Flow

1. Load policy steps and detector calls, sorted by episode and step.
2. For each step with `memory_prior.top_candidates`, compute current detector
   visibility and future target visibility within the horizon.
3. Emit one row per candidate with:
   - state metadata: episode, step, action, decision, target category;
   - candidate metadata: rank, score, expected evidence, travel/path distance,
     viewpoint/frontier cells, bearing error, view quality;
   - selection metadata: whether this candidate matches the selected
     viewpoint/frontier fields in `memory_prior`;
   - labels:
     `state_hidden_to_visible_within_horizon`,
     `observed_candidate_label_available`, and
     `observed_candidate_hidden_to_visible_within_horizon`.
4. The selected candidate receives the observed state outcome. Unselected
   candidates receive `observed_candidate_label_available=False` and a null
   observed-candidate label.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Trace lacks `top_candidates` | `candidate_count=0` | Export still records zero rows; use newer active traces. |
| Candidate lacks viewpoint cell | Null viewpoint fields | Match by frontier when viewpoint is absent. |
| Future horizon crosses episode boundary | Skipped horizon count | Same handling as view-recall dataset. |
| Unselected candidates treated as negatives by mistake | Explicit observed-label flag | Downstream trainers must filter by label availability. |

## Verification Plan

1. RED synthetic test: two top candidates, one selected, future target visible.
   Export must create two rows and only the selected row may have the observed
   positive label.
2. RED CSV test for stable candidate fields and null unobserved labels.
3. RED CLI/packaging test for module and console script registration.
4. Local focused tests, compileall, and `git diff --check`.
5. Sync to Linux, rerun focused tests, and export candidate datasets from
   active-perception trace variants.

## Implementation Notes

- Added JSON/CSV candidate export in
  `habitat_official_view_candidate_dataset`.
- Added CLI and console script
  `objectnav_habitat_official_view_candidate_dataset`.
- Linux exports across four active-perception traces produced `665` candidate
  rows from `133` states, with `133` selected-candidate labels and `532`
  explicitly unobserved counterfactual candidates.
- Selected candidate rank was always `0`; this confirms the current traces are
  useful for auditing candidate sets but not enough for direct counterfactual
  candidate-value training.

## Research Relevance

This dataset is the honest bridge between the current observational
view-recall model and a publishable learned active-sensing policy. It exposes
candidate coverage and selection bias explicitly, preventing the project from
training on fake negatives while still giving the next algorithm a structured
candidate set tied to the robot's memory-search decisions.

## Open Questions

- Whether to collect true counterfactual candidate labels through short
  simulation rollouts from saved states.
- Whether candidate ranking should predict detector recovery directly or learn
  a value combining recovery probability and travel cost.
