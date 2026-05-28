# Experiment Report: Structured-Visibility Grounding-DINO Replay

Date: 2026-05-28  
Owner: Codex  
Status: Completed, not a paper claim

## Question

After adding `episode_selection_strategy=structured_visibility`, does the
Habitat RGB-noise replay select more structural episodes, and does that make
`usability_memory` separate from the positive-only `naive_count` baseline?

## Hypothesis

The metadata selector should avoid obviously flat / single-view episodes, but
it may still be too weak to create the same stale/ghost-memory challenge as the
synthetic grid trace. If it only selects repeatedly visible targets, then
`naive_count` should remain competitive or better.

## Environment

| Item | Value |
|---|---|
| Branch / commit | First replay: `main`, `22cacd2`; phase-audit replay: `main`, `5b2a583` |
| Machine | `badger-linux` |
| Environment | `conda habitat` |
| Dataset / scene root | HM3D ObjectNav `val_mini`, HM3D scene root on Linux |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny`, image-side cap `384` |
| Resolution | `1280x720` |
| Noise levels | `clean,mild,heavy` |
| Memory modes | `on,naive_count,off` |
| Selection | `structured_visibility`, 2 episodes/category, min goal viewpoints `2`, min geodesic `2.0`, min complexity `1.2` |
| Output | First replay: `runs/habitat_usability/structured_visibility_grounding_dino_replay_1280x720_epc2_cap384`; phase-audit replay: `runs/habitat_usability/structured_visibility_grounding_dino_replay_1280x720_epc2_cap384_phase_audit` |

## Command

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav && \
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
/home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_usability/structured_visibility_grounding_dino_replay_1280x720_epc2_cap384 \
  --noise-levels clean,mild,heavy \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --grounding-dino-max-image-side 384 \
  --memory-ablation on,naive_count,off \
  --episodes-per-category 2 \
  --episode-selection-strategy structured_visibility \
  --structured-min-goal-viewpoints 2 \
  --structured-min-geodesic-distance 2.0 \
  --structured-min-path-complexity-ratio 1.2 \
  --target-categories bed,sofa,toilet,plant,tv_monitor \
  --sensor-width 1280 \
  --sensor-height 720 \
  --yolo-prompt-mode target \
  --no-stop-on-trust \
  --seed 313
```

## Metrics

### Episode Selection

| Metric | Value |
|---|---:|
| Category candidate episodes | `23` |
| Structured candidates | `9` |
| Dropped by structured filter | `14` |
| Selected episodes | `6` |
| Selected IDs | `3, 33, 55, 39, 62, 84` |
| Selected category counts | `bed=2`, `toilet=2`, `plant=2` |

Metadata audit by requested category:

| Category | Candidate episodes | Structured candidates | Notes |
|---|---:|---:|---|
| `bed` | `7` | `2` | selected |
| `sofa` | `3` | `0` | failed complexity threshold |
| `toilet` | `5` | `2` | selected |
| `plant` | `5` | `5` | selected |
| `tv_monitor` | `3` | `0` | failed complexity threshold |

The phase-audit replay made this explicit in
`summary.json["episode_selection"]["category_audit"]`:

| Category | Raw candidates | Structured candidates | Selected IDs | Selection status |
|---|---:|---:|---|---|
| `bed` | `7` | `2` | `3, 33` | `selected` |
| `sofa` | `3` | `0` | none | `no_structured_candidates` |
| `toilet` | `5` | `2` | `55, 39` | `selected` |
| `plant` | `5` | `5` | `62, 84` | `selected` |
| `tv_monitor` | `3` | `0` | none | `no_structured_candidates` |

`zero_structured_candidate_categories = ["sofa", "tv_monitor"]`.

### Replay Summary

| Metric | Value |
|---|---:|
| Replay summaries | `54` |
| Trace rows | `810` |
| Positive evidence rows | `474` |
| Non-confirmation rows | `144` |
| Unknown rows | `192` |
| Detector filtered count | `315` |
| Mean detector precision | `0.365904` |
| Mean oracle recall | `0.530368` |
| Oracle-stop success rows | `255` |

### Phase-Audit Replay

The phase-audit replay used the same command and parameters, but ran from
commit `5b2a583` and wrote:

`runs/habitat_usability/structured_visibility_grounding_dino_replay_1280x720_epc2_cap384_phase_audit`

It completed with the same selected episodes and aggregate memory metrics as
the first replay, but added `replay_phase` to the trace and phase-level summary
counts.

| Phase | Rows | Target-visible rows | Positive rows | Non-confirmation rows | Raw trust | Gated trust / success | Gate rejections |
|---|---:|---:|---:|---:|---:|---:|---:|
| `confirm` | `162` | `126` | `72` | `0` | `44` | `28` | `16` |
| `depart` | `216` | `144` | `144` | `0` | `105` | `96` | `9` |
| `non_confirm` | `216` | `198` | `108` | `90` | `82` | `66` | `16` |
| `revisit` | `216` | `180` | `150` | `54` | `85` | `65` | `20` |

Per-memory phase results:

| Memory | Phase | Rows | Visible | Positive | Non-confirmation | Raw trust | Gated trust / success | Gate rejections |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `on` | `confirm` | `54` | `42` | `24` | `0` | `32` | `16` | `16` |
| `on` | `depart` | `72` | `48` | `48` | `0` | `57` | `48` | `9` |
| `on` | `non_confirm` | `72` | `66` | `36` | `30` | `34` | `32` | `2` |
| `on` | `revisit` | `72` | `60` | `50` | `18` | `27` | `27` | `0` |
| `naive_count` | `confirm` | `54` | `42` | `24` | `0` | `12` | `12` | `0` |
| `naive_count` | `depart` | `72` | `48` | `48` | `0` | `48` | `48` | `0` |
| `naive_count` | `non_confirm` | `72` | `66` | `36` | `30` | `48` | `34` | `14` |
| `naive_count` | `revisit` | `72` | `60` | `50` | `18` | `58` | `38` | `20` |

The critical audit finding is that the `non_confirm` phase is not actually a
clean non-confirmation interval: `198 / 216` rows are still target-visible and
`108 / 216` rows are positive. The current out-and-back action trace therefore
does not force the stale-memory condition we need.

### Memory Comparison

| Memory mode | Rows | Raw trust | Gated trust / success | Gate rejections | Positive rows | Mean `p_valid` |
|---|---:|---:|---:|---:|---:|---:|
| `on` | `270` | `150` | `123` | `27` | `158` | `0.834805` |
| `naive_count` | `270` | `166` | `132` | `34` | `158` | `0.834306` |
| `off` | `270` | `0` | `0` | `0` | `158` | `0.714019` |

Noise-level comparison:

| Memory | Noise | Raw trust | Gated trust / success | Gate rejections | Positive rows |
|---|---|---:|---:|---:|---:|
| `on` | clean | `41` | `39` | `2` | `55` |
| `on` | mild | `60` | `43` | `17` | `52` |
| `on` | heavy | `49` | `41` | `8` | `51` |
| `naive_count` | clean | `58` | `45` | `13` | `55` |
| `naive_count` | mild | `54` | `44` | `10` | `52` |
| `naive_count` | heavy | `54` | `43` | `11` | `51` |

Category comparison:

| Category | Memory | Visible rows | Raw trust | Gated trust / success | Gate rejections | Positive rows |
|---|---|---:|---:|---:|---:|---:|
| `bed` | `on` | `90` | `70` | `68` | `2` | `76` |
| `bed` | `naive_count` | `90` | `78` | `70` | `8` | `76` |
| `toilet` | `on` | `84` | `52` | `52` | `0` | `66` |
| `toilet` | `naive_count` | `84` | `78` | `54` | `24` | `66` |
| `plant` | `on` | `42` | `28` | `3` | `25` | `16` |
| `plant` | `naive_count` | `42` | `10` | `8` | `2` | `16` |

## Observations

- The structured selector worked mechanically: it reduced 23 requested-category
  episodes to 9 structured candidates and selected 6. However, it excluded
  `sofa` and `tv_monitor` entirely because none of their `val_mini` metadata
  entries met the `1.2` path-complexity threshold.
- This replay still does not reproduce the synthetic structured challenge. It
  mostly rewards repeated positives rather than disappearance, blocked access,
  stale path cost, or multi-object ambiguity.
- The phase-audit replay confirms why: the index-based `non_confirm` window
  still contains many visible and positive target observations, so the route is
  not a true memory invalidation challenge.
- `naive_count` remains slightly ahead on gated trust / oracle-stop success
  (`132` vs `123`). It also has more gate rejections (`34` vs `27`), so the
  shared gate is still useful, but this is not a memory-win result.
- `plant` is still problematic: memory `on` raw-trusts 28 times, but only 3
  survive the current-positive gate. `naive_count` has fewer raw trusts and 8
  gated successes. This points back to detector/visibility quality rather than
  a clean memory advantage.
- The run used the detector area filter and recorded `315` filtered detections.

## Result

The selector is useful as an audit layer, but it is insufficient as the final
Habitat memory challenge. It selects episodes with nontrivial metadata, yet the
result remains a repeated-positive replay where `naive_count` is competitive.
The current conclusion is:

1. `structured_visibility` should stay as a prefilter and audit field.
2. `replay_phase` and `category_audit` should stay in the trace/summary because
   they expose whether a run is actually testing memory.
3. It should not be treated as proof that the Habitat replay now tests
   lifelong/dual-anchor memory.
4. The next implementation step should create an explicit structured replay
   protocol, not only metadata selection or index-based labels: first confirm,
   move to an actually target-not-visible view, force a non-confirmation
   window, then revisit and test whether memory recovers or retires.

## Follow-up

- Add a fallback selection mode so categories with zero structured candidates
  can still be included with a `fallback_reason` instead of excluding them.
- Replace index-based phase labeling with a Habitat viewpoint/action protocol
  that chooses actual confirm, target-not-visible, and revisit viewpoints.
- Export representative `plant` structured-replay gate rejections if this
  subset is used for future claims.
- Do not claim memory beats `naive_count` from this run.
