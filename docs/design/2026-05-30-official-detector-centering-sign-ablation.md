# Design Doc: Official Detector Centering Sign Ablation

Date: 2026-05-30
Owner: Codex
Status: Implemented; diagnostic YOLO smoke completed

## Goal

Expose the detector bbox-to-turn sign in `memory_belief_frontier` as an
explicit ablation parameter. The default policy keeps the existing convention,
while diagnostic runs can invert the sign to test whether live Habitat
camera/action geometry is responsible for detector-centering oscillation.

## Non-Goals

- Do not silently change the default policy behavior.
- Do not change official Habitat metric handling.
- Do not use target pose, semantic oracle masks, pathfinder shortcuts, or
  success labels.
- Do not claim benchmark improvement from a four-episode smoke.
- Do not add more one-step servo heuristics in this slice.

## Background

The detector-guided approach smoke produced `23` target-match detections but
no official success. Policy tracing showed repeated detector centering followed
by a reversal. The adaptive one-step servo made that reversal explicit as
`reacquire_detector_target`, but official success, SPL, SoftSPL, and action
counts did not improve. One unresolved root-cause hypothesis remains: the
image-center offset sign may be opposite the discrete turn convention in the
live Habitat camera/action loop.

## System Boundary

Modify only the official ObjectNav evaluator and CLI surface:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`
- `objectnav_core.cli.run_habitat_official_objectnav_eval`

The parameter affects only detector local control in
`memory_belief_frontier`. `memory_guided_frontier`, official metrics, memory
prior loading, and detector tracing remain unchanged.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Detector center direction sign | `1` or `-1` | Default `1` preserves existing behavior. |
| Input | Detector bbox center offset | float fraction | Existing target-evidence field. |
| Output | Action | Habitat discrete action | `turn_left` or `turn_right` for off-center target detections. |
| Output | Debug | `policy_debug.memory_prior` and `policy_trace.json` | Records the sign used for each detector-centering action. |
| Output | Manifest | `protocol_manifest.json` | Records the configured sign for reproducibility. |

## Interfaces

- `run_habitat_official_objectnav_eval(..., detector_center_direction_sign=1)`
- `run_official_objectnav_episode_loop(..., detector_center_direction_sign=1)`
- CLI flag: `--detector-center-direction-sign {1,-1}`

## Data Flow

1. The run config validates that the sign is either `1` or `-1`.
2. Each episode initializes `OfficialPolicyState.detector_center_direction_sign`
   from the configured value.
3. Off-center detector target matches call the existing
   `_detector_center_action` helper with that sign.
4. The adaptive servo may still flip the per-episode sign after immediate
   target loss, starting from the configured initial value.
5. The manifest, summary config, and policy debug expose the sign used so runs
   remain auditable.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Invalid sign value | Config validation raises before running | Restrict to `1` and `-1`. |
| Inverted sign worsens behavior | Official metrics and traces regress | Keep default unchanged; document negative result. |
| Inverted sign helps only the tiny smoke | Larger validation fails | Treat the smoke as diagnostic; require broader official runs before claims. |
| Adaptive flip obscures initial-sign effect | Trace shows sign flips after target loss | Record sign per step and compare first target-control steps. |

## Verification Plan

1. RED unit test: configuring sign `-1` makes a positive bbox offset choose
   `turn_left` and records `detector_center_direction_sign=-1`.
2. RED CLI/preflight test: `--detector-center-direction-sign -1` is accepted
   and recorded in `protocol_manifest.json`.
3. Preserve existing default centering behavior and adaptive-servo tests.
4. Run focused local tests, compile checks, and `git diff --check`.
5. Run the same focused tests in the Linux `habitat` conda environment.
6. Rerun the four-episode YOLO diagnostic with inverted sign and compare
   official metrics plus detector/policy traces against the adaptive-servo
   artifact.

## Verification Result

Completed on 2026-05-30.

- RED episode-loop test failed because
  `run_official_objectnav_episode_loop(...)` did not accept
  `detector_center_direction_sign`.
- RED CLI test failed because `--detector-center-direction-sign` was not a
  recognized flag.
- GREEN tests passed after adding config validation, manifest recording, CLI
  parsing, and per-episode state initialization from the configured sign.
- Local official evaluator/CLI tests passed: `47` tests.
- Local focused official-memory/exporter set passed: `66` tests.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set passed in conda env `habitat`:
  `66` tests.
- Linux `compileall` and `git diff --check` returned cleanly.

Diagnostic YOLO query smoke:

- Artifact:
  `runs/habitat_official_objectnav/memory_belief_frontier_inverted_center_sign_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.
- Official success stayed `0/4`; SPL stayed `0.0`; SoftSPL stayed
  `0.0009902771347611306`.
- Detector trace stayed unchanged from the adaptive-servo run:
  `196` calls, `224` detections, and `23` target-match detections.
- Policy trace stayed effectively unchanged:
  `23` `center_detector_target`, `22` `reacquire_detector_target`, `148`
  fallback decisions, and `4` budget stops.
- The first target-control action changed from `turn_right` to `turn_left`, but
  the policy still alternated around the same target-visible heading. This is
  negative evidence for the simple sign-convention hypothesis.

## Research Relevance

This is a root-cause ablation, not a new algorithmic contribution. It keeps the
official evaluator honest by testing a geometry/control convention hypothesis
before investing in a more ambitious multi-frame detector evidence controller.

## Open Questions

- Whether sign inversion changes target-match persistence or simply mirrors
  the existing oscillation.
- Whether the adaptive servo should be disabled in a future cleaner sign-only
  ablation.
