# Design Doc: Official TargetNav DDPPO Backend

Date: 2026-05-31
Owner: Codex
Status: Implemented; four-episode official smoke completed with `0/4` success

## Goal

Connect the detector/depth TargetNav belief to a mature Habitat-Baselines
PointNav/DDPPO local policy so terminal navigation uses a learned local
navigator instead of hand-written turn rules.

## Non-Goals

- Do not use Habitat pathfinder, episode goal positions, or shortest-path
  follower online.
- Do not train a new DDPPO model in this slice.
- Do not claim benchmark improvement until official Habitat metrics prove it.
- Do not commit downloaded checkpoints or model zips; `models/` is ignored.

## Background

The current TargetNav occupancy backend and the provisional FMM backend both
expose the same bottleneck: target belief can be produced, but low-level action
execution oscillates. The Linux `habitat` environment can install the matching
Habitat-Baselines checkout with:

```bash
pip install -e third_party/habitat-lab/habitat-baselines
```

The official HM3D PointNav comparison release provides
`hm3d_ddppo_pointnav_baselines_v1.zip`, including:

- `hm3d-depth/ckpt.60.pth`
- `hm3d-rgb/ckpt.59.pth`
- partial-data and Gibson/MP3D variants

The depth checkpoint was verified on Linux against the current
`PointNavResNetPolicy` with `missing=0` and `unexpected=0` after loading the old
checkpoint config with a small compatibility shim.

## System Boundary

Owned by this slice:

- New policy: `memory_active_perception_frontier_targetnav_ddppo`.
- Optional DDPPO backend loader and inference adapter.
- State management for recurrent hidden state, previous action, and mask.
- CLI/config fields for checkpoint path and device.

Dependencies:

- Existing TargetNav target belief:
  `_targetnav_pointgoal_with_gps_compass(...)`.
- Official Habitat depth, GPS, and compass observations.
- Optional Linux runtime dependencies: `torch`, `gym`, `habitat_baselines`.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Target belief | `x_m`, `z_m` | Episode-local detector/depth estimate. |
| Input | PointGoal | `[rho, -phi]` | Habitat polar convention. |
| Input | Depth | `H x W` or `H x W x 1` | Converted to `256 x 256 x 1` float32. |
| Input | Checkpoint | `.pth` | HM3D depth DDPPO checkpoint. |
| Output | Action | Habitat ObjectNav action string | `stop`, `move_forward`, `turn_left`, `turn_right`. |
| Output | Debug | JSON | Backend, checkpoint path, pointgoal, action id, fallback reason. |

## Interfaces

CLI:

```bash
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --policy memory_active_perception_frontier_targetnav_ddppo \
  --targetnav-ddppo-checkpoint-path \
    models/habitat/ddppo/hm3d_ddppo_pointnav_baselines_v1/hm3d-depth/ckpt.60.pth
```

Internal APIs:

- `_select_targetnav_ddppo_action(...)`
- `_load_targetnav_ddppo_backend(...)`
- `HabitatPointNavDDPPOBackend`
- `_prepare_ddppo_depth_observation(...)`

## Data Flow

1. Existing memory-active-perception policy searches until a target detector
   match exists.
2. Detector bbox plus depth estimates a target belief in the episode frame.
3. `_targetnav_pointgoal_with_gps_compass(...)` converts the target belief to
   PointNav polar input.
4. The DDPPO backend receives:
   - depth tensor;
   - `pointgoal_with_gps_compass`;
   - recurrent hidden state;
   - previous action;
   - not-done mask.
5. The backend runs deterministic `PointNavResNetPolicy.act(...)`.
6. The selected action id is mapped to the official Habitat action string.
7. If DDPPO import, checkpoint load, target belief, pointgoal, or depth
   preparation fails, the policy falls back to active-perception frontier and
   records the reason.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| `habitat_baselines` missing | Import error | Fail preflight for DDPPO policy or fallback if injected backend absent. |
| Old checkpoint config pickle incompatible | `torch.load` attribute error | Use trusted-source shim or export a pure state-dict artifact. |
| Checkpoint architecture mismatch | nonzero missing/unexpected keys | Reject backend load and record incompatibility. |
| Depth shape/range mismatch | preparation returns invalid tensor | Fallback and record `invalid_depth`. |
| DDPPO outputs invalid action id | action id not in `{0,1,2,3}` | Fallback and record `invalid_ddppo_action`. |

## Verification Plan

1. RED/GREEN manifest/config tests for DDPPO policy and checkpoint path:
   complete.
2. RED/GREEN unit test with an injected fake DDPPO backend to prove pointgoal
   and depth reach the backend and action id maps correctly: complete.
3. RED/GREEN depth preprocessing tests for normalized `H x W`, `H x W x 1`, and
   meter-valued depth: complete.
4. Linux import/load probe:
   - `habitat_baselines` import: complete;
   - checkpoint state dict load: complete;
   - `PointNavResNetPolicy.load_state_dict(..., strict=False)` with zero
     missing/unexpected keys: complete.
5. Linux DDPPO backend smoke:
   - real HM3D depth checkpoint load plus one deterministic `act(...)` call:
     complete on CPU;
   - official Habitat YOLO smoke: complete for four episodes, with DDPPO
     activated on the matched `tv_monitor` episode.

## Implementation Notes

The implemented backend is `HabitatPointNavDDPPOBackend` in
`src/objectnav_core/objectnav_core/evaluation/habitat_pointnav_ddppo_backend.py`.
It keeps Habitat-Baselines imports lazy, installs a narrow compatibility shim
for the old checkpoint's `habitat.config.default.Config` pickle reference,
strips the `actor_critic.` checkpoint prefix, and rejects any nonzero
missing/unexpected keys when loading into `PointNavResNetPolicy`.

The evaluator now registers
`memory_active_perception_frontier_targetnav_ddppo`, requires
`targetnav_ddppo_checkpoint_path`, resets recurrent DDPPO state at each
episode boundary, and maps action ids with Habitat's standard PointNav action
order: `0=stop`, `1=move_forward`, `2=turn_left`, `3=turn_right`.

The first official four-episode YOLO smoke wrote
`runs/habitat_official_objectnav/targetnav_ddppo_yolo_4ep_100steps_20260531_v1`.
It produced `0/4` official success, SPL `0.0`, SoftSPL
`0.06665590634964569`, mean distance `5.384531855583191`, and `95`
`targetnav_ddppo_*` decisions. This proves online integration, not navigation
success.

The follow-up oracle contract diagnostic wrote
`runs/habitat_official_objectnav/oracle_targetnav_ddppo_contract_ablation_tv_monitor_20260531_v1`.
It showed that the TargetNav PointGoal adapter matches Habitat's native
`PointGoalWithGPSCompassSensor` math to numerical precision, but the downloaded
HM3D depth checkpoint fails on the `tv_monitor` oracle goal under the default
ObjectNav control/sensor contract. The checkpoint was trained with
`TURN_ANGLE=10`, 256x256 depth, 90 degree HFOV, camera height `1.25`, depth
range `0.0-10.0`, and sliding enabled; the official ObjectNav loop uses
`TURN_ANGLE=30`, 640x480 RGB-D, 79 degree HFOV, camera height `0.88`, depth
range `0.5-5.0`, and sliding disabled. When the ObjectNav diagnostic was
changed to match the checkpoint contract, the oracle `tv_monitor` run succeeded
with final distance `0.029823284596204758`, SPL `0.9851193591581345`, and
SoftSPL `0.9812302867951809`. That run is diagnostic-only, not a
benchmark-valid ObjectNav result.

## Research Relevance

This is the local-navigation substrate the memory paper needs. The paper claim
should be about lifelong semantic object memory and drift-robust recall, not a
custom low-level controller. A standard PointNav/DDPPO backend makes the
architecture easier to compare against SOTA-style systems and eventually easier
to replace with a robot Nav2 backend.

## Open Questions

- What is the best benchmark-valid local policy training target under the
  official ObjectNav contract: PointNav-to-viewpoint, detector-depth TargetNav,
  or a short-horizon collision-recovery option policy?
- Should the next local policy use depth-only input for easier transfer, or
  RGB-D after verifying the RGB checkpoint and observation contract?
- Does PointNav trained on oracle goal coordinates transfer cleanly to
  detector-depth target beliefs after the action/sensor contract is fixed, or
  do we still need a learned belief-to-goal adapter?
- Should old checkpoint configs be loaded with a runtime shim, or should we
  export trusted pure state-dict artifacts once and use those thereafter?
