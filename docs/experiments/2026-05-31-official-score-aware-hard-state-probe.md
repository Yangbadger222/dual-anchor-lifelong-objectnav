# Experiment Report: Official Score-Aware Hard-State Probe

Date: 2026-05-31
Owner: Codex
Status: Completed diagnostic; no benchmark claim

## Question

If candidate-rollout export samples high top-candidate-score states before
applying category caps, do `chair` and `bed` become recoverable under the
repeat-first action-matrix label?

## Hypothesis

If the `chair` and `bed` failures in the category-balanced probe were mostly
caused by first-N state selection, then `top_score_desc` sampling should select
stronger states and yield at least some repeat-first positive rollouts for those
categories. If they still do not recover, the bottleneck is more likely the
current label/action design or the underlying candidate-viewpoint quality.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Linux mirror, `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | HM3D ObjectNav `val_mini` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Source trace | `runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json` |
| Rollout labels | Repeat-first action matrix, horizon `5`, actions `turn_left,turn_right,move_forward` |
| State sampling | `top_score_desc`, cap `8` states per category |

## Command

Trace-only selection preview:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
python3 - <<'PY'
import json
from collections import Counter

path = "runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json"
with open(path, encoding="utf-8") as f:
    payload = json.load(f)

rows = []
for order, step in enumerate(payload.get("steps", [])):
    prior = step.get("memory_prior") if isinstance(step, dict) else None
    if not isinstance(prior, dict):
        continue
    candidates = prior.get("top_candidates")
    if not isinstance(candidates, list) or not candidates:
        continue
    try:
        score = float(candidates[0].get("score"))
    except Exception:
        score = None
    rows.append((score is None, -(score or 0.0), order, step.get("target_category")))

print(len(rows), Counter(row[3] for row in rows))
PY
```

Score-aware branch rollout:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core
export HABITAT_SIM_LOG=quiet
export MAGNUM_LOG=quiet
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

OUT=runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_score_top_max8cat_yolo_20260531_v1
mkdir -p "$OUT"

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json \
  --output "$OUT/dataset.json" \
  --csv-output "$OUT/rollouts.csv" \
  --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
  --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --split val_mini \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor \
  --branch-actions turn_left,turn_right,move_forward \
  --branch-followup-policy repeat_first_action \
  --rollout-horizon-steps 5 \
  --max-states-per-category 8 \
  --state-sampling top_score_desc

python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
  "$OUT/dataset.json" \
  --output "$OUT/report.json" \
  --csv-output "$OUT/states.csv"

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  "$OUT/report.json" \
  --output "$OUT/hard_states.json" \
  --csv-output "$OUT/hard_states.csv"

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  "$OUT/report.json" \
  --output "$OUT/hard_or_tie_states.json" \
  --csv-output "$OUT/hard_or_tie_states.csv" \
  --include-baseline-ties
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Exporter candidate-bearing states in trace | `879` | `chair 477`, `bed 238`, `tv_monitor 159`, `sofa 5` |
| Selected states | `29` | `tv_monitor 8`, `chair 8`, `bed 8`, `sofa 5` |
| Selected top-score examples | `sofa 0.550`, `tv_monitor 0.433`, `chair 0.0226`, `bed 0.00000638` | Best selected top score by category |
| Rollout dataset | `87` rollouts | `18` positives, `0` invalid |
| Positive branch rollouts | `sofa 8`, `tv_monitor 10` | `chair` and `bed` had `0` |
| Current-hidden report | `28` states, `84` action rows | One selected state was current-visible and skipped |
| Current-hidden categories | `tv_monitor 8`, `chair 8`, `bed 8`, `sofa 4` | Report states only |
| Oracle-recovered states | `12/28` | `tv_monitor 8`, `sofa 4` |
| Strict fastest actions | `turn_left 6`, `move_forward 3`, `turn_right 1` | Plus `2` fastest-action ties |
| Always-left-not-fastest hard states | `5/28` | `sofa 3`, `tv_monitor 2` |
| Hard-or-tie states | `6/28` | `sofa 4`, `tv_monitor 2` |

## Observations

- The new sampling mode behaves as intended: the dataset metadata records
  `candidate_state_sampling=top_score_desc`, and selected states follow the
  descending top-score order before category caps.
- Score-aware selection did not rescue `chair` or `bed`. Even their best
  selected top-candidate scores are very small relative to `sofa` and
  `tv_monitor`, and neither category produced a repeat-first positive rollout.
- Recovered and hard states remain confined to `sofa` and `tv_monitor`. The
  specific hard-state count changed because this probe uses an `8` state cap
  rather than the previous `12` cap, but the category conclusion is unchanged.
- The exporter still pays the known cost of creating a fresh Habitat env per
  branch. This is acceptable for capped diagnostics and not acceptable for
  large-scale data generation.

## Result

The score-aware exporter control works, but the probe is negative for the
research question. Higher top-candidate-score sampling does not make `chair` or
`bed` recoverable under the current repeat-first macro-action labels. This
strengthens the case that the next step should redesign labels/actions rather
than tune another utility model on the same supervision.

## Follow-up

- Add phase-aware diagnostics around `orient_memory_anchor_from_active_viewpoint`
  and `scan_memory_anchor_from_active_viewpoint` states.
- Prototype exact state-restore or candidate-viewpoint labels so supervision can
  test whether the selected viewpoint itself is useful, not just whether a
  repeated primitive action recovers visibility.
- Inspect `chair` and `bed` detector visibility around the source trace to
  separate detector misses from geometry/action-label failures.
