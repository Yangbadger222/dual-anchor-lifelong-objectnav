# Design Doc: Official Robot-Viewpoint Memory Anchor

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Add a non-privileged memory-discovery mode that stores the robot's current
episode-relative position when the detector sees the target, rather than
storing a single-frame depth-projected object center.

## Non-Goals

- Do not solve final visual servoing or SLAM loop closure in this slice.
- Do not remove projected bbox-depth anchors; keep them as a baseline and
  diagnostic.
- Do not claim benchmark validity from 4-episode smoke runs.
- Do not require privileged Habitat target viewpoints.

## Background

The corrected detector-positive viewpoint diagnostic reaches `4/4` with an
oracle TargetNav backend because it stores a navigable place from which the
object is visible. The opportunistic projected-anchor prior exports many more
anchors after Grounding-DINO aliasing, but those anchors remain meters away
from both oracle object anchors and detector-positive viewpoint anchors.

This points to the memory representation: ObjectNav needs a place to revisit
and reacquire the object, not necessarily a noisy object-center estimate from a
single RGB-D frame.

## System Boundary

Extend the existing official discovery pipeline:

- `objectnav_core.evaluation.official_episode_memory`
- `objectnav_core.evaluation.habitat_official_memory_discovery`
- `objectnav_core.cli.run_habitat_official_memory_discovery`

The new mode exports official memory-prior anchors using the current robot
pose from the observation's GPS/compass frame. The current detection source,
confidence, category, scene id, and episode id remain attached to the anchor.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | RGB observation | Habitat observation | Runs detector as before. |
| Input | GPS/compass pose | Habitat observation | Current pose in episode-relative frame. |
| Input | Detection bbox/confidence | detector output | Used as evidence, not as target point. |
| Output | Memory prior | JSON | Anchor `x_m/z_m` are robot viewpoint pose. |
| Output | Summary metadata | JSON | Includes `anchor_mode=robot_viewpoint`. |
| Output | Detection CSV | CSV | Records anchor mode and evidence rows. |

## Interfaces

```bash
python -m objectnav_core.cli.run_habitat_official_memory_discovery \
  --output runs/.../grounding_dino_robot_viewpoint_prior_4ep_100steps_20260531_v1 \
  --max-episodes 4 \
  --max-steps 100 \
  --detector grounding_dino \
  --grounding-dino-max-image-side 384 \
  --anchor-mode robot_viewpoint
```

`--anchor-mode projected_detection` preserves the current bbox-depth behavior.

## Data Flow

1. Run the existing exploration policy and detector on RGB observations.
2. Filter detections by target category and confidence.
3. If `anchor_mode=projected_detection`, keep the existing bbox-depth
   projection path.
4. If `anchor_mode=robot_viewpoint`, write an anchor at the current
   episode-relative robot position from the observation.
5. Keep source strings and CSV rows tied to the detection that justified the
   memory.
6. Query policies can navigate to that remembered viewpoint; later local
   camera servoing or scan behavior reacquires and approaches the target.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Missing GPS | helper returns origin today | record as a limitation; later add stricter validity if needed. |
| Detector sees object from too far away | quality report large error vs privileged viewpoints | add evidence filters or multi-view confirmation later. |
| Viewpoint is target-visible but not close enough for stop | oracle query low SR against object center | add local scan/servo after returning to viewpoint. |
| Multiple observations of same object | confidence ranking picks a weak viewpoint | add viewpoint scoring/ranking after the first smoke. |

## Verification Plan

1. RED/GREEN unit test that `robot_viewpoint` anchors use current GPS pose even
   when depth projection would fail.
2. RED/GREEN CLI forwarding test for `--anchor-mode`.
3. Local focused tests for discovery, memory anchor quality, and packaging.
4. Remote focused tests in the Habitat conda environment.
5. Remote 4-episode Grounding-DINO smoke for `robot_viewpoint` mode.
6. Compare the resulting prior against detector-positive viewpoint and oracle
   priors with the anchor-quality report, then query with oracle TargetNav.

## Implementation Notes

Implemented `anchor_mode=robot_viewpoint` in the existing official discovery
pipeline. The mode exports the robot's current episode-relative `x_m/z_m`
using the same detection source, category, confidence, scene id, and episode id
as the projected anchor path. The original `anchor_mode=projected_detection`
remains the default for backward-compatible CLI behavior.

First 4-episode Grounding-DINO smoke result:

- `robot_viewpoint` exported the same `17` target-category anchors as the
  fixed projected run.
- All matched anchors now carry exact episode ids.
- Against the privileged detector-positive viewpoint prior, nearest mean error
  was `6.378549 m` and selected mean error was `6.742113 m`.
- Against the oracle object prior, nearest mean error was `5.049185 m` and
  selected mean error was `5.398587 m`.
- Oracle TargetNav query remained SR `0/4`.

This is useful evidence, not a failed direction. It shows that storing the
robot pose at the first detector-positive observation is too weak when the
exploration policy is mostly rotating or detecting from far away. The next
method step should move/servo toward a detector-confirmed viewpoint before
committing memory, then store that reached pose as the memory anchor.

## Research Relevance

This is the first non-privileged bridge from the privileged detector-positive
viewpoint diagnostic to an online memory method. It tests the hypothesis the
user identified: store where the robot was when evidence was observed, then use
vision/SLAM/local control to reacquire nearby, instead of trusting one
single-frame depth projection as the memory target.

## Open Questions

- Should future memory anchors store heading/yaw explicitly for faster
  reacquisition?
- Should repeated detector-positive robot poses be clustered into a compact
  viewpoint belief rather than exported as independent anchors?
- What local servo criterion should decide success after returning to the
  remembered viewpoint?

## Detector-Approach Commit Extension

The first `robot_viewpoint` smoke showed that committing memory at the first
raw detector-positive frame is too early. To bridge toward the user's proposed
camera/SLAM approach behavior, add a discovery-time commit policy:

- `anchor_commit_policy=immediate`: current behavior, commit the anchor at the
  same observation that produced the detection.
- `anchor_commit_policy=detector_approach`: when the detector first sees the
  target, use detector bbox/depth evidence for local action selection and defer
  committing the memory until after a bounded detector-guided approach step.

This extension still stores a `robot_viewpoint` anchor, not a projected object
center. The bbox/depth evidence is only used as local control evidence to move
the robot toward a better viewpoint before writing the memory.

Initial scope:

1. Support `detector_approach` only with `anchor_mode=robot_viewpoint`.
2. Use the existing target evidence helpers from the official query policy for
   bbox center/depth reasoning.
3. Defer the first positive observation, execute one or more detector-guided
   local actions, then commit the next detector-positive robot pose.
4. Record `anchor_commit_policy` and the number of deferred approach actions in
   summary/CSV metadata.

This is deliberately a small, testable bridge. Later versions should replace
the hand-coded detector action with a learned local approach policy trained
from traces, but this slice gives the memory system a non-privileged way to
commit a better viewpoint than "where the robot first happened to see it."
