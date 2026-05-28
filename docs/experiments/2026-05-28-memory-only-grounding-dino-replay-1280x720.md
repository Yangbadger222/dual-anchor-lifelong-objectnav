# Experiment Report: Memory-Only Grounding-DINO Replay At 1280x720

Date: 2026-05-28  
Owner: Codex  
Status: Completed, controlled replay result updated with `naive_count` and shared gate

## Question

With the navigation system still absent, can the current Habitat replay harness
validate the ObjectNav memory path by holding the trajectory fixed and comparing
Grounding-DINO observations across:

- `memory=on`: the Dual-Anchor / Lifelong memory path.
- `memory=naive_count`: a deliberately simple accumulating baseline that only
  counts positive detector evidence inside the current replay.
- `memory=off`: a single-frame sanity baseline.

The run also asks whether a shared decision-side current-positive gate reduces
`plant` and `tv_monitor` false-trust without unfairly benefiting one memory
mode.

## Hypothesis

Memory `on` and `naive_count` should both beat the single-frame `off` baseline
because they accumulate evidence across replay observations. The shared gate
should reduce out-of-view false-trust for sparse categories by allowing raw
`TRUST` to become gated `TRUST` only when the current frame has target
visibility and positive detector evidence.

## Boundary

This is a memory-only / replay-style simulation, not a full ObjectNav navigation
run:

- The trajectory is the deterministic `out_and_back` action sequence.
- `--no-stop-on-trust` keeps all 15 observation rows per replay so recall and
  gate rejection can be inspected after the first trust event.
- The success proxy is `oracle_stop_success`: gated `TRUST` while the oracle
  target is visible in the current frame.
- The run does not report official Habitat ObjectNav success, SPL, path length,
  or learned-policy behavior.
- `memory=off` applies each frame's evidence to `INITIAL_BELIEF` and discards
  that belief before the next row.
- `memory=naive_count` only counts positive evidence. It ignores
  non-confirmation and unknown observations, has no geometry, has no delayed
  birth model, and does not persist across episodes. In this run, two positives
  are required before it crosses the trust threshold.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `df8a3e2` |
| Machine | `badger-linux`, via `ssh badger@100.88.131.52` |
| Dataset | HM3D ObjectNav `val_mini` |
| Simulator | Habitat-Sim / Habitat-Lab in conda env `habitat` |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Detector cap | `grounding_dino_max_image_side=384` |
| Habitat render resolution | `1280x720` |
| Noise levels | `clean,mild,heavy` |
| Memory modes | `on,naive_count,off` |
| Categories | `bed,sofa,toilet,plant,tv_monitor` |
| Episodes per category | `2` |
| Seed | `313` |
| Output | `runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384_naive_count_gate` |

`chair` remains excluded because previous Grounding-DINO qualification showed
that first-N chair samples are blocked by target visibility rather than clean
detector capability.

## Command

Preflight:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --output runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384_naive_count_gate_preflight --noise-levels clean,mild,heavy --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --memory-ablation on,naive_count,off --episodes-per-category 2 --target-categories bed,sofa,toilet,plant,tv_monitor --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --preflight-only'
```

Main run:

```bash
ssh badger@100.88.131.52 \
  'cd ~/Desktop/dual-anchor-lifelong-objectnav && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_usability/memory_only_grounding_dino_replay_1280x720_epc2_cap384_naive_count_gate --noise-levels clean,mild,heavy --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --memory-ablation on,naive_count,off --episodes-per-category 2 --target-categories bed,sofa,toilet,plant,tv_monitor --sensor-width 1280 --sensor-height 720 --yolo-prompt-mode target --no-stop-on-trust --seed 313'
```

## Overall Metrics

| Metric | Value | Notes |
|---|---:|---|
| Replay runs completed | `90` | 5 categories x 2 episodes x 3 noise levels x 3 memory modes |
| Trace rows | `1350` | 15 rows per replay run |
| Target-visible rows | `954` | 318 per memory mode |
| Positive evidence rows | `1044` | Same detector configuration across modes |
| Non-confirmation rows | `72` | Visible oracle target but insufficient detector mask evidence |
| Unknown rows | `234` | Reset or target-out-of-view / weak observation |
| Raw trust rows | `694` | Before the shared current-positive gate |
| Gated trust rows | `488` | After the shared decision-side gate |
| Gate rejections | `206` | Raw `TRUST` changed to `VERIFY` |
| Oracle-stop success rows | `488` | Equal to gated trust because gated trust requires current visible positive |
| Mean detector precision | `0.315586` | Averaged over trace rows |
| Mean oracle recall | `0.637678` | Averaged over trace rows |
| Mean final `p_valid` | `0.903922` | Averaged over replay summaries |

Gate reasons:

| Reason | Rows | Interpretation |
|---|---:|---|
| `current_positive_confirmation` | 488 | Raw trust accepted by shared gate |
| `target_not_currently_visible` | 184 | Main false-trust source, especially `tv_monitor` |
| `missing_current_positive_evidence` | 22 | Target visible or memory confident, but current detector evidence not positive |
| `not_raw_trust` | 656 | Policy did not request trust |

## Memory Mode Result

| Memory mode | Rows | Visible rows | Positive rows | Raw trust | Gated trust / success | Gate rejections | Mean row `p_valid` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `on` | 450 | 318 | 348 | 372 | 246 | 126 | 0.924046 |
| `naive_count` | 450 | 318 | 348 | 322 | 242 | 80 | 0.863564 |
| `off` | 450 | 318 | 348 | 0 | 0 | 0 | 0.765035 |

Interpretation:

- `off` remains a useful lower sanity check: one frame of evidence does not
  reach trust.
- `naive_count` is now the fairer accumulating baseline. It performs nearly as
  well as memory `on` in this fixed replay matrix.
- The current replay result therefore supports the claim that positive evidence
  accumulation matters, but it does not yet demonstrate that Dual-Anchor /
  Lifelong memory beats a naive positive-count baseline.
- The shared gate materially changes the result: old raw memory confidence is
  no longer counted as success unless the current frame confirms the target.

## Noise Breakdown

| Noise | Memory | Replay runs | Visible rows | Success rows | Success replay runs | Mean final `p_valid` |
|---|---|---:|---:|---:|---:|---:|
| `clean` | `on` | 10 | 106 | 77 | 9 | 0.988713 |
| `clean` | `naive_count` | 10 | 106 | 82 | 10 | 0.941192 |
| `clean` | `off` | 10 | 106 | 0 | 0 | 0.811041 |
| `mild` | `on` | 10 | 106 | 85 | 9 | 0.969093 |
| `mild` | `naive_count` | 10 | 106 | 81 | 10 | 0.941192 |
| `mild` | `off` | 10 | 106 | 0 | 0 | 0.811041 |
| `heavy` | `on` | 10 | 106 | 84 | 8 | 0.942898 |
| `heavy` | `naive_count` | 10 | 106 | 79 | 9 | 0.919092 |
| `heavy` | `off` | 10 | 106 | 0 | 0 | 0.811041 |

Mild/heavy noise still does not collapse Grounding-DINO in this selected matrix.
The main differences come from category visibility and whether raw memory trust
is accepted by the current-positive gate.

## Category Breakdown

| Category | Memory | Visible rows | Positive rows | Raw trust | Gated success | Gate rejections | Rejection rate |
|---|---|---:|---:|---:|---:|---:|---:|
| `bed` | `on` | 90 | 84 | 87 | 82 | 5 | 0.057 |
| `bed` | `naive_count` | 90 | 84 | 78 | 78 | 0 | 0.000 |
| `bed` | `off` | 90 | 84 | 0 | 0 | 0 | n/a |
| `sofa` | `on` | 90 | 84 | 84 | 80 | 4 | 0.048 |
| `sofa` | `naive_count` | 90 | 84 | 78 | 78 | 0 | 0.000 |
| `sofa` | `off` | 90 | 84 | 0 | 0 | 0 | n/a |
| `toilet` | `on` | 84 | 84 | 87 | 76 | 11 | 0.126 |
| `toilet` | `naive_count` | 84 | 84 | 78 | 72 | 6 | 0.077 |
| `toilet` | `off` | 84 | 84 | 0 | 0 | 0 | n/a |
| `plant` | `on` | 42 | 16 | 27 | 3 | 24 | 0.889 |
| `plant` | `naive_count` | 42 | 16 | 10 | 8 | 2 | 0.200 |
| `plant` | `off` | 42 | 16 | 0 | 0 | 0 | n/a |
| `tv_monitor` | `on` | 12 | 80 | 87 | 5 | 82 | 0.943 |
| `tv_monitor` | `naive_count` | 12 | 80 | 78 | 6 | 72 | 0.923 |
| `tv_monitor` | `off` | 12 | 80 | 0 | 0 | 0 | n/a |

The shared gate fixes the main reporting failure from the previous run:
`tv_monitor` still produces many raw trust rows because detections accumulate
while the target is sparse, but those rows are mostly rejected as
`target_not_currently_visible`.

The category result is now:

- `bed`, `sofa`, and `toilet` are still the strongest controlled replay
  positives.
- `plant` is weak for memory `on` under the gate because many raw trusts happen
  without current positive confirmation.
- `tv_monitor` remains sparse-view sensitive and should not be used as a strong
  success claim yet.

## Revisit Proxy

Using `step_index >= 8` as a rough second-half replay proxy:

| Memory | Late rows | Late visible rows | Late positive rows | Late raw trust | Late gated success | Late gate rejections |
|---|---:|---:|---:|---:|---:|---:|
| `on` | 210 | 156 | 180 | 171 | 123 | 48 |
| `naive_count` | 210 | 156 | 180 | 178 | 128 | 50 |
| `off` | 210 | 156 | 180 | 0 | 0 | 0 |

Both accumulating methods trust on revisits. This is good for the replay
pipeline, but it is not yet a Dual-Anchor advantage because `naive_count` is
competitive.

## Result

The updated memory-only replay matrix gives a sharper and more honest result:

- The previous `off` baseline was too weak for the main comparison.
- The new `naive_count` baseline confirms that simple positive accumulation
  already explains much of the replay success.
- The shared decision gate substantially reduces `plant` and `tv_monitor`
  false-trust by rejecting raw `TRUST` without current target visibility or
  current positive evidence.
- Under this fixed replay protocol, Dual-Anchor / Lifelong memory is not yet
  better than the naive positive-count baseline. The current evidence supports
  "accumulation helps", not "our memory algorithm beats a naive accumulator."

## Follow-Up

1. Add diagnostics for why memory `on` has more gate rejections than
   `naive_count` on `plant` and `tv_monitor`.
2. Add a task where naive count should fail: cross-episode object persistence,
   scene-change handling, negative evidence, or geometry consistency.
3. Generate debug PNGs for `plant` and `tv_monitor` gate rejections.
4. Add visibility-aware episode selection before reintroducing `chair`.
5. Only after those checks, connect this replay harness to a real navigation
   policy or Habitat follower and report navigation metrics.

## Historical Note

The earlier `7ae7de8` run used only `memory=on/off` and no shared gate. It
reported 268 memory-on success rows and 104 false-trust rows. That result is now
superseded for algorithm comparison by this `df8a3e2` run because it includes a
non-strawman accumulating baseline and applies the same trust gate to all
memory modes.
