# Design Doc: Official Oracle Memory Prior Upper Bound

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Create a diagnostic Habitat memory-prior exporter that writes perfect
episode-specific target anchors into the same JSON schema consumed by the
official memory policies.

This lets the evaluator compare noisy discovered memory against an oracle
memory upper bound while keeping the navigation backend interface unchanged.

## Non-Goals

- Do not claim oracle-memory runs as benchmark-valid ObjectNav results.
- Do not train or tune a new memory model in this slice.
- Do not change official Habitat metrics or success computation.
- Do not hard-code a particular HM3D scene, object category, map, or robot.
- Do not replace the selected TargetNav backend; the oracle prior must route
  through the existing backend selector.

## Background

The current TargetNav memory policy can execute remembered anchors through
`occupancy_grid`, `fmm_grid`, `ddppo_pointnav`, or `oracle_follower`. The latest
YOLO-memory smoke showed that the backend/coordinate path works, but the
remembered anchor can be badly localized. We need a clean upper bound to answer
whether failures now come from memory quality or downstream execution.

Official Habitat episodes expose privileged goal/viewpoint positions and the
episode start pose. Those positions can be converted into the existing
`episode_start_relative` memory frame (`x=right`, `z=forward`). The exporter must
tag the resulting prior as oracle-only so future reports cannot confuse it with
a learned or detector-derived memory result.

## System Boundary

Owned by this slice:

- an oracle-memory export module that iterates Habitat episodes and writes
  memory-prior JSON;
- optional `episode_id` metadata on memory anchors so multiple same-scene,
  same-category episodes can coexist in one prior;
- selector behavior that prefers matching episode-specific anchors while
  preserving generic anchors from existing priors;
- manifest source-validity reporting for oracle memory priors;
- CLI entry point and focused regression tests.

Outside this slice:

- learned/discovered memory quality improvements;
- non-oracle ObjectNav benchmark claims;
- DDPPO checkpoint contract repair;
- robot Nav2/FASTLIO2 backend implementation.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Habitat config | `OfficialObjectNavRunConfig` fields | Same config/dataset/scene-root inputs as official eval. |
| Input | Habitat episode | `episode_id`, `scene_id`, `object_category`, `start_position`, `start_rotation`, `goals` | Goal/viewpoint positions are privileged labels. |
| Output | Memory prior | JSON with `anchors` and `metadata` | Same anchor schema used by current memory policies. |
| Output | Anchor | `OfficialMemoryAnchor` | Includes `episode_id`, scene/category, confidence `1.0`, and oracle source tag. |
| Output | Manifest validity | `source_validity=oracle_diagnostic_only` | Prevents benchmark-valid interpretation. |

## Interfaces

New CLI:

```bash
objectnav_habitat_official_oracle_memory_prior \
  --output runs/.../oracle_memory_prior.json \
  --max-episodes 4
```

Existing eval path:

```bash
objectnav_habitat_official_objectnav_eval \
  --policy memory_active_perception_frontier_targetnav \
  --targetnav-backend fmm_grid \
  --memory-prior-path runs/.../oracle_memory_prior.json
```

Core helpers:

- `export_habitat_official_oracle_memory_prior(...)`
- `make_official_oracle_memory_anchor(...)`
- `_world_position_to_episode_relative_xz(...)`
- `select_official_memory_anchor(..., episode_id=...)`

## Data Flow

1. Create the same Habitat env used by the official evaluator.
2. For each selected episode, reset the env and read its privileged target
   goal/viewpoint positions.
3. Select the nearest goal/viewpoint from the current simulator state when the
   pathfinder is available; otherwise fall back to the first episode goal.
4. Convert that Habitat world position into episode-start-relative `x/z`.
5. Write one oracle anchor per episode, with `episode_id` and diagnostic
   metadata.
6. The existing memory policy loads the prior and selects the episode-specific
   anchor before falling back to generic anchors or exploration.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Episode has no goals/viewpoints | No positions from `_episode_goal_positions` | Skip episode and report skipped count. |
| Missing start pose | `start_position` or `start_rotation` cannot parse | Skip episode and report skipped count. |
| Invalid object category | Empty `object_category` | Skip episode and report skipped count. |
| Habitat unavailable locally | Env creation fails | Unit tests use fake env; real smoke runs on Linux Habitat host. |
| Multiple anchors match an episode | Selector sees episode-specific and generic anchors | Prefer exact `episode_id`, then highest confidence. |
| Oracle prior used in eval | Manifest detects oracle metadata | Mark `oracle_memory_prior_diagnostic`; keep official metrics separate. |

## Verification Plan

1. Add failing tests for:
   - round-tripping optional `episode_id` in official memory anchors;
   - selector preference for exact episode-specific anchors;
   - world-to-episode-relative conversion from Habitat goal position;
   - fake-env oracle prior export and metadata validity;
   - manifest marking oracle priors as diagnostic-only.
2. Implement the minimal schema, exporter, CLI, and manifest plumbing.
3. Run focused unit tests locally.
4. Run `compileall` and `git diff --check`.
5. If the Linux Habitat host is reachable, sync the slice and run focused tests
   plus a tiny oracle-memory export/eval smoke.

Completed verification:

- Local focused RED tests failed before implementation for missing `episode_id`,
  missing oracle-prior manifest validity, and missing exporter/CLI.
- Local focused tests passed after implementation: `7 passed`.
- Local evaluator/memory/CLI/packaging slice passed: `119 passed`.
- Local full `src/objectnav_core/tests` suite passed: `523 passed`.
- Local `compileall` and `git diff --check` returned cleanly.
- Remote Habitat focused tests passed: `7 passed`.
- Remote Habitat evaluator/memory/CLI/packaging slice passed: `119 passed`.
- Remote Habitat `compileall` returned cleanly.
- Remote HM3D `val_mini` oracle-memory export wrote four episode-specific
  anchors with zero skipped episodes.
- Remote diagnostic evals:
  - oracle memory + oracle backend, goal radius `1.0`: SR `0/4`, SPL `0.0`,
    SoftSPL `0.6810`, mean distance `2.2272`;
  - oracle memory + oracle backend, goal radius `0.2`: SR `2/4`, SPL
    `0.4503`, SoftSPL `0.7533`, mean distance `1.5385`;
  - oracle memory + FMM backend: SR `0/4`, SPL `0.0`, SoftSPL `0.0010`,
    mean distance `5.8806`.

## Research Relevance

This is the clean ablation the paper story needs:

- oracle memory + oracle backend isolates the best possible memory/execution
  path under privileged labels;
- oracle memory + FMM or DDPPO shows executor limitations with perfect memory;
- YOLO/discovered memory + oracle backend shows memory-quality limitations.

The result should define the gap that future memory learning, multi-view
fusion, and stale-anchor verification must close.

## Open Questions

- Should future priors include multiple oracle viewpoints per episode rather
  than one nearest anchor?
- Should the benchmark-facing non-oracle baseline use FMM, DDPPO, or a learned
  local policy as the default executor once memory quality improves?
