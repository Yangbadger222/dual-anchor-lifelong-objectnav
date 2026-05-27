# Experiment Report: Habitat Val-Mini Episode-Start Confirmation Stress

Date: 2026-05-27
Owner: Codex
Status: Completed

## Question

How poor is target visibility from official HM3D ObjectNav `val_mini` episode
starts under the current scripted action sweep, and can temporal/multi-view
positive confirmation block single-frame false-positive semantic masks before
they update usability memory?

## Hypothesis

Official episode starts should see the target much less often than
goal-viewpoint starts, because ObjectNav starts are designed for navigation
rather than immediate semantic confirmation. Requiring repeated positive
candidates from changed viewpoints, plus detector-mask overlap, should suppress
low-precision single-frame positives, but it will also lower final memory
validity when real target views are sparse or fragmented.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `4cf941e`, dirty worktree |
| Machine | `badger-linux`, Ubuntu Linux 6.8.0-111-generic, NVIDIA RTX 4070 Laptop GPU |
| Dataset / scene | HM3D ObjectNav `objectnav_hm3d_v1/val_mini`; local HM3D scenes `00800-TEEsavR23oF` and `00802-wcojb4TFT35` |
| Simulator / robot | Habitat-Sim 0.3.3 direct RGB-D-semantic sensors, no robot |
| Python / env | conda env `habitat`, Python 3.9.23 |
| Key parameters | 30 episodes, 7 rows per episode, seed `313`, sensor size `96`, breaker modes `clean, miss, fly_point, edge_break, mixed`, positive confirmation `2` frames, `0.05 m` translation or `5 deg` rotation, mask IoU `0.05` |

## Commands

Goal-viewpoint semantic stress with positive confirmation:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_objectnav_valmini_semantic_stress \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_usability/hm3d_valmini_semantic_stress_confirmed_30ep \
  --max-episodes 30 \
  --start-source goal_viewpoint \
  --seed 313 \
  --sensor-size 96 \
  --positive-confirmation-frames 2 \
  --positive-confirmation-min-translation 0.05 \
  --positive-confirmation-min-rotation-deg 5.0 \
  --positive-confirmation-min-mask-iou 0.05
```

Official episode-start semantic stress with the same confirmation gate:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_objectnav_valmini_semantic_stress \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_usability/hm3d_valmini_semantic_stress_episode_start_confirmed_30ep \
  --max-episodes 30 \
  --start-source episode_start \
  --seed 313 \
  --sensor-size 96 \
  --positive-confirmation-frames 2 \
  --positive-confirmation-min-translation 0.05 \
  --positive-confirmation-min-rotation-deg 5.0 \
  --positive-confirmation-min-mask-iou 0.05
```

## Metrics

| Metric | Goal Viewpoint + Confirmation | Episode Start + Confirmation | Notes |
|---|---:|---:|---|
| Episodes completed | 30 | 30 | Same `val_mini` subset |
| Trace rows | 210 | 210 | Reset + 6 scripted actions |
| Target-visible episodes | 27 | 6 | Official starts see target in only 20% of episodes |
| Target-visible rows | 174 | 27 | 82.9% vs 12.9% of rows |
| Candidate evidence counts | `POSITIVE=58`, `NON_CONFIRMATION=9`, `UNKNOWN=143` | `POSITIVE=24`, `NON_CONFIRMATION=5`, `UNKNOWN=181` | Candidate is pre-confirmation evidence |
| Final evidence counts | `POSITIVE=31`, `NON_CONFIRMATION=9`, `UNKNOWN=170` | `POSITIVE=4`, `NON_CONFIRMATION=5`, `UNKNOWN=201` | Final evidence is what updated memory |
| Decision counts | `VERIFY=190`, `TRUST=20` | `VERIFY=210` | Official starts never reached trust |
| Mean final `p_valid` | 0.683128 | 0.625552 | Confirmation is conservative |
| Candidate positive rows | 58 | 24 | Raw accepted-by-quality positive candidates |
| Confirmed positive rows | 31 | 4 | Passed temporal/view/mask gate |
| Suppressed positive rows | 27 | 20 | Held as quarantined `UNKNOWN` |
| False-positive-candidate rows | 4 | 14 | Low-precision candidates before confirmation |
| False-positive-positive rows | 0 | 0 | No low-precision candidate reached memory |
| Missed visible target rows | 11 | 6 | Oracle target visible but detector mask below threshold |

## Breaker Mode Notes

| Start | Mode | Target-visible episodes | Candidate positives | Confirmed positives | Suppressed positives | False-positive candidates | False-positive positives | Mean final `p_valid` |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Goal viewpoint | `clean` | 6 | 31 | 25 | 6 | 0 | 0 | 0.955269 |
| Goal viewpoint | `miss` | 5 | 8 | 1 | 7 | 0 | 0 | 0.442884 |
| Goal viewpoint | `fly_point` | 5 | 10 | 5 | 5 | 0 | 0 | 0.727931 |
| Goal viewpoint | `edge_break` | 6 | 3 | 0 | 3 | 0 | 0 | 0.641903 |
| Goal viewpoint | `mixed` | 5 | 6 | 0 | 6 | 4 | 0 | 0.647654 |
| Episode start | `clean` | 1 | 3 | 1 | 2 | 0 | 0 | 0.642715 |
| Episode start | `miss` | 2 | 3 | 1 | 2 | 0 | 0 | 0.535703 |
| Episode start | `fly_point` | 1 | 0 | 0 | 0 | 0 | 0 | 0.647654 |
| Episode start | `edge_break` | 1 | 4 | 2 | 2 | 0 | 0 | 0.654031 |
| Episode start | `mixed` | 1 | 14 | 0 | 14 | 14 | 0 | 0.647654 |

## Comparison To Previous No-Confirmation Run

| Metric | Previous goal-viewpoint run | Goal-viewpoint confirmation run | Effect |
|---|---:|---:|---|
| Mean final `p_valid` | 0.757149 | 0.683128 | Lower confidence from stricter acceptance |
| Clean mean final `p_valid` | 0.970945 | 0.955269 | Small clean penalty |
| Mixed mean final `p_valid` | 0.743600 | 0.647654 | Mixed positives no longer inflate memory |
| Final positive rows | 58 | 31 | 27 candidates suppressed |
| False-positive-positive rows | 4 | 0 | Single-frame low-precision positives blocked |

## Observations

- Official episode starts are a poor semantic-memory stress start for this
  scripted action sweep: only 6 of 30 episodes ever saw the target, and only 27
  of 210 rows had enough oracle target pixels.
- Goal-viewpoint starts remain useful for isolating memory behavior because
  they make the target visible in 27 of 30 episodes and 174 of 210 rows.
- The confirmation gate blocked all low-precision positive updates in both
  runs. In the episode-start mixed mode, 14 low-precision candidate positives
  were all suppressed.
- The gate is deliberately conservative. It reduced false positives to zero,
  but also suppressed real positives when scripted motion did not produce
  enough temporal/view/mask consistency.
- A temporal/view-only dry run still allowed mixed false positives through, so
  the final rule also requires detector-mask IoU with the pending positive.

## Result

The official episode-start visibility is very poor under the current scripted
actions: target-visible episodes drop from 27/30 with goal viewpoints to 6/30
with official starts, and target-visible rows drop from 174/210 to 27/210. This
confirms that `episode_start` is the right pass for measuring navigation
difficulty, but not a clean semantic-memory pressure test unless a real
navigation policy is moving toward the goal.

The temporal/multi-view/mask-consistency confirmation gate closes the observed
single-frame false-positive weakness for this 30-episode `val_mini` run:
false-positive-positive rows are 0 in both start modes. The cost is lower memory
confidence and many suppressed positives, so the next policy layer should make
confirmation adaptive rather than simply stricter.

This is still not an official ObjectNav benchmark result: no learned navigation
policy was run, no real YOLO model was run, and no success/SPL metric is
reported.

## Follow-up

- Add debug PNG export for suppressed false-positive candidates and missed
  visible targets.
- Make positive confirmation adaptive by category, mask area, and target range.
- Replace scripted actions with a navigation policy before using
  `episode_start` to judge full ObjectNav behavior.
- Replace corrupted oracle masks with real detector masks after debug export is
  available.
