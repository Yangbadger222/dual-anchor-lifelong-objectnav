# Design Doc: Official Confirmed Detector-Approach Memory Write

Date: 2026-05-31
Owner: Codex
Status: Implemented; diagnostic smoke negative

## Goal

Make official Habitat memory discovery target-reactive: when the detector sees
the episode target category, the robot should locally approach and center the
target before writing memory. The memory prior should store a confirmed
detector-positive robot viewpoint, not the first weak glimpse seen during
frontier exploration.

## Non-Goals

- Do not claim official benchmark improvement from this policy until it is
  evaluated against the targetnav-equated comparison scaffold.
- Do not use Habitat target poses, semantic masks, object centers, or official
  `view_points` at write time.
- Do not replace terminal TargetNav or tune the query controller in this slice.
- Do not add language/GPT control here.

## Background

The targetnav-equated comparison showed that current memory can underperform a
no-memory TargetNav row even when terminal navigation is held fixed. The
view-quality memory selector then failed: larger or more centered passive
detections still often came from poor exploration poses. The correct behavior
for a robot is not "see target, keep wandering, write whatever pose happened to
see it"; it is "see target, approach/center/confirm, then write the viewpoint
that should be useful next time."

Existing `detector_approach` delayed commit can execute detector-guided local
actions, but it still commits after a fixed budget even when the target was not
range-confirmed. The new policy makes confirmation explicit.

## System Boundary

Extend official memory discovery only:

- `objectnav_core.evaluation.habitat_official_memory_discovery`
- `objectnav_core.cli.run_habitat_official_memory_discovery`
- focused discovery and CLI tests
- devlog, handoff, and experiment report after verification/smoke

Query-time ObjectNav policies and the memory-prior JSON schema remain
compatible. The policy writes ordinary `robot_viewpoint` anchors.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | RGB-D/GPS/compass observation | Habitat observation | Same official sensor stream as existing discovery. |
| Input | Detector match | adapter detection | Must match the target category and confidence threshold. |
| Input | Commit policy | CLI/config string | New value: `confirmed_detector_approach`. |
| Input | Approach budget | integer steps | Reuses `detector_approach_max_steps`. |
| Output | Memory anchor | official memory prior JSON | Written only from a confirmed robot viewpoint. |
| Output | Summary counts | JSON | Records deferred, confirmed, and unconfirmed approach outcomes. |
| Output | Detection CSV | CSV | Records confirmed anchor evidence for selected writes. |

## Interfaces

CLI:

```bash
python -m objectnav_core.cli.run_habitat_official_memory_discovery \
  --output runs/.../grounding_dino_confirmed_detector_approach_prior \
  --detector grounding_dino \
  --anchor-mode robot_viewpoint \
  --anchor-commit-policy confirmed_detector_approach \
  --detector-approach-max-steps 6
```

Programmatic API:

```python
run_habitat_official_memory_discovery(
    output_dir,
    detector_adapter=detector,
    anchor_mode="robot_viewpoint",
    anchor_commit_policy="confirmed_detector_approach",
    detector_approach_max_steps=6,
)
```

## Data Flow

1. Run the normal exploration policy while no target-category detector match is
   visible.
2. When a target match is visible and `anchor_mode=robot_viewpoint`, enter a
   detector-guided local approach loop.
3. Use the existing detector local controller to choose:
   - turn left/right if the bbox is not centered;
   - move forward if centered and the depth corridor is clear;
   - "stop" when the detector evidence is centered and range-confirmed.
4. For `confirmed_detector_approach`, do not execute STOP during discovery.
   Instead, commit the current robot viewpoint as memory and resume exploration.
5. If the approach budget expires before range confirmation, do not write a
   memory anchor for that weak glimpse. Count it as unconfirmed and resume
   exploration.
6. Keep per-episode anchor selection (`confidence` or `view_quality`) after
   confirmed candidates are collected.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Detector sees object only from far away | approach budget expires; unconfirmed count rises | Do not write a bad memory; report lower coverage. |
| Local corridor is blocked | controller returns no approach action before confirmation | Mark unconfirmed and resume frontier exploration. |
| Detector false positive becomes range-confirmed | later query still fails | Keep detector confidence/evidence in CSV; compare against oracle and detector-positive viewpoint diagnostics. |
| Too strict confirmation drops all memories | exported anchor count and coverage collapse | Sweep budget/thresholds as ablations, but keep the strict policy as the high-precision baseline. |
| Policy accidentally stores first glimpse | tests inspect actions, source step, and anchor pose | Regression tests enforce deferred commit until confirmation. |

## Verification Plan

1. RED test: `confirmed_detector_approach` takes detector-guided turn/move
   actions and commits only when the detector controller would range-confirm.
2. RED test: if the approach budget expires before confirmation, no memory
   anchor is written and the episode records an unconfirmed target glimpse.
3. RED CLI test: `--anchor-commit-policy confirmed_detector_approach` is
   accepted and forwarded.
4. Run focused local tests for discovery, discovery CLI, and packaging.
5. Run `compileall`, `git diff --check`, and touched-file whitespace checks.
6. Sync to Linux and run the same focused tests in conda env `habitat`.
7. Run a four-episode Grounding-DINO discovery/query diagnostic with
   `anchor_mode=robot_viewpoint`, `anchor_commit_policy=confirmed_detector_approach`,
   and fixed `targetnav_backend=oracle_follower`.

## Implementation Result

Implemented `anchor_commit_policy=confirmed_detector_approach`.

- The previous `immediate` and `detector_approach` paths remain available.
- The new policy is valid only with `anchor_mode=robot_viewpoint`.
- When a target-category detection appears, discovery uses the existing local
  detector controller to turn toward or move toward the target.
- If the detector controller would issue `stop`, discovery writes the current
  robot viewpoint as a confirmed memory instead of stopping the Habitat episode.
- If the approach budget expires or the detector controller cannot produce a
  valid local action before range confirmation, discovery records an
  unconfirmed target attempt and writes no anchor for that weak glimpse.
- Summary JSON now records `detector_approach_confirmed_count` and
  `detector_approach_unconfirmed_count`.

Focused local and Linux tests passed for memory discovery, discovery CLI, and
ROS packaging (`20 passed` on both machines). Local and Linux `compileall`
checks over the touched files were clean.

Four-episode Grounding-DINO diagnostics:

| Write policy | Approach budget | Exported anchors | Confirmed | Deferred actions | Unconfirmed attempts | Query SR |
|---|---:|---:|---:|---:|---:|---:|
| `confirmed_detector_approach` | `8` | `0` | `0` | `46` | `60` | not run; empty prior |
| `detector_approach` | `8` | `2` | `0` | `46` | `0` | `0/4` |

The strict policy proves the robot is not merely wandering after target
detections: it attempted detector-guided local control 46 times. It also proves
the current local approach/confirmation loop is not strong enough to produce
range-confirmed memory writes in this DINO smoke.

The non-strict long-budget comparison exported two anchors, but they remained
poor:

- vs detector-positive viewpoint references: selected mean error `6.262038 m`,
  good anchors `0`, coverage `2/4`;
- vs oracle object-anchor references: selected mean error `5.752019 m`, good
  anchors `0`, coverage `2/4`;
- oracle-backend query: SR `0/4`, SPL `0.0`, SoftSPL
  `0.003394134213343364`, mean distance-to-goal `5.8624347448349`.

The selected non-strict anchors were still near the episode origin:

- toilet episode `6`: `(x=0.0, z=-0.0)`;
- tv episode `0`: `(x=0.033494, z=-0.125)`.

Interpretation: the correct write policy should indeed be target-reactive, as
it would be on a real robot with SLAM/Nav2, but the current simulator local
servo cannot yet convert weak detections into confirmed useful memory
viewpoints. The next research step should improve the target-tracking approach
option itself, add richer approach-attempt traces, or train a local servo from
successful detector/evidence-gain rollouts.

## Research Relevance

This is a stronger lifelong-memory write boundary. It separates exploration
coverage from memory quality and gives the paper a defensible mechanism: memory
is written at confirmed useful viewpoints produced by the robot's own sensor
stream and local control, not by a prior map or an oracle object pose. Negative
results remain useful because they quantify whether the bottleneck is target
coverage, local approach, detector reliability, or query-time navigation.

## Open Questions

- Should confirmation require a minimum number of consecutive target-visible
  frames before writing?
- Should unconfirmed glimpses be kept as low-trust memories for a separate
  recall mode, or excluded entirely from the main memory prior?
- Should the approach budget scale with detected depth/box area rather than be
  a fixed step cap?
