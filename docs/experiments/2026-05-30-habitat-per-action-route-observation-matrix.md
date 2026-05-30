# Experiment Report: Habitat Per-Action Route Observation Matrix

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Does per-action route observation address the current failure mode where learned
memory-validity rejection falls back to weak endpoint-only navmesh search?

## Hypothesis

Checking observations along the executed route should recover targets that are
visible before an option endpoint. In relocation, memory-guided search may gain
over frontier-only when a stale memory is still a useful spatial prior for
post-memory local frontier recovery. The learned validity model should be
reported separately: if route observation changes the action model enough, the
learned probability may become neutral rather than producing a decision gain.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `3ac6ab7` |
| Machine | `badger-linux` |
| Dataset / scene | HM3D ObjectNav `val` |
| Simulator / detector | Habitat-Sim, Grounding-DINO tiny |
| Route observation | `option_end` reference vs `per_action` |
| Frontier | `navmesh_frontier` |
| Detector confirmation | `multiview` |
| Noise | clean RGB/depth profiles |
| Learned model | `runs/habitat_closed_loop_dual_anchor/memory_validity_learning_grounding_dino_current_stable_relocation_balanced6_evidence_only_20260530_v1/model.json` |

## Commands

The stable per-action baseline used:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/event_posterior_stable_balanced6_per_action_current_20260530_v2 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 6 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --challenge stable \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode event_posterior \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 5 \
  --frontier-probe-heading-count 4 \
  --route-observation-mode per_action \
  --detector-confirmation-mode multiview \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --grounding-dino-max-image-side 384 \
  --rgb-noise-profile configs/noise/rgb_published_v1.yaml \
  --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml \
  --noise-level clean \
  --min-target-pixels 24 \
  --min-detector-pixels 20 \
  --max-detection-area-ratio 0.7 \
  --detector-prompt-mode target
```

Relocation per-action used the same command with:

```bash
--output runs/habitat_closed_loop_dual_anchor/event_posterior_goal_object_relocation_balanced6_per_action_current_20260530_v1
--sensor-width 640
--sensor-height 360
--challenge goal_object_relocation
--frontier-probe-count 3
--frontier-probe-heading-count 2
```

The learned per-action replays used the same commands with
`--memory-validity-model` set to the model listed above and output directories:

- `runs/habitat_closed_loop_dual_anchor/learned_validity_stable_balanced6_evidence_only_per_action_20260530_v1`
- `runs/habitat_closed_loop_dual_anchor/learned_validity_goal_object_relocation_balanced6_evidence_only_per_action_20260530_v1`

Reference `option_end` artifacts are from the matched current-code matrix in
`docs/experiments/2026-05-30-habitat-learned-memory-validity-online-replay.md`.

## Metrics

| Slice | Route observation | Validity | Memory-guided success | Memory-guided actions | Frontier-only success | Frontier-only actions | Naive success | Naive actions |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Stable balanced6 | `option_end` | event posterior | `4/6` | `528` | `0/6` | `2089` | `5/6` | `573` |
| Stable balanced6 | `option_end` | learned | `4/6` | `795` | `0/6` | `2089` | `5/6` | `573` |
| Stable balanced6 | `per_action` | event posterior | `5/6` | `441` | `3/6` | `831` | `6/6` | `473` |
| Stable balanced6 | `per_action` | learned | `5/6` | `441` | `3/6` | `831` | `6/6` | `473` |
| Relocation balanced6 | `option_end` | event posterior | `0/6` | `1446` | `0/6` | `2039` | `0/6` | `910` |
| Relocation balanced6 | `option_end` | learned | `0/6` | `1643` | `0/6` | `2039` | `0/6` | `910` |
| Relocation balanced6 | `per_action` | event posterior | `3/6` | `1176` | `2/6` | `1647` | `3/6` | `1254` |
| Relocation balanced6 | `per_action` | learned | `3/6` | `1176` | `2/6` | `1647` | `3/6` | `1254` |

The matched event-posterior and learned per-action rows had zero decision,
success, or action-count differences in both stable and relocation slices.

## Selected Sofa Check

The selected relocated `sofa` row that originally motivated this follow-up
changed as follows:

| Run | Route observation | Validity | Decision | Success | Actions | Key evidence |
|---|---|---|---|---:|---:|---|
| Baseline selected | `option_end` | event posterior | `memory_first` | `0/1` | `49` | memory endpoint false |
| Learned selected | `option_end` | learned | `frontier_first` | `0/1` | `246` | query-start frontier endpoint pending/suppressed |
| Baseline selected | `per_action` | event posterior | `memory_first` | `1/1` | `171` | post-memory frontier confirmed at `navmesh_frontier_probe:2:step:0` |
| Learned selected | `per_action` | learned | `memory_first` | `1/1` | `171` | same post-memory frontier confirmation |

The learned model still lowered the probability from the event-posterior
baseline (`0.2875`) to `0.006685`, but the per-action post-memory frontier route
was short enough that expected utility still selected `memory_first`.

## Observations

- Per-action route observation is the first current-code change that turns the
  relocation balanced6 slice from all failures into partial recovery:
  memory-guided `0/6 -> 3/6`, frontier-only `0/6 -> 2/6`.
- Memory-guided has one relocation success beyond frontier-only: the relocated
  `sofa` row succeeds only when the stale memory is used as a spatial prior
  before local post-memory frontier search.
- Learned validity is neutral once per-action route observation is enabled on
  this matrix. It changes probabilities, but not decisions or outcomes.
- Stable also improves under per-action route observation:
  memory-guided `4/6 -> 5/6`, and actions drop from `528` to `441`.
- The stable `bed` row remains a diagnostic failure: memory evidence is
  positive, but expected utility selects a zero-action frontier option that
  fails. This is an evaluation/policy limitation to investigate before any
  paper claim.
- These results are not official ObjectNav SPL. The runner still uses
  deterministic navmesh probes, counterfactual route accounting, and
  simulator-side target overlap for audit.

## Result

The experiment changes the near-term research direction. The bottleneck is not
only memory-validity classification. Route-level active confirmation makes
stale-memory rejection useful by exposing target evidence along the actual path,
and memory remains valuable as a local search prior after stale verification
fails. The learned validity model is a working decision mechanism, but this
matched per-action matrix does not show an additional learned-policy gain.

## Follow-up

- Fix or redesign the expected-utility handling for zero-action failed frontier
  options, using the stable `bed` row as the first regression target.
- Promote route-level active confirmation into the next algorithmic design:
  memory should be a spatial prior for local search, not only a terminal goal.
- Scale beyond balanced6 with confidence intervals and scene/category holdouts.
- Replace deterministic navmesh probes with an occupancy/depth frontier policy
  before claiming benchmark-level ObjectNav performance.

## Targeted Bed Follow-Up

After this matrix, the zero-action failed-frontier diagnostic was fixed in
commit `033c8b8`. The decision helper now treats a failed zero-action frontier
as unavailable rather than as a free option.

Targeted selected-group verification on Linux:

| Run | Artifact | Decision | Success | Actions |
|---|---|---|---:|---:|
| Event posterior | `runs/habitat_closed_loop_dual_anchor/event_posterior_bed_stable_per_action_selected_unavailable_frontier_fix_20260530_v1` | `memory_first` | `1/1` | `32` |
| Learned | `runs/habitat_closed_loop_dual_anchor/learned_validity_bed_stable_per_action_selected_unavailable_frontier_fix_20260530_v1` | `memory_first` | `1/1` | `32` |

The balanced6 matrix table above is still the pre-fix matrix and should not be
silently edited. Rerun the stable and relocation per-action balanced6 matrix on
`033c8b8` or later before reporting updated aggregate numbers.
