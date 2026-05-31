# Design Doc: Official Pathfinder Suffix Diagnostic

Date: 2026-05-31
Owner: Codex
Status: Implemented; diagnostic smoke complete

## Goal

Add a diagnostic official Habitat ObjectNav policy that keeps the current
memory-guided active-perception exploration stack, but switches to a Habitat
pathfinder follower after the target detector has seen the queried object. The
goal is to isolate whether exploration plus memory can create a recoverable
target sighting while temporarily bypassing the weak hand-written terminal
approach controller.

## Non-Goals

- Do not treat this policy as a benchmark-valid method.
- Do not use pathfinder, target goal positions, or shortest paths in the final
  online robot policy.
- Do not replace the learned candidate-ranking work.
- Do not claim paper performance from this oracle suffix.
- Do not add persistent `habitat_world` memory anchors.

## Background

The fixed sticky plus blocked-scan active-perception controller produces target
detector matches, but the matched online smokes still report `0/4` success and
`0.0` SPL. The option-utility label slice also found zero official progress and
zero STOP-success support on the tiny enriched YOLO artifact, even when detector
gain and hidden-to-visible labels were positive.

This suggests the terminal approach/STOP behavior is a likely bottleneck. A
temporary pathfinder suffix can answer a narrower question: once memory-guided
exploration reacquires the target, could a competent local navigation suffix
convert that sighting into official success?

## System Boundary

Owned by this slice:

- Add a new diagnostic policy name in the official ObjectNav evaluator.
- Add a small pathfinder-suffix controller interface that can be faked in local
  tests and backed by Habitat's installed follower in Linux Habitat runs.
- Record explicit debug fields showing suffix activation, selected goal, and
  follower actions.
- Add CLI configuration for the suffix goal radius.
- Add docs, devlog, handoff, and a smoke experiment report.

Dependencies:

- Existing detector adapter and memory-active-perception policy.
- Habitat official metrics via `env.get_metrics()`.
- Habitat-Lab `ShortestPathFollower` or Habitat-Sim greedy follower only inside
  the diagnostic suffix.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy | CLI string | `memory_active_perception_frontier_pathfinder_suffix` |
| Input | Target detector match | Runtime observation | Suffix activates only after a target-category detection meets confidence threshold. |
| Input | Episode goal/viewpoint positions | Habitat episode metadata | Diagnostic oracle goal source after detection. |
| Input | Goal radius | Meters | Default `1.0`; follower stops within this radius. |
| Output | Official metrics | JSON summary | Still read only from `env.get_metrics()`. |
| Output | Policy trace/debug | JSON | Records suffix activation and follower action decisions. |

## Interfaces

New policy:

```bash
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --policy memory_active_perception_frontier_pathfinder_suffix \
  --pathfinder-suffix-goal-radius-m 1.0
```

Internal interfaces:

- `OfficialPolicyState.pathfinder_suffix_controller`
- `OfficialPolicyState.pathfinder_suffix_goal_position`
- `_select_memory_active_perception_frontier_pathfinder_suffix_action(...)`
- `_episode_goal_positions(...)`
- `_follower_action_name(...)`

## Data Flow

1. Run the existing memory-active-perception frontier policy until a target
   detector match is observed.
2. On the first detector match, select a Habitat episode goal/viewpoint position
   and mark the pathfinder suffix active.
3. Each subsequent policy step asks the suffix follower for the next action
   toward the selected goal.
4. When the follower returns `stop` or `None`, emit `stop`.
5. Record all official metrics using Habitat's normal ObjectNav measures.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No target detector match | suffix debug absent | Existing active-perception behavior continues. |
| No episode goal/viewpoint position | debug reason `no_pathfinder_goal` | Fall back to existing detector/local action behavior. |
| Habitat follower unavailable | debug reason `pathfinder_suffix_unavailable` | Fall back to existing detector/local action behavior. |
| Follower emits unsupported action id | debug reason `unsupported_pathfinder_action` | Emit `stop` only when safe; otherwise fall back. |
| Success improves only with oracle goal | experiment report labels result diagnostic only | Do not compare as final method or SOTA. |

## Verification Plan

1. Local RED/GREEN tests:
   - policy is registered and marked as diagnostic/oracle in the manifest;
   - suffix activates only after a target detector match;
   - fake suffix controller actions are executed before the old local detector
     approach behavior;
   - follower action ids map to ObjectNav action names;
   - missing suffix goal falls back to existing detector behavior.
2. Local focused pytest for official ObjectNav eval tests.
3. `compileall` on touched Python files.
4. CLI help confirms `--pathfinder-suffix-goal-radius-m`.
5. Linux Habitat smoke on the same four-episode YOLO trace configuration.
6. Record success/SPL/SoftSPL, target-match calls, suffix activation counts, and
   whether any success is nonzero.

## Research Relevance

This is a failure-decomposition diagnostic, not the final algorithm. A nonzero
success under the suffix would show that exploration plus memory can reach a
recoverable target sighting and that the current bottleneck is terminal
navigation/STOP. That makes the next paper-relevant step clearer: replace the
oracle suffix with detector-depth PointNav/VLFM-style local navigation.

## Implementation Notes

The evaluator now registers
`memory_active_perception_frontier_pathfinder_suffix` as an oracle diagnostic
policy. It reuses the current memory-active-perception detector check and, after
the first target match, switches to an injectable pathfinder suffix controller.
Local tests use a fake controller; Habitat runs build a lazy
`ShortestPathFollower` from the installed Habitat-Lab environment.

The first Linux smoke with `--pathfinder-suffix-goal-radius-m 1.0` activated the
suffix but stayed at official success `0/4` because the ObjectNav config uses
`success_distance: 0.1`. The follow-up smoke with radius `0.05` and a `100` step
cap reached `1/4` success. This is the first nonzero official success in the
current diagnostic sequence, but it remains invalid for benchmark claims because
the suffix uses Habitat goal/viewpoint positions after detection.

## Open Questions

- If the oracle suffix still gives `0` success, is the issue detector false
  positives, wrong episode goal selection, or active-perception timing?
- Should the follow-up non-oracle suffix use VLFM's PointNav policy directly or
  a local Habitat-compatible PointNav adapter trained/evaluated in this repo?
