# Experiment Report: Official TargetNav DDPPO Contract Diagnostic

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Why does the TargetNav DDPPO backend fail on the matched `tv_monitor` episode
even when TargetNav activates and receives a plausible target belief?

## Hypothesis

If DDPPO still fails when fed oracle Habitat goal/viewpoint coordinates, then
the blocker is not detector target-belief quality. It is more likely a
PointGoal/action/observation contract mismatch between the HM3D PointNav
checkpoint and the official ObjectNav evaluation loop.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `0f14893` plus uncommitted TargetNav DDPPO changes |
| Machine | `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini`, `objectnav_hm3d_v1/val_mini/val_mini.json.gz` |
| Simulator / robot | Habitat-Lab official `ObjectNav-v1` env |
| Key parameters | Episode index `2`, episode id `0`, category `tv_monitor`, max steps `100`, checkpoint `hm3d-depth/ckpt.60.pth`, CUDA |

## Command

The diagnostic was run as an inline Python script over SSH. It created:

```bash
runs/habitat_official_objectnav/oracle_targetnav_ddppo_tv_monitor_20260531_v1
runs/habitat_official_objectnav/oracle_targetnav_ddppo_contract_ablation_tv_monitor_20260531_v1
```

Each run used oracle Habitat goal/viewpoint positions only for failure
decomposition. The online benchmark policy still does not use these values.

## Metrics

| Variant | Success | Final Distance | SPL | SoftSPL | Notes |
|---|---:|---:|---:|---:|---|
| Oracle goal, in-repo adapter, default ObjectNav contract | `0.0` | `4.759258270263672` | `0.0` | `0.3699993889916494` | Adapter and native pointgoal differed by at most `4.98e-7`. |
| Oracle goal, native Habitat pointgoal, default ObjectNav contract | `0.0` | `4.759258270263672` | `0.0` | `0.3699993889916494` | Same behavior as adapter path. |
| Native pointgoal, ObjectNav with `turn_angle=10` only | `0.0` | `1.9689984321594238` | `0.0` | `0.7393563986460863` | Large improvement, still not success. |
| Native pointgoal, DDPPO-matched turn/sensor/sliding contract | `1.0` | `0.029823284596204758` | `0.9851193591581345` | `0.9812302867951809` | Oracle diagnostic succeeds in `49` actions. |

## Observations

- The PointGoal adapter is not the blocker: the in-repo `[rho, -phi]` adapter
  matches Habitat's native `PointGoalWithGPSCompassSensor` math to numerical
  precision on the live `tv_monitor` episode.
- Under the default ObjectNav contract, DDPPO moves from distance
  `7.554370880126953` to `4.759258270263672`, then becomes physically stuck
  around internal pose `x=-2.70`, `z=-0.875` while repeatedly issuing
  `move_forward`.
- The HM3D depth checkpoint was trained with a different local-control
  contract: `TURN_ANGLE=10`, 256x256 depth, 90 degree HFOV, camera height
  `1.25`, normalized depth range `0.0-10.0`, and sliding enabled.
- The official ObjectNav config used by the benchmark loop has `TURN_ANGLE=30`,
  640x480 RGB-D, 79 degree HFOV, camera height `0.88`, normalized depth range
  `0.5-5.0`, and sliding disabled.

## Result

The current DDPPO failure is primarily an environment/action/observation
contract mismatch, not a TargetNav PointGoal sign bug and not solely detector
belief noise. The off-the-shelf HM3D PointNav checkpoint can solve the same
`tv_monitor` oracle diagnostic only when the ObjectNav environment is changed
to match the checkpoint's training contract. That adjusted run is diagnostic
only and is not a benchmark-valid ObjectNav result.

## Follow-up

- Do not claim benchmark-valid TargetNav DDPPO success with the current
  off-the-shelf checkpoint under the default ObjectNav config.
- Train or fine-tune a local PointNav/TargetNav policy under the official
  ObjectNav sensor/action contract, or use a backend whose contract already
  matches it.
- Keep the DDPPO-matched ObjectNav override as an oracle diagnostic for
  decomposition only, not as a reported policy setting.
