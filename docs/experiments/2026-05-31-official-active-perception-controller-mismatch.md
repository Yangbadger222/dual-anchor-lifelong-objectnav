# Experiment Report: Official Active-Perception Controller Mismatch

Date: 2026-05-31
Owner: Codex
Status: Completed; partial controller recovery, no ranker win

## Question

Is the online failure of the candidate-viewpoint ranker caused mainly by a bad
learned candidate order, or by mismatch between offline candidate labels and
the online active-perception controller that executes the chosen viewpoint?

## Hypothesis

The offline restore-label branches may be recoverable because their continuation
controller scans locally after reaching or failing to reach a candidate
viewpoint. If the online policy reselects every step or abandons a blocked
active-perception target before scanning, it can fail even when the selected
candidate has useful short-horizon detector evidence.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `0f14893` plus uncommitted research changes |
| Machine | Linux mirror `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | Habitat ObjectNav HM3D `val_mini` |
| Policy | `memory_active_perception_frontier` |
| Memory prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |
| No-rank model | `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/model.json` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |

## Implementation

Two controller changes were added to the online active-perception option:

- Short-lived viewpoint commitment: after a viewpoint is selected, subsequent
  policy calls keep the same `viewpoint_cell` while it remains available and
  the viewpoint has not completed its scan.
- Blocked-target scan: when the selected active-perception target is aligned
  but center depth blocks forward motion, the policy performs one bounded local
  scan before clearing the target and falling back to occupancy exploration.

These changes do not add oracle target pose, teleportation, semantic labels, or
persistent `habitat_world` memory. The policy still acts through official
Habitat discrete actions and episode-relative anchors.

## Commands

Focused regression tests added for the controller behavior:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py -q
```

Linux no-rank ranker smoke with sticky commitment only:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/ranker_guided_active_perception_no_candidate_rank_sticky_yolo_4ep_50steps_20260531_v1 \
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

Linux no-rank ranker smoke with sticky commitment plus blocked-target scan:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/ranker_guided_active_perception_no_candidate_rank_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1 \
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

Matched hand-score smoke with the same sticky plus blocked-scan controller:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/memory_active_perception_frontier_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1 \
    --policy memory_active_perception_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
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

Metrics below were read from each artifact's `summary.json` and
`policy_trace.json`.

## Metrics

| Run | Success | SPL | SoftSPL | Mean Distance | Target-Match Calls | Target-Match Detections | Ranker-Active Steps | Key Trace |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| No-rank ranker, no controller fix | `0/4` | `0.0` | `0.0009902771347611306` | `5.880594372749329` | `0` | `0` | `49` | selected rank `4` on `48/49` active steps |
| No-rank ranker, sticky only | `0/4` | `0.0` | `0.0009902771347611306` | `5.880594372749329` | `0` | `0` | `49` | commitment continued, still no detector evidence |
| No-rank ranker, sticky plus blocked scan | `0/4` | `0.0` | `0.02518699682786324` | `5.697803378105164` | `4` | `4` | `44` | `20` orient-anchor steps, `20` scan-anchor steps, `1` blocked-scan step |
| Hand-score, sticky plus blocked scan | `0/4` | `0.0` | `0.02518699682786324` | `5.697803378105164` | `4` | `4` | `0` | same official metrics and target evidence as no-rank ranker |

## Result

The blocked-target scan is the first part of this slice that changed online
detector evidence: target-match calls increased from `0` to `4` and SoftSPL
rose from `0.0009902771347611306` to `0.02518699682786324`. However, the matched
no-ranker hand-score run produced the same official metrics and target-match
counts under the same controller.

This is not a benchmark win. Success remained `0/4` and SPL remained `0.0`.
It is also not evidence that the learned ranker helps online. The improvement
comes from controller alignment.

## Interpretation

The current offline candidate-viewpoint ranker is not the limiting factor in
this smoke. The offline branch labeler used a follow-up behavior that was more
forgiving than the online active-perception controller. Once the online
controller was changed to pursue an option and locally scan before blocked
fallback, both the learned no-rank selector and the hand-score selector reached
the same partial recovery.

The next learning target should therefore label candidate options under the
actual online continuation controller. Good candidates should be measured by
downstream detector target evidence, official progress, or short-horizon option
value, not by teleport/restore visibility alone.

## Follow-Up

- Keep sticky commitment and blocked-target scan as controller-alignment
  behavior only if focused tests continue to pass.
- Do not claim learned-ranker improvement from the current smoke.
- Build an online option-value dataset using the same active-perception
  continuation that the policy will execute.
- Keep grouped splits by source artifact and restored state so the next model
  does not leak across near-duplicate branch labels.
