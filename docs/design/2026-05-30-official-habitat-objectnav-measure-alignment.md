# Design Doc: Official Habitat ObjectNav Measure Alignment

Date: 2026-05-30
Owner: Codex
Status: Draft

## Goal

Add an official Habitat-Lab evaluation path so Dual-Anchor ObjectNav policies
can report benchmark-comparable `Success`, `SPL`, `SoftSPL`, and
`DistanceToGoal` metrics instead of only internal replay action counts.

The immediate goal is protocol alignment, not a performance claim: run the same
memory policy under official Habitat-Lab task measures, sensor sizes, action
space, episode starts, stop semantics, and goal definitions.

## Non-Goals

- Do not report current lifecycle replay success/action counts as official SPL.
- Do not change official ObjectNav episode starts, target categories, success
  distance, action definitions, or sensor dimensions to favor memory.
- Do not use `habitat_baselines`; it is not installed in the current Linux
  `habitat` environment.
- Do not collapse lifelong memory claims into single-episode ObjectNav claims.
  Official ObjectNav metrics are needed for comparison, but separate lifelong
  memory/relocation protocols remain necessary for the paper's core claim.

## Background

The current closed-loop Habitat runner is an internal lifecycle replay harness.
It uses real HM3D scenes, Grounding-DINO, route following, and detector evidence,
but it does not instantiate the official Habitat-Lab ObjectNav task with
measurements enabled. Therefore its success/action-count tables are useful for
debugging memory mechanisms, but they cannot be compared to SOTA ObjectNav
numbers.

On the Linux machine, Habitat-Lab `0.3.3` is installed and registers official
navigation measures including `Success`, `SPL`, `SoftSPL`, `DistanceToGoal`,
and `DistanceToGoalReward`. `habitat_baselines` is not installed, so this work
should use Habitat-Lab env/task APIs directly.

## System Boundary

This adapter belongs beside, not inside, the lifecycle replay runner. It should:

- load official HM3D ObjectNav episode datasets;
- create a Habitat-Lab `ObjectNav-v1` environment with official task measures;
- wrap a Dual-Anchor policy as the action producer;
- let Habitat-Lab compute official metrics;
- write per-episode and aggregate JSON/CSV reports.

It should not:

- teleport the agent;
- use route follower shortcuts as policy actions when reporting official SPL;
- alter official target-success conditions;
- use simulator oracle target pose to choose actions, except in clearly labeled
  oracle sanity checks.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Episode dataset | official Habitat ObjectNav `.json.gz` | `val_mini` first, then `val`. |
| Input | Scene root | HM3D scene directory | Must match episode scene ids. |
| Input | Policy config | YAML/CLI | Memory on/off, detector, GPT/language disabled initially. |
| Input | Sensor config | Habitat-Lab config | Must match official benchmark dimensions. |
| Output | Per-episode metrics | JSONL/CSV | Habitat-Lab measure values plus memory debug fields. |
| Output | Aggregate metrics | `summary.json` | SR, SPL, SoftSPL, distance-to-goal, action counts. |
| Output | Protocol manifest | JSON | Habitat version, measures, success distance, sensors, dataset split. |

## Interfaces

Planned CLI:

```bash
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --config configs/habitat/objectnav_official_hm3d_valmini.yaml \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_official_objectnav/<run_name> \
  --policy dual_anchor_memory \
  --detector grounding_dino \
  --max-episodes 30
```

Required official measures:

- `Success`
- `SPL`
- `SoftSPL`
- `DistanceToGoal`
- `DistanceToGoalReward` when available in the task config

Policy comparison modes:

- `official_baseline_oracle_stop`: sanity check only;
- `frontier_only`: no memory;
- `dual_anchor_memory`: memory-enabled policy;
- `dual_anchor_memory_language_ready`: same interface with a future language
  goal parser, GPT disabled until policy metrics are stable.

## Data Flow

1. Load Habitat-Lab config and official ObjectNav dataset.
2. Verify every requested episode scene exists under `scene_root`.
3. Reset the environment for each episode and capture the official measure
   names/UUIDs before stepping.
4. Build policy state from the official observation stream only.
5. Emit discrete Habitat actions until `STOP` or max steps.
6. Read official measures from `env.get_metrics()` after each episode.
7. Persist official metrics and separate memory debug telemetry.
8. Aggregate SR/SPL/SoftSPL only from Habitat-Lab measure outputs.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Scene asset mismatch | episode scene ids missing | report missing scenes and block metric claim. |
| Sensor/action mismatch | manifest differs from official config | fail preflight before evaluation. |
| Internal replay metrics mixed with official metrics | output schema has ambiguous fields | namespace official metrics as `habitat_official.*`. |
| Policy uses oracle shortcuts | action source trace contains follower/teleport/oracle goal | mark run invalid for benchmark comparison. |
| Memory protocol not represented by single episode | official SR/SPL improves little despite lifecycle benefit | report as separate result: official ObjectNav comparability vs lifelong memory benchmark. |
| Detector latency makes official action loop too slow | runtime manifest records per-step time | start with `val_mini`, cache detector outputs only if cache key uses observation bytes/config. |

## Verification Plan

1. Unit-test config parsing and measure-name extraction with a tiny fake env.
2. Add a preflight command that imports Habitat-Lab, lists registered measures,
   verifies dataset and scene availability, and writes a protocol manifest.
3. Run one official `val_mini` episode with a random/no-op policy and verify
   `env.get_metrics()` contains official measures.
4. Run a small deterministic policy smoke on `val_mini` and confirm SR/SPL are
   read from Habitat-Lab, not recomputed by local code.
5. Only after this path is stable, port `frontier_only` and `dual_anchor_memory`
   policies into the official step loop.
6. Compare `frontier_only` vs memory on `val_mini`, then `val`, while keeping
   lifecycle relocation results as a separate paper table.

## Research Relevance

This work closes the evaluation gap needed for a top robotics submission. The
paper needs two evidence tracks:

- official ObjectNav comparability: SR/SPL/SoftSPL under Habitat-Lab measures;
- lifelong memory contribution: cross-episode memory reuse, stale-memory
  rejection, relocation recovery, and robot-transfer readiness.

Without the official measure adapter, the project can show interesting memory
mechanisms but cannot make a credible SOTA comparison.

## Open Questions

- Which official sensor resolution and max-step settings should be treated as
  the primary comparison protocol for HM3D ObjectNav in Habitat-Lab `0.3.3`?
- Should the first official adapter use Grounding-DINO live inference or a
  frozen observation-level detector cache for reproducibility?
- How should the paper present lifelong relocation benefits that are not fully
  captured by single-episode ObjectNav SPL?
