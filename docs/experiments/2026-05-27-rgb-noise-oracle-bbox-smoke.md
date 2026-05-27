# Experiment Report: RGB-Noise ObjectNav Oracle-BBox Smoke

Date: 2026-05-27  
Owner: Codex  
Status: Completed

## Question

Can the new RGB/depth-noise sim-to-real validation base be pulled onto the Linux Habitat machine and run through a minimal Habitat episode with noise profiles, out-and-back actions, and persistent memory enabled?

## Hypothesis

The new code should pass focused tests in the `conda habitat` environment, validate the noise/detector/memory configuration without importing Habitat or YOLO, and run a 1-episode Habitat smoke using `oracle_bbox` as a lightweight detector stand-in.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `f608c63` |
| Machine | `badger-linux`, via `ssh badger@100.88.131.52` |
| Dataset / scene | HM3D ObjectNav `val_mini`, scene `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb` |
| Simulator / robot | Habitat-Sim in conda env `habitat`, no robot |
| Python / env | `/home/badger/anaconda3/bin/conda run -n habitat`, Python 3.9 env |
| Key parameters | `max_episodes=1`, `noise_levels=clean`, `detector=oracle_bbox`, `memory_ablation=on`, `sensor_size=64`, `seed=313` |

## Command

Pull latest code:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only origin main'
```

Install missing test runner in the Habitat env:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat python -m pip install pytest'
```

Focused tests:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_objectnav_rgb_noise_stress.py src/objectnav_core/tests/test_rgb_noise.py src/objectnav_core/tests/test_depth_noise.py src/objectnav_core/tests/test_yolo_world_adapter.py src/objectnav_core/tests/test_revisit_controller.py src/objectnav_core/tests/test_lifelong_memory_harness.py src/objectnav_core/tests/test_ros_packaging.py -q'
```

Preflight:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --output runs/habitat_usability/rgb_noise_preflight_linux --preflight-only'
```

Habitat smoke:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/rgb_noise_oracle_bbox_smoke --noise-levels clean --detector oracle_bbox --memory-ablation on --max-episodes 1 --seed 313 --sensor-size 64'
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Focused Linux tests | 15 passed | Required installing `pytest` in `conda habitat` |
| Preflight | passed | Validated profiles, target categories, memory ablation, out-and-back actions |
| Habitat episodes completed | 1 | `episode_id=39`, category `toilet` |
| Trace rows | 15 | Reset + 14 out-and-back actions |
| Evidence counts | `positive=14`, `unknown=1` | Clean oracle-bbox smoke |
| Decision counts | `TRUST=12`, `VERIFY=3` | No search/retire |
| Target-visible rows | 15 | Goal-viewpoint start |
| Oracle-stop success rows | 12 | V1 proxy metric, not official SPL |
| Mean detector precision | 0.888438 | Bbox covers some non-target pixels |
| Mean oracle recall | 1.0 | Oracle bbox fully covers target mask |
| Mean final `p_valid` | 0.999599 | Persistent memory mode `on` |

## Observations

- Non-interactive SSH shell did not have `conda` in `PATH`; using `/home/badger/anaconda3/bin/conda` worked.
- The `habitat` env initially lacked `pytest`; it was installed with `pip`.
- Full repository tests are not meaningful in this env because the env is Python 3.9 while the project declares Python `>=3.13`, and full tests also need `pydantic`. Focused new tests passed.
- `ultralytics` and `torch` are not installed in `conda habitat`, so YOLO-World was not run.
- The smoke wrote ignored artifacts under `runs/habitat_usability/rgb_noise_oracle_bbox_smoke/`: `rgb_noise_trace.csv`, `summary.json`, `lifelong_memory.sqlite`, and a run-local Habitat scene config.

## Result

The new RGB/depth-noise validation base is runnable on the Linux Habitat machine. The `oracle_bbox` detector mode confirms the Habitat scene/episode loader, noise profile plumbing, out-and-back action sequence, evidence conversion, and persistent memory table work together for a minimal clean episode.

This is a wiring smoke only. It does not validate the real detector claim because YOLO-World was not installed or run.

## Follow-up

- Install a compatible `ultralytics` / PyTorch stack in `conda habitat` or a sibling detector env.
- Run a 1-episode `--detector yolo_world --noise-levels clean` smoke.
- If YOLO clean recall is nonzero, run `clean,mild,heavy` with `memory_ablation on,off` for 30 val_mini episodes.
