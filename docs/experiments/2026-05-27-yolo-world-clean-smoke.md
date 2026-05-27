# Experiment Report: YOLO-World Clean Habitat Smoke

Date: 2026-05-27  
Owner: Codex  
Status: Completed

## Question

Can the Linux `conda habitat` environment load YOLO-World on the RTX 4070 Laptop GPU and run the new RGB-noise ObjectNav harness with a real detector on a clean HM3D `val_mini` episode?

## Hypothesis

After installing PyTorch CUDA wheels, Ultralytics, and YOLO-World's CLIP dependency, the detector should initialize on GPU and produce detections on clean Habitat frames. If the detector misses a target that is oracle-visible, the memory policy should lower validity instead of trusting stale memory.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `de8c758` |
| Machine | `badger-linux`, via `ssh badger@100.88.131.52` |
| GPU / driver | NVIDIA GeForce RTX 4070 Laptop GPU, driver `580.159.03`, CUDA runtime display `13.0` |
| Dataset / scene | HM3D ObjectNav `val_mini`, scene `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb` |
| Simulator / robot | Habitat-Sim 0.3.3 / Habitat-Lab 0.3.3, no robot |
| Python / env | conda env `habitat`, Python 3.9.23 |
| Detector stack | `torch==2.8.0+cu128`, `torchvision==0.23.0+cu128`, `ultralytics==8.4.56`, `clip==1.0` |
| Key parameters | `detector=yolo_world`, `detector_weights=yolov8s-worldv2.pt`, `noise_levels=clean`, `memory_ablation=on`, `max_episodes=1`, `seed=313`, `sensor_size=64` and `96` |

## Command

Install PyTorch CUDA wheels:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128'
```

Install Ultralytics:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat python -m pip install ultralytics'
```

Verify imports / CUDA:

```bash
ssh badger@100.88.131.52 \
  "cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat python -c 'import numpy as np, habitat_sim, habitat, torch, torchvision, ultralytics; print(\"numpy\", np.__version__); print(\"habitat_sim\", getattr(habitat_sim, \"__version__\", \"unknown\")); print(\"habitat\", getattr(habitat, \"__version__\", \"unknown\")); print(\"torch\", torch.__version__); print(\"torchvision\", torchvision.__version__); print(\"cuda_available\", torch.cuda.is_available()); print(\"cuda_device_count\", torch.cuda.device_count()); print(\"cuda_device\", torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"none\"); print(\"ultralytics\", ultralytics.__version__)'"
```

Initialize YOLO-World adapter:

```bash
ssh badger@100.88.131.52 \
  "cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -c 'import numpy as np; from objectnav_core.perception.yolo_world_adapter import YoloWorldDetector; detector=YoloWorldDetector(weights=\"yolov8s-worldv2.pt\", categories=[\"bed\",\"chair\",\"plant\",\"sofa\",\"toilet\",\"tv_monitor\"], conf=0.25, device=\"0\"); print(\"adapter_ready\", detector.weights); results=detector.detect(np.zeros((96,96,3), dtype=np.uint8)); print(\"dummy_detection_count\", len(results))'"
```

Run clean smoke at `sensor_size=64`:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/rgb_noise_yolo_world_clean_smoke --noise-levels clean --detector yolo_world --memory-ablation on --max-episodes 1 --seed 313 --sensor-size 64'
```

Run clean smoke at `sensor_size=96`:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/rgb_noise_yolo_world_clean_smoke_96 --noise-levels clean --detector yolo_world --memory-ablation on --max-episodes 1 --seed 313 --sensor-size 96'
```

## Metrics

| Metric | 64 px | 96 px | Notes |
|---|---:|---:|---|
| Adapter initialization | passed | passed | Downloaded `yolov8s-worldv2.pt`; auto-installed `clip` dependency |
| Torch CUDA available | true | true | RTX 4070 Laptop GPU detected |
| Episodes completed | 1 | 1 | `episode_id=39`, category `toilet` |
| Trace rows | 15 | 15 | Reset + 14 out-and-back actions |
| Target-visible rows | 15 | 15 | Oracle semantic target visible throughout |
| Evidence counts | `unknown=1`, `non_confirmation=14` | `unknown=1`, `non_confirmation=14` | No detector positives |
| Decision counts | `VERIFY=5`, `SEARCH=2`, `RETIRE=8` | `VERIFY=5`, `SEARCH=2`, `RETIRE=8` | No trust rows |
| Mean detector precision | 0.0 | 0.0 | No target detections |
| Mean oracle recall | 0.0 | 0.0 | YOLO-World missed visible target |
| Oracle-stop success rows | 0 | 0 | V1 proxy metric |
| Final `p_valid` | 0.011171 | 0.011171 | Memory correctly decayed under repeated misses |

## Observations

- PyTorch CUDA install succeeded but was slow because `torch-2.8.0+cu128` and `triton` wheels were large; the download resumed after a timeout and completed.
- `pip check` reported no broken requirements after installing PyTorch, Ultralytics, CLIP, and their dependencies.
- Habitat-Sim and Habitat-Lab still import at version 0.3.3 after installing the detector stack.
- YOLO-World initialized and ran through the adapter on GPU.
- Clean Habitat frames for the first `val_mini` episode did not produce `toilet` detections at either 64 or 96 px, despite oracle target visibility.
- The memory policy behaved conservatively: repeated detector misses produced `NON_CONFIRMATION`, no `TRUST`, and final validity collapsed.

## Result

The Linux detector environment is installed and functional: PyTorch CUDA, Ultralytics, YOLO-World weights, CLIP dependency, Habitat imports, and the repository's detector adapter all run.

The first clean YOLO-World Habitat smoke failed at the perception layer. This is a useful failure, not an environment failure: YOLO-World did not detect the visible `toilet` target under the current prompt set and rendered RGB resolution.

## Follow-up

- Export debug PNGs for clean RGB, GT mask, and detector boxes on missed-visible rows.
- Try expanded prompts such as `"toilet"`, `"bathroom toilet"`, and `"white toilet"` through the adapter.
- Try higher sensor sizes (`224` or `320`) before running the full matrix.
- Run a category sweep to determine whether this is category-specific or a general Habitat-rendering/domain-gap issue.
