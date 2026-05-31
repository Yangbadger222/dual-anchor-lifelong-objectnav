# Design Doc: Official Policy Step Trace

Date: 2026-05-30
Owner: Codex
Status: Implemented; diagnostic YOLO smoke completed

## Goal

Add a diagnostic `policy_trace.json` artifact for official Habitat ObjectNav
query runs. The trace should record each selected action with the policy
decision/debug state that produced it, so detector-guided local control and
memory-belief search failures can be diagnosed step by step.

## Non-Goals

- Do not add benchmark-facing metrics; official SR/SPL/SoftSPL still come only
  from `habitat.Env.get_metrics()`.
- Do not change policy behavior in this slice.
- Do not add image/video dumps or large observation payloads.
- Do not solve the detector local-control oscillation yet.
- Do not expose CLI flags until the artifact proves useful in live diagnostics.

## Background

The detector-guided approach smoke improved target-match detections from `1`
to `23` but official success stayed `0/4`. A post-hoc join between
`detector_trace.json` and final episode actions showed every target match in
episode 2 was paired with `turn_right` and the same right-edge bbox
`[553, 68, 640, 173]`. The current summary only preserves final episode debug,
so it cannot explain the intervening non-match steps or policy switching. This
missing trace is now the blocking diagnostic boundary.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`

Add:

- in-memory policy-step trace collection inside
  `run_official_objectnav_episode_loop`;
- optional `policy_trace.json` writing in
  `run_habitat_official_objectnav_eval`;
- summary counts under `summary["policy_trace"]`.

The trace consumes only existing policy state and official observations. It
does not feed back into action selection.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy state | `OfficialPolicyState` | Current memory/debug/occupancy state after action selection. |
| Input | Action | Habitat discrete action string | The action sent to `env.step`. |
| Input | Observation metadata | official observation | Only pose/depth summary fields, never raw images/depth arrays. |
| Output | `policy_trace.json` | JSON artifact | Diagnostic step records. |
| Output | Summary | `summary["policy_trace"]` | Step count, action counts, decision counts. |

## Interfaces

- `run_habitat_official_objectnav_eval(..., write_policy_trace=True)`
- `run_official_objectnav_episode_loop(..., policy_trace=...)`

Default behavior should write the trace for full official eval calls because
current policy research depends on step-level debugging. A caller may disable
it with `write_policy_trace=False`.

## Data Flow

1. `run_habitat_official_objectnav_eval` creates an empty trace list when
   `write_policy_trace` is enabled.
2. The episode loop selects an action exactly as before.
3. Before calling `env.step(action)`, the loop appends a compact step record:
   - episode index/id, scene id, target category;
   - step index and selected action;
   - current pose from corrected `gps/compass` helpers;
   - `memory_prior` debug snapshot when present;
   - occupancy-frontier counts and selected bearing when present.
4. Budget STOP steps are recorded as `decision="budget_stop"` rather than
   reusing stale debug from the previous step.
5. The full eval writes `policy_trace.json` and summary counts.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Trace grows too large | Artifact size scales with episodes x max steps | Store compact metadata only; no raw observations. |
| Stale debug on budget STOP | Trace final step repeats previous decision | Explicitly override budget-stop decision in trace. |
| Trace is mistaken for benchmark metric | Summary notes and artifact naming | Keep official metrics namespace unchanged. |
| Direct episode-loop callers do not need trace | `policy_trace=None` default | No behavior change for unit-level callers. |

## Verification Plan

1. RED test: full official eval writes `policy_trace.json` and records the
   first detector-guided action decision.
2. RED test: budget STOP is recorded as `budget_stop`, not stale detector
   debug.
3. RED test: `write_policy_trace=False` suppresses the artifact.
4. GREEN implementation: add compact trace recording and summary counts.
5. Run focused official evaluator tests, focused official-memory tests,
   `compileall`, and `git diff --check`.
6. Sync to Linux and rerun focused verification in conda env `habitat`.
7. Rerun the four-episode YOLO diagnostic to inspect step-level decision
   patterns.

## Verification Result

Completed on 2026-05-30.

- RED tests failed because `policy_trace.json` and `write_policy_trace` did
  not exist.
- GREEN tests passed after adding compact per-step trace collection and
  artifact writing.
- Local official evaluator tests passed: `40` tests.
- Local focused official-memory/exporter set passed: `62` tests.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set passed in conda env `habitat`:
  `62` tests.
- Linux `compileall` and `git diff --check` returned cleanly.

Diagnostic YOLO query smoke:

- Artifact:
  `runs/habitat_official_objectnav/memory_belief_frontier_policy_trace_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.
- Official success stayed `0/4`; SPL stayed `0.0`; SoftSPL stayed
  `0.0009902771347611306`.
- `policy_trace.json` recorded `200` steps:
  - `center_detector_target`: `23`;
  - `fallback_occupancy_frontier`: `170`;
  - `turn_toward_memory_belief_frontier`: `3`;
  - `budget_stop`: `4`.
- Episode 2 showed the concrete oscillation: after initial memory-belief
  turns, even steps `4..48` were `center_detector_target`/`turn_right` with the
  same right-edge target bbox, while odd steps `5..47` were
  `fallback_occupancy_frontier`/`turn_left` with
  `fallback_reason="blocked_memory_belief_frontier_corridor"`.

This proves the next bottleneck is not "detector never sees the target." The
detector sees it repeatedly, but single-frame detector control loses ownership
on the next frame and the fallback policy reverses the centering action.

## Research Relevance

The paper-facing system needs a principled memory/search/approach loop, not
more blind threshold tweaks. This trace supplies the evidence needed to design
that loop: when memory belief chooses frontiers, when detector control takes
over, when it loses target evidence, and which action sequence causes failure.

## Open Questions

- Whether the trace should later include per-step detector match summaries
  directly, instead of requiring a join with `detector_trace.json`.
- Whether live-policy diagnostics should eventually export lightweight videos
  or thumbnails for qualitative paper figures.
