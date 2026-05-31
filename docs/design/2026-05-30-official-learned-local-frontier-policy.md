# Design Doc: Official Learned Local Frontier Policy

Date: 2026-05-30
Owner: Codex
Status: Implemented; four-episode YOLO smoke is diagnostic only

## Goal

Add an official Habitat ObjectNav policy variant that uses the learned local
action-effect scorer online. The new policy should keep memory-conditioned
search and detector evidence from `memory_evidence_frontier`, but replace the
hand-authored "approach after failed centering" action with candidate scoring
over official discrete actions.

## Non-Goals

- Do not replace or silently change `memory_evidence_frontier`.
- Do not use oracle semantics, Habitat success, geodesic distance, pathfinder
  routes, or future observations for online action selection.
- Do not claim benchmark improvement until official Habitat metrics improve.
- Do not make the logistic scorer look stronger than it is; the current model
  is trained from a sparse four-episode smoke and is only a diagnostic policy.
- Do not integrate language/GPT control in this slice.

## Background

The local action-effect dataset and scorer established a learning interface:
given current target evidence, score `move_forward`, `turn_left`, and
`turn_right` for next-step target visibility. On the visible `tv_monitor`
failure rows, the scorer ranked `turn_left` above repeated forward movement,
including at the final visible step before target loss.

The next useful test is online integration. The right comparison is not to
change the existing ablation, but to add a new policy:

- `memory_evidence_frontier`: hand-authored action-effect baseline
- `memory_learned_local_frontier`: learned local action scorer plugged into the
  same official memory/detector/fallback boundary

## System Boundary

Modify the official ObjectNav evaluator and CLI:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`
- `objectnav_core.cli.run_habitat_official_objectnav_eval`
- focused official evaluator/CLI tests

Reuse:

- official memory prior handling;
- detector traces and policy traces;
- `OfficialPolicyState`;
- `score_official_local_action_candidates` from
  `habitat_official_local_action_model`;
- official Habitat discrete action strings only.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Memory prior | JSON anchors | Same requirement as memory policies. |
| Input | Local action model | JSON logistic model | Required for `memory_learned_local_frontier`. |
| Input | Detector match | RGB detector result | Same detector adapter boundary. |
| Output | Action | Habitat discrete action | Chosen from official actions. |
| Output | Debug | `policy_trace.json` / `policy_debug.memory_prior` | Includes candidate scores and selected learned action. |
| Output | Manifest | `protocol_manifest.json` | Records model path and model metadata. |

## Interfaces

Policy:

- `policy="memory_learned_local_frontier"`

CLI:

```bash
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --policy memory_learned_local_frontier \
  --memory-prior-path <memory_prior.json> \
  --local-action-model-path <model.json>
```

Python API arguments:

- `local_action_model_path: str | Path | None = None`

## Data Flow

1. Load and validate the local action model once before the episode loop.
2. Store the loaded model in `OfficialPolicyState`.
3. If target detector confirms range, STOP as before.
4. If target is visible but not range-confirmed, construct a model example from
   current pre-action detector evidence, pose, heading, and failed-center state.
5. Build candidates:
   - suppress detector-centering turn actions already observed to lose the
     target for the current bbox offset sign;
   - include remaining `turn_left` / `turn_right` candidates when target is
     visible;
   - include `move_forward` only when the center corridor is clear.
6. Score candidates with `score_official_local_action_candidates`.
7. Execute the highest-scoring candidate and record compact debug fields:
   selected action, candidate scores, score label, suppressed centering actions,
   and detector evidence.
8. If the detector is lost immediately after a centering/learned turn, reuse the
   existing reacquisition/action-effect bookkeeping.
9. If no detector-local action applies, fall back to memory-belief frontier.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Model file missing or malformed | Preflight/eval validation fails | Require explicit `--local-action-model-path` for learned policy. |
| Sparse model prefers bad turn | Official metrics and trace reveal regression | Keep as separate ablation policy; do not replace baseline. |
| Model prefers an action already observed to lose the target | Policy trace shows chosen action equals suppressed failed turn | Exclude failed turn candidates for the current offset sign before scoring. |
| Model selects forward into obstacle | Candidate builder excludes `move_forward` when center depth is blocked | Fall back to turn candidates. |
| Model scores are all low | Trace records scores | Still chooses argmax; later policy can add calibrated abstention after larger data. |
| Learned policy overfits four episodes | Larger official smoke fails | Record as negative result; collect larger traces before paper claims. |

## Verification Plan

1. RED registration/preflight test:
   - policy is supported;
   - learned policy requires both memory prior and model path;
   - manifest records model metadata.
2. RED CLI test:
   - `--local-action-model-path` is accepted and written to manifest.
3. RED behavior test:
   - use a synthetic model that scores `turn_left` higher than `move_forward`;
   - reproduce target-visible after failed centering;
   - assert learned policy chooses `turn_left` where
     `memory_evidence_frontier` would choose `move_forward`;
   - assert policy trace records `decision="learned_local_action_score"`.
4. Run focused local official tests, compile checks, and `git diff --check`.
5. Copy to Linux and run the same focused set in conda env `habitat`.
6. Run a small YOLO comparison against the existing four-episode artifact and
   document official metrics without overclaiming.

Completed verification:

- Local focused official-memory/exporter/model/evaluator gate: `80` passed.
- Local `compileall` and `git diff --check`: clean.
- Linux focused official gate in env `habitat`: `80` passed.
- Linux `compileall` and `git diff --check`: clean.
- Initial YOLO smoke without failed-turn candidate suppression regressed to the
  old center/reacquire loop: success `0/4`, SPL `0.0`, SoftSPL
  `0.0009902771347611306`.
- Fixed YOLO smoke with failed-turn candidate suppression restored the
  action-effect behavior: success `0/4`, SPL `0.0`, SoftSPL
  `0.02518699682786324`, mean distance-to-goal `5.697803378105164`.

## Result Update

The online learned scorer is verified as a policy variant, but the current
single-step model is not a benchmark improvement. The first smoke exposed a
boundary bug: the scorer could choose a detector turn already recorded as
losing the target. Excluding failed turn candidates for the current bbox offset
sign prevents that loop and makes the learned policy behave like the
action-effect baseline on the four-episode YOLO diagnostic. This is a useful
negative result: the next publishable direction needs richer temporal evidence
or a short-horizon local controller, not only a one-step visibility scorer.

## Research Relevance

This is the first online bridge from memory-conditioned ObjectNav to learned
local action-effect control. It keeps the robot-facing story intact: memory
anchors the search region, detector evidence grounds the target, and a learned
model chooses local actions under partial-FOV uncertainty. The design is also
portable to the real robot because the scorer depends on action/evidence traces,
not Habitat-only oracle state.

## Open Questions

- Whether the first learned policy should always trust the scorer or add a
  confidence/abstention gate after larger data collection.
- Whether training should optimize next target visibility or a multi-task score
  combining visibility, bbox area, center offset, and depth.
- Whether the learned policy can improve official success or only provide a
  better trace diagnostic until more data exists.
