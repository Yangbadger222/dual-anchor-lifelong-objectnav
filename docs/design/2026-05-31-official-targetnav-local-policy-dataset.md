# Design Doc: Official TargetNav Local Policy Dataset

Date: 2026-05-31
Owner: Codex
Status: Implemented locally; Linux Habitat export pending

## Goal

Create a benchmark-contract-aligned supervised dataset for a learned local
TargetNav policy. The dataset should pair official ObjectNav observations
(`depth`, `gps`, `compass`) and oracle Habitat goal/viewpoint PointGoals with
the shortest-path follower action under the unmodified official ObjectNav
action/sensor contract.

## Non-Goals

- Do not use the exported oracle actions online in benchmark-valid ObjectNav
  evaluation.
- Do not change the official ObjectNav simulator contract to match the
  downloaded DDPPO checkpoint.
- Do not train a deep policy in this slice. The output is a model-ready dataset
  and small metadata manifest.
- Do not solve semantic memory quality here; this is the local-navigation
  substrate needed after a remembered or detected target belief is available.

## Background

The TargetNav DDPPO contract diagnostic found that the PointGoal adapter is
correct but the downloaded HM3D PointNav checkpoint was trained under a
different action/sensor contract. Under default ObjectNav it failed even with
oracle goals; under checkpoint-matched settings it succeeded. A publishable
memory system therefore needs a local policy trained or fine-tuned under the
official ObjectNav contract instead of relying on an off-contract checkpoint.

## System Boundary

This dataset module owns offline sample export only:

- create/reset official Habitat ObjectNav environments;
- select oracle goal/viewpoint positions for each episode;
- compute native-compatible TargetNav PointGoals from official observations;
- ask Habitat's shortest-path follower for the teacher action;
- serialize compact JSON/CSV examples for later imitation or offline RL.

It depends on `habitat_official_objectnav_eval` for config/env helpers,
goal-position extraction, PointGoal conversion, action naming, and official
metric access.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Habitat config | YAML path | Defaults to official HM3D ObjectNav config. |
| Input | Dataset path / scene root | Habitat paths | Same defaults as official evaluator. |
| Input | Episode and step limits | CLI integers | Small limits support smoke exports; larger runs happen on Linux. |
| Output | `dataset.json` | JSON object | Includes schema, config, summary counts, and examples. |
| Output | `labels.csv` | CSV | Stable tabular view for quick inspection/training scripts. |

## Interfaces

- Python API:
  `export_official_targetnav_local_policy_dataset(...)`
- CSV writer:
  `write_official_targetnav_local_policy_dataset_csv(...)`
- CLI:
  `python -m objectnav_core.cli.export_habitat_official_targetnav_local_policy_dataset`

## Data Flow

1. Build an `OfficialObjectNavRunConfig` with the official ObjectNav contract.
2. For each episode, reset the environment and enumerate Habitat goal
   viewpoints with `_episode_goal_positions(...)`.
3. At each step, choose the nearest reachable goal/viewpoint to the current
   pose for the teacher query.
4. Convert that goal into episode-relative `x/z` and the tested
   `pointgoal_with_gps_compass` representation.
5. Query `ShortestPathFollower.get_next_action(goal_position)`.
6. Record observation metadata, compact depth statistics, pointgoal, teacher
   action, official distance-to-goal, and provenance.
7. Step the environment with the teacher action to collect the next sample.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Habitat runtime unavailable locally | Import/env creation raises | Unit tests use fake env/follower factories; real export runs on Linux. |
| Episode has no goal/viewpoints | Empty goal list | Skip episode and record skipped count. |
| Shortest-path follower unavailable | Factory returns `None` | Mark examples unavailable and stop teacher rollout for that episode. |
| Teacher action id is unknown | `_follower_action_name(...)` returns unsupported value | Skip that sample with `invalid_reason`. |
| Depth missing or malformed | `_depth_frame_2d(...)` returns `None` | Keep pointgoal/action metadata, set depth stats to `None`, and flag sample. |
| Oracle source leaks into benchmark policy | Dataset schema marks `source_validity=oracle_teacher_only` | Evaluator must not consume this dataset online except in explicitly non-benchmark training or ablation code. |

## Verification Plan

- Unit tests with a fake official env and fake follower prove:
  - examples contain schema/config/provenance fields;
  - PointGoal values use official GPS `[forward, right]` and compass sign;
  - CSV output is stable;
  - CLI writes JSON and CSV through an injected runner;
  - unavailable follower or missing goals are counted instead of crashing.
- Local focused pytest and `compileall`.
- Linux Habitat smoke export for one or two episodes with a small step limit,
  recording example counts and action distribution in an experiment report.

## Implementation Notes

- Added `habitat_official_targetnav_local_policy_dataset.py` with
  `export_official_targetnav_local_policy_dataset(...)` and
  `write_official_targetnav_local_policy_dataset_csv(...)`.
- Added CLI
  `python -m objectnav_core.cli.export_habitat_official_targetnav_local_policy_dataset`.
- Local fake-env tests cover oracle provenance, episode-relative target goal
  conversion from Habitat start pose, PointGoal export, depth statistics,
  CSV flattening, CLI JSON/CSV output, missing-goal skip counts, and unavailable
  teacher skip counts.
- The exporter is intentionally offline/diagnostic: examples are marked
  `source_validity=oracle_teacher_only` and must not be consumed online by a
  benchmark policy.

## Research Relevance

This turns the DDPPO mismatch from a dead end into a training path: a local
navigation policy can be trained under the same action/sensor contract used by
official ObjectNav metrics. That keeps the future paper claim focused on
lifelong semantic memory and target recall, while still replacing brittle
hand-coded local motion rules with a learned, benchmark-aligned controller.

## Open Questions

- Should the first learner be a compact depth-statistics MLP, a shallow depth
  CNN, or a fine-tuned Habitat-Baselines `PointNavResNetPolicy`?
- Should labels target exact follower actions, short-horizon option values, or
  both?
- How much HM3D data is needed before this local policy is strong enough to
  justify integrating behind TargetNav?
