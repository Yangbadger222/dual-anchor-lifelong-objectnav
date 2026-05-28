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
- Added gate-rejection PNG export for visual diagnostics:
  - CLI flags:
    `--debug-export-gate-rejections`,
    `--debug-export-categories plant,tv_monitor`,
    `--debug-export-limit-per-category 256`
  - trace rows now include `debug_png`
  - summaries include `debug_png_counts` and `debug_png_skipped_counts`
  - each PNG shows clean/noisy RGB, Grounding-DINO boxes, Habitat GT mask,
    detector mask, overlap, gate reason, detector confidence, oracle pixels,
    detector pixels, precision, and recall
- Ran the plant/tv-monitor diagnostic export:
  - output:
    `runs/habitat_usability/gate_rejection_debug_plant_tv_monitor_grounding_dino_1280x720_epc2_cap384`
  - completed 24 replay-runs and 360 trace rows
  - exported 177 debug PNGs: `plant=23`, `tv_monitor=154`
  - no PNGs were skipped by the per-category cap
  - local quick-review samples:
    `/tmp/dual_anchor_gate_debug_samples/contact_sheet.png`
  - diagnostic report:
    `docs/experiments/2026-05-28-gate-rejection-debug-pngs.md`
  - current read: `tv_monitor` is mostly Grounding-DINO false-positive /
    over-broad-box behavior; `plant` is mixed between detector false positives
    and strict/clipped Habitat GT masks
- Added a detector-side max-area filter:
  - default `--max-detection-area-ratio 0.7`
  - set `--max-detection-area-ratio 0` to disable for ablations
  - rejects both individual over-broad boxes and over-broad union masks
  - trace rows include `detection_filtered_count`
  - summaries include total `detection_filtered_count`
  - the filter uses only detector bbox geometry and image size, not Habitat GT
- Filter follow-up:
  - `0.70` reduced out-of-view positive rows from `158` to `128` without
    reducing visible positives (`36`) or success rows (`21`)
  - `0.40` reduced out-of-view positives to `102`, but killed all plant visible
    positives and reduced success rows to `11`
  - keep `0.70`; do not solve the remaining detector issue by tightening area
    alone
- Added and ran the structured `naive_count` decision challenge locally:
  - output:
    `runs/grid_trace/structured_naive_count_decision_challenge_seed17_ep900`
  - command:
    `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_grid_trace_experiment --output runs/grid_trace/structured_naive_count_decision_challenge_seed17_ep900 --seed 17 --episodes 900 --steps-per-episode 8`
  - `naive_count` remains positive-only with a two-positive trust threshold
  - both policies share the same current-positive decision gate
  - result: `naive_count` had `1241` unsafe raw-trust rows versus `882` for
    `usability_memory`
  - `removed_or_moved`: `naive_count` had `600` unsafe raw-trust rows after
    early positives; `usability_memory` had `7` and retired
  - `multi_object_association`: `naive_count` had `200` false-positive
    write-pressure rows; the JPDA-style memory path had zero
  - report:
    `docs/experiments/2026-05-28-structured-naive-count-decision-challenge.md`
    and HTML companion
    `docs/experiments/2026-05-28-structured-naive-count-decision-challenge.zh.html`
- Ran the structured-visibility Habitat replay on Linux:
  - pulled to commit `22cacd2`
  - remote focused tests passed in `conda habitat`: 24 tests
  - output:
    `runs/habitat_usability/structured_visibility_grounding_dino_replay_1280x720_epc2_cap384`
  - artifacts: `summary.json`, `rgb_noise_trace.csv`, `lifelong_memory.sqlite`
  - episode selection:
    - requested categories: `bed,sofa,toilet,plant,tv_monitor`
    - category candidates: `23`
    - structured candidates: `9`
    - selected episodes: `3,33,55,39,62,84`
    - selected categories: `bed=2`, `toilet=2`, `plant=2`
    - `sofa` and `tv_monitor` had zero candidates under complexity ratio `1.2`
  - memory metrics:
    - `on`: 150 raw trust, 123 gated trust / success, 27 gate rejections
    - `naive_count`: 166 raw trust, 132 gated trust / success, 34 gate rejections
    - `off`: 0 trust / success
  - conclusion: metadata-based structured selection is useful for audit, but it
    still produces a repeated-positive replay where `naive_count` remains
    competitive. Do not use this run as a memory-beats-baseline claim.
  - report:
    `docs/experiments/2026-05-28-structured-visibility-grounding-dino-replay.md`
- Added local audit instrumentation for the next replay:
  - trace rows now include `replay_phase` with `confirm`, `depart`,
    `non_confirm`, and `revisit`
  - summaries now include `replay_phase_counts`,
    `replay_phase_evidence_counts`, `replay_phase_decision_counts`, and
    `replay_phase_raw_decision_counts`
  - `summary.json["episode_selection"]["category_audit"]` reports per-category
    raw candidates, structured candidates, selected IDs, dropped counts, and
    selection status
  - `summary.json["episode_selection"]["zero_structured_candidate_categories"]`
    explicitly names categories such as `sofa` or `tv_monitor` when the current
    thresholds exclude them
  - focused local tests passed: 26 tests in
    `src/objectnav_core/tests/test_habitat_objectnav_rgb_noise_stress.py`
- Pulled commit `5b2a583` on `badger-linux`, ran the focused test in
  `conda habitat`, and reran the structured-visibility replay with phase audit:
  - output:
    `runs/habitat_usability/structured_visibility_grounding_dino_replay_1280x720_epc2_cap384_phase_audit`
  - trace rows: `810`
  - replay summaries: `54`
  - selected episodes: `3,33,55,39,62,84`
  - selected categories: `bed=2`, `toilet=2`, `plant=2`
  - zero structured categories: `sofa`, `tv_monitor`
  - phase evidence:
    - `confirm`: `162` rows, `126` target-visible, `72` positive
    - `depart`: `216` rows, `144` target-visible, `144` positive
    - `non_confirm`: `216` rows, `198` target-visible, `108` positive,
      `90` non-confirmation
    - `revisit`: `216` rows, `180` target-visible, `150` positive,
      `54` non-confirmation
  - memory metrics are unchanged in conclusion:
    - `on`: `150` raw trust, `123` gated trust / success, `27` gate rejections
    - `naive_count`: `166` raw trust, `132` gated trust / success, `34` gate
      rejections
  - conclusion: the phase labels are useful audit fields, but the current
    out-and-back path still does not create a true non-confirmation challenge.
- Added local `visibility_challenge` replay protocol:
  - CLI flag: `--replay-protocol visibility_challenge`
  - default remains `out_and_back`
  - chooses a measured target-visible Habitat goal view for `confirm/revisit`
  - chooses a measured target-hidden turned-around view for
    `depart/non_confirm`
  - trace rows include `replay_protocol`, `replay_source`, and
    `replay_source_target_pixels`
  - the protocol emits 3 confirm frames, 2 depart frames, 4 non-confirm frames,
    and 4 revisit frames
  - detector inference, evidence classification, memory update logic,
    positive-only `naive_count`, and the shared current-positive gate are
    unchanged
  - local focused tests passed: 29 tests in
    `src/objectnav_core/tests/test_habitat_objectnav_rgb_noise_stress.py`
- Pulled commit `df8cf45` on `badger-linux` and ran visibility-challenge
  smokes:
  - remote focused test passed in `conda habitat`: 29 tests
  - `oracle_bbox` output:
    `runs/habitat_usability/visibility_challenge_oracle_bbox_smoke`
  - Grounding-DINO output:
    `runs/habitat_usability/visibility_challenge_grounding_dino_smoke_clean`
  - both outputs have 117 trace rows and 9 replay summaries
  - phase visibility is now correct:
    - `confirm`: 27/27 target-visible rows
    - `depart`: 0/18 target-visible rows
    - `non_confirm`: 0/36 target-visible rows
    - `revisit`: 36/36 target-visible rows
  - oracle-bbox hidden phases produce `unknown`, not `non_confirmation`
  - Grounding-DINO hidden phases include detector positives despite zero oracle
    target visibility: 6 positive `depart` rows and 12 positive `non_confirm`
    rows
  - protocol report:
    `docs/experiments/2026-05-28-visibility-challenge-replay-smoke.md`
- Ran larger `1280x720` Grounding-DINO visibility-challenge replay:
  - output:
    `runs/habitat_usability/visibility_challenge_grounding_dino_replay_1280x720_epc2_cap384`
  - config: `bed,toilet,plant`, two structured episodes per category,
    `clean,mild,heavy`, `on,naive_count,off`, `--no-stop-on-trust`
  - trace rows: `702`
  - replay summaries: `54`
  - selected episodes: `3,33,55,39,62,84`
  - phase visibility:
    - `confirm`: `162/162` target-visible rows
    - `depart`: `0/108` target-visible rows
    - `non_confirm`: `0/216` target-visible rows
    - `revisit`: `216/216` target-visible rows
  - memory metrics:
    - `on`: `215` raw trust, `93` gated trust / success, `122` gate rejections
    - `naive_count`: `197` raw trust, `86` gated trust / success, `111` gate
      rejections
    - `off`: `0` trust / success
  - hidden-phase positives are all `bed`: `108` hidden positive rows with zero
    oracle target-visible rows; `plant` and `toilet` have zero hidden positives
  - this is the first Habitat real-detector replay in this sequence where
    memory `on` beats `naive_count` on gated success, but it remains diagnostic
    because hidden-phase bed detector false positives dominate the result.
- Ran bed-only hidden debug export:
  - output:
    `runs/habitat_usability/visibility_challenge_hidden_bed_debug_1280x720_cap384`
  - exported `79` bed PNGs, including all `72` hidden-phase gate rejections
  - local contact sheet:
    `/tmp/dual_anchor_hidden_bed_debug/contact_sheet.png`
  - visual read: Grounding-DINO repeatedly boxes door/furniture regions in the
    turned-around hidden view. This looks like detector false positives under
    the `bed` prompt rather than Habitat GT being too strict on a visible bed.
- Added local trace-filtered debug PNG export:
  - CLI flags:
    `--debug-export-replay-phases` and `--debug-export-evidence-types`
  - trace-filtered exports write to `debug_rows/`
  - the old `--debug-export-gate-rejections` mode still writes to
    `debug_gate_rejections/` when used alone
  - local tests passed: `35` focused tests across RGB-noise stress and grid
    trace
  - CLI preflight recorded `debug_export_directory=debug_rows` for
    `depart,non_confirm` + `positive`

Still not run:

- Full test suite in `conda habitat`, because that env is Python 3.9 while the repo declares Python `>=3.13`, and full tests need `pydantic`.
- Manual review of all 177 exported PNGs; only representative samples and a
  contact sheet have been inspected so far.
- Visibility-aware category qualification that selects episodes by actual
  oracle-visible reset/goal-viewpoint rows.
- Linux trace-filtered PNG diagnostic for hidden-phase positives. The export
  feature is implemented locally, but the remote Habitat/Grounding-DINO run has
  not been executed yet.
- Full planner-backed Habitat action protocol. The new visibility challenge
  teleports between measured viewpoints; it is still a memory/evidence stress
  test, not a navigation metric.
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

1. Pull the detector-area-filter commit on `badger-linux` and rerun the
   `plant,tv_monitor` diagnostic subset with the default filter. Completed for
   `0.70` and `0.40`; see the diagnostic report.
2. Manually review the full
   `runs/habitat_usability/gate_rejection_debug_plant_tv_monitor_grounding_dino_1280x720_epc2_cap384/debug_gate_rejections/`
   directory before making a paper claim about detector-vs-GT responsibility.
3. Pull the trace-filtered debug export on `badger-linux` and run a bed-only
   hidden-positive diagnostic using `--debug-export-replay-phases
   depart,non_confirm` and `--debug-export-evidence-types positive`.
4. Decide whether hidden-view `unknown` is enough for the next memory claim or
   whether the harness needs an explicit expected-location-empty evidence
   context to produce true `NON_CONFIRMATION`.
5. Add visibility-aware episode selection and reintroduce `chair`.
6. Add a fallback selection mode so categories with zero structured candidates
   can still be included with an explicit `fallback_reason`.
7. Then connect the replay harness to a real navigation policy or Habitat
   follower and report navigation metrics.

## Context for Next Contributor

This implementation deliberately changes the validation question. The older semantic-mask breakers remain useful for unit stress, but the research-facing path should now run RGB/depth noise before detection, then compare memory `on` vs `off` under revisit.
