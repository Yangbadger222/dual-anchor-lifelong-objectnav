# Handoff: RGB-Noise Sim-to-Real Validation

Date: 2026-05-28
Owner: Codex  
Status: Ready For Memory Ablation Refinement And Stop-Gate Fixes

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
- Pulled commit `28b01b9` on `badger-linux`, ran focused tests, and ran the
  clean target-conditioned smoke:
  - output: `runs/habitat_usability/rgb_noise_yolo_world_clean_smoke_target_default`
  - `sensor_size=320`
  - `yolo_prompt_mode=target`
  - evidence counts: `positive=4`, `non_confirmation=10`, `unknown=1`
  - decision counts: `TRUST=1`, `VERIFY=10`, `SEARCH=1`, `RETIRE=3`
  - mean oracle recall: `0.333309`
  - oracle-stop success rows: `1`
- Pulled commit `0845c2b` on `badger-linux`, ran focused tests, and reran the
  stop-on-trust smoke:
  - output: `runs/habitat_usability/rgb_noise_yolo_world_clean_smoke_stop_on_trust_v2`
  - trace rows: `6`
  - evidence counts: `positive=4`, `non_confirmation=1`, `unknown=1`
  - decision counts: `TRUST=1`, `VERIFY=5`
  - mean oracle recall: `0.833272`
  - final `p_valid=0.921945`
  - edge trace confirms the single miss was side-clipped: `right|bottom`
- Ran a 6-episode clean category sweep with target prompts:
  - output: `runs/habitat_usability/rgb_noise_yolo_world_clean_category_sweep6_stop`
  - toilet episodes: `3/3` oracle-stop success
  - plant episodes: `0/3` oracle-stop success
- Ran the same 6-episode sweep with `target_aliases`:
  - output: `runs/habitat_usability/rgb_noise_yolo_world_clean_category_sweep6_aliases_stop`
  - oracle-stop success rows: `0`; aliases degraded toilet and did not help plant
- Wrote a detailed local HTML status report:
  - `docs/experiments/2026-05-27-yolo-world-objectnav-status-report.zh.html`
- Pulled commit `18254e7` on `badger-linux`, ran focused tests, and started
  real-resolution detector category qualification:
  - output: `runs/habitat_usability/detector_category_qualification_1280x720_epc1`
  - config: clean RGB, `sensor_resolution=1280x720`, `episodes_per_category=1`,
    `yolo_prompt_mode=target`, `stop_on_trust=true`
  - first-pass detector-ready categories: `bed`, `sofa`, `toilet`
  - first-pass blockers: `plant`, `tv_monitor`; `chair` was not assessable
    because the first selected episode had zero target-visible rows
- Ran full-trace two-episode-per-category qualification:
  - output: `runs/habitat_usability/detector_category_qualification_1280x720_epc2_fulltrace`
  - episodes completed: `12`
  - trace rows: `180`
  - detector-ready: `bed`, `sofa`, usable/view-sensitive `toilet`
  - blockers: `plant`, `tv_monitor`
  - `chair` still had `0` target-visible rows in the first two episodes
- Ran chair/tv-monitor probe:
  - output: `runs/habitat_usability/detector_category_qualification_1280x720_chair_tv_probe`
  - chair: 7 sampled episodes, but only sparse or zero target-visible rows and
    no positives
  - tv-monitor: 3 sampled episodes, 2 visible rows each, no positives
- Recorded this in
  `docs/experiments/2026-05-28-detector-category-qualification-1280x720.md`.
- Wrote a detailed local HTML report:
  - `docs/experiments/2026-05-28-detector-category-qualification-1280x720.zh.html`
- Added Grounding-DINO as a detector backend and ran clean `1280x720`
  qualification with detector-side cap `384`:
  - output: `runs/habitat_usability/grounding_dino_category_qualification_1280x720_epc1_cap384`
  - output: `runs/habitat_usability/grounding_dino_category_qualification_1280x720_epc2_fulltrace_cap384`
  - output: `runs/habitat_usability/grounding_dino_category_qualification_1280x720_chair_probe_cap384`
  - `bed`, `sofa`, `toilet`, and `plant` are ready in the main full-trace pass
  - `tv_monitor` is usable but sparse-view sensitive
  - `chair` succeeds in later sparse-visible probe episodes but remains blocked
    by first-N episode visibility
- Recorded this in
  `docs/experiments/2026-05-28-grounding-dino-category-qualification-1280x720.md`.
- Ran the first memory-only / replay-style matrix without a navigation system:
  - output:
    `runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384`
  - config: fixed `out_and_back` replay, Grounding-DINO
    `IDEA-Research/grounding-dino-tiny`, `grounding_dino_max_image_side=384`,
    `sensor_resolution=1280x720`, `noise_levels=clean,mild,heavy`,
    `memory_ablation=on,off`, `--no-stop-on-trust`
  - categories: `bed`, `sofa`, `toilet`, `plant`, `tv_monitor`
  - completed 60 replay-runs and 900 trace rows
  - memory `on`: 372 trust rows and 268 oracle-stop success rows
  - memory `off`: 0 trust rows and 0 oracle-stop success rows
  - strongest categories: `bed`, `sofa`, `toilet`
  - risk categories: `plant`, `tv_monitor`, because many trust decisions occur
    when the oracle target is not currently visible
- Recorded this in
  `docs/experiments/2026-05-28-memory-only-grounding-dino-replay-1280x720.md`
  and
  `docs/experiments/2026-05-28-memory-only-grounding-dino-replay-1280x720.zh.html`.
- Added `memory_ablation=naive_count` as the fairer accumulating baseline:
  - it only counts positive detector evidence inside one replay
  - it ignores non-confirmation and unknown observations
  - it does not use delayed birth, geometry, negative evidence handling, or
    cross-episode persistence
  - the first positive observation increments the count but stays below the
    trust threshold
  - the current trust threshold is two positive observations
- Added a shared decision-side current-positive gate for all memory modes:
  - raw `TRUST` only remains gated `TRUST` when the current frame has target
    visibility and positive detector evidence
  - trace rows now include `raw_decision`, gated `decision`,
    `decision_gate_reason`, and `naive_positive_count`
  - summaries now include `raw_decision_counts` and
    `decision_gate_reason_counts`
- Re-ran the full replay matrix with `on,naive_count,off`:
  - output:
    `runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384_naive_count_gate`
  - completed 90 replay-runs and 1350 trace rows
  - summary: 694 raw trust rows, 488 gated trust / success rows, 206 gate
    rejections
  - memory `on`: 372 raw trust, 246 gated success, 126 gate rejections
  - `naive_count`: 322 raw trust, 242 gated success, 80 gate rejections
  - memory `off`: 0 trust and 0 success
  - result: accumulation matters, but this replay matrix does not show
    Dual-Anchor / Lifelong memory beating naive positive counting

Still not run:

- Full test suite in `conda habitat`, because that env is Python 3.9 while the repo declares Python `>=3.13`, and full tests need `pydantic`.
- Visibility-aware category qualification that selects episodes by actual
  oracle-visible reset/goal-viewpoint rows.
- A task designed to separate Dual-Anchor / Lifelong memory from naive positive
  accumulation.
- Full navigation-backed ObjectNav run with Habitat follower / planner metrics.

## Known Risks

- `oracle_bbox` is only a wiring smoke; it is not evidence for detector robustness.
- YOLO-World misses the first visible `toilet` episode under 64/96/224 px
  renders. At 320 px with target-conditioned prompting and stop-on-trust,
  toilet smoke succeeds.
- Plant remains a YOLO-World detector/category bottleneck, but Grounding-DINO
  clears it in the clean `1280x720` qualification.
- `tv_monitor` remains sparse-view sensitive, but Grounding-DINO produced
  success rows in the second full-trace tv-monitor episode.
- `chair` cannot be evaluated from the current early sampled goal viewpoints;
  semantic chair IDs exist, and Grounding-DINO succeeds on later sparse-visible
  chair samples.
- Grounding-DINO uncapped / large-cap inference OOMs on the 4070 Laptop GPU.
  Use `--grounding-dino-max-image-side 384` unless running on a larger GPU.
- The out-and-back controller is a deterministic action retrace helper, not a navmesh-aware `ShortestPathFollower` integration yet.
- The success metric is oracle-stop row count, not official Habitat SPL.
- The current memory `off` baseline is intentionally harsh: it applies each
  frame's evidence to `INITIAL_BELIEF` and discards belief before the next row.
  It is a single-frame baseline, not an episode-local accumulating baseline.
- `naive_count` is intentionally weak and positive-only. Do not add
  non-confirmation, unknown handling, delayed birth, geometry, or persistence to
  it, because those are algorithm contributions.
- Do not reduce `naive_count` to a one-positive trust baseline; that makes it a
  single-frame strawman again.
- The current-positive gate is shared by all memory modes. Keep it on the
  decision path, not as a post-hoc metric-only filter.

## Next Recommended Step

1. Pull the naive-count/shared-gate commit on `badger-linux`.
2. Add a task where naive count should fail: cross-episode persistence,
   scene-change handling, negative evidence, or geometry consistency.
3. Generate debug PNGs for `plant` and `tv_monitor` gate rejections.
4. Add visibility-aware episode selection and reintroduce `chair`.
5. Then connect the replay harness to a real navigation policy or Habitat
   follower and report navigation metrics.

## Context for Next Contributor

This implementation deliberately changes the validation question. The older semantic-mask breakers remain useful for unit stress, but the research-facing path should now run RGB/depth noise before detection, then compare memory `on` vs `off` under revisit.
