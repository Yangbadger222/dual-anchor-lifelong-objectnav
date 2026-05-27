# Experiment Report: Habitat-Lab ObjectNav Smoke

Date: 2026-05-27  
Owner: Codex  
Status: Completed

## Question

Can the local `habitat` conda environment run a complete Habitat scene-load, Habitat-Lab `ObjectNav-v1` episode reset/step, and trace export? Can it progress from a toy test asset to a real HM3D scene?

## Hypothesis

After installing Habitat-Lab v0.3.3 to match the existing Habitat-Sim v0.3.3 install, a synthetic one-episode ObjectNav task should run on both a local Habitat-Sim test scene and an HM3D example scene, writing RGB-D trace artifacts.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `db13f53`, dirty worktree |
| Machine | `badger-linux`, Ubuntu Linux 6.8.0-111-generic, NVIDIA RTX 4070 Laptop GPU |
| Dataset / scene | `simple_room.glb`; HM3D example `GLAQ4DNUx5U.basis.glb` |
| Simulator / robot | Habitat-Lab 0.3.3 + Habitat-Sim 0.3.3, no robot |
| Python / env | conda env `habitat`, Python 3.9.23 |
| Key parameters | seed `23`, sensor sizes `64` and `128`, deterministic action sequences |

## Command

Habitat-Lab install followed the Habitat-Lab v0.3.3 README pattern: clone the repo and install the `habitat-lab` package in editable mode.

```bash
git clone --branch v0.3.3 --depth 1 https://github.com/facebookresearch/habitat-lab.git third_party/habitat-lab
conda run -n habitat python -m pip install -e third_party/habitat-lab/habitat-lab
conda run -n habitat python -m pip install 'pillow==10.4.0'
conda run -n habitat python -m pip install jinja2 typeguard
conda run -n habitat python -m pip check
```

Official Habitat-Sim test data download was attempted:

```bash
mkdir -p datasets/habitat
conda run -n habitat python -m habitat_sim.utils.datasets_download \
  --uids habitat_test_scenes habitat_test_pointnav_dataset \
  --data-path datasets/habitat/ \
  --no-replace
```

It failed because Hugging Face timed out:

```text
fatal: unable to access 'https://huggingface.co/datasets/ai-habitat/habitat_test_scenes.git/': Failed to connect to huggingface.co port 443
```

Toy scene smoke command:

```bash
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_objectnav_smoke \
  --scene /home/badger/Desktop/habitat-sim-main/data/test_assets/scenes/simple_room.glb \
  --output runs/habitat_usability/smoke \
  --seed 23 \
  --sensor-size 64
```

HM3D official-scene smoke command:

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

Additional official-data attempts:

```bash
conda install -n habitat -c conda-forge git-lfs -y
conda run -n habitat python -m habitat_sim.utils.datasets_download \
  --uids habitat_test_pointnav_dataset \
  --data-path datasets/habitat/ \
  --no-replace
conda run -n habitat python -m habitat_sim.utils.datasets_download \
  --uids hm3d_example_full \
  --data-path datasets/habitat/ \
  --no-replace
```

`habitat_test_pointnav_dataset` and `hm3d_example_full` downloaded successfully. Hugging Face `habitat_test_scenes` and DropBox ObjectNav episode links failed from the current network.

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Toy scene smoke | passed | `simple_room.glb`, 6 trace rows |
| HM3D scene smoke | passed | `GLAQ4DNUx5U.basis.glb`, 7 trace rows |
| HM3D navmesh loaded | true | Start/target sampled from pathfinder |
| HM3D semantic metadata | 908 objects / 124 categories | Detected in scene probe |
| HM3D episode over | true | Final `stop` action ended the synthetic episode |
| HM3D observation keys | 5 | `compass`, `depth`, `gps`, `objectgoal`, `rgb` |
| HM3D mean depth valid ratio | 1.0 | From exported trace rows |
| HM3D mean depth | 1.299647 | Meters after disabling normalized depth |
| HM3D collision steps | 0 | Deterministic action sequence did not collide |
| Official HM3D ObjectNav episodes | downloaded | HM3D v1 episode archive is local; referenced HM3D v0.1 scene assets require credentials |

## Observations

- `habitat` and `habitat_sim` now both import at version 0.3.3.
- `pip check` passes after installing `jinja2`, `typeguard`, and matching `pillow==10.4.0`.
- Habitat printed duplicate plugin warnings and a Gym deprecation warning, but the smoke completed.
- Habitat-Sim warned that `simple_room.glb` has no semantic annotations, so this smoke cannot support oracle semantic evidence.
- The HM3D scene smoke detected semantic scene metadata in the probe, but the current RGB-D smoke does not export semantic observations.
- Both smoke runs use an in-memory synthetic ObjectNav dataset, not an official benchmark split.
- The official HM3D ObjectNav v1 episode archive was downloaded after this smoke, but its `val_mini` scenes are not present locally.
- Task measurements were disabled, so this report does not contain success, SPL, geodesic distance, or benchmark navigation metrics.
- HM3D scene-dataset config emitted many missing-glob warnings for splits not present in the example subset; the selected example scene still loaded and ran.

## Result

The local machine can now run a complete Habitat-Lab ObjectNav plumbing smoke on both a toy Habitat-Sim asset and a real HM3D example scene: scene load, `ObjectNav-v1` reset/step, RGB-D observation capture, and trace export all completed.

This is a valid integration smoke result and a real-scene simulation preflight. It is not a Habitat ObjectNav benchmark result and not yet evidence for the usability-memory research claim.

## Follow-up

- Provide Matterport/HM3D credentials or offline HM3D v0.1 val/minival scene assets under ignored `datasets/habitat/`.
- Run an official ObjectNav episode with task measurements enabled.
- Extend the trace exporter from depth/RGB health rows to `EvidenceEvent` rows consumed by `UsabilityUpdater`.
