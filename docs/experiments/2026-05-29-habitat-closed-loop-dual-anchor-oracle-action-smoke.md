# Experiment Report: Habitat Closed-Loop Dual-Anchor Oracle Action Smoke

Date: 2026-05-29  
Owner: Codex  
Status: Partial evidence, not paper-ready

## Question

Can the Habitat closed-loop runner execute real HM3D action routes while
exercising memory-vs-frontier decisions, dual-anchor frame restart metadata,
ambiguous matching, and repeated stale repair?

## Hypothesis

A memory-guided policy should reduce repeated exploration when the remembered
anchor is useful, defer to frontier when matching is ambiguous or stale-risk is
not worth probing, and beat a positive-only `naive_count` baseline after stale
repair. In a stable scene, memory-guided may tie `naive_count`; that tie is
expected because no stale/ambiguity behavior is needed.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `7c1acf2` |
| Machine | Linux `badger@100.88.131.52` |
| Dataset / map | HM3D ObjectNav `val`, full HM3D scene root |
| Simulator / robot | Habitat-Sim GreedyGeodesic action routes |
| Detector | Oracle semantic visibility smoke |
| Sensor resolution | `1280x720` |
| Policies | `memory_guided`, `frontier_only`, `naive_count` |
| Challenge modes | `stable`, `ambiguous`, `stale_proxy` |
| Expected-utility prior | `memory_valid_prior=0.5` unless noted |

## Main Commands

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
```

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/oracle_action_stale_proxy_repeats2_balanced6_eu_p05_v1 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 6 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stale_proxy \
  --query-repeats 2 \
  --memory-valid-prior 0.5
```

## Selected Episodes

Balanced `max_groups=6` now selects one group per category before taking
duplicate categories:

| Category | Group |
|---|---|
| `chair` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|chair|goal_object:445` |
| `plant` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|plant|goal_object:183` |
| `sofa` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|sofa|goal_object:275` |
| `toilet` | `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|toilet|goal_object:51` |
| `bed` | `hm3d/val/00802-wcojb4TFT35/wcojb4TFT35.basis.glb|bed|goal_object:17` |
| `tv_monitor` | `hm3d/val/00813-svBbv1Pavdk/svBbv1Pavdk.basis.glb|tv_monitor|goal_object:287` |

Candidate episode count was `652`; selected group count was `6`.

## Results

### Stable Balanced6 Sanity Check

Run: `runs/habitat_closed_loop_dual_anchor/oracle_action_stable_balanced6_eu_p05_v1`

| Policy | Episodes | Success | Actions | Distance |
|---|---:|---:|---:|---:|
| `memory_guided` | 6 | 6/6 | 575 | 86.391889 m |
| `naive_count` | 6 | 6/6 | 575 | 86.391889 m |
| `frontier_only` | 6 | 6/6 | 1311 | 183.893982 m |

Stable interpretation: memory routes save `736` actions and `97.502093 m`
versus frontier. `memory_guided` ties `naive_count`, which is expected when
there is no ambiguity or stale object.

### Repeated Stale Balanced6 With Expected Utility

Run: `runs/habitat_closed_loop_dual_anchor/oracle_action_stale_proxy_repeats2_balanced6_eu_p05_v1`

| Policy | Episodes | Success | Actions | Distance | Memory reuse | Frontier selections |
|---|---:|---:|---:|---:|---:|---:|
| `memory_guided` | 12 | 12/12 | 2020 | 280.893940 m | 6 | 6 |
| `naive_count` | 12 | 12/12 | 4148 | 581.317722 m | 0 | 12 |
| `frontier_only` | 12 | 12/12 | 3074 | 424.852192 m | 0 | 12 |

Memory-guided deltas:

| Comparison | Action delta | Distance delta |
|---|---:|---:|
| vs `frontier_only` | +1054 | +143.958252 m |
| vs `naive_count` | +2128 | +300.423782 m |

Group action totals:

| Group category | `memory_guided` | `frontier_only` | `naive_count` |
|---|---:|---:|---:|
| `chair` | 509 | 710 | 880 |
| `plant` | 341 | 404 | 1094 |
| `sofa` | 365 | 936 | 534 |
| `toilet` | 488 | 618 | 1086 |
| `bed` | 88 | 88 | 188 |
| `tv_monitor` | 229 | 318 | 366 |

Decision trace counts for `memory_guided`: `accepted=6`,
`expected_utility_frontier=3`, `no_current_observation=3`.

## Debug History And Negative Results

- Before direct repaired-route accounting, stale repeat produced
  `memory_guided=545`, `frontier_only=476`, `naive_count=614` on the single
  plant group. That was a useful negative result, but root-cause analysis found
  the repaired anchor was incorrectly charged as a frontier proxy route.
- After fixing direct repaired memory, the single plant stale repeat became
  `memory_guided=446`, `frontier_only=476`, `naive_count=614`.
- On unbalanced max6 without expected utility, memory-guided beat naive on all
  groups but still lost to frontier in several groups. This showed stale-risk
  decision logic was necessary.
- With expected utility and balanced selection, memory-guided no longer blindly
  probes high-risk stale memories. It ties or beats frontier on all six selected
  categories in this oracle/action smoke.
- Sensitivity check: `memory_valid_prior=0.8` was worse than `0.5` on max6
  (`memory_guided=2151` actions vs `1917`) because it over-trusted the toilet
  stale probe. This is a sign the prior should eventually be learned or derived
  from evidence, not hand-picked.

## Current Interpretation

This is the strongest simulation evidence so far for the revised direction:
closed-loop option decisions are executed as Habitat action routes; session
restart metadata is recorded; stale repair changes future behavior; and the
comparison includes both exploration and positive-only counting baselines.

It is not yet a paper claim:

- It uses oracle semantic visibility, not Grounding-DINO per-step perception.
- Frontier is still a deterministic search proxy, not a true occupancy frontier
  policy.
- `stale_proxy` is protocol-level stale simulation, not physical object
  relocation/removal in Habitat.
- The runner reports action-route smoke metrics, not official Habitat SPL.
- The selected six groups are balanced by category but still small.

## Next Steps

1. Replace oracle visibility with Grounding-DINO observations in the closed-loop
   runner.
2. Add real frontier mapping/exploration instead of search-proxy waypoints.
3. Implement natural Habitat object relocation/removal or a clearly documented
   semantic-object hide/replace protocol.
4. Scale balanced runs beyond six groups and report confidence intervals.
5. Learn or estimate `memory_valid_prior` from detector evidence, covariance,
   object class, and session age instead of fixing it by hand.
