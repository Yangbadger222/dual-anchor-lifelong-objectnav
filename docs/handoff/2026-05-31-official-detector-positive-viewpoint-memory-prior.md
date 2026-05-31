# Handoff: Official Detector-Positive Viewpoint Memory Prior

Date: 2026-05-31
Owner: Codex
Status: Ready for Review

## Current State

Implemented a diagnostic official Habitat exporter that restores official
episode target `view_points`, runs Grounding-DINO or YOLO-World, and exports
detector-positive viewpoint anchors in the existing official memory-prior JSON
schema. The output is explicitly marked
`source_validity=privileged_viewpoint_detector_diagnostic`.

Remote Habitat diagnostics show:

- opportunistic official DINO discovery prior: previously `0/4` with oracle
  backend;
- new detector-positive viewpoint prior before aliasing: `3/4` with oracle
  backend;
- per-viewpoint trace identified the `tv_monitor` miss as a prompt/label alias
  issue;
- after ObjectNav alias prompting, detector-positive viewpoint prior: `4/4`
  with oracle backend;
- opportunistic alias discovery exported `17` anchors but still produced `0/4`
  with oracle backend, so projected-anchor localization remains bad.

## Files Touched

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_detector_viewpoint_memory_prior.py`
- `src/objectnav_core/objectnav_core/cli/export_habitat_official_detector_viewpoint_memory_prior.py`
- `src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py`
- `src/objectnav_core/objectnav_core/perception/grounding_dino_adapter.py`
- `src/objectnav_core/tests/test_grounding_dino_adapter.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `src/objectnav_core/setup.py`
- `docs/design/2026-05-31-official-detector-positive-viewpoint-memory-prior.md`
- `docs/superpowers/plans/2026-05-31-official-detector-positive-viewpoint-memory-prior.md`
- `docs/experiments/2026-05-31-official-detector-positive-viewpoint-memory-prior.md`
- `docs/devlog/2026-05.md`

## Commands Run

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_ros_packaging.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q

python3 -m compileall -q src/objectnav_core/objectnav_core/evaluation/habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/objectnav_core/cli/export_habitat_official_detector_viewpoint_memory_prior.py

git diff --check

rsync -avR src/objectnav_core/objectnav_core/evaluation/habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/objectnav_core/cli/export_habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/tests/test_ros_packaging.py src/objectnav_core/setup.py docs/design/2026-05-31-official-detector-positive-viewpoint-memory-prior.md badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m pytest src/objectnav_core/tests/test_habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/envs/habitat/bin/python -m compileall -q src/objectnav_core/objectnav_core/evaluation/habitat_official_detector_viewpoint_memory_prior.py src/objectnav_core/objectnav_core/cli/export_habitat_official_detector_viewpoint_memory_prior.py'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior --output runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_prior_4ep_8vp_20260531_v1/memory_prior.json --max-episodes 4 --max-viewpoints-per-episode 8 --grounding-dino-max-image-side 384 --min-detection-confidence 0.25'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.run_habitat_official_objectnav_eval --output runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_prior_oracle_backend_4ep_100steps_20260531_v1 --policy memory_active_perception_frontier_targetnav --memory-prior-path runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_prior_4ep_8vp_20260531_v1/memory_prior.json --targetnav-backend oracle_follower --max-episodes 4 --max-steps 100 --pathfinder-suffix-goal-radius-m 0.05'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -m objectnav_core.cli.export_habitat_official_detector_viewpoint_memory_prior --output runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_prior_4ep_32vp_20260531_v1/memory_prior.json --max-episodes 4 --max-viewpoints-per-episode 32 --grounding-dino-max-image-side 384 --min-detection-confidence 0.25'
```

## Verification

Passed:

- Initial RED exporter/CLI tests failed with missing modules, then passed after
  implementation.
- Initial RED packaging test failed with missing console script, then passed
  after setup update.
- Local focused regression: `27 passed`.
- Local `compileall`: clean.
- Local `git diff --check`: clean.
- Remote focused regression: `27 passed`.
- Remote `compileall`: clean.
- Remote 8-viewpoint export: `3` anchors from `13` restored viewpoints.
- Remote 32-viewpoint export: `3` anchors from `37` restored viewpoints.
- Remote query with oracle TargetNav backend: success rate `0.75`.
- Added per-viewpoint trace/image artifacts and ObjectNav Grounding-DINO
  aliases.
- Local focused regression after aliasing: `35 passed`.
- Remote focused regression after aliasing: `35 passed`.
- Alias trace export:
  `runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_trace_alias_4ep_32vp_20260531_v1`
  exported `4` anchors from `6` restored viewpoints.
- Alias trace prior + oracle TargetNav backend:
  `runs/habitat_official_objectnav/grounding_dino_detector_positive_viewpoint_alias_oracle_backend_4ep_100steps_20260531_v1`
  produced SR `4/4`, SPL `0.8134277193790571`, SoftSPL
  `0.8060506098824843`, and mean distance-to-goal `0.04706096462905407`.
- Opportunistic alias discovery:
  `runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_4ep_100steps_20260531_v1`
  exported `17` anchors, but oracle-backend query still produced SR `0/4`.

Not run:

- Full local test suite after this slice.
- Large official Habitat split.
- Non-oracle backend query with this prior.

## Known Risks

- The exporter is privileged because it uses official target `view_points`.
- The query result is also privileged because it uses `oracle_follower`.
- The original Grounding-DINO `tv_monitor` miss was due to prompt/label aliasing
  and is fixed for this adapter, but broader category aliases may still need
  validation on larger splits.
- Opportunistic projected anchors remain spatially poor even after aliasing.
- The code reuses private helper functions from official evaluation/oracle
  modules; acceptable for this diagnostic slice but worth cleaning before a
  stable public API.
- The repo still has many pre-existing untracked official/Habitat files, so use
  explicit file lists rather than broad git assumptions.

## Next Recommended Step

1. Build a non-privileged candidate-viewpoint proposer that can generate
   target-visible memory viewpoints from exploration observations.
2. Replace single-frame projected anchors with multi-view/viewpoint memory
   anchors and evaluate with oracle/non-oracle TargetNav backends.
3. Compare the resulting non-privileged viewpoint prior against the current
   opportunistic bbox-depth prior and this privileged viewpoint diagnostic.

## Context for Next Contributor

This slice confirms the user's point about the old DINO results: the key win
was detector-positive viewpoint memory, not merely using Grounding-DINO. Treat
the new exporter as a bridge/upper-bound diagnostic. It should guide the next
method design, but it must not be reported as a benchmark-facing ObjectNav
number.
