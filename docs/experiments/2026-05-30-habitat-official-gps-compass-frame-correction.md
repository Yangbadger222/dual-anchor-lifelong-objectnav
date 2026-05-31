# Experiment Report: Habitat Official GPS/Compass Frame Correction

Date: 2026-05-30
Owner: Codex
Status: Completed frame-correction smoke, not a benchmark result

## Question

Does the official ObjectNav memory policy interpret Habitat-Lab `gps` and
`compass` observations in the same episodic frame that Habitat actually
emits?

## Hypothesis

Habitat ObjectNav's 2D GPS is `[forward, right]`, not `[right, forward]`, and
right turns make compass negative. The policy should therefore map GPS to
internal `(x=right, z=forward)` by swapping the two components, and map compass
to internal positive-right heading by negating it.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` at `0f14893` plus uncommitted official-eval/exporter slice |
| Machine | `badger-linux` |
| Conda env | `habitat` |
| Habitat-Lab | `0.3.3` |
| Dataset | HM3D ObjectNav `val_mini` |
| Policy | `memory_guided_frontier` |
| Smoke artifact | `runs/habitat_official_objectnav/memory_guided_frontier_episode_frame_forward_probe_1ep_20260530_v1` |

## Command

Live sensor probe:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -c "... create official env, print gps/compass before and after move/turn ..."
```

Frame-correction smoke:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/memory_guided_frontier_episode_frame_forward_probe_1ep_20260530_v1 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy memory_guided_frontier \
    --memory-prior-path runs/habitat_official_objectnav/memory_guided_frontier_episode_frame_forward_probe_1ep_20260530_v1/memory_prior.json \
    --memory-stop-radius-m 0.35 \
    --memory-bearing-tolerance-deg 20 \
    --memory-min-confidence 0.5 \
    --max-episodes 1 \
    --max-steps 6 \
    --validate-habitat
```

The prior used:

```json
{
  "anchors": [
    {
      "object_category": "chair",
      "x_m": 0.0,
      "z_m": 2.0,
      "confidence": 1.0,
      "source": "synthetic_episode_frame_forward_probe:not_benchmark_valid",
      "coordinate_frame": "episode_start_relative"
    }
  ]
}
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| RED regression tests | `2 failed` | Before fix: wrong first action in both tests. |
| GREEN regression tests | `2 passed` | After `_observation_xz` and `_observation_heading` fix. |
| Linux focused tests | `33 passed` | Official eval, CLI, and lifecycle export tests. |
| Smoke actions | `move_forward` x5, then `stop` | Confirms forward episode-frame anchor is treated as forward. |
| Smoke bearing error | `1.0362705893385282e-07` | Near zero. |
| Smoke success/SPL | `0.0` / `0.0` | Expected; synthetic prior is not benchmark-valid. |

## Observations

- Live probe after one `move_forward`:
  - start GPS `[-0.0, 0.0]`
  - after move GPS approximately `[0.0444, 0.0]`
  - compass stayed approximately `0.0`
- Live probe after `turn_right`:
  - compass approximately `-0.5236`
  - after right turn plus move, GPS approximately `[0.0160, 0.0092]`
- Habitat-Lab source confirms the 2D GPS convention:
  `[-agent_position[2], agent_position[0]]`.

## Result

The official adapter now converts Habitat observations into the policy's
internal local frame at the observation boundary:

- `gps[0]` maps to internal `z_m` forward.
- `gps[1]` maps to internal `x_m` right.
- `compass` maps to internal heading by negating the raw sensor value.

This is an evaluation-integrity fix. It does not create a policy win by itself,
but it is required before memory priors, occupancy maps, and learned memory
policies can be evaluated honestly in the official loop.

## Follow-up

- Re-run the previous official `occupancy_frontier` smoke because its map rays
  also used the same observation boundary.
- Build the next episode-relative memory bridge on top of this corrected frame.
- Keep lifecycle `habitat_world` anchors rejected until a documented transform
  or direct episode-relative memory logger exists.
