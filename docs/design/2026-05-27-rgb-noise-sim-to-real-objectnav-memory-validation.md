# Design Doc: RGB-Noise-Driven Sim-to-Real Validation for ObjectNav Memory Algorithm

Date: 2026-05-27
Owner: Codex (analysis), badger (decision)
Status: Approved

## Locked Decisions (2026-05-27)

| Item | Decision | Rationale |
|---|---|---|
| Publication target | Robotics systems venues (ICRA / IROS / RA-L / CoRL); not HM3D ObjectNav leaderboard | [decision record](../decisions/2026-05-27-publication-target-robotics-systems-no-benchmark-grinding.md) |
| Object detector | **YOLO-World** (open-vocabulary, single small/medium model) | Fits 4070 Laptop GPU, real-time, supports text prompts for the 6 HM3D ObjectNav categories without retraining |
| RGB noise model | Poisson-Gaussian heteroscedastic (Foi et al. 2008) + motion blur (Brooks et al. 2019) + JPEG quality | Published models, fully citable, no real-camera recording required for v1 |
| Depth noise model | Axial+lateral noise as in Nguyen et al. 2012, parameterized for **Intel RealSense D435** | Target real hardware is D435; depth noise is load-bearing for memory geometry on real robot |
| Noise levels | `clean / mild / heavy`, 3 levels per axis | Smallest grid that supports a "noise vs memory utility" claim |
| Noise profile provenance | YAML file with `provenance: published_model` for v1; later overridden by `provenance: calibrated_d435_<date>` once a real D435 bag is recorded | Lets us start without hardware and refine without code changes |
| Cross-episode memory | Persisted per scene, keyed by `(scene_id, episode_dataset_version)` | Required to test the *Lifelong* claim |
| Revisit strategy | `out_and_back` controller as v1; frontier-based revisit deferred | Minimum that exercises Dual-Anchor without building a planner |
| ObjectNav success metric | Oracle stop (`TRUST` while within 1.0 m and target in view) for v1 | Acceptable under the robotics-systems venue decision; no learned policy needed |

## Goal

Validate the Dual-Anchor Lifelong ObjectNav memory algorithm in Habitat so
that the result is meaningful evidence for deploying on a real robot.

Concretely:

1. Inject realistic **RGB camera noise** into Habitat observations so that
   detection/memory failures observed in simulation correspond to failures the
   real robot will see.
2. Run a **real object detector** on those noisy RGB frames instead of
   corrupting Habitat's oracle semantic mask, so that memory is exposed to
   real detector failure modes (correlated, confidence-driven, not just
   geometric).
3. Drive the agent with a controller that **revisits the same target**, so
   that the *Lifelong* and *Dual-Anchor* parts of the algorithm actually
   execute in simulation.
4. Produce a result table that supports the claim:
   *"under realistic RGB noise, the memory algorithm improves ObjectNav
   reliability compared to a memoryless baseline."*

## Non-Goals

- Reporting official Habitat ObjectNav benchmark numbers (success / SPL on
  the full HM3D `val` split). This work is a sim-to-real preflight, not a
  benchmark submission.
- Training a new learned navigation policy. The agent only needs to be
  capable enough to revisit targets.
- Training a new object detector. Use an off-the-shelf open-vocabulary
  detector for the 6 ObjectNav categories.
- Modeling every possible sensor failure. The RGB noise set must be small,
  documented, and tied to known real-camera failure modes.

## Background

### What Codex has done so far

Four Habitat experiments exist (see
[docs/experiments/](../experiments/) entries dated 2026-05-26..27).
All four runners share the same skeleton:

```
1. Take official HM3D ObjectNav val_mini episode metadata
2. Teleport agent to start (or goal viewpoint)
3. Execute a fixed 6-step action sequence:
   turn_left, move_forward, turn_right, move_forward, turn_left, move_forward
4. Per step: grab RGB / depth / semantic, corrupt the oracle semantic mask
   with a "YOLO-breaker" (miss / fly_point / edge_break / mixed),
   feed corrupted mask to UsabilityUpdater, append a trace row.
5. Reset for next episode. Memory is not persisted across episodes.
```

The runner is
[habitat_objectnav_valmini_semantic_stress.py](../../src/objectnav_core/objectnav_core/evaluation/habitat_objectnav_valmini_semantic_stress.py)
and CLI
[run_habitat_objectnav_valmini_semantic_stress.py](../../src/objectnav_core/objectnav_core/cli/run_habitat_objectnav_valmini_semantic_stress.py).
Default action set is defined in
[habitat_semantic_yolo_stress.py](../../src/objectnav_core/objectnav_core/evaluation/habitat_semantic_yolo_stress.py).

### Why this does not yet validate the algorithm for real-robot deployment

| Concern | Current state | Real-world consequence |
|---|---|---|
| Noise injection layer | Mask geometry is corrupted post hoc | Real failures originate from RGB noise upstream of the detector and are *correlated* (motion blur affects mask shape, confidence, and depth alignment together). Mask-only corruption does not capture this. |
| Detector | No real detector runs; oracle semantic ids are used | The memory layer never sees real detector confidence distributions, real false-positive categories, or real recall-vs-distance curves. |
| Action policy | Fixed 6 scripted actions, no revisit | The *Lifelong* and *Dual-Anchor* paths of the algorithm (recall → re-observe → fuse) are not triggered. The current results test only single-encounter updates. |
| Episode memory | Memory is cleared every reset | The *Lifelong* claim is not tested at all. |
| Navigation metric | None (no `stop`, no success, no SPL) | No quantitative bridge to ObjectNav literature, and no way to express "memory helps" as a navigation outcome. |

The drop in `p_valid` observed when moving from a single hand-picked scene
(0.909 clean) to official `val_mini` (0.757) and to `episode_start` (0.626)
is not a regression in the algorithm; it is the test setup exposing harder
categories, harder viewpoints, and (under `episode_start`) target
invisibility. See
[docs/experiments/2026-05-27-habitat-objectnav-valmini-semantic-stress.md](../experiments/2026-05-27-habitat-objectnav-valmini-semantic-stress.md)
and
[docs/experiments/2026-05-27-habitat-valmini-episode-start-confirmation.md](../experiments/2026-05-27-habitat-valmini-episode-start-confirmation.md).

## System Boundary

This design owns:

- An **RGB noise pipeline** implementing Foi 2008 Poisson-Gaussian + Brooks
  2019 motion blur + JPEG quality, configurable through a YAML profile,
  applied to every Habitat RGB observation before any downstream module
  sees it.
- A **depth noise pipeline** implementing Nguyen 2012 axial + lateral noise
  for Intel RealSense D435, applied to Habitat depth observations.
- A **detector adapter** wrapping **YOLO-World** (Ultralytics
  `YOLOWorld('yolov8s-worldv2.pt')` or equivalent) that produces per-frame
  `(category, bbox, confidence, mask)` tuples. For the ObjectNav harness the
  default prompt policy is target-conditioned: YOLO-World is prompted with the
  current episode goal category rather than the full 6-category set. This
  matches the ObjectNav interface, where the goal category is known, and avoids
  open-vocabulary class competition such as visible `toilet` regions being
  labeled `bed`. The legacy full category prompt set remains available as
  `--yolo-prompt-mode all_categories` for ablations. Masks are derived from
  boxes (axis-aligned) for v1; instance masks via YOLO-World's segmentation head
  are deferred to v2.
- A **revisit controller** (`out_and_back`) that produces an action
  sequence guaranteed to view the target from ≥2 distinct viewpoints with
  a non-target interval in between.
- A **lifelong harness** that persists `UsabilityUpdater` / dual-anchor
  memory state across episodes within the same scene, using
  [sqlite_store.py](../../src/objectnav_core/objectnav_core/memory/sqlite_store.py)
  keyed by `(scene_id, episode_dataset_version)`.
- An **evaluator** that computes both perception-level metrics (detection
  P/R by noise level, against oracle GT masks) and memory-level metrics
  (recall@revisit, false-trust rate, time-to-trust, cross-episode recall).

This design depends on:

- Habitat-Sim 0.3.3 RGB + depth + semantic sensors (already installed).
- HM3D `val_mini` scenes + episodes (already on disk).
- `ultralytics >= 8.3` for YOLO-World (new dependency, CPU/GPU optional).
- The existing
  [UsabilityUpdater](../../src/objectnav_core/objectnav_core/memory/usability.py)
  and the
  [sqlite_store.py](../../src/objectnav_core/objectnav_core/memory/sqlite_store.py)
  memory backend.

This design explicitly does **not** own:

- Modifications to UsabilityUpdater math. If the noise pipeline reveals
  bugs, those are tracked separately.
- A learned navigation policy.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Habitat RGB obs | `np.uint8 [H, W, 3]` | From Habitat-Sim direct sensor |
| Input | Habitat depth obs | `np.float32 [H, W]` | Used for memory geometry + optional depth noise |
| Input | Habitat oracle semantic mask | `np.uint32 [H, W]` | Used **only** to compute ground-truth target-visibility, never fed to the algorithm |
| Input | Episode metadata | `val_mini/*.json.gz` | Scene id, target category, episode start, goal viewpoints |
| Input | Noise profile | YAML | Per-level parameters for each noise type |
| Output | Trace rows | JSONL | One per step: pose, GT visibility, detector outputs, memory state |
| Output | Per-run summary | JSON | Aggregated metrics by noise level, by category, by revisit count |
| Output | Optional debug PNGs | `runs/.../debug/` | Side-by-side: clean RGB, noisy RGB, detector mask, GT mask |

## Interfaces

CLI (new):

```bash
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_usability/rgb_noise_stress_v1 \
  --rgb-noise-profile configs/noise/rgb_published_v1.yaml \
  --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml \
  --noise-levels clean,mild,heavy \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --revisit-strategy out_and_back \
  --lifelong persistent_per_scene \
  --memory-ablation on,off \
  --max-episodes 30 \
  --stop-on-trust \
  --seed 313
```

Python interfaces (new):

- `simulation/rgb_noise.py`
  - `class RgbNoisePipeline(profile: RgbNoiseProfile, seed: int)`
  - `apply(rgb: np.uint8[H,W,3], agent_motion: AgentMotion, level: str) -> np.uint8[H,W,3]`
  - Internal ops: `PoissonGaussianNoise` (Foi 2008),
    `MotionBlur` (Brooks 2019, PSF from `agent_motion` × exposure),
    `JpegCompression`.
- `simulation/depth_noise.py`
  - `class DepthNoisePipelineD435(profile: DepthNoiseProfile, seed: int)`
  - `apply(depth: np.float32[H,W], surface_normals: np.float32[H,W,3] | None, level: str) -> np.float32[H,W]`
  - Internal ops: `AxialNoise` (σ_z = α·z²), `LateralNoise` (σ_xy
    grows with incidence angle), `DepthHoles` (drop pixels where
    z > z_max or low-confidence proxy).
- `perception/yolo_world_adapter.py`
  - `class YoloWorldDetector(weights: str, categories: list[str], conf: float, device: str)`
  - `detect(rgb: np.uint8[H,W,3]) -> list[Detection]`
  - `Detection = (category: str, bbox: tuple[int,int,int,int], confidence: float, mask: np.bool_[H,W])`
- `simulation/revisit_controller.py`
  - `class OutAndBackController(forward_actions)`
  - `actions_for_episode(start_pose, target_pose) -> list[str]`
  - V1 uses deterministic Habitat actions to create a target revisit interval.
    Navmesh-aware `ShortestPathFollower` revisit remains a later upgrade.
- `evaluation/lifelong_memory_harness.py`
  - `class LifelongMemoryHarness(memory_store, scene_id, dataset_version)`
  - Loads / persists memory keyed by `(scene_id, dataset_version)`.
  - Wraps episode loop, runs noise → detector → memory chain.

## Noise Model Specification

All noise operations are deterministic given a seed and a pixel position.
Each op is independently switchable in the YAML profile so that ablation by
op is possible without code changes.

### RGB noise pipeline

Applied in order: `motion_blur → poisson_gaussian → jpeg`.

**1. Poisson-Gaussian heteroscedastic noise** (Foi et al., *Practical
Poissonian-Gaussian noise modeling and fitting for single-image raw-data*,
IEEE TIP 2008):

```
I_noisy(x) = I_clean(x) + n(x),    n(x) ~ N(0, σ²(I_clean(x)))
σ²(I) = a · I + b
```

`I` is normalized to `[0, 1]`. `a` is the shot-noise coefficient (scales
with sensor gain / ISO). `b` is the read-noise variance.

| Level | `a` | `b` | Approx. real condition |
|---|---:|---:|---|
| clean | 0 | 0 | Identity (sanity) |
| mild  | 0.005 | 0.0005 | Indoor, good light, low ISO |
| heavy | 0.020 | 0.0050 | Low light, high ISO, gain-up |

**2. Motion blur** (Brooks et al., *Unprocessing Images for Learned Raw
Denoising*, CVPR 2019; classical line PSF for translation, arc PSF for
rotation):

```
I_blur = I_clean ⊛ PSF(Δp, Δθ, t_exp)
```

`Δp` = agent translation between previous and current Habitat step
(meters), `Δθ` = agent rotation (rad), `t_exp` = simulated exposure time
(seconds). The PSF length in pixels is computed from the projected image-
plane displacement of a point at depth `z_ref = 2.0 m` using the Habitat
RGB sensor intrinsics.

| Level | `t_exp` (ms) | Notes |
|---|---:|---|
| clean | 0 | PSF = δ, no blur |
| mild  | 15 | Typical indoor auto-exposure |
| heavy | 40 | Low-light long exposure |

The default Habitat actions in
[`DEFAULT_ACTIONS`](../../src/objectnav_core/objectnav_core/evaluation/habitat_semantic_yolo_stress.py#L23)
move 0.25 m per `move_forward` and 30° per turn, which yields
deterministic per-step PSF lengths once `t_exp` is fixed.

**3. JPEG compression**:

```
I_jpeg = JPEG_decode(JPEG_encode(I, quality=Q))
```

Implementation: `cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, Q])`.

| Level | `Q` | Notes |
|---|---:|---|
| clean | 100 | Effectively lossless |
| mild  | 80  | Typical webcam/ROS image_transport default |
| heavy | 50  | Aggressive compression / bandwidth-limited link |

### Depth noise pipeline (Intel RealSense D435)

Applied in order: `axial_noise → lateral_noise → holes`.

**1. Axial noise** (Nguyen et al., *Modeling Kinect Sensor Noise for
Improved 3D Reconstruction and Tracking*, 3DIMPVT 2012; D435 white-paper
values):

```
σ_z(z) = α · z²      (meters; z in meters)
```

| Level | `α` | Notes |
|---|---:|---|
| clean | 0 | Identity |
| mild  | 0.0025 | D435 indoor, well-lit, 1 m–3 m sweet spot |
| heavy | 0.0080 | D435 in dim light, IR projector saturated, > 3 m |

**2. Lateral noise** (incidence-angle term):

```
σ_xy(z, θ) = β · z / cos(θ)
```

`θ` is the angle between the surface normal and the optical axis. When
surface normals are not available, `θ` is estimated from local depth
gradient. `β` defaults: `clean=0`, `mild=0.001`, `heavy=0.004` (meters).

**3. Holes**:

```
mask_hole = (z > z_max) ∨ (z < z_min) ∨ Bernoulli(p_drop)
depth[mask_hole] = NaN
```

| Level | `z_min` (m) | `z_max` (m) | `p_drop` |
|---|---:|---:|---:|
| clean | 0.1 | 10.0 | 0.000 |
| mild  | 0.2 |  4.0 | 0.005 |
| heavy | 0.3 |  3.0 | 0.030 |

The downstream memory geometry must treat NaN depth pixels as "no
measurement" rather than as zero distance; this is a verification check.

### YAML profile format

`configs/noise/rgb_published_v1.yaml`:

```yaml
provenance: published_model
references:
  - Foi 2008 IEEE TIP
  - Brooks 2019 CVPR
levels:
  clean: { pg: { a: 0.0,   b: 0.0     }, blur: { t_exp_ms: 0  }, jpeg: { q: 100 } }
  mild:  { pg: { a: 0.005, b: 0.0005  }, blur: { t_exp_ms: 15 }, jpeg: { q: 80  } }
  heavy: { pg: { a: 0.020, b: 0.0050  }, blur: { t_exp_ms: 40 }, jpeg: { q: 50  } }
```

`configs/noise/depth_realsense_d435_v1.yaml`:

```yaml
provenance: published_model
target_camera: Intel RealSense D435
references:
  - Nguyen 2012 3DIMPVT
  - Intel D400 series datasheet
levels:
  clean: { axial: { alpha: 0.0    }, lateral: { beta: 0.0   }, holes: { zmin: 0.1, zmax: 10.0, p_drop: 0.000 } }
  mild:  { axial: { alpha: 0.0025 }, lateral: { beta: 0.001 }, holes: { zmin: 0.2, zmax:  4.0, p_drop: 0.005 } }
  heavy: { axial: { alpha: 0.0080 }, lateral: { beta: 0.004 }, holes: { zmin: 0.3, zmax:  3.0, p_drop: 0.030 } }
```

When a real D435 bag is later recorded, only the `levels` block changes
and `provenance` becomes `calibrated_d435_<date>`.

## Data Flow

```diagram
╭──────────────╮  rgb   ╭──────────────╮  noisy_rgb  ╭───────────────╮
│  Habitat-Sim │───────▶│ RgbNoisePipe │────────────▶│ OpenVocab     │
│  RGB sensor  │        ╰──────────────╯             │ Detector      │
╰──────┬───────╯                                     ╰──────┬────────╯
       │ depth (optional DepthNoise)                        │ detections
       ▼                                                    ▼
╭──────────────╮                              ╭──────────────────────╮
│ UsabilityUpd │◀─────────────────────────────│ Detection → Evidence │
│ + DualAnchor │                              ╰──────────────────────╯
╰──────┬───────╯
       │ memory state                  ╭──────────────────────╮
       ▼                               │ Oracle semantic mask │ ── GT visibility
╭──────────────╮                       ╰──────────┬───────────╯
│ Trace writer │◀─────────────────────────────────╯
╰──────┬───────╯
       ▼
   runs/.../*.jsonl, summary.json, debug/
```

Per-episode loop:

```
for episode in val_mini:
    if lifelong: load_or_init_memory(scene_id)
    else:        reset_memory()

    pose = teleport(episode.start)
    actions = revisit_controller.actions_for_episode(start, target)

    for action in actions:
        obs = sim.step(action)
        noisy_rgb = noise.apply(obs.rgb, agent_velocity, level)
        detections = detector(noisy_rgb, target_categories)
        gt_visible = oracle_visibility(obs.semantic, target_id)
        evidence = build_evidence(detections, obs.depth, pose)
        memory.update(evidence)
        trace.write(pose, gt_visible, detections, memory.snapshot())
        if stop_on_trust and memory.decision == TRUST and gt_visible:
            break

    if lifelong: persist_memory(scene_id)
```

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Noise pipeline too aggressive: detector recall ~0 at every level | Per-level detection recall vs clean recall in summary | Calibrate noise parameters per level against an external real-camera reference set; expose noise knobs in YAML |
| Detector category mismatch (no class for `tv_monitor`, `plant`) | Pre-flight check: detect on each category's GT crop, log P/R | Use open-vocab prompts; fall back to per-category prompt list in config |
| Edge-clipped target views look oracle-visible but are poor detector evidence | Trace `oracle_bbox`, `oracle_touches_edge`, and `oracle_edge_clearance_ratio` | Stop on valid `TRUST`; improve revisit sampling before treating later edge-clipped misses as detector failures |
| Revisit controller cannot reach the target (navmesh blocked) | Episode flagged `unreachable` in summary | Skip the episode from memory metrics; keep for perception metrics |
| Lifelong memory leaks identity across scenes | Memory key collision check at load | Key by `(scene_id, episode_dataset_version)` only; never share across scenes |
| Memory ablation `off` is not actually memoryless (e.g. uses prior) | Unit test: feed two identical episodes with `off`, expect identical decisions | Implement `off` as fresh `UsabilityUpdater` per step |
| Sim-to-real noise profile is invented, not measured | Document profile provenance in YAML header | Tie each profile to a referenced camera spec or a recorded bag; mark synthetic profiles `provenance: synthetic` |

## Verification Plan

### Unit-level

- `tests/test_rgb_noise.py`: each noise op is deterministic given seed,
  preserves shape/dtype, and respects `level=clean → identity`.
- `tests/test_detector_adapter.py`: dummy detector backend returns the same
  detection list the adapter forwards.
- `tests/test_revisit_controller.py`: `OutAndBackController` produces an
  action list whose simulated end-pose is within ε of the start pose, and
  whose midpoint pose looks at the target.

### Integration-level (Habitat smoke)

- 1 scene, 1 episode, 1 noise level (`clean`), real detector loaded:
  - Memory `on` produces ≥1 confirmed positive when target is visible.
  - Memory `off` produces no persistent state between steps.
  - Trace JSONL parses; debug PNGs render.

### Experiment-level

Run the full 30-episode `val_mini` subset under:

| Noise level | Memory | Revisit | Lifelong | Purpose |
|---|---|---|---|---|
| clean | on | out_and_back | per-scene | Upper bound |
| mild  | on | out_and_back | per-scene | Realistic-noise main result |
| heavy | on | out_and_back | per-scene | Stress test |
| clean | off | out_and_back | n/a | Baseline upper bound |
| mild  | off | out_and_back | n/a | Memory-helps claim, mid-noise |
| heavy | off | out_and_back | n/a | Memory-helps claim, high-noise |

Report:

| Metric | Definition |
|---|---|
| Detection P / R | Per-frame, with oracle-mask GT, by noise level |
| First-positive latency | Steps from first GT visibility to first memory `POSITIVE` |
| False-trust rate | Fraction of `TRUST` decisions whose memory location lies outside the GT instance |
| Recall@revisit | Of episodes where target was confirmed on first visit, fraction still confirmed after the revisit interval |
| Cross-episode recall | Per scene, fraction of `TRUST`s in episode 2..N that reuse memory from episode 1 |
| ObjectNav success (oracle stop) | Memory says `TRUST` while the target is in view; the default runner stops the episode at this point |

The result is acceptable when, at `mild` noise level:

- Memory `on` improves `first-positive latency` by ≥30% over `off`.
- Memory `on` `false-trust rate` ≤ memory `off` `false-trust rate`.
- `cross-episode recall` is strictly > 0 (currently it cannot be, because
  memory is wiped on reset).

## Research Relevance

This is the experiment that supports the central paper claim
*"Dual-Anchor Lifelong semantic memory improves ObjectNav reliability under
realistic perception noise"*. Without it, the repository's current Habitat
work only supports a much weaker claim about mask-corruption robustness of
the usability update rule. It is also the gate for moving to real-robot
trials: noise profiles calibrated here become the spec the real perception
stack must match or beat.

## Open Questions

### Resolved 2026-05-27

| Question | Decision |
|---|---|
| Open-vocab detector | **YOLO-World** (`yolov8s-worldv2.pt` to start; can swap to `yolov8m-worldv2.pt` if recall is low) |
| Noise-profile provenance | Start from **published models** (Foi 2008, Brooks 2019, Nguyen 2012). Calibrated D435 profile is a later refinement; code does not change. |
| Depth noise in v1 | **Yes**, included. Target real camera is RealSense D435, so depth noise is load-bearing for sim-to-real. |
| Memory persistence | Use existing [sqlite_store.py](../../src/objectnav_core/objectnav_core/memory/sqlite_store.py), keyed by `(scene_id, episode_dataset_version)`. |
| Revisit strategy for v1 | `out_and_back` only. Frontier-based multi-target revisit is deferred. |
| ObjectNav success metric for v1 | Oracle stop (memory says `TRUST` while agent is within 1.0 m and target is in view). Acceptable under the robotics-systems venue decision. |
| YOLO-World prompt strategy | Use target-conditioned prompts by default. The full 6-category prompt set is retained only as an ablation/debug mode because it caused class competition on the first visible `toilet` smoke. |

### Still open

- YOLO-World mask source: stay with bbox-derived rectangular masks for v1,
  or switch to YOLO-World seg variants if recall@IoU is too low. Decide
  after smoke.
- Whether to record a small real D435 bag in the same lab as the target
  robot before the main experiment, to bias `mild` parameters toward the
  actual deployment scene. Cheap; recommended but not blocking.
- Whether to add a fourth noise level `extreme` (motion blur ≥ 80 ms +
  JPEG Q=30 + `p_drop=0.1`) to probe the breaking point. Decide after the
  main 6-cell matrix is in.
