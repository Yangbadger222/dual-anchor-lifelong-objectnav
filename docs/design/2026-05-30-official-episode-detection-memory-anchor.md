# Design Doc: Official Episode Detection Memory Anchor

Date: 2026-05-30
Owner: Codex
Status: Implemented first slice

## Goal

Create a non-oracle bridge from official Habitat observations plus detector
outputs to `episode_start_relative` memory-prior anchors that
`memory_guided_frontier` can consume.

This is the first "robot saw an object, now write memory" primitive inside the
official observation frame.

## Non-Goals

- Do not run Grounding DINO, YOLO, or GPT in this slice.
- Do not use Habitat target pose, semantic oracle masks, pathfinder, or route
  follower data.
- Do not convert lifecycle `habitat_world` DB anchors into actionable priors.
- Do not claim benchmark performance from synthetic detector boxes.

## Background

The official policy now has the correct episode-local frame:

- internal `x_m` means right/lateral;
- internal `z_m` means forward;
- Habitat 2D `gps` is `[forward, right]` and is converted at the observation
  boundary;
- raw Habitat compass is negated so positive internal heading means right.

The missing piece is an observation-only memory writer. If a detector reports a
box or mask for a target object in the current RGB-D observation, the system
should estimate the object's episode-relative anchor using:

- current official `gps`;
- current official `compass`;
- official `depth`;
- camera horizontal field of view;
- detector bounding box center and depth patch.

## System Boundary

Add a focused module beside the official evaluator:

- `objectnav_core.evaluation.official_episode_memory`

The module owns detector-box-to-anchor projection and memory-prior payload
serialization. It depends on official observation dictionaries and the
`OfficialMemoryAnchor` schema. It does not own detector inference, policy
selection, database persistence, or Habitat environment stepping.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Observation | Mapping | Uses `depth`, `gps`, and `compass`. |
| Input | Detection bbox | `(x1, y1, x2, y2)` | Pixel coordinates, x2/y2 exclusive. |
| Input | Category/confidence/source | Scalars | Passed through to memory prior. |
| Output | Anchor | `OfficialMemoryAnchor` | `coordinate_frame="episode_start_relative"`. |
| Output | Payload | JSON-compatible dict | `{"anchors": [...]}` round-trips through the official parser. |

## Interfaces

```python
estimate_episode_detection_anchor(
    observation,
    bbox_xyxy=(x1, y1, x2, y2),
    object_category="chair",
    confidence=0.82,
    source="grounding_dino:frame_12",
    scene_id="optional scene id",
)
```

For a centered detection two meters ahead while the robot is at
`gps=[1.0, 0.0]`, the output anchor should be approximately
`x_m=0.0`, `z_m=3.0`: one meter current forward position plus two meters
detected depth.

## Data Flow

1. Convert official depth to a 2D array.
2. Validate the bbox and clip it to image bounds.
3. Use the median positive finite depth inside the box.
4. Convert normalized Habitat depth to meters when needed.
5. Convert bbox center to a horizontal bearing using camera HFOV.
6. Read current position and heading in the corrected internal episode frame.
7. Project the detected object into episode-relative `x,z`.
8. Return an `OfficialMemoryAnchor` with
   `coordinate_frame="episode_start_relative"`.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Empty/invalid bbox | bbox validation | return `None`. |
| Missing or invalid depth | no finite positive patch depth | return `None`. |
| Normalized depth treated as meters | finite depth max <= `1.0` | convert with configured min/max depth. |
| Detector label is wrong | external detector/evaluator evidence | preserve confidence/source for later gating. |
| Stale memory in later episode | official policy failure and memory debug | feed into validity learning rather than hiding it. |

## Verification Plan

1. Unit-test centered bbox projection with official GPS ordering.
2. Unit-test compass sign by projecting a centered detection after a right
   turn.
3. Unit-test normalized depth conversion.
4. Unit-test invalid bbox/depth returns `None`.
5. Unit-test payload round-trip through `load_official_memory_prior_from_payload`.
6. Run local focused tests and the full test suite.
7. Sync to Linux and run focused tests in conda env `habitat`.

Implemented first-slice verification:

- RED test run failed with missing module
  `objectnav_core.evaluation.official_episode_memory`.
- GREEN focused projection tests: `6` passed locally.
- Local focused official-memory set: `39` passed.
- Local full test suite: `330` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory set in conda env `habitat`: `39` passed.
- Linux `git diff --check` returned cleanly.

## Research Relevance

This is a small but important bridge from perception to memory under official
ObjectNav constraints. It lets future experiments replace synthetic priors with
detector-produced episode-relative memories without using oracle target poses.
That is necessary before comparing memory-conditioned search against
target-agnostic exploration in a way that could support a serious robotics
paper.
