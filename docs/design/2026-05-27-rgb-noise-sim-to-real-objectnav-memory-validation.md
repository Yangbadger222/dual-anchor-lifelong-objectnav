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

## Update: Grounding-DINO Detector Comparison (2026-05-28)

The first YOLO-World detector category qualification at `1280x720` showed that
`bed`, `sofa`, and `toilet` are usable, while `plant`, `tv_monitor`, and
`chair` remain blocked by detector and/or visibility issues. The next detector
comparison adds **Grounding-DINO** as a second real open-vocabulary detector
backend under the same harness.

The comparison must preserve the existing evaluation boundary:

- Grounding-DINO replaces only the detector adapter.
- RGB/depth noise, oracle visibility, memory update, stop-on-trust semantics,
  category balancing, and summary metrics remain unchanged.
- Grounding-DINO detections are converted to the same
  `(category, bbox, confidence, mask)` interface as YOLO-World, with masks
  derived from axis-aligned boxes for v1.
- The first run is a clean `1280x720` detector category qualification, not a
  full noise-memory matrix.

This makes the outcome directly comparable with the YOLO-World qualification
report and keeps detector failures separate from memory-algorithm behavior.

## Update: Memory-Only Replay Stage Without Navigation (2026-05-28)

Because the navigation stack is not yet integrated, the first memory-system
validation matrix uses a fixed replay protocol rather than a planner:

- The action policy is the deterministic `out_and_back` controller.
- Habitat RGB/depth observations still run through the same noise pipelines and
  real detector adapter.
- `memory=on` persists and accumulates belief through the replay using the
  existing `LifelongMemoryHarness`.
- `memory=off` is interpreted as a strict single-frame sanity baseline: each
  observation updates `INITIAL_BELIEF` and then discards that belief before the
  next row.
- `memory=naive_count` is the main non-memory accumulating baseline. It only
  counts positive detector evidence inside the current replay and trusts after
  a fixed positive-count threshold. It must not use non-confirmation, unknown,
  delayed birth, geometric consistency, or cross-episode persistence because
  those are algorithm contributions.
- A shared decision-side current-view gate is applied to all memory ablations
  before `TRUST` is allowed to become a stop/success decision. The gate must be
  independent of memory mode so the comparison stays fair.
- The main metric is `oracle_stop_success`: gated `TRUST` while the oracle
  target is visible in the current frame, plus false-trust rows where raw memory
  preference says `TRUST` but the shared gate rejects the current stop.
- This stage may support a memory-update / evidence-accumulation claim, but it
  must not be reported as official Habitat ObjectNav success or SPL.

The next ablation needed before a stronger lifelong-memory claim is this
`naive_count` baseline. It separates short-horizon positive-count accumulation
from Dual-Anchor / Lifelong behavior without borrowing the algorithm's
negative-evidence handling or birth logic.

## Update: Gate-Rejection Visual Diagnostics (2026-05-28)

The shared current-positive gate revealed many rejected raw `TRUST` rows for
`plant` and `tv_monitor`. These rows cannot be interpreted from scalar metrics
alone because two different failure modes look similar in the trace:

- Grounding-DINO may be drawing a plausible target prompt box on the wrong
  visible object or region.
- Habitat's semantic ground-truth mask may be very small, missing, clipped, or
  otherwise stricter than the visual object humans would judge as visible.

The RGB-noise replay runner therefore supports an optional debug export for
gate rejections. When enabled, each exported PNG contains:

- clean RGB with the Habitat target bounding box;
- noisy RGB with detector boxes;
- noisy RGB plus Habitat GT mask;
- noisy RGB plus detector box-mask;
- a combined overlay where GT is green, detector-only pixels are red, and
  overlap is yellow;
- per-frame metadata including category, memory mode, noise level, step,
  gate reason, oracle pixels, detector pixels, precision, recall, and detector
  confidence.

This export is diagnostic only. It must not change metrics, gate behavior,
memory updates, or detector outputs. The trace records a `debug_png` path only
for exported rows so reviewers can jump from aggregate false-trust counts to
the exact image evidence.

## Update: Trace-Filtered Visual Diagnostics (2026-05-28)

The visibility-challenge replay exposed a second diagnostic need: some frames
need to be exported because their trace fields match a research question, even
when they are not gate rejections. In particular, hidden-phase detector
positives should be inspectable directly so we can tell whether Grounding-DINO
is hallucinating objects or Habitat GT is too strict.

The replay runner therefore extends the PNG export with optional trace filters:

- `debug_export_replay_phases` filters by row `replay_phase`, for example
  `depart,non_confirm`;
- `debug_export_evidence_types` filters by row `evidence_type`, for example
  `positive`;
- `debug_export_categories` still scopes categories for both gate-rejection
  and trace-filtered exports;
- the existing `debug_export_gate_rejections` mode remains available and can be
  combined with the trace filters;
- per-category export caps, skipped counts, row-level `debug_png`, and summary
  artifact reporting use the same code path.

This remains instrumentation only. It must not change replay viewpoint
selection, detector inference, evidence classification, memory updates,
`naive_count`, or the shared decision-side gate.

## Update: Detector Area Sanity Filter (2026-05-28)

The debug PNG review showed that some Grounding-DINO `tv_monitor` boxes cover
most or all of the `1280x720` image while Habitat GT has zero target pixels.
Those boxes are not useful evidence for memory and should be rejected before
the detector mask enters the evidence classifier.

The replay runner therefore applies a shared detector-side maximum area filter
before the detector mask enters the evidence classifier:

- default `max_detection_area_ratio=0.70`;
- `None` / CLI value `<=0` disables the filter for ablations;
- the first pass rejects individual detector boxes above the threshold;
- the second pass rejects the whole detector mask when the union of remaining
  boxes still covers more than the same threshold;
- the rule uses only detector geometry and image size, never Habitat GT;
- the filter is applied before all memory modes, so `on`, `naive_count`, and
  `off` see the same filtered detector evidence;
- trace rows record `detection_filtered_count`, and summaries report the total
  filtered detection count.

This is still a v1 heuristic, not a substitute for instance segmentation. It is
intended to remove pathological open-vocabulary full-frame detections while
preserving the existing shared current-positive gate.

## Update: Structured Habitat Episode Selection (2026-05-28)

The synthetic structured decision challenge showed that positive-only
`naive_count` fails most clearly when a target is first confirmed and then
invalidated by scene change, negative evidence, path blockage, or association
ambiguity. The next Habitat stage therefore must stop selecting only the first
N episodes per category.

The RGB-noise harness now exposes `episode_selection_strategy`:

- `category_balanced`: the old behavior, selecting the first matching episodes
  per category.
- `structured_visibility`: a metadata-only filter that prefers episodes with
  multiple goal viewpoints, nontrivial geodesic distance, and a
  geodesic/euclidean path-complexity ratio above threshold.

This filter is intentionally conservative. It does not claim the episode
contains a true room/corridor memory challenge; it only avoids obviously flat
or single-view episodes before the expensive Grounding-DINO replay. The summary
records candidate counts, selected episode IDs, and dropped counts so the run
can be audited before interpreting memory results.

## Update: Replay Phase and Category Selection Audit (2026-05-28)

The first structured-visibility replay showed that metadata filtering alone is
not enough to prove the memory system is being challenged. It selected useful
episodes for `bed`, `toilet`, and `plant`, but `sofa` and `tv_monitor` were
silently excluded by the current path-complexity threshold. The replay trace
also made it hard to tell whether a row belonged to first confirmation,
departure, a non-confirmation interval, or revisit.

The RGB-noise harness therefore records two new audit surfaces:

- `summary.json["episode_selection"]["category_audit"]` reports, per requested
  category, raw category candidates, structured candidates, selected IDs,
  dropped-by-filter counts, and selection status.
- `summary.json["episode_selection"]["zero_structured_candidate_categories"]`
  explicitly names requested categories that have no structured candidates
  under the current thresholds.
- Each trace row records `replay_phase`, partitioning the deterministic
  out-and-back sequence into `confirm`, `depart`, `non_confirm`, and `revisit`.
- The run summary reports phase-level evidence, gated decision, and raw
  decision counts.

This is audit instrumentation only. It does not alter Habitat actions,
detector outputs, evidence classification, memory updates, `naive_count`, or
the shared current-positive gate. The next Linux replay should first inspect
whether `non_confirm` and `revisit` actually contain the evidence mix needed to
stress memory before treating aggregate memory-vs-baseline metrics as a claim.

## Update: Visibility-Challenge Replay Protocol (2026-05-28)

The phase-audit replay showed that index-based phase labels are insufficient:
the nominal `non_confirm` interval still contained many target-visible and
detector-positive rows. The harness therefore adds an explicit
`replay_protocol=visibility_challenge` mode.

This protocol:

- measures target pixels at each Habitat goal viewpoint and at a 180-degree
  turned-around view from that same position;
- selects the strongest target-visible view as `confirm` / `revisit`;
- selects the lowest-target-pixel hidden view as `depart` / `non_confirm`;
- emits three `confirm` frames so both memory `on` and positive-only
  `naive_count` can accumulate initial positive evidence before the hidden
  interval;
- emits two `depart`, four `non_confirm`, and four `revisit` frames;
- records `replay_protocol`, `replay_source`, and
  `replay_source_target_pixels` in the trace.

The default remains `out_and_back` for backward compatibility. The new
protocol changes only the replay viewpoint sequence. It does not change
detector inference, evidence classification, memory updates, `naive_count`, or
the shared current-positive gate. Because it teleports between measured
viewpoints rather than using a planner, its result is still a memory/evidence
stress test, not an official navigation metric.

## Update: Long-Range Geodesic Replay Bridge (2026-05-28)

The next validation step must move beyond goal-viewpoint teleport tests without
claiming a full learned ObjectNav policy. The runner therefore adds a
`replay_protocol=geodesic_path` bridge:

- start from the official ObjectNav episode start, or the configured
  `start_source`;
- query Habitat-Sim's navmesh shortest path from that start to the episode
  goal viewpoint;
- downsample the path to a bounded number of replay waypoints;
- teleport the agent through those waypoints while orienting it along the path;
- finish with repeated goal-viewpoint confirmation frames using the Habitat
  goal-viewpoint rotation;
- record `approach` and `confirm` replay phases plus the usual RGB/depth noise,
  detector, memory, gate, and trace fields.

This is a long-range replay, not closed-loop navigation. It is intended to
answer whether the perception/memory stack behaves plausibly over official
ObjectNav start-to-goal distances before we invest in an action-level follower.
It must not be reported as official Habitat success/SPL. The next step after a
successful geodesic replay is an action-level Habitat follower or policy that
executes navigational actions and reports path-efficiency metrics.

## Update: Current-Positive Opportunistic Trust (2026-05-28)

The first Grounding-DINO `geodesic_path` smoke showed that memory `on` can be
too conservative after repeated positive observations: it reduces raw false
trust compared with `naive_count`, but sometimes misses gated success rows
because the cost policy asks for one more `VERIFY` even while the current frame
already confirms the target.

The decision policy therefore gets a shared current-positive shortcut:

- the evidence classifier remains unchanged;
- the shared current-positive gate remains unchanged;
- `DecisionContext` records whether the current frame has positive evidence;
- if `p_valid` is already above a high threshold and the current frame is
  positive, the policy may choose `TRUST` immediately instead of another
  `VERIFY`;
- the rule is shared by `memory=on`, `memory=naive_count`, and `memory=off`.

This is not a baseline handicap. `naive_count` still only accumulates positive
counts and still ignores non-confirmation/unknown evidence. The shortcut only
removes unnecessary extra verification when the current frame itself is already
positive and the mode's own belief state is high enough.

## Update: Delayed Birth For Long-Range Replay (2026-05-28)

The first long-range `geodesic_path` replay exposed an implementation mismatch
with the intended memory semantics. When the agent starts from the official
ObjectNav episode start, many approach frames occur before the target has ever
been detected. Feeding these pre-birth `UNKNOWN`, `NON_CONFIRMATION`, or
`FREE` events into `memory=on` decays the default belief before a candidate
memory exists. The positive-only `naive_count` baseline does not suffer that
penalty, so the comparison unintentionally rewards the baseline for ignoring
all non-positive evidence.

The RGB-noise harness therefore treats candidate birth explicitly for
`memory=on`:

- a fresh category-scene belief loaded from the default state is considered
  not yet born;
- before birth, only `POSITIVE` evidence creates the candidate and updates the
  belief;
- pre-birth `UNKNOWN`, `NON_CONFIRMATION`, `FREE`, `OCCLUDED`,
  `ACCESS_BLOCKED`, and `SCENE_CHANGED` leave the default belief unchanged;
- once a candidate is born, all evidence types are applied normally, so stale,
  moved, blocked, or repeatedly unconfirmed memory can still decay and retire;
- beliefs loaded from SQLite that differ from the default are treated as
  already born, preserving lifelong persistence across episodes;
- `naive_count` remains unchanged: it only counts positive observations and
  does not receive delayed birth, non-confirmation handling, geometry, or
  persistence.

This is an algorithm-boundary fix, not a metric-only change. It aligns the
long-range replay with the original delayed-birth contribution while keeping
the shared current-positive gate and the shared current-positive trust shortcut
unchanged.

## Update: Long-Range Lifelong Timing Metrics (2026-05-28)

The delayed-birth rerun did not change the small Grounding-DINO
`geodesic_path` smoke because the first positive evidence appears early in
the selected episodes. The result shows that row-count success alone is too
coarse for lifelong memory evaluation: a cross-episode memory may be valuable
because it trusts sooner after a current confirmation, not only because it
creates more success rows.

The replay summary therefore records timing and distance metrics per replay:

- first positive step and phase;
- first raw trust step and phase;
- first gated trust step and phase;
- first oracle-stop-success step and phase;
- replay path translation accumulated up to first success;
- whether the replay ever produced an oracle-stop success.

The run summary also reports `memory_mode_metrics`, aggregating:

- replay episodes per memory mode;
- successful replay episodes per memory mode;
- success rows, raw trust rows, and gate-rejection rows;
- mean first-success step;
- mean path translation to first success;
- mean final `p_valid`.

These are reporting metrics only. They do not change detector inference,
evidence classification, memory updates, `naive_count`, the shared gate, or
stop-on-trust behavior. They are needed before scaling to a larger lifelong
matrix because top-tier evidence should show both reliability and efficiency
over long-distance episodes.

## Update: Expected-Empty Replay Challenge (2026-05-28)

The long-range `geodesic_path` smoke still mostly rewards repeated positive
detections. It does not reliably create the stale-memory condition where an
agent goes to a remembered/expected object location, observes that the target
is absent, and must reduce trust before later recovery or search.

The harness therefore adds `replay_protocol=expected_empty_challenge`:

- choose a measured target-visible Habitat goal view for initial confirmation;
- choose a measured target-hidden view as an explicit expected-empty
  verification interval;
- emit `confirm -> expected_empty -> revisit` phases;
- mark only the expected-empty interval with `expected_target_absent=True`;
- when `expected_target_absent=True`, the target is not oracle-visible, and
  the detector does not produce a positive target mask, convert the frame's
  evidence to `NON_CONFIRMATION` with reason `expected_location_empty`;
- preserve detector positives in the expected-empty interval as positives so
  false-positive pressure remains visible;
- record `expected_target_absent` in each trace row.

This is not a post-hoc success filter and it is not added to `naive_count`.
`naive_count` still only accumulates positive evidence and ignores
non-confirmation. The goal is to expose the algorithm's negative-evidence and
retirement behavior in Habitat before scaling to a larger noise/category
matrix.

## Update: Long-Range Expected-Empty Replay Challenge (2026-05-28)

The short `expected_empty_challenge` isolates stale-memory handling, while the
`geodesic_path` replay isolates official start-to-goal distance. Neither alone
is a strong proxy for long-range lifelong ObjectNav. The harness therefore adds
`replay_protocol=geodesic_expected_empty_challenge`:

- start from the configured episode start, normally the official ObjectNav
  episode start;
- replay bounded Habitat navmesh shortest-path waypoints as `approach`;
- repeat the measured goal viewpoint as `confirm` so both memory `on` and
  `naive_count` can accumulate initial positive evidence;
- jump to a measured target-hidden expected-empty viewpoint and mark only that
  interval with `expected_target_absent=True`;
- return to the goal viewpoint for `revisit`.

This protocol composes existing mechanisms instead of adding a new metric. It
does not change Grounding-DINO inference, detector filtering, evidence
classification outside the expected-empty interval, memory updates, the
positive-only `naive_count` baseline, or the shared decision gate. Its intended
claim boundary is still replay-style validation: it can support a stronger
memory/evidence claim over long official ObjectNav distances, but it is not
official Habitat SPL and not closed-loop navigation.

## Update: Memory Geometry Gate Prototype (2026-05-28)

The expected-empty Grounding-DINO matrix exposed a detector/memory boundary
issue for `bed`: the detector can produce positive target evidence in an
expected-empty view by labeling a spatially different object, such as a door
edge or dresser, as `bed`. A category-only belief table cannot distinguish
that false positive from a revisit to the same remembered object.

The RGB-noise runner therefore adds an optional `memory=on` geometry-gate
prototype:

- CLI flag: `--memory-geometry-gate-radius-m <meters>`;
- CLI flag: `--memory-geometry-gate-fov` / `--no-memory-geometry-gate-fov`;
- distance gate default: disabled, preserving previous distance-threshold
  experiment results unless explicitly enabled;
- FOV gate default: enabled for `memory=on` when the geometry prototype is
  used, because it does not depend on a brittle bbox-depth distance threshold;
- the first accepted positive observation in a replay creates a lightweight
  memory anchor by projecting the detector bbox center through the noisy depth
  image into Habitat world `x/z`;
- later `memory=on` positives whose projected anchor is farther than the
  configured radius are quarantined as `UNKNOWN` with reason
  `geometry_inconsistent_positive`;
- later `memory=on` positives are also quarantined when the remembered anchor
  is outside the current camera field of view, because a same-category
  detector hit in that view cannot be confirming the remembered object;
- trace rows record the memory anchor, observation anchor, geometry distance,
  and geometry gate reason;
- `naive_count` is unchanged: it still only counts positive observations and
  receives no geometry, non-confirmation, delayed birth, or persistence logic.

This is a candidate-association prototype, not the final Dual-Anchor memory
store. The anchor is currently per replay and is not persisted in SQLite across
episodes. It is intended to test whether spatial consistency helps reject
detector false positives before investing in a full object-instance memory
schema with anchor covariance and multi-object association.

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
- **Detector adapters** wrapping real open-vocabulary detectors that produce
  per-frame `(category, bbox, confidence, mask)` tuples:
  - **YOLO-World** via Ultralytics `YOLOWorld('yolov8s-worldv2.pt')` or
    equivalent.
  - **Grounding-DINO** via Hugging Face Transformers
    `AutoProcessor` / `AutoModelForZeroShotObjectDetection`, defaulting to
    `IDEA-Research/grounding-dino-tiny` unless overridden by
    `--detector-weights`.
  For the ObjectNav harness the default prompt policy is target-conditioned:
  the detector is prompted with the current episode goal category rather than
  the full 6-category set. This matches the ObjectNav interface, where the
  goal category is known, and avoids open-vocabulary class competition such as
  visible `toilet` regions being labeled `bed`. The legacy full category prompt
  set remains available as `--yolo-prompt-mode all_categories` for ablations.
  Masks are derived from boxes (axis-aligned) for v1; instance masks via a
  segmentation head are deferred to v2.
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
  --sensor-width 1280 \
  --sensor-height 720 \
  --stop-on-trust \
  --seed 313
```

Detector category qualification should run before the full noise-memory
matrix. It uses clean RGB, target-conditioned prompts, balanced category
sampling, and a real-camera-like render resolution:

```bash
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_usability/detector_category_qualification_1280x720 \
  --noise-levels clean \
  --detector yolo_world \
  --memory-ablation on \
  --episodes-per-category 1 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --yolo-prompt-mode target \
  --stop-on-trust \
  --seed 313
```

Grounding-DINO should use the same qualification protocol:

```bash
python -m objectnav_core.cli.run_habitat_objectnav_rgb_noise_stress \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_usability/grounding_dino_category_qualification_1280x720 \
  --noise-levels clean \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --memory-ablation on \
  --episodes-per-category 2 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --yolo-prompt-mode target \
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
- `perception/grounding_dino_adapter.py`
  - `class GroundingDinoDetector(model_id: str, categories: list[str], conf: float, text_threshold: float, device: str)`
  - `detect(rgb: np.uint8[H,W,3]) -> list[Detection]`
  - Uses the same `Detection` tuple shape as YOLO-World so the Habitat and
    memory harness does not care which detector produced the boxes.
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
| Edge-clipped target views look oracle-visible but are poor detector evidence | Trace `oracle_bbox`, `oracle_edge_sides`, `oracle_touches_side_edge`, and `oracle_edge_clearance_ratio` | Stop on valid `TRUST`; improve revisit sampling before treating later edge-clipped misses as detector failures |
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
- Detector qualification:
  - Clean RGB only, target-conditioned YOLO-World prompts.
  - Run at real-camera-like rectangular resolution, starting with
    `1280x720` because it matches the D435 depth stream maximum and is much
    closer to deployed RGB-D operation than the old square smoke renders.
  - Select balanced episodes with `--episodes-per-category` so early dataset
    ordering cannot hide unsupported categories.
  - Categories with repeated clean failures are detector limitations, not
    memory-algorithm failures, and should be fixed or explicitly scoped before
    the full noise-memory matrix.

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
