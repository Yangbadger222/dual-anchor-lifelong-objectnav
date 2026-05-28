# Experiment Report: Memory-Only Grounding-DINO Replay At 1280x720

Date: 2026-05-28  
Owner: Codex  
Status: Completed, controlled replay result

## Question

With the navigation system still absent, can the current Habitat replay harness
validate the ObjectNav memory path by holding the trajectory fixed and comparing
Grounding-DINO observations with memory `on` versus memory `off` under
`clean/mild/heavy` RGB and depth noise?

## Hypothesis

On the same fixed out-and-back trajectory, memory `on` should accumulate
Grounding-DINO positive evidence across frames and revisits until the policy
chooses `TRUST`. Memory `off` should act as a strict single-frame baseline and
therefore should mostly stay in `VERIFY`, even when the detector sees the
target, because one frame of evidence is not enough to overcome verification
cost.

## Boundary

This is a memory-only / replay-style simulation, not a full ObjectNav navigation
run:

- The trajectory is the deterministic `out_and_back` action sequence.
- `--no-stop-on-trust` keeps all 15 observation rows per replay so recall and
  false-trust behavior can be inspected after the first trust event.
- The success proxy is `oracle_stop_success`: `TRUST` while the oracle target is
  visible in the current frame.
- The run does not report official Habitat ObjectNav success, SPL, path length,
  or learned-policy behavior.
- Memory `off` currently resets to `INITIAL_BELIEF` before applying each frame's
  evidence. It is a single-frame baseline, not an episode-local accumulating
  memory.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `7ae7de8` |
| Machine | `badger-linux`, via `ssh badger@100.88.131.52` |
| Dataset | HM3D ObjectNav `val_mini` |
| Simulator | Habitat-Sim / Habitat-Lab in conda env `habitat` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Detector cap | `grounding_dino_max_image_side=384` |
| Habitat render resolution | `1280x720` |
| Noise levels | `clean,mild,heavy` |
| Memory modes | `on,off` |
| Categories | `bed,sofa,toilet,plant,tv_monitor` |
| Episodes per category | `2` |
| Seed | `313` |
| Output | `runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384` |

`chair` was intentionally excluded from this first memory matrix because the
previous Grounding-DINO qualification found that first-N chair samples were
blocked by target visibility rather than clean detector capability.

## Command

Preflight:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --output runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_preflight --noise-levels clean,mild,heavy --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --memory-ablation on,off --episodes-per-category 2 --target-categories bed,sofa,toilet,plant,tv_monitor --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --preflight-only'
```

Main run:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384 --noise-levels clean,mild,heavy --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --memory-ablation on,off --episodes-per-category 2 --target-categories bed,sofa,toilet,plant,tv_monitor --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --seed 313'
```

Artifact check:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && git rev-parse --short HEAD && test -s runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384/summary.json && test -s runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384/rgb_noise_trace.csv && /home/badger/anaconda3/bin/conda run -n habitat python -c "import json, pathlib; p=pathlib.Path(\"runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384/summary.json\"); s=json.loads(p.read_text()); print(s[\"episodes_completed\"], s[\"trace_rows\"], s[\"oracle_stop_success_rows\"], s[\"sensor_resolution\"], s[\"detector\"], s[\"grounding_dino_max_image_side\"])"'
```

Output:

```text
7ae7de8
60 900 268 1280x720 grounding_dino 384
```

## Overall Metrics

| Metric | Value | Notes |
|---|---:|---|
| Replay runs completed | `60` | 5 categories x 2 episodes x 3 noise levels x 2 memory modes |
| Trace rows | `900` | 15 rows per replay run |
| Target-visible rows | `636` | 318 per memory mode |
| Positive evidence rows | `696` | Same detector observations are reused for memory `on/off` |
| Non-confirmation rows | `48` | Visible oracle target but detector did not provide enough usable mask evidence |
| Unknown rows | `156` | Reset or target-out-of-view / weak observation |
| Trust decisions | `372` | All from memory `on` |
| Oracle-stop success rows | `268` | All from memory `on` |
| Mean detector precision | `0.315586` | Averaged over trace rows |
| Mean oracle recall | `0.637678` | Averaged over trace rows |
| Mean final `p_valid` | `0.888971` | Averaged over replay summaries |

## Memory On/Off Result

| Memory mode | Rows | Visible rows | Positive rows | Trust rows | Oracle-stop success rows | False-trust rows | Mean row `p_valid` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `off` | 450 | 318 | 348 | 0 | 0 | 0 | 0.765035 |
| `on` | 450 | 318 | 348 | 372 | 268 | 104 | 0.924046 |

Interpretation:

- The detector input is identical for memory `on` and `off`; the positive,
  non-confirmation, and unknown evidence counts are therefore identical by
  design.
- Memory `off` never reaches `TRUST` because it applies each frame's evidence
  to `INITIAL_BELIEF` and discards the accumulated belief before the next row.
- Memory `on` accumulates evidence across the replay and reaches `TRUST` in 27
  of 30 replay summaries, yielding 268 oracle-stop success rows.
- The memory path is therefore active and useful in this controlled replay, but
  the memory-off baseline is intentionally harsh.

## Noise Breakdown

| Noise | Memory | Replay runs | Visible rows | Positive rows | Trust rows | Oracle-stop success rows | Success replay runs | Mean final `p_valid` |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `clean` | `off` | 10 | 106 | 120 | 0 | 0 | 0 | 0.811041 |
| `clean` | `on` | 10 | 106 | 120 | 107 | 80 | 9 | 0.988713 |
| `mild` | `off` | 10 | 106 | 114 | 0 | 0 | 0 | 0.811041 |
| `mild` | `on` | 10 | 106 | 114 | 137 | 95 | 10 | 0.969093 |
| `heavy` | `off` | 10 | 106 | 114 | 0 | 0 | 0 | 0.811041 |
| `heavy` | `on` | 10 | 106 | 114 | 128 | 93 | 9 | 0.942898 |

The heavy and mild noise runs did not collapse detector recall in this selected
matrix. That is useful, but it should not be over-read: the category/view
composition dominates this small sample, and Grounding-DINO at cap 384 can still
produce over-confident boxes when the target is not currently visible.

## Category Breakdown

| Category | Memory | Visible rows | Positive rows | Trust rows | Oracle-stop success rows | False-trust rows | Result |
|---|---|---:|---:|---:|---:|---:|---|
| `bed` | `off` | 90 | 84 | 0 | 0 | 0 | Baseline never trusts |
| `bed` | `on` | 90 | 84 | 87 | 87 | 0 | Strong |
| `sofa` | `off` | 90 | 84 | 0 | 0 | 0 | Baseline never trusts |
| `sofa` | `on` | 90 | 84 | 84 | 84 | 0 | Strong |
| `toilet` | `off` | 84 | 84 | 0 | 0 | 0 | Baseline never trusts |
| `toilet` | `on` | 84 | 84 | 87 | 81 | 6 | Strong, minor out-of-view trust |
| `plant` | `off` | 42 | 16 | 0 | 0 | 0 | Baseline never trusts |
| `plant` | `on` | 42 | 16 | 27 | 6 | 21 | Weak, sparse/low-quality evidence |
| `tv_monitor` | `off` | 12 | 80 | 0 | 0 | 0 | Baseline never trusts |
| `tv_monitor` | `on` | 12 | 80 | 87 | 10 | 77 | Not ready as a success claim |

The category story is more important than the single aggregate number:

- `bed`, `sofa`, and `toilet` are the cleanest memory-only positives.
- `plant` produces some successes, but most `TRUST` rows happen when the oracle
  target is not currently visible.
- `tv_monitor` is still sparse-view sensitive. It gets many Grounding-DINO
  positive rows, but only 12 oracle-visible rows across all replay rows, so its
  high trust count mostly measures memory confidence rather than current-frame
  success.

## Revisit Proxy

Using `step_index >= 8` as a rough second-half replay proxy:

| Noise | Memory | Late rows | Late visible rows | Late positive rows | Late trust rows | Late success rows | Late false-trust rows |
|---|---|---:|---:|---:|---:|---:|---:|
| `clean` | `off` | 70 | 52 | 64 | 0 | 0 | 0 |
| `clean` | `on` | 70 | 52 | 64 | 58 | 42 | 16 |
| `mild` | `off` | 70 | 52 | 58 | 0 | 0 | 0 |
| `mild` | `on` | 70 | 52 | 58 | 57 | 41 | 16 |
| `heavy` | `off` | 70 | 52 | 58 | 0 | 0 | 0 |
| `heavy` | `on` | 70 | 52 | 58 | 56 | 40 | 16 |

This supports the replay-level memory claim: when the path revisits the area,
memory `on` keeps enough accumulated belief to choose `TRUST`, while memory
`off` does not. It also shows the next risk: some late `TRUST` decisions occur
out of the current oracle view and need a stronger current-view or geometric
gate before this can become a robot stop policy.

## Result

The current memory-only / replay-style harness can run the intended
`clean/mild/heavy x memory on/off` matrix with Grounding-DINO at `1280x720` and
produces a clear controlled result:

- Memory `on` turns repeated detector evidence into trust and oracle-stop
  success on fixed trajectories.
- Memory `off` is a single-frame baseline and never trusts under the current
  policy.
- The best supported categories for the next memory experiment are still
  `bed`, `sofa`, and `toilet`.
- `plant` and `tv_monitor` need false-trust / current-view gating before their
  rows can be used as a strong success claim.

This is useful evidence that the memory update and decision path works in
Habitat replay, but it is not yet evidence that a navigation stack can find an
object or improve SPL.

## Follow-Up

1. Add an `episode_local` ablation between `on` and `off` so the comparison can
   separate within-episode accumulation from cross-episode lifelong memory.
2. Add a current-view confirmation gate for stop decisions, especially for
   sparse categories like `tv_monitor`.
3. Implement visibility-aware episode selection before reintroducing `chair`.
4. Add debug frame export for false-trust rows so `plant` and `tv_monitor`
   errors can be separated into detector false positives, oracle visibility
   sparsity, and view geometry issues.
5. Only after those checks, connect this replay harness to a real navigation
   policy or Habitat follower and report navigation metrics.
