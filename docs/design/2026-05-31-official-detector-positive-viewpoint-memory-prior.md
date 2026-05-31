# Design Doc: Official Detector-Positive Viewpoint Memory Prior

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Port the earlier Grounding-DINO `detector_positive` memory-anchor idea into the
official Habitat memory-prior path: store a navigable target-viewpoint anchor
only after the detector confirms the target from that viewpoint.

## Non-Goals

- Do not claim benchmark-valid ObjectNav performance from this exporter.
- Do not replace the online discovery policy.
- Do not remove bbox-depth projected discovery anchors.
- Do not use this as a final paper result without a non-privileged viewpoint
  proposal source.

## Background

Earlier Grounding-DINO lifecycle and navmesh runs achieved `6/6`, `12/12`, and
later `24/24` diagnostic success because they did not store arbitrary single
bbox-depth projections. They selected detector-positive, navigable viewpoints
and used shared fallback/candidate evidence. The first official DINO discovery
smoke did not reproduce that: it exported only one chair anchor, and that
anchor was about `5.65 m` from the oracle chair anchor.

The key difference is the anchor representation. For ObjectNav, a remembered
place that can see the object is often more useful than a noisy single-frame
object-center estimate.

## System Boundary

Add a diagnostic exporter:

- `objectnav_core.evaluation.habitat_official_detector_viewpoint_memory_prior`
- `objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior`

The exporter owns:

- scanning official episode goal viewpoints;
- restoring observations at those viewpoints;
- running an injected detector;
- exporting the first detector-positive viewpoint as an official memory anchor.

It depends on privileged Habitat episode goal/viewpoint metadata, so its output
is diagnostic-only.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Habitat official config/dataset | paths | Same defaults as official ObjectNav eval. |
| Input | Detector backend | CLI enum | Defaults to Grounding-DINO. |
| Input | Viewpoint cap | int | Bounds runtime per episode. |
| Output | Memory prior | JSON | `episode_start_relative`, detector-positive viewpoint anchors. |
| Output | Summary | JSON/stdout | Counts positives, skipped episodes, and caveats. |

## Interfaces

```bash
python -m objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior \
  --output runs/habitat_official_objectnav/dino_viewpoint_prior.json \
  --max-episodes 4 \
  --max-viewpoints-per-episode 8 \
  --grounding-dino-max-image-side 384
```

## Data Flow

1. Reset each official episode.
2. Read goal `view_points` from the episode.
3. Restore the simulator camera to each candidate viewpoint.
4. Run the detector on RGB.
5. If a detection label matches the episode target category and passes the
   confidence threshold, convert the viewpoint world position into
   episode-start-relative `x/y/z`.
6. Write the anchor with diagnostic metadata and continue to the next episode.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No episode viewpoints | skipped episode reason | record `missing_viewpoints`. |
| Restore fails | skipped episode reason/count | try remaining viewpoints. |
| Detector misses all viewpoints | skipped episode reason | record `no_detector_positive_viewpoint`. |
| DINO OOM | command failure | keep image-side cap `384`. |
| Diagnostic prior used as benchmark claim | metadata | mark source validity as privileged viewpoint diagnostic. |

## Verification Plan

1. Unit-test fake-env export where a detector-positive viewpoint writes an
   episode-relative anchor.
2. Unit-test no-positive skip accounting.
3. Unit-test CLI argument forwarding and default DINO weights.
4. Run local focused tests, full tests, compileall, and `git diff --check`.
5. Sync to Linux, run focused tests, export a DINO viewpoint prior, then query
   it through the existing official oracle-backend diagnostic.

## Implementation Notes

Implemented files:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_detector_viewpoint_memory_prior.py`
- `src/objectnav_core/objectnav_core/cli/export_habitat_official_detector_viewpoint_memory_prior.py`
- `src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_ros_packaging.py`

The exporter writes the same official memory-prior JSON schema as the existing
oracle and detector-discovery paths, but marks the source as
`habitat_official_detector_positive_viewpoint_memory_prior` with
`source_validity=privileged_viewpoint_detector_diagnostic`.

Remote Habitat diagnostic results:

- 4-episode, 8-viewpoint cap: `13` restored viewpoints, `9` detections,
  `3` detector-positive target viewpoints, `3` exported anchors.
- 4-episode, 32-viewpoint cap: `37` restored viewpoints, `27` detections,
  `3` detector-positive target viewpoints, `3` exported anchors.
- In both exports, the tv-monitor episode had no Grounding-DINO positive
  viewpoint and was skipped.
- Querying the 8-viewpoint prior with the oracle TargetNav backend produced
  official SR `3/4`, SPL `0.5891520577351606`, SoftSPL
  `0.615534292748382`, and mean distance-to-goal `1.6792370742186904`.
- After adding ObjectNav category aliases to the Grounding-DINO adapter, the
  same 4-episode, 32-viewpoint diagnostic exported `4/4` anchors after only `6`
  restored viewpoints. Querying that prior with the oracle TargetNav backend
  produced official SR `4/4`, SPL `0.8134277193790571`, SoftSPL
  `0.8060506098824843`, and mean distance-to-goal `0.04706096462905407`.

These are diagnostic numbers only. They use official target viewpoints and an
oracle executor, so they are useful for decomposition but invalid as benchmark
claims.

## Per-Viewpoint Trace Extension

The first remote diagnostic exposed a specific failure: `tv_monitor` had no
Grounding-DINO positive even after restoring 37 official viewpoints. To make
that actionable, extend the exporter without changing the memory-prior schema:

- write a sibling `viewpoint_trace.json` when requested;
- optionally save restored RGB frames under `viewpoint_images/`;
- record one trace row per restored or failed viewpoint;
- include every detector output with category, confidence, bbox, and
  `matches_target`;
- mark whether the row became the exported memory anchor.

The trace is diagnostic evidence, not policy input. It answers whether a missed
anchor is due to missing official viewpoints, restore failure, detector miss,
wrong label, confidence threshold, or category prompt mismatch.

The first trace showed the `tv_monitor` miss was a prompt/label mismatch:
Grounding-DINO was prompted with `tv_monitor` and produced only `plant`/`bed`
labels across the skipped episode. The adapter now expands ObjectNav aliases
for prompts, e.g. `tv_monitor -> tv monitor. television. tv.`, and maps accepted
aliases back to the canonical ObjectNav label. This fixed the privileged
viewpoint diagnostic, but the opportunistic bbox-depth discovery path still
produced SR `0/4` with the oracle backend, confirming that online anchor
localization remains the main method bottleneck.

## Research Relevance

This bridges the gap the user pointed out: previous DINO results worked because
they used detector-positive viewpoints. The exporter lets us test that idea in
the official memory-prior interface before designing a non-privileged online
viewpoint proposer.
