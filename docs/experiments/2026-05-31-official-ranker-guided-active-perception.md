# Experiment Report: Official Ranker-Guided Active Perception

Date: 2026-05-31
Owner: Codex
Status: Completed; negative diagnostic result

## Question

Does the source-diverse candidate-viewpoint ranker improve the online official
`memory_active_perception_frontier` policy when used to choose active
perception viewpoints?

## Hypothesis

The ranker should select better inspection candidates than the hand-scored
active-perception order, but online execution may expose a distribution mismatch
because the ranker was trained on offline teleport/restore labels.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `0f14893` plus uncommitted research changes |
| Machine | Linux mirror `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | Habitat ObjectNav HM3D `val_mini` |
| Policy | `memory_active_perception_frontier` |
| Memory prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |
| Ranker model | `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v2/model.json` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |

## Implementation

The implementation adds an optional candidate-viewpoint ranker model path to the
official evaluator. When present, the existing active-perception selector builds
online candidate rows from pre-label fields and reranks only the hand-score
top-K candidates. The no-model path is unchanged.

Important debugging note: the first online smoke scored every online frontier
candidate. Because the offline model was trained on top-5 restore-label rows,
the `candidate_rank` feature extrapolated badly and selected hand-score ranks
such as `40`, `53`, and `84`. A regression test now enforces that the online
ranker only reranks the bounded top-K set.

## Commands

Local verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

Linux focused verification:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q
```

Linux preflight:

```bash
OUT=runs/habitat_official_objectnav/ranker_guided_active_perception_preflight_20260531_v1
/home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output "$OUT" \
    --policy memory_active_perception_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_20ep_80steps_20260530_v1/memory_prior.json \
    --candidate-viewpoint-ranker-model-path runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v2/model.json \
    --max-episodes 1 \
    --max-steps 5 \
    --preflight-only
```

Linux YOLO smoke after top-K guard:

```bash
OUT=runs/habitat_official_objectnav/ranker_guided_active_perception_yolo_4ep_50steps_20260531_v2
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output "$OUT" \
    --policy memory_active_perception_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --candidate-viewpoint-ranker-model-path runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v2/model.json \
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

| Run | Success | SPL | SoftSPL | Detector target-match calls | Detector target-match detections | Notes |
|---|---:|---:|---:|---:|---:|---|
| Hand-score active perception | `0/4` | `0.0` | `0.02518699682786324` | `39` | `39` | Existing baseline on same prior |
| Rotation-aware hand-score active perception | `0/4` | `0.0` | `0.03315001996589104` | `30` | `30` | Existing stronger diagnostic smoke |
| Ranker-guided active perception v2 | `0/4` | `0.0` | `0.0009902771347611306` | `0` | `0` | New top-K-bounded learned reranker |

Ranker-guided v2 policy trace:

| Metric | Value |
|---|---:|
| Step count | `200` |
| Ranker-active steps | `49` |
| Budget stops | `4` |
| `turn_toward_memory_active_perception_frontier` decisions | `26` |
| `fallback_occupancy_frontier` decisions | `170` |
| Selected ranks | Mostly hand-score rank `4` within top-5 |

## Result

The integration works mechanically, but the first online policy result is
negative. The ranker stays inside the intended top-K candidate set after the
fix, yet it selects candidate rank `4` for most active steps and eliminates
target-match detector evidence on this four-episode smoke. This does not support
a benchmark claim or a policy improvement claim.

## Interpretation

The offline candidate-viewpoint labels are useful for supervision, but direct
deployment of the logistic offline ranker is not sufficient. The likely failure
is online/offline mismatch:

- offline labels use teleport/restore candidate viewpoint scans;
- online execution must approach through local geometry and blocked corridors;
- detector centering/reacquisition interacts with candidate choice;
- the logistic model appears too sensitive to candidate-rank distribution.

## Follow-up

- Candidate-rank ablation was run separately in
  `docs/experiments/2026-05-31-official-ranker-guided-active-perception-candidate-rank-ablation.md`.
  It preserved offline recovery but did not improve online behavior, so
  `candidate_rank` is not the root cause by itself.
- Train an online rollout value model that labels candidate choices by actual
  downstream detector evidence or official progress, not only teleport/restore
  visibility.
- Add a conservative blended selector that can deviate from hand score only
  when the ranker margin is high and the candidate is not pathologically worse
  in travel cost.
- Keep the optional ranker path for ablations, but do not use it as the default
  policy until it beats hand-score active perception in official-action smokes.
