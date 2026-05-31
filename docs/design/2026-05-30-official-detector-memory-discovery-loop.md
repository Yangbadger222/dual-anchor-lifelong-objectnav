# Design Doc: Official Detector Memory Discovery Loop

Date: 2026-05-30
Owner: Codex
Status: Implemented core loop, not benchmark-validated

## Goal

Generate official memory-prior JSON artifacts from detector observations inside
the official Habitat ObjectNav observation/action loop.

This connects the previous episode-relative projection helper to an actual
"saw object, wrote memory" workflow.

## Non-Goals

- Do not claim benchmark performance from the first generated priors.
- Do not add GPT/language grounding in this slice.
- Do not force lifecycle `habitat_world` anchors into the official policy.
- Do not require a real detector in unit tests; tests should use an injected
  detector adapter.

## Background

The project now has:

- an official ObjectNav action loop that records Habitat-provided SR/SPL;
- a frame-correct `episode_start_relative` memory policy;
- a projection helper that converts detector bbox plus official RGB-D/GPS/
  compass observation into an `OfficialMemoryAnchor`.

The missing next step is a discovery loop that can run before a query run,
collect detector positives, write `memory_prior.json`, and record enough trace
data to audit where each memory came from.

## System Boundary

Add:

- `objectnav_core.evaluation.habitat_official_memory_discovery`

The module owns:

- iterating official env episodes and steps;
- calling an injected detector adapter on `rgb`;
- filtering detections by current episode category;
- projecting kept detections into episode-relative anchors;
- writing `memory_prior.json`, `summary.json`, and `detections.csv`.

It reuses existing official policy action selection for exploration. It does
not own detector model loading in this first slice; model factory/CLI wiring can
come after the core loop is tested.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Env | Habitat-like env | Must expose `reset`, `step`, `current_episode`, and `get_metrics`. |
| Input | Detector adapter | object with `detect(rgb)` | Returns `Detection` records. |
| Input | Policy | official policy name | Defaults to `occupancy_frontier` for exploration. |
| Output | Memory prior | JSON | Official `{"anchors": [...]}` payload. |
| Output | Detection trace | CSV | Episode, step, bbox, confidence, projected anchor. |
| Output | Summary | JSON | Counts, policy, artifact paths, caveats. |

## Interfaces

```python
run_habitat_official_memory_discovery(
    output_dir,
    env_factory=...,
    detector_adapter=...,
    policy="occupancy_frontier",
    max_episodes=1,
    max_steps=100,
)
```

The output memory prior is still source-labeled as detector-generated and
`not_benchmark_validated` until a documented discovery/query split is run.

## Data Flow

1. Reset official env for each discovery episode.
2. Read episode object category and scene id.
3. Run detector on `observation["rgb"]`.
4. Keep detections whose normalized label matches the episode target category.
5. Project each kept detection with `estimate_episode_detection_anchor`.
6. Sort projected anchors by confidence and cap anchors per episode/category.
7. Select the next official action using the configured exploration policy.
8. Write prior, trace, and summary artifacts.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Observation lacks RGB/depth | missing key | skip detection and record skipped count. |
| Detector finds wrong category | label filter | do not write memory. |
| Depth projection fails | projection returns `None` | record skipped projection count. |
| Many duplicate detections | per-episode cap/confidence sort | keep highest confidence anchors first. |
| Discovery prior overfits same episode | manifest caveat | compare only under documented protocol. |

## Verification Plan

1. Unit-test fake env plus static detector writes a valid memory prior.
2. Unit-test wrong-category detections are filtered out.
3. Unit-test projection failures are counted and omitted.
4. Unit-test trace CSV includes source bbox/confidence/anchor coordinates.
5. Unit-test per-episode caps keep the highest-confidence projected anchors.
6. Unit-test generated priors can be loaded by `memory_guided_frontier` and
   acted on without a fallback.
7. Run local focused tests and full suite.
8. Sync to Linux and run focused tests in conda env `habitat`.

## Research Relevance

This turns the official memory pipeline from hand-authored priors into
detector-produced memory artifacts. It is still only the first discovery side
of a full lifelong benchmark, but it is the right non-oracle interface for the
paper direction: perception produces memory; a later policy consumes memory
under official metrics.
