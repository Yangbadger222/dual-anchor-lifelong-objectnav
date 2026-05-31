# Experiment Report: Official Local Action-Effect Scorer YOLO Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Can the official local action-effect dataset train a persisted scorer that
predicts next-step target visibility and produces candidate-action scores for
the fragile `tv_monitor` local-control states?

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Source dataset | `runs/habitat_official_objectnav/local_action_effect_dataset_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/dataset.json` |
| Source policy | `memory_evidence_frontier` |
| Source detector | YOLO-World target-category matching |
| Training model | Deterministic logistic regression |
| Label | `labels.next_target_visible` |

## Command

```bash
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.train_habitat_official_local_action_model \
  runs/habitat_official_objectnav/local_action_effect_dataset_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/dataset.json \
  --output runs/habitat_official_objectnav/local_action_effect_model_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/model.json \
  --epochs 400 \
  --learning-rate 0.1 \
  --l2 0.001
```

The same export/train commands were also run on the Linux mirror in conda env
`habitat`.

## Artifacts

- `runs/habitat_official_objectnav/local_action_effect_model_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/model.json`

## Metrics

| Metric | Value |
|---|---:|
| Examples | `196` |
| Positive labels | `4` |
| Negative labels | `192` |
| Accuracy | `0.989796` |
| Log loss | `0.057894` |
| Brier score | `0.011688` |
| Mean prediction | `0.026852` |

These metrics are dominated by class imbalance and must not be used as evidence
of ObjectNav improvement.

## Candidate Scores on Visible `tv_monitor` Rows

| Step | Actual action | Next visible | Best candidate | Move forward | Turn left | Turn right |
|---:|---|---|---|---:|---:|---:|
| `3` | `turn_left` | true | `turn_left` | `0.013959` | `0.031805` | `0.012813` |
| `4` | `turn_right` | false | `turn_left` | `0.082834` | `0.173258` | `0.076469` |
| `5` | `turn_left` | true | `turn_left` | `0.013959` | `0.031805` | `0.012813` |
| `6` | `move_forward` | true | `turn_left` | `0.833344` | `0.920653` | `0.820927` |
| `7` | `move_forward` | true | `turn_left` | `0.678285` | `0.830284` | `0.659042` |
| `8` | `move_forward` | false | `turn_left` | `0.457599` | `0.661889` | `0.436128` |

## Interpretation

This is a useful diagnostic, not a policy result. The scorer learned from a
tiny behavior-policy trace and therefore cannot be trusted as a final local
controller. However, it produces the right kind of actionable hypothesis: on
the edge-visible states where repeated forward movement eventually lost the
target, the model assigns higher target-retention probability to `turn_left`.
That gives the next official policy slice a concrete learned candidate scorer
to test against official Habitat metrics.

## Follow-up

- Integrate the scorer as a new policy variant, likely
  `memory_learned_local_frontier`, without changing `memory_evidence_frontier`.
- Collect larger official traces so the learned local scorer has more than four
  positive labels.
- Compare learned-local policy against `memory_evidence_frontier` on official
  Habitat success/SPL/SoftSPL before making any benchmark-facing claim.
