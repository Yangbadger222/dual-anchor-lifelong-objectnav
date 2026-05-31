# Design Doc: Official Action-Conditioned Local Action Scorer

Date: 2026-05-30
Owner: Codex
Status: Implemented locally and on Linux mirror; offline 20-episode diagnostic completed

## Goal

Make the learned local action scorer capable of state-dependent candidate
ranking. The scorer should support action-conditioned interaction features such
as `action_move_forward__current_abs_center_offset_fraction`, so temporal and
geometric state can change which candidate action is preferred.

## Non-Goals

- Do not add a new online policy in this slice.
- Do not change official Habitat metric handling.
- Do not claim ObjectNav benchmark improvement from offline model metrics.
- Do not add a black-box dependency; keep the deterministic logistic model
  auditable.

## Background

The temporal v2 dataset improved offline next-visibility prediction, but the
existing logistic candidate scorer is additive:

```text
score(action, state) = action_weight(action) + state_weight(state)
```

Because the state term is identical for all candidate actions, temporal
features improve calibration but cannot change action ranking except through
candidate suppression. A serious local controller needs state-action
interactions: moving forward may be good when centered and bad when bbox offset
is increasing, while turning may have the opposite behavior.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_local_action_model`
- focused model tests

The dataset schema remains unchanged. The trainer and scorer should generate
interaction values on demand when feature names contain `__`.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Dataset example | JSON example with `features` and `action` | Same v1/v2 dataset examples. |
| Input | Candidate action | Habitat discrete action string | Overrides example action during candidate scoring. |
| Input | Feature name | `action_<name>__<state_feature>` | Generated as action one-hot times numeric state feature. |
| Output | Prediction | probability | Same logistic scorer output. |
| Output | Model artifact | JSON | Feature names record selected interaction terms. |

## Interfaces

No CLI change is required because `--features` already accepts comma-separated
feature names. Interaction features can be trained with:

```bash
--features action_move_forward__current_abs_center_offset_fraction,\
action_turn_left__current_abs_center_offset_fraction
```

## Data Flow

1. Build base feature values exactly as before, including action one-hots and
   numeric temporal fields.
2. When a requested feature name contains `__`, split it into
   `left_feature__right_feature`.
3. If both sides are finite numeric values, emit their product.
4. For candidate scoring, recompute the base action one-hots for each candidate
   action, so interaction terms become candidate-specific.
5. Missing or nonnumeric interactions remain `None` and use the existing
   training-time mean imputation path.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Interaction feature misspelled | Feature has no finite values and preprocessing warns | Keep existing warnings; model artifact exposes feature names. |
| Interaction accidentally uses label/future field | Feature only exists if present in base features | Do not copy labels into base features. |
| Ranking still action-constant | Unit test scores two states and verifies best action changes | Require candidate scoring test. |
| Too many interactions overfit | Offline metrics look high but online fails | Treat as diagnostic until official online policy improves. |

## Verification Plan

1. RED unit test with a hand-authored model:
   - low-offset example should prefer `move_forward`;
   - high-offset example should prefer `turn_left`;
   - same model, same candidate set, different state.
2. GREEN interaction feature generation in `_feature_values`.
3. Run focused local model tests and official gate.
4. Train an interaction temporal model on the 20-episode v2 dataset and compare
   offline metrics against additive temporal features.

Completed verification:

- RED local unit test failed because interaction feature values were not
  generated and the hand-authored model still preferred `move_forward` at high
  offset.
- GREEN local model tests: `4` passed.
- Local focused official-memory/exporter/model/evaluator gate: `82` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official gate in conda env `habitat`: `82` passed.
- Linux `compileall` and `git diff --check` returned cleanly.
- Linux 20-episode interaction temporal model training completed.

## Result Update

On the same 20-episode temporal v2 dataset, action-conditioned interaction
features improved the offline next-visible model from the additive temporal
log loss `0.059308` to `0.054151` and Brier score `0.011546` to `0.010386`.
More importantly for policy use, the additive temporal model ranked
`turn_right` first on all `500` visible examples, while the interaction model
produced state-varying best actions: `272` `turn_right`, `150` `turn_left`,
and `78` `move_forward`.

This is still not an ObjectNav result. The trace remains on-policy and has
sparse support for some counterfactual action/state pairs, so online smoke
testing must inspect candidate scores and official metrics before any claim.

## Research Relevance

This is necessary for a publishable learned local controller. It lets the model
learn action effects conditioned on detector geometry and recent evidence,
rather than choosing a globally preferred action. The mechanism is simple and
auditable, and it can later be replaced by a richer sequence model while
preserving the same state-action interface.

## Open Questions

- Which interaction feature subset best balances expressiveness and overfit.
- Whether the online policy should use single-action interactions first or move
  directly to short action-sequence scoring.
