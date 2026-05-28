# Experiment Report: Long-Range Expected-Empty Grounding-DINO Replay

Date: 2026-05-28  
Owner: Codex  
Status: Completed replay matrix, diagnostic result

## Question

Can a long-range replay protocol combine official ObjectNav start-to-goal
distance with an expected-empty stale-memory challenge, and does `memory=on`
beat or at least improve over positive-only `naive_count` under Grounding-DINO,
RGB/depth noise, and the shared current-positive decision gate?

## Hypothesis

`geodesic_expected_empty_challenge` should be harder and more research-relevant
than either short expected-empty teleport replay or repeated-positive
`geodesic_path` alone. Memory should reduce stale raw trust through the
expected-empty interval. It may still have fewer gated success rows than
`naive_count` if the detector keeps producing current positives.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `937e47c` for final matrix |
| Machine | `badger-linux` |
| Environment | `conda habitat` |
| Dataset / scene root | HM3D ObjectNav `val_mini`, `datasets/habitat/scene_datasets/hm3d` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny`, image-side cap `384` |
| Resolution | `1280x720` |
| Noise | `clean,mild,heavy` RGB/depth noise profiles |
| Memory modes | `on,naive_count,off` |
| Selection | `structured_visibility`, `bed,toilet,plant`, 2 episodes/category |
| Replay | `geodesic_expected_empty_challenge`, `episode_start`, max 12 geodesic waypoints |
| Geometry gate | FOV enabled, distance radius disabled |
| Final output | `runs/habitat_usability/geodesic_expected_empty_grounding_dino_matrix_1280x720_epc2_cap384_recovery084` |

## Command

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav && \
source ~/anaconda3/etc/profile.d/conda.sh && \
conda activate habitat && \
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --output runs/habitat_usability/geodesic_expected_empty_grounding_dino_matrix_1280x720_epc2_cap384_recovery084 \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --rgb-noise-profile configs/noise/rgb_published_v1.yaml \
  --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml \
  --noise-levels clean,mild,heavy \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --grounding-dino-max-image-side 384 \
  --memory-ablation on,naive_count,off \
  --target-categories bed,toilet,plant \
  --episodes-per-category 2 \
  --episode-selection-strategy structured_visibility \
  --structured-min-goal-viewpoints 2 \
  --structured-min-geodesic-distance 2.0 \
  --structured-min-path-complexity-ratio 1.2 \
  --start-source episode_start \
  --replay-protocol geodesic_expected_empty_challenge \
  --geodesic-path-max-steps 12 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --no-stop-on-trust \
  --memory-geometry-gate-radius-m 0 \
  --memory-geometry-gate-fov \
  --seed 313
```

## Protocol

The replay sequence for each selected episode is:

1. `approach`: replay sampled Habitat navmesh shortest-path waypoints from the
   official ObjectNav episode start toward the goal viewpoint.
2. `confirm`: repeat the measured goal viewpoint.
3. `expected_empty`: jump to a measured target-hidden view and mark
   `expected_target_absent=True`.
4. `revisit`: return to the goal viewpoint.

This is still replay-style validation. It is not closed-loop navigation and
must not be reported as official Habitat SPL.

## Metrics

### Episode Selection

| Metric | Value |
|---|---:|
| Selected episode IDs | `3,33,55,39,62,84` |
| Selected category counts | `bed=2`, `toilet=2`, `plant=2` |
| Candidate episodes after structured filter | `9` |
| Dropped by structured filter | `8` |
| Zero structured candidate categories | none |

### Final EPC2 Matrix

| Metric | Value |
|---|---:|
| Episodes completed | `54` |
| Trace rows | `1152` |
| Replay phase counts | `approach=558`, `confirm=162`, `expected_empty=216`, `revisit=216` |
| Expected-empty evidence | `168 non_confirmation`, `48 positive` |
| Revisit evidence | `188 positive`, `27 non_confirmation`, `1 unknown` |
| Detector filtered count | `195` |

Memory comparison:

| Memory mode | Successful episodes | Success rows | Raw trust rows | Gate rejections | Mean first success step | Mean path to first success | Mean final `p_valid` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `on` | `17/18` | `117` | `240` | `123` | `8.176471` | `13.344742 m` | `0.860704` |
| `naive_count` | `17/18` | `136` | `256` | `120` | `8.176471` | `13.471588 m` | `0.928914` |
| `off` | `0/18` | `0` | `0` | `0` | n/a | n/a | `0.793014` |

Category detail:

| Category | Memory | Success rows | Raw trust rows | Gate rejections | Successful episodes | Expected-empty evidence | Revisit evidence |
|---|---|---:|---:|---:|---:|---|---|
| `bed` | `on` | `53` | `71` | `18` | `6/6` | `24 non_confirmation` | `24 positive` |
| `bed` | `naive_count` | `57` | `88` | `31` | `6/6` | `24 positive` | `24 positive` |
| `plant` | `on` | `20` | `69` | `49` | `5/6` | `24 non_confirmation` | `14 positive`, `9 non_confirmation`, `1 unknown` |
| `plant` | `naive_count` | `29` | `76` | `47` | `5/6` | `24 non_confirmation` | `15 positive`, `9 non_confirmation` |
| `toilet` | `on` | `44` | `100` | `56` | `6/6` | `24 non_confirmation` | `24 positive` |
| `toilet` | `naive_count` | `50` | `92` | `42` | `6/6` | `24 non_confirmation` | `24 positive` |

Noise detail:

| Noise | Memory | Success rows | Raw trust rows | Gate rejections | Successful episodes | Expected-empty evidence | Revisit evidence |
|---|---|---:|---:|---:|---:|---|---|
| `clean` | `on` | `46` | `77` | `31` | `6/6` | `24 non_confirmation` | `24 positive` |
| `clean` | `naive_count` | `52` | `108` | `56` | `6/6` | `8 positive`, `16 non_confirmation` | `24 positive` |
| `mild` | `on` | `38` | `84` | `46` | `6/6` | `24 non_confirmation` | `22 positive`, `2 non_confirmation` |
| `mild` | `naive_count` | `47` | `79` | `32` | `6/6` | `8 positive`, `16 non_confirmation` | `22 positive`, `2 non_confirmation` |
| `heavy` | `on` | `33` | `79` | `46` | `5/6` | `24 non_confirmation` | `16 positive`, `7 non_confirmation`, `1 unknown` |
| `heavy` | `naive_count` | `37` | `69` | `32` | `5/6` | `8 positive`, `16 non_confirmation` | `17 positive`, `7 non_confirmation` |

Failure:

| Memory | Failed episode | Reason |
|---|---|---|
| `on` | `plant`, episode `84`, `heavy` | Detector produced mostly non-confirmation during visible confirm/revisit; memory cannot recover without current positives. |
| `naive_count` | `plant`, episode `84`, `heavy` | Same detector miss pattern; final `p_valid=0.720192`, no gated trust. |

## Ablation Notes

Three runs were needed before the final matrix:

| Run | Output | Main result |
|---|---|---|
| Initial long-range expected-empty smoke | `geodesic_expected_empty_grounding_dino_smoke_1280x720_epc1_cap384` | `memory=on` only `3/9`; FOV gate applied too early and poisoned recovery. |
| Phase-scoped FOV gate | `geodesic_expected_empty_grounding_dino_smoke_1280x720_epc1_cap384_phase_scoped_fov` | `memory=on` improved to `8/9`; early approach/confirm positives no longer rejected by the anchor. |
| Current-positive recovery threshold `0.84` | `geodesic_expected_empty_grounding_dino_smoke_1280x720_epc1_cap384_recovery084` | `memory=on` reached `9/9`, with lower raw trust than `naive_count` (`110` vs `136`). |

The final EPC2 matrix uses the phase-scoped FOV gate and `0.84` current-positive
recovery threshold.

## Observations

- The new protocol is mechanically useful: it combines long official
  start-to-goal replay distance with explicit expected-empty stale-memory
  evidence.
- `memory=on` no longer loses recovery after the expected-empty interval. It
  matches `naive_count` on successful episodes in the final matrix (`17/18`).
- `memory=on` produces fewer raw trust rows overall (`240` vs `256`) and
  reaches first success at slightly shorter path translation on average
  (`13.344742 m` vs `13.471588 m`).
- `naive_count` still has more gated success rows (`136` vs `117`), because the
  current replay often rewards repeated positive detections even when they
  come from positive-only accumulation.
- For `bed`, FOV geometry turns all expected-empty detections into
  non-confirmation for `memory=on`; `naive_count` still sees 24 expected-empty
  positives.
- The only failed selected episode is `plant` episode `84` under heavy noise,
  and both memory modes fail. This is primarily a detector/visibility failure,
  not a memory-specific regression.

## Result

This is the strongest replay result so far, but it is not yet a top-tier paper
claim by itself:

1. The harness can run long-range replay from official ObjectNav starts with
   Grounding-DINO, `1280x720` RGB/depth noise, expected-empty stale-memory
   verification, and the shared decision gate.
2. `memory=on` matches the accumulating positive-only baseline on successful
   episodes while using fewer raw trust decisions and slightly shorter mean
   path-to-first-success.
3. `memory=on` is still more conservative in gated success row count, so the
   current result is best framed as a safety/staleness improvement, not a
   decisive navigation-efficiency win.
4. The remaining gap points to the next research step: persist object-instance
   anchors and run a true long-horizon multi-room/multi-corridor lifecycle with
   object movement/removal, rather than only replaying a single episode.

## Follow-up

- Scale beyond EPC2 after adding object-instance anchor persistence.
- Add an action-level Habitat follower so the report can include path length,
  stop decisions, and SPL-like metrics instead of replay row counts.
- Add a harder lifecycle scenario: confirm object, leave across multiple
  rooms/corridors, verify expected-empty, then search/reacquire or retire.
- Keep `naive_count` positive-only; do not give it non-confirmation, delayed
  birth, geometry, or persistence.
- Diagnose `plant` heavy noise with PNG exports if plant remains a blocker in
  larger matrices.
