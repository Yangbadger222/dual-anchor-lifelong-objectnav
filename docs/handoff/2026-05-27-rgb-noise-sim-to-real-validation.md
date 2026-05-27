# Handoff: RGB-Noise Sim-to-Real Validation

Date: 2026-05-27  
Owner: Codex  
Status: Detector Prompt Fix Ready For Linux Rerun

## Current State

The project direction is now the RGB/depth-noise sim-to-real validation path in `docs/design/2026-05-27-rgb-noise-sim-to-real-objectnav-memory-validation.md`.

Implemented v1 code:

- Published-model RGB noise profile and pipeline.
- D435-style depth noise profile and pipeline.
- YOLO-World detector adapter with lazy `ultralytics` import.
- Out-and-back action sequence helper.
- SQLite-backed usability-belief persistence harness.
- New `run_habitat_objectnav_rgb_noise_stress` CLI.
- Full runner supports `detector=oracle_bbox` for Habitat wiring smoke and `detector=yolo_world` for real detector runs.
- YOLO-World prompting now defaults to the current ObjectNav target category,
  with `all_categories` and `target_aliases` available as explicit debug modes.
- The RGB-noise ObjectNav harness now defaults to `sensor_size=320` for real
  detector runs.

## Files Touched

- `configs/noise/rgb_published_v1.yaml`
- `configs/noise/depth_realsense_d435_v1.yaml`
- `src/objectnav_core/objectnav_core/simulation/rgb_noise.py`
- `src/objectnav_core/objectnav_core/simulation/depth_noise.py`
- `src/objectnav_core/objectnav_core/simulation/revisit_controller.py`
- `src/objectnav_core/objectnav_core/perception/yolo_world_adapter.py`
- `src/objectnav_core/objectnav_core/evaluation/lifelong_memory_harness.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_objectnav_rgb_noise_stress.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_objectnav_rgb_noise_stress.py`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_*noise*.py`
- `src/objectnav_core/tests/test_yolo_world_adapter.py`
- `src/objectnav_core/tests/test_revisit_controller.py`
- `src/objectnav_core/tests/test_lifelong_memory_harness.py`
- `src/objectnav_core/tests/test_habitat_objectnav_rgb_noise_stress.py`
- `README.md`
- `docs/README.md`
- `docs/devlog/2026-05.md`
- `docs/design/2026-05-27-rgb-noise-sim-to-real-objectnav-memory-validation.md`
- `docs/experiments/2026-05-27-yolo-world-toilet-debug.md`

## Commands Run

```bash
git status --short --branch
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_rgb_noise.py src/objectnav_core/tests/test_depth_noise.py src/objectnav_core/tests/test_yolo_world_adapter.py src/objectnav_core/tests/test_revisit_controller.py src/objectnav_core/tests/test_lifelong_memory_harness.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_objectnav_rgb_noise_stress.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_objectnav_rgb_noise_stress.py src/objectnav_core/tests/test_rgb_noise.py src/objectnav_core/tests/test_depth_noise.py src/objectnav_core/tests/test_yolo_world_adapter.py src/objectnav_core/tests/test_revisit_controller.py src/objectnav_core/tests/test_lifelong_memory_harness.py src/objectnav_core/tests/test_ros_packaging.py -q
```

## Verification

Passed locally on macOS:

- 11 focused component tests.
- 4 CLI/packaging tests.
- 15 combined tests covering the new RGB-noise validation base.

Passed on Linux after pulling commit `f608c63`:

- Focused new tests: 15 passed in `conda habitat`.
- Preflight CLI wrote `runs/habitat_usability/rgb_noise_preflight_linux/summary.json`.
- Habitat `oracle_bbox` smoke wrote `runs/habitat_usability/rgb_noise_oracle_bbox_smoke/summary.json`, `rgb_noise_trace.csv`, `lifelong_memory.sqlite`, and scene config.

After detector setup:

- Installed `torch==2.8.0+cu128`, `torchvision==0.23.0+cu128`, `ultralytics==8.4.56`, `clip==1.0`, and transitive deps into `conda habitat`.
- Verified `torch.cuda.is_available() == True` on NVIDIA GeForce RTX 4070 Laptop GPU.
- Verified `pip check` reports no broken requirements.
- Verified Habitat-Sim / Habitat-Lab still import at 0.3.3.
- Initialized `YoloWorldDetector` with `yolov8s-worldv2.pt` and ran a dummy detection.
- Ran clean YOLO-World Habitat smokes at sensor sizes 64 and 96. Both completed but produced zero detector recall on the visible `toilet` target.
- Debugged the first `toilet` miss:
  - `sensor_size=224` still produced zero detector positives.
  - `sensor_size=320` with the legacy all-category prompt produced 2 positive rows out of 15 visible rows.
  - A raw 320 px reset-frame probe detected `toilet` at confidence `0.738678`.
  - Low-threshold probes showed class competition: later visible target regions were often labeled `bed` or `sofa`.
  - `toilet_only` prompting improved target positives from 2/15 to 5/15 on the same 320 px trajectory.
- Added target-conditioned YOLO prompt mode and raised the default harness sensor size to 320.

Still not run:

- Full test suite in `conda habitat`, because that env is Python 3.9 while the repo declares Python `>=3.13`, and full tests need `pydantic`.

## Known Risks

- `oracle_bbox` is only a wiring smoke; it is not evidence for detector robustness.
- YOLO-World misses the first visible `toilet` episode under 64/96/224 px
  renders. At 320 px, target-conditioned prompting recovers early full-target
  views but later out-and-back frames are edge-clipped and remain poor detector
  evidence.
- The out-and-back controller is a deterministic action retrace helper, not a navmesh-aware `ShortestPathFollower` integration yet.
- The success metric is oracle-stop row count, not official Habitat SPL.

## Next Recommended Step

1. Pull the prompt-mode fix on `badger-linux`.
2. Run the clean 1-episode YOLO-World smoke with the new defaults
   (`sensor_size=320`, `yolo_prompt_mode=target`).
3. Run a category sweep before the full 6-cell matrix.

## Context for Next Contributor

This implementation deliberately changes the validation question. The older semantic-mask breakers remain useful for unit stress, but the research-facing path should now run RGB/depth noise before detection, then compare memory `on` vs `off` under revisit.
