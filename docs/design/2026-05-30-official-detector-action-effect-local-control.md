# Design Doc: Official Detector Action-Effect Local Control

Date: 2026-05-30
Owner: Codex
Status: Implemented; diagnostic YOLO smoke completed

## Goal

Add a new official ObjectNav policy variant that uses online detector
action-effect evidence to avoid the local visual-servo loop seen in
`memory_belief_frontier`. When a detector-centering turn immediately loses a
target that was visible at the image edge, the policy should remember that
failed action effect and choose a bounded edge-tracking approach action on the
next matching view instead of repeating the same loss/reacquire cycle.

## Non-Goals

- Do not use target pose, semantic oracle masks, Habitat pathfinder shortcuts,
  route followers, teleportation, or success labels for action selection.
- Do not change official Habitat metric handling.
- Do not claim benchmark improvement unless official Habitat success/SPL move.
- Do not replace the long-term memory system or discovery pipeline in this
  slice.
- Do not tune around one category or scene. The controller must be expressed as
  action-effect evidence that can later become a learned local value model.

## Background

The official YOLO diagnostic sequence established three negative results:

1. `memory_belief_frontier` increased target-match evidence but did not solve
   the episode.
2. The adaptive one-step servo turned fallback reversals into
   `reacquire_detector_target`, but official metrics and action counts stayed
   unchanged.
3. Inverting the detector-centering sign only mirrored the turn order. The
   target remained visible at heading about `-2.094`, and both neighboring
   30-degree turns lost it.

This suggests the local controller is hitting a discrete-action/partial-FOV
failure: the target can be visible near the edge, but a 30-degree turn jumps
past the useful view. The next policy should learn from that failed action
effect online. This is closer to a publishable robot behavior than another
static sign or threshold: the robot treats its own recent action outcomes as
evidence about which local action preserves target information.

Recent ObjectNav and embodied-memory systems generally support persistent
semantic/topological memory and online grounding, but this repo's
benchmark-facing path must stay inside official Habitat actions and metrics.
This design is a bridge: memory proposes the search neighborhood, detector
evidence controls short-horizon local action choice, and official metrics
judge the result.

## System Boundary

Modify the official ObjectNav evaluator:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`
- `objectnav_core.cli.run_habitat_official_objectnav_eval`
- focused official evaluator/CLI tests

Add a policy variant, tentatively:

- `memory_evidence_frontier`

It should reuse:

- memory prior loading and scene/category matching;
- occupancy-frontier and memory-belief frontier scoring;
- detector target evidence fields;
- policy trace and detector trace artifacts;
- official Habitat discrete action strings.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Memory anchors | `OfficialMemoryAnchor` records | Same boundary as existing memory policies. |
| Input | Detector match/no-match | RGB detector result | Optional injected detector, no oracle. |
| Input | Bbox/depth evidence | existing detector evidence payload | Center offset, area fraction, median depth. |
| Input | Last local action effect | per-episode policy state | Records whether a centering turn immediately lost target evidence. |
| Output | Action | Habitat discrete action | `turn_left`, `turn_right`, `move_forward`, `stop`. |
| Output | Debug | `policy_debug.memory_prior` and `policy_trace.json` | Records action-effect state, suppressed centering action, and decision. |
| Output | Manifest | `protocol_manifest.json` | Records `memory_evidence_frontier` policy kind. |

## Interfaces

- `policy="memory_evidence_frontier"`
- Existing `target_detector_adapter` and `target_detector_min_confidence`
- Existing `detector_center_direction_sign`
- Existing `write_detector_trace` and `write_policy_trace`

No new detector thresholds should be exposed in this first slice. The first
implementation should be an auditable policy variant, not a hidden default
change to `memory_belief_frontier`.

## Data Flow

1. At each step, run the target detector when RGB is available.
2. If the target is visible and range-confirmed, emit STOP as before.
3. If the target is visible and centered enough but not close enough, approach
   through the existing forward-depth gate.
4. If the target is visible but off-center, compute the nominal centering turn.
5. If that same nominal turn has recently caused immediate target loss for the
   same offset sign, suppress the turn and choose a bounded edge-tracking
   approach action when the forward corridor is clear.
6. If the target is lost immediately after a detector-centering turn, record a
   failed action effect and emit one reacquisition turn back toward the last
   known target view.
7. If no detector-local-control action is active, fall back to memory-belief
   frontier scoring.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Forward edge-tracking walks past the target | Policy trace shows repeated approach with worsening depth/area | Bound approach by current depth and stop/return to frontier if target disappears outside the immediate-loss window. |
| False-positive detector match triggers edge tracking | Official metrics stay false; detector trace shows weak/unstable label | Require target-category match and reuse existing confidence gate; do not claim improvement from small smokes. |
| Action-effect evidence overfits one offset | Trace shows suppressed turns for unrelated views | Key failed effects by action and offset sign, reset per episode. |
| No detector target appears | Same behavior as memory-belief frontier | Fall back to memory-belief frontier scoring. |
| Edge-tracking close target remains off-center | Depth/area improve but STOP gate rejects | Only consider an edge-range STOP after a failed centering action and close depth/large area evidence. |

## Verification Plan

1. RED registration test: `memory_evidence_frontier` appears in supported
   official policies and manifest policy kind.
2. RED action-effect test: target visible at right edge, centering turn loses
   target, reacquisition restores the same edge target, then the policy
   suppresses the failed centering turn and emits `move_forward` when clear.
3. RED debug test: policy trace records the failed centering action, offset
   sign, and `decision="approach_detector_target_after_center_loss"`.
4. Preserve existing `memory_belief_frontier` adaptive-servo behavior and
   sign-ablation tests.
5. Run focused local and Linux official-memory test sets.
6. Run the same four-episode YOLO diagnostic with
   `memory_evidence_frontier` and compare:
   - official success/SPL/SoftSPL;
   - target-match detections;
   - `center_detector_target`, `reacquire_detector_target`,
     `approach_detector_target_after_center_loss`, and fallback counts.

## Verification Result

Completed on 2026-05-30.

- RED registration tests failed because `memory_evidence_frontier` was not a
  supported official policy or CLI choice.
- RED action-effect test failed because the delegated
  `memory_belief_frontier` path repeated centering after reacquisition instead
  of suppressing the failed turn.
- GREEN tests passed after adding the policy variant, per-episode failed
  detector centering effects, and the edge-tracking approach decision.
- Local official evaluator tests passed: `44` tests.
- Local official CLI tests passed: `6` tests.
- Local focused official-memory/exporter set passed: `69` tests.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set passed in conda env `habitat`:
  `69` tests.
- Linux `compileall` and `git diff --check` returned cleanly.

Diagnostic YOLO query smoke:

- Artifact:
  `runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.
- Official success stayed `0/4`; SPL stayed `0.0`.
- SoftSPL improved from `0.0009902771347611306` to
  `0.02518699682786324`, and mean distance-to-goal improved from
  `5.880594372749329` to `5.697803378105164`.
- The target episode detector loop collapsed from `23`
  `center_detector_target` plus `22` `reacquire_detector_target` decisions to
  `1` plus `1`, followed by `3`
  `approach_detector_target_after_center_loss` decisions.
- Target-match detections dropped from `23` to `4` because the policy left the
  repeated target-visible heading instead of oscillating there.
- After three edge-tracking forward steps, target evidence disappeared and the
  policy fell back to memory-belief frontier turns. This is partial positive
  evidence for action-effect control, but not an official ObjectNav success.

## Research Relevance

This moves the system from static hand-coded centering toward an online
action-effect model: the robot remembers what its own last local action did to
target evidence and changes short-horizon control accordingly. That is a small
but real step toward a learned visual-servo value model trained from
`policy_trace.json` and `detector_trace.json`, while preserving the official
Habitat benchmark boundary.

## Open Questions

- Whether edge-tracking approach improves official success or only changes the
  oscillation mode.
- Whether the failed-action memory should become a short-horizon action scorer
  over `turn_left`, `turn_right`, and `move_forward`.
- Whether this should later replace `memory_belief_frontier` or remain a
  separate ablation policy.
