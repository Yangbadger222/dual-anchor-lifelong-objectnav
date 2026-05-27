# Design Doc: Habitat Val-Mini Semantic Stress

Date: 2026-05-27
Owner: Codex
Status: Implemented

## Goal

Run the usability-memory semantic-mask stress test from official HM3D ObjectNav
`val_mini` episode files instead of a single synthetic Habitat-Sim reset loop.
The runner should prove that local HM3D scene assets, official ObjectNav episode
metadata, Habitat semantic masks, YOLO-breaker corruptions, and trace export can
work together in one reproducible command.

## Non-Goals

- Do not claim official Habitat ObjectNav success, SPL, or policy quality.
- Do not implement a learned navigation policy.
- Do not run a real YOLO detector.
- Do not rewrite downloaded dataset files or require permanent symlinks inside
  `datasets/`.

## Background

The repository already has a Habitat-Sim semantic stress runner that samples a
visible target from one scene and corrupts its semantic mask. Local HM3D assets
now include ObjectNav `val_mini` episode files and scene assets under:

- `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini`
- `datasets/habitat/scene_datasets/hm3d/habitat`
- `datasets/habitat/scene_datasets/hm3d/semantic`

The official episode files refer to scenes as `hm3d/val/...`, while the local
downloaded assets are laid out as `hm3d/habitat/...`. A runner-local resolver is
needed to map this without mutating the dataset.

## System Boundary

The new runner owns:

- reading official ObjectNav `content/*.json.gz` files
- resolving `hm3d/val/<scene>/<scene>.basis.glb` to local `.basis.glb`
- generating a run-local Habitat scene dataset config with absolute scene paths
- resetting Habitat-Sim agents to official episode start poses
- extracting target-category semantic masks from Habitat semantic observations
- applying the existing YOLO-breaker mask corruptions
- updating usability memory and exporting trace/summary/report artifacts

It depends on:

- Habitat-Sim in the `habitat` conda environment
- existing `objectnav_core.memory.usability`
- existing semantic mask corruption and evidence helpers
- local HM3D scene and ObjectNav assets

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Episode directory | `objectnav_hm3d_v1/val_mini` | Reads `content/*.json.gz` |
| Input | Scene root | `scene_datasets/hm3d` | Expects `habitat/` and optional `semantic/` |
| Input | Breaker modes | CSV CLI string | `clean,miss,fly_point,edge_break,mixed` |
| Output | Trace | CSV | One row per reset/action observation |
| Output | Summary | JSON | Counts by evidence, decision, breaker mode, and scene |
| Output | Report | HTML | Human-readable experiment summary |
| Output | Run-local scene config | JSON | Stored under the run output directory |

## Interfaces

- Python API:
  `run_habitat_objectnav_valmini_semantic_stress(output_dir, dataset_dir, scene_root, ...)`
- CLI:
  `python -m objectnav_core.cli.run_habitat_objectnav_valmini_semantic_stress`
- Console script:
  `objectnav_habitat_objectnav_valmini_semantic_stress`
- Artifacts:
  `objectnav_valmini_semantic_trace.csv`, `summary.json`, `report.html`,
  `hm3d_valmini_annotated_basis.scene_dataset_config.json`

## Data Flow

1. Load official `val_mini/content/*.json.gz` files.
2. Select up to `--max-episodes` episodes.
3. Resolve each episode scene path from `hm3d/val/...` to the local scene root.
4. Generate one run-local scene dataset config containing the resolved scenes.
5. For each scene group, create a Habitat-Sim RGB-D-semantic simulator.
6. For each episode, set the agent to the official start pose.
7. For reset and each scripted action, extract an oracle target mask for the
   episode object category.
8. Apply the configured YOLO-breaker mode.
9. Classify evidence, update usability memory, choose a trust/verify/search
   decision, and append a trace row.
10. Export CSV, JSON, and HTML artifacts.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Episode scene path does not map to a local `.basis.glb` | `FileNotFoundError` during dataset load | Include missing scene id in error |
| Scene lacks navmesh | Simulator pathfinder reports unloaded | Mark scene invalid and fail the run |
| Scene semantic metadata is missing | Semantic object/category count is zero | Fail before claiming semantic stress |
| Target category has no semantic ids in the scene | Empty category-id map | Rows become `UNKNOWN` with explicit reason |
| Target is not visible under scripted actions | Oracle target pixels stay below threshold | Export `target_not_visible` rows; do not treat absence as `FREE` |
| Corrupt masks survive quality gates | Positive with low precision | Count `false_positive_positive_rows` |

## Verification Plan

- Unit tests for:
  - official episode loading from `.json.gz`
  - `hm3d/val` to local `hm3d/habitat` path resolution
  - run-local scene dataset config generation
  - target-category semantic id lookup
  - evidence behavior when a target category is absent or out of view
- Import test to ensure Habitat imports remain lazy.
- Run a one-episode probe against `TEEsavR23oF`.
- Run the full local `val_mini` set: 30 episodes, 7 rows each.
- Run all Python tests and `compileall`.

## Research Relevance

This bridges the prior synthetic semantic stress test to official ObjectNav
episode metadata. It supports claims about semantic evidence robustness under
ObjectNav-like starts and target categories, while keeping the limitation clear:
the action sequence is scripted and no official ObjectNav policy metrics are
reported.

## Open Questions

- How much should positive evidence require temporal or multi-view confirmation?
- Should the next runner use a learned or classical navigation policy to make
  target visibility less dependent on scripted actions?
- Should real YOLO masks replace oracle semantic-mask corruptions after the
  memory stress thresholds are stable?
