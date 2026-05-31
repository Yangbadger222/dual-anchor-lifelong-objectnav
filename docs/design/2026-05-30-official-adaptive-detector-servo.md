# Design Doc: Official Adaptive Detector Servo

Date: 2026-05-30
Owner: Codex
Status: Implemented; diagnostic YOLO smoke completed

## Goal

Reduce detector-centering oscillation in `memory_belief_frontier` by adding a
small adaptive visual-servo state. If a detector centering turn immediately
loses the target on the next frame, the policy should treat that as negative
action-effect evidence, reverse the centering direction for future detections,
and perform one reacquisition turn instead of handing control to frontier
fallback.

## Non-Goals

- Do not change official Habitat metric handling.
- Do not use semantic oracle masks, target pose, pathfinder, or success labels.
- Do not claim benchmark improvement from this mechanism unless official
  Habitat metrics improve.
- Do not build a learned visual servo in this slice.
- Do not affect `memory_guided_frontier`; this is scoped to
  `memory_belief_frontier`.

## Background

The new `policy_trace.json` artifact showed the target episode oscillating:
even steps saw `tv_monitor` at the right image edge and chose
`center_detector_target`/`turn_right`; odd steps lost the target and fell back
to `fallback_occupancy_frontier`/`turn_left`, returning to the same right-edge
view. This suggests the detector controller needs action-effect memory. The
first direction chosen from bbox sign may be wrong for the live observation
geometry, or too coarse; either way, losing the target immediately is evidence
that the policy should not keep using the same centering direction.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`

Use only:

- current detector match/no-match from official RGB;
- existing detector bbox evidence;
- existing per-episode `OfficialPolicyState`;
- Habitat discrete actions.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Detector match | existing target-match payload | Includes bbox center offset. |
| Input | No-match step | detector returns no target match | Used only if it follows a detector-centering action. |
| State | Center direction sign | `1` or `-1` | Maps bbox offset to turn action. |
| State | Last detector center action | action + step | Detects immediate target loss. |
| Output | Action | Habitat discrete action | `turn_left`, `turn_right`, `move_forward`, `stop`. |
| Output | Debug | `policy_debug.memory_prior` and `policy_trace.json` | Records reacquire/flip decisions. |

## Data Flow

1. On a target detection with off-center bbox, choose a centering turn using the
   current center-direction sign and record the step/action/offset.
2. If the next step has no target match and the previous step was detector
   centering, treat the target as immediately lost.
3. Flip the center-direction sign and emit the opposite turn with
   `decision="reacquire_detector_target"`.
4. The next target detection uses the flipped direction.
5. If no target match occurs outside that immediate loss window, use the
   existing memory-belief/frontier behavior.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Target loss was caused by detector dropout, not wrong turn | Trace shows alternating reacquire without centering | Limit reacquisition to one immediate step. |
| Direction flip helps one target but hurts another | State is per episode | Reset on episode boundary. |
| Servo still oscillates | Policy trace shows repeated flips | Next slice should use evidence accumulation or learned local control. |

## Verification Plan

1. RED test with a sequence detector: match with right-edge bbox, no match,
   then same match again. Expect actions `turn_right`, `turn_left`,
   `turn_left` because the no-match step flips future centering.
2. Assert trace/debug records `reacquire_detector_target` on the no-match step.
3. Preserve existing detector approach/STOP tests.
4. Run focused local and Linux verification.
5. Rerun the four-episode YOLO diagnostic and compare policy-trace oscillation
   counts and official metrics.

## Verification Result

Completed on 2026-05-30.

- RED adaptive-servo test failed because no-match steps after detector
  centering still fell through to fallback.
- GREEN test passed after adding per-episode detector center-direction state,
  one-step reacquisition, and direction flips after immediate target loss.
- Local official evaluator tests passed: `41` tests.
- Local focused official-memory/exporter set passed: `63` tests.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set passed in conda env `habitat`:
  `63` tests.
- Linux `compileall` and `git diff --check` returned cleanly.

Diagnostic YOLO query smoke:

- Artifact:
  `runs/habitat_official_objectnav/memory_belief_frontier_adaptive_servo_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.
- Official success stayed `0/4`; SPL stayed `0.0`; SoftSPL stayed
  `0.0009902771347611306`.
- Policy trace changed `22` odd-step fallback decisions into
  `reacquire_detector_target`, but the episode still alternated:
  `center_detector_target` at heading about `-2.094`, then reacquire in the
  opposite direction, then the next detection at the same heading.

This is negative evidence for a one-step hard flip. It confirms that the
problem is a persistent local-control/partial-observation loop, not just the
absence of a reacquisition action.

## Research Relevance

This is still a diagnostic controller, but it moves away from static
hand-tuned behavior toward online action-effect adaptation. The robot uses
detector evidence to update how it controls its view, which is a necessary
bridge toward a learned memory-conditioned active-search policy.

## Open Questions

- Whether a one-step adaptive flip is enough in Habitat's 30-degree turn
  action space.
- Whether the next version should use a belief over centering directions rather
  than a hard flip.
