# Experiment Report: Candidate-Rank Ablation for Ranker-Guided Active Perception

Date: 2026-05-31
Owner: Codex
Status: Completed; negative diagnostic result

## Question

Was the poor online transfer of the source-diverse candidate-viewpoint ranker
mainly caused by the `candidate_rank` feature?

## Hypothesis

The full ranker selected hand-score rank `4` on nearly all active online steps.
If this was mostly caused by the learned `candidate_rank` coefficient, retraining
without `candidate_rank` should preserve offline recovery while making online
candidate choices less biased toward hand-score rank `4`.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `0f14893` plus uncommitted research changes |
| Machine | Linux mirror `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | Five source-diverse candidate-viewpoint restore artifacts from 2026-05-31 |
| Policy | `memory_active_perception_frontier` |
| Memory prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |
| Full ranker baseline | `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v2/model.json` |
| Ablation ranker | `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/model.json` |

## Implementation

The ranker trainer now accepts an explicit feature exclusion list:

```bash
--exclude-feature candidate_rank
```

The exclusion is recorded in the model artifact under
`dataset.training_filter.excluded_feature_names`. The online evaluator did not
need policy changes because it consumes the model artifact's feature list.

## Commands

Focused tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q'
```

Offline ablation training and evaluation:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_active_frontier_4ep_yolo_20260531_v2/dataset.json \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_rotation_aware_4ep_yolo_20260531_v2/dataset.json \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_path_aware_4ep_yolo_20260531_v1/dataset.json \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_viewpoint_scan_4ep_yolo_20260531_v1/dataset.json \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1/dataset.json \
    --output runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/model.json \
    --scores-output runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/scores.json \
    --csv-output runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/scores.csv \
    --state-fold-output runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/state_folds.json \
    --leave-one-source-output runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/leave_one_source.json \
    --fold-count 4 \
    --exclude-feature candidate_rank
```

Online smoke:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/ranker_guided_active_perception_no_candidate_rank_yolo_4ep_50steps_20260531_v1 \
    --policy memory_active_perception_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --candidate-viewpoint-ranker-model-path runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/model.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313
```

## Metrics

### Offline Ranker

| Model | Feature Count | Candidate Rank Feature | ROC-AUC | Model / Oracle | Top-Rank | Top-Score | Leave-One-Source |
|---|---:|---|---:|---:|---:|---:|---:|
| Full source-diverse v2 | `49` | yes | `0.949131` | `22/23` oracle-recoverable | `18/23` | `18/23` | `22/31` all states |
| No `candidate_rank` | `48` | no | `0.952830` | `22/23` oracle-recoverable | `18/23` | `18/23` | `22/31` all states |

Offline selected-rank distribution changed:

| Model | Rank 0 | Rank 2 | Rank 3 | Rank 4 |
|---|---:|---:|---:|---:|
| Full source-diverse v2 | `1` | `0` | `4` | `26` |
| No `candidate_rank` | `2` | `7` | `10` | `12` |

### Online Smoke

| Run | Success | SPL | SoftSPL | Target-Match Calls | Ranker-Active Steps | Online Selected Hand Ranks |
|---|---:|---:|---:|---:|---:|---|
| Full source-diverse v2 | `0/4` | `0.0` | `0.0009902771347611306` | `0` | `49` | rank `4` on `48/49`, rank `3` on `1/49` |
| No `candidate_rank` | `0/4` | `0.0` | `0.0009902771347611306` | `0` | `49` | rank `4` on `48/49`, rank `2` on `1/49` |

## Result

Removing `candidate_rank` does not fix the online transfer failure. Offline
source-held-out recovery is unchanged, but online behavior remains essentially
the same: no target-match detector evidence and almost every active-perception
step selects hand-score rank `4`.

## Interpretation

`candidate_rank` was a visible symptom, not the root cause. The no-rank model
still learns preferences that favor the same online candidates, including
positive weights on path/travel distance and geometry/state features that do
not represent downstream action utility. The next model should be trained on an
online rollout target such as detector evidence gain, official progress gain, or
short-horizon success proxy rather than offline teleport/restore visibility.

## Follow-Up

- Keep the no-`candidate_rank` model as an ablation artifact, not a policy win.
- Do not make the offline ranker the default active-perception selector.
- Build the next learning target around online downstream utility, with
  source/state grouping to prevent leakage.

## Controller-Mismatch Follow-Up

After this ablation, the online active-perception controller was changed to keep
a short-lived commitment to the selected viewpoint and to scan once before
abandoning a blocked active-perception target. This recovered some detector
evidence for the no-rank ranker smoke but did not isolate a learned-ranker
benefit:

| Run | Success | SPL | SoftSPL | Target-Match Calls | Target-Match Detections | Ranker-Active Steps |
|---|---:|---:|---:|---:|---:|---:|
| No-rank ranker, sticky only | `0/4` | `0.0` | `0.0009902771347611306` | `0` | `0` | `49` |
| No-rank ranker, sticky plus blocked scan | `0/4` | `0.0` | `0.02518699682786324` | `4` | `4` | `44` |
| Hand-score, sticky plus blocked scan | `0/4` | `0.0` | `0.02518699682786324` | `4` | `4` | `0` |

The evidence recovery is therefore attributable to controller alignment rather
than the no-rank learned selector. The standalone controller report is
`docs/experiments/2026-05-31-official-active-perception-controller-mismatch.md`.
