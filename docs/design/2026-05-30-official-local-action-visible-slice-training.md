# Design Doc: Official Local Action Visible-Slice Training

Date: 2026-05-30
Owner: Codex
Status: Implemented locally; Linux mirror sync pending

## Goal

Allow the official local action model trainer to fit on target-visible
examples only. The online `memory_learned_local_frontier` scorer is invoked
when the target detector is currently visible, so training should support a
matching visible-control slice instead of always mixing in absent/search rows.

## Non-Goals

- Do not remove full-dataset training.
- Do not change official Habitat metrics.
- Do not hide the filter; the model artifact must record it.
- Do not make this an online heuristic. This is a training-distribution choice.

## Background

The 20-episode temporal dataset has `1580` examples but only `500`
visible-before examples. Training on all rows is useful for calibration, but
the local controller is queried only after target evidence exists. Absent rows
can dominate loss and action priors, especially for action-conditioned
features. A visible-only training option lets us compare full-trace and
local-control-specific models without changing the policy boundary.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_local_action_model`
- `objectnav_core.cli.train_habitat_official_local_action_model`
- focused model/CLI tests

Dataset export and online policy code remain unchanged.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|
| Input | Dataset examples | JSON | Existing v1/v2 local action-effect examples. |
| Input | `current_visible_only` / CLI flag | boolean | Defaults to false. |
| Output | Model artifact | JSON | Records filtered example counts and filter settings. |

## Data Flow

1. Load and parse examples as before.
2. If `current_visible_only` is true, keep examples whose
   `features.current_target_visible` is truthy.
3. Train using the filtered rows.
4. Record both the source example count and training example count in the
   artifact.
5. Raise a clear error if the filter removes every example.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Filter silently changes sample size | Artifact records source and trained counts | Tests assert counts. |
| No visible examples | Trainer raises `ValueError` | Caller must collect richer traces. |
| Existing scripts break | Default keeps full dataset | CLI flag is opt-in. |

## Verification Plan

1. RED API test: train with `current_visible_only=True` on mixed examples and
   assert only visible rows are counted.
2. GREEN trainer filtering and artifact metadata.
3. RED CLI test: `--current-visible-only` writes a filtered model artifact.
4. GREEN CLI parser plumbing.
5. Run focused model tests, focused official gate, `compileall`, and
   `git diff --check`.

Completed local verification:

- RED API test failed because the trainer did not accept
  `current_visible_only`.
- GREEN API test passed after filtering examples before preprocessing.
- RED CLI test failed because `--current-visible-only` was not accepted.
- GREEN CLI test passed after parser/trainer plumbing.
- Local model tests: `8` passed.
- Local focused official-memory/exporter/model/evaluator gate: `87` passed.
- Local `compileall` and `git diff --check` returned cleanly.

Not completed:

- Linux mirror sync and Linux focused gate are pending while `badger-linux` is
  offline over Tailscale.

## Research Relevance

This makes the offline learning protocol closer to the online local-control
use case. It supports a more honest ablation matrix: full-trace calibration,
visible-only local control, horizon labels, and action-conditioned temporal
features can be compared separately before any official benchmark claim.
