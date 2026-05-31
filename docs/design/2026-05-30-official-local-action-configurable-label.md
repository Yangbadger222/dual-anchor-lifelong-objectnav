# Design Doc: Official Local Action Configurable Label Training

Date: 2026-05-30
Owner: Codex
Status: Implemented locally; Linux mirror sync pending

## Goal

Allow the official local action logistic scorer to train on any boolean label
present in the local action-effect dataset, not only `next_target_visible`.
This lets us train short-horizon retention models such as
`target_visible_at_horizon` or `target_lost_within_horizon` without changing
the online policy boundary or official Habitat metrics.

## Non-Goals

- Do not change official ObjectNav metric collection.
- Do not claim benchmark progress from alternate offline labels.
- Do not add a black-box learning dependency.
- Do not remove the default `next_target_visible` behavior.

## Background

The temporal v2 dataset added horizon labels, but the trainer still hard-codes
`next_target_visible`. That label is too myopic for the failure mode seen in
YOLO traces: actions can preserve visibility for one step while making bbox
area shrink and center offset drift until the target is lost. A stronger local
controller needs to compare labels aligned with retention and short-horizon
evidence quality.

## Approach Options

Recommended: add a `label_name` argument to the trainer and `--label` to the
CLI, with the current label as default. This is the smallest interface that
unlocks horizon-label experiments while preserving all existing artifacts.

Alternative 1: create a separate horizon trainer. This would duplicate
preprocessing and candidate scoring logic.

Alternative 2: encode multiple heads in one artifact. That is more expressive,
but premature before we know which label produces useful online behavior.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_local_action_model`
- `objectnav_core.cli.train_habitat_official_local_action_model`
- focused model/CLI tests

Dataset export and online policy code remain unchanged in this slice.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Dataset example labels | JSON object | Any boolean-ish label under `example["labels"]`. |
| Input | `label_name` / `--label` | string | Defaults to `next_target_visible`. |
| Output | Model artifact | JSON | Records the selected `label_name` and metrics for that target. |
| Output | Candidate scores | JSON/debug | Existing scorer reports the artifact label name. |

## Data Flow

1. CLI parses `--label`, defaulting to `next_target_visible`.
2. Trainer passes `label_name` into label extraction.
3. Missing or falsey labels are treated as negative, matching current behavior.
4. Model artifact records the selected label name.
5. Prediction/scoring continues to use the artifact `feature_names`, weights,
   preprocessing, and label metadata.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Label typo creates all-negative training data | Existing one-class warning records the issue | Keep warning behavior; artifact exposes selected label. |
| CLI silently ignores requested label | CLI test asserts model artifact label and counts | Add `--label` coverage. |
| Existing users break | Default remains `next_target_visible` | Preserve current API default. |

## Verification Plan

1. RED API test: train on `target_visible_at_horizon` and assert label name and
   positive count use that label rather than `next_target_visible`.
2. GREEN trainer label plumbing.
3. RED CLI test: `--label target_visible_at_horizon` writes an artifact with
   the requested label.
4. GREEN CLI parser plumbing.
5. Run focused model tests, focused official gate, `compileall`, and
   `git diff --check`.

Completed local verification:

- RED API test failed because `train_official_local_action_logistic_model`
  did not accept `label_name`.
- GREEN API test passed after label extraction used the requested label.
- RED CLI test failed because `--label` was not accepted.
- GREEN CLI test passed after parser/trainer plumbing.
- Local model tests: `6` passed.
- Local focused official-memory/exporter/model/evaluator gate: `85` passed.
- Local `compileall` and `git diff --check` returned cleanly.

Not completed:

- Linux mirror sync and Linux focused gate are pending because the Tailscale
  peer `badger-linux` is currently offline from this machine.

## Research Relevance

This supports the paper-facing learned local controller direction by making it
easy to compare one-step visibility, horizon retention, and loss-avoidance
targets on the same official traces. It is a modest interface change, but it
prevents us from overfitting the algorithmic story to a myopic label.
