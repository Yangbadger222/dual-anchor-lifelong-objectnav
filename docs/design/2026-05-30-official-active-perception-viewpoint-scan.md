# Design Doc: Official Active-Perception Viewpoint Scan Phase

Date: 2026-05-30
Owner: Codex
Status: Implemented; controller-alignment diagnostic still negative

## Goal

Make a selected active-perception viewpoint actionable by adding a bounded
scan/orient phase. When the policy has reached a selected free viewpoint, it
should turn the sensor toward the remembered anchor and briefly scan for
detector evidence instead of immediately reselecting another waypoint or moving
through the viewpoint.

The 2026-05-31 controller-alignment update extends this from a reached-viewpoint
primitive into a short option state machine: once an active-perception viewpoint
is chosen, keep pursuing that viewpoint across successive policy calls, and if
the final approach corridor is blocked, perform one bounded local scan before
abandoning the memory option.

## Non-Goals

- Do not use target pose, oracle semantics, route followers, or prior maps.
- Do not tune a large rule set to the four-episode smoke.
- Do not claim benchmark improvement unless official Habitat metrics support
  it.
- Do not add language/GPT control in this slice.

## Background

The path-aware viewpoint selector made active-perception candidates physically
reachable but regressed the small YOLO smoke. The trace showed finite
`path_distance_m` and positive expected evidence, yet target-match calls fell.
The missing execution primitive is clear: selecting a viewpoint is only useful
if the robot then aims or scans its camera from that viewpoint to acquire
detector evidence. Since detector-first logic already runs at the start of each
step, the scan phase can be implemented as bounded turn actions that create new
views for the next observation.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`
- focused official ObjectNav evaluator tests
- docs/devlog/handoff and a smoke report if Linux execution is run

The scan phase stays inside the official discrete action loop and uses only
memory anchors, online occupancy, GPS, compass, depth, and detector outputs.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Selected viewpoint candidate | JSON-safe selector dict | Must include `viewpoint_cell`, `path_distance_m`, and anchor score fields. |
| Input | Memory anchor | `OfficialMemoryAnchor` | Provides episode-relative scan bearing. |
| Input | Observation | Habitat `gps`, `compass`, optional `depth` | Provides current pose and heading. |
| Output | Action | `turn_left` or `turn_right` during orient/scan | Detector is evaluated on the following observation. |
| Output | Debug | `memory_prior` fields | Records scan phase, anchor bearing error, and remaining scan steps. |

## Data Flow

1. Run detector-first handling exactly as before.
2. Select a reachable active-perception viewpoint.
3. If `path_distance_m` is within one map cell, treat the viewpoint as reached.
4. Compute the bearing from current pose to the remembered anchor.
5. If the camera is not facing the anchor within memory bearing tolerance, turn
   toward the anchor and record `active_perception_phase=orient_anchor`.
6. If already facing the anchor and this viewpoint has not exhausted its scan,
   perform a bounded turn sweep and record `active_perception_phase=scan_anchor`.
7. Once the bounded scan is exhausted for that viewpoint, allow normal
   viewpoint navigation/fallback again so the policy does not spin forever.
8. If a viewpoint was selected on the previous step and has not yet completed
   its scan, prefer that same viewpoint on the next step when it remains in the
   candidate set. Record `active_perception_commitment=continued`.
9. If the committed/selected viewpoint is aligned but center depth blocks the
   final forward motion, run the same bounded scan once for that blocked
   viewpoint and record `active_perception_phase=blocked_scan_anchor`.
10. After the blocked scan is exhausted, clear the active-perception target and
    fall back to occupancy exploration unless detector-first handling has found
    usable target evidence.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Viewpoint never reached | `path_distance_m` remains above threshold | Continue normal viewpoint navigation. |
| Viewpoint choice oscillates every step | Trace alternates selected `viewpoint_cell` while still navigating | Keep a short-lived committed viewpoint until scan completion or fallback. |
| Scan loops forever | Trace repeats same scan decision after budget | Mark scanned viewpoint and bound scan steps. |
| Corridor blocks final approach but viewpoint is near useful evidence | `center_depth` blocked after selecting active-perception target | Run one bounded local scan before fallback. |
| Anchor bearing is wrong due memory drift | Detector trace remains negative | Fall back to active-perception/occupancy after bounded scan. |
| Scan reduces exploration | Official metrics regress | Record as negative ablation; keep only if useful as interface. |

## Verification Plan

1. RED unit/policy test: with current cell equal to the selected viewpoint and
   anchor to the right, the active-perception fallback returns `turn_right`
   with `active_perception_phase=orient_anchor` instead of moving forward.
2. GREEN implementation with bounded scan state fields in `OfficialPolicyState`.
3. Focused active-perception tests and full official evaluator tests.
4. Local focused gate, compileall, and `git diff --check`.
5. Sync to Linux, rerun the focused gate, and run the same four-episode YOLO
   smoke if online action traces change.

## Implementation Notes

- Added bounded scan bookkeeping to `OfficialPolicyState`.
- Added short-lived active-perception target commitment:
  `active_perception_target_viewpoint_cell`.
- Added blocked-target scan bookkeeping:
  `active_perception_blocked_scan_viewpoint_cell`.
- Added reached-viewpoint behavior inside
  `_select_memory_active_perception_frontier_fallback`: if a selected
  `viewpoint_cell` is within one occupancy cell, orient toward the memory
  anchor before moving through the viewpoint.
- Added blocked-target behavior inside
  `_select_memory_active_perception_frontier_fallback`: if a selected
  active-perception target is aligned but the center depth corridor is blocked,
  scan locally once before clearing the target and falling back.
- Added debug fields for `active_perception_phase`, anchor bearing/error, and
  remaining scan steps.
- Added debug field `active_perception_commitment` to distinguish new viewpoint
  selections from continued option execution.
- Local focused gate passed with `97` tests, plus compileall and
  `git diff --check`.
- Linux focused gate passed with `97` tests, plus compileall and
  `git diff --check`.
- The four-episode YOLO smoke remained negative: official success `0/4`, SPL
  `0.0`, SoftSPL `0.02518699682786324`, and target-match detector calls `4`.

The scan phase is mechanically useful but not yet a performance improvement.
It recovered part of the path-aware viewpoint regression, but it reduced target
matches relative to the rotation-aware frontier-cell smoke. This suggests the
next publishable direction should be learned or data-driven view-value
estimation and memory coverage, not more hand-authored scan rules.

2026-05-31 controller-alignment follow-up:

- Sticky viewpoint commitment alone did not improve the matched no-rank ranker
  smoke: success `0/4`, SPL `0.0`, SoftSPL `0.0009902771347611306`, and `0`
  target-match calls.
- Adding the blocked-target local scan recovered some evidence for the no-rank
  ranker smoke: success `0/4`, SPL `0.0`, SoftSPL `0.02518699682786324`, and
  `4` target-match calls.
- The matched no-ranker hand-score run with the same controller produced the
  same official metrics and target evidence: success `0/4`, SPL `0.0`,
  SoftSPL `0.02518699682786324`, and `4` target-match calls.
- This means the recovered evidence is a controller-alignment effect, not an
  online learned-ranker improvement.

## Research Relevance

This frames active perception as an option: choose a reachable sensing pose,
orient toward the memory hypothesis, and collect detector evidence. That is a
cleaner robotics contribution than one-step frontier scoring and is compatible
with future learned view-value models, ROS 2/Nav2 waypoint execution, and
language-level commands such as "look for the chair you saw before."

## Open Questions

- Whether the scan sweep should later be learned from detector-recall data
  rather than a bounded deterministic turn primitive.
- Whether the next learned selector should label candidate options by online
  downstream utility under this exact option state machine instead of by
  teleport/restore visibility.
