# Design Doc: Habitat-Sim Usability Memory Replay

Date: 2026-05-26  
Owner: Codex  
Status: Draft

## Goal

Define the next simulation layer for evaluating the usability-centered ObjectNav memory algorithm in Habitat-Sim before real RGB-D/RTK robot experiments.

The immediate output is an operation guide and repository structure, not executable Habitat integration code.

## Non-Goals

- Do not run Habitat-Sim in this task.
- Do not add a detector, GroundingDINO, VLM, or learned perception model.
- Do not claim Habitat leaderboard performance.
- Do not commit Habitat datasets, scene assets, simulator clones, videos, or generated traces.
- Do not replace the existing 2D grid trace or localization bag audit.

## Background

The project now has three lower-cost validation layers:

1. deterministic Phase 1A core trials
2. 2D statistical grid trace stress tests
3. localization-only XJTLU bag audits

The missing middle layer is sensor-realistic indoor simulation. Habitat-Sim can provide RGB-D, agent state, scene geometry, and semantic/oracle visibility, which lets the algorithm face depth holes, occlusion, view geometry, and realistic navigation costs before the real robot stack is ready.

## System Boundary

The Habitat replay layer should own:

- Habitat scene loading
- RGB-D and agent-state sampling
- oracle semantic/object visibility for first-stage evidence extraction
- conversion to a stable trace schema
- offline replay through `UsabilityUpdater` and `UsabilityDecisionPolicy`
- report generation for evidence and decision metrics

It should not own:

- object detector training
- real robot ROS 2 launch
- RTK/GNSS fusion
- Nav2 controller tuning
- dataset storage inside git

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Habitat scene | Dataset asset path | Stored under ignored `datasets/habitat/scene_datasets/`. |
| Input | Config | YAML | Suggested path: `configs/habitat/usability_smoke.yaml`. |
| Input | Episode count / seed | CLI flags | Must be deterministic. |
| Output | `habitat_trace.csv` | CSV | Intermediate trace compatible with future XJTLU replay. |
| Output | `summary.json` | JSON | Evidence counts, decision counts, and failure metrics. |
| Output | `report.html` | HTML | Human-readable result report. |
| Output | optional debug frames | PNG/MP4 | Ignored under `runs/`. |

## Interfaces

Target CLI shape:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_habitat_usability_replay \
  --config configs/habitat/usability_smoke.yaml \
  --scene datasets/habitat/scene_datasets/replica/room_0/habitat/mesh_semantic.ply \
  --output runs/habitat_usability/smoke \
  --episodes 20 \
  --max-steps 250 \
  --seed 23
```

Operation guide:

```text
docs/simulation/2026-05-26-habitat-sim-usability-memory.zh.html
```

## Data Flow

1. Load Habitat scene and configure RGB-D sensors.
2. Select target category and target object using oracle scene annotations.
3. Step agent through sampled or Habitat-provided ObjectNav episodes.
4. For each step, compute depth health, visibility, occlusion, ray-free indicators, and navigation cost proxies.
5. Convert those signals into `EvidenceEvent`-compatible trace rows.
6. Replay trace rows through the current usability-memory updater and decision policy.
7. Compare against baselines such as last-seen memory, conservative unknown, and log-odds occupancy memory.
8. Write CSV, JSON, and HTML artifacts.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Habitat install breaks local environment | Keep Habitat in separate conda env and ignored `third_party/` / `datasets/` paths | Do not add Habitat as core dependency until smoke passes. |
| Oracle semantic makes results too optimistic | Label first stage as oracle upper-bound | Add detector replay only after algorithm trace path works. |
| FREE evidence is too rare | UNKNOWN ratio stays high | Report it explicitly; sweep thresholds before claiming success. |
| FREE evidence is too aggressive | False deletion rises | Gate FREE by depth health and edge invalid ratio. |
| Verification dominates decisions | Verify ratio and path-cost regret are high | Add geodesic cost and opportunistic verification ablations. |
| Datasets accidentally enter git | `.gitignore` covers dataset, scene, video, and asset extensions | Keep generated artifacts under `runs/`. |

## Verification Plan

- Docs-only for this task:
  - confirm the HTML guide exists
  - confirm repository file-management doc exists
  - confirm `.gitignore` covers Habitat datasets and generated artifacts
  - run core tests to ensure repo cleanup did not break Python package state
- Future implementation:
  - unit-test trace schema and evidence extraction without Habitat
  - run 20-episode Habitat smoke
  - run 500+ episode depth/occlusion stress
  - write experiment reports for each run

## Research Relevance

Habitat-Sim is the bridge between synthetic 2D logic tests and real XJTLU robot logs. It can directly test whether the proposed memory state separation avoids two reviewer-critical failures:

- false deletion from depth artifacts and occlusion
- ghost retention when objects are moved or removed

The first Habitat result should be framed as simulation evidence and ablation support, not as real-robot validation.

## Open Questions

- Which scene dataset is easiest to install on the available machine: Replica, ReplicaCAD, HM3D, or MP3D?
- Should the first Habitat adapter live in `objectnav_core` with optional imports, or in a separate `src/objectnav_habitat` package?
- Should geodesic distance come from Habitat pathfinder directly or from a cached topological approximation?

