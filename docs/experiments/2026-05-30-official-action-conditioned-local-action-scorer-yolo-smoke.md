# Experiment Report: Official Action-Conditioned Local Action Scorer YOLO Trace

Date: 2026-05-30
Owner: Codex
Status: Completed offline diagnostic; not an ObjectNav benchmark result

## Question

Do action-state interaction features make the official local action scorer
produce state-dependent candidate rankings on the 20-episode temporal YOLO
trace?

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val_mini` |
| Simulator | Habitat-Lab official `ObjectNav-v1` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Dataset | `official-local-action-effect-v2`, 20-episode memory-evidence trace |
| Model | deterministic logistic regression with action-state interaction features |

## Command

```bash
PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.train_habitat_official_local_action_model \
  runs/habitat_official_objectnav/local_action_effect_dataset_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/dataset.json \
  --output runs/habitat_official_objectnav/local_action_effect_model_interaction_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/model.json \
  --epochs 500 \
  --learning-rate 0.1 \
  --l2 0.001 \
  --features <48 explicit one-frame, temporal, and action-state interaction features>
```

## Artifacts

- Dataset:
  `runs/habitat_official_objectnav/local_action_effect_dataset_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/dataset.json`
- Additive temporal model:
  `runs/habitat_official_objectnav/local_action_effect_model_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/model.json`
- Interaction temporal model:
  `runs/habitat_official_objectnav/local_action_effect_model_interaction_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/model.json`

## Metrics

All rows use the same 20-episode dataset and `labels.next_target_visible`.

| Model | Feature count | Accuracy | Log loss | Brier score | Mean prediction |
|---|---:|---:|---:|---:|---:|
| Default one-frame | `15` | `0.955063` | `0.174072` | `0.039334` | `0.315358` |
| Additive temporal | `30` | `0.987342` | `0.059308` | `0.011546` | `0.321754` |
| Action-conditioned temporal | `48` | `0.987975` | `0.054151` | `0.010386` | `0.321554` |

## Candidate Ranking Diagnostic

On the `500` visible-before examples:

- additive temporal model: `turn_right` was best for all `500`;
- action-conditioned temporal model: `turn_right` best for `272`,
  `turn_left` best for `150`, and `move_forward` best for `78`;
- best action changed between the additive and interaction models on `228`
  visible examples.

This confirms the intended modeling correction: temporal state alone improved
calibration, but interaction features are needed before temporal evidence can
change candidate ranking.

## Caveats

The data is still on-policy. Some high-offset counterfactual actions are
sparsely or never observed, so learned rankings can extrapolate outside the
trace support. This model should be treated as a candidate for online
diagnostic smoke testing, not as a paper claim.

## Verification

- Local interaction RED test failed before implementation and passed after
  interaction feature generation.
- Local model tests: `4` passed.
- Local focused official gate: `82` passed.
- Local `compileall`: passed.
- Local `git diff --check`: clean.
- Linux focused official gate in env `habitat`: `82` passed.
- Linux `compileall`: passed.
- Linux `git diff --check`: clean.
