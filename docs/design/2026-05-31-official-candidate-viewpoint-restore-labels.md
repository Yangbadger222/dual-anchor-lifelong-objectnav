# Design Doc: Official Candidate-Viewpoint Restore Labels

Date: 2026-05-31
Owner: Codex
Status: Implemented and smoke-tested

## Goal

Export detector labels measured from memory-policy candidate viewpoints, not
only from the exact current policy view. For each candidate-bearing memory query
state, replay the official Habitat episode prefix to the logged decision state,
restore or teleport to each selected top candidate viewpoint, scan headings at
that viewpoint, and record whether the target category is visible.

## Non-Goals

- Do not claim an online ObjectNav policy improvement.
- Do not replace official Habitat success, SPL, SoftSPL, or distance-to-goal
  metrics.
- Do not train or integrate a controller in this slice.
- Do not introduce persistent `habitat_world` memory coordinates.
- Do not assume a specific robot, camera, campus, or map.

## Background

The repeat-first action-matrix labels exposed useful diagnostic states, but the
learned action utility model was not robust under held-out validation. Exact
state-restore labels then showed that only `1/24` phase/path-selected states in
the bounded 20-episode YOLO smoke were already target-visible at the restored
current view. The next supervision target should answer a stronger question:
if the agent evaluates the memory policy's candidate viewpoint itself, would the
target be visible there?

The active-perception policy records candidate `viewpoint_cell` and
`frontier_cell` values from an `OccupancyFrontierMap`. Those cells are in the
same episode-relative grid used by `_world_to_grid_cell`: internal
`x=right`, `z=forward`, with Habitat GPS convention `[forward, right]`. The
exporter must invert that grid frame without treating it as persistent Habitat
world memory.

## System Boundary

The change belongs to the official candidate-rollout evaluation layer. It
extends the existing state-restore replay path and detector-label plumbing, but
emits a separate dataset task and schema. It depends on:

- policy traces containing candidate-bearing `memory_prior.top_candidates`
- official Habitat env replay to the logged state
- a detector adapter with `detect(rgb)` behavior
- a pose-restore adapter for candidate viewpoint observations

The exporter owns:

- candidate-state selection
- top-K candidate expansion
- grid-cell to episode-relative pose conversion
- candidate viewpoint restore attempts
- heading-sweep detector labeling
- stable JSON and CSV outputs

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | JSON | Existing official policy trace. |
| Input | Habitat env | Habitat env or fake test env | Replayed to the logged decision state. |
| Input | Detector adapter | Python object | Same contract as rollout/state-restore exporters. |
| Input | Grid metadata | CLI/API values | Defaults match `create_occupancy_frontier_map`: size `81`, cell size `0.25m`. |
| Input | Heading count | CLI/API integer | Default fixed scan count for candidate viewpoint labels. |
| Output | Candidate-viewpoint dataset | JSON | One row per candidate viewpoint label attempt. |
| Output | CSV | CSV | Stable schema for audits and model training. |

Each output row records:

- source trace, episode, scene, category, and step metadata
- current state action/decision and numeric predecision state features
- candidate rank/count and candidate score fields
- `viewpoint_cell`, `frontier_cell`, grid defaults, and converted
  episode-relative candidate `x/z`
- restore validity and invalid reason
- heading-sweep metadata and per-heading detector visibility summary
- labels separating current-view visibility from candidate-viewpoint visibility

## Interfaces

New API:

- `export_official_candidate_viewpoint_restore_dataset(...)`
- `write_official_candidate_viewpoint_restore_dataset_csv(...)`

New CLI:

```bash
python -m objectnav_core.cli.export_habitat_official_candidate_viewpoint_restore_dataset \
  <policy_trace.json> \
  --output <dataset.json> \
  --csv-output <labels.csv> \
  --candidates-per-state 5 \
  --viewpoint-heading-count 8 \
  --state-sampling active_phase_path
```

The CLI should reuse existing exporter flags:

- Habitat config/data/scene/split
- detector selection and detector thresholds
- category list
- `max_states`
- `max_states_per_category`
- `max_states_per_category_episode`
- `state_sampling`

## Data Flow

1. Load the policy trace and select candidate-bearing states using the existing
   sampling logic.
2. For each selected state, create an env and replay logged actions to the
   exact decision state.
3. Detect target visibility at the restored current view so candidate labels
   can distinguish current-visible states from hidden-to-visible candidate
   recoveries.
4. Expand `memory_prior.top_candidates` up to `candidates_per_state`.
5. Convert each `viewpoint_cell` to episode-relative candidate `x/z` using the
   occupancy-map inverse:
   `x_m = (col - origin_col) * cell_size_m`,
   `z_m = (origin_row - row) * cell_size_m`.
6. Restore or teleport the agent to the candidate viewpoint. In real Habitat,
   map episode-relative `x/z` through the episode start pose and rotation; in
   tests, use a fake env hook with the same episode-relative interface.
7. Sweep `viewpoint_heading_count` evenly spaced episode-relative headings at
   that viewpoint and run the target detector on each resulting observation.
8. Write one row per candidate with validity, evidence, and labels.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Replay fails before state | `valid_state_restore=false` | Keep candidate rows with label unavailable and replay invalid reason. |
| Candidate lacks valid `viewpoint_cell` | conversion returns no pose | Mark candidate invalid; do not treat as negative. |
| Candidate pose cannot be restored | pose adapter returns failure | Mark `valid_candidate_restore=false` with reason. |
| Candidate pose snaps too far from requested point | snap distance exceeds tolerance | Mark invalid or record snapped pose, depending on adapter result. |
| Detector unavailable or RGB missing | `label_available=false` | Keep row but exclude from supervised negatives. |
| Current state already target-visible | current label positive | Preserve row but set hidden-to-visible candidate label false. |
| Grid defaults drift from policy defaults | row records grid size/cell size/origin | Future traces should carry explicit grid metadata before policy defaults change. |
| Heading sweep overstates one-action visibility | labels name scan semantics explicitly | Do not compare scan labels directly to one-step action labels. |

## Verification Plan

- RED test: converting a candidate `viewpoint_cell` with default grid metadata
  produces the expected episode-relative `x/z` with Habitat GPS ordering
  preserved.
- RED test: candidate-viewpoint exporter expands top-K candidates and calls the
  fake env candidate restore hook with the converted episode-relative pose.
- RED test: heading-sweep labels report a positive candidate when any heading
  sees the target and preserve current-view hidden status.
- RED test: invalid replay or invalid candidate restore yields
  `label_available=false` rather than a false negative.
- RED test: CSV writer and CLI write the new schema.
- Run focused local tests, full local suite, `compileall`, `git diff --check`,
  and touched-file whitespace scan.
- Sync touched files to Linux and run targeted tests in conda env `habitat`.
- Run a bounded real Habitat/Yolo smoke on the 20-episode phase/path trace and
  compare candidate-viewpoint coverage with current-view state-restore labels.

## Research Relevance

This dataset is the next step toward a real memory-based ObjectNav system. It
tests whether remembered candidate viewpoints contain detector-confirmable
evidence when the current view does not. If candidate-viewpoint labels are much
richer than current-view labels, they can support a learned candidate-ranking or
viewpoint-selection model. If they are not richer, the research direction should
shift toward stronger memory anchoring, more informative exploration labels, or
better detector/viewpoint models rather than polishing local action heuristics.

## Open Questions

- How many headings are enough to approximate active viewpoint scanning without
  making the label too optimistic?
- Should future policy traces store explicit occupancy-map grid metadata and
  memory anchor coordinates so heading selection can orient toward the remembered
  anchor instead of using a uniform scan?
- Should current-visible rows be excluded from candidate-ranker training or used
  as a separate calibration class?

## Implementation Note

The implementation adds a separate candidate-viewpoint restore exporter and CLI.
Local focused tests passed with `23` tests after adding a regression for
Habitat-Sim RGBA candidate-restore observations. The full local test suite
passed with `428` tests, and local compileall, diff check, and touched-file
whitespace scan were clean. Linux targeted tests in conda env `habitat` passed
with `23` tests.

The bounded real Habitat/Yolo smoke artifact is:

- `runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1`

It produced `24` states, `120` candidate rows, `120/120` valid candidate
restores, `74/120` visible candidate rows, and `69/120` hidden-to-visible
candidate rows. At the state level, `16/24` states had at least one visible
candidate viewpoint and `15/24` had at least one hidden-to-visible candidate
viewpoint, compared with `1/24` visible states in the exact current-view
state-restore artifact.
