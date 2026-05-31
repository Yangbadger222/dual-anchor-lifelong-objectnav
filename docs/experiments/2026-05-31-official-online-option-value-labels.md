# Experiment Report: Official Online Option-Value Labels

Date: 2026-05-31
Owner: Codex
Status: Completed; diagnostic only; not benchmark-valid

## Question

Can active-perception candidates be labeled by their actual short-horizon
downstream detector value under the same sticky plus blocked-scan option
controller used online, and does a tiny model trained on those labels move the
matched online smoke beyond the hand-score selector?

## Hypothesis

Teleport/restore candidate-viewpoint labels were too optimistic for direct
online policy transfer. If candidate rows are instead labeled by target evidence
within a real option rollout using live GPS/compass/depth, the learned selector
should prefer the candidates that the online continuation can actually exploit.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `0f14893` plus uncommitted research changes |
| Machine | Linux mirror `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | Habitat ObjectNav HM3D `val_mini` |
| Simulator | Habitat-Lab official ObjectNav config |
| Policy | `memory_active_perception_frontier` |
| Memory prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |
| Source trace | `runs/habitat_official_objectnav/memory_active_perception_frontier_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1/policy_trace.json` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Seed | `313` |

## Implementation

The exporter replays a policy trace to a candidate-bearing state, expands the
top-K active-perception candidates, forces each candidate option, updates pose
from live observations at each action, and records target detector evidence
within the option rollout.

Main files:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`
- `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_viewpoint_ranker_model.py`
- `src/objectnav_core/objectnav_core/cli/train_habitat_official_candidate_viewpoint_ranker.py`
- `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- `src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py`

## Commands

Focused tests and syntax checks:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_viewpoint_ranker_model.py \
  src/objectnav_core/objectnav_core/cli/train_habitat_official_candidate_viewpoint_ranker.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py
```

Linux option-value export:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset \
    runs/habitat_official_objectnav/memory_active_perception_frontier_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1/policy_trace.json \
    --output runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1/dataset.json \
    --csv-output runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1/labels.csv \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-states 8 \
    --state-sampling active_phase_path \
    --candidates-per-state 5 \
    --option-horizon-steps 8 \
    --option-scan-steps 4 \
    --seed 313
```

Tiny option-value ranker:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
    runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1/dataset.json \
    --label hidden_to_visible_within_option_rollout \
    --output runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/model.json \
    --scores-output runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/scores.json \
    --csv-output runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/scores.csv \
    --state-fold-output runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/state_folds.json \
    --fold-count 4
```

Matched online diagnostic:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/option_value_ranker_guided_active_perception_yolo_4ep_50steps_20260531_v1 \
    --policy memory_active_perception_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --candidate-viewpoint-ranker-model-path runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/model.json \
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

### Option-Value Dataset

Artifact:
`runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1`

| Metric | Value | Notes |
|---|---:|---|
| Candidate states | `8` | All selected from episode index `2` active-perception path states |
| Candidate options | `40` | Top `5` candidates per state |
| Invalid options | `0` | No invalid candidate poses or replay failures |
| Hidden-to-visible positives | `16` | `40%` positive row rate |
| Oracle-recoverable states | `8/8` | At least one positive candidate per state |
| Top-rank recovered states | `0/8` | Hand-score rank `0` was never positive |
| Top-score recovered states | `0/8` | Same outcome as top-rank in this slice |
| Positive rank distribution | rank `2`: `8`, rank `3`: `8` | Positives were consistently below the hand-score top choice |

### Tiny Same-Trace Ranker

Artifact:
`runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2`

| Metric | Value | Notes |
|---|---:|---|
| Features | `44` | Logistic candidate-viewpoint ranker |
| Training candidates | `40` | Same artifact as above |
| Positives / negatives | `16 / 24` | Current-hidden rows only |
| Training ROC-AUC | `1.0` | Same-trace diagnostic only |
| State-fold recovery | model `8/8`, oracle `8/8`, top-rank `0/8`, top-score `0/8` | Tiny folds, not independent evidence |
| Model selected ranks | rank `3` on `8/8` scored states | Learns away from hand-score top-rank |

### Matched Online Smoke

Artifact:
`runs/habitat_official_objectnav/option_value_ranker_guided_active_perception_yolo_4ep_50steps_20260531_v1`

| Run | Success | SPL | SoftSPL | Target-Match Calls | Target-Match Detections |
|---|---:|---:|---:|---:|---:|
| Hand-score, sticky plus blocked scan | `0/4` | `0.0` | `0.02518699682786324` | `4` | `4` |
| No-`candidate_rank` ranker, sticky plus blocked scan | `0/4` | `0.0` | `0.02518699682786324` | `4` | `4` |
| Option-value ranker, sticky plus blocked scan | `0/4` | `0.0` | `0.02518699682786324` | `4` | `4` |

The option-value model was active online: it selected hand-score rank `3` on
`40/44` active-selection steps, rank `2` on `2/44`, and rank `4` on `2/44`.

## Observations

- The new label family is sharply different from hand-score top-rank on this
  slice: all recoverable candidates are at ranks `2` or `3`.
- The option-value model learned that tiny target and changed online candidate
  choices accordingly.
- The online diagnostic did not improve official success, SPL, SoftSPL, or
  target-match detector evidence over the matched hand-score controller.
- The identical online metrics suggest that this four-episode failure is no
  longer primarily explained by the first candidate choice. The remaining
  bottleneck is likely the continuation after selecting a useful candidate:
  local control, detector reacquisition, scan/stop timing, or the tiny and
  same-trace nature of the model.

## Result

The option-value exporter is useful and correctly exposes a supervision signal
that top-rank hand-score misses. The first same-trace model is not an online
policy improvement: it changes selected ranks but matches hand-score outcomes
on the diagnostic smoke.

This result should be framed as a new supervision substrate and a negative
policy-transfer diagnostic, not as benchmark evidence.

## Follow-Up

- Expand option-value export beyond one episode/source and evaluate with
  source/state separation before training another online selector.
- Add richer targets such as time-discounted detector evidence, official
  distance-progress delta, or stop-success eligibility within the option.
- Inspect the active continuation after rank `2/3` selection, especially
  detector reacquisition and stop timing.
- Keep official Habitat metrics as the only basis for paper or benchmark claims.
