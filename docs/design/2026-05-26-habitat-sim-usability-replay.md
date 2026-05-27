# Design Doc: Habitat-Sim Usability Memory Replay

Date: 2026-05-26  
Owner: Codex  
Status: Active

## Goal

Define the next simulation layer for evaluating the usability-centered ObjectNav memory algorithm in Habitat-Sim before real RGB-D/RTK robot experiments.

The initial 2026-05-26 output was an operation guide and repository structure. The first executable 2026-05-27 slice is a synthetic Habitat-Lab ObjectNav smoke that verifies scene loading, `ObjectNav-v1` reset/step, RGB-D observation capture, and trace export before downloading large official ObjectNav datasets.

The next 2026-05-27 slice adds a semantic-mask stress path: Habitat-Sim exports RGB-D-semantic observations directly, an oracle visible semantic id is selected as the target for each episode, and deterministic "YOLO breaker" corruptions are injected into the target mask before evidence extraction. This is intended to stress the usability-memory update policy against detector-like failures before adding a real detector.

## Non-Goals

- Do not add a detector, GroundingDINO, VLM, or learned perception model.
- Do not claim Habitat leaderboard performance.
- Do not commit Habitat datasets, scene assets, simulator clones, videos, or generated traces.
- Do not replace the existing 2D grid trace or localization bag audit.
- Do not treat the synthetic smoke as a benchmark result, SPL result, or semantic-memory result.

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

Implemented synthetic smoke CLI:

```bash
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_objectnav_smoke \
  --scene /home/badger/Desktop/habitat-sim-main/data/test_assets/scenes/simple_room.glb \
  --output runs/habitat_usability/smoke \
  --seed 23 \
  --sensor-size 64
```

This writes:

- `runs/habitat_usability/smoke/habitat_trace.csv`
- `runs/habitat_usability/smoke/summary.json`
- `runs/habitat_usability/smoke/report.html`

The CLI imports Habitat only inside the smoke runner so normal `objectnav_core` imports and tests remain ROS/Habitat-free. It creates a one-episode synthetic ObjectNav dataset in memory, disables Habitat task measurements to avoid requiring a benchmark navmesh, and records RGB-D/depth-health trace rows. It is not the final usability-memory replay CLI.

Implemented HM3D official-scene smoke CLI:

```bash
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_objectnav_smoke \
  --scene datasets/habitat/scene_datasets/hm3d/example/00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb \
  --scene-dataset-config datasets/habitat/scene_datasets/hm3d/example/hm3d_annotated_basis.scene_dataset_config.json \
  --output runs/habitat_usability/hm3d_official_scene_smoke \
  --seed 23 \
  --sensor-size 128 \
  --sample-navigable \
  --actions move_forward,turn_left,move_forward,turn_right,move_forward
```

This run uses a real HM3D example scene and navmesh-sampled synthetic start/target points. It still uses a synthetic ObjectNav episode. HSSD/ProcTHOR ObjectNav episode downloads from DropBox were blocked, and the official HM3D ObjectNav episodes downloaded later still require official HM3D v0.1 scene assets before benchmark execution.

Implemented multi-episode usability replay CLI:

```bash
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_usability_replay \
  --scene datasets/habitat/scene_datasets/hm3d/example/00337-CFVBbU9Rsyb/CFVBbU9Rsyb.basis.glb \
  --scene datasets/habitat/scene_datasets/hm3d/example/00770-NBg5UqG3di3/NBg5UqG3di3.basis.glb \
  --scene datasets/habitat/scene_datasets/hm3d/example/00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb \
  --scene-dataset-config datasets/habitat/scene_datasets/hm3d/example/hm3d_annotated_basis.scene_dataset_config.json \
  --output runs/habitat_usability/hm3d_usability_replay_30ep \
  --episodes 30 \
  --seed 101 \
  --sensor-size 96
```

This runner cycles three HM3D example scenes and three synthetic-anchor scenarios, exports aggregate Habitat trace rows, converts depth/collision/target-distance proxies into `EvidenceEvent` rows, and replays them through `UsabilityUpdater` and `UsabilityDecisionPolicy`. It is an algorithm plumbing and decision-behavior test, not an official ObjectNav benchmark.

Target semantic stress CLI shape:

```bash
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_semantic_yolo_stress \
  --scene datasets/habitat/scene_datasets/hm3d/example/00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb \
  --scene-dataset-config datasets/habitat/scene_datasets/hm3d/example/hm3d_annotated_basis.scene_dataset_config.json \
  --output runs/habitat_usability/hm3d_semantic_yolo_stress \
  --episodes 30 \
  --seed 211 \
  --sensor-size 96
```

This runner should write:

- `semantic_yolo_trace.csv`
- `summary.json`
- `report.html`

The detector-like breaker modes are:

- `miss`: drop all or part of the target semantic mask to simulate YOLO false negatives.
- `fly_point`: inject small disconnected false-positive target blobs.
- `edge_break`: leak or cut target pixels at mask boundaries to simulate edge failures.
- `mixed`: combine the above.

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

2026-05-27 synthetic smoke data flow:

1. Load a local Habitat-Sim test scene asset.
2. Create one synthetic Habitat-Lab `ObjectNav-v1` episode in memory.
3. Reset the Habitat-Lab environment and run deterministic actions.
4. Capture `rgb`, `depth`, `gps`, `compass`, and `objectgoal` observations.
5. Export per-step rows with agent pose, objectgoal id, depth health, RGB statistics, collision flags, and synthetic target distance.
6. Write `habitat_trace.csv`, `summary.json`, and `report.html`.

2026-05-27 multi-episode replay data flow:

1. Run the synthetic Habitat-Lab ObjectNav smoke repeatedly over HM3D example scenes.
2. Cycle synthetic-anchor scenarios: requested near anchor, local verification radius, and random navmesh anchor.
3. Convert each trace row into `UNKNOWN`, `POSITIVE`, `FREE`, `NON_CONFIRMATION`, or `ACCESS_BLOCKED` evidence using deterministic depth/collision/distance proxies.
4. Update `MemoryBelief` with `UsabilityUpdater`.
5. Query `UsabilityDecisionPolicy` for `TRUST`, `VERIFY`, `SEARCH`, or `RETIRE`.
6. Write aggregate `habitat_trace.csv`, `usability_replay.csv`, `summary.json`, and `report.html`.

2026-05-27 semantic YOLO-breaker stress data flow:

1. Load a semantic HM3D scene in Habitat-Sim with RGB, depth, and semantic sensors.
2. Sample a navigable start and observe a semantic frame.
3. Select a visible semantic id as the episode target.
4. Step a deterministic action sequence while recording semantic masks.
5. Convert the target-id mask into an oracle target mask.
6. Corrupt the oracle target mask with miss, fly-point, edge-break, or mixed breaker modes.
7. Extract detector-quality metrics: area, oracle recall, false-positive ratio, edge-touch ratio, component count, largest-component ratio, and depth health.
8. Convert the corrupted mask into `EvidenceEvent` values and replay the current usability memory policy.
9. Report belief collapse, false-positive confirmations, missed-visible-target rows, and decision distribution.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Habitat install breaks local environment | Keep Habitat in separate conda env and ignored `third_party/` / `datasets/` paths | Do not add Habitat as core dependency until smoke passes. |
| Oracle semantic makes results too optimistic | Label first stage as oracle upper-bound | Add detector replay only after algorithm trace path works. |
| FREE evidence is too rare | UNKNOWN ratio stays high | Report it explicitly; sweep thresholds before claiming success. |
| FREE evidence is too aggressive | False deletion rises | Gate FREE by depth health and edge invalid ratio. |
| Verification dominates decisions | Verify ratio and path-cost regret are high | Add geodesic cost and opportunistic verification ablations. |
| Datasets accidentally enter git | `.gitignore` covers dataset, scene, video, and asset extensions | Keep generated artifacts under `runs/`. |
| Smoke overclaims benchmark readiness | `summary.json` marks `benchmark_dataset: false` | Require official scene and ObjectNav episode datasets before SPL/success claims. |
| Habitat-Sim test scene lacks semantic annotations | Simulator warning and report `limits` field | Use this only for plumbing; switch to HM3D/HSSD/MP3D semantic assets for oracle evidence. |
| Official dataset download blocked | Download command exits non-zero | Use local test assets for smoke; retry download or provide offline dataset later. |
| Semantic mask ids do not map to target objects | Zero visible target mask or unknown id | Select target ids from actually visible semantic observations and record category if available. |
| YOLO breaker becomes too destructive to interpret | Positive/negative evidence collapses to one class | Run clean, miss, fly-point, edge-break, and mixed modes side by side. |
| Flying-point positives create ghost confidence | High positive count with low oracle IoU | Track false-positive-positive rows and compare final `p_valid` by breaker mode. |
| Edge-break masks look like valid detections | High edge-touch or fragmented components | Add mask-quality gates before emitting high-strength `POSITIVE` evidence. |

## Verification Plan

- Docs-only for this task:
  - confirm the HTML guide exists
  - confirm repository file-management doc exists
  - confirm `.gitignore` covers Habitat datasets and generated artifacts
  - run core tests to ensure repo cleanup did not break Python package state
- Future implementation:
  - unit-test trace schema and evidence extraction without Habitat
  - run a synthetic Habitat-Lab ObjectNav smoke
  - run 20-episode official Habitat ObjectNav smoke
  - run 500+ episode depth/occlusion stress
  - write experiment reports for each run

2026-05-27 verification completed:

- Installed Habitat-Lab v0.3.3 into the existing `habitat` conda environment.
- Verified `habitat` and `habitat_sim` imports at version 0.3.3.
- Ran the synthetic ObjectNav smoke on `simple_room.glb`.
- Verified trace, summary, and report artifacts exist under ignored `runs/habitat_usability/smoke`.
- Official `habitat_test_scenes` download from Hugging Face timed out; official ObjectNav datasets were not downloaded.
- Installed `git-lfs` inside the `habitat` conda environment.
- Downloaded HM3D example full assets under ignored `datasets/habitat/`.
- Downloaded the official Habitat test PointNav episode zip under ignored `datasets/habitat/`.
- Ran the smoke on a real HM3D example scene with navmesh sampling and wrote artifacts under ignored `runs/habitat_usability/hm3d_official_scene_smoke`.
- DropBox ObjectNav episode links remained unreachable from this network, so official ObjectNav benchmark episodes are still pending.
- Downloaded the official HM3D ObjectNav v1 episode zip from `dl.fbaipublicfiles.com`, extracted it under ignored `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1`, and added a local `v1` symlink.
- Verified the official episode archive contains `val_mini` with 30 episodes over 2 scenes and `val` with 2000 episodes over 20 scenes, but local HM3D v0.1 scene assets are missing.
- Attempting `hm3d_minival_v0.1` scene download failed because the Habitat downloader requires a Matterport/HM3D username.
- Ran the 30-episode HM3D example usability replay and wrote artifacts under ignored `runs/habitat_usability/hm3d_usability_replay_30ep`.
- Verified Habitat-Sim direct semantic sensor output on HM3D `GLAQ4DNUx5U`; the semantic mask is a `uint32` id image.
- Ran the 30-episode semantic YOLO-breaker stress and wrote artifacts under ignored `runs/habitat_usability/hm3d_semantic_yolo_stress_30ep`.
- Semantic stress metrics: `POSITIVE=71`, `NON_CONFIRMATION=13`, `UNKNOWN=126`, mean final `p_valid=0.819062`, 9 false-positive-positive rows, and 16 missed-visible-target rows.

## Research Relevance

Habitat-Sim is the bridge between synthetic 2D logic tests and real XJTLU robot logs. It can directly test whether the proposed memory state separation avoids two reviewer-critical failures:

- false deletion from depth artifacts and occlusion
- ghost retention when objects are moved or removed

The first Habitat result should be framed as simulation evidence and ablation support, not as real-robot validation.

## Open Questions

- Which scene dataset is easiest to install on the available machine: Replica, ReplicaCAD, HM3D, or MP3D?
- Should the first Habitat adapter live in `objectnav_core` with optional imports, or in a separate `src/objectnav_habitat` package?
- Should geodesic distance come from Habitat pathfinder directly or from a cached topological approximation?
