# Design Doc: Official View-Quality Memory Selection

Date: 2026-05-31
Owner: Codex
Status: Implemented; diagnostic smoke negative

## Goal

Add a non-privileged memory-write selection policy for official Habitat memory
discovery that prefers target-visible viewpoints likely to be useful for later
reacquisition, instead of ranking candidates only by detector confidence.

## Non-Goals

- Do not use Habitat target poses, success labels, oracle semantic masks, or
  official target `view_points`.
- Do not claim benchmark validity from a four-episode smoke.
- Do not replace the detector-positive viewpoint prior; keep it as a
  privileged diagnostic ceiling.
- Do not tune the terminal TargetNav backend in this slice.
- Do not introduce learned ranking yet; this is the transparent baseline that
  defines features and artifacts for a later learned model.

## Background

The targetnav-equated comparison holds terminal navigation fixed and shows the
current memory rows underperform `no_memory_targetnav`. The discovered DINO
memory priors export many target detections, but the selection rule keeps the
highest-confidence candidates. Confidence is a detector belief, not a
navigation-memory quality measure. For ObjectNav memory, a better write should
prefer the robot viewpoint where the target is centered and occupies a larger
image region, because that viewpoint is more likely to support later
reacquisition and official STOP success.

## System Boundary

Extend only official memory discovery:

- `objectnav_core.evaluation.habitat_official_memory_discovery`
- `objectnav_core.cli.run_habitat_official_memory_discovery`
- focused discovery tests and docs

The official query/evaluator policies and memory-prior JSON schema remain
compatible. Extra diagnostic fields are written to `detections.csv` and summary
metadata.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Detection confidence | float | Preserved for compatibility and tie-breaking. |
| Input | Detection bbox | xyxy pixels | Used to compute centering and area. |
| Input | RGB/depth observation | Habitat observation | Existing observation source; depth is diagnostic in this slice. |
| Input | Anchor selection policy | CLI/config string | `confidence` preserves current behavior; `view_quality` is new. |
| Output | Memory prior | JSON | Same anchor schema as today. |
| Output | Detection CSV | CSV | Adds view-quality evidence fields and selection policy. |
| Output | Summary metadata | JSON | Records `anchor_selection_policy`. |

## Interfaces

```bash
python -m objectnav_core.cli.run_habitat_official_memory_discovery \
  --output runs/.../grounding_dino_view_quality_robot_viewpoint_prior_4ep_20260531_v1 \
  --detector grounding_dino \
  --grounding-dino-max-image-side 384 \
  --anchor-mode robot_viewpoint \
  --anchor-selection-policy view_quality \
  --max-anchors-per-episode 1 \
  --max-episodes 4 \
  --max-steps 100
```

Programmatic API:

```python
run_habitat_official_memory_discovery(
    output_dir,
    detector_adapter=detector,
    anchor_mode="robot_viewpoint",
    anchor_selection_policy="view_quality",
)
```

## Data Flow

1. Run the existing exploration policy and detector.
2. For every target-category detection, compute existing anchor candidates.
3. Also compute detector view evidence:
   - bbox area fraction;
   - center offset fraction;
   - depth median when available.
4. If `anchor_selection_policy=confidence`, keep the current confidence sort.
5. If `anchor_selection_policy=view_quality`, sort by:
   - larger bbox area first;
   - smaller absolute center offset second;
   - higher confidence third.
6. Apply `max_anchors_per_episode` after this ranking.
7. Write the selected anchors and evidence rows.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Large false positive selected | Official query remains poor; CSV shows large bbox evidence | Keep confidence as tie-breaker; later use multi-view consistency or learned ranker. |
| Off-center close view discarded despite being recoverable | Anchor-quality report shows worse nearest-viewpoint error | Keep policy selectable and compare against confidence ranking. |
| Depth is normalized or missing | CSV evidence has missing/normalized depth | Do not make depth primary in first ranker; use it for diagnostics. |
| Better selected viewpoint still fails official STOP | Targetnav-equated smoke remains negative | Add local scan/servo after returning to remembered viewpoint. |

## Verification Plan

1. RED/GREEN unit test: `view_quality` selects a lower-confidence but larger,
   centered robot-viewpoint candidate over a higher-confidence off-center one.
2. RED/GREEN unit test: default `confidence` selection behavior is unchanged.
3. RED/GREEN CLI test: `--anchor-selection-policy view_quality` is forwarded.
4. Run focused discovery and CLI tests locally.
5. Run `compileall` and `git diff --check`.
6. Sync touched code/tests/docs to Linux and run the focused tests in conda env
   `habitat`.
7. Run a four-episode Grounding-DINO smoke:
   - export `robot_viewpoint` memory with `view_quality`;
   - compare anchor quality against detector-positive viewpoint and oracle
     references;
   - query with `memory_active_perception_frontier_targetnav` plus
     `targetnav_backend=oracle_follower`.

## Implementation Result

Implemented `anchor_selection_policy=confidence|view_quality`.

- `confidence` preserves the previous detector-confidence ranking.
- `view_quality` ranks candidates by larger bbox area, smaller absolute center
  offset, then confidence.
- Discovery summaries and memory-prior metadata record
  `anchor_selection_policy`.
- `detections.csv` now records bbox area, center offset, depth evidence, and the
  selection policy for selected anchors.

Local and remote focused tests passed for discovery, discovery CLI, and ROS
packaging (`17 passed` on both machines). Local and remote `compileall` checks
for the touched discovery module and CLI were clean.

Four-episode Grounding-DINO diagnostic:

- Artifact:
  `runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_view_quality_prior_4ep_100steps_20260531_v1`.
- Parameters:
  `anchor_mode=robot_viewpoint`, `anchor_selection_policy=view_quality`,
  `max_anchors_per_episode=1`.
- Detections: `666` total, `620` label-filtered, `3` exported anchors.
- Anchor quality vs detector-positive viewpoint prior:
  selected mean error `6.891912 m`, nearest mean error `6.891912 m`,
  good anchors `0/4`, one missing reference.
- Anchor quality vs oracle object prior:
  selected mean error `5.543938 m`, nearest mean error `5.543938 m`,
  good anchors `0/4`, one missing reference.
- Query with `memory_active_perception_frontier_targetnav` and
  `targetnav_backend=oracle_follower` stayed at SR `0/4`, SPL `0.0`,
  SoftSPL `0.0`, mean distance-to-goal `6.0735965967178345`.

Interpretation:

View-quality ranking is not enough. It selected only three covered anchors, and
two selected viewpoints were still at the episode origin with very small target
boxes. This turns the negative targetnav-equated result into a sharper
diagnosis: passive detection ranking cannot solve the memory-write problem when
exploration itself does not reach useful confirmed viewpoints. The next method
should label and learn online write/option utility from actual approach
rollouts, or explicitly execute a stronger local approach/scan option before
committing memory.

## Research Relevance

This is the first non-privileged step toward confirmed-viewpoint memory. It
directly attacks the failure exposed by the targetnav-equated comparison:
current memory priors choose bad targets even when terminal navigation is held
fixed. A view-quality selector is not the final top-tier algorithm, but it
turns memory writing into an explicit, measurable module with features that can
later support a learned viewpoint ranker.

## Open Questions

- Should view-quality ranking cluster repeated detections before selecting
  anchors?
- Should heading and target bearing be added to the memory schema before real
  robot deployment?
- How much of the remaining gap to the privileged detector-positive viewpoint
  prior is selection quality versus exploration coverage?
