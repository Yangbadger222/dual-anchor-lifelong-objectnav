# Design Doc: Official Local Action Candidate Score Report

Date: 2026-05-30
Owner: Codex
Status: Implemented; Linux diagnostic comparison completed

## Goal

Add a reproducible report for applying a trained official local action model
to a local action-effect dataset and summarizing candidate rankings. This
turns ad hoc Python inspection into a JSON/CSV artifact that can be used before
online official smoke runs.

## Non-Goals

- Do not change model training or online policy behavior.
- Do not treat offline candidate rankings as official ObjectNav metrics.
- Do not require Habitat or detector dependencies.

## Background

The action-conditioned temporal model finally produced state-varying candidate
rankings, but that finding came from an ad hoc script. For paper-quality
experiments, model selection needs a repeatable diagnostic artifact that shows
which actions the model prefers, where rankings differ between models, and
whether summaries are computed on the same visible-control slice used online.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_local_action_model`
- add a CLI under `objectnav_core.cli`
- focused local action model tests

The report consumes existing dataset/model JSON artifacts only.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Dataset | local action-effect JSON | v1 or v2 examples. |
| Input | Model | local action logistic model JSON | Existing artifact. |
| Input | Candidate actions | comma-separated strings | Defaults to `move_forward,turn_left,turn_right`. |
| Input | `current_visible_only` | boolean | Optional diagnostic slice. |
| Output | Report JSON | summary plus rows | Offline diagnostic only. |
| Output | CSV | per-example candidate scores | Optional. |

## Data Flow

1. Load dataset and model JSON.
2. Parse valid examples, optionally filtering to current-visible examples.
3. For each example, score candidate actions with
   `score_official_local_action_candidates`.
4. Write one row per example with identity fields, observed action, label,
   current-visible flag, best action, whether best action matches observed
   action, and candidate scores.
5. Aggregate best-action counts, observed-action counts, label counts, and
   best-action match count.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Dataset has no examples after filter | Function raises `ValueError` | Caller should collect or choose another slice. |
| Candidate action list is empty | CLI/parser rejects or report raises | Require at least one action. |
| Report mistaken for benchmark result | `task` and docs label it as diagnostic | Official metrics remain untouched. |

## Verification Plan

1. RED API test with a hand-authored interaction model and two examples whose
   best actions differ.
2. GREEN report function and CSV writer.
3. RED CLI test that writes JSON and CSV.
4. GREEN CLI.
5. Run focused model tests, focused official gate, `compileall`, and
   `git diff --check`.

## Implementation Notes

- Added `score_official_local_action_dataset_candidates` and
  `write_official_local_action_candidate_scores_csv` in
  `objectnav_core.evaluation.habitat_official_local_action_model`.
- Added
  `objectnav_core.cli.score_habitat_official_local_action_model`, including
  `--model`, `--output`, `--csv-output`, `--actions`, and
  `--current-visible-only`.
- Registered the installable console script as
  `objectnav_habitat_official_local_action_score`.
- Local verification on 2026-05-30 passed:
  `pytest -q ...` focused official gate (`89 passed`),
  `python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests`,
  and `git diff --check`.
- Linux verification on 2026-05-30 passed the same focused gate
  (`89 passed`), compileall, and `git diff --check`.
- Linux diagnostic artifacts were written under
  `runs/habitat_official_objectnav/local_action_model_comparison_temporal_yolo_20ep_80steps_20260530_v1`.

## Research Relevance

This report is a guardrail for the learned local-control paper story. It makes
offline model comparison auditable before we spend official Habitat runs, and
it records when a model is merely calibrated versus actually changing local
action rankings.
