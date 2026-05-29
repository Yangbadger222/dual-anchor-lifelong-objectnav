# Experiment Report: Habitat Navmesh Evidence Calibration Smoke

Date: 2026-05-29  
Owner: Codex  
Status: Completed smoke, not paper-ready

## Question

Does the strong-positive evidence calibration remove the balanced6
`valid_memory_wrongly_deferred` error exposed by hindsight regret, without
breaking the case where frontier is genuinely shorter than memory?

This is a narrow calibration check. It is still an oracle, option-level Habitat
navmesh-probe smoke, not an official ObjectNav benchmark or SPL result.

## Hypothesis

After calibration:

- the `sofa` row should change from `valid_memory_wrongly_deferred` to
  `memory_shorter_reused`;
- the `plant` row should remain `frontier_shorter_selected`;
- `memory_guided` total hindsight action regret should become `0` on this
  balanced6 smoke;
- aggregate action count should improve slightly over the previous evidence
  run, but this should not be treated as a robust result.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `3bff3c5` |
| Machine | Linux `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset / map | HM3D ObjectNav `val`, HM3D v0.2 scene root |
| Simulator | Habitat-Sim GreedyGeodesic option routes |
| Detector | `oracle_semantic_visibility` |
| Frontier | `navmesh_frontier` probes with fixed heading scan |
| Sensor resolution | `1280x720` |
| Challenge | `stable` |
| Reliability mode | `evidence` |
| Memory valid prior fallback | `0.5` |
| Probe budget | `frontier_probe_count=5`, `frontier_probe_heading_count=4` |

## Command

Focused Linux tests:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
git pull --ff-only origin codex/habitat-memory-lifecycle
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
```

Balanced6 calibration smoke:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
rm -rf runs/habitat_closed_loop_dual_anchor/navmesh_frontier_oracle_smoke_balanced6_evidence_calibrated_v1
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/navmesh_frontier_oracle_smoke_balanced6_evidence_calibrated_v1 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 6 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stable \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode evidence \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 5 \
  --frontier-probe-heading-count 4
```

## Selected Episodes

Candidate episode count was `652`; selected group count was `6`.

| Category | Group |
|---|---|
| `chair` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|chair|goal_object:445` |
| `plant` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|plant|goal_object:183` |
| `sofa` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|sofa|goal_object:275` |
| `toilet` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|toilet|goal_object:51` |
| `bed` | `hm3d/val/00802-wcojb4TFT35/wcojb4TFT35.basis.glb|bed|goal_object:17` |
| `tv_monitor` | `hm3d/val/00813-svBbv1Pavdk/svBbv1Pavdk.basis.glb|tv_monitor|goal_object:287` |

## Metrics

Run artifact:
`runs/habitat_closed_loop_dual_anchor/navmesh_frontier_oracle_smoke_balanced6_evidence_calibrated_v1`

| Policy | Episodes | Success | Actions | Distance | Memory reuse | Frontier selections | Hindsight action regret |
|---|---:|---:|---:|---:|---:|---:|---:|
| `memory_guided` | 6 | 6/6 | 561 | 83.772279 m | 5 | 1 | 0 |
| `naive_count` | 6 | 6/6 | 575 | 86.391889 m | 6 | 0 | 14 |
| `frontier_only` | 6 | 5/6 | 943 | 135.483215 m | 0 | 6 | 93 |

Comparison fields:

| Comparison | Action delta | Distance delta |
|---|---:|---:|
| `memory_guided` vs `frontier_only` | 382 | 51.710936 m |
| `memory_guided` vs `naive_count` | 14 | 2.619610 m |

Memory-guided buckets:

| Bucket | Count |
|---|---:|
| `memory_shorter_reused` | 4 |
| `memory_rescued_frontier_failure` | 1 |
| `frontier_shorter_selected` | 1 |

Memory-guided row audit:

| Category | Selected | Actions | Bucket | Hindsight best | Regret | Reliability |
|---|---|---:|---|---|---:|---|
| `chair` | `memory` | 69 | `memory_shorter_reused` | `memory` | 0 | `0.96`, `strong_current_evidence_floor` |
| `plant` | `frontier` | 125 | `frontier_shorter_selected` | `frontier` | 0 | `0.96`, `strong_current_evidence_floor` |
| `sofa` | `memory` | 98 | `memory_shorter_reused` | `memory` | 0 | `0.96`, `strong_current_evidence_floor` |
| `toilet` | `memory` | 179 | `memory_rescued_frontier_failure` | `memory` | 0 | `0.96`, `strong_current_evidence_floor` |
| `bed` | `memory` | 44 | `memory_shorter_reused` | `memory` | 0 | `0.96`, `strong_current_evidence_floor` |
| `tv_monitor` | `memory` | 46 | `memory_shorter_reused` | `memory` | 0 | `0.96`, `strong_current_evidence_floor` |

## Observations

- The targeted `sofa` row changed from the previous `valid_memory_wrongly_deferred`
  bucket to `memory_shorter_reused`.
- The targeted `plant` row still selected frontier and kept zero hindsight
  regret.
- `memory_guided` improved from the previous balanced6 evidence run by 4
  actions (`565` to `561`) and reduced its hindsight action regret to `0`.
- All six memory-guided reliability estimates hit the same strong-positive
  floor. That is useful for this calibration smoke, but it also means the run
  is not evidence that the estimator is well calibrated across weaker evidence,
  detector noise, or held-out scenes.

## Result

The calibration fixed the known balanced6 hindsight-regret error in this oracle
navmesh smoke. It also preserved the shorter-frontier `plant` decision. This is
a useful guardrail for the expected-utility policy, but the effect size is small
and the evidence source is still oracle/candidate-view based.

Do not use this as a paper claim. Use it as a diagnostic step before replacing
the heuristic floor with detector/per-action evidence or learned calibration and
before running larger held-out Habitat suites.

## Follow-up

- Run the same audit with Grounding-DINO candidate-view evidence.
- Add weaker-evidence and stale-memory calibration cases so the strong-positive
  floor does not hide harmful memory reuse.
- Move reliability evidence to per-action detector observations.
- Scale beyond balanced6 and report confidence intervals only after a true
  occupancy/frontier baseline exists.
