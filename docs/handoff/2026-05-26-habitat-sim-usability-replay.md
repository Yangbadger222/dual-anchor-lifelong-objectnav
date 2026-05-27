# Handoff: Habitat-Sim Usability Memory Replay

Date: 2026-05-26  
Owner: Codex  
Status: Official Val-Mini Semantic Stress Completed; Benchmark Metrics Still Pending

## Current State

The Habitat-Sim step now has both documentation and executable code. The repository has a synthetic Habitat-Lab ObjectNav smoke, an HM3D real-scene smoke, a multi-episode Habitat usability replay that feeds trace-derived evidence into `UsabilityUpdater` and `UsabilityDecisionPolicy`, a semantic-mask YOLO-breaker stress runner using Habitat-Sim RGB-D-semantic sensors, and an official HM3D ObjectNav `val_mini` semantic stress runner.

The official HM3D ObjectNav v1 episode archive has been downloaded under ignored `datasets/habitat/`. The local `scene_datasets/hm3d/habitat` and `scene_datasets/hm3d/semantic` assets include the two `val_mini` scene ids, so the new runner maps official `hm3d/val/...` episode paths onto the local `hm3d/habitat/...` layout. This supports semantic stress against official episode metadata, but it is still not an official benchmark result because the run uses goal viewpoints/scripted actions and reports no success/SPL.

2026-05-27 environment checkpoint:

- The user reported that the current development setup is already in a ROS 2 environment and that the conda environment named `habitat` is configured well enough to run simulation.
- Codex verified that `/opt/ros/humble/bin/ros2` is visible from the current shell.
- Codex verified that sourcing `install/setup.zsh` exposes the local `objectnav_ros` and `objectnav_core` ROS 2 packages.
- Codex verified that conda environment `habitat` exists, uses Python 3.9.23, and can import `habitat_sim` version 0.3.3.
- Codex did not verify a full Habitat scene run, ObjectNav episode replay, trace export, or memory replay.
- Codex did not verify Habitat-Lab; `import habitat` failed in `conda run -n habitat`, and `pip show` did not find `habitat-lab`. Treat commands that require the `habitat` Python package as pending until Habitat-Lab is installed or placed on `PYTHONPATH`.

2026-05-27 synthetic ObjectNav smoke update:

- Habitat-Lab v0.3.3 was cloned to ignored `third_party/habitat-lab` and installed into the existing `habitat` conda environment.
- `habitat` and `habitat_sim` now both import at version 0.3.3.
- `pip check` passes after pinning `pillow==10.4.0` and installing `jinja2` and `typeguard`.
- Added `objectnav_core.evaluation.habitat_objectnav_smoke` and `objectnav_core.cli.run_habitat_objectnav_smoke`.
- Ran a synthetic one-episode Habitat-Lab `ObjectNav-v1` smoke on `/home/badger/Desktop/habitat-sim-main/data/test_assets/scenes/simple_room.glb`.
- The smoke wrote ignored artifacts under `runs/habitat_usability/smoke`: `habitat_trace.csv`, `summary.json`, and `report.html`.
- Official Habitat test-scene download from Hugging Face timed out, so no official ObjectNav benchmark dataset was run.

2026-05-27 HM3D official-scene smoke update:

- Installed `git-lfs` inside the `habitat` conda environment.
- Downloaded `habitat_test_pointnav_dataset` successfully under ignored `datasets/habitat/`.
- Downloaded `hm3d_example_full` successfully under ignored `datasets/habitat/`.
- Ran the synthetic one-episode Habitat-Lab `ObjectNav-v1` smoke on real HM3D scene `GLAQ4DNUx5U.basis.glb`.
- The run sampled synthetic start/target positions from the HM3D navmesh and wrote ignored artifacts under `runs/habitat_usability/hm3d_official_scene_smoke`.
- HM3D scene probe detected 908 semantic objects and 124 semantic categories. The current RGB-D trace does not export semantic observations yet.
- HSSD/ProcTHOR ObjectNav episode downloads remained blocked: Hugging Face `habitat_test_scenes` clone failed, and DropBox ObjectNav episode links reset/timed out. The HM3D ObjectNav episode archive was downloaded later from `dl.fbaipublicfiles.com`.

2026-05-27 multi-episode usability replay update:

- Downloaded the official HM3D ObjectNav v1 episode archive from `dl.fbaipublicfiles.com`.
- Extracted it to ignored `datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1` and added ignored symlink `datasets/habitat/datasets/objectnav/hm3d/v1`.
- Verified `val_mini` has 30 episodes over 2 official HM3D scenes and `val` has 2000 episodes over 20 official HM3D scenes.
- Verified none of those official HM3D v0.1 val scene assets are present locally.
- Attempted `hm3d_minival_v0.1`; Habitat-Sim downloader failed with `Username required`.
- Added `objectnav_core.evaluation.habitat_usability_replay` and `objectnav_core.cli.run_habitat_usability_replay`.
- Ran 30 synthetic ObjectNav-v1 Habitat episodes over the three downloaded HM3D example scenes.
- The replay wrote aggregate artifacts under ignored `runs/habitat_usability/hm3d_usability_replay_30ep`.
- Main result: 30 episodes, 210 replay rows, evidence counts `positive=62`, `free=27`, `non_confirmation=44`, `access_blocked=47`, `unknown=30`; decision counts `verify=128`, `trust=26`, `search=27`, `retire=29`.

2026-05-27 semantic YOLO-breaker stress update:

- Added `objectnav_core.evaluation.habitat_semantic_yolo_stress` and `objectnav_core.cli.run_habitat_semantic_yolo_stress`.
- Verified Habitat-Sim direct semantic sensor output on HM3D `GLAQ4DNUx5U`; `semantic` observations are `uint32` id masks.
- Implemented synthetic detector corruption modes over target semantic masks: `miss`, `fly_point`, `edge_break`, and `mixed`, plus a `clean` baseline.
- Added mask-quality metrics: oracle recall, detector precision, false-positive ratio, component count, largest-component ratio, and edge-touch ratio.
- Converted corrupted masks into `EvidenceEvent` rows and replayed them through `UsabilityUpdater` and `UsabilityDecisionPolicy`.
- Ran 30 semantic stress episodes under ignored `runs/habitat_usability/hm3d_semantic_yolo_stress_30ep`.
- Main result: 30 episodes, 210 rows, evidence counts `positive=71`, `non_confirmation=13`, `unknown=126`; decision counts `verify=176`, `trust=34`; mean final `p_valid=0.819062`.
- Stress signals: clean mean final `p_valid=0.908939`, miss mean `0.610724`, fly-point mean `0.847893`, edge-break mean `0.866955`, mixed mean `0.860801`; mixed produced 9 false-positive-positive rows and miss produced 16 missed-visible-target rows.

2026-05-27 official ObjectNav val_mini semantic stress update:

- Added `objectnav_core.evaluation.habitat_objectnav_valmini_semantic_stress` and `objectnav_core.cli.run_habitat_objectnav_valmini_semantic_stress`.
- The runner reads `objectnav_hm3d_v1/val_mini/content/*.json.gz`, resolves official `hm3d/val/...` scene ids to the local `hm3d/habitat/...` layout, and writes a run-local Habitat scene dataset config.
- It extracts semantic masks for official target categories, applies the same YOLO-breaker modes, and feeds evidence into usability memory.
- Ran a 1-episode probe and a full 30-episode `val_mini` stress under ignored `runs/habitat_usability/hm3d_valmini_semantic_stress_30ep`.
- Main result: 30 episodes, 210 rows, target-visible episodes `27`, evidence counts `positive=58`, `non_confirmation=9`, `unknown=143`; decision counts `verify=175`, `trust=35`; mean final `p_valid=0.757149`.
- Stress signals: clean mean final `p_valid=0.970945`, miss mean `0.569045`, fly-point mean `0.780606`, edge-break mean `0.721548`, mixed mean `0.743600`; mixed produced 4 false-positive-positive rows and miss produced 11 missed-visible-target rows.

## Files Touched

- `README.md`
- `.gitignore`
- `docs/README.md`
- `docs/repository-file-management.md`
- `docs/design/2026-05-26-habitat-sim-usability-replay.md`
- `docs/simulation/README.md`
- `docs/simulation/2026-05-26-habitat-sim-usability-memory.zh.html`
- `docs/handoff/2026-05-26-habitat-sim-usability-replay.md`
- `docs/devlog/2026-05.md`

2026-05-27 synthetic smoke files:

- `README.md`
- `docs/README.md`
- `docs/repository-file-management.md`
- `docs/design/2026-05-26-habitat-sim-usability-replay.md`
- `docs/experiments/2026-05-27-habitat-objectnav-smoke.md`
- `docs/handoff/2026-05-26-habitat-sim-usability-replay.md`
- `docs/devlog/2026-05.md`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_objectnav_smoke.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_objectnav_smoke.py`
- `src/objectnav_core/tests/test_habitat_objectnav_smoke.py`
- `src/objectnav_core/tests/test_ros_packaging.py`

2026-05-27 HM3D official-scene smoke additional files:

- `README.md`
- `docs/design/2026-05-26-habitat-sim-usability-replay.md`
- `docs/experiments/2026-05-27-habitat-objectnav-smoke.md`
- `docs/handoff/2026-05-26-habitat-sim-usability-replay.md`
- `src/objectnav_core/objectnav_core/cli/run_habitat_objectnav_smoke.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_objectnav_smoke.py`

2026-05-27 multi-episode replay additional files:

- `README.md`
- `docs/README.md`
- `docs/repository-file-management.md`
- `docs/design/2026-05-26-habitat-sim-usability-replay.md`
- `docs/experiments/2026-05-27-habitat-objectnav-smoke.md`
- `docs/experiments/2026-05-27-habitat-usability-replay.md`
- `docs/handoff/2026-05-26-habitat-sim-usability-replay.md`
- `docs/devlog/2026-05.md`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_objectnav_smoke.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_usability_replay.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_objectnav_smoke.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_usability_replay.py`
- `src/objectnav_core/tests/test_habitat_usability_replay.py`
- `src/objectnav_core/tests/test_ros_packaging.py`

2026-05-27 semantic YOLO-breaker stress additional files:

- `README.md`
- `docs/README.md`
- `docs/repository-file-management.md`
- `docs/design/2026-05-26-habitat-sim-usability-replay.md`
- `docs/experiments/2026-05-27-habitat-semantic-yolo-stress.md`
- `docs/handoff/2026-05-26-habitat-sim-usability-replay.md`
- `docs/devlog/2026-05.md`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_semantic_yolo_stress.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_semantic_yolo_stress.py`
- `src/objectnav_core/tests/test_habitat_semantic_yolo_stress.py`
- `src/objectnav_core/tests/test_ros_packaging.py`

2026-05-27 official ObjectNav val_mini semantic stress additional files:

- `README.md`
- `docs/README.md`
- `docs/repository-file-management.md`
- `docs/design/2026-05-27-habitat-val-mini-semantic-stress.md`
- `docs/experiments/2026-05-27-habitat-objectnav-valmini-semantic-stress.md`
- `docs/handoff/2026-05-26-habitat-sim-usability-replay.md`
- `docs/devlog/2026-05.md`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_objectnav_valmini_semantic_stress.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_objectnav_valmini_semantic_stress.py`
- `src/objectnav_core/tests/test_habitat_objectnav_valmini_semantic_stress.py`
- `src/objectnav_core/tests/test_ros_packaging.py`

## Commands Run

```bash
git status --short --branch
find . -maxdepth 3 -type f | sed 's#^./##' | sort | head -240
find docs -maxdepth 3 -type f | sort
find src -maxdepth 5 -type f | sort
find . -name '.DS_Store' -delete
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
rm -rf .pytest_cache
git check-ignore -v .DS_Store docs/.DS_Store src/.DS_Store runs/.DS_Store runs/grid_trace/latest/events.csv runs/localization_bag_audit/latest/summary.json datasets/habitat/foo.glb third_party/habitat-sim/foo
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests -q
python3 -m compileall -q src/objectnav_core/objectnav_core
```

2026-05-27 environment checkpoint commands:

```bash
git status --short --branch
rg -n "Habitat|habitat|ROS 2|ros2|simulation|仿真" docs src || true
rg --files docs | sort
sed -n '1,220p' docs/repository-file-management.md
sed -n '1,260p' docs/design/2026-05-26-habitat-sim-usability-replay.md
sed -n '1,260p' docs/handoff/2026-05-26-habitat-sim-usability-replay.md
tail -n 220 docs/devlog/2026-05.md
which ros2
ros2 pkg list | head -40
printf 'CONDA_DEFAULT_ENV=%s\n' "$CONDA_DEFAULT_ENV"
which conda
conda info --envs
python - <<'PY'
import sys
print(sys.executable)
for name in ("habitat", "habitat_sim"):
    try:
        module = __import__(name)
        version = getattr(module, "__version__", "unknown")
        print(f"{name}: import ok, version={version}")
    except Exception as exc:
        print(f"{name}: import failed: {type(exc).__name__}: {exc}")
PY
conda run -n habitat python - <<'PY'
import sys
print(sys.executable)
for name in ("habitat", "habitat_sim"):
    try:
        module = __import__(name)
        version = getattr(module, "__version__", "unknown")
        print(f"{name}: import ok, version={version}")
    except Exception as exc:
        print(f"{name}: import failed: {type(exc).__name__}: {exc}")
PY
ros2 pkg prefix rclpy
ros2 pkg prefix nav2_bringup
ros2 pkg prefix objectnav_ros
conda run -n habitat python -c 'import sys; print(sys.executable); import habitat; print("habitat import ok", getattr(habitat, "__version__", "unknown")); import habitat_sim; print("habitat_sim import ok", getattr(habitat_sim, "__version__", "unknown"))'
conda run -n habitat python --version
test -f install/setup.zsh
source install/setup.zsh
ros2 pkg prefix objectnav_ros
ros2 pkg prefix objectnav_core
conda run -n habitat python -c 'import habitat_sim; print("habitat_sim import ok", getattr(habitat_sim, "__version__", "unknown"))'
conda run -n habitat python -c 'import pkgutil; print("habitat-like modules:", sorted(m.name for m in pkgutil.iter_modules() if "habitat" in m.name.lower()))'
conda run -n habitat python -m pip show habitat-lab habitat-sim habitat habitat_sim
```

2026-05-27 synthetic smoke commands:

```bash
git clone --branch v0.3.3 --depth 1 https://github.com/facebookresearch/habitat-lab.git third_party/habitat-lab
conda run -n habitat python -m pip install -e third_party/habitat-lab/habitat-lab
conda run -n habitat python -m pip install 'pillow==10.4.0'
conda run -n habitat python -m pip install jinja2 typeguard
conda run -n habitat python -m pip check
conda run -n habitat python -c 'import habitat, habitat_sim, gym; print("habitat", habitat.__version__); print("habitat_sim", habitat_sim.__version__); print("gym", gym.__version__)'
mkdir -p datasets/habitat
conda run -n habitat python -m habitat_sim.utils.datasets_download --uids habitat_test_scenes habitat_test_pointnav_dataset --data-path datasets/habitat/ --no-replace
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_objectnav_smoke.py src/objectnav_core/tests/test_ros_packaging.py -q
python3 -m compileall -q src/objectnav_core/objectnav_core
git diff --check
conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_smoke --scene /home/badger/Desktop/habitat-sim-main/data/test_assets/scenes/simple_room.glb --output runs/habitat_usability/smoke --seed 23 --sensor-size 64
find runs/habitat_usability/smoke -maxdepth 1 -type f -printf '%p %s bytes\n' | sort
sed -n '1,120p' runs/habitat_usability/smoke/summary.json
sed -n '1,10p' runs/habitat_usability/smoke/habitat_trace.csv
rg -n "Habitat ObjectNav Smoke|synthetic_objectnav_v1|trace_rows" runs/habitat_usability/smoke/report.html
git check-ignore -v third_party/habitat-lab datasets/habitat/versioned_data/habitat_test_scenes runs/habitat_usability/smoke/habitat_trace.csv
```

2026-05-27 HM3D official-scene smoke commands:

```bash
conda install -n habitat -c conda-forge git-lfs -y
conda run -n habitat git-lfs version
conda run -n habitat python -m habitat_sim.utils.datasets_download --uids habitat_test_scenes habitat_test_pointnav_dataset --data-path datasets/habitat/ --no-replace
conda run -n habitat python -m habitat_sim.utils.datasets_download --uids habitat_test_pointnav_dataset --data-path datasets/habitat/ --no-replace
conda run -n habitat python -m habitat_sim.utils.datasets_download --uids hm3d_example_full --data-path datasets/habitat/ --no-replace
find datasets/habitat -maxdepth 6 -type f \( -name '*.glb' -o -name '*.basis.glb' -o -name '*.semantic.glb' -o -name '*.navmesh' -o -name '*.semantic.txt' -o -name '*.scene_dataset_config.json' -o -name '*.json.gz' \) | sort
du -sh datasets/habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_objectnav_smoke.py -q
python3 -m compileall -q src/objectnav_core/objectnav_core
git diff --check
conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_smoke --scene datasets/habitat/scene_datasets/hm3d/example/00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb --scene-dataset-config datasets/habitat/scene_datasets/hm3d/example/hm3d_annotated_basis.scene_dataset_config.json --output runs/habitat_usability/hm3d_official_scene_smoke --seed 23 --sensor-size 128 --sample-navigable --actions move_forward,turn_left,move_forward,turn_right,move_forward
find runs/habitat_usability/hm3d_official_scene_smoke -maxdepth 1 -type f -printf '%p %s bytes\n' | sort
sed -n '1,180p' runs/habitat_usability/hm3d_official_scene_smoke/summary.json
sed -n '1,10p' runs/habitat_usability/hm3d_official_scene_smoke/habitat_trace.csv
curl -I --max-time 30 https://dl.dropboxusercontent.com/s/26ribfiup5249b8/objectnav_hssd-hab_v0.2.3.zip
curl -I --max-time 30 'https://www.dropbox.com/s/mdfpevn1srr37cr/objectnav_procthor-hab.zip?dl=1'
```

2026-05-27 multi-episode replay commands:

```bash
curl -I --max-time 30 https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/hm3d/v1/objectnav_hm3d_v1.zip
mkdir -p datasets/habitat/downloads
curl -L --fail --retry 3 --retry-delay 5 -C - -o datasets/habitat/downloads/objectnav_hm3d_v1.zip https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/hm3d/v1/objectnav_hm3d_v1.zip
unzip -l datasets/habitat/downloads/objectnav_hm3d_v1.zip | sed -n '1,120p'
mkdir -p datasets/habitat/datasets/objectnav/hm3d
unzip -q -o datasets/habitat/downloads/objectnav_hm3d_v1.zip -d datasets/habitat/datasets/objectnav/hm3d
ln -sfn objectnav_hm3d_v1 datasets/habitat/datasets/objectnav/hm3d/v1
conda run -n habitat python -m habitat_sim.utils.datasets_download --uids hm3d_minival_v0.1 --data-path datasets/habitat/ --no-replace
python3 - <<'PY'
import gzip,json
from pathlib import Path
root=Path('datasets/habitat/datasets/objectnav/hm3d/v1')
scene_root=Path('datasets/habitat/scene_datasets')
for split in ['val_mini','val']:
    content=root/split/'content'
    episodes=0
    scenes=set()
    for fp in sorted(content.glob('*.json.gz')):
        data=json.load(gzip.open(fp,'rt',encoding='utf-8'))
        for ep in data.get('episodes',[]):
            episodes += 1
            scenes.add(ep['scene_id'])
    missing=[scene for scene in sorted(scenes) if not (scene_root/scene).exists()]
    print(f'{split}: episodes={episodes} unique_scenes={len(scenes)} local_scene_assets={len(scenes)-len(missing)} missing_scene_assets={len(missing)}')
PY
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_objectnav_smoke.py src/objectnav_core/tests/test_habitat_usability_replay.py src/objectnav_core/tests/test_ros_packaging.py -q
conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_usability_replay --scene datasets/habitat/scene_datasets/hm3d/example/00337-CFVBbU9Rsyb/CFVBbU9Rsyb.basis.glb --scene datasets/habitat/scene_datasets/hm3d/example/00770-NBg5UqG3di3/NBg5UqG3di3.basis.glb --scene datasets/habitat/scene_datasets/hm3d/example/00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb --scene-dataset-config datasets/habitat/scene_datasets/hm3d/example/hm3d_annotated_basis.scene_dataset_config.json --output runs/habitat_usability/hm3d_usability_replay_30ep --episodes 30 --seed 101 --sensor-size 96
wc -l runs/habitat_usability/hm3d_usability_replay_30ep/habitat_trace.csv runs/habitat_usability/hm3d_usability_replay_30ep/usability_replay.csv
```

2026-05-27 semantic YOLO-breaker stress commands:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_semantic_yolo_stress.py src/objectnav_core/tests/test_ros_packaging.py -q
conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_semantic_yolo_stress --scene datasets/habitat/scene_datasets/hm3d/example/00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb --scene-dataset-config datasets/habitat/scene_datasets/hm3d/example/hm3d_annotated_basis.scene_dataset_config.json --output runs/habitat_usability/hm3d_semantic_yolo_stress_smoke --episodes 5 --seed 211 --sensor-size 96
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_semantic_yolo_stress.py -q
conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_semantic_yolo_stress --scene datasets/habitat/scene_datasets/hm3d/example/00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb --scene-dataset-config datasets/habitat/scene_datasets/hm3d/example/hm3d_annotated_basis.scene_dataset_config.json --output runs/habitat_usability/hm3d_semantic_yolo_stress_30ep --episodes 30 --seed 211 --sensor-size 96
wc -l runs/habitat_usability/hm3d_semantic_yolo_stress_30ep/semantic_yolo_trace.csv
```

2026-05-27 official ObjectNav val_mini semantic stress commands:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_objectnav_valmini_semantic_stress.py src/objectnav_core/tests/test_ros_packaging.py -q
python3 -m compileall -q src/objectnav_core/objectnav_core
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_valmini_semantic_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/hm3d_valmini_semantic_stress_probe --max-episodes 1 --start-source goal_viewpoint --seed 313 --sensor-size 64
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_valmini_semantic_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/hm3d_valmini_semantic_stress_30ep --max-episodes 30 --start-source goal_viewpoint --seed 313 --sensor-size 96
find runs/habitat_usability/hm3d_valmini_semantic_stress_30ep -maxdepth 1 -type f -printf '%f %s bytes\n' | sort
```

## Verification

- Full core pytest: 37 tests passed.
- Python compile check: exited successfully.
- File existence checks passed for the HTML guide, repository management doc, design doc, handoff, and implementation plan.
- Cache cleanup was repeated after verification; `.DS_Store`, `__pycache__`, and `.pytest_cache` counts were zero.

The user explicitly said not to check HTML rendering, so no browser/render validation is expected.

2026-05-27 environment checkpoint verification:

- ROS 2 command discovery passed: `which ros2` returned `/opt/ros/humble/bin/ros2`.
- The truncated `ros2 pkg list | head -40` probe printed ROS 2 packages but ended with a `BrokenPipeError` from the head-truncated pipe, so it was not used as the final ROS 2 verification.
- ROS 2 base package lookup passed for `rclpy` and `nav2_bringup`.
- Workspace package lookup initially failed before sourcing the workspace for `objectnav_ros`; after `source install/setup.zsh`, both `objectnav_ros` and `objectnav_core` resolved under this repository's `install/`.
- Conda environment lookup passed: `habitat` exists at `/home/badger/anaconda3/envs/habitat`.
- The current non-interactive shell does not have conda activated; bare `python` was not found.
- `conda run -n habitat python --version` returned Python 3.9.23.
- `conda run -n habitat python -c 'import habitat_sim ...'` passed and reported Habitat-Sim 0.3.3.
- `import habitat` failed with `ModuleNotFoundError`, and `pip show` reported `habitat-lab` and `habitat` not found.
- A full simulator scene load, episode run, trace export, and memory replay were not run.

2026-05-27 synthetic smoke verification:

- `conda run -n habitat python -m pip check` passed.
- `habitat`, `habitat_sim`, and `gym` imported; versions were Habitat-Lab 0.3.3, Habitat-Sim 0.3.3, and Gym 0.23.0.
- Official `habitat_test_scenes` download failed with a Hugging Face port 443 timeout; it also warned that `git-lfs` is not installed.
- First CLI run failed after Habitat reset because `numpy-quaternion` rotation serialization was missing; this was fixed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_objectnav_smoke.py src/objectnav_core/tests/test_ros_packaging.py -q` passed with 5 tests.
- `python3 -m compileall -q src/objectnav_core/objectnav_core` passed.
- `git diff --check` passed.
- Final Habitat smoke passed and produced 6 trace rows, `episode_over: true`, mean depth `0.739173`, mean depth valid ratio `1.0`, and 2 collision steps.
- Artifacts exist: `habitat_trace.csv` 1891 bytes, `summary.json` 1016 bytes, and `report.html` 2084 bytes.

2026-05-27 HM3D official-scene smoke verification:

- `conda install -n habitat -c conda-forge git-lfs -y` installed `git-lfs` 3.7.1 inside the conda environment.
- Retrying `habitat_test_scenes` still failed against Hugging Face with TLS/clone errors.
- `habitat_test_pointnav_dataset` downloaded successfully from `dl.fbaipublicfiles.com`.
- `hm3d_example_full` downloaded successfully from GitHub/Matterport raw assets; `datasets/habitat` is about 402 MB.
- HM3D files present include `GLAQ4DNUx5U.basis.glb`, `GLAQ4DNUx5U.basis.navmesh`, `GLAQ4DNUx5U.semantic.glb`, `GLAQ4DNUx5U.semantic.txt`, and HM3D scene dataset config JSON files.
- HM3D smoke passed and produced 7 trace rows, `episode_over: true`, `navmesh_loaded: true`, `sampled_navigable_start: true`, semantic object count `908`, semantic category count `124`, mean depth `1.299647`, mean depth valid ratio `1.0`, and 0 collision steps.
- Artifacts exist: `habitat_trace.csv` 2838 bytes, `summary.json` 1452 bytes, and `report.html` 2656 bytes.
- DropBox direct ObjectNav links remained unavailable: HSSD objectnav timed out through `dl.dropboxusercontent.com`; ProcTHOR objectnav reset through `www.dropbox.com`.

2026-05-27 multi-episode replay verification:

- Official HM3D ObjectNav zip HEAD succeeded with HTTP 200 and content length about 132 MB.
- Download and unzip of `objectnav_hm3d_v1.zip` succeeded.
- Official HM3D ObjectNav `val_mini` integrity check found 30 episodes over 2 unique scenes; `val` found 2000 episodes over 20 unique scenes.
- Local official HM3D scene availability check found 0 of 2 `val_mini` scenes and 0 of 20 `val` scenes present.
- `conda run -n habitat python -m habitat_sim.utils.datasets_download --uids hm3d_minival_v0.1 ...` failed with `AssertionError: Username required`.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_objectnav_smoke.py src/objectnav_core/tests/test_habitat_usability_replay.py src/objectnav_core/tests/test_ros_packaging.py -q` passed with 8 tests before the near-target sampling guard and 7 Habitat replay tests after the guard.
- `python3 -m compileall -q src/objectnav_core/objectnav_core` passed.
- 30-episode replay completed with 210 trace/replay rows and wrote `habitat_trace.csv`, `usability_replay.csv`, `summary.json`, `report.html`, `command.log`, and 30 per-episode smoke directories.
- Final replay metrics: evidence counts `positive=62`, `free=27`, `non_confirmation=44`, `access_blocked=47`, `unknown=30`; decision counts `verify=128`, `trust=26`, `search=27`, `retire=29`; overall mean final `p_valid=0.410633`.
- Scenario means: near-anchor final `p_valid=0.814795`, local-verify final `p_valid=0.303595`, random-anchor final `p_valid=0.113509`.

2026-05-27 semantic YOLO-breaker stress verification:

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_semantic_yolo_stress.py src/objectnav_core/tests/test_ros_packaging.py -q` passed with 7 tests after the first implementation.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_semantic_yolo_stress.py -q` passed with 8 tests after treating out-of-view target absence as `UNKNOWN`.
- `python3 -m compileall -q src/objectnav_core/objectnav_core` passed.
- 5-episode semantic smoke completed and produced clean/miss/fly-point/edge-break/mixed rows.
- First 30-episode run exposed an overly aggressive `FREE` classification for target-out-of-view frames; it was corrected to `UNKNOWN` and rerun.
- Final 30-episode semantic stress completed with 210 rows and artifacts `semantic_yolo_trace.csv`, `summary.json`, `report.html`, and `command.log`.
- Final metrics: `POSITIVE=71`, `NON_CONFIRMATION=13`, `UNKNOWN=126`; decisions `VERIFY=176`, `TRUST=34`; mean final `p_valid=0.819062`.
- Breaker mode means: clean `0.908939`, miss `0.610724`, fly-point `0.847893`, edge-break `0.866955`, mixed `0.860801`.
- Mixed mode produced 9 false-positive-positive rows; miss mode produced 16 missed-visible-target rows.

2026-05-27 official ObjectNav val_mini semantic stress verification:

- Confirmed `datasets/habitat/scene_datasets/hm3d` is a symlink to `datasets/habitat/versioned_data/hm3d-0.2/hm3d`.
- Confirmed `scene_datasets/hm3d/habitat` contains `TEEsavR23oF.basis.glb` and `wcojb4TFT35.basis.glb` plus navmeshes and semantic assets.
- Confirmed `val_mini/content/TEEsavR23oF.json.gz` and `wcojb4TFT35.json.gz` contain 15 episodes each.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_objectnav_valmini_semantic_stress.py src/objectnav_core/tests/test_ros_packaging.py -q` passed with 8 tests.
- `python3 -m compileall -q src/objectnav_core/objectnav_core` passed.
- 1-episode probe completed and found target-visible rows for the official `toilet` episode.
- Final 30-episode run completed with 210 rows and artifacts `objectnav_valmini_semantic_trace.csv`, `summary.json`, `report.html`, and `hm3d_valmini_annotated_basis.scene_dataset_config.json`.
- Final metrics: `POSITIVE=58`, `NON_CONFIRMATION=9`, `UNKNOWN=143`; decisions `VERIFY=175`, `TRUST=35`; target-visible episodes `27`; mean final `p_valid=0.757149`.
- Breaker mode means: clean `0.970945`, miss `0.569045`, fly-point `0.780606`, edge-break `0.721548`, mixed `0.743600`.
- Mixed mode produced 4 false-positive-positive rows; miss mode produced 11 missed-visible-target rows.

## Known Risks

- Habitat-Sim install commands can change; the HTML document points to official Habitat docs and keeps commands as a project-side operating plan.
- Mac support may be fragile for Habitat-Sim. Linux + NVIDIA GPU remains the safer execution target.
- The first Habitat stage should use oracle semantic evidence to isolate algorithm behavior. Detector integration should be a later ablation.
- Dataset paths and scene assets must stay ignored.
- Local shell activation matters: ROS 2 workspace packages require sourcing this workspace's `install/setup.zsh`, and Habitat-Sim commands should be run through `conda run -n habitat` or an activated `habitat` environment.
- Habitat-Lab is now installed, but the completed smoke is synthetic and uses no official ObjectNav dataset.
- The local Habitat-Sim test scene has no semantic annotations, so it cannot validate oracle semantic visibility or object-memory evidence.
- Task measurements are disabled in the smoke to avoid benchmark navmesh requirements; success, SPL, and geodesic distance remain unverified.
- Official dataset download failed due a Hugging Face timeout and missing `git-lfs`; retry before claiming official Habitat dataset readiness.
- HM3D scene-dataset config emits many missing-glob warnings because the example subset contains only a few scenes while the annotated basis config lists full splits.
- The HM3D smoke detects semantic metadata in a scene probe, but the Habitat-Lab RGB-D task trace does not include semantic sensor observations yet.
- The successful HM3D run is a real-scene smoke with synthetic ObjectNav episode data, not an official ObjectNav benchmark episode.
- Official HM3D ObjectNav episodes are local, but official scenes are not. Do not claim official ObjectNav success/SPL until HM3D v0.1 val/minival scenes are provided and measurements are enabled.
- The multi-episode replay evidence is proxy evidence from distance/depth/collision, not semantic object visibility or detector output.
- Two HM3D example scenes report no semantic metadata in the current probe; only `GLAQ4DNUx5U` reports semantic metadata.
- Semantic YOLO stress uses oracle semantic ids corrupted into detector-like masks. It is stronger than distance-proxy replay but still does not run a learned YOLO detector.
- Single-frame false-positive masks can still inflate memory if they survive component/edge quality gates. Add temporal consistency before treating this as robust to detector hallucination.
- The official `val_mini` semantic stress uses official episode metadata but starts from goal viewpoints by default to keep targets visible; it is not a navigation-policy benchmark and reports no success/SPL.
- Local HM3D v0.2 scene layout is mapped onto official `hm3d/val/...` paths. Keep this as a runner-local resolver unless the dataset layout is deliberately normalized later.

## Next Recommended Step

1. Keep using the local ROS 2 Humble workspace plus conda environment `habitat` as the execution target.
2. Run a separate official `val_mini` pass with `--start-source episode_start` to measure target visibility from official starts under scripted actions.
3. Add temporal and multi-view consistency gates for `POSITIVE` evidence from semantic/detector masks.
4. Replace corrupted oracle masks with real detector replay.
5. Provide Matterport/HM3D credentials or pre-downloaded HM3D v0.1/v0.2 val scene assets if full `val` or benchmark measurements are needed.
6. Run official HM3D ObjectNav with a real navigation policy and task measurements enabled before claiming success/SPL.
7. Add semantic debug PNG export for representative false-positive and missed-visible rows.

## Context for Next Contributor

The implemented CLIs are documented in `docs/design/2026-05-26-habitat-sim-usability-replay.md` and `docs/design/2026-05-27-habitat-val-mini-semantic-stress.md`. Keep Habitat dependencies optional so `objectnav_core` tests still run on machines without ROS or Habitat. The strongest current conclusion is "semantic memory stress works against official ObjectNav `val_mini` metadata and local HM3D semantic assets"; the not-yet-supported conclusion is "official ObjectNav benchmark performance".
