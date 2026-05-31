# Design Doc: Official Temporal Learned Local Frontier Policy

Date: 2026-05-30
Owner: Codex
Status: Implemented locally; Linux mirror sync blocked by SSH timeout

## Goal

Carry the same past-only temporal local-action features used by the v2
offline dataset into the online `memory_learned_local_frontier` policy. A
temporal/action-conditioned local action model should receive observed history
values at runtime instead of relying on training-set mean imputation.

## Non-Goals

- Do not change official Habitat metric collection.
- Do not replace `memory_evidence_frontier`.
- Do not use future observations, oracle semantics, shortest paths, or Habitat
  success signals as online features.
- Do not claim ObjectNav benchmark progress from offline model metrics alone.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`
- focused official evaluator tests

Reuse the existing model artifact format and candidate scorer. The dataset
schema remains unchanged.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Current detector match | policy-local debug evidence | Target category, confidence, bbox, depth, offset. |
| Input | Prior policy steps | in-memory history | Previous action, decision, and detector-visible evidence. |
| Input | Local action model | JSON logistic model | May include temporal and interaction feature names. |
| Output | Candidate scores | policy debug | Same action-score map, now backed by temporal features. |
| Output | Policy trace | JSON | Records compact temporal feature values for audit. |

## Data Flow

1. After each selected action, append a compact pre-action record to
   `OfficialPolicyState`: step index, action, decision, pose, heading, and
   detector evidence if the target was visible.
2. Keep only the recent history needed for the local-action feature window.
3. When building the learned-local model example, combine current detector
   evidence with prior records to compute:
   - previous target visibility;
   - recent visible count;
   - recent action and reacquisition counts;
   - confidence, area, depth, and absolute-offset deltas;
   - suppressed turn flags.
4. Score only the already-allowed candidate actions. Failed turn suppression
   remains the policy boundary before model scoring.
5. Record compact temporal feature values in policy debug so traces can show
   what the model actually saw.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| History leaks current action before scoring | Unit test checks a temporal model flips only from previous observations | Append history only after action selection. |
| Missing temporal features silently use means | Policy trace lacks expected temporal feature payload | Record compact online feature values in learned-local debug. |
| Stale history crosses episodes | Per-episode `OfficialPolicyState` construction resets history | State is rebuilt on every `env.reset()`. |
| Sparse interaction model extrapolates poorly | Official smoke trace and candidate scores regress | Keep variant separate and report negative results honestly. |

## Verification Plan

1. RED online policy test with a hand-authored temporal interaction model:
   without real history, `move_forward` wins; with recent target-visible
   history, `turn_left` wins.
2. GREEN policy-state history and temporal feature builder.
3. Run focused official evaluator/model gate, `compileall`, and
   `git diff --check`.
4. Mirror to Linux, run the same focused gate, then run a small official YOLO
   smoke only if the offline and trace diagnostics justify it.

Completed local verification:

- RED online policy test failed because the temporal interaction model picked
  `move_forward` when runtime examples omitted recent target-visible history.
- GREEN learned-local policy tests around learned scoring, online temporal
  history, and failed-turn suppression: `3` passed.
- Local focused official-memory/exporter/model/evaluator gate: `83` passed.
- Local `compileall` and `git diff --check` returned cleanly.

Not completed:

- Linux mirror sync and Linux focused gate for this online temporal-policy
  slice were blocked by SSH timeout to `badger@100.88.131.52`.
- No official YOLO smoke was run with the temporal interaction model online.

## Research Relevance

This closes the train/test feature gap for learned local control. It lets the
official online policy consume the same temporal detector trends that improved
offline calibration, while keeping the benchmark boundary clean and
hardware-independent.
