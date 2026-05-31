# Design Doc: Official Ranker-Guided Active Perception

Date: 2026-05-31
Owner: Codex
Status: Implemented; diagnostic online smoke negative

## Goal

Use the offline candidate-viewpoint ranker as an online candidate selector for
the official `memory_active_perception_frontier` policy. The policy should keep
executing Habitat discrete actions, but when a ranker model is supplied it
should choose the active-perception viewpoint with the highest learned recovery
score instead of the hand-scored top candidate.

## Non-Goals

- Do not claim official ObjectNav success or SPL improvement from this wiring
  alone.
- Do not use candidate-viewpoint teleport labels online.
- Do not read detector-label fields, target visibility labels, or Habitat
  semantic oracle state at action time.
- Do not replace detector-first local centering/approach behavior.
- Do not remove top-rank/top-score/hand-score baselines; the ranker must remain
  optional and auditable.
- Do not add language or GPT control in this slice.

## Background

Candidate-viewpoint restore labels now show a stronger offline signal:
source-held-out model recovery is `22/31` current-hidden states, or `22/23`
oracle-recoverable states, versus `18/31` and `18/23` for top-rank/top-score.
The largest source holdout improved from a tie to model `14/23` versus
top-rank/top-score `13/23`, with oracle `15/23`. This is still offline
supervision, but it is enough to justify testing whether the learned selector
helps an online official-action policy.

The current online policy already computes top candidate viewpoints in
`_select_memory_active_perception_frontier(...)` and records the same feature
families used by the ranker: candidate rank/score, expected evidence, belief,
view quality, path distance, travel distance, bearing error, candidate cells,
target category, state decision, and state features. The missing bridge is a
loaded model artifact and a feature-compatible candidate row at action time.

## System Boundary

Modify the official Habitat evaluator only:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`
- `objectnav_core.cli.run_habitat_official_objectnav_eval`
- focused official evaluator and CLI tests
- docs/devlog/handoff/experiment report after smoke

The ranker model stays a JSON artifact produced by
`train_habitat_official_candidate_viewpoint_ranker`. Online policy code consumes
the artifact read-only.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Candidate ranker model | JSON | `habitat_official_candidate_viewpoint_ranker_model` artifact. |
| Input | Memory anchor | `OfficialMemoryAnchor` | Existing episode-relative anchor selection boundary. |
| Input | Occupancy map | `OccupancyFrontierMap` | Built online from official depth/GPS/compass. |
| Input | Observation | Habitat RGB-D/GPS/compass | No prior map or target pose. |
| Output | Action | Habitat discrete action | Existing policy action set. |
| Output | Debug payload | JSON-safe dict | Records ranker prediction, selected rank, and baseline hand score. |

## Interfaces

New API:

- `load_official_candidate_viewpoint_ranker_model(path)`

Extended config/API:

- `OfficialObjectNavRunConfig.candidate_viewpoint_ranker_model_path`
- `run_habitat_official_objectnav_eval(..., candidate_viewpoint_ranker_model_path=...)`
- `run_habitat_official_objectnav_preflight(..., candidate_viewpoint_ranker_model_path=...)`
- `run_official_objectnav_episode_loop(..., candidate_viewpoint_ranker_model=...)`

Extended CLI:

```bash
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --policy memory_active_perception_frontier \
  --memory-prior-path <memory_prior.json> \
  --candidate-viewpoint-ranker-model-path <model.json> \
  --output <run_dir>
```

## Data Flow

1. Validate and load the optional ranker model during preflight/eval setup.
2. Store the model on `OfficialPolicyState`.
3. Build active-perception candidate viewpoints exactly as the current policy
   does from the online occupancy map.
4. Add online ranker feature rows to each candidate using only pre-label fields:
   candidate rank, candidate count, hand score, expected evidence, belief,
   view-quality terms, path/travel distance, bearing error, candidate
   episode-relative pose, target category, current step index when available,
   and state features that can be known online.
5. If a model is present, compute `ranker_prediction` for each candidate with
   `predict_official_candidate_viewpoint_ranker(...)`.
6. Select the highest-prediction candidate; break ties with hand score,
   expected evidence, and shorter travel distance.
7. If no model is present, preserve current hand-score ordering exactly.
8. Record debug fields:
   `candidate_viewpoint_ranker_model`, `ranker_prediction`,
   `ranker_selected_candidate_rank`, and each top candidate's prediction.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Model path missing or wrong task | Config validation raises `ValueError` | Do not run silently with a bad model. |
| Ranker feature set lacks an online feature | Existing ranker prediction fills missing values with zero/preprocessing defaults | Debug records model feature count and prediction. |
| Model makes candidate choice worse | Online official smoke metrics and policy trace comparison | Keep baseline hand-score mode available; do not claim success from wiring. |
| Label leakage sneaks into online row | Unit tests assert no `labels`, detector confidence, or visibility fields are added | Use only the candidate fields already available before action selection. |
| Current policy behavior changes without model | Regression test with no model | Preserve existing hand-score selection path. |
| Model overfits source artifacts | Official online comparison against hand-score/top-rank/top-score | Treat smoke as diagnostic until larger independent runs pass. |

## Verification Plan

1. RED test: `load_official_candidate_viewpoint_ranker_model` rejects a wrong
   task and accepts a real ranker artifact shape.
2. RED test: `_select_memory_active_perception_frontier(...)` preserves the
   current hand-score winner when no ranker model is provided.
3. RED test: with a synthetic ranker model that weights `candidate_rank`, the
   active-perception selector chooses a lower hand-score candidate and records
   `ranker_prediction` debug.
4. RED test: `run_official_objectnav_episode_loop(...)` passes the model into
   policy state and emits ranker debug in `policy_debug.memory_prior`.
5. RED CLI/preflight test: `--candidate-viewpoint-ranker-model-path` reaches
   the runner and appears in the protocol manifest.
6. Run focused official evaluator/CLI tests, ranker tests, full local suite,
   compileall, `git diff --check`, and a touched-file whitespace scan.
7. Sync/run focused tests on Linux in conda env `habitat`.
8. Run a small official Habitat/Yolo query smoke comparing:
   - baseline `memory_active_perception_frontier`;
   - ranker-guided `memory_active_perception_frontier` with the v2 source-diverse
     model.

## Implementation Status

Implemented on 2026-05-31.

- Added optional loading/manifest plumbing for
  `habitat_official_candidate_viewpoint_ranker_model` artifacts.
- Added `--candidate-viewpoint-ranker-model-path` to the official evaluator CLI.
- Added model storage on `OfficialPolicyState`.
- Added online candidate rows and ranker predictions to the existing
  `memory_active_perception_frontier` selector.
- Preserved the no-model hand-score path.
- Added a top-K guard: the online ranker only reranks the same bounded
  hand-score top-K candidate set that the offline restore-label model was
  trained on. This prevents unbounded `candidate_rank` extrapolation.

Diagnostic result:

- Preflight with the real source-diverse v2 ranker model succeeded and recorded
  the 49-feature logistic model in `protocol_manifest.json`.
- An initial smoke before the top-K guard exposed a bug: the model scored all
  online frontier candidates and selected high hand-rank candidates such as
  `40`, `53`, and `84`, outside the top-5 restore-label distribution.
- After the top-K guard, a 4-episode YOLO query smoke ran successfully:
  `runs/habitat_official_objectnav/ranker_guided_active_perception_yolo_4ep_50steps_20260531_v2`.
- Official Habitat success remained `0/4`, SPL `0.0`, and SoftSPL
  `0.0009902771347611306`.
- Detector target-match calls regressed to `0`, while prior hand-score
  active-perception baselines on the same memory prior had nonzero target-match
  calls (`39` for the original active-perception smoke and `30` for the
  rotation-aware smoke).
- The ranker was active for `49` policy-trace steps and usually selected
  hand-score rank `4` within the bounded top-5 set.
- A no-`candidate_rank` ablation was trained as
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1`.
  It preserved offline leave-one-source recovery (`22/31` all current-hidden
  states, `22/23` oracle-recoverable states) but did not improve the matched
  online smoke: success `0/4`, SPL `0.0`, SoftSPL
  `0.0009902771347611306`, and `0` target-match detector calls.
- The ablation still selected hand-score rank `4` on `48/49` online
  ranker-active steps, so `candidate_rank` is not the sole cause of the
  transfer failure.
- A controller-mismatch diagnostic then added short-lived viewpoint commitment
  and a blocked-target local scan to the online active-perception option. Sticky
  commitment alone did not recover evidence, but adding the blocked scan raised
  the no-rank smoke to `4` target-match calls and SoftSPL
  `0.02518699682786324` while success stayed `0/4`.
- The matched no-ranker hand-score smoke under the same controller produced the
  same result: success `0/4`, SPL `0.0`, SoftSPL `0.02518699682786324`, and `4`
  target-match calls.

Interpretation:

The offline candidate-viewpoint ranker is wired into the online policy, but the
first online transfer result is negative. The likely issue is distribution
mismatch: the offline teleport/restore labels reward candidate viewpoints that
can reveal the object under fixed heading scans, while the online policy still
has to physically approach, orient, avoid blocked corridors, and interact with
detector centering/reacquisition. The no-`candidate_rank` ablation shows that
candidate rank alone is not enough to explain the failure; other geometry and
state features can reproduce the same preference for poor online candidates.
The controller-mismatch diagnostic adds a second constraint: the offline label
continuation and the online option controller must match. The recovered target
evidence came from controller alignment and was matched by the hand-score
selector, so it is not a learned-ranker win. This is useful evidence that the
next publishable algorithm should train on online option rollouts, or use a
conservative ranker/blended value objective, rather than directly deploying the
offline classifier as a policy.

## Research Relevance

This is the first direct bridge from offline memory-viewpoint supervision to an
online ObjectNav policy. If the learned selector improves target-view detector
evidence or official metrics over the existing hand-score selector, it becomes
a defensible algorithmic contribution: lifelong memory supplies candidate
locations, active perception generates reachable inspection viewpoints, and a
learned model chooses which viewpoint to inspect first. If it does not improve
online behavior, the negative result is still useful because it distinguishes
offline label recoverability from policy usefulness.

## Open Questions

- Should the first online comparison use the source-diverse v2 full model or a
  model trained without the largest phase-path source to reduce source-family
  bias?
- Do we need explicit `state_features` parity between restore-label rows and
  online policy rows before broader training, or is candidate geometry enough
  for the first online smoke?
- Should the online policy report separate model-selected, hand-score-selected,
  and top-rank-selected candidates in trace rows for richer ablations?
- What is the smallest online rollout label that predicts downstream utility:
  next-window detector target evidence, official progress gain, or a
  short-horizon success proxy?
- Should future candidate labels execute the exact sticky plus blocked-scan
  option controller used online before assigning utility?
