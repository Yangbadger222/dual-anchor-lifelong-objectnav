# Experiment Report: Official Candidate-Viewpoint Ranker

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Can the candidate-viewpoint restore labels support a held-out candidate ranker
that chooses useful memory-inspection viewpoints better than simple top-rank or
top-score selection?

## Hypothesis

The new teleport/restore labels should contain enough signal for a deterministic
logistic ranker to recover more current-hidden states than the candidate order
or raw candidate score baselines, but a one-source artifact is not enough for an
online-policy claim.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `0f14893` plus uncommitted research changes |
| Machine | Linux mirror `badger@100.88.131.52` |
| Dataset / bag / map | `runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1/dataset.json` |
| Simulator / robot | Offline Habitat-Sim restore labels from prior export; no robot |
| Key parameters | current-hidden filter, `fold-count=4`, logistic epochs `600`, learning rate `0.2`, L2 `0.001` |

## Command

```bash
OUT=runs/habitat_official_objectnav/candidate_viewpoint_ranker_phase_path_features_max8cat_max2episode_yolo_20260531_v1
mkdir -p "$OUT"
/home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1/dataset.json \
    --output "$OUT/model.json" \
    --scores-output "$OUT/scores.json" \
    --csv-output "$OUT/scores.csv" \
    --state-fold-output "$OUT/state_folds.json" \
    --fold-count 4
```

## Metrics

### Single-Source Baseline

| Metric | Value | Notes |
|---|---:|---|
| Source candidates | `120` | Before current-hidden filtering |
| Training/eval candidates | `115` | Current-hidden, label-available rows |
| Positive candidates | `69` | `hidden_to_visible_from_candidate_viewpoint=true` |
| Negative candidates | `46` | Current-hidden non-recovery rows |
| Candidate ROC-AUC | `0.959042` | Train-set diagnostic only |
| Candidate accuracy | `0.878261` | Train-set diagnostic only |
| Current-hidden states | `23` | One current-visible state filtered out |
| Oracle-recoverable states | `15/23` | At least one positive candidate |
| Model-recovered states | `14/23` | State-level top model score |
| Top-rank baseline | `13/23` | Candidate rank `0` |
| Top-score baseline | `13/23` | Highest raw candidate score |
| 4-fold state-holdout model | `14/23` | Train/holdout state keys disjoint by fold |
| 4-fold top-rank baseline | `13/23` | Same holdout states |
| 4-fold top-score baseline | `13/23` | Same holdout states |

### Source-Diverse Validation

Source-diverse candidate-viewpoint label exports:

| Source artifact | States | Candidates | Visible | Hidden-to-visible | Invalid restores |
|---|---:|---:|---:|---:|---:|
| `candidate_viewpoint_restore_active_frontier_4ep_yolo_20260531_v2` | `2` | `10` | `10` | `10` | `0` |
| `candidate_viewpoint_restore_rotation_aware_4ep_yolo_20260531_v2` | `2` | `10` | `10` | `10` | `0` |
| `candidate_viewpoint_restore_path_aware_4ep_yolo_20260531_v1` | `2` | `10` | `7` | `7` | `0` |
| `candidate_viewpoint_restore_viewpoint_scan_4ep_yolo_20260531_v1` | `2` | `10` | `6` | `6` | `0` |
| `candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1` | `24` | `120` | `74` | `69` | `0` |

Ranker output:

```bash
runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v2
```

| Metric | Value | Notes |
|---|---:|---|
| Source candidates | `160` | Five input artifacts |
| Training/eval candidates | `155` | Current-hidden and label-available |
| Positive candidates | `102` | Hidden-to-visible rows |
| Negative candidates | `53` | Label-available non-recovery rows |
| Candidate ROC-AUC | `0.949131` | Train-set diagnostic only |
| Current-hidden states | `31` | Label-available grouped states |
| Oracle-recoverable states | `23/31` | At least one positive candidate |
| Model-recovered states | `22/31` | Full-source train-set score report |
| Top-rank baseline | `18/31` | Candidate rank `0` |
| Top-score baseline | `18/31` | Highest raw candidate score |
| 4-fold state-holdout model | `22/31` | State-fold diagnostic |
| Leave-one-source model | `22/31` | Source artifacts held out |
| Leave-one-source top-rank baseline | `18/31` | Same held-out sources |
| Leave-one-source top-score baseline | `18/31` | Same held-out sources |

## Observations

- The model improves over top-rank/top-score by one state on this artifact.
- Category recovery counts `[states, oracle, model, top_rank, top_score]` were:
  `bed [7, 3, 2, 1, 1]`, `chair [8, 4, 4, 4, 4]`,
  `sofa [3, 3, 3, 3, 3]`, and `tv_monitor [5, 5, 5, 5, 5]`.
- The single model-only improvement was a `bed` state where the learned model
  selected candidate rank `4` while top-rank/top-score selected rank `0`.
- The model still missed one oracle-recoverable `bed` state, also selecting
  candidate rank `4`.
- This remains offline teleport/restore supervision. It does not measure
  online navigation, stopping, SPL, SoftSPL, or official Habitat ObjectNav
  success.
- Root cause for the invalid 4-episode active-frontier and rotation-aware
  artifacts was source-format compatibility: those traces store candidates as
  `frontier_cell` only, while the exporter previously required
  `viewpoint_cell`.
- After adding a `frontier_cell` fallback, both repaired v2 artifacts produced
  `0` invalid restores and `10/10` hidden-to-visible candidates.
- Source-diverse leave-one-source validation now holds out all five source
  artifacts. Recovery improved over simple baselines by four states:
  model `22/31` vs top-rank/top-score `18/31`, with oracle `23/31`.
- The largest held-out source is no longer a tie: model `14/23`,
  top-rank `13/23`, top-score `13/23`, oracle `15/23`; equivalently, the model
  recovers `14/15` oracle-recoverable states versus `13/15` for each simple
  baseline.

## Result

Candidate-viewpoint labels are learnable enough to justify the ranker interface
and artifact path. Source-diverse validation now gives a stronger but still
offline result: model recovery is `22/31` all current-hidden states, or `22/23`
oracle-recoverable states, versus `18/31` and `18/23` for top-rank/top-score.
This supports continuing toward online integration experiments, but it still
does not support an official ObjectNav benchmark claim yet.

## Follow-up

- Generate larger independent candidate-viewpoint artifacts so source holdouts
  are not dominated by one 20-episode source and two-state auxiliary sources.
- Test whether the learned ranker can drive an online active-perception
  selection without route followers, target-pose shortcuts, or teleportation.
- Consider recording explicit memory-anchor coordinates so candidate labels can
  compare uniform heading scans with anchor-facing observations.
