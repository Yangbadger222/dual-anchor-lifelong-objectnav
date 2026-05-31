# Experiment Report: Official View-Candidate Recall Dataset

Date: 2026-05-30
Owner: Codex
Status: Candidate export implemented; counterfactual labels intentionally unavailable

## Question

Can existing official active-perception traces expose candidate viewpoint sets
for learned view-value research without falsely treating unexecuted candidates
as negative examples?

## Hypothesis

The active-perception traces contain enough `memory_prior.top_candidates`
metadata to export a candidate dataset. Only the selected candidate should
receive an observed future detector-recall label; unselected candidates should
remain explicitly unobserved until we collect real counterfactual rollouts.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted research workspace |
| Machine | Local macOS plus Linux mirror `badger@100.88.131.52` |
| Python env | Linux conda env `habitat` |
| Source traces | Active-perception YOLO official policy/detector traces |
| Horizon | `5` future same-episode steps |

## Commands

Local/targeted verification during implementation:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

Linux export pattern:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

python -m objectnav_core.cli.export_habitat_official_view_candidate_dataset \
  runs/habitat_official_objectnav/<source-run>/policy_trace.json \
  --detector-trace runs/habitat_official_objectnav/<source-run>/detector_trace.json \
  --output runs/habitat_official_objectnav/<candidate-output>/dataset.json \
  --csv-output runs/habitat_official_objectnav/<candidate-output>/candidates.csv \
  --source-run-id <source-run> \
  --horizon-steps 5
```

## Metrics

| Dataset | States with candidates | Candidate rows | Selected labels | Positive selected labels | Unobserved candidates |
|---|---:|---:|---:|---:|---:|
| active original | `25` | `125` | `25` | `8` | `100` |
| active rotation-aware | `29` | `145` | `29` | `9` | `116` |
| active path-aware | `35` | `175` | `35` | `8` | `140` |
| active viewpoint scan | `44` | `220` | `44` | `4` | `176` |
| total | `133` | `665` | `133` | `29` | `532` |

Selected candidate rank was always `0` in these traces. This means the online
handcrafted scorer always executed its top-ranked candidate, so lower-ranked
candidates remain counterfactual and cannot be labeled as failures.

Selected-candidate median diagnostics:

| Dataset | Positive score median | Negative score median | Positive travel median | Negative travel median | Interpretation |
|---|---:|---:|---:|---:|---|
| active original | `0.0266` | `-0.0395` | `0.5` | `0.7906` | weak positive separation |
| active rotation-aware | `0.4309` | `0.4124` | `0.5` | `2.1506` | travel distance helps |
| active path-aware | `0.4953` | `0.3667` | `0.375` | `3.0` | best score/travel separation |
| active viewpoint scan | `0.4701` | `0.5075` | `0.875` | `0.25` | handcrafted score inverted |

## Observations

- The exporter now preserves candidate coverage without inventing labels for
  unexecuted options.
- The data confirm the current limitation: top-5 candidate lists are available,
  but only the selected top-ranked candidate has an observed future outcome.
- The viewpoint-scan trace again looks unhealthy. Its selected positive rows
  have lower median handcrafted score and higher median travel distance than
  selected negatives.
- A publishable candidate ranker needs either intervention data or simulator
  rollouts from saved states so unselected candidates can receive real labels.

## Result

This slice produces the right audit artifact for candidate-view learning, but
it also proves that existing logs alone are insufficient for direct
counterfactual candidate supervision. The next algorithmic step should collect
or simulate candidate rollouts rather than training on unselected candidates as
if they were negatives.

## Follow-up

- Add short-horizon candidate rollout collection in simulation for selected
  saved states, evaluating multiple top candidates from the same memory state.
- Train candidate value only on candidates with real observed rollout labels.
- Use this candidate-rollout dataset as the gate before replacing the online
  active-perception scorer.
