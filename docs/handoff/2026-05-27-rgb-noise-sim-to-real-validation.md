# Handoff: RGB-Noise Sim-to-Real Validation

Date: 2026-05-27  
Owner: Codex  
Status: Ready for Next Detector Smoke

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

Not run:

- Full test suite in `conda habitat`, because that env is Python 3.9 while the repo declares Python `>=3.13`, and full tests need `pydantic`.
- YOLO-World real detector run, because `ultralytics` and `torch` are not installed in `conda habitat`.

## Known Risks

- `oracle_bbox` is only a wiring smoke; it is not evidence for detector robustness.
- YOLO-World may require installing `ultralytics` and downloading `yolov8s-worldv2.pt` in the Linux `habitat` environment.
- The out-and-back controller is a deterministic action retrace helper, not a navmesh-aware `ShortestPathFollower` integration yet.
- The success metric is oracle-stop row count, not official Habitat SPL.

## Next Recommended Step

1. Install or verify a compatible `ultralytics` / PyTorch stack in `conda habitat`.
2. Run a 1-episode `--detector yolo_world --noise-levels clean` smoke.
3. If clean YOLO recall is nonzero, run the 6-cell matrix from the design doc.

## Context for Next Contributor

This implementation deliberately changes the validation question. The older semantic-mask breakers remain useful for unit stress, but the research-facing path should now run RGB/depth noise before detection, then compare memory `on` vs `off` under revisit.
