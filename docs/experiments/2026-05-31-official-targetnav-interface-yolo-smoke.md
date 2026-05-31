# Experiment Report: Official TargetNav Interface YOLO Smoke

Date: 2026-05-31
Owner: Codex
Status: Completed; negative local-backend diagnostic

## Question

Can a benchmark-valid TargetNav interface convert memory-active-perception target
reacquisition into official ObjectNav success without using Habitat goal
viewpoints or online pathfinder?

## Hypothesis

If the remaining bottleneck is only one-frame target estimation, then refreshing
the detector-depth target estimate over multiple frames should stabilize the
TargetNav goal and improve the matched `tv_monitor` episode. If metrics remain
unchanged, the bottleneck is the low-level local navigation backend.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / uncommitted research changes |
| Machine | Linux mirror `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset / simulator | Habitat ObjectNav HM3D `val_mini` |
| Policy | `memory_active_perception_frontier_targetnav` |
| Detector | YOLO-World `yolov8s-worldv2.pt`, confidence `0.25` |
| Memory prior | `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json` |
| Key parameters | 4 episodes, 100 max steps, seed `313` |

## Commands

Local verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py

git diff --check
```

Linux verification:

```bash
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  source /home/badger/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_ros_packaging.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  source /home/badger/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
  PYTHONPATH=src/objectnav_core python -m compileall -q \
    src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
    src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_ros_packaging.py'
```

Baseline TargetNav occupancy smoke before multi-frame target belief:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_active_perception_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313
```

Target-belief smoothing smoke:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_belief_active_perception_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313
```

## Metrics

| Run | Success | SPL | SoftSPL | Mean Distance | Target-match calls | TargetNav samples |
|---|---:|---:|---:|---:|---:|---:|
| Fixed controller hand-score, 50 steps | `0/4` | `0.0` | `0.02518699682786324` | `5.697803378105164` | `4` | n/a |
| Oracle pathfinder suffix, radius `0.05`, 100 steps | `1/4` | `0.24261777449152924` | `0.24163039972246855` | `4.007396151311696` | `1` | n/a |
| TargetNav occupancy, 100 steps | `0/4` | `0.0` | `0.0009902771347611306` | `5.880594372749329` | `1` | `1` |
| TargetNav target belief, 100 steps | `0/4` | `0.0` | `0.0009902771347611306` | `5.880594372749329` | `48` | `48` |

Matched `tv_monitor` episode:

| Run | Final distance | Decision profile | Target estimate |
|---|---:|---|---|
| Oracle pathfinder suffix | `0.061577994376420975` | `44` `follow_pathfinder_suffix` steps | Habitat goal/viewpoint oracle |
| TargetNav occupancy | `7.554370880126953` | `95` `targetnav_occupancy_turn` steps | `x=-2.306587`, `z=0.168733`, depth `2.31275` |
| TargetNav target belief | `7.554370880126953` | `95` `targetnav_occupancy_turn` steps | same smoothed estimate, `48` samples |

## Observations

- Multi-frame target belief worked mechanically: YOLO target-match calls rose
  from `1` to `48`, and the final target debug recorded
  `smoothing_sample_count=48`.
- Official metrics did not improve. The matched target episode still spent
  almost the entire suffix alternating turns toward the same occupancy target.
- The negative result separates target estimation from local control: the
  current occupancy-grid backend is too weak for benchmark claims even when the
  target remains visible and the target coordinate is refreshed.
- The oracle pathfinder suffix remains useful as a teacher/diagnostic, but it
  is not valid as an online benchmark policy.

## Result

The next paper-relevant work should stop hand-tuning detector-local turn rules.
The memory/TargetNav layer should output a target belief or long-term goal, and
the benchmark policy should use a standard sensor-only local navigation backend:
FMM/A* over a depth-built cost map, a Habitat-baselines PointNav/DDPPO-style
local policy, or a learned local TargetNav policy trained from pathfinder
teacher labels but not using pathfinder online.

## Follow-up

- Add a benchmark-valid local navigation backend under the TargetNav interface.
- Use Habitat pathfinder only for supervision and failure decomposition.
- Compare memory policies only after the low-level backend can solve target
  approach from estimated coordinates without simulator oracle access.
