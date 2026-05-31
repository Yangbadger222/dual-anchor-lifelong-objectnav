# Design Doc: Official Candidate Rollout Labeling

Date: 2026-05-30
Owner: Codex
Status: Implemented with Habitat action-matrix controls

## Goal

Create a simulator-side rollout labeler that turns active-perception
candidate sets into real intervention labels. For each logged candidate state,
the labeler should replay the episode to the same decision point, branch over
the top candidate viewpoints/actions, execute a short rollout, and record
whether the target detector becomes visible.

Add an action-matrix mode for the same replay states. In that mode the labeler
branches explicit first actions such as `turn_left`, `turn_right`, and
`move_forward` before the diagnostic follow-up rollout. This is separate from
candidate-viewpoint ranking and is meant to collect honest counterfactual
local-action evidence when candidate viewpoints collapse to the same scan
action.

The action-matrix output must be interpreted by horizon. With
`rollout_horizon_steps=5`, labels measure short-horizon recovery after the
forced first action plus the diagnostic follow-up controller. With
`rollout_horizon_steps=1`, labels measure immediate detector recovery after
only the forced first action. The two settings answer different questions and
must not be mixed when training or reporting action effects.

The next exporter revision makes the follow-up controller explicit. The
default remains `left_scan` for backward-compatible reproduction of existing
artifacts. A new `repeat_first_action` policy repeats the branch action for the
whole rollout horizon, so the action matrix can label symmetric macro-action
interventions instead of converting every non-immediate branch into a left
scan.

## Non-Goals

- Do not integrate a learned candidate ranker into the online ObjectNav policy
  in this slice.
- Do not treat unselected logged candidates as negative examples.
- Do not use Habitat semantic oracle target poses, goal distance, shortest
  paths, or map priors as labels.
- Do not claim official Habitat benchmark improvement from rollout-label data.
- Do not alter official ObjectNav metrics; success/SPL remain copied only from
  `habitat.Env.get_metrics` in benchmark runs.
- Do not train an online policy from all-positive candidate-viewpoint smokes.
  Action-matrix labels are a diagnostic bridge, not a final policy.
- Do not call horizon-5 action-matrix labels immediate first-action labels;
  those rows include delayed recovery from the follow-up scan controller.

## Background

The official view-candidate dataset export found `665` candidate rows, but only
the selected top-ranked candidate had an observed label. The learned
hidden-to-visible state model showed recovery signal offline, but candidate
action scoring collapsed to logged-action bias. The next credible step is
intervention data: evaluate each candidate branch from the same simulator state
and label it with detector recovery.

The safest first version should replay from episode start using the logged
action prefix instead of requiring Habitat internal simulator-state snapshots.
That makes the artifact reproducible from existing policy traces, detector
settings, and official dataset configuration.

## System Boundary

Create:

- `objectnav_core.evaluation.habitat_official_candidate_rollout_dataset`
- `objectnav_core.cli.export_habitat_official_candidate_rollout_dataset`
- focused tests for rollout labeling, replay behavior, CLI output, and package
  script registration

Modify:

- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix`
  for cost-aware summary artifacts.
- docs/devlog, docs/experiments, and docs/handoff after verification

The rollout labeler may reuse official eval helpers for Habitat config/env
creation, GPS/compass/depth interpretation, and detector traces. It should keep
its output diagnostic and separate from official benchmark summaries.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | `policy_trace.json` | Contains logged actions and `memory_prior.top_candidates`. |
| Input | Candidate dataset | JSON | Optional; used to filter candidate states and preserve candidate fields. |
| Input | Habitat config | YAML path plus dataset/scene paths | Same boundary as official eval CLI. |
| Input | Detector adapter | Python object or CLI detector args | Used only for target-visible rollout labels. |
| Input | Rollout limits | integers | Max states, candidates per state, replay horizon. |
| Output | Rollout dataset JSON | JSON | One row per evaluated candidate branch. |
| Output | Rollout CSV | CSV | Flat audit rows. |
| Output | Pre-decision state features | JSON object plus CSV columns | Carried on every rollout row and collapsed once per replay state in action-matrix reports. |

## Interfaces

Python API:

```python
export_official_candidate_rollout_dataset(
    policy_trace_path,
    output_dir=...,
    config_path=...,
    dataset_data_path=...,
    scene_root=...,
    split="val_mini",
    target_detector_adapter=detector,
    target_detector_min_confidence=0.25,
    max_states=None,
    candidates_per_state=5,
    rollout_horizon_steps=5,
    branch_followup_policy="left_scan",
    env_factory=None,
)

write_official_candidate_rollout_dataset_csv(dataset, path)
```

CLI:

```bash
python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/<run>/policy_trace.json \
  --output runs/habitat_official_objectnav/<rollout-output>/dataset.json \
  --csv-output runs/habitat_official_objectnav/<rollout-output>/rollouts.csv \
  --detector yolo_world \
  --target-detector-min-confidence 0.25 \
  --candidates-per-state 5 \
  --rollout-horizon-steps 5
```

Counterfactual first-action matrix:

```bash
python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/<run>/policy_trace.json \
  --output runs/habitat_official_objectnav/<rollout-output>/dataset.json \
  --csv-output runs/habitat_official_objectnav/<rollout-output>/rollouts.csv \
  --detector yolo_world \
  --branch-actions turn_left,turn_right,move_forward \
  --branch-followup-policy left_scan \
  --rollout-horizon-steps 5
```

Console script:

```bash
objectnav_habitat_official_candidate_rollout_dataset ...
```

## Data Flow

1. Load and sort policy trace steps by `(episode_index, step_index)`.
2. Select states with non-empty `memory_prior.top_candidates`.
3. For each selected state:
   - create a fresh Habitat env;
   - reset through episodes until `episode_index`;
   - replay logged actions before the target `step_index`;
   - record current detector visibility at the branch state;
   - extract pre-decision state features from the logged policy state and
     replayed observation before any branch action;
   - in candidate mode, for each top candidate, choose an initial
     candidate-conditioned action from candidate `bearing_error_rad` and
     center-depth clearance;
   - in action-matrix mode, branch each requested first action from the same
     replayed state;
   - continue for a short horizon with the configured branch follow-up policy:
     `left_scan` preserves the current diagnostic controller, while
     `repeat_first_action` repeats the branch action for symmetric
     macro-action labels;
   - call the detector on each rollout observation and record whether the
     branch is hidden-to-visible, visible-within-horizon, or invalid.
4. Emit rows containing source state metadata, candidate metadata, rollout
   actions, pre-decision features, detector evidence, and validity flags.
5. For action-matrix datasets, build a cost-aware report by grouping rows back
   into replay states, computing per-action recovery, time-to-visible, fastest
   action sets, strict fastest actions, and state-level oracle recovery while
   preserving exactly one pre-decision feature payload per state.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Logged replay reaches episode end before branch state | Mark state invalid | Emit skipped count; do not create candidate labels. |
| Env episode order differs from trace episode index | Episode metadata mismatch | Mark invalid with mismatch reason. |
| Trace lacks RGB at branch or rollout step | Detector call cannot run | Record missing RGB and keep label false/unavailable as appropriate. |
| Candidate lacks bearing/path fields | Field validation | Use safe fallback scan action and record missing feature flags. |
| Habitat unavailable on local machine | Import/runtime error | Unit tests use fake env; real export runs in Linux `habitat` env. |
| Candidate controller is not a full planner | Dataset metadata | Label as short-horizon branch rollout, not oracle viewpoint value. |
| Candidate branches collapse to one action | Branch-action histograms | Use action-matrix mode to collect local counterfactual labels. |
| Follow-up scan dominates first-action labels | Horizon-1 control export and rollout action-length histograms | Treat horizon-5 rows as recovery labels; use horizon-1 or a redesigned symmetric follow-up policy for immediate action learning. |
| Follow-up policy is not recorded | Dataset metadata audit | Store `branch_followup_policy` in JSON summaries and CSV rows indirectly through rollout actions. |
| Branch state is already target-visible | `current_target_visible` label | Filter current-visible rows when training hidden-to-visible recovery models. |
| State features leak labels | Schema review and tests | Feature extraction runs before rollout actions and excludes `labels`, action outcomes, fastest-action fields, and post-branch detector evidence. |
| Missing trace/observation feature fields | Null-safe feature extraction | Preserve `null`/false defaults and let model preprocessing impute numeric values. |

## Verification Plan

1. RED test: fake env plus sequence detector where two candidates from the same
   logged state produce different hidden-to-visible labels.
2. RED test: replay must execute the exact logged action prefix before
   branching.
3. RED CSV test: flat output preserves candidate rank and rollout labels.
4. RED CLI/packaging test: module writes JSON/CSV and console script is
   registered.
5. Local focused pytest, compileall, and `git diff --check`.
6. Linux focused pytest in `conda activate habitat`.
7. Linux smoke export on a small active-perception trace with low state/candidate
   limits before any larger run.
8. Linux action-matrix exports on all active traces at horizon 5 and horizon 1
   before training any action scorer.
9. Local fake-env test that `repeat_first_action` repeats each explicit branch
   action across the rollout horizon and that the CLI forwards the policy.
10. Local fake-dataset test that the action-matrix report identifies
    fastest-action ties and strict fastest actions, plus a CLI smoke that writes
    JSON and CSV.
11. Local RED/GREEN tests that rollout rows expose pre-decision geometry,
    depth, and detector-history features; action-matrix reports preserve them
    at the replay-state level; and the utility model consumes the numeric state
    features deterministically.

## Research Relevance

This module creates the missing supervision for a memory-conditioned active
perception candidate ranker. It moves the project from observational logged
action correlations toward intervention labels collected from the same state,
which is the kind of evidence needed for a defensible paper contribution.

The cost-aware report is the bridge from raw branch rollouts to learned active
memory retrieval: it exposes whether an action merely recovers eventually or
recovers faster than alternatives from the same replay state.

The first learned scorer should train on report rows, not raw rollout rows. Its
label is action utility: `1 / time_to_visible_steps` for recovering actions and
`0` for non-recovering actions. It must evaluate ranking by chosen-action
success, fastest-action membership, and time-to-visible regret. Leave-one
source-dataset evaluation is required before any online integration.

The first linear utility baseline is expected to be only a diagnostic. If it
does not beat always-`turn_left`, the next design should add stronger
state/action features rather than integrate the model online.

The pre-decision feature revision tests the next plausible paper contribution:
whether local geometry and evidence can explain when active memory retrieval
should turn left, turn right, or move forward from the same replay state. It is
still offline supervision. Passing tests or improving the offline utility model
does not imply official Habitat ObjectNav gains until a later online policy is
integrated and evaluated with official metrics.

The next diagnostic revision adds pre-decision state features to the
rollout/report/model path. These features may use only the logged policy state
and the replayed branch observation before any branch action is executed:
episode-relative agent pose, memory-prior geometry/evidence fields, selected
candidate aggregates, local depth clearance, and detector-history fields already
present in the policy trace. They must not use branch rollout outcomes,
fastest-action labels, Habitat oracle goal distance, shortest paths to the
object, or post-branch detector evidence.

## Open Questions

- Whether the diagnostic branch controller is too permissive. Initial Linux
  smokes produced valid rows but all-positive labels, so the next version may
  need Habitat simulator teleport/state restore or a stronger candidate-view
  controller to evaluate exact viewpoint cells.
- Whether action-matrix labels are sufficient to train a memory-conditioned
  local controller, or only a diagnostic for designing the exact viewpoint
  rollout controller. The first full active-trace export suggests horizon-5
  labels are mostly delayed recovery, while horizon-1 labels are too sparse for
  a useful scorer.
- Whether labels should predict raw detector recovery or a utility combining
  recovery, action cost, and travel distance. The repeat-first export makes
  binary recovery less confounded, but the strongest learning target now looks
  like time-to-visible or fastest-action ranking.
- How many branch rollouts are affordable per benchmark split before training a
  first candidate ranker.
