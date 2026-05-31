# Experiment Report: Habitat Official ObjectNav Measure Adapter Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed protocol smoke, not a policy result

## Question

Can the project instantiate the official Habitat-Lab ObjectNav task and persist
`success`, `spl`, `soft_spl`, and `distance_to_goal` from
`habitat.Env.get_metrics()` instead of internal replay accounting?

## Environment

| Item | Value |
|---|---|
| Branch | `codex/habitat-memory-lifecycle` |
| Machine | `badger-linux` |
| Conda env | `habitat` |
| Habitat-Lab | `0.3.3` |
| Config | `third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml` |
| Dataset | HM3D ObjectNav `val_mini` |
| Scene root | `datasets/habitat/scene_datasets/hm3d` |
| Official max steps | `500` for default smoke; `5` for short random smoke |
| Official measures | `success`, `spl`, `soft_spl`, `distance_to_goal`, `distance_to_goal_reward` |

## Commands

Focused Linux tests:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

Validated preflight:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/preflight_valmini_20260530_v1 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy noop \
    --max-episodes 1 \
    --preflight-only \
    --validate-habitat
```

One-episode `noop` official smoke:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/noop_valmini_1ep_20260530_v1 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy noop \
    --max-episodes 1 \
    --validate-habitat
```

Short `random` official smoke:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/random_valmini_1ep_5steps_20260530_v1 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy random \
    --max-episodes 1 \
    --max-steps 5 \
    --validate-habitat
```

## Artifacts

- `runs/habitat_official_objectnav/preflight_valmini_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/preflight_valmini_20260530_v1/protocol_manifest.json`
- `runs/habitat_official_objectnav/noop_valmini_1ep_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/noop_valmini_1ep_20260530_v1/episodes.csv`
- `runs/habitat_official_objectnav/random_valmini_1ep_5steps_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/random_valmini_1ep_5steps_20260530_v1/episodes.csv`

## Results

| Run | Policy | Episodes | Success | SPL | SoftSPL | Distance to goal | Action count |
|---|---|---:|---:|---:|---:|---:|---:|
| `noop_valmini_1ep_20260530_v1` | `noop` | `1` | `0.0` | `0.0` | `0.0` | `8.412616729736328` | `1` |
| `random_valmini_1ep_5steps_20260530_v1` | `random` | `1` | `0.0` | `0.0` | `0.0007339080957522448` | `8.406442642211914` | `5` |

The manifest confirms Habitat-Lab `0.3.3`, task type `ObjectNav-v1`, dataset
type `ObjectNav-v1`, split `val_mini`, and measurements:

- `distance_to_goal`
- `success`
- `spl`
- `soft_spl`
- `distance_to_goal_reward`

## Interpretation

The official metric adapter is now mechanically working. It loads official
HM3D ObjectNav episodes through `habitat.Env`, steps discrete Habitat actions,
and copies metrics from `env.get_metrics()`.

This is not a benchmark result. `noop` and short `random` are trivial protocol
smokes and are explicitly marked invalid for benchmark claims in the protocol
manifest.

## Follow-up

- Port a target-agnostic `frontier_only` action policy into the official step
  loop.
- Then port `dual_anchor_memory` without using route-follower shortcuts or
  target-pose oracle actions.
- Keep lifecycle relocation experiments as a separate evidence track from
  official single-episode ObjectNav SR/SPL.

## Addendum: Target-Agnostic Frontier Baseline Smoke

After the initial protocol smoke, the adapter was extended with a first
`frontier_only` policy. This policy is target-agnostic and uses only the current
depth observation:

- move forward when the center depth window is clear;
- keep turning left when blocked;
- stop on the final budgeted step;
- no target pose, route follower, semantic oracle, detector-positive shortcut,
  or teleportation.

Two implementation bugs were found and fixed during Linux smoke testing:

1. Habitat official depth observations are normalized to `0.0..1.0`, while the
   first local policy assumed meter-scale depth.
2. Alternating `turn_left` and `turn_right` actions caused blocked episodes to
   oscillate in place.

Regression tests now cover normalized depth and sustained blocked turning.

Final frontier smoke command:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/frontier_only_valmini_3ep_200steps_turnfix_20260530_v1 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy frontier_only \
    --max-episodes 3 \
    --max-steps 200 \
    --validate-habitat
```

Artifacts:

- `runs/habitat_official_objectnav/frontier_only_valmini_3ep_200steps_20260530_v1`
- `runs/habitat_official_objectnav/frontier_only_valmini_3ep_200steps_depthfix_20260530_v1`
- `runs/habitat_official_objectnav/frontier_only_valmini_3ep_200steps_turnfix_20260530_v1`

Final frontier result:

| Run | Policy | Episodes | Success | SPL | SoftSPL | Mean distance to goal |
|---|---|---:|---:|---:|---:|---:|
| `frontier_only_valmini_3ep_200steps_turnfix_20260530_v1` | `frontier_only` | `3` | `0.0` | `0.0` | `0.0013203695130148407` | `6.915587266286214` |

Interpretation:

The official loop can now run a nontrivial, target-agnostic baseline policy, but
this first depth-reactive baseline is intentionally weak. It is useful as a
protocol scaffold and failure probe, not as a paper baseline. The next policy
needs a real occupancy/depth frontier map or learned exploration component,
then the Dual-Anchor memory policy should be connected to the same official
step loop.

## Addendum: Occupancy Frontier Baseline Smoke

The adapter now includes a first map-backed no-memory baseline,
`occupancy_frontier`. It uses only official `depth`, `gps`, and `compass`
observations to maintain a small 2D occupancy grid:

- normalized or meter-scale depth is converted to metric ray endpoints;
- cells along depth rays are marked free;
- finite depth endpoints are marked occupied;
- unknown cells adjacent to free cells are counted as frontiers;
- the policy moves through clear center depth and turns toward frontier cells
  when blocked.
- blocked turns use a short four-step turn burst before replanning, which
  avoids frame-by-frame left/right flip-flops without locking the robot into a
  full-budget spin.

This still does not use target pose, semantic oracle masks, detector positives,
Habitat pathfinder shortcuts, route followers, or teleportation.

Final command:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_turn_burst_20260530_v4 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy occupancy_frontier \
    --max-episodes 3 \
    --max-steps 200 \
    --validate-habitat
```

Artifact:

- `runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_20260530_v1`
- `runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_verify_20260530_v2`
- `runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_turn_latch_20260530_v3`
- `runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_turn_burst_20260530_v4`

The `v3` full blocked-turn latch is retained only as negative debug history:
it removed immediate alternation, but over-rotated on blocked episodes and
regressed SoftSPL to the depth-reactive scaffold level.

Result:

| Run | Policy | Episodes | Success | SPL | SoftSPL | Mean distance to goal |
|---|---|---:|---:|---:|---:|---:|
| `occupancy_frontier_valmini_3ep_200steps_turn_burst_20260530_v4` | `occupancy_frontier` | `3` | `0.0` | `0.0` | `0.04420002662118805` | `6.509775956471761` |

Comparison to depth-reactive scaffold:

| Policy | Episodes | Success | SPL | SoftSPL | Mean distance to goal |
|---|---:|---:|---:|---:|---:|
| `frontier_only` | `3` | `0.0` | `0.0` | `0.0013203695130148407` | `6.915587266286214` |
| `occupancy_frontier` | `3` | `0.0` | `0.0` | `0.04420002662118805` | `6.509775956471761` |

Interpretation:

The occupancy frontier baseline is a better official-loop scaffold than the
depth-reactive baseline, but it is still far from a publishable ObjectNav
baseline because it does not yet stop on detected targets and did not solve any
of the three smoke episodes. Its value is architectural: the official loop now
has a map-backed no-memory policy and emits map debug telemetry that the
Dual-Anchor memory policy can later reuse or bias.

## Addendum: Frame-Corrected Occupancy Frontier Rerun

After the GPS/compass frame correction in
`docs/experiments/2026-05-30-habitat-official-gps-compass-frame-correction.md`,
the same three-episode occupancy-frontier smoke was rerun because the occupancy
map uses the same observation boundary.

Command:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_framefix_20260530_v5 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy occupancy_frontier \
    --max-episodes 3 \
    --max-steps 200 \
    --validate-habitat
```

Artifact:

- `runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_framefix_20260530_v5`

Result:

| Run | Policy | Episodes | Success | SPL | SoftSPL | Mean distance to goal |
|---|---|---:|---:|---:|---:|---:|
| `occupancy_frontier_valmini_3ep_200steps_framefix_20260530_v5` | `occupancy_frontier` | `3` | `0.0` | `0.0` | `0.044200068701652974` | `6.509775638580322` |

Interpretation:

The corrected frame did not materially change this smoke metric, but the new
artifact supersedes `turn_burst_20260530_v4` as the current official
occupancy-frontier scaffold. It still solves none of the three episodes and
remains a weak no-memory baseline, not a paper-grade comparator.
