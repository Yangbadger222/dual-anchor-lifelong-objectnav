# Handoff: Closed-Loop Dual-Anchor Habitat ObjectNav

Date: 2026-05-30
Owner: Codex
Status: In Progress

## Latest Confirmed Detector-Approach Memory Write

Status: implemented; diagnostic smoke negative.

The user pointed out the core behavioral issue: during exploration, the robot
should approach a detected target before writing memory. Added
`anchor_commit_policy=confirmed_detector_approach` to official memory
discovery. This policy is valid with `anchor_mode=robot_viewpoint`; it uses the
existing detector-guided local controller after target-category detections and
writes memory only when that controller would range-confirm the target. If the
approach budget expires or the controller cannot produce a valid approach
action before confirmation, the weak glimpse is counted as unconfirmed and no
anchor is written.

Remote strict confirmed artifact:

`runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_confirmed_detector_approach_prior_4ep_100steps_20260531_v1`

Result:

- Grounding-DINO discovery saw `633` detections and `433` label-filtered
  detections.
- The policy executed `46` detector-approach deferred actions and recorded `60`
  unconfirmed target attempts.
- It produced `0` range-confirmed anchors.

Remote non-strict long-budget comparison:

`runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_detector_approach8_prior_4ep_100steps_20260531_v1`

Result:

- Same detector run shape: `633` detections, `433` label-filtered detections,
  and `46` detector-approach deferred actions.
- Exported `2` anchors, but both stayed near the episode origin:
  - toilet episode `6`: `(x=0.0, z=-0.0)`;
  - tv episode `0`: `(x=0.033494, z=-0.125)`.
- Anchor quality vs detector-positive viewpoint prior:
  selected mean error `6.262038 m`, nearest mean error `6.262038 m`, good
  anchors `0`, coverage `2/4`.
- Anchor quality vs oracle object prior:
  selected mean error `5.752019 m`, nearest mean error `5.752019 m`, good
  anchors `0`, coverage `2/4`.
- Query with `memory_active_perception_frontier_targetnav` and
  `targetnav_backend=oracle_follower` stayed at SR `0/4`, SPL `0.0`, SoftSPL
  `0.003394134213343364`, mean distance-to-goal `5.8624347448349`.

Verification:

- Local focused tests:
  `src/objectnav_core/tests/test_habitat_official_memory_discovery.py`,
  `src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py`,
  and `src/objectnav_core/tests/test_ros_packaging.py`: `20 passed`.
- Remote focused tests in conda env `habitat`: `20 passed`.
- Local and remote `compileall` for touched discovery module/CLI/tests were
  clean.
- Local `git diff --check` and touched-file whitespace scan were clean.

Interpretation:

- The robot is no longer just passively writing first-glimpse memory in this
  policy. It tried target-reactive approach, but the current local detector
  servo did not produce confirmed useful viewpoints in the DINO smoke.
- The strict policy correctly avoids writing bad memories; the non-strict
  budget-8 policy shows why this matters by exporting near-origin anchors that
  still fail fixed-backend query.
- This is likely more natural on the real robot because SLAM/Nav2 and
  continuous control can help local target approach, but the paper system
  should not rely on a permanently stable global map. SLAM should be a local
  execution substrate; the memory should be confirmed visual/geometric evidence
  robust to long-term drift.

Next recommended action:

1. Add an approach-attempt trace artifact so unconfirmed target reactions expose
   per-step pose, bbox, depth, chosen detector action, and lost-target events.
2. Build a stronger target-tracking memory-write option that keeps visual lock,
   scans/reacquires when the detector is lost, and commits only after view
   quality improves.
3. Keep the targetnav-equated comparison fixed while improving only memory
   write quality.

## Latest Official View-Quality Memory Selection

Status: implemented; diagnostic smoke negative.

Added `anchor_selection_policy=confidence|view_quality` to official memory
discovery. The default `confidence` path preserves existing behavior.
`view_quality` ranks accepted detector candidates by larger bbox area, smaller
absolute center offset, and detector confidence. Discovery CSV rows now include
the selected candidate's bbox area, center offset, depth evidence, and selection
policy.

Remote artifact:

`runs/habitat_official_objectnav/grounding_dino_robot_viewpoint_view_quality_prior_4ep_100steps_20260531_v1/memory_prior.json`

Result:

- Grounding-DINO discovery saw `666` detections, `620` label-filtered
  detections, and exported `3` one-per-episode `robot_viewpoint` anchors.
- Anchor quality vs detector-positive viewpoint prior:
  selected mean error `6.891912 m`, nearest mean error `6.891912 m`, good
  anchors `0/4`, one missing reference.
- Anchor quality vs oracle object prior:
  selected mean error `5.543938 m`, nearest mean error `5.543938 m`, good
  anchors `0/4`, one missing reference.
- Query with `memory_active_perception_frontier_targetnav` and
  `targetnav_backend=oracle_follower` stayed at SR `0/4`, SPL `0.0`, SoftSPL
  `0.0`, mean distance-to-goal `6.0735965967178345`.

Verification:

- Local focused tests:
  `src/objectnav_core/tests/test_habitat_official_memory_discovery.py`,
  `src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py`,
  and `src/objectnav_core/tests/test_ros_packaging.py`: `17 passed`.
- Remote focused tests in conda env `habitat`: `17 passed`.
- Local and remote `compileall` for the touched discovery module and CLI were
  clean.

Interpretation:

- View-quality ranking is not enough. Two selected anchors are still at the
  episode origin with tiny target boxes, and one episode has no selected memory
  anchor.
- The bottleneck is active memory writing: the robot needs to execute a local
  approach/scan option before committing memory, or learn an online write-value
  model from actual option rollouts.

## Latest Official TargetNav-Equated Memory Comparison

Status: diagnostic complete.

Implemented and verified a cleaner official comparison scaffold that holds the
terminal TargetNav backend fixed and varies only the memory condition:

- `memory_guided` -> `memory_active_perception_frontier_targetnav`
- `no_memory` -> `no_memory_targetnav`
- `naive_count` -> `naive_count_targetnav`
- shared backend: `targetnav_backend=oracle_follower`

Remote comparison artifact:

`runs/habitat_official_objectnav/targetnav_equated_grounding_dino_memory_comparison_4ep_100steps_20260531_v1/comparison.json`

Result:

| Method | Policy | SR | SPL | SoftSPL | DistanceToGoal | Caveat |
|---|---|---:|---:|---:|---:|---|
| `memory_guided` | `memory_active_perception_frontier_targetnav` | 0.0000 | 0.0000 | 0.1914 | 5.9202 | `targetnav_oracle_backend_diagnostic` |
| `no_memory` | `no_memory_targetnav` | 0.5000 | 0.4673 | 0.4615 | 2.8931 | `targetnav_oracle_backend_diagnostic` |
| `naive_count` | `naive_count_targetnav` | 0.0000 | 0.0000 | 0.1914 | 5.9202 | `targetnav_oracle_backend_diagnostic` |

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_memory_comparison.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_memory_comparison \
    --output runs/habitat_official_objectnav/targetnav_equated_grounding_dino_memory_comparison_4ep_100steps_20260531_v1 \
    --memory-guided-prior-path runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_episode_ids_4ep_100steps_20260531_v1/memory_prior.json \
    --naive-count-prior-path runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_episode_ids_threshold2_4ep_100steps_20260531_v1/memory_prior.json \
    --targetnav-backend oracle_follower \
    --pathfinder-suffix-goal-radius-m 0.05 \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313
```

Verification:

- Local focused tests: `118 passed`.
- Remote focused tests in conda env `habitat`: `118 passed`.
- Local and remote `compileall` checks over the touched evaluator,
  comparison, and CLI modules were clean.
- The remote `comparison.json` and generated `comparison.md` both report
  `metric_source=habitat.Env.get_metrics`.

Interpretation:

- This is a negative memory-quality result, not a terminal-navigation result.
  Since all rows share `oracle_follower`, the gap points to current DINO memory
  target selection/write policy.
- The no-memory detector-triggered row solves `2/4`; both memory rows solve
  `0/4`.
- The next work should keep this scaffold and improve confirmed viewpoint
  memory writes before spending more effort on controller tuning.

## Latest Official Memory Upper-Bound State

Implemented a diagnostic oracle-memory prior exporter for official Habitat
ObjectNav:

- Design:
  `docs/design/2026-05-31-official-oracle-memory-prior-upper-bound.md`
- Experiment report:
  `docs/experiments/2026-05-31-official-oracle-memory-prior-upper-bound-smoke.md`
- Export module:
  `src/objectnav_core/objectnav_core/evaluation/habitat_official_oracle_memory_prior.py`
- CLI:
  `python -m objectnav_core.cli.export_habitat_official_oracle_memory_prior`
  or installed entry point
  `objectnav_habitat_official_oracle_memory_prior`

Current behavior:

- Official memory anchors now support optional `episode_id`.
- Memory selection prefers exact episode-specific anchors, then generic anchors.
- Oracle-memory JSON is tagged with
  `metadata.source=habitat_official_oracle_memory_prior` and
  `source_validity=oracle_diagnostic_only`.
- The protocol manifest reports oracle memory priors as diagnostic only. With a
  non-oracle backend the invalidity reason is
  `oracle_memory_prior_diagnostic`; with `oracle_follower`, the backend reason
  remains `targetnav_oracle_backend_diagnostic`.

Commands already run locally:

```bash
PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_select_official_memory_anchor_prefers_exact_episode_anchor \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_protocol_manifest_marks_oracle_memory_prior_diagnostic \
  src/objectnav_core/tests/test_official_episode_memory.py::test_official_memory_prior_payload_round_trips_episode_id \
  src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py -q

PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/evaluation/official_episode_memory.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_oracle_memory_prior.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_oracle_memory_prior.py \
  src/objectnav_core/setup.py

git diff --check
```

Local verification:

- Focused oracle-memory tests: `7 passed`.
- Evaluator/memory/CLI/packaging slice: `119 passed`.
- Full objectnav_core tests: `523 passed`.
- Compile and whitespace checks: clean.

Remote Linux Habitat verification:

```bash
rsync -avR \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/evaluation/official_episode_memory.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_oracle_memory_prior.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_oracle_memory_prior.py \
  src/objectnav_core/setup.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_oracle_memory_prior.py \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/
```

- Remote focused tests: `7 passed`.
- Remote evaluator/memory/CLI/packaging slice: `119 passed`.
- Remote compileall: clean.
- Oracle memory export:
  `runs/habitat_official_objectnav/oracle_memory_prior_valmini_4ep_20260531_v1/memory_prior.json`
  with `4` anchors and `0` skipped episodes.
- Oracle memory + oracle backend, radius `1.0`:
  `runs/habitat_official_objectnav/oracle_memory_oracle_backend_4ep_100steps_20260531_v1`,
  SR `0/4`, SPL `0.0`, SoftSPL `0.6810`, mean distance `2.2272`.
- Oracle memory + oracle backend, radius `0.2`:
  `runs/habitat_official_objectnav/oracle_memory_oracle_backend_radius02_4ep_150steps_20260531_v1`,
  SR `2/4`, SPL `0.4503`, SoftSPL `0.7533`, mean distance `1.5385`.
- Oracle memory + FMM backend:
  `runs/habitat_official_objectnav/oracle_memory_fmm_backend_4ep_150steps_20260531_v1`,
  SR `0/4`, SPL `0.0`, SoftSPL `0.0010`, mean distance `5.8806`.

Interpretation:

- The oracle-memory/export/episode-relative transform path is usable.
- A tight oracle follower radius matters for official success; radius `1.0`
  stopped too early.
- FMM remains a local execution bottleneck even with perfect memory.
- Do not present any oracle-memory run as benchmark-valid.

Next recommended action:

1. Improve the oracle upper bound by exporting multiple goal viewpoints per
   episode or choosing viewpoints more aligned with the official visibility and
   success condition.
2. Use oracle memory + oracle backend as the diagnostic ceiling.
3. Compare discovered memory + oracle backend against that ceiling to quantify
   memory-quality gap before investing more in FMM.

## Current State

The project has been redirected away from treating the teleport/search-proxy
lifecycle protocol as the main result. That protocol remains useful as a
diagnostic layer, but it is not strong enough for a top-tier ObjectNav claim.

The new direction is documented in
`docs/design/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`.

Implemented foundation:

- Habitat-independent dual-anchor geometry:
  `src/objectnav_core/objectnav_core/geometry/dual_anchor.py`
- Covariance propagation through 2D frame transforms.
- Mahalanobis instance matching with explicit ambiguity rejection.
- Memory-guided planner hook:
  ambiguous/rejected dual-anchor evidence lowers memory utility so frontier can
  win the decision.
- Deterministic pressure runner:
  `src/objectnav_core/objectnav_core/evaluation/dual_anchor_pressure.py`
- CLI artifact entry point:
  `python -m objectnav_core.cli.run_dual_anchor_pressure --output <dir>`
- Closed-loop grid harness:
  `python -m objectnav_core.cli.run_closed_loop_dual_anchor_benchmark --output <dir>`
  executes option-level memory-vs-frontier decisions across two sessions, with
  non-identity frame restart, ambiguity rejection, and stale repair.
- Habitat closed-loop smoke entry:
  `python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --output <dir>`
  has preflight plus oracle and Grounding-DINO candidate-gate HM3D smoke paths.
  It reuses existing Habitat episode/group selection and GreedyGeodesic route
  execution. It now supports `--challenge stable|ambiguous|stale_proxy` and
  `--detector oracle_semantic_visibility|grounding_dino`.
- The Habitat smoke now supports
  `--frontier-mode search_proxy|navmesh_frontier`. `search_proxy` is still the
  default. `navmesh_frontier` samples target-agnostic pathfinder probes,
  follows and verifies them one at a time, and stops at the first positive
  shared gate. It also supports a fixed local heading sweep at each probe via
  `--frontier-probe-heading-count`; extra scanned headings are counted as
  zero-translation scan actions.
- Repaired-memory direct route accounting for repeated stale queries.
- Expected-utility memory-vs-frontier decisions using `--memory-valid-prior`.
  `memory_guided` can defer from an accepted memory to frontier when expected
  action cost prefers frontier-first; `naive_count` remains the always-reuse
  accepted-memory baseline.
- Evidence-derived memory reliability mode via
  `--memory-reliability-mode evidence`; default remains `fixed`. Evidence mode
  records a row-level reliability trace and uses it as the expected-utility
  memory-valid probability.
- Adaptive detector event reliability via
  `--memory-reliability-mode event_posterior`. This mode blends the existing
  evidence reliability estimate with a context-filtered posterior over
  confirmed and suppressed detector confirmation events. It is oracle-free and
  intended as an interpretable calibration baseline, not the final learned
  model.
- Offline Habitat decision-sensitivity mining via
  `python -m objectnav_core.cli.mine_habitat_decision_sensitivity`. The miner
  reads existing closed-loop `summary.json` artifacts, recomputes fixed,
  evidence, and event-posterior expected-utility counterfactuals from saved row
  components, and ranks rows by close costs, detector-event mixture,
  reliability delta, decision flips, and hindsight regret.
- Detector-backed reliability uses detector pixels for current evidence instead
  of borrowing oracle semantic pixel counts. Oracle pixels remain in row payloads
  for audit/gate diagnostics, but must not inflate Grounding-DINO-backed policy
  reliability.
- Route observation mode via `--route-observation-mode option_end|per_action`.
  `option_end` preserves previous candidate/probe endpoint checks. `per_action`
  records GreedyGeodesic poses after each action, verifies them in execution
  order, and truncates memory/fallback/navmesh-probe route cost at the first
  positive shared gate. Initial stale-proxy memory attempts are explicitly kept
  non-confirming and untruncated.
- Summary rows now include `memory_route_observation`,
  `fallback_route_observation`, and
  `fallback_from_memory_route_observation` payloads so per-action route evidence
  can be audited without parsing anchor strings.
- Detector evidence payloads now include audit-only
  `detector_overlap_success` and `detector_false_confirmation` flags, and
  policy summaries count false confirmations across memory, fallback, and
  post-memory fallback evidence.
- Detector confirmation mode via
  `--detector-confirmation-mode single_frame|multiview`. `single_frame` keeps
  previous behavior. `multiview` suppresses raw single-frame detector positives
  to weak `UNKNOWN` evidence until repeated positives show sufficient view
  change and mask consistency. Row evidence payloads include confirmation
  diagnostics, rows include runtime `detector_confirmation_events`, and policy
  summaries include selected-evidence `detector_confirmation_counts` plus
  runtime event counts by outcome and context.
- Row-level `memory_decision_bucket` and per-policy bucket counts for separating
  memory wins, frontier wins, harmful memory avoided, valid memory wrongly
  deferred, naive reuse, and frontier-only rows.
- Row-level hindsight best candidate and regret diagnostics for calibrating
  reliability by error magnitude, not just bucket count.
- Strong-positive evidence reliability calibration for accepted, highly
  visible, low-covariance memory candidates. This is designed to remove the
  balanced6 `sofa` `valid_memory_wrongly_deferred` row without breaking the
  `plant` shorter-frontier decision.
- Category-balanced group selection before duplicate categories when
  `--max-groups` is set.
- Explicit `selected_group_ids` replay slicing for the Habitat closed-loop
  runner and CLI. Explicit slices bypass balanced sampling, preserve requested
  order, and are recorded in `episode_selection`.
- Goal-object relocation challenge:
  `--challenge goal_object_relocation` pairs same-scene, same-category
  `goal_object:<id>` lifecycle groups so discovery memory comes from an old
  instance and query/fallback verification targets a different instance. Rows
  now record `memory_instance_id`, `target_instance_id`, and
  `relocation_pair_distance_m` for auditability. Automatic relocation pair
  selection ranks by old-memory to new-query pose separation before balanced
  category selection.
- A Markdown and Chinese HTML experiment report for the latest Habitat
  oracle/action smoke.
- A Markdown experiment report for the Grounding-DINO candidate-gate smoke:
  `docs/experiments/2026-05-29-habitat-closed-loop-grounding-dino-candidate-gate.md`.

Not implemented yet:

- True closed-loop per-step replanning. The current `per_action` mode observes
  poses along a precomputed option route and can stop/charge early, but it does
  not yet choose a new action after every observation.
- True Habitat frontier mapping/exploration policy.
- Physical object relocation/removal in Habitat. The new relocation challenge
  is an instance-pair proxy built from existing HM3D episodes, not a mesh edit.
- SPL-like action-level ObjectNav metrics for memory-vs-frontier decisions.
- Broader Linux Habitat relocation sweep and decision-sensitivity mining beyond
  the initial two-group smoke.

## Latest Relocation State

Local implementation is in place for the relocation proxy. The focused local
checks passed:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --output /tmp/habitat_goal_object_relocation_preflight --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --target-categories chair,sofa --max-groups 2 --challenge goal_object_relocation --preflight-only
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/objectnav_core/evaluation/habitat_memory_lifecycle_objectnav.py src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
git diff --check

if rg -n "[ \t]+$" docs/design/2026-05-30-official-candidate-rollout-labeling.md \
  docs/experiments/2026-05-30-official-candidate-rollout-labeling.md \
  docs/devlog/2026-05.md \
  docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_action_utility_model.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_action_utility_model.py; \
then exit 1; else exit 0; fi

rsync -av --relative \
  docs/design/2026-05-30-official-candidate-rollout-labeling.md \
  docs/experiments/2026-05-30-official-candidate-rollout-labeling.md \
  docs/devlog/2026-05.md \
  docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_action_utility_model.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_action_utility_model.py \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh -o BatchMode=yes -o ConnectTimeout=5 badger@100.88.131.52 \
  'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
  export PYTHONPATH=src/objectnav_core && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_action_utility_model.py \
    src/objectnav_core/tests/test_ros_packaging.py -q'

ssh -o BatchMode=yes -o ConnectTimeout=5 badger@100.88.131.52 \
  'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
  export PYTHONPATH=src/objectnav_core && \
  python -m compileall \
    src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_action_utility_model.py \
    src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/objectnav_core/cli/report_habitat_official_candidate_rollout_action_matrix.py \
    src/objectnav_core/objectnav_core/cli/train_habitat_official_candidate_rollout_action_utility_model.py'
```

Initial Linux oracle and Grounding-DINO relocation smokes completed before the
spatial-separation selector and are summarized in
`docs/experiments/2026-05-30-habitat-goal-object-relocation-smoke.md`.
They selected `bed goal_object:194->goal_object:698` and
`chair goal_object:13->goal_object:483`, showed stale-memory reuse avoided by
`memory_guided`, and mined reliability-sensitive rows with `0` counterfactual
flips. Do not claim detector-event reliability improvement until a broader
relocation sweep produces a true mined flip. Next sweep should use the
separation-ranked selector and inspect `relocation_pair_distance_m` in rows and
mined candidates.

The separation-ranked Linux sweeps are now complete:

- Oracle ranked balanced6:
  `runs/habitat_closed_loop_dual_anchor/oracle_goal_object_relocation_ranked_navmesh_balanced6_20260530_v1`
- Grounding-DINO ranked balanced6:
  `runs/habitat_closed_loop_dual_anchor/grounding_dino_goal_object_relocation_ranked_navmesh_event_posterior_balanced6_20260530_v1`
- Best mined row so far: `toilet goal_object:260->goal_object:714`, with
  oracle boundary gap `0.022283` and Grounding-DINO boundary gap `0.048397`.
- Still `0` counterfactual flips. Detector events occurred in fallback
  contexts, while memory-validity event counts remained `0`.

Next recommended action: design a pre-decision memory-validity evidence step
or learned validity model for near-boundary relocation rows, rather than
continuing blind category sweeps.

The first step toward learned validity calibration is now a local exporter:

- Design: `docs/design/2026-05-30-memory-validity-learning-dataset.md`
- API: `objectnav_core.evaluation.habitat_memory_validity_dataset`
- CLI:
  `python -m objectnav_core.cli.export_habitat_memory_validity_dataset <inputs...> --output <report.json> --csv-output <examples.csv>`

The exporter labels rows from `memory_evidence.shared_gate_success` and keeps
features pre-decision only: planned route costs, memory evidence,
memory-reliability components, memory-context detector-event components, and
relocation distance. It intentionally excludes fallback evidence and final row
success from features.

The first learned validity baseline is now local/offline:

- Design: `docs/design/2026-05-30-memory-validity-logistic-baseline.md`
- Plan:
  `docs/superpowers/plans/2026-05-30-memory-validity-logistic-baseline.md`
- API: `objectnav_core.evaluation.habitat_memory_validity_model`
- CLI:
  `python -m objectnav_core.cli.train_habitat_memory_validity_model <dataset.json> --output <model.json>`

The model is deterministic logistic regression over the exporter feature schema.
It stores feature names, imputation means, scales, weights, bias, training
hyperparameters, and train-set metrics in JSON. It is not yet connected to the
online Habitat runner. Next research step remains real-artifact export/training
on Linux and checking whether learned validity crosses ranked relocation
decision boundaries such as `toilet goal_object:260->goal_object:714`.
Local verification after adding the baseline: focused model/exporter tests
produced `5` passed, `py_compile` passed for the trainer and CLI, the full
local core suite produced `270` passed, and `git diff --check` was clean.

The learned-decision scorer is also local/offline:

- Design:
  `docs/design/2026-05-30-memory-validity-learned-decision-scorer.md`
- Plan:
  `docs/superpowers/plans/2026-05-30-memory-validity-learned-decision-scorer.md`
- API:
  `score_memory_validity_decisions(dataset, model)` and
  `write_memory_validity_decision_scores_csv(path, rows)`
- CLI:
  `python -m objectnav_core.cli.score_habitat_memory_validity_model <dataset.json> --model <model.json> --output <scores.json> --csv-output <scores.csv>`

This scorer applies model probabilities to the same expected-utility arithmetic
used by the decision-sensitivity miner. It reports learned validity, expected
memory-first cost, frontier-first cost, boundary reliability, boundary region,
and flips against saved auxiliary decisions. It still does not prove a Habitat
result until run on real ranked relocation artifacts. Local verification after
adding the scorer: focused model/exporter tests produced `8` passed,
`py_compile` passed for trainer and scorer modules, the full local core suite
produced `273` passed, and `git diff --check` was clean.

Held-out evaluation support is now local/offline:

- Design: `docs/design/2026-05-30-memory-validity-heldout-evaluation.md`
- Plan:
  `docs/superpowers/plans/2026-05-30-memory-validity-heldout-evaluation.md`
- API:
  `split_memory_validity_dataset(dataset, holdout_field=..., holdout_values=...)`
  and `evaluate_memory_validity_model(dataset, model)`
- CLI extension:
  `python -m objectnav_core.cli.train_habitat_memory_validity_model <dataset.json> --output <model.json> --holdout-field category --holdout-values toilet`

When holdout flags are used, the trainer fits only on non-holdout examples and
writes `split`, `evaluation.train`, and `evaluation.holdout` sections. This is
still offline evidence plumbing; it needs real ranked relocation exports before
supporting any paper claim. Local verification after adding holdout evaluation:
focused model/exporter tests produced `11` passed, `py_compile` passed for the
trainer/model modules, the full local core suite produced `276` passed, and
`git diff --check` was clean.

The end-to-end offline learning pipeline is now local:

- Design: `docs/design/2026-05-30-memory-validity-learning-pipeline.md`
- Plan:
  `docs/superpowers/plans/2026-05-30-memory-validity-learning-pipeline.md`
- API:
  `run_memory_validity_learning_pipeline(inputs, output_dir=..., ...)`
- CLI:
  `python -m objectnav_core.cli.run_habitat_memory_validity_learning_pipeline <inputs...> --output-dir <dir>`

The pipeline writes `dataset.json`, `examples.csv`, `model.json`,
`scores.json`, `scores.csv`, `decision_sensitivity.json`,
`decision_sensitivity.csv`, and `pipeline_report.json`. It mines
fixed/evidence/event-posterior decision sensitivity by default; use
`--skip-decision-sensitivity` only for fast learned-only smoke runs. Suggested
first Linux run once SSH is reachable:

```bash
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_memory_validity_learning_pipeline \
  runs/habitat_closed_loop_dual_anchor/grounding_dino_goal_object_relocation_ranked_navmesh_event_posterior_balanced6_20260530_v1 \
  --output-dir runs/habitat_closed_loop_dual_anchor/memory_validity_learning_grounding_dino_ranked_relocation_balanced6_20260530_v1 \
  --features memory_evidence_detector_precision,memory_action_count,fallback_action_count,fallback_from_memory_action_count,relocation_pair_distance_m,memory_reliability_current_evidence,memory_reliability_matching,memory_reliability_transform_covariance,memory_reliability_recency,memory_detector_event_count,memory_detector_event_confirmed_weight,memory_detector_event_suppressed_weight,memory_detector_event_posterior \
  --holdout-field category \
  --holdout-values toilet
```

Local verification after adding the pipeline: focused pipeline/model/exporter
tests produced `13` passed, `py_compile` passed for the pipeline API and CLI,
the full local core suite produced `278` passed, and `git diff --check` was
clean.
After adding baseline mining to the pipeline, focused pipeline/model/exporter
and decision-sensitivity tests produced `21` passed, `py_compile` passed for
the pipeline API and CLI, the full local core suite produced `279` passed, and
`git diff --check` was clean.

Online learned validity replay is now implemented:

- Design:
  `docs/design/2026-05-30-habitat-learned-memory-validity-online.md`
- Experiment:
  `docs/experiments/2026-05-30-habitat-learned-memory-validity-online-replay.md`
- CLI hook:
  `python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav ... --memory-validity-model <model.json>`

Linux pulled commit `6162b8a`, and the focused Habitat runner/CLI suite passed
with `74` tests. The mixed stable-plus-relocation evidence-only learning
pipeline used:

- Stable input:
  `runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_event_posterior_option_end_v2`
- Relocation input:
  `runs/habitat_closed_loop_dual_anchor/grounding_dino_goal_object_relocation_ranked_navmesh_event_posterior_balanced6_20260530_v1`
- Output:
  `runs/habitat_closed_loop_dual_anchor/memory_validity_learning_grounding_dino_stable_relocation_balanced6_evidence_only_20260530_v1`

That pipeline produced `12` examples (`5` valid, `7` invalid), trained on `10`
non-toilet examples, held out `2` toilet examples, reported one learned
decision flip, and still found `0` fixed/evidence/event-posterior heuristic
flips in the bundled decision-sensitivity output.

The first online replay of the flipped relocated `sofa` row is complete:

- Baseline:
  `runs/habitat_closed_loop_dual_anchor/event_posterior_sofa_relocation_baseline_online_20260530_v1`
- Learned:
  `runs/habitat_closed_loop_dual_anchor/learned_validity_sofa_relocation_evidence_only_online_20260530_v1`
- Group:
  `hm3d/val/00820-mL8ThkuaVTM/mL8ThkuaVTM.basis.glb|sofa|relocated:goal_object:220->goal_object:341`

Matched A/B result:

- Baseline event-posterior reliability: `0.2875`
- Baseline decision: `memory_first`
- Learned probability: `0.006685`
- Learned decision: `frontier_first`
- Learned decision bucket: `harmful_memory_reuse_avoided`
- Memory evidence label: invalid (`shared_gate_success=false`,
  `detector_precision=0.0`)
- Success: `0/1` for both baseline and learned replay

This finally demonstrates a detector-backed learned pre-decision validity signal
causing an online Habitat memory-vs-frontier policy flip. It is not yet a
benchmark win because the selected relocation row still fails after choosing
frontier.

Broader matched current-code learned replay is also complete:

- Stable baseline:
  `runs/habitat_closed_loop_dual_anchor/event_posterior_stable_balanced6_current_online_20260530_v1`
- Stable learned:
  `runs/habitat_closed_loop_dual_anchor/learned_validity_stable_balanced6_evidence_only_online_20260530_v1`
- Relocation baseline:
  `runs/habitat_closed_loop_dual_anchor/event_posterior_goal_object_relocation_balanced6_current_online_20260530_v1`
- Relocation learned:
  `runs/habitat_closed_loop_dual_anchor/learned_validity_goal_object_relocation_balanced6_evidence_only_online_20260530_v1`
- Current-code learning pipeline:
  `runs/habitat_closed_loop_dual_anchor/memory_validity_learning_grounding_dino_current_stable_relocation_balanced6_evidence_only_20260530_v1`

Matched matrix result:

- Stable memory-guided baseline: `4/6`, `528` actions.
- Stable learned memory-guided: `4/6`, `795` actions.
- Stable online learned flip: `tv_monitor`, `memory_first -> frontier_first`,
  `0.242777 -> 0.015903`, still failed.
- Relocation memory-guided baseline: `0/6`, `1446` actions.
- Relocation learned memory-guided: `0/6`, `1643` actions.
- Relocation online learned flip: `sofa`, `memory_first -> frontier_first`,
  `0.2875 -> 0.006685`, still failed.

The current-code evidence-only learning pipeline produced a model JSON
identical to the earlier evidence-only model. The offline current-code scorer
found two decision flips (`stable tv_monitor` and relocated `sofa`), while
fixed/evidence/event-posterior heuristic mining still found `0` flips.

Interpretation: learned validity is now a real online decision mechanism, but
not yet an ObjectNav gain. The next bottleneck is the fallback side of the
policy: when learned validity rejects stale or false-positive memory,
`navmesh_frontier` often cannot recover the target.

## Latest Official ObjectNav Local-Control Learning State

The official Habitat ObjectNav path now has a self-supervised local
action-effect dataset exporter:

- Design:
  `docs/design/2026-05-30-official-local-action-effect-learning.md`
- Experiment:
  `docs/experiments/2026-05-30-official-local-action-effect-dataset-yolo-trace.md`
- API:
  `objectnav_core.evaluation.habitat_official_local_action_dataset`
- CLI:
  `python -m objectnav_core.cli.export_habitat_official_local_action_dataset <policy_trace.json> --detector-trace <detector_trace.json> --output <dataset.json> --csv-output <examples.csv>`

The exporter joins official `policy_trace.json` and `detector_trace.json`
artifacts by episode/step. It records pre-action features and labels the next
observation as target retained, lost, acquired, or remained absent. It also
merges detector evidence from `policy_trace` debug payloads, because the
official detector trace stores raw detections while bbox area and center-offset
features live in the policy debug.

Initial export from
`memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`
wrote:

- `runs/habitat_official_objectnav/local_action_effect_dataset_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/dataset.json`
- `runs/habitat_official_objectnav/local_action_effect_dataset_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/examples.csv`

Summary counts: `200` policy steps, `196` action-effect examples, `2`
retained, `2` lost, `2` acquired, and `190` remained-absent transitions. The
visible examples all come from the `tv_monitor` local-control failure: two
forward edge-tracking steps retain the target while bbox area drops and
absolute center offset increases, then the next forward step loses the target.

Verification after adding the exporter: focused local API tests produced `5`
passed; the local focused official-memory/exporter set produced `73` passed;
`py_compile`, local `compileall`, and local `git diff --check` passed. The new
slice was copied to the Linux mirror, where the same focused set produced `73`
passed and Linux `compileall` plus `git diff --check` were clean. No benchmark
improvement is claimed from this; it is a learning dataset substrate. Next
recommended action is to train an initial local action-effect scorer and
integrate it as a new official policy variant, while collecting a larger trace
set than the four-episode smoke.

The initial scorer is now implemented:

- Design:
  `docs/design/2026-05-30-official-local-action-effect-scorer.md`
- Experiment:
  `docs/experiments/2026-05-30-official-local-action-effect-scorer-yolo-smoke.md`
- API:
  `objectnav_core.evaluation.habitat_official_local_action_model`
- CLI:
  `python -m objectnav_core.cli.train_habitat_official_local_action_model <dataset.json> --output <model.json>`

It is a deterministic logistic model that predicts
`labels.next_target_visible` from pre-action local detector evidence and
candidate action identity. Candidate-action scoring supports action overrides,
so later policy code can ask the same evidence state how `move_forward`,
`turn_left`, and `turn_right` score. The default feature set intentionally
excludes outcome fields and excludes behavior-policy decision one-hots to avoid
leaking the policy that collected the trace into counterfactual action scoring.

The YOLO scorer smoke wrote:

- `runs/habitat_official_objectnav/local_action_effect_model_memory_evidence_frontier_action_effect_yolo_4ep_50steps_20260530_v1/model.json`

Metrics on the tiny trace: `196` examples, `4` positive labels, `192` negative
labels, accuracy `0.989796`, log loss `0.057894`, Brier `0.011688`, mean
prediction `0.026852`. These are class-imbalance diagnostics only, not evidence
of ObjectNav improvement. On the visible `tv_monitor` rows, the scorer ranked
`turn_left` above repeated `move_forward`, including at step `8` before target
loss. Next recommended action is to integrate this scorer as a separate
official policy variant, not to overwrite `memory_evidence_frontier`.

## Files Touched

- `docs/design/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- `docs/design/2026-05-29-habitat-decision-sensitivity-miner.md`
- `docs/design/2026-05-30-habitat-goal-object-relocation-challenge.md`
- `docs/design/2026-05-30-memory-validity-learning-dataset.md`
- `docs/design/2026-05-30-memory-validity-logistic-baseline.md`
- `docs/design/2026-05-30-memory-validity-learned-decision-scorer.md`
- `docs/design/2026-05-30-memory-validity-heldout-evaluation.md`
- `docs/design/2026-05-30-memory-validity-learning-pipeline.md`
- `docs/devlog/2026-05.md`
- `docs/experiments/2026-05-30-habitat-goal-object-relocation-smoke.md`
- `docs/experiments/2026-05-29-dual-anchor-pressure-smoke.md`
- `docs/experiments/2026-05-29-closed-loop-dual-anchor-grid-smoke.md`
- `docs/experiments/2026-05-29-habitat-closed-loop-grounding-dino-candidate-gate.md`
- `docs/experiments/2026-05-29-habitat-closed-loop-dual-anchor-oracle-action-smoke.md`
- `docs/experiments/2026-05-29-habitat-closed-loop-dual-anchor-oracle-action-smoke.zh.html`
- `docs/experiments/2026-05-29-habitat-decision-sensitivity-broad-balanced6.md`
- `docs/experiments/2026-05-29-habitat-detector-confirmation-ablation-balanced3.md`
- `docs/experiments/2026-05-29-habitat-decision-sensitivity-mining-balanced3.md`
- `docs/experiments/2026-05-29-habitat-event-posterior-balanced3-comparison.md`
- `docs/experiments/2026-05-29-habitat-event-posterior-grounding-dino-smoke.md`
- `docs/experiments/2026-05-29-habitat-event-posterior-stale-balanced3-comparison.md`
- `docs/experiments/2026-05-29-habitat-navmesh-evidence-calibration-smoke.md`
- `docs/experiments/2026-05-29-habitat-navmesh-grounding-dino-evidence-calibration-smoke.md`
- `docs/experiments/2026-05-29-habitat-navmesh-grounding-dino-stale-detector-pixels-smoke.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- `docs/superpowers/plans/2026-05-29-adaptive-detector-event-reliability.md`
- `docs/superpowers/plans/2026-05-29-closed-loop-dual-anchor-grid-benchmark.md`
- `docs/superpowers/plans/2026-05-29-habitat-decision-sensitivity-miner.md`
- `docs/superpowers/plans/2026-05-29-habitat-closed-loop-dual-anchor-smoke.md`
- `docs/superpowers/plans/2026-05-30-memory-validity-logistic-baseline.md`
- `docs/superpowers/plans/2026-05-30-memory-validity-learned-decision-scorer.md`
- `docs/superpowers/plans/2026-05-30-memory-validity-heldout-evaluation.md`
- `docs/superpowers/plans/2026-05-30-memory-validity-learning-pipeline.md`
- `src/objectnav_core/objectnav_core/cli/run_habitat_memory_validity_learning_pipeline.py`
- `src/objectnav_core/objectnav_core/cli/mine_habitat_decision_sensitivity.py`
- `src/objectnav_core/objectnav_core/cli/score_habitat_memory_validity_model.py`
- `src/objectnav_core/objectnav_core/cli/train_habitat_memory_validity_model.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`
- `src/objectnav_core/objectnav_core/cli/run_closed_loop_dual_anchor_benchmark.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_decision_sensitivity.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_pipeline.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_action_follower.py`
- `src/objectnav_core/objectnav_core/evaluation/closed_loop_dual_anchor_benchmark.py`
- `src/objectnav_core/objectnav_core/geometry/dual_anchor.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_memory_lifecycle_objectnav.py`
- `src/objectnav_core/objectnav_core/evaluation/dual_anchor_pressure.py`
- `src/objectnav_core/objectnav_core/cli/run_dual_anchor_pressure.py`
- `src/objectnav_core/objectnav_core/planning/memory_guided.py`
- `src/objectnav_core/tests/test_closed_loop_dual_anchor_benchmark.py`
- `src/objectnav_core/tests/test_closed_loop_dual_anchor_cli.py`
- `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`
- `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py`
- `src/objectnav_core/tests/test_habitat_decision_sensitivity.py`
- `src/objectnav_core/tests/test_habitat_memory_validity_model.py`
- `src/objectnav_core/tests/test_habitat_memory_validity_pipeline.py`
- `src/objectnav_core/tests/test_habitat_action_follower.py`
- `src/objectnav_core/tests/test_dual_anchor_geometry.py`
- `src/objectnav_core/tests/test_dual_anchor_pressure.py`
- `src/objectnav_core/tests/test_dual_anchor_pressure_cli.py`
- `src/objectnav_core/tests/test_lifelong_objectnav_benchmark.py`

## Commands Run

Local:

```bash
git diff --check
python -m py_compile src/objectnav_core/objectnav_core/evaluation/dual_anchor_pressure.py src/objectnav_core/objectnav_core/cli/run_dual_anchor_pressure.py
python -m pytest src/objectnav_core/tests/test_dual_anchor_geometry.py src/objectnav_core/tests/test_dual_anchor_pressure.py src/objectnav_core/tests/test_lifelong_objectnav_benchmark.py -q
python -m pytest src/objectnav_core/tests/test_dual_anchor_pressure.py src/objectnav_core/tests/test_dual_anchor_pressure_cli.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_dual_anchor_pressure --output /tmp/dual_anchor_pressure_smoke
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_closed_loop_dual_anchor_benchmark.py src/objectnav_core/tests/test_closed_loop_dual_anchor_cli.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_closed_loop_dual_anchor_benchmark --output /tmp/closed_loop_dual_anchor_grid_smoke
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --output /tmp/habitat_closed_loop_dual_anchor_preflight --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --target-categories plant,toilet --max-groups 2 --preflight-only
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --output /tmp/habitat_closed_loop_grounding_dino_preflight --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --target-categories plant,toilet --max-groups 2 --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.2 --grounding-dino-max-image-side 384 --rgb-noise-profile configs/noise/rgb_published_v1.yaml --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml --noise-level mild --min-target-pixels 24 --min-detector-pixels 20 --max-detection-area-ratio 0.7 --detector-prompt-mode target --preflight-only
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_calibrated_memory_decision_keeps_strong_shorter_memory src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_calibrated_memory_decision_still_uses_frontier_when_frontier_is_shorter src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_evidence_reliability_boosts_strong_current_positive_memory src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_evidence_reliability_rejects_nonpositive_or_ambiguous_memory -q
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only origin codex/habitat-memory-lifecycle && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/navmesh_frontier_oracle_smoke_1group_v1 --target-categories plant,toilet --max-groups 1 --sensor-width 1280 --sensor-height 720 --challenge stable --query-repeats 1 --memory-valid-prior 0.5 --frontier-mode navmesh_frontier --frontier-probe-count 5'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only origin codex/habitat-memory-lifecycle && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && rm -rf runs/habitat_closed_loop_dual_anchor/navmesh_frontier_oracle_smoke_balanced6_evidence_calibrated_v1 && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/navmesh_frontier_oracle_smoke_balanced6_evidence_calibrated_v1 --target-categories bed,chair,plant,sofa,toilet,tv_monitor --max-groups 6 --sensor-width 1280 --sensor-height 720 --challenge stable --query-repeats 1 --memory-valid-prior 0.5 --memory-reliability-mode evidence --frontier-mode navmesh_frontier --frontier-probe-count 5 --frontier-probe-heading-count 4'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && rm -rf runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_evidence_calibrated_v1 && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/navmesh_frontier_grounding_dino_smoke_balanced6_evidence_calibrated_v1 --target-categories bed,chair,plant,sofa,toilet,tv_monitor --max-groups 6 --sensor-width 1280 --sensor-height 720 --challenge stable --query-repeats 1 --memory-valid-prior 0.5 --memory-reliability-mode evidence --frontier-mode navmesh_frontier --frontier-probe-count 5 --frontier-probe-heading-count 4 --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --rgb-noise-profile configs/noise/rgb_published_v1.yaml --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml --noise-level clean --min-target-pixels 24 --min-detector-pixels 20 --max-detection-area-ratio 0.7 --detector-prompt-mode target'
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_detector_reliability_uses_detector_pixels_not_oracle_pixels -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_action_follower.py::test_follow_greedy_geodesic_route_records_per_action_observations src/objectnav_core/tests/test_habitat_action_follower.py::test_follow_greedy_geodesic_route_sequence_preserves_waypoint_costs -q
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_habitat_closed_loop_preflight_records_route_observation_mode src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_per_action_route_observation_truncates_at_first_positive_step -q
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py::test_habitat_closed_loop_cli_preflight_accepts_route_observation_mode -q
PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_stale_proxy_initial_memory_route_is_not_truncated_by_per_action_positive -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_action_follower.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_action_follower.py src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
git diff --check
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only origin codex/habitat-memory-lifecycle && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only origin codex/habitat-memory-lifecycle && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_action_follower.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && rm -rf runs/habitat_closed_loop_dual_anchor/per_action_oracle_navmesh_1group_v1 && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/per_action_oracle_navmesh_1group_v1 --target-categories plant,toilet --max-groups 1 --sensor-width 1280 --sensor-height 720 --challenge stable --query-repeats 1 --memory-valid-prior 0.5 --memory-reliability-mode evidence --frontier-mode navmesh_frontier --frontier-probe-count 5 --frontier-probe-heading-count 4 --route-observation-mode per_action'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only origin codex/habitat-memory-lifecycle && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && rm -rf runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_1group_v1 && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_1group_v1 --target-categories plant,toilet --max-groups 1 --sensor-width 1280 --sensor-height 720 --challenge stable --query-repeats 1 --memory-valid-prior 0.5 --memory-reliability-mode evidence --frontier-mode navmesh_frontier --frontier-probe-count 5 --frontier-probe-heading-count 4 --route-observation-mode per_action --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --rgb-noise-profile configs/noise/rgb_published_v1.yaml --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml --noise-level clean --min-target-pixels 24 --min-detector-pixels 20 --max-detection-area-ratio 0.7 --detector-prompt-mode target'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only origin codex/habitat-memory-lifecycle && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_action_follower.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && rm -rf runs/habitat_closed_loop_dual_anchor/per_action_oracle_navmesh_trace_1group_v1 && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/per_action_oracle_navmesh_trace_1group_v1 --target-categories plant,toilet --max-groups 1 --sensor-width 1280 --sensor-height 720 --challenge stable --query-repeats 1 --memory-valid-prior 0.5 --memory-reliability-mode evidence --frontier-mode navmesh_frontier --frontier-probe-count 5 --frontier-probe-heading-count 4 --route-observation-mode per_action'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only origin codex/habitat-memory-lifecycle && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_action_follower.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q'
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && rm -rf runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_audit_1group_v1 && HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_audit_1group_v1 --target-categories plant,toilet --max-groups 1 --sensor-width 1280 --sensor-height 720 --challenge stable --query-repeats 1 --memory-valid-prior 0.5 --memory-reliability-mode evidence --frontier-mode navmesh_frontier --frontier-probe-count 5 --frontier-probe-heading-count 4 --route-observation-mode per_action --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --rgb-noise-profile configs/noise/rgb_published_v1.yaml --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml --noise-level clean --min-target-pixels 24 --min-detector-pixels 20 --max-detection-area-ratio 0.7 --detector-prompt-mode target'
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py::test_miner_ranks_close_mixed_event_rows -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py::test_miner_marks_evidence_to_event_posterior_decision_flips -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py::test_decision_sensitivity_cli_writes_json_and_csv -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_decision_sensitivity.py src/objectnav_core/objectnav_core/cli/mine_habitat_decision_sensitivity.py
git diff --check
```

Linux commands run:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
git pull --ff-only origin codex/habitat-memory-lifecycle
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/oracle_action_stale_proxy_repeats2_balanced6_eu_p05_v1 --target-categories bed,chair,plant,sofa,toilet,tv_monitor --max-groups 6 --sensor-width 1280 --sensor-height 720 --challenge stale_proxy --query-repeats 2 --memory-valid-prior 0.5
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/oracle_action_stable_balanced6_eu_p05_v1 --target-categories bed,chair,plant,sofa,toilet,tv_monitor --max-groups 6 --sensor-width 1280 --sensor-height 720 --challenge stable --query-repeats 1 --memory-valid-prior 0.5
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/grounding_dino_candidate_gate_6cat_stale_repeats2_v1 --target-categories bed,chair,plant,sofa,toilet,tv_monitor --max-groups 6 --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --rgb-noise-profile configs/noise/rgb_published_v1.yaml --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml --noise-level clean --min-target-pixels 24 --min-detector-pixels 20 --max-detection-area-ratio 0.7 --detector-prompt-mode target --challenge stale_proxy --query-repeats 2
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/grounding_dino_candidate_gate_6cat_stable_v1 --target-categories bed,chair,plant,sofa,toilet,tv_monitor --max-groups 6 --detector grounding_dino --detector-weights IDEA-Research/grounding-dino-tiny --detector-conf 0.25 --grounding-dino-text-threshold 0.25 --grounding-dino-max-image-side 384 --rgb-noise-profile configs/noise/rgb_published_v1.yaml --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml --noise-level clean --min-target-pixels 24 --min-detector-pixels 20 --max-detection-area-ratio 0.7 --detector-prompt-mode target --challenge stable --query-repeats 1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.mine_habitat_decision_sensitivity runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_event_posterior_v1/summary.json runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_stale_event_posterior_v1/summary.json --output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_balanced3_event_posterior_mining_v1/report.json --csv-output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_balanced3_event_posterior_mining_v1/candidates.csv --top-k 20
```

## Verification

Passed locally before this handoff update:

- Focused dual-anchor geometry/planning tests: `9` passed.
- Pressure CLI/report tests: `3` passed.
- `py_compile` for the pressure runner and CLI.
- `git diff --check`.
- Closed-loop grid benchmark/CLI focused tests: `2` passed.
- Closed-loop grid CLI smoke generated `summary.json` with:
  `memory_guided=67.210933 m`, `frontier_only=81.389524 m`,
  `naive_count=67.210933 m`.
- Habitat closed-loop preflight/CLI focused tests: `3` passed locally.
- Full local core tests after adding the Habitat smoke entry: `189` passed.
- Habitat challenge-mode focused tests: `4` passed locally.
- Full local core tests after challenge modes: `190` passed.
- Habitat challenge semantics focused tests: `5` passed locally.
- Full local core tests after challenge semantics fix: `191` passed.
- Habitat repeated stale focused tests: `6` passed locally.
- Full local core tests after repeated stale smoke: `192` passed.
- Full local core tests after repaired direct-memory route: `193` passed.
- Full local core tests after expected-utility decisions: `195` passed.
- Full local core tests after decision-trace cleanup: `196` passed.
- Full local core tests after balanced group selection: `197` passed.
- Full local core tests after Grounding-DINO candidate-gate support: `200`
  passed.
- Full local core tests after stale-proxy evidence correction: `201` passed.
- Local closed-loop Habitat/CLI tests after navmesh frontier interface and
  helper wiring: `19` passed.
- Local closed-loop Habitat/CLI tests after fixed-heading scan support:
  `21` passed.
- Full local core tests after fixed-heading scan support: `207` passed.
- `git diff --check` passed after fixed-heading scan support.
- Linux focused Habitat tests after pulling fixed-heading scan support:
  `21` passed.
- Linux 1-group oracle navmesh heading-sweep smoke completed successfully with
  `--frontier-probe-count 5 --frontier-probe-heading-count 4`. It produced
  `frontier_only=124` actions and success through
  `navmesh_frontier_probe:1:heading:3`, while `memory_guided` and
  `naive_count` used accepted memory at `139` actions. This is a mechanism
  validation, not evidence that memory is better.
- Local closed-loop Habitat/CLI tests after cost-aware accepted-memory support:
  `24` passed.
- Full local core tests after cost-aware accepted-memory support: `210` passed.
- `git diff --check` passed after cost-aware accepted-memory support.
- Linux focused Habitat/CLI tests after pulling cost-aware accepted-memory
  support: `24` passed.
- Linux 1-group cost-aware oracle navmesh heading-sweep smoke completed
  successfully. It produced `memory_guided=124`, `frontier_only=124`, and
  `naive_count=139` actions. `memory_guided` selected `['frontier']` with
  `memory_decision=frontier_first`; `naive_count` selected `['memory']`.
- Linux balanced3 cost-aware oracle navmesh heading-sweep smoke completed
  successfully. It produced `memory_guided=419`, `frontier_only=708`, and
  `naive_count=387` actions across chair, plant, and toilet. `memory_guided`
  selected frontier for chair/plant, memory for toilet, and succeeded in all 3
  episodes. `frontier_only` failed on toilet; `naive_count` remained shorter in
  aggregate because chair memory was cheaper than the sampled frontier route.
- Local closed-loop Habitat/CLI tests after evidence reliability mode:
  `29` passed.
- Full local core tests after evidence reliability mode: `215` passed.
- `git diff --check` passed after evidence reliability mode.
- Linux focused Habitat/CLI tests after pulling evidence reliability mode:
  `29` passed.
- Linux balanced3 evidence-reliability oracle navmesh smoke completed
  successfully. It produced `memory_guided=373`, `frontier_only=708`, and
  `naive_count=387` actions. `memory_guided` selected memory for chair/toilet,
  frontier for plant, and succeeded in all 3 episodes. This is the first
  navmesh smoke in this slice where memory-guided beats both frontier-only and
  naive-count, but it is still only a 3-group oracle smoke.
- Local adaptive detector event reliability tests passed after the
  `event_posterior` implementation. The focused new tests produced `5` passed,
  the reliability/confirmation subset produced `11` passed, the focused
  Habitat route/CLI suite produced `65` passed, `py_compile` passed, and the
  full local core suite produced `248` passed.
- Linux pulled commit `1419a5e` and the focused Habitat route/CLI suite passed
  with `65` tests.
- Linux 1-group Grounding-DINO per-action navmesh smoke with
  `--memory-reliability-mode event_posterior` completed successfully at
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_event_posterior_1group_v1`.
  It produced the same action outcome as the earlier `evidence` event probe
  (`memory_guided=127`, `naive_count=127`, `frontier_only=354`), but lowered
  the memory-guided reliability from `0.96` to `0.710654` and recorded
  `detector_event_posterior=0.506644` from mixed confirmed/suppressed events.
- Linux paired balanced3 Grounding-DINO comparison completed:
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_evidence_events_v2`
  versus
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_event_posterior_v1`.
  Both modes produced `memory_guided=354`, `naive_count=354`, and
  `frontier_only=1016` actions with no memory-guided hindsight regret.
  `event_posterior` lowered memory reliability by row (`chair=0.683481`,
  `plant=0.710654`, `toilet=0.81947`) but did not flip decisions.
- Linux paired stale balanced3 Grounding-DINO comparison completed:
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_stale_evidence_v1`
  versus
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced3_stale_event_posterior_v1`.
  Both modes produced `memory_guided=766`, `naive_count=782`, and
  `frontier_only=1858` actions across six rows, with no memory-guided hindsight
  regret. `event_posterior` kept repeat-0 stale/no-current rows at `0.225`
  despite high detector-event posterior, then lowered repaired repeat-1
  reliability from `0.96` to about `0.73` without flipping decisions.
- Linux balanced6 evidence-reliability oracle navmesh smoke completed
  successfully. It produced `memory_guided=565`, `frontier_only=943`, and
  `naive_count=575` actions. `memory_guided` selected memory for chair, toilet,
  bed, and tv_monitor; frontier for plant and sofa; and succeeded in all 6
  episodes. The gain over naive-count is small (`10` actions), so this is a
  useful direction check, not a benchmark claim.
- Local closed-loop Habitat/CLI tests after memory decision bucket support:
  `32` passed.
- Full local core tests after memory decision bucket support: `218` passed.
- `git diff --check` passed after memory decision bucket support.
- Linux focused Habitat/CLI tests after pulling memory decision buckets:
  `32` passed.
- Linux balanced6 evidence-mode navmesh rerun with buckets preserved
  `memory_guided=565`, `frontier_only=943`, and `naive_count=575` actions.
  Memory-guided bucket counts were `memory_shorter_reused=3`,
  `memory_rescued_frontier_failure=1`, `frontier_shorter_selected=1`, and
  `valid_memory_wrongly_deferred=1`.
- Local closed-loop Habitat/CLI tests after hindsight regret diagnostics:
  `34` passed.
- Full local core tests after hindsight regret diagnostics: `220` passed.
- `git diff --check` passed after hindsight regret diagnostics.
- Linux focused Habitat/CLI tests after pulling hindsight regret diagnostics:
  `34` passed.
- Linux balanced3 evidence-mode navmesh smoke with hindsight regret diagnostics
  produced `memory_guided=373`, `frontier_only=708`, and `naive_count=387`
  actions. `memory_guided` had `total_hindsight_action_regret=0`; `naive_count`
  had `14` action regret.
- Local calibration tests after the strong-positive reliability update:
  `4` passed. The new regressions cover keeping the shorter strong `sofa`
  memory and preserving the shorter `plant` frontier decision.
- Local closed-loop Habitat/CLI tests after the calibration update:
  `36` passed.
- Full local core tests after the calibration update: `222` passed.
- `git diff --check` passed after the calibration update.
- Linux focused Habitat/CLI tests after pulling calibration commit `3bff3c5`:
  `36` passed.
- Linux balanced6 oracle navmesh evidence calibration smoke completed
  successfully. It produced `memory_guided=561`, `naive_count=575`, and
  `frontier_only=943` actions. `memory_guided` had
  `total_hindsight_action_regret=0` and buckets
  `memory_shorter_reused=4`, `memory_rescued_frontier_failure=1`, and
  `frontier_shorter_selected=1`. The targeted `sofa` row selected memory at
  `98` actions; the targeted `plant` row still selected frontier at `125`
  actions.
- Linux balanced6 Grounding-DINO candidate-view navmesh evidence calibration
  smoke completed successfully. It produced `memory_guided=564`,
  `naive_count=575`, and `frontier_only=946` actions. `memory_guided` again had
  `total_hindsight_action_regret=0`, selected memory for `sofa`, and selected
  frontier for `plant`.
- Local detector-pixel reliability red test initially failed with
  `assert 0.98 == 0.72`, showing oracle pixels were inflating detector-backed
  current evidence. After the fix, the focused detector reliability test passed,
  focused Habitat/CLI tests produced `37` passed, and full local core tests
  produced `223` passed.
- Linux focused Habitat/CLI tests after pulling detector-pixel reliability fix
  `ffcfd41`: `37` passed.
- Linux stable Grounding-DINO balanced6 navmesh detector-pixel v2 smoke
  preserved the previous aggregate result: `memory_guided=564`,
  `naive_count=575`, and `frontier_only=946`, with `memory_guided`
  `total_hindsight_action_regret=0`.
- Linux stale-proxy Grounding-DINO balanced6 navmesh detector-pixel v2 smoke
  produced `memory_guided=1334`, `naive_count=1962`, and `frontier_only=2038`
  actions. Repeat-0 stale memories had `current_evidence=0.15`,
  `memory_valid_prior=0.225`, and reason `matching_no_current_observation`;
  repaired detector-positive memories could return to prior `0.96` on repeat 1.
- Local per-action route observation red tests failed first because route
  observations, the CLI/preflight argument, and `_observe_route_until_positive`
  were missing. After implementation, focused route/CLI tests produced `46`
  passed.
- A stale-proxy per-action accounting regression failed first because
  `_observe_initial_memory_route` was missing, then because positive upstream
  evidence was still accepted. The final helper keeps initial stale memory
  routes untruncated and non-confirming.
- Full local core tests after per-action route observation mode: `229` passed.
- `py_compile` for `habitat_action_follower.py`,
  `habitat_closed_loop_dual_anchor_objectnav.py`, and the Habitat CLI passed.
- `git diff --check` passed after the per-action route observation update.
- Linux focused Habitat route/CLI tests after pulling commit `847c66a`:
  `46` passed.
- Linux 1-group oracle navmesh smoke with `--route-observation-mode per_action`
  completed successfully. It recorded `route_observation_mode=per_action` and
  `frontier_mode=navmesh_frontier`. On the selected `plant` group,
  `memory_guided=118` actions, `naive_count=118`, and `frontier_only=124`.
  Memory-guided reused accepted memory; frontier-only succeeded through
  `navmesh_frontier_probe:1:heading:3`; post-memory fallback had a per-action
  positive at `navmesh_frontier_probe:0:step:0`.
- Linux 1-group Grounding-DINO navmesh smoke with
  `--route-observation-mode per_action` completed successfully. It recorded
  `detector=grounding_dino`, `route_observation_mode=per_action`, and
  `frontier_mode=navmesh_frontier`. On the selected `plant` group,
  `memory_guided=122`, `naive_count=122`, and `frontier_only=159` actions.
  Memory, fallback, and post-memory fallback evidence were all
  `detector_positive_mask`.
- Local row trace tests after the Grounding-DINO smoke added explicit
  `memory_route_observation`, `fallback_route_observation`, and
  `fallback_from_memory_route_observation` payloads. Focused Habitat route/CLI
  tests produced `49` passed; full local core tests produced `232` passed.
- Linux focused Habitat route/CLI tests after pulling commit `1667d14`:
  `49` passed.
- Linux 1-group oracle navmesh trace smoke after commit `1667d14` confirmed the
  new row payloads in `summary.json`: memory route selected
  `goal_viewpoint:10:route:step:117` with `observation_count=118`, frontier
  fallback selected `navmesh_frontier_probe:1:heading:3`, and post-memory
  fallback selected `navmesh_frontier_probe:0:step:0`.
- Linux balanced3 Grounding-DINO navmesh smoke with
  `--route-observation-mode per_action` completed successfully on chair, plant,
  and toilet. It produced `memory_guided=347`, `naive_count=347`, and
  `frontier_only=357` actions. The run is diagnostic, not a benchmark claim:
  the `plant` memory row was detector-positive with `overlap_pixels=0` and
  `detector_precision=0.0`, exposing a detector false confirmation.
- Local detector false-confirmation audit tests added
  `detector_false_confirmation` row fields and summary counts. Focused Habitat
  route/CLI tests produced `51` passed; full local core tests produced `234`
  passed.
- Linux focused Habitat route/CLI tests after pulling commit `46d94d5`:
  `51` passed.
- Linux 1-group Grounding-DINO per-action audit smoke after commit `46d94d5`
  completed successfully and confirmed the runtime summary fields. All three
  policies reported `detector_false_confirmation_counts={'memory': 1}` for the
  selected `plant` group; the row-level memory evidence had
  `detector_overlap_success=false` and `detector_false_confirmation=true`.
- Local detector multiview confirmation tests added the API/CLI summary fields,
  helper behavior, weak pending reliability, confirmed-detector audit, and
  summary counts. Focused detector confirmation tests produced `5` passed;
  the focused CLI confirmation test produced `1` passed.
- Local focused Habitat route/CLI tests after multiview confirmation wiring
  produced `58` passed.
- Full local core tests after multiview confirmation wiring produced
  `241` passed.
- `py_compile` passed for the Habitat closed-loop runner, lifecycle verification
  module, and Habitat CLI.
- `git diff --check` passed after the multiview confirmation update.
- Linux focused Habitat route/CLI tests after pulling commit `88d1fa0`:
  `58` passed.
- Linux 1-group Grounding-DINO per-action navmesh smoke with
  `--detector-confirmation-mode multiview` completed successfully. It recorded
  `detector_confirmation_mode=multiview`, `route_observation_mode=per_action`,
  and `detector=grounding_dino`. The selected `plant` group produced
  `memory_guided=127`, `naive_count=127`, and `frontier_only=354` actions.
  Policy summaries reported `detector_confirmation_counts={'confirmed': 2}`.
  Memory evidence and post-memory fallback evidence were
  `confirmed_detector_positive_mask`; no detector false confirmations were
  counted in this smoke.
- Linux paired detector-confirmation balanced3 ablation completed. The
  `single_frame` run reproduced the earlier action profile
  (`memory_guided=347`, `frontier_only=357`, `naive_count=347`) and retained a
  `plant` memory false confirmation. The `multiview` run removed the false
  confirmation and reported `detector_confirmation_counts={'confirmed': 7}`,
  but frontier-only failed on two categories and rose to `1016` actions
  (`memory_guided=354`, `naive_count=354`). Two invalid multiview command
  attempts failed before producing metrics and are documented as excluded in the
  experiment report.
- Local detector-confirmation event tests initially failed because
  `_apply_detector_confirmation` did not accept an event sink and policy
  summaries had no runtime event counts. After the event wiring, the two new
  focused tests passed, and the full closed-loop objectnav test file produced
  `50` passed.
- Focused Habitat route/CLI suite after runtime confirmation event wiring:
  `60` passed. Full local core tests produced `243` passed. `py_compile`,
  `git diff --check`, and the sensitive scan produced no issues.
- Linux focused Habitat tests after pulling navmesh frontier commit: `19`
  passed.
- First Linux `navmesh_frontier` oracle smoke failed in
  `GreedyGeodesicFollower.next_action_along(...)` with
  `habitat_sim.errors.GreedyFollowerError` during post-memory probe routing.
  Local follow-up regression now covers skipping skippable route errors; rerun
  the Linux smoke after pushing that fix.
- Rerun after skipping unreachable probe segments completed successfully for
  1 group with `--frontier-probe-count 5`: memory-guided and naive-count
  succeeded through stable memory (`139` actions each), while frontier-only
  failed after `339` actions because sampled probes had no positive evidence.
  This run motivated local fixed-heading scan support before scaling.
- Linux focused Habitat tests after the expected-utility CLI update: `9` passed.
- Linux focused Habitat tests after Grounding-DINO candidate-gate support:
  `14` passed.
- Linux focused Habitat tests after stale-proxy evidence correction: `15`
  passed.
- Linux stable balanced6 oracle/action smoke:
  `memory_guided=575` actions, `naive_count=575`,
  `frontier_only=1311`.
- Linux stale balanced6 oracle/action smoke with
  `--query-repeats 2 --memory-valid-prior 0.5`:
  `memory_guided=2020` actions, `frontier_only=3074`,
  `naive_count=4148`.
- Linux stable balanced6 Grounding-DINO candidate-gate smoke:
  `memory_guided=575` actions, `naive_count=575`,
  `frontier_only=1313`, with all selected memory and fallback gates positive.
- Linux stale balanced6 Grounding-DINO candidate-gate smoke:
  `memory_guided=2018` actions, `frontier_only=3072`,
  `naive_count=4144`. Old stale memory evidence is
  `non_confirmation/shared_gate_success=false`; fallback/repaired anchors are
  detector-positive for all six selected categories.
- Local decision-sensitivity miner TDD verified the red states first:
  analyzer tests failed while
  `objectnav_core.evaluation.habitat_decision_sensitivity` was missing, and
  the CLI test failed while
  `objectnav_core.cli.mine_habitat_decision_sensitivity` was missing.
- Local decision-sensitivity miner focused tests produced `4` passed.
- Local integration-adjacent suite with the new miner plus Habitat closed-loop
  objectnav/CLI tests produced `65` passed.
- Full local core suite after the decision-sensitivity miner update produced
  `252` passed.
- `py_compile` passed for
  `habitat_decision_sensitivity.py` and
  `mine_habitat_decision_sensitivity.py`.
- `git diff --check` passed after the decision-sensitivity miner update.
- Narrow sensitive-pattern scan for the provided Linux password produced no
  matches in `docs` or `src`. The exact command is omitted so the secret is not
  recorded in docs.
- Linux pulled commit `2476009` and the focused decision-sensitivity miner tests
  produced `4` passed in conda env `habitat`.
- Linux decision-sensitivity mining over stable and stale balanced3
  Grounding-DINO `event_posterior` summaries completed successfully at
  `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_balanced3_event_posterior_mining_v1`.
  The report mined `2` summaries, scanned `9` memory-guided rows, reported `9`
  candidate rows, and found `0` counterfactual decision flips with `0`
  warnings. Top rows were stable `chair` repeat 0
  (`margin=2.050443`, `0.96 -> 0.683481`) and stale `chair` repeat 1
  (`margin=3.808479`, `0.96 -> 0.730507`).
- Local boundary-region refinement for the miner added an unclamped
  decision-boundary reliability and boundary-region field. The red regression
  failed before implementation; after implementation, focused analyzer tests
  produced `5` passed, integration-adjacent tests produced `66` passed, and
  the full local core suite produced `253` passed.
- Linux broad mining after the boundary refinement completed at
  `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_broad_existing_v3_all`.
  It mined `50` summaries, scanned `206` memory-guided rows, reported `144`
  candidates, found `95` reliability-sensitive boundaries, and still found `0`
  counterfactual flips.
- Linux balanced6 per-action Grounding-DINO `event_posterior` run completed at
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_balanced6_event_posterior_v1`.
  It produced `memory_guided=473`, `naive_count=473`, and
  `frontier_only=1064` actions, with `memory_guided` success `6/6` and `0`
  hindsight regret. Mining found `6` candidates and `0` flips.
- Linux matched option-end balanced6 multiview runs completed for `evidence`
  and `event_posterior`. Both produced identical decisions and aggregates:
  `memory_guided=773`, `naive_count=573`, and `frontier_only=2079`, with
  success `5/6`, `5/6`, and `1/6`. Mining found `0` counterfactual flips.
  One earlier option-end command failed before metrics because the depth-noise
  profile path was mistyped; it is excluded.

## Known Risks

- The current pressure runner is deterministic synthetic math, not Habitat.
- The closed-loop grid harness is option-level and config-truth, not Habitat.
- The Habitat closed-loop runner now has optional per-action route observation
  on precomputed GreedyGeodesic options, but it is still not a stepwise policy
  that replans after each frame and it still lacks true frontier mapping.
- `navmesh_frontier` is target-agnostic with respect to sampled route goals, but
  it is still a navmesh probe approximation, not an occupancy frontier built
  from depth observations. It now has local tests and several Linux Habitat
  smokes, but skipped route errors and scan-action counts should keep being
  audited so a weak frontier does not silently become an empty or free-sensing
  search.
- Early Linux smokes exposed invalid frontier accounting, partial challenge
  semantics, repaired-memory route mischarging, and stale-risk overprobing.
  These are fixed in the current branch and documented in the experiment
  report as negative/debug history.
- The current grid smoke does not beat `naive_count`; after the shared gate,
  memory-guided and naive-count tie. Treat this as plumbing/pressure validation,
  not a headline result.
- The previous lifecycle results should not be promoted as the main benchmark.
- The next Habitat implementation must give frontier/no-memory/naive baselines
  the same perception, action budget, and gate semantics as memory-guided.
- Natural staleness may require a careful Habitat object hide/move protocol if
  HM3D mesh-level object relocation is not clean.
- `memory_valid_prior=0.5` is a hand-set expected-utility prior. The sensitivity
  run with `0.8` was worse (`memory_guided=2151` actions on unbalanced max6
  versus `1917` at `0.5`), so this should become learned or evidence-derived.
- The current accepted-memory policy fix has been rerun on Linux for 1 group.
  It prevents costly memory reuse in that smoke, but does not yet show memory
  beating a fair frontier baseline.
- The balanced3 navmesh result shows the fixed `memory_valid_prior=0.5` is too
  blunt: it keeps the toilet win where frontier fails, but gives up cheap valid
  chair memory. Treat this as evidence for learning/estimating memory
  reliability, not as a reason to manually tune the prior.
- Evidence reliability mode now has a Linux balanced3 smoke. It improves this
  tiny oracle run and a balanced6 direction check, but it uses
  oracle/Grounding-DINO candidate-view evidence rather than per-action
  perception and remains a transparent heuristic, not learned calibration.
- The Linux balanced6 calibration smoke fixed the targeted `sofa`
  wrong-deferral row and kept `plant` frontier-selected, but this is still a
  tiny oracle navmesh smoke with a small 14-action gain over `naive_count`, not
  a benchmark claim.
- The Grounding-DINO candidate-view calibration smoke preserved the same bucket
  pattern with an 11-action gain over `naive_count`. Per-action route
  observation mode now has Linux oracle and 1-group Grounding-DINO smokes, but
  still needs larger detector-backed runs.
- The balanced3 Grounding-DINO per-action smoke exposed a `plant` detector false
  confirmation. This reinforces that aggregate action reductions must be
  reported alongside detector audit counts; do not treat detector-positive alone
  as proof of real target localization in simulation.
- Multiview detector confirmation has one Linux 1-group smoke. It confirmed two
  positive evidence sources and a paired balanced3 ablation. It removed the
  observed plant false confirmation, but it also made frontier-only much less
  reliable. This should motivate adaptive or learned detector reliability, not a
  fixed claim that stricter confirmation is always better.
- Runtime `detector_confirmation_events` now expose suppressed positives that
  do not become the selected row evidence. This is diagnostic-only and should
  be treated as training/calibration signal for reliability, not as an oracle
  policy gate.
- The targeted 1-group Grounding-DINO multiview event probe has now verified
  those runtime event counts in an actual Habitat artifact:
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_event_probe_1group_v1/summary.json`.
  Each policy summary reported
  `detector_confirmation_event_counts={'confirmed': 8, 'suppressed': 8}` with
  suppressed events in `memory`, `fallback`, and `fallback_from_memory`
  contexts. Treat this as diagnostic coverage, not a benchmark result.
- Detector-backed reliability no longer borrows oracle semantic pixel counts.
  The current stable/stale detector smokes are unchanged in aggregate because
  selected memory detector masks are strong, but broader weak-positive
  calibration still needs coverage beyond the 1-group event probe.
- The strong-positive floor is a hand-designed guardrail from hindsight-regret
  diagnostics. It should be treated as a calibration baseline, not the final
  algorithm, until it is validated on held-out scenes and replaced or supported
  by learned/evidence-derived reliability.
- `event_posterior` is still an interpretable posterior with hand-designed
  quality weights. It is a stronger adaptive baseline because it consumes
  runtime detector-event traces, but it still needs Linux Habitat smokes,
  held-out categories/scenes, and learned calibration before paper claims.
- The decision-sensitivity miner reproduces only summary-level
  expected-utility arithmetic. It is useful for selecting targeted follow-up
  rows, but mined rows are not policy results until rerun in Habitat with the
  chosen detector/frontier configuration.
- The first learned-validity online replay is now a policy result, but only a
  one-row mechanism result. It should not be presented as broad ObjectNav
  performance evidence.
- The balanced learned replay confirms multiple online flips but still no
  success or action-count improvement. Do not promote learned validity as a
  benchmark gain until frontier/search recovery improves.
- The first balanced3 mining smoke found no counterfactual decision flips.
  This reinforces that the existing balanced3 slices are still too stable for
  policy-gain claims.
- Broad boundary-aware mining and targeted balanced6 event-posterior checks
  still found no detector-event posterior decision flips. Current evidence
  supports confidence calibration, not a policy-benefit claim.
- Matched option-end evidence/event-posterior runs show that the weaker
  multiview option-end aggregate is caused by detector-confirmation behavior,
  not by the event-posterior rule alone.

## Next Recommended Step

1. Add or use a selector that ranks candidates by distance between the
   evidence/event-posterior reliability interval and the decision boundary.
   The explicit replay slice has now been used on the targeted `sofa` row, but
   that row stayed at `decision_boundary_reliability_raw=1.0`.
2. Investigate learned reliability calibration using mined rows as supervision,
   rather than hand-tuning the event-posterior weights.
3. Continue calibrating the reliability estimator against bucket counts and
   regret, especially valid memories wrongly deferred versus harmful memory
   reuse avoided.
4. Replace oracle/candidate-view reliability evidence with detector/per-action
   evidence before making benchmark claims.
5. Add a true occupancy/frontier exploration policy; `navmesh_frontier` is only
   an intermediate target-agnostic probe baseline.
6. Move Grounding-DINO from selected candidate-view verification to larger
   per-action observation and stopping experiments.
7. Implement natural Habitat object relocation/removal or a clearly labeled
   semantic-object hide/replace protocol.
8. Scale the balanced runs beyond six groups and report confidence intervals.
9. Convert the smoke metrics into SPL-like metrics only after per-action
   perception and a real frontier policy are in place.

## Context for Next Contributor

The target paper story is now stricter: show that dual-anchor memory helps
lifelong ObjectNav under map-frame restarts, localization uncertainty, instance
ambiguity, and stale objects. A small advantage over a weak search proxy is not
enough.

## 2026-05-29 Replay Slice Update

The Habitat closed-loop runner now accepts explicit `selected_group_ids` and
records the requested slice in `episode_selection`. This is the missing control
plane for replaying mined decision-boundary rows.

Verification run just completed:

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py -q`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_decision_sensitivity.py -q`
- `python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`
- `git diff --check`

Next step:
- Use the replay slice with a stronger selector: prioritize candidates whose
  decision boundary is close to, or bracketed by, the evidence/event-posterior
  reliability interval.

## 2026-05-29 Targeted Sofa Replay Result

The new replay interface was exercised on Linux with the mined `sofa` group:

- `hm3d/val/00800-TEEsavR23oF/TEEsavR23oF.basis.glb|sofa|goal_object:275`

Artifacts:

- Baseline:
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_sofa_event_posterior_selected_group_v1/summary.json`
- Sweep report:
  `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_sofa_selected_group_event_posterior_sweep_v1/report.json`
- Experiment write-up:
  `docs/experiments/2026-05-29-habitat-targeted-sofa-event-posterior-replay.md`

Result:

- Explicit selection worked: `selected_group_count=1` and
  `selection_mode=explicit_group_ids`.
- The row produced mixed detector events:
  `detector_event_count=6`, confirmed weight `7.517547`, suppressed weight
  `2.85`.
- Event posterior moved reliability from `0.96` to `0.819916`.
- No flip occurred. All five selected/sweep runs had
  `memory_action_count=63`, `fallback_action_count=63`,
  `fallback_from_memory_action_count=2`, and
  `decision_boundary_reliability_raw=1.0`.

## 2026-05-29 Interval-Gap Miner Update

The decision-sensitivity miner now records how far the reliability decision
boundary is from the interval spanned by evidence reliability and
event-posterior reliability.

New fields:

- `reliability_interval_min`
- `reliability_interval_max`
- `boundary_reliability_interval_gap`
- `boundary_reliability_interval_position`

New reason:

- `near_reliability_interval_boundary`

This directly addresses the targeted sofa replay failure: the row had mixed
events and a small action margin, but the decision boundary was just above the
reliability interval. The next broad mining pass should prioritize rows with a
small interval gap, not merely rows with small action margins.

## 2026-05-29 Targeted Tv Monitor Replay / Replay-Control Finding

The next interval-gap candidate was replayed on Linux:

- `hm3d/val/00813-svBbv1Pavdk/svBbv1Pavdk.basis.glb|tv_monitor|goal_object:287`

Artifacts:

- Selected replay:
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_tv_monitor_event_posterior_selected_group_v1/summary.json`
- Mined report:
  `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_tv_monitor_selected_group_event_posterior_v1/report.json`
- Experiment write-up:
  `docs/experiments/2026-05-29-habitat-targeted-tv-monitor-event-posterior-replay.md`

Result:

- Explicit selection worked: `selected_group_count=1` and
  `selection_mode=explicit_group_ids`.
- Detector-event posterior moved reliability from `0.96` to `0.6078` with
  `detector_event_count=4`, confirmed weight `1.77855`, and suppressed weight
  `4.35`.
- No flip occurred. The selected replay mined as
  `decision_boundary_region=memory_always_no_worse` with
  `memory_action_count=24`, `fallback_action_count=236`, and
  `fallback_from_memory_action_count=2`.

Important caveat:

- This selected replay did not reproduce the broad balanced6 row's frontier
  route accounting. The broad source row had `fallback_action_count=24` and
  fallback source `navmesh_frontier_probe:0:step:23`; the selected replay had
  `fallback_action_count=236` and fallback source
  `navmesh_frontier_probe:4:step:21`.
- Root cause: the runner derived navmesh frontier probe seeds and detector
  frame-index bases from `len(rows)`. Isolating the sixth balanced row changed
  row order and therefore changed target-agnostic frontier probes.

Local fix in progress:

- Added stable replay-control helpers in
  `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`.
- Future seeds are derived from `group_id` plus route context; detector frame
  bases are derived from `group_id`.
- Added regression coverage in
  `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`.
- Updated the targeted replay design note with the determinism requirement.

Verification already run locally for the fix:

- Red test
  `test_replay_control_values_are_stable_for_group_not_row_order` failed before
  implementation.
- Focused closed-loop/CLI suite passed: `65` tests.
- Full local core suite passed: `258` tests.
- `py_compile` passed for the runner and CLI module.
- `git diff --check` passed.

Additional Linux verification after commit `d963151`:

- Linux fast-forwarded to `d963151`.
- Focused closed-loop/CLI suite passed on Linux: `65` tests.
- Stable one-group replay:
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_tv_monitor_event_posterior_selected_group_stable_replay_controls_v1/summary.json`
- Stable one-group mining:
  `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_tv_monitor_selected_group_stable_replay_controls_v1/report.json`
- Stable two-group replay:
  `runs/habitat_closed_loop_dual_anchor/per_action_grounding_dino_navmesh_sofa_tv_monitor_event_posterior_selected_groups_stable_replay_controls_v1/summary.json`
- Stable two-group mining:
  `runs/habitat_closed_loop_dual_anchor/decision_sensitivity_sofa_tv_monitor_selected_groups_stable_replay_controls_v1/report.json`

Stable-control result:

- The one-group and two-group stable replays both produce the same
  `tv_monitor` route accounting:
  `memory_action_count=24`, `fallback_action_count=24`,
  `fallback_from_memory_action_count=2`, and fallback source
  `navmesh_frontier_probe:0:step:23`.
- This matches the original balanced6 broad row and confirms that selected
  replay no longer changes the `tv_monitor` frontier probes by row order.
- The mined result is still negative for policy flips:
  `decision_boundary_reliability_raw=1.0`,
  `decision_boundary_region=frontier_requires_perfect_memory`,
  `event_posterior_reliability=0.6078`, and
  `counterfactual_decision_flip=false`.
- The two-group run also reproduced the `sofa` boundary-edge negative:
  `memory_action_count=63`, `fallback_action_count=63`,
  `fallback_from_memory_action_count=2`, and boundary raw `1.0`.

Next step:

- Use the interval-gap miner to search beyond the current `sofa` and
  `tv_monitor` edge cases, or change experiment construction to create rows
  where the reliability boundary lies inside the evidence/event-posterior
  interval.

## 2026-05-30 Per-Action Route Observation Matrix

The learned-validity endpoint-only matrix exposed the next bottleneck: learned
validity can flip decisions, but endpoint-only frontier/search often cannot
recover the target. I picked up the interrupted relocated `sofa` per-action
replay, then ran a matched per-action matrix on current code.

Artifacts:

- Selected sofa baseline per-action:
  `runs/habitat_closed_loop_dual_anchor/event_posterior_sofa_relocation_baseline_per_action_selected_20260530_v1/summary.json`
- Selected sofa learned per-action:
  `runs/habitat_closed_loop_dual_anchor/learned_validity_sofa_relocation_evidence_only_per_action_selected_20260530_v1/summary.json`
- Stable balanced6 event-posterior per-action:
  `runs/habitat_closed_loop_dual_anchor/event_posterior_stable_balanced6_per_action_unavailable_frontier_fix_20260530_v1/summary.json`
- Stable balanced6 learned per-action:
  `runs/habitat_closed_loop_dual_anchor/learned_validity_stable_balanced6_evidence_only_per_action_unavailable_frontier_fix_20260530_v1/summary.json`
- Relocation balanced6 event-posterior per-action:
  `runs/habitat_closed_loop_dual_anchor/event_posterior_goal_object_relocation_balanced6_per_action_current_20260530_v1/summary.json`
- Relocation balanced6 learned per-action:
  `runs/habitat_closed_loop_dual_anchor/learned_validity_goal_object_relocation_balanced6_evidence_only_per_action_20260530_v1/summary.json`
- Experiment report:
  `docs/experiments/2026-05-30-habitat-per-action-route-observation-matrix.md`

Result:

- Selected relocated `sofa`:
  - `option_end` baseline failed in `49` actions.
  - `option_end` learned flipped to frontier and failed in `246` actions.
  - `per_action` baseline and learned both succeeded in `171` actions.
  - The win comes from post-memory local frontier confirmation at
    `navmesh_frontier_probe:2:step:0`, not from the learned model.
- Stable balanced6:
  - `option_end` event-posterior memory-guided: `5/6`, `573` actions.
  - `option_end` learned memory-guided: `5/6`, `840` actions.
  - `per_action` event-posterior memory-guided: `6/6`, `473` actions.
  - `per_action` learned memory-guided: `6/6`, `473` actions.
- Relocation balanced6:
  - `option_end` event-posterior memory-guided: `0/6`, `1446` actions.
  - `per_action` event-posterior memory-guided: `3/6`, `1176` actions.
  - `per_action` learned memory-guided: `3/6`, `1176` actions.

Interpretation:

- The current success improvement comes from route-level active confirmation,
  not from learned validity.
- Learned validity is still a real online decision mechanism under
  `option_end`, but in the per-action matrix it changes probabilities without
  changing decisions or outcomes.
- Memory remains valuable in relocation because it can seed local search after
  stale verification. In the relocation balanced6 matrix, frontier-only reaches
  `2/6`; memory-guided reaches `3/6` via the relocated `sofa` row.

Commands already run:

```bash
# Failed immediately due to wrong depth-noise profile path:
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav ... \
  --output runs/habitat_closed_loop_dual_anchor/event_posterior_stable_balanced6_per_action_current_20260530_v1 \
  --depth-noise-profile configs/noise_realsense_d435_v1.yaml

# Corrected stable baseline used _v2:
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav ... \
  --output runs/habitat_closed_loop_dual_anchor/event_posterior_stable_balanced6_per_action_current_20260530_v2 \
  --challenge stable \
  --sensor-width 1280 \
  --sensor-height 720 \
  --frontier-probe-count 5 \
  --frontier-probe-heading-count 4 \
  --route-observation-mode per_action

# Stable learned used the same settings plus:
--memory-validity-model runs/habitat_closed_loop_dual_anchor/memory_validity_learning_grounding_dino_current_stable_relocation_balanced6_evidence_only_20260530_v1/model.json

# Relocation baseline/learned used:
--challenge goal_object_relocation
--sensor-width 640
--sensor-height 360
--frontier-probe-count 3
--frontier-probe-heading-count 2
--route-observation-mode per_action
```

Next recommended action:

1. Treat the stable `bed` row as the first diagnostic for the next policy
   improvement. It has positive memory evidence, but expected utility selects a
   zero-action failed frontier option, causing the only stable per-action
   memory-guided failure.
2. Design memory-conditioned local active search explicitly: memory should seed
   a local frontier/confirmation policy after stale verification, instead of
   being only a terminal waypoint.
3. After fixing the degenerate frontier option and designing the local-search
   policy, rerun the same current-code per-action matrix before scaling beyond
   balanced6.

## 2026-05-30 Unavailable Frontier Decision Fix

Commit `033c8b8` fixes the first diagnostic from the per-action matrix:
`memory_guided` could select `navmesh_frontier_probe:none` because the failed
frontier route had `fallback_action_count=0`. The decision helper now accepts a
`fallback_available` flag, and the Habitat runner sets it to false when the
fallback route has zero actions and no positive verification.

Verification already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py -q -k unavailable_frontier

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q

python -m py_compile \
  src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest src/objectnav_core/tests -q
```

Linux verification:

- Focused closed-loop/CLI tests: `75` passed.
- Event-posterior selected stable `bed` replay:
  `runs/habitat_closed_loop_dual_anchor/event_posterior_bed_stable_per_action_selected_unavailable_frontier_fix_20260530_v1/summary.json`
  now chooses `memory_first`, succeeds, and uses `32` actions.
- Learned selected stable `bed` replay:
  `runs/habitat_closed_loop_dual_anchor/learned_validity_bed_stable_per_action_selected_unavailable_frontier_fix_20260530_v1/summary.json`
  now chooses `memory_first`, succeeds, and uses `32` actions.

Important caveat:

- The stable balanced6 matrix was rerun after `033c8b8`.
- Updated stable aggregates:
  - `option_end` event-posterior: `5/6`, `573` actions.
  - `option_end` learned: `5/6`, `840` actions.
  - `per_action` event-posterior: `6/6`, `473` actions.
  - `per_action` learned: `6/6`, `473` actions.
- Relocation per-action artifacts were not rerun after `033c8b8`, but the
  recorded relocation memory-guided rows did not contain a zero-action
  query-start frontier option.

Additional post-fix stable artifacts:

- `runs/habitat_closed_loop_dual_anchor/event_posterior_stable_balanced6_option_end_unavailable_frontier_fix_20260530_v1/summary.json`
- `runs/habitat_closed_loop_dual_anchor/learned_validity_stable_balanced6_evidence_only_option_end_unavailable_frontier_fix_20260530_v1/summary.json`
- `runs/habitat_closed_loop_dual_anchor/event_posterior_stable_balanced6_per_action_unavailable_frontier_fix_20260530_v1/summary.json`
- `runs/habitat_closed_loop_dual_anchor/learned_validity_stable_balanced6_evidence_only_per_action_unavailable_frontier_fix_20260530_v1/summary.json`

## 2026-05-30 High-Budget Relocation Probe

I probed the remaining relocation failures with a larger random navmesh budget:
`frontier_probe_count=8`, `frontier_probe_heading_count=4`,
`route_observation_mode=per_action`.

Artifacts:

- `runs/habitat_closed_loop_dual_anchor/event_posterior_tv_monitor_relocation_per_action_probe8_heading4_20260530_v1/summary.json`
- `runs/habitat_closed_loop_dual_anchor/learned_validity_tv_monitor_relocation_per_action_probe8_heading4_20260530_v1/summary.json`
- `runs/habitat_closed_loop_dual_anchor/event_posterior_relocation_remaining_failures_per_action_probe8_heading4_20260530_v1/summary.json`

Result:

- `tv_monitor` relocation:
  - event-posterior and learned both choose `memory_first`, succeed, and use
    `684` memory-guided actions.
  - frontier-only succeeds too, but needs `998` actions.
  - learned validity lowers probability to `0.006685`, yet post-memory search
    remains cheaper than query-start frontier.
- Reverse `chair` relocation:
  - event-posterior succeeds in `190` actions via query-start frontier.
- `toilet` relocation:
  - event-posterior still fails after `803` actions.

Interpretation:

- More random navmesh budget can recover some failures, but it is inefficient
  and incomplete.
- The next useful design is memory-conditioned local active search: use the
  memory anchor and route evidence to direct where the robot looks, instead of
  only increasing random probe count.

## 2026-05-30 Memory-Conditioned Local Active Search Design

New design doc:

- `docs/design/2026-05-30-memory-conditioned-local-active-search.md`

Design summary:

- Add a post-memory search mode that treats memory as a spatial prior even when
  it is not valid enough to be a stop target.
- Generate reachable local probes around the transformed memory anchor with
  expanding radii.
- Score probes by expected information gain per action, using distance to
  memory, route novelty, detector confirmation/suppression history, and route
  cost.
- Keep oracle target pixels audit-only; do not use relocated target pose or
  semantic id to choose probes.

Recommended next step:

1. Write tests for deterministic local probe generation and zero-action
   candidate rejection.
2. Implement the `memory_local_active` mode behind a CLI flag without replacing
   existing `navmesh_frontier`.
3. Run selected `sofa`, `tv_monitor`, and `toilet` relocation replays before
   another balanced6 matrix.

## 2026-05-30 Memory-Conditioned Local Active Search Implementation

Implemented locally:

- `--post-memory-search-mode memory_local_active` changes only the post-memory
  repair route. Query-start frontier remains controlled by `--frontier-mode`.
- `--post-memory-search-mode frontier_mode` is the default and preserves prior
  behavior.
- Local active search generates deterministic radial probes around the memory
  anchor, labels them as `memory_local_active_probe:*`, and executes them
  through the same route follower and detector-confirmation code path as
  `navmesh_frontier`.
- Expected-utility selection now rejects unavailable zero-action post-memory
  repair routes as free options.

Local verification:

```bash
python3 -m pytest \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q

python3 -m py_compile \
  src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py

git diff --check
```

Focused Linux replay template:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/<run_name> \
  --target-categories sofa,tv_monitor,chair,toilet \
  --selected-group-ids '<comma-separated selected relocation group ids>' \
  --sensor-width 640 \
  --sensor-height 360 \
  --challenge goal_object_relocation \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode event_posterior \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 3 \
  --frontier-probe-heading-count 2 \
  --post-memory-search-mode memory_local_active \
  --local-search-radii-m 1.0,2.0,4.0 \
  --local-search-probe-count 8 \
  --local-search-heading-count 4 \
  --local-search-score-mode distance_prior \
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

Priority rows:

- `hm3d/val/00820-mL8ThkuaVTM/mL8ThkuaVTM.basis.glb|sofa|relocated:goal_object:220->goal_object:341`
- the high-budget `tv_monitor` relocation row that previously needed `684`
  memory-guided actions;
- the reverse `chair` relocation row that recovered in `190` actions;
- the `toilet` relocation row that still failed after `8x4` probes.

Risk:

- The first implementation is not yet a learned active-search policy and does
  not persist the full candidate-score trace. Treat it as the first Habitat
  testbed for memory-conditioned search, not as a paper result until selected
  and balanced6 replays prove a material improvement.

## 2026-05-30 Official Habitat Measure Alignment Gap

User-raised issue:

- Current lifecycle/closed-loop replay tests do not use official Habitat-Lab
  measures, so their success/action tables cannot be reported as official
  SR/SPL or compared directly with SOTA ObjectNav papers.

Current environment check on Linux:

- Habitat-Lab version: `0.3.3`
- `habitat_baselines`: not installed
- Registered relevant measures include:
  - `Success`
  - `SPL`
  - `SoftSPL`
  - `DistanceToGoal`
  - `DistanceToGoalReward`

New design doc:

- `docs/design/2026-05-30-official-habitat-objectnav-measure-alignment.md`

Recommended next implementation:

1. Add an official-eval preflight CLI that imports Habitat-Lab, loads official
   ObjectNav episode metadata, verifies scene availability, lists configured
   measures, and writes a protocol manifest.
2. Run one `val_mini` episode with a trivial policy and verify metrics come
   from `env.get_metrics()`.
3. Port `frontier_only` and `dual_anchor_memory` into that official action loop.
4. Keep lifecycle relocation results separate from official single-episode
   ObjectNav SR/SPL in paper tables.

## 2026-05-30 Official Habitat Measure Adapter First Slice

Implemented locally and synced to Linux:

- Module:
  `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- CLI:
  `python -m objectnav_core.cli.run_habitat_official_objectnav_eval`
- Tests:
  `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
  and `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- Plan:
  `docs/superpowers/plans/2026-05-30-official-habitat-objectnav-measure-adapter.md`
- Experiment report:
  `docs/experiments/2026-05-30-habitat-official-objectnav-measure-adapter-smoke.md`

What it does:

- Writes `protocol_manifest.json`, `summary.json`, and `episodes.csv`.
- Supports `--preflight-only` and `--validate-habitat`.
- Supports trivial `noop` and deterministic `random` policies for protocol
  smoke testing.
- Stores official metrics under `habitat_official`.
- Aggregates official metrics only from `habitat.Env.get_metrics()`.
- Marks trivial-policy runs as invalid for benchmark claims.

Verification already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q

python -m py_compile \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py
```

Linux conda `habitat` verification:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

Result: `5` passed.

Habitat artifacts:

- `runs/habitat_official_objectnav/preflight_valmini_20260530_v1`
- `runs/habitat_official_objectnav/noop_valmini_1ep_20260530_v1`
- `runs/habitat_official_objectnav/random_valmini_1ep_5steps_20260530_v1`

Observed official metrics:

- `noop`: `success=0.0`, `spl=0.0`, `soft_spl=0.0`,
  `distance_to_goal=8.412616729736328`.
- `random` with `5` max steps: `success=0.0`, `spl=0.0`,
  `soft_spl=0.0007339080957522448`,
  `distance_to_goal=8.406442642211914`.

Important limitation:

- This is official metric plumbing, not a competitive policy result. The next
  research step is to port a fair target-agnostic `frontier_only` policy into
  this official step loop, then port `dual_anchor_memory` without using
  GreedyGeodesic route shortcuts, teleportation, or target-pose oracle actions.

## 2026-05-30 Official Frontier Baseline First Slice

Implemented after the official metric adapter:

- `--policy frontier_only` in
  `python -m objectnav_core.cli.run_habitat_official_objectnav_eval`.
- The official loop is now observation-reactive. Policies receive the current
  observation each step and choose one Habitat action.
- `frontier_only` uses only depth:
  - move forward when center depth is clear;
  - keep turning left when blocked;
  - stop on the final budgeted step.
- It does not use target pose, a route follower, semantic oracle visibility,
  detector-positive shortcuts, or teleportation.

Debug findings:

- Habitat official depth observations are normalized to `0.0..1.0`; the first
  implementation assumed meter-scale depth and spun in place.
- Alternating left/right turns caused blocked episodes to oscillate in place.
- Both cases now have regression tests.

Linux verification:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

Result: `10` passed.

Official Habitat smoke:

- `runs/habitat_official_objectnav/frontier_only_valmini_3ep_200steps_turnfix_20260530_v1`
- Result: `0/3` success, `0.0` SPL,
  `0.0013203695130148407` SoftSPL,
  mean distance-to-goal `6.915587266286214`.

Interpretation:

- This is a real official-loop no-memory baseline scaffold, but it is not a
  strong exploration policy.
- Do not compare memory against this as a serious SOTA baseline. The immediate
  next research step is an occupancy/depth frontier mapper or learned
  exploration policy in the same official action loop.

## 2026-05-30 Official Occupancy Frontier Baseline First Slice

Implemented after the depth-reactive frontier scaffold:

- `--policy occupancy_frontier` in
  `python -m objectnav_core.cli.run_habitat_official_objectnav_eval`.
- A small target-agnostic occupancy grid updated from official `depth`, `gps`,
  and `compass` observations.
- Free-space ray marking, finite-depth obstacle marking, unknown-adjacent-free
  frontier counting, and selected frontier bearing telemetry.
- A four-step blocked-turn burst. This was added after an official smoke showed
  frame-by-frame frontier replanning could still alternate left/right while
  blocked.
- Per-episode `policy_debug.occupancy_frontier` counts for free, occupied,
  unknown, and frontier cells.

Important boundary:

- This policy still does not use target pose, route followers, semantic oracle
  visibility, detector positives, Habitat pathfinder shortcuts, or
  teleportation.
- It is a map-backed official-loop scaffold, not a final paper baseline.

Verification already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

Result after the latest local turn-burst update: `16` passed.

Linux conda `habitat` verification after syncing the turn-burst update also
produced `16` focused tests passed.

Official Habitat smoke:

- `runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_turn_burst_20260530_v4`
- Result: `0/3` success, `0.0` SPL,
  `0.04420002662118805` SoftSPL,
  mean distance-to-goal `6.509775956471761`.
- Negative debug artifact:
  `runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_turn_latch_20260530_v3`
  removed immediate turn alternation but over-rotated and regressed SoftSPL to
  `0.0013203695130148407`.

Interpretation:

- The map-backed scaffold improves SoftSPL over the depth-reactive
  `frontier_only` smoke, but still solves none of the three episodes.
- The next research step is not to claim this as a baseline win. Add
  detector-backed stop decisions, then connect Dual-Anchor memory as a bias
  over the same occupancy/frontier substrate.

## 2026-05-30 Official Memory-Prior Policy First Slice

Implemented after the official occupancy frontier scaffold:

- `--policy memory_guided_frontier` in
  `python -m objectnav_core.cli.run_habitat_official_objectnav_eval`.
- JSON memory prior parser with anchors containing `object_category`, optional
  `scene_id`, `x_m`, `z_m`, `confidence`, and `source`.
- Official action policy that:
  - selects a matching memory by category/scene/confidence;
  - stops inside `--memory-stop-radius-m`;
  - turns toward the remembered bearing when misaligned;
  - moves forward when aligned and depth is clear;
  - falls back to `occupancy_frontier` when memory is missing or blocked.
- Debug telemetry under `policy_debug.memory_prior`.

Important boundary:

- This is memory-prior plumbing, not a benchmark result.
- Synthetic or hand-authored priors are marked with
  `invalid_for_benchmark_claim_reason=memory_prior_source_not_benchmark_validated`.
- The policy still needs a documented non-oracle discovery process and
  detector-backed target verification before paper-facing comparisons.

Verification already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q
```

Local result: `26` passed.

Linux conda `habitat` result after syncing the official memory-prior slice:
`26` focused tests passed.

Official Habitat smoke:

- `runs/habitat_official_objectnav/memory_guided_frontier_synthetic_prior_1ep_20260530_v1`
- Result: `1` action (`stop`), `0.0` success, `0.0` SPL,
  `0.0` SoftSPL, distance-to-goal `8.412616729736328`.
- The memory debug payload selected
  `synthetic_start_anchor:not_benchmark_valid` at `range_m=0.0` and recorded
  `decision=stop_at_memory`.

Next step:

- Create a non-oracle memory-prior generator from previous discovery/detector
  traces, then rerun `memory_guided_frontier` against `occupancy_frontier` under
  official Habitat metrics.

## 2026-05-30 Selected Memory-Local Active Replay Result

Experiment report:

- `docs/experiments/2026-05-30-habitat-memory-local-active-selected-replay.md`

Artifacts:

- `runs/habitat_closed_loop_dual_anchor/event_posterior_relocation_selected_memory_local_active_per_action_accounting_fix_20260530_v1/summary.json`
- `runs/habitat_closed_loop_dual_anchor/event_posterior_relocation_selected_navmesh_per_action_accounting_fix_20260530_v1/summary.json`

Matched selected-row result:

| Post-memory search | Memory-guided success | Memory-guided actions | Frontier-only success | Frontier-only actions |
|---|---:|---:|---:|---:|
| `navmesh_frontier` via `frontier_mode` | `1/4` | `1195` | `0/4` | `1312` |
| `memory_local_active` | `0/4` | `767` | `0/4` | `1312` |

Interpretation:

- Deterministic radial local-active search is not a paper-worthy improvement.
- It is cheaper on failed rows, but it regresses the relocated `sofa` row that
  navmesh post-memory search repairs.
- Do not scale this exact policy to a broader matrix as a claimed improvement.
- The next local-search version should use occupancy/depth visibility or a
  learned candidate scorer with candidate trace logging.

Additional accounting note:

- Commit `74e63ab` fixed failed post-memory repair accounting. Old failed-row
  action totals before this commit undercount attempted post-memory search.

## 2026-05-30 Official Lifecycle Memory Prior Export And Frame Guard

Current state:

- The official evaluator now has a real lifecycle-memory export path:
  `python -m objectnav_core.cli.export_lifecycle_memory_prior`.
- The exporter reads lifecycle SQLite memory DBs in read-only mode, joins
  `object_instance_anchors` with optional `usability_beliefs`, and writes the
  official memory-prior JSON shape.
- Exported lifecycle anchors default to `coordinate_frame="habitat_world"`.
- The official selector only acts on `episode_start_relative` anchors by
  default. This is intentional: lifecycle anchors are Habitat world-frame
  coordinates, while official ObjectNav `gps` observations are relative to the
  episode start.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/lifecycle_memory_prior_export.py`
- `src/objectnav_core/objectnav_core/cli/export_lifecycle_memory_prior.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_lifecycle_memory_prior_export.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-lifecycle-memory-prior-export.md`
- `docs/experiments/2026-05-30-lifecycle-memory-prior-export-frame-guard.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check

ssh badger-linux 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q'

ssh badger-linux 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_lifecycle_memory_prior \
    --memory-db runs/habitat_usability/habitat_memory_lifecycle_val_grounding_dino_detector_anchor_matrix_v1/lifecycle_memory.sqlite \
    --output runs/habitat_official_objectnav/lifecycle_memory_prior_export_grounding_dino_detector_anchor_matrix_20260530_v1/official_memory_prior.json \
    --source-tag lifecycle_grounding_dino_detector_anchor_matrix \
    --min-confidence 0.5 \
    --dataset-version objectnav_hm3d_v1/val_mini'
```

Verification:

- Local focused exporter/official tests: `31` passed.
- Local full test suite: `322` passed.
- Local `compileall` returned cleanly.
- Local `git diff --check` returned cleanly.
- Linux focused exporter/official tests in conda env `habitat`: `31` passed.
- Real export artifact:
  `runs/habitat_official_objectnav/lifecycle_memory_prior_export_grounding_dino_detector_anchor_matrix_20260530_v1/official_memory_prior.json`.
  It contains `12` anchors, all `habitat_world`, with confidence `0.903168`.
- Official guard smoke:
  `runs/habitat_official_objectnav/memory_guided_frontier_world_prior_guard_1ep_20260530_v1`.
  The policy loaded `12` candidates, recorded
  `fallback_reason=no_matching_memory`, and used Habitat-provided metrics.

Known risks:

- The exported lifecycle memory prior is a bridge artifact, not an actionable
  official memory input. Do not run it as a claimed memory baseline until a
  frame bridge exists.
- The confidence calculation is a simple belief product. It is useful for
  filtering but not yet a learned validity model.
- The official policy still lacks detector-backed stop confirmation, so even
  actionable priors would need target verification before strong claims.

Next recommended step:

1. Design and implement a fair way to produce `episode_start_relative` memory
   anchors: either a documented Habitat world-to-episode transform or direct
   logging from the official observation stream.
2. Add detector-backed stop/confirmation in the official action loop.
3. Only then compare `memory_guided_frontier` against `occupancy_frontier`
   under official Habitat metrics.

## 2026-05-30 Official GPS/Compass Frame Correction

Current state:

- The official adapter now maps Habitat 2D GPS from `[forward, right]` into the
  internal policy frame `(x=right, z=forward)`.
- The official adapter now negates raw Habitat compass so internal positive
  heading means a rightward turn.
- This fixes the observation boundary used by both `memory_guided_frontier`
  and `occupancy_frontier`.

Root-cause evidence:

- Live Linux Habitat probe:
  - start GPS approximately `[0.0, 0.0]`;
  - after one `move_forward`, GPS approximately `[0.0444, 0.0]`;
  - after one `turn_right`, compass approximately `-0.5236`.
- Habitat-Lab source for `EpisodicGPSSensor` returns
  `[-agent_position[2], agent_position[0]]`.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-gps-compass-frame-correction.md`
- `docs/experiments/2026-05-30-habitat-official-gps-compass-frame-correction.md`

Verification so far:

- RED local regression tests failed before the fix with the expected wrong
  actions.
- GREEN local regression tests passed after the fix.
- Local focused official/exporter tests: `33` passed.
- Linux focused official/exporter tests in conda env `habitat`: `33` passed.
- Official forward-anchor smoke:
  `runs/habitat_official_objectnav/memory_guided_frontier_episode_frame_forward_probe_1ep_20260530_v1`.
  It emitted five `move_forward` actions then `stop`, with near-zero memory
  bearing error.
- Corrected occupancy-frontier rerun:
  `runs/habitat_official_objectnav/occupancy_frontier_valmini_3ep_200steps_framefix_20260530_v5`.
  It produced `0/3` success, SPL `0.0`, SoftSPL
  `0.044200068701652974`, and mean distance-to-goal
  `6.509775638580322`.

Known risks:

- The older official `occupancy_frontier` smoke metrics were produced before
  this frame fix. Treat them as historical diagnostics; use
  `occupancy_frontier_valmini_3ep_200steps_framefix_20260530_v5` as the current
  scaffold artifact.
- The frame correction does not solve the lifecycle world-to-episode transform.
  `habitat_world` exports should remain rejected by default.

Next recommended step:

1. Continue to the actionable-memory bridge using the corrected
   `episode_start_relative` convention.

## 2026-05-30 Official Episode Detection Memory Anchor Projection

Current state:

- Added `objectnav_core.evaluation.official_episode_memory`.
- `estimate_episode_detection_anchor(...)` converts an official observation
  plus detector bbox into an `OfficialMemoryAnchor` in
  `coordinate_frame="episode_start_relative"`.
- `make_official_memory_prior_payload(...)` serializes projected anchors into
  the official prior JSON shape.

What it uses:

- official `depth`;
- official `gps`, interpreted through the corrected `[forward, right]` mapping;
- official `compass`, negated into positive-right internal heading;
- detector bbox center and median positive finite depth patch;
- no target pose, semantic oracle, pathfinder, route follower, or lifecycle
  world-frame transform.

Verification:

- RED test run failed with missing module
  `objectnav_core.evaluation.official_episode_memory`.
- GREEN focused projection tests: `6` passed locally.
- Local focused official-memory set: `39` passed.
- Local full test suite: `330` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory set in conda env `habitat`: `39` passed.
- Linux `git diff --check` returned cleanly.

Known risks:

- This is a geometry primitive, not yet a full detector-backed memory-discovery
  run. It has not run Grounding DINO/YOLO inside the official evaluator yet.
- Detector labels and boxes still need confidence gating and trace logging
  before paper-facing use.

Next recommended step:

1. Add an official detector-discovery/preflight path that calls
   `estimate_episode_detection_anchor` on real detector outputs and writes a
   memory-prior artifact.
2. Feed that artifact into `memory_guided_frontier` and compare against the
   corrected `occupancy_frontier` scaffold under official metrics.

## 2026-05-30 Official Detector Memory Discovery Loop

Current state:

- Added `objectnav_core.evaluation.habitat_official_memory_discovery`.
- `run_habitat_official_memory_discovery(...)` runs a Habitat-like official
  observation loop, calls an injected detector adapter, filters detections by
  target category/confidence, projects detections into episode-relative
  anchors, and writes:
  - `memory_prior.json`;
  - `summary.json`;
  - `detections.csv`.
- The generated memory-prior payload uses
  `coordinate_frame="episode_start_relative"` and is loadable by the existing
  official memory-prior parser.
- The per-episode anchor cap now keeps the highest-confidence projected
  candidates, not simply the first detections returned by the adapter.

What it uses:

- official `rgb` for detector input;
- official `depth/gps/compass` for projection through
  `estimate_episode_detection_anchor`;
- current episode `object_category` and `scene_id` for filtering and policy
  compatibility;
- an injected detector adapter with `detect(rgb) -> list[Detection]`.

Verification:

- RED module test failed with missing
  `objectnav_core.evaluation.habitat_official_memory_discovery`.
- RED confidence-cap regression failed before the fix with exported confidence
  `0.2` instead of `0.9`.
- GREEN discovery tests: `5` passed locally.
- Local focused official-memory set: `44` passed.
- Local full test suite: `335` passed.
- Local `compileall` returned cleanly.
- Local `git diff --check` returned cleanly.
- Linux focused official-memory set in conda env `habitat`: `44` passed.
- Linux `git diff --check` returned cleanly.

Known risks:

- This is still detector-injected core-loop plumbing, not a real Grounding DINO
  or YOLO-World official discovery/query benchmark.
- The generated prior can be consumed by `memory_guided_frontier`, but the
  policy still stops based on memory radius rather than detector-confirmed
  target visibility.
- No benchmark-facing claim should be made until discovery and query episodes
  are split and evaluated under official Habitat metrics.

Next recommended step:

1. Add a discovery CLI or model factory for the existing Grounding DINO /
   YOLO-World adapters.
2. Run a tiny real-detector official discovery/query smoke and save the
   generated artifacts.
3. Compare `memory_guided_frontier` against corrected `occupancy_frontier` only
   once the memory source and query protocol are documented.

## 2026-05-30 Official Detector Memory Discovery CLI And YOLO Smoke

Current state:

- Added `objectnav_core.cli.run_habitat_official_memory_discovery`.
- Added console script `objectnav_habitat_official_memory_discovery`.
- The CLI can build `YoloWorldDetector` or `GroundingDinoDetector`, parse
  categories and detector thresholds, run the official discovery core, and
  print the summary JSON.
- Linux conda env `habitat` has the required live-smoke dependencies:
  `habitat`, `ultralytics`, `transformers`, and `torch`.

Files touched:

- `src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_discovery.py`
- `src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `src/objectnav_core/setup.py`
- `docs/design/2026-05-30-official-detector-memory-discovery-cli.md`
- `docs/experiments/2026-05-30-official-detector-memory-discovery-cli-yolo-smoke.md`

Verification:

- RED CLI/packaging test failed with missing module
  `objectnav_core.cli.run_habitat_official_memory_discovery`.
- GREEN CLI/packaging tests: `5` passed locally.
- Local focused CLI/official-memory/packaging set: `49` passed.
- Local full test suite: `339` passed.
- Local `compileall` returned cleanly.
- Local `git diff --check` returned cleanly.
- Linux focused CLI/official-memory/packaging set in conda env `habitat`:
  `49` passed.
- Linux `git diff --check` returned cleanly.

Live smoke artifacts:

- Discovery, one episode / 20 steps:
  `runs/habitat_official_objectnav/discovery_yolo_world_valmini_1ep_20steps_20260530_v1`.
  It ran successfully but exported `0` anchors because the first target was
  `chair` and the probed first frame detected `bed`.
- Discovery, four episodes / 50 steps:
  `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1`.
  It processed `200` observations and `189` detections, then exported `8`
  `episode_start_relative` `tv_monitor` anchors.
- Query with generated prior:
  `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_4ep_50steps_20260530_v1`.
  The policy selected the generated YOLO prior in the matching `tv_monitor`
  episode and recorded `decision=turn_toward_memory`.
- Same-budget no-memory context:
  `runs/habitat_official_objectnav/occupancy_frontier_valmini_4ep_50steps_20260530_v1`.

Known risks:

- The generated-prior policy result is negative: `memory_guided_frontier`
  produced `0/4` success, SPL `0.0`, and SoftSPL
  `0.0009902771347611306`; same-budget `occupancy_frontier` produced `0/4`
  success, SPL `0.0`, and SoftSPL `0.03315005152623973`.
- Discovery trace CSV currently records exported anchors, not all filtered
  detector labels. The one-episode smoke needed a separate probe to explain
  why all target detections were filtered.
- The memory policy can consume generated priors, but nearest-anchor steering
  can degrade exploration when the memory is off-bearing, duplicated, or lacks
  detector-confirmed target visibility.

Next recommended step:

1. Add detector-backed stop confirmation to the official policy.
2. Extend discovery traces to log all detections and filter reasons.
3. Add memory deduplication/fusion before using generated priors in broader
   official benchmark comparisons.

## 2026-05-30 Official Detector-Confirmed Memory Stop

Current state:

- Added an optional detector-confirmed STOP hook to
  `memory_guided_frontier` inside the official Habitat ObjectNav evaluator.
- The hook only uses current official `rgb`, an injected detector adapter, the
  current episode target category, and a confidence threshold.
- Matching detector output records `policy_debug.memory_prior.decision` as
  `stop_on_detector`; wrong-category or low-confidence detector outputs leave
  existing memory behavior unchanged.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-detector-confirmed-memory-stop.md`
- `docs/experiments/2026-05-30-official-detector-confirmed-memory-stop-yolo-query-smoke.md`

Verification:

- Detector-confirmed STOP tests: `3` passed locally.
- Local focused official-memory set: `51` passed.
- Local full test suite: `342` passed.
- Local `compileall` returned cleanly.
- Local `git diff --check` returned cleanly.
- Linux focused official-memory set in conda env `habitat`: `51` passed.
- Linux `git diff --check` returned cleanly.

Live smoke artifacts:

- Query with generated YOLO prior plus injected YOLO detector:
  `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_stop_4ep_50steps_20260530_v1`.
- Traced rerun with detector call sidecar:
  `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_stop_trace_4ep_50steps_20260530_v1`.

Live smoke result:

- Official success: `0/4`.
- Official SPL: `0.0`.
- Official SoftSPL: `0.0009902771347611306`.
- Detector calls in trace: `196`.
- Target-match detector calls: `0`.
- Target-match detections: `0`.
- `stop_on_detector` did not fire in the live smoke because YOLO never emitted
  the current target category on the query frames.

Known risks:

- The detector STOP interface is necessary but not sufficient. The live policy
  still fails because nearest-anchor steering does not reliably bring the
  target into view.
- Query detector tracing is currently ad hoc; future runs need reusable trace
  logging in the evaluator or CLI.
- No benchmark-facing improvement should be claimed from this slice.

Next recommended step:

1. Add reusable query-time detector trace logging.
2. Build a stronger memory-conditioned local active search policy around
   remembered anchors, using detector evidence as online feedback.
3. Add memory fusion/deduplication before broad official comparisons.

## 2026-05-30 Official Query Detector Trace Artifacts

Current state:

- Added built-in query detector trace collection to the official ObjectNav
  evaluator.
- Detector-backed `run_habitat_official_objectnav_eval` calls now write
  `detector_trace.json` by default and include trace counts in
  `summary["detector_trace"]`.
- No-detector runs remain unchanged and do not emit the trace artifact.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-query-detector-trace.md`
- `docs/superpowers/plans/2026-05-30-official-query-detector-trace.md`

Verification:

- RED trace-artifact test failed on missing `detector_trace.json`.
- GREEN trace-artifact and no-detector guard tests: `2` passed.
- Nonmatching-detection trace guard: `1` passed.
- Local official evaluator tests: `32` passed.
- Local focused official-memory/exporter set: `54` passed.
- Local `compileall` returned cleanly.
- Local `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set in conda env `habitat`: `54`
  passed.
- Linux `compileall` returned cleanly.
- Linux `git diff --check` returned cleanly.
- Linux built-in trace YOLO query smoke wrote
  `runs/habitat_official_objectnav/memory_guided_frontier_yolo_discovery_prior_detector_trace_builtin_4ep_50steps_20260530_v1`.

Known risks:

- This is diagnostic infrastructure, not an algorithmic benchmark gain.
- The built-in trace smoke reproduced the negative detector evidence profile:
  `196` detector calls, `234` detections, `0` target-match calls, `0`
  target-match detections, and official success `0/4`.

Next recommended step:

1. Begin the stronger memory-conditioned active search policy.
2. Use built-in detector traces as the evidence signal for whether search near
   memory anchors actually increases target-view detections.
3. Add memory fusion/deduplication before broad official comparisons.

## 2026-05-30 Official Memory-Belief Frontier Policy

Current state:

- Added `memory_belief_frontier` to the official Habitat ObjectNav evaluator.
- It scores occupancy frontiers by memory-induced target belief around the
  selected anchor and a small travel-distance penalty.
- It keeps detector-confirmed STOP ahead of frontier scoring and writes
  built-in detector traces when an injected detector is used.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-memory-belief-frontier-policy.md`
- `docs/experiments/2026-05-30-official-memory-belief-frontier-yolo-query-smoke.md`
- `docs/superpowers/plans/2026-05-30-official-memory-belief-frontier-policy.md`

Verification:

- Local official evaluator tests: `36` passed.
- Local focused official-memory/exporter set: `58` passed.
- Local `compileall` returned cleanly.
- Local `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set in conda env `habitat`: `58`
  passed.
- Linux `compileall` returned cleanly.
- Linux `git diff --check` returned cleanly.

Live smoke artifact:

- `runs/habitat_official_objectnav/memory_belief_frontier_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Live smoke result:

- Official success: `0/4`.
- Official SPL: `0.0`.
- Official SoftSPL: `0.0009902771347611306`.
- Built-in detector trace: `152` calls, `81` detections, `1` target-match
  detection.
- The policy reached `stop_on_detector` on the `tv_monitor` episode, but
  Habitat still scored failure.

Known risks:

- This is not a benchmark improvement.
- The current detector STOP condition is too permissive for official success;
  a label match may occur before the agent is close enough.
- Memory belief currently uses one selected anchor, not fused multi-anchor or
  learned validity estimates.

Next recommended step:

1. Add detector-guided approach/centering before STOP.
2. Use depth inside the detector bbox to decide whether STOP is plausible.
3. Then re-run the same four-episode diagnostic and compare official metrics
   plus target-match traces.

## 2026-05-30 Official Detector-Guided Memory Approach

Current state:

- `memory_belief_frontier` now treats current target detections as local
  control evidence before STOP.
- Off-center bbox detections emit `center_detector_target`.
- Centered far detections emit `approach_detector_target` when the forward
  depth corridor is clear.
- STOP now requires centered bbox, minimum bbox area, and close bbox depth,
  recorded as `stop_on_detector_range_confirmed`.
- `memory_guided_frontier` still keeps the older immediate
  `stop_on_detector` behavior.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-detector-guided-memory-approach.md`
- `docs/experiments/2026-05-30-official-detector-guided-memory-approach-yolo-query-smoke.md`
- `docs/superpowers/plans/2026-05-30-official-detector-guided-memory-approach.md`

Verification:

- RED local tests failed for the expected immediate-STOP behavior.
- Targeted GREEN tests passed for centering, approach, range-confirmed STOP,
  and `memory_guided_frontier` compatibility.
- Local official evaluator tests: `38` passed.
- Local focused official-memory/exporter set: `60` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set in conda env `habitat`: `60`
  passed.
- Linux `compileall` and `git diff --check` returned cleanly.

Live smoke artifact:

- `runs/habitat_official_objectnav/memory_belief_frontier_detector_guided_approach_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Live smoke result:

- Official success: `0/4`.
- Official SPL: `0.0`.
- Official SoftSPL: `0.0009902771347611306`.
- Detector trace: `196` calls, `257` detections, `23` target-match calls, `23`
  target-match detections.
- Target episode final detector-control debug:
  `decision=center_detector_target`, bbox `[553, 68, 640, 173]`, center
  offset `0.43203125`, normalized depth median `0.40283340215682983`, bbox
  area fraction `0.029736328125`.

Known risks:

- This is still not a benchmark gain. The policy increased target-view
  detector evidence but did not improve official Habitat success/SPL.
- Only the final episode policy debug is persisted in `episodes.csv`/summary;
  step-level policy decision tracing is needed to diagnose oscillation and
  approach behavior.
- The detector gate uses conservative constants rather than learned evidence
  accumulation. Treat it as a diagnostic bridge, not the final paper algorithm.

Next recommended step:

1. Add step-level policy decision tracing for official query runs.
2. Build a persistent detector-evidence/local-servo state that can center,
   approach, and stop without oscillating on single-frame detections.
3. Add memory fusion/deduplication before broader official comparisons.

## 2026-05-30 Official Policy Step Trace

Current state:

- Full official eval calls now write `policy_trace.json` by default.
- The trace records one compact row per selected action with episode metadata,
  step index, action, decision, corrected `x_m/z_m/heading_rad`, memory debug,
  and occupancy-frontier summary.
- `write_policy_trace=False` suppresses the artifact.
- Budget STOP is recorded as `budget_stop`, avoiding stale previous-step
  detector debug.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-policy-step-trace.md`
- `docs/experiments/2026-05-30-official-policy-step-trace-yolo-query-smoke.md`
- `docs/superpowers/plans/2026-05-30-official-policy-step-trace.md`

Verification:

- RED trace tests failed with missing artifact/parameter.
- Local official evaluator tests: `40` passed.
- Local focused official-memory/exporter set: `62` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set in conda env `habitat`: `62`
  passed.
- Linux `compileall` and `git diff --check` returned cleanly.

Live smoke artifact:

- `runs/habitat_official_objectnav/memory_belief_frontier_policy_trace_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Live smoke result:

- Official success: `0/4`.
- Official SPL: `0.0`.
- Official SoftSPL: `0.0009902771347611306`.
- Detector trace: `196` calls, `257` detections, `23` target-match detections.
- Policy trace: `200` steps; `170` fallback occupancy decisions, `23`
  detector-centering decisions, `3` memory-belief turns, `4` budget stops.
- Root cause for the target episode is now explicit:
  `center_detector_target`/`turn_right` on even steps alternates with
  `fallback_occupancy_frontier`/`turn_left` on odd steps.

Known risks:

- This trace does not improve policy behavior by itself.
- The current local detector controller has no state across one-frame target
  dropouts, so fallback can reverse detector centering immediately.
- The trace is compact but enabled by default; broad benchmark runs may need
  `write_policy_trace=False` or artifact compression.

Next recommended step:

1. Add persistent detector-local-control state with last target offset and
   evidence age.
2. Prevent blocked fallback from immediately reversing the last detector
   centering action.
3. Rerun the same diagnostic and compare policy-trace decision counts before
   touching larger benchmarks.

## 2026-05-30 Adaptive Detector Servo Negative Result

Current state:

- Added detector center-direction state to `memory_belief_frontier`.
- Immediate target loss after detector centering now triggers one
  `reacquire_detector_target` action and flips the center-direction sign.
- The implementation is verified but did not improve the live diagnostic.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-adaptive-detector-servo.md`
- `docs/experiments/2026-05-30-official-adaptive-detector-servo-yolo-query-smoke.md`
- `docs/superpowers/plans/2026-05-30-official-adaptive-detector-servo.md`

Verification:

- RED adaptive-servo test failed before the stateful reacquire path.
- Local official evaluator tests: `41` passed.
- Local focused official-memory/exporter set: `63` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set in conda env `habitat`: `63`
  passed.
- Linux `compileall` and `git diff --check` returned cleanly.

Live smoke artifact:

- `runs/habitat_official_objectnav/memory_belief_frontier_adaptive_servo_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Live smoke result:

- Official success: `0/4`.
- Official SPL: `0.0`.
- Official SoftSPL: `0.0009902771347611306`.
- Detector trace: `196` calls, `224` detections, `23` target-match detections.
- Policy trace: `23` `center_detector_target`, `22`
  `reacquire_detector_target`, `148` fallback, `3` memory-belief turns, `4`
  budget stops.
- The action-count distribution stayed unchanged from the previous trace run:
  `move_forward=49`, `turn_left=87`, `turn_right=60`, `stop=4`.

Known risks:

- The active policy now includes a verified but non-improving one-step servo
  heuristic. Treat it as a diagnostic bridge, not a publishable algorithm.
- More single-step rules are unlikely to be enough. The evidence points toward
  multi-frame local search or learned visual servoing.

Next recommended step:

1. Decide whether to keep the adaptive servo enabled as diagnostic scaffolding
   or gate it behind a policy variant.
2. Design a multi-frame detector-evidence controller that owns local search
   for several steps after target evidence, with explicit search state and
   termination criteria.
3. Use accumulated `detector_trace.json` + `policy_trace.json` as the dataset
   for learned local-control ablations.

## 2026-05-30 Detector Centering Sign Ablation

Current state:

- Added a configurable detector-centering sign to the official ObjectNav
  evaluator and CLI:
  `detector_center_direction_sign` / `--detector-center-direction-sign`.
- Default sign remains `1`, preserving existing behavior.
- Sign `-1` is available only as an explicit diagnostic ablation.
- `protocol_manifest.json` records
  `detector_control.center_direction_sign`, and `summary.json` records the
  run config sign.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- `docs/design/2026-05-30-official-detector-centering-sign-ablation.md`
- `docs/experiments/2026-05-30-official-detector-centering-sign-ablation-yolo-query-smoke.md`

Verification:

- Targeted RED/GREEN tests: `2` passed.
- Local official evaluator/CLI tests: `47` passed.
- Local focused official-memory/exporter set: `66` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set in conda env `habitat`: `66`
  passed.
- Linux `compileall` and `git diff --check` returned cleanly.

Live smoke artifact:

- `runs/habitat_official_objectnav/memory_belief_frontier_inverted_center_sign_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Live smoke result:

- Official success: `0/4`.
- Official SPL: `0.0`.
- Official SoftSPL: `0.0009902771347611306`.
- Detector trace: `196` calls, `224` detections, `23` target-match detections.
- Policy trace: `23` `center_detector_target`, `22`
  `reacquire_detector_target`, `148` fallback, `3` memory-belief turns, `4`
  budget stops.
- Compared with the adaptive-servo run, the first target-control action
  flipped from `turn_right` to `turn_left`, but the loop persisted around the
  same headings. This is negative evidence for a simple visual-centering sign
  bug.

Known risks:

- The active policy still contains a verified but non-improving one-step servo
  heuristic.
- The sign ablation knob is useful for reproducibility, but it is not a paper
  contribution and did not improve official metrics.

Next recommended step:

1. Pivot to a multi-frame detector evidence controller or learned local visual
   servo.
2. Use `policy_trace.json` to score short action sequences around target
   evidence instead of flipping individual turns.
3. Keep all benchmark-facing claims tied only to official Habitat metrics.

## 2026-05-30 Detector Action-Effect Local Control

Current state:

- Added a new official policy variant: `memory_evidence_frontier`.
- The policy reuses memory-belief frontier fallback, but detector local control
  now records failed centering action effects.
- If a detector-centering turn immediately loses target evidence and
  reacquisition returns to the same edge-visible target, the policy suppresses
  the failed center action and approaches forward under
  `decision=approach_detector_target_after_center_loss`.
- Previous `memory_belief_frontier` behavior is preserved for ablation
  comparability.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- `docs/design/2026-05-30-official-detector-action-effect-local-control.md`
- `docs/experiments/2026-05-30-official-detector-action-effect-local-control-yolo-query-smoke.md`
- `docs/superpowers/plans/2026-05-30-official-detector-action-effect-local-control.md`

Verification:

- Targeted RED/GREEN tests: `3` passed.
- Local official evaluator tests: `44` passed.
- Local official CLI tests: `6` passed.
- Local focused official-memory/exporter set: `69` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter set in conda env `habitat`: `69`
  passed.
- Linux `compileall` and `git diff --check` returned cleanly.

Live smoke artifact:

- `runs/habitat_official_objectnav/memory_evidence_frontier_action_effect_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Live smoke result:

- Official success: `0/4`.
- Official SPL: `0.0`.
- Official SoftSPL: `0.02518699682786324`.
- Mean distance-to-goal: `5.697803378105164`.
- Detector trace: `196` calls, `276` detections, `4` target-match detections.
- Policy trace: `1` `center_detector_target`, `1`
  `reacquire_detector_target`, `3`
  `approach_detector_target_after_center_loss`, `167` fallback decisions,
  `24` memory-belief turns, `4` budget stops.

Interpretation:

- Partial positive: the pathological target-control loop is largely gone, and
  official SoftSPL/distance-to-goal improved.
- Still not a benchmark success: no episode succeeded and SPL remains zero.
- Target evidence disappeared after three edge-tracking forward steps, so the
  next controller must reason over evidence trends after approach, not only a
  single failed centering action.

Known risks:

- `memory_evidence_frontier` is still a diagnostic bridge, not the final paper
  algorithm.
- The current approach decision is hand-authored from one action-effect event.
  It should be replaced or generalized by a short-horizon local action scorer.

Next recommended step:

1. Add trace fields for local evidence trends: bbox center offset delta, bbox
   area delta, depth median delta, and action outcome.
2. Use those traces to learn or score short action sequences
   (`turn_left`, `turn_right`, `move_forward`) under official observations.
3. Run the same four-episode diagnostic after the scorer, then only scale up if
   official success or distance-to-goal improves materially.

## 2026-05-30 Learned Local Frontier Smoke

Current state:

- Added a new official policy variant:
  `memory_learned_local_frontier`.
- The policy requires `local_action_model_path` and records local-action model
  metadata in the protocol manifest.
- The learned scorer is used only after detector-centering action-effect
  evidence exists.
- Failed detector-turn candidates for the current bbox offset sign are
  suppressed before scoring. This matters: the first online smoke allowed the
  scorer to repeat a known failed turn and recreated the old
  center/reacquire loop.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- `docs/design/2026-05-30-official-learned-local-frontier-policy.md`
- `docs/experiments/2026-05-30-official-learned-local-frontier-yolo-query-smoke.md`
- `docs/superpowers/plans/2026-05-30-official-learned-local-frontier-policy.md`

Verification:

- Local focused official-memory/exporter/model/evaluator gate: `80` passed.
- Local `compileall` and `git diff --check` passed.
- Linux focused official gate in conda env `habitat`: `80` passed.
- Linux `compileall` and `git diff --check` passed.
- Fixed four-episode YOLO official smoke completed.

Artifacts:

- Initial learned-local smoke:
  `runs/habitat_official_objectnav/memory_learned_local_frontier_yolo_discovery_prior_local_action_model_trace_4ep_50steps_20260530_v1`
- Fixed learned-local smoke:
  `runs/habitat_official_objectnav/memory_learned_local_frontier_suppressed_failed_turns_yolo_discovery_prior_local_action_model_trace_4ep_50steps_20260530_v1`

Result:

- Initial learned-local smoke regressed to the old loop:
  success `0/4`, SPL `0.0`, SoftSPL `0.0009902771347611306`, mean
  distance-to-goal `5.880594372749329`, `22`
  `learned_local_action_score` decisions, and `22`
  `reacquire_detector_target` decisions.
- Fixed learned-local smoke recovered the action-effect baseline:
  success `0/4`, SPL `0.0`, SoftSPL `0.02518699682786324`, mean
  distance-to-goal `5.697803378105164`, `4`
  `learned_local_action_score` decisions, and `2`
  `reacquire_detector_target` decisions.
- No official benchmark improvement should be claimed. The current scorer is a
  useful diagnostic bridge, not a publishable controller.

Next recommended step:

1. Build a larger official action-effect corpus, ideally across more episodes
   and with target-visible local-control slices mined explicitly.
2. Add temporal features or sequence labels: bbox offset delta, area delta,
   depth delta, visibility retention/loss, and action history.
3. Replace the one-step next-visibility scorer with a short-horizon local
   controller/value model, still inside the official observation/action
   boundary.

## 2026-05-30 Temporal Local Action-Effect Dataset

Current state:

- Upgraded the official local action-effect exporter to schema
  `official-local-action-effect-v2`.
- The exporter now accepts `history_steps` and `horizon_steps`.
- Features remain online-safe and use only current/past trace evidence:
  previous visibility, recent visible count, action history, detector evidence
  deltas, current depth, and suppressed-turn indicators.
- Future/horizon information is recorded only under labels:
  target visible within horizon, visible at horizon, target lost within horizon,
  first loss delta, and best-future evidence deltas.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_dataset.py`
- `src/objectnav_core/objectnav_core/cli/export_habitat_official_local_action_dataset.py`
- `src/objectnav_core/tests/test_habitat_official_local_action_dataset.py`
- `docs/design/2026-05-30-official-temporal-local-action-effect-dataset.md`
- `docs/experiments/2026-05-30-official-temporal-local-action-effect-dataset-yolo-trace.md`
- `docs/superpowers/plans/2026-05-30-official-temporal-local-action-effect-dataset.md`

Verification:

- Local dataset tests: `5` passed.
- Local focused official-memory/exporter/model/evaluator gate: `81` passed.
- Local `compileall` and `git diff --check` passed.
- Linux focused official gate in conda env `habitat`: `81` passed.
- Linux `compileall` and `git diff --check` passed.
- Linux 20-episode discovery, query, temporal export, and temporal logistic
  model smoke completed.

Artifacts:

- Four-episode temporal dataset:
  `runs/habitat_official_objectnav/local_action_effect_dataset_temporal_learned_local_suppressed_yolo_4ep_50steps_20260530_v1`
- 20-episode discovery:
  `runs/habitat_official_objectnav/discovery_yolo_world_valmini_20ep_80steps_20260530_v1`
- 20-episode query:
  `runs/habitat_official_objectnav/memory_evidence_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260530_v1`
- 20-episode temporal dataset:
  `runs/habitat_official_objectnav/local_action_effect_dataset_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1`
- Temporal logistic model:
  `runs/habitat_official_objectnav/local_action_effect_model_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/model.json`

Result:

- The 20-episode query is not a benchmark win: official success `0/20`, SPL
  `0.0`, SoftSPL `0.02945252626989075`.
- The 20-episode v2 dataset is much less starved than the four-episode smoke:
  `1580` examples, `500` visible-before examples, `498` visible-after
  examples, `454` retained transitions, `46` lost transitions, and `44`
  acquired transitions.
- Offline logistic smoke on the same 20-episode dataset improved from default
  one-frame features to temporal features:
  log loss `0.174072` to `0.059308`, Brier score `0.039334` to `0.011546`.
- This is a data/model diagnostic only. It is useful evidence that temporal
  state matters, not an ObjectNav result.

Next recommended step:

1. Add online temporal local-control state to `memory_learned_local_frontier`
   so runtime candidate scoring receives the same history features as the v2
   dataset.
2. Train a temporal model with a label aligned to local control, such as
   avoiding horizon loss or maximizing short-horizon evidence quality.
3. Compare the resulting online policy against `memory_evidence_frontier` on
   official Habitat metrics before scaling to larger benchmark runs.

## 2026-05-30 Action-Conditioned and Online Temporal Learned Local State

Current state:

- The local action model now supports generated interaction features named
  `left_feature__right_feature`.
- Candidate scoring passes model feature names into the feature builder, so
  action overrides correctly recompute interactions such as
  `action_turn_left__current_abs_center_offset_fraction`.
- A 20-episode interaction temporal model was trained on the Linux mirror:
  `runs/habitat_official_objectnav/local_action_effect_model_interaction_temporal_memory_evidence_yolo_20ep_80steps_20260530_v1/model.json`.
- The online `memory_learned_local_frontier` policy now carries compact
  past-only local-action history and adds v2-compatible temporal features to
  learned-local model examples.
- Learned-local policy traces include `learned_local_temporal_features` so the
  next person can audit what the online model actually saw.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_local_action_model.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-action-conditioned-local-action-scorer.md`
- `docs/design/2026-05-30-official-temporal-learned-local-frontier-policy.md`
- `docs/experiments/2026-05-30-official-action-conditioned-local-action-scorer-yolo-smoke.md`
- `docs/superpowers/plans/2026-05-30-official-action-conditioned-local-action-scorer.md`
- `docs/superpowers/plans/2026-05-30-official-temporal-learned-local-frontier-policy.md`

Verification completed:

- Action-conditioned RED unit test failed before implementation and passed
  after interaction feature generation.
- Online temporal-history RED policy test failed before implementation and
  passed after adding policy-state history.
- Local model tests: `4` passed.
- Local learned-local focused tests: `3` passed.
- Local focused official-memory/exporter/model/evaluator gate: `83` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused official gate for the action-conditioned scorer slice:
  `82` passed.
- Linux `compileall` and `git diff --check` returned cleanly before the
  online temporal-policy slice.

Verification not completed:

- Linux mirror sync for the online temporal-policy slice timed out when
  connecting to `badger@100.88.131.52`.
- No official YOLO online smoke has been run with the temporal interaction
  model.

Offline diagnostic result:

- Default one-frame model on the 20-episode v2 dataset:
  log loss `0.174072`, Brier `0.039334`.
- Additive temporal model:
  log loss `0.059308`, Brier `0.011546`.
- Action-conditioned temporal model:
  log loss `0.054151`, Brier `0.010386`.
- Additive temporal candidate ranking was constant on visible rows
  (`turn_right` for all `500`), while the interaction model produced varied
  rankings (`272` `turn_right`, `150` `turn_left`, `78` `move_forward`).

Risks and assumptions:

- The interaction model is still trained from on-policy traces, so some
  counterfactual action/state pairs are poorly supported.
- Offline next-visible metrics are not official ObjectNav evidence.
- The online temporal policy has only local synthetic verification so far.

Next recommended action:

1. Retry SSH to the Linux mirror.
2. Sync the updated evaluator/test/docs paths.
3. Run the focused official gate in conda env `habitat`.
4. Run a small official YOLO smoke with
   `memory_learned_local_frontier` and the interaction temporal model.
5. Inspect `learned_local_temporal_features` and candidate scores before
   considering any larger run.

## 2026-05-30 Configurable Local Action Training Label

Current state:

- The official local action logistic trainer accepts `label_name`, defaulting
  to `next_target_visible`.
- The CLI accepts `--label`, so future Linux experiments can train on
  `target_visible_at_horizon`, `target_lost_within_horizon`, or other boolean
  v2 labels without code edits.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py`
- `src/objectnav_core/objectnav_core/cli/train_habitat_official_local_action_model.py`
- `src/objectnav_core/tests/test_habitat_official_local_action_model.py`
- `docs/design/2026-05-30-official-local-action-configurable-label.md`
- `docs/superpowers/plans/2026-05-30-official-local-action-configurable-label.md`

Verification completed:

- RED API test failed before `label_name` was implemented.
- RED CLI test failed before `--label` was implemented.
- Local model tests: `6` passed.
- Local focused official-memory/exporter/model/evaluator gate: `85` passed.
- Local `compileall` and `git diff --check` returned cleanly.

Original pending items before the Linux update:

- Linux mirror sync and Linux focused gate.
- Training horizon-label interaction models on the 20-episode v2 dataset.
- Online official YOLO smoke with the temporal interaction model.

Mirror status:

- `tailscale status` shows `badger-linux` / `100.88.131.52` offline, last
  seen about 10 minutes before the check.
- `ping`, `tailscale ping`, TCP port `22`, and verbose SSH all timed out before
  authentication. The provided password is therefore not the limiting factor at
  this point.

## 2026-05-30 Visible-Slice Local Action Training

Current state:

- The official local action trainer accepts `current_visible_only`, defaulting
  to full-dataset training.
- The CLI accepts `--current-visible-only`.
- Model artifacts record source example count, trained example count, and the
  current-visible-only filter setting.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py`
- `src/objectnav_core/objectnav_core/cli/train_habitat_official_local_action_model.py`
- `src/objectnav_core/tests/test_habitat_official_local_action_model.py`
- `docs/design/2026-05-30-official-local-action-visible-slice-training.md`
- `docs/superpowers/plans/2026-05-30-official-local-action-visible-slice-training.md`

Verification completed:

- RED API filter test failed before `current_visible_only` was implemented.
- RED CLI filter test failed before `--current-visible-only` was implemented.
- Local model tests: `8` passed.
- Local focused official-memory/exporter/model/evaluator gate: `87` passed.
- Local `compileall` and `git diff --check` returned cleanly.

Original pending items before the later Linux update:

- Linux mirror sync and Linux focused gate.
- Training visible-only interaction/horizon-label models on the 20-episode v2
  dataset.
- Official online YOLO smoke with the best candidate temporal model.

## 2026-05-30 Official Local Action Candidate Score Report CLI

Current state:

- Added a reproducible offline candidate-ranking report for official local
  action models.
- The pure report function scores each exported local-action example against a
  configurable action set and summarizes best-action counts, observed-action
  counts, label counts, and best-action/observed-action agreement.
- The CLI is available as
  `objectnav_core.cli.score_habitat_official_local_action_model` and the
  console script
  `objectnav_habitat_official_local_action_score`.
- CLI options include `--model`, `--output`, `--csv-output`, `--actions`, and
  `--current-visible-only`.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_local_action_model.py`
- `src/objectnav_core/objectnav_core/cli/score_habitat_official_local_action_model.py`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_habitat_official_local_action_model.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `docs/design/2026-05-30-official-local-action-candidate-score-report.md`

Verification completed:

- RED CLI test failed before the score CLI module existed.
- RED packaging test failed before the console script was registered.
- Local model/report tests: `10` passed.
- Local packaging test: `1` passed.
- Local focused official-memory/exporter/model/evaluator/packaging gate:
  `89` passed.
- Local `compileall` and `git diff --check` returned cleanly.

Original pending items before the Linux update:

- Sync this latest CLI/report slice to the Linux mirror now that the peer is
  reachable again.
- Run the Linux focused gate in conda env `habitat`.
- Use the score CLI on the 20-episode temporal v2 dataset to compare:
  full-trace versus `--current-visible-only`, `next_target_visible` versus
  `target_visible_at_horizon`, and additive versus interaction feature sets.
- Select the best credible diagnostic model for a small official
  `memory_learned_local_frontier` YOLO smoke.

Update:

- Linux sync completed after the peer came back online.
- Linux focused official gate passed: `89` tests.
- Linux compileall and `git diff --check` returned cleanly.
- Offline model comparison artifacts:
  `runs/habitat_official_objectnav/local_action_model_comparison_temporal_yolo_20ep_80steps_20260530_v1`.
- New experiment report:
  `docs/experiments/2026-05-30-official-temporal-learned-local-model-comparison-yolo-smoke.md`.
- The current-visible interaction model had the best common visible-slice
  calibration (`log_loss=0.074327`, `Brier=0.014401`), but its visible-slice
  ranking used only `move_forward` and `turn_right`.
- The full-trace interaction model had lower common visible calibration
  (`log_loss=0.086042`, `Brier=0.017490`) but broader ranking diversity:
  `78` `move_forward`, `149` `turn_left`, `273` `turn_right`.
- Official four-episode YOLO smokes with both interaction models remained
  negative:
  - `interaction_next_target_visible_full`: success `0/4`, SPL `0.0`,
    SoftSPL `0.02518699682786324`, learned-local decisions `4`.
  - `interaction_next_target_visible_visible`: success `0/4`, SPL `0.0`,
    SoftSPL `0.02518699682786324`, learned-local decisions `3`.
- One run at
  `runs/habitat_official_objectnav/memory_learned_local_frontier_interaction_next_full_yolo_discovery_prior_4ep_50steps_20260530_v1`
  is invalid for YOLO conclusions because it used the console CLI, which does
  not inject a detector adapter. The valid smokes have `yolo_detector_trace` in
  their run names and include `detector_trace.json`.

Revised next recommended action:

1. Do not spend more runs tuning the one-step local scorer in isolation.
2. Add a detector-injecting official query CLI or extend the existing eval CLI
   so future YOLO smokes are reproducible from the command line.
3. Start the next algorithmic slice around active perception/search: decide
   when to seek target detector evidence and how to couple memory-belief
   frontiers with detector-evidence acquisition, not just how to pick a
   one-step recovery action after target loss.

## 2026-05-30 Official Query Detector Injection CLI

Current state:

- The official ObjectNav eval CLI now accepts optional query detector
  injection args:
  `--detector {none,yolo_world,grounding_dino}`,
  `--detector-weights`, `--detector-conf`, `--detector-device`,
  `--target-detector-min-confidence`, `--categories`,
  `--grounding-dino-text-threshold`, and
  `--grounding-dino-max-image-side`.
- Default behavior remains `--detector none`.
- Preflight-only runs do not construct detectors.
- Unit tests use fake `detector_factory` and `runner` seams; they do not load
  YOLO, Grounding-DINO, or Habitat.

Files touched:

- `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- `docs/design/2026-05-30-official-query-detector-injection-cli.md`
- `docs/superpowers/plans/2026-05-30-official-query-detector-injection-cli.md`

Verification completed:

- RED detector-injection CLI test failed before `main()` accepted
  `detector_factory`.
- Focused detector-injection CLI test passed.
- Full official ObjectNav CLI tests: `8` passed.
- Local focused official-memory/exporter/model/evaluator/packaging gate:
  `90` passed.
- Local compileall and `git diff --check` returned cleanly.
- Linux focused official-memory/exporter/model/evaluator/packaging gate:
  `90` passed.
- Linux CLI help showed the detector flags.
- Linux compileall and `git diff --check` returned cleanly.

Remaining next action:

- Use this CLI path for the next YOLO query smoke rather than the earlier
  direct Python snippet.

## 2026-05-30 Active-Perception Frontier Rotation-Aware Fix

Current state:

- Added the official policy variant `memory_active_perception_frontier`.
- The first active-perception scorer multiplied prospective viewpoint value by
  the cosine between the approach bearing and the future sensing bearing. That
  was conceptually wrong because the agent can rotate in place after reaching a
  viewpoint.
- A regression now covers this directly: a side/standoff frontier near the
  remembered anchor keeps `view_bearing_quality=1.0` and positive
  `expected_evidence`.
- The scorer now treats `view_bearing_quality` as rotation-aware. Frontier
  bearing is still used to navigate to the viewpoint, but not to suppress the
  expected evidence available after rotating/scanning there.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-active-perception-frontier-policy.md`
- `docs/experiments/2026-05-30-official-active-perception-frontier-rotation-aware-yolo-smoke.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_active_perception_frontier_keeps_side_viewpoint_evidence_positive -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_active_perception_frontier_prefers_viewpoint_with_expected_evidence src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_frontier_records_expected_evidence_debug src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_frontier_policy_is_registered_with_memory_boundary -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

Linux commands run after syncing the active-perception files:

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_official_objectnav_eval --output runs/habitat_official_objectnav/memory_active_perception_frontier_rotation_aware_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1 --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz --scene-root datasets/habitat/scene_datasets/hm3d --split val_mini --policy memory_active_perception_frontier --max-episodes 4 --max-steps 50 --seed 313 --validate-habitat --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json --memory-min-confidence 0.25 --detector yolo_world --detector-weights yolov8s-worldv2.pt --detector-conf 0.25 --detector-device auto --target-detector-min-confidence 0.25 --categories bed,chair,plant,sofa,toilet,tv_monitor
```

Verification:

- Local side-view regression first failed with `view_bearing_quality=0.0`,
  then passed after the scorer change.
- Local focused gate: `94` passed.
- Local `compileall` and `git diff --check` passed.
- Linux focused gate: `94` passed.
- Linux `compileall` and `git diff --check` passed.
- Fixed YOLO smoke artifact:
  `runs/habitat_official_objectnav/memory_active_perception_frontier_rotation_aware_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Result:

- Official success remains `0/4`, SPL `0.0`, SoftSPL
  `0.03315001996589104`, mean distance-to-goal `5.637647747993469`.
- Active-perception decisions increased from `8` in the flawed smoke to `29`
  in the fixed smoke.
- Selected active-perception expected evidence is now strictly positive:
  `0.4498654945233323..0.519892411627075`.
- Inspected top-candidate zero-evidence cases dropped from `21/40` to `0/145`.
- This is a mechanism fix and diagnostic trace improvement, not a benchmark
  result.

Known risks:

- Three of the four smoke episodes still had no matching memory anchor and
  fell back to occupancy frontier. Larger claims require better query memory
  coverage.
- The current active-perception value is still a lightweight standoff prior,
  not a learned or path-aware evidence-acquisition model.
- The smoke is too small for paper claims even though SoftSPL moved upward.

Next recommended step:

1. Build a broader active-perception dataset/report that includes memory-prior
   coverage by query category and scene.
2. Replace the fixed standoff prior with a path-aware or learned expected
   detector-recall value over reachable viewpoints plus in-place scan actions.
3. Compare only with official Habitat `success`, `spl`, `soft_spl`, and
   `distance_to_goal` before considering scale-up.

## 2026-05-30 Path-Aware Active-Perception Viewpoint Scoring

Current state:

- The active-perception selector now scores reachable free viewpoints adjacent
  to unknown frontier cells, rather than treating unknown frontier cells as
  navigable sensing poses.
- It computes path distance with 4-connected BFS through known free occupancy
  cells and skips disconnected viewpoints.
- Policy traces now include `selected_viewpoint_cell`, `selected_frontier_cell`,
  `path_distance_m`, and top candidates with both viewpoint/frontier cells.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-path-aware-active-perception-viewpoints.md`
- `docs/superpowers/plans/2026-05-30-official-path-aware-active-perception-viewpoints.md`
- `docs/experiments/2026-05-30-official-path-aware-active-perception-viewpoint-yolo-smoke.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_active_perception_frontier_scores_reachable_free_viewpoint -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_active_perception_frontier_uses_free_space_path_distance -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

Linux commands run after syncing:

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_official_objectnav_eval --output runs/habitat_official_objectnav/memory_active_perception_frontier_path_aware_viewpoint_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1 --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz --scene-root datasets/habitat/scene_datasets/hm3d --split val_mini --policy memory_active_perception_frontier --max-episodes 4 --max-steps 50 --seed 313 --validate-habitat --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json --memory-min-confidence 0.25 --detector yolo_world --detector-weights yolov8s-worldv2.pt --detector-conf 0.25 --detector-device auto --target-detector-min-confidence 0.25 --categories bed,chair,plant,sofa,toilet,tv_monitor
```

Verification:

- The two new RED tests failed before implementation because `viewpoint_cell`
  was missing.
- Local full official evaluator file: `54` passed.
- Local focused gate: `96` passed.
- Local `compileall` and `git diff --check` passed.
- Linux focused gate: `96` passed.
- Linux `compileall` and `git diff --check` passed.
- Smoke artifact:
  `runs/habitat_official_objectnav/memory_active_perception_frontier_path_aware_viewpoint_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Result:

- Negative official smoke: success `0/4`, SPL `0.0`, SoftSPL
  `0.0009902771347611306`, mean distance-to-goal `6.065265536308289`.
- This regressed from the rotation-aware frontier-cell smoke SoftSPL
  `0.03315001996589104`.
- Target-match detector calls dropped from `30` to `13`.
- Selected expected evidence remained positive
  (`0.5103327473937014..0.5200065629595595`) and selected path distances were
  finite (`0.25..3.0`), so the mechanism works but the online behavior is not
  yet useful.

Known risks:

- Cleaner viewpoint scoring reduced opportunistic target reacquisition in the
  small smoke.
- The selector is still stateless: it can change viewpoint every step and does
  not perform an explicit rotate/scan phase once a viewpoint is chosen.
- Only one of four smoke episodes has a matching memory anchor, limiting what
  this diagnostic can prove.

Next recommended step:

1. Add a bounded active-perception scan/commit state so the policy turns toward
   the memory anchor and samples detector evidence after choosing or reaching a
   viewpoint.
2. Keep the reachable-viewpoint/path-distance interface as the candidate layer
   for that stateful scan policy.
3. Judge the next slice by target-match recovery and official Habitat metrics,
   not by expected-evidence scores alone.

## 2026-05-30 Active-Perception Viewpoint Scan Phase

Current state:

- Added a bounded orient/scan phase when
  `memory_active_perception_frontier` reaches a selected free viewpoint.
- The policy now records `active_perception_phase`,
  `anchor_bearing_error_rad`, and
  `active_perception_scan_steps_remaining`.
- This made the option semantics cleaner but did not improve the official
  smoke result.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-30-official-active-perception-viewpoint-scan.md`
- `docs/superpowers/plans/2026-05-30-official-active-perception-viewpoint-scan.md`
- `docs/experiments/2026-05-30-official-active-perception-viewpoint-scan-yolo-smoke.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_frontier_orients_to_anchor_from_reached_viewpoint -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

Linux commands run after syncing:

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_official_objectnav_eval --output runs/habitat_official_objectnav/memory_active_perception_frontier_viewpoint_scan_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1 --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz --scene-root datasets/habitat/scene_datasets/hm3d --split val_mini --policy memory_active_perception_frontier --max-episodes 4 --max-steps 50 --seed 313 --validate-habitat --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json --memory-min-confidence 0.25 --detector yolo_world --detector-weights yolov8s-worldv2.pt --detector-conf 0.25 --detector-device auto --target-detector-min-confidence 0.25 --categories bed,chair,plant,sofa,toilet,tv_monitor
```

Verification:

- RED reached-viewpoint test failed before implementation with `move_forward`
  instead of `turn_right`.
- Local full evaluator file: `55` passed.
- Local focused gate: `97` passed.
- Local `compileall` and `git diff --check` passed.
- Linux focused gate: `97` passed.
- Linux `compileall` and `git diff --check` passed.
- Smoke artifact:
  `runs/habitat_official_objectnav/memory_active_perception_frontier_viewpoint_scan_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1`.

Result:

- Negative official smoke: success `0/4`, SPL `0.0`, SoftSPL
  `0.02518699682786324`, mean distance-to-goal `5.697803378105164`.
- This recovered from the path-aware viewpoint smoke SoftSPL
  `0.0009902771347611306`, but remained below the simpler rotation-aware
  frontier-cell smoke SoftSPL `0.03315001996589104`.
- Detector target-match calls fell to `4`.
- Decision counts included `20` orient actions and `20` scan actions.

Known risks:

- More hand-authored scan logic appears unlikely to produce a top-tier result.
- Current memory coverage remains poor: three of four smoke episodes still use
  fallback due `no_matching_memory`.
- The active policy is now useful as an ablation instrument, not as a benchmark
  candidate.

Next recommended step:

1. Stop adding hand-authored active-perception rules to this policy.
2. Export a detector-view recall dataset from existing policy/detector traces,
   including pose relative to memory anchor, viewpoint/path fields, scan phase,
   and target-match outcome.
3. Train or evaluate a learned expected-evidence/view-value model before the
   next official smoke.

## 2026-05-30 Official Detector View-Recall Dataset

Current state:

- Added a new offline dataset exporter:
  `objectnav_core.evaluation.habitat_official_view_recall_dataset`.
- Added CLI:
  `python -m objectnav_core.cli.export_habitat_official_view_recall_dataset`.
- Added console script:
  `objectnav_habitat_official_view_recall_dataset`.
- The dataset converts official `policy_trace.json` plus `detector_trace.json`
  into examples with memory/viewpoint features and future target-recall labels.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_view_recall_dataset.py`
- `src/objectnav_core/objectnav_core/cli/export_habitat_official_view_recall_dataset.py`
- `src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `docs/design/2026-05-30-official-detector-view-recall-dataset.md`
- `docs/superpowers/plans/2026-05-30-official-detector-view-recall-dataset.md`
- `docs/experiments/2026-05-30-official-detector-view-recall-dataset.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
```

Linux commands run after syncing:

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_official_episode_memory.py src/objectnav_core/tests/test_lifecycle_memory_prior_export.py src/objectnav_core/tests/test_habitat_official_memory_discovery.py src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py src/objectnav_core/tests/test_habitat_official_local_action_dataset.py src/objectnav_core/tests/test_habitat_official_local_action_model.py src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.export_habitat_official_view_recall_dataset runs/habitat_official_objectnav/memory_active_perception_frontier_viewpoint_scan_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/policy_trace.json --detector-trace runs/habitat_official_objectnav/memory_active_perception_frontier_viewpoint_scan_yolo_discovery_prior_detector_trace_4ep_50steps_20260530_v1/detector_trace.json --output runs/habitat_official_objectnav/view_recall_dataset_active_perception_viewpoint_scan_yolo_4ep_50steps_20260530_v1/dataset.json --csv-output runs/habitat_official_objectnav/view_recall_dataset_active_perception_viewpoint_scan_yolo_4ep_50steps_20260530_v1/examples.csv --source-run-id memory_active_perception_frontier_viewpoint_scan_yolo_4ep_50steps_20260530_v1 --horizon-steps 5
```

Verification:

- RED test failed because the module did not exist.
- Local view-recall tests: `2` passed.
- Local focused gate: `99` passed.
- Local `compileall` and `git diff --check` passed.
- Linux focused gate: `99` passed.
- Linux `compileall` and `git diff --check` passed.

First dataset result:

- Artifact:
  `runs/habitat_official_objectnav/view_recall_dataset_active_perception_viewpoint_scan_yolo_4ep_50steps_20260530_v1`.
- `step_count=200`, `example_count=196`, `skipped_horizon_count=4`.
- `positive_within_horizon_count=8`.
- `active_perception_example_count=44`.
- Positive labels by phase:
  - non-scan phases: `8/156`
  - `orient_anchor`: `0/20`
  - `scan_anchor`: `0/20`

Known risks:

- This is a small and imbalanced dataset from one four-episode smoke.
- Existing traces do not yet include metric coordinates for selected
  viewpoints, only grid cells and path/evidence scores.
- No learned model has been trained from this dataset yet.

Next recommended step:

1. Export the same view-recall dataset from the rotation-aware and path-aware
   active-perception smokes plus memory-evidence runs.
2. Train a deterministic baseline view-recall scorer.
3. Use offline ranking and calibration to decide whether a learned view-value
   policy is worth another official detector-backed smoke.

## 2026-05-30 Official Detector View-Recall Comparison

Current state:

- The view-recall exporter summary now counts active examples from either
  explicit phase fields, selected viewpoint fields, or top-level decisions that
  contain `active_perception`.
- Ten compatible policy/detector trace pairs were exported on the Linux mirror
  under `runs/habitat_official_objectnav/view_recall_dataset_*_20260530_v1`.
- The comparison uses a hidden-to-visible split:
  `current_target_visible=False` and
  `target_visible_within_horizon=True`.

Files touched in this comparison slice:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_view_recall_dataset.py`
- `src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py`
- `docs/design/2026-05-30-official-detector-view-recall-dataset.md`
- `docs/experiments/2026-05-30-official-detector-view-recall-dataset.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py::test_official_view_recall_dataset_counts_decision_only_active_perception -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py -q
```

Linux commands run after syncing:

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_dataset.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.export_habitat_official_view_recall_dataset <policy_trace.json> --detector-trace <detector_trace.json> --output <dataset.json> --csv-output <examples.csv> --source-run-id <source-run-id> --horizon-steps 5
```

Verification:

- RED active-count regression failed before implementation with
  `active_perception_example_count == 0`.
- Local view-recall tests: `3` passed.
- Linux view-recall tests: `3` passed.
- Re-exported comparison datasets after the counter fix.

Key comparison result:

| Dataset | Examples | Future positives | Hidden-to-visible | Active examples | Active hidden-to-visible |
|---|---:|---:|---:|---:|---:|
| active original | `196` | `48` | `10` | `8` | `8` |
| active rotation-aware | `196` | `39` | `11` | `29` | `9` |
| active path-aware | `196` | `22` | `10` | `35` | `8` |
| active viewpoint scan | `196` | `8` | `5` | `44` | `4` |
| memory evidence, 20 episodes | `1580` | `545` | `53` | `0` | `0` |

Interpretation:

- The hand-authored scan phase remains a dead end for this trace family:
  `orient_anchor=0/20`, `scan_anchor=0/20`.
- Across the four active-perception datasets, all `29` active
  hidden-to-visible positives came from memory-frontier turn/move decisions.
- The 20-episode memory-evidence export gives scale, but most positives are
  detector-continuity rows where the target was already visible.

Next recommended step:

1. Train a deterministic view-recall baseline on hidden-to-visible labels, with
   detector-continuity positives stratified or down-weighted.
2. Score whether learned view value ranks memory-frontier turn/viewpoint
   decisions above anchor scan dead ends.
3. Only run another official YOLO smoke after the offline ranking signal is
   stronger than the current handcrafted expected-evidence score.

## 2026-05-30 Official Hidden-to-Visible View-Recall Model

Current state:

- Added deterministic logistic training/scoring for exported official
  view-recall datasets.
- Default label is derived as `hidden_to_visible_within_horizon`.
- Default train/score filter keeps only current-hidden examples, avoiding
  detector-continuity rows where the target was already visible.
- Train and score CLIs are available as modules and console scripts:
  - `python -m objectnav_core.cli.train_habitat_official_view_recall_model`
  - `python -m objectnav_core.cli.score_habitat_official_view_recall_model`
  - `objectnav_habitat_official_view_recall_model`
  - `objectnav_habitat_official_view_recall_score`

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_view_recall_model.py`
- `src/objectnav_core/objectnav_core/cli/train_habitat_official_view_recall_model.py`
- `src/objectnav_core/objectnav_core/cli/score_habitat_official_view_recall_model.py`
- `src/objectnav_core/tests/test_habitat_official_view_recall_model.py`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `docs/design/2026-05-30-official-view-recall-model.md`
- `docs/superpowers/plans/2026-05-30-official-view-recall-model.md`
- `docs/experiments/2026-05-30-official-view-recall-model.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_model.py::test_official_view_recall_model_trains_hidden_to_visible_slice -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_model.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_model.py src/objectnav_core/tests/test_ros_packaging.py -q
```

Linux commands run:

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_recall_model.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.train_habitat_official_view_recall_model runs/habitat_official_objectnav/view_recall_dataset_memory_evidence_yolo_20ep_80steps_20260530_v1/dataset.json --output runs/habitat_official_objectnav/view_recall_model_hidden_to_visible_20260530_v1/memory_evidence_20ep_model.json --epochs 800 --learning-rate 0.15 --l2 0.001
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.score_habitat_official_view_recall_model <dataset.json> --model <model.json> --output <score-report.json> --csv-output <score-report.csv> --actions move_forward,turn_left,turn_right
```

Verification:

- Local focused view-recall model + packaging tests: `6` passed.
- Linux focused view-recall model + packaging tests: `6` passed.
- Real model/score artifacts written under
  `runs/habitat_official_objectnav/view_recall_model_hidden_to_visible_20260530_v1`.

Key offline results:

| Probe | Hidden examples | Hidden positives | ROC AUC | Top-10 positives | Caution |
|---|---:|---:|---:|---:|---|
| memory-evidence train | `1080` | `53` | `0.975262` | `10/10` | candidate best action all `turn_right` |
| memory model on active original | `157` | `10` | `1.0` | `10/10` | candidate best action all `turn_right` |
| memory model on active rotation | `166` | `11` | `0.992962` | `9/10` | candidate best action all `turn_right` |
| memory model on active path | `183` | `10` | `1.0` | `10/10` | candidate best action all `turn_right` |
| memory model on active scan | `192` | `5` | `0.828877` | `1/10` | over-scores scan/orient negatives |
| active leave-scan-out on scan | `192` | `5` | `1.0` | `5/10` | over-scores unseen scan phases |

Interpretation:

- There is a real hidden-recovery ranking signal in the exported data.
- The current model is not ready for closed-loop policy use because
  observational candidate overrides collapse to one global turn.
- Scan negatives must be included in training or a model can assign high value
  to `orient_anchor` and `scan_anchor` despite `0/20` positives.

Next recommended step:

1. Export or synthesize a candidate-view/action dataset where each state has
   multiple candidate actions or viewpoints with labels.
2. Train a candidate ranker directly, with explicit scan/viewpoint negatives.
3. Use held-out candidate ranking, not in-sample AUC alone, as the gate before
   another official YOLO policy smoke.

## 2026-05-30 Official View-Candidate Recall Dataset

Current state:

- Added an exporter for `memory_prior.top_candidates` in official
  active-perception traces.
- The dataset emits one row per candidate viewpoint/frontier option.
- Only selected candidates receive an observed hidden-to-visible label.
  Unselected candidates are marked with
  `observed_candidate_label_available=False` and null observed-candidate label.
- CLI:
  `python -m objectnav_core.cli.export_habitat_official_view_candidate_dataset`.
- Console script:
  `objectnav_habitat_official_view_candidate_dataset`.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_view_candidate_dataset.py`
- `src/objectnav_core/objectnav_core/cli/export_habitat_official_view_candidate_dataset.py`
- `src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `docs/design/2026-05-30-official-view-candidate-recall-dataset.md`
- `docs/experiments/2026-05-30-official-view-candidate-recall-dataset.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py::test_official_view_candidate_dataset_labels_only_selected_candidate -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py src/objectnav_core/tests/test_ros_packaging.py -q
```

Linux commands run:

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.export_habitat_official_view_candidate_dataset <policy_trace.json> --detector-trace <detector_trace.json> --output <dataset.json> --csv-output <candidates.csv> --source-run-id <source-run-id> --horizon-steps 5
```

Verification:

- Local candidate exporter + packaging tests: `4` passed.
- Linux candidate exporter + packaging tests: `4` passed.
- Real exports completed for original, rotation-aware, path-aware, and
  viewpoint-scan active-perception traces.

Key results:

| Dataset | States | Candidates | Selected labels | Positive selected labels | Unobserved candidates |
|---|---:|---:|---:|---:|---:|
| active original | `25` | `125` | `25` | `8` | `100` |
| active rotation-aware | `29` | `145` | `29` | `9` | `116` |
| active path-aware | `35` | `175` | `35` | `8` | `140` |
| active viewpoint scan | `44` | `220` | `44` | `4` | `176` |
| total | `133` | `665` | `133` | `29` | `532` |

Interpretation:

- Candidate sets are available in the trace, but only the executed top-ranked
  candidate has an observed outcome.
- Selected candidate rank was always `0`, so existing logs cannot directly
  train a counterfactual candidate ranker.
- The dataset is still valuable because it exposes the missing supervision
  explicitly and prevents treating unselected candidates as fake negatives.

Next recommended step:

1. Add a simulator-side candidate rollout collector that starts from saved
   active-perception states and evaluates multiple top candidates.
2. Use those real rollout labels to train a candidate-view value model.
3. Gate any online policy integration on held-out candidate ranking, not on
   observational state AUC.

## 2026-05-30 Official Candidate Rollout Labeling

Current state:

- Added a replay-based candidate rollout exporter for official
  active-perception traces.
- The exporter replays the logged action prefix to each candidate decision
  state, then evaluates each top candidate in a fresh branch rollout.
- Labels are derived from the target detector during the branch rollout:
  `current_target_visible`, `target_visible_within_rollout`, and
  `hidden_to_visible_within_rollout`.
- CLI:
  `python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset`.
- Console script:
  `objectnav_habitat_official_candidate_rollout_dataset`.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`
- `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py`
- `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `docs/design/2026-05-30-official-candidate-rollout-labeling.md`
- `docs/superpowers/plans/2026-05-30-official-candidate-rollout-labeling.md`
- `docs/experiments/2026-05-30-official-candidate-rollout-labeling.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py src/objectnav_core/tests/test_habitat_official_view_recall_model.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py
git diff --check
```

Linux commands run:

```bash
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py src/objectnav_core/tests/test_habitat_official_view_recall_model.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python -m compileall src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py
git diff --check

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset <active-original-policy-trace> --output runs/habitat_official_objectnav/candidate_rollout_dataset_active_original_yolo_5states3cand_20260530_v1/dataset.json --csv-output runs/habitat_official_objectnav/candidate_rollout_dataset_active_original_yolo_5states3cand_20260530_v1/rollouts.csv --detector yolo_world --max-states 5 --candidates-per-state 3 --rollout-horizon-steps 5
python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset <active-scan-policy-trace> --output runs/habitat_official_objectnav/candidate_rollout_dataset_active_scan_yolo_10states3cand_20260530_v1/dataset.json --csv-output runs/habitat_official_objectnav/candidate_rollout_dataset_active_scan_yolo_10states3cand_20260530_v1/rollouts.csv --detector yolo_world --max-states 10 --candidates-per-state 3 --rollout-horizon-steps 5
```

Verification:

- RED test failed first because the rollout dataset module was missing.
- Local rollout dataset and packaging tests: `4` passed.
- RED CLI guard test failed before adding the `__main__` guard.
- RED replay-budget regression failed before setting env `max_steps` from the
  trace prefix plus rollout horizon.
- Local focused rollout/candidate/model/packaging gate: `13` passed.
- Local `compileall` for the new rollout module and CLI returned cleanly.
- Local `git diff --check` returned cleanly.
- Linux focused rollout/candidate/model/packaging gate: `13` passed.
- Linux `compileall` and `git diff --check` returned cleanly.
- Linux active-original smoke: `15` rollout rows, `15` positives, `0` invalid.
- Linux active-scan smoke: `30` rollout rows, `30` positives, `0` invalid.

Known risks:

- The branch controller is diagnostic: candidate bearing chooses the first
  action, and later steps scan left. It is not an oracle teleport to the exact
  candidate viewpoint.
- The first two real smokes are all-positive. This validates replay mechanics
  but is not enough to train a discriminative candidate ranker.
- Detector runtime cost scales with `states * candidates * horizon`, so start
  with small limits.

Next recommended step:

1. Improve candidate branch control so rollouts evaluate the intended
   viewpoint rather than mostly scan-left recovery.
2. Sample harder/later active-perception states and confirm negative rollout
   labels appear.
3. Train a candidate scorer only after the rollout dataset has both positive
   and negative labels for unselected candidates.

## 2026-05-30 Official Action-Matrix Rollout Control State

Current state:

- Action-matrix mode is available in
  `objectnav_core.evaluation.habitat_official_candidate_rollout_dataset` via
  `branch_actions`.
- CLI usage:
  `python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset <policy_trace.json> --detector yolo_world --branch-actions turn_left,turn_right,move_forward --rollout-horizon-steps <N>`.
- Full Linux exports were run on the active original, rotation-aware,
  path-aware, and viewpoint-scan YOLO traces.

Commands already run:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/<trace>/policy_trace.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_<variant>_yolo_allstates_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_<variant>_yolo_allstates_20260530_v1/rollouts.csv \
  --detector yolo_world \
  --branch-actions turn_left,turn_right,move_forward \
  --candidates-per-state 3 \
  --rollout-horizon-steps 5

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/<trace>/policy_trace.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_h1_<variant>_yolo_allstates_20260530_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_h1_<variant>_yolo_allstates_20260530_v1/rollouts.csv \
  --detector yolo_world \
  --branch-actions turn_left,turn_right,move_forward \
  --candidates-per-state 3 \
  --rollout-horizon-steps 1
```

What passed:

- Horizon-5 all-active action matrix:
  `399` rollouts, `172` hidden-to-visible positives, `0` invalid.
- Horizon-5 current-hidden subset:
  `172/309` positives; by action:
  `move_forward 53/103`, `turn_left 96/103`, `turn_right 23/103`.
- Horizon-1 all-active immediate-action control:
  `399` rollouts, `8` positives, `0` invalid.
- Horizon-1 current-hidden subset:
  `8/309` positives; by action:
  `move_forward 0/103`, `turn_left 7/103`, `turn_right 1/103`.

Interpretation:

- The rollout exporter is operational and produces valid counterfactual branch
  data.
- Horizon-5 labels are short-horizon recovery labels, not immediate
  first-action labels. Most positives appear after the diagnostic follow-up
  scan.
- Horizon-1 labels are too sparse for training a useful action scorer from
  these traces.
- `90/399` horizon-5 rows were already target-visible at the branch state and
  should be filtered for hidden-to-visible recovery training.

Risks and assumptions:

- The post-first-action controller currently scans left, creating a strong
  `turn_left` bias.
- The action matrix is not yet an exact candidate-viewpoint value dataset.
- No official ObjectNav benchmark result changed.

Next recommended action:

1. Redesign the branch follow-up controller so action branches are symmetric
   or explicitly action-conditioned.
2. Keep separate labels for immediate first-action effect, short-horizon
   recovery, and exact candidate viewpoint utility.
3. Only train a learned action scorer after the redesigned labels show both
   enough positives and enough negatives without a trivial global action
   baseline.

## 2026-05-31 Repeat-First Action-Matrix Follow-Up

Current state:

- The rollout exporter now supports `--branch-followup-policy`.
- Supported values:
  - `left_scan`: previous behavior, preserves old artifacts.
  - `repeat_first_action`: repeats each explicit branch action for the whole
    rollout horizon.
- API parameter:
  `export_official_candidate_rollout_dataset(..., branch_followup_policy="left_scan")`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_recall_model.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py

git diff --check
```

Linux commands already run:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py -q

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/<trace>/policy_trace.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_<variant>_yolo_allstates_20260531_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_<variant>_yolo_allstates_20260531_v1/rollouts.csv \
  --detector yolo_world \
  --branch-actions turn_left,turn_right,move_forward \
  --branch-followup-policy repeat_first_action \
  --candidates-per-state 3 \
  --rollout-horizon-steps 5
```

What passed:

- Local rollout test red-green cycle:
  - RED failed because `branch_followup_policy` was absent from the API/CLI.
  - GREEN rollout tests: `6` passed.
- Local focused gate: `15` passed.
- Local compileall and `git diff --check`: exit `0`.
- Linux focused rollout tests: `6` passed.
- Full Linux repeat-first exports:
  - original: `13/75` positive, `0` invalid
  - rotation-aware: `29/87` positive, `0` invalid
  - path-aware: `51/105` positive, `0` invalid
  - viewpoint scan: `108/132` positive, `0` invalid
  - aggregate: `201/399` positive, `0` invalid

Interpretation:

- Repeat-first removes the hidden left-scan continuation from action-matrix
  labels.
- Current-hidden recovery by action is now:
  `move_forward 49/103`, `turn_left 96/103`, `turn_right 56/103`.
- Binary recovery still favors `turn_left`, so this is not yet an online policy
  result.
- Time-to-visible is more promising for learning: strict fastest actions among
  current-hidden states were `turn_left 29`, `turn_right 11`, and
  `move_forward 1`, with `62` ties.

Next recommended action:

1. Add a cost-aware action utility report/dataset over repeat-first rollouts.
2. Evaluate held-out trace-family ranking of fastest/time-to-visible actions.
3. Only then consider a learned active-memory action scorer in the online
   Habitat policy.

## 2026-05-31 Cost-Aware Action-Matrix Report

Current state:

- New report API:
  `build_official_candidate_rollout_action_matrix_report(datasets, current_hidden_only=True)`.
- New CSV writer:
  `write_official_candidate_rollout_action_matrix_report_csv(report, path)`.
- New CLI:
  `python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix`.
- New console script:
  `objectnav_habitat_official_candidate_rollout_action_matrix_report`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_recall_model.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/report_habitat_official_candidate_rollout_action_matrix.py

git diff --check
```

Linux commands already run:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_active_original_yolo_allstates_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_active_rotation_yolo_allstates_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_active_path_yolo_allstates_20260531_v1/dataset.json \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_active_scan_yolo_allstates_20260531_v1/dataset.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_report_all_active_yolo_20260531_v1/report.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_report_all_active_yolo_20260531_v1/states.csv
```

What passed:

- RED tests failed for missing report functions, CLI module, and console
  script registration.
- Local report/packaging tests: `9` passed.
- Local focused gate: `17` passed.
- Linux report/packaging tests: `9` passed.
- Report artifact generated:
  `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_report_all_active_yolo_20260531_v1/report.json`.

Report result:

- Current-hidden states: `103`
- Rollouts summarized: `309`
- Oracle recovered states: `103`
- Action success:
  `move_forward 49/103`, `turn_left 96/103`, `turn_right 56/103`
- Strict fastest:
  `turn_left 29`, `turn_right 11`, `move_forward 1`
- Fastest ties: `62`

Next recommended action:

1. Train a deterministic cost-aware utility scorer from the report states.
2. Evaluate leave-one-trace-family-out fastest-action ranking and time-to-visible
   regret.
3. Do not integrate online until the learned scorer beats simple baselines
   under held-out trace-family validation.

## 2026-05-31 First Cost-Aware Utility Model Baseline

Current state:

- New model API:
  `train_official_candidate_rollout_action_utility_model(report)`.
- New scorer:
  `score_official_candidate_rollout_action_utility_report(report, model)`.
- New held-out evaluation:
  `evaluate_action_utility_leave_one_source(report)`.
- New CLI:
  `python -m objectnav_core.cli.train_habitat_official_candidate_rollout_action_utility_model`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_action_utility_model.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_recall_model.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_action_utility_model.py \
  src/objectnav_core/objectnav_core/cli/train_habitat_official_candidate_rollout_action_utility_model.py

git diff --check
```

Linux commands already run:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_action_utility_model.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

python -m objectnav_core.cli.train_habitat_official_candidate_rollout_action_utility_model \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_report_all_active_yolo_20260531_v1/report.json \
  --output runs/habitat_official_objectnav/action_utility_model_repeat_first_all_active_step_interaction_yolo_20260531_v1/model.json \
  --scores-output runs/habitat_official_objectnav/action_utility_model_repeat_first_all_active_step_interaction_yolo_20260531_v1/scores.json \
  --leave-one-source-output runs/habitat_official_objectnav/action_utility_model_repeat_first_all_active_step_interaction_yolo_20260531_v1/leave_one_source.json \
  --epochs 1000 \
  --learning-rate 0.2 \
  --l2 0.001
```

What passed:

- RED tests failed for missing model, CLI, setup entry, and missing action-step
  interaction capacity.
- Local focused gate: `21` passed.
- Linux utility/packaging tests: `5` passed.
- Training artifact written:
  `runs/habitat_official_objectnav/action_utility_model_repeat_first_all_active_step_interaction_yolo_20260531_v1/model.json`.

Result:

- Full report:
  `91/103` chosen actions are fastest, `96/103` recover, mean utility regret
  `0.038835`.
- Chosen action counts:
  `turn_left 71`, `move_forward 25`, `turn_right 7`.
- Always-`turn_left` baseline on the same report:
  `91/103` fastest, `96/103` recover, regret `0.038835`.
- Leave-one-source evaluation:
  `84/103` fastest, `89/103` recover, regret `0.052427`.

Interpretation:

- The first learned utility model is not policy-worthy. It diversifies actions
  but does not beat always-left in aggregate and generalizes worse under
  leave-one-source evaluation.
- The blocker is likely feature poverty: report states do not yet expose
  memory-anchor bearing, relative heading, local traversability/depth, or recent
  detector evidence.

Next recommended action:

1. Extend the action-matrix report with richer pre-decision state features.
2. Regenerate the report/model and require held-out improvement over
   always-left before any online policy integration.

## 2026-05-31 Pre-Decision Action-Utility Features

Current state:

- Rollout rows now include a `state_features` payload extracted before any
  branch action.
- Feature sources are limited to logged policy state and replayed pre-branch
  observation fields: agent pose, memory-prior geometry/evidence, top-candidate
  score summary, local center-depth clearance, and detector-history fields if
  already present in the trace.
- Action-matrix reports preserve `state_features` once per replay state.
- The linear action-utility model now consumes numeric `state_feature=*` and
  action-conditioned `action_state_feature=*` terms.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_action_utility_model.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_action_utility_model.py \
  src/objectnav_core/tests/test_habitat_official_view_candidate_dataset.py \
  src/objectnav_core/tests/test_habitat_official_view_recall_model.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_action_utility_model.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/report_habitat_official_candidate_rollout_action_matrix.py \
  src/objectnav_core/objectnav_core/cli/train_habitat_official_candidate_rollout_action_utility_model.py

git diff --check
```

What passed:

- RED tests failed first for missing rollout `state_features`, missing report
  preservation, and missing model feature terms.
- Focused rollout/model unit gate: `15` passed.
- Local focused gate: `24` passed.
- Full local `src/objectnav_core/tests` suite: `413` passed.
- Compileall exited `0`.
- `git diff --check` exited `0`.
- Explicit trailing-whitespace scan over touched files exited `0`.
- Linux focused rollout/model/packaging gate in conda env `habitat`: `16`
  passed.
- Linux compileall in conda env `habitat` exited `0`.
- Linux `git diff --check` and explicit trailing-whitespace scan exited `0`.

This section is superseded by the artifact-regeneration section below: Linux
tests, real feature-bearing rollout export, report generation, and retraining
have now run.

## 2026-05-31 Feature-Bearing Repeat-First Artifact Regeneration

Current state:

- Four repeat-first action-matrix datasets were regenerated on Linux with
  `state_features`.
- Aggregate report:
  `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_state_features_report_all_active_yolo_20260531_v1/report.json`.
- Tuned feature-aware model:
  `runs/habitat_official_objectnav/action_utility_model_repeat_first_state_features_tuned_all_active_yolo_20260531_v1/model.json`.
- Baseline comparison:
  `runs/habitat_official_objectnav/action_utility_model_repeat_first_state_features_tuned_all_active_yolo_20260531_v1/baseline_comparison.json`.

What passed:

- One-state real Habitat/Yolo smoke: `3` rollouts, `2` positives, `0` invalid,
  `state_features` present.
- Full regenerated datasets:
  original `13/75`, rotation `29/87`, path `51/105`, scan `108/132`
  positives; all had `0` invalid rollouts and non-empty `state_features`.
- Aggregate report: `103` current-hidden states, `309` action rollouts,
  `25` feature keys.

Model result:

- Always-`turn_left`: `91/103` fastest, `96/103` success, regret `0.038835`.
- Old step-interaction model on the new report: same aggregate as always-left.
- Default feature model with old hyperparameters collapsed to always-`move_forward`:
  `48/103` fastest, `49/103` success, regret `0.220388`.
- Tuned feature model full report:
  `95/103` fastest, `100/103` success, regret `0.018608`.
- Tuned feature model leave-one-source:
  `91/103` fastest, `96/103` success, regret `0.038835`, which only ties
  always-left.
- Scratch pairwise-ranking probe reached `99/103` fastest on the full report,
  but only `85/103` leave-one-source, so it is also not policy-ready.

Interpretation:

- The pre-decision features help fit the current report, but not held-out trace
  families. This is not an online policy claim.
- The likely blocker is data/label coverage: the four repeat-first active traces
  are too source-skewed, and always-left remains too strong.

Next recommended action:

1. Mine hard states where always-left is not fastest.
2. Regenerate a balanced/source-diverse counterfactual dataset around those hard
   states.
3. Consider exact candidate-viewpoint/state-restore labels or a richer local
   action space before another policy model.

## 2026-05-31 Always-Left Hard-State Mining

Current state:

- New design:
  `docs/design/2026-05-31-official-action-matrix-hard-state-mining.md`.
- New API:
  `mine_official_candidate_rollout_hard_states(report, baseline_action="turn_left")`.
- New CSV writer:
  `write_official_candidate_rollout_hard_states_csv(report, path)`.
- New CLI:
  `python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states`.
- New console script:
  `objectnav_habitat_official_candidate_rollout_hard_states`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_hard_state_mining.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_hard_state_mining.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

Linux commands already run:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_hard_state_mining.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_state_features_report_all_active_yolo_20260531_v1/report.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_hard_states_all_active_yolo_20260531_v1/hard_states.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_hard_states_all_active_yolo_20260531_v1/hard_states.csv

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_state_features_report_all_active_yolo_20260531_v1/report.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_hard_or_tie_states_all_active_yolo_20260531_v1/hard_or_tie_states.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_hard_or_tie_states_all_active_yolo_20260531_v1/hard_or_tie_states.csv \
  --include-baseline-ties
```

What passed:

- RED tests failed first for missing miner module, CLI module, and console
  script registration.
- Local miner/packaging tests: `5` passed.
- Linux miner/packaging tests in conda env `habitat`: `5` passed.
- Default hard-state artifact generated from the real feature-bearing report.
- Hard-or-tie diagnostic artifact generated from the same report.

Result:

- Default always-left-not-fastest slice:
  `12/103` states.
- Strict fastest counts:
  `turn_right 11`, `move_forward 1`.
- Baseline always-left succeeded, but was slower, in `5/12` hard states.
- Source-family split:
  active original `1`, active rotation `5`, active path `5`, active scan `1`.
- Category split:
  all `12` hard states are `tv_monitor`.
- Hard-or-tie diagnostic slice:
  `74/103` states, made of `12` not-fastest states plus `62` fastest-action
  ties where always-left is still co-fastest.

Interpretation:

- Hard-state mining succeeded as a diagnostic, but it reinforces the data
  limitation. The true always-left-failure slice is tiny and has no category
  diversity.
- The `--include-baseline-ties` slice is useful for ambiguity analysis, not for
  claiming a learned controller beats always-left.
- Do not train another policy model on this slice alone.

Next recommended action:

1. Collect broader hard-state rollouts that include categories beyond
   `tv_monitor`.
2. Keep source-family breakdowns explicit in any future sampling or held-out
   validation.
3. Revisit exact candidate-viewpoint/state-restore labels or a richer symmetric
   action space before policy integration.

## 2026-05-31 Category-Balanced 20-Episode Hard-State Probe

Current state:

- New design:
  `docs/design/2026-05-31-official-category-balanced-rollout-export.md`.
- New experiment report:
  `docs/experiments/2026-05-31-official-category-balanced-hard-state-probe.md`.
- Exporter API now accepts:
  `max_states_per_category`.
- Exporter CLI now accepts:
  `--max-states-per-category`.
- Linux active-perception trace:
  `runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1`.
- Linux capped repeat-first action matrix:
  `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_limit_states_per_target_category \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_cli_writes_json_and_csv -q
```

Linux commands already run:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_limit_states_per_target_category \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_cli_writes_json_and_csv -q

python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --output runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1 \
  --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
  --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --split val_mini \
  --policy memory_active_perception_frontier \
  --max-episodes 20 \
  --max-steps 80 \
  --seed 313 \
  --validate-habitat \
  --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_20ep_80steps_20260530_v1/memory_prior.json \
  --memory-min-confidence 0.25 \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/dataset.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/rollouts.csv \
  --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
  --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --split val_mini \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor \
  --branch-actions turn_left,turn_right,move_forward \
  --branch-followup-policy repeat_first_action \
  --rollout-horizon-steps 5 \
  --max-states-per-category 12

python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/dataset.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/report.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/states.csv

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/report.json \
  --output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/hard_states.json \
  --csv-output runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_balanced20ep_yolo_max12cat_20260531_v1/hard_states.csv
```

What passed:

- RED tests failed first for missing `max_states_per_category` API and CLI
  support.
- Local targeted exporter tests: `2` passed.
- Linux targeted exporter tests: `2` passed.
- 20-episode active-perception trace completed.
- Category-balanced repeat-first rollout export completed with `0` invalid
  rollouts.
- Action-matrix report and hard-state mining completed.

Result:

- 20-episode active-perception trace:
  `1600` steps, official success `0/20`, SPL `0.0`, SoftSPL
  `0.02824322412933835`.
- Active candidate states in the trace:
  `chair 477`, `bed 238`, `tv_monitor 85`, `sofa 5`.
- Category-balanced rollout dataset:
  `41` states and `123` rollouts with `32` positives and `0` invalid.
- Selected dataset categories:
  `chair 12`, `bed 12`, `tv_monitor 12`, `sofa 5`.
- Current-hidden report:
  `40` states and `120` action rows.
- Report positive actions:
  `sofa 8`, `tv_monitor 24`; `chair` and `bed` had no repeat-first recovery.
- Always-left-not-fastest hard states:
  `8/40`, split `tv_monitor 5` and `sofa 3`.
- Hard-or-tie states:
  `15/40`, split `tv_monitor 11` and `sofa 4`.

Interpretation:

- Category balancing worked and broke the all-`tv_monitor` hard-state lock.
- The current repeat-first labels are still not broad enough: `chair` and `bed`
  did not recover, so they cannot yet provide useful fastest-action
  supervision.
- This is a data/label design result, not a policy improvement. Official
  success and SPL remain `0`.

Next recommended action:

1. Add score/phase-aware candidate-state sampling, not just first-N per
   category.
2. Inspect why `chair` and `bed` states do not recover: detector visibility,
   selected viewpoint quality, or macro-action label weakness.
3. Prioritize exact candidate-viewpoint/state-restore labels before more
   utility-model training.

## 2026-05-31 Score-Aware Hard-State Probe

Current state:

- New design:
  `docs/design/2026-05-31-official-score-aware-rollout-export.md`.
- New experiment report:
  `docs/experiments/2026-05-31-official-score-aware-hard-state-probe.md`.
- New implementation plan:
  `docs/superpowers/plans/2026-05-31-official-score-aware-rollout-export.md`.
- Exporter API now accepts:
  `state_sampling`.
- Exporter CLI now accepts:
  `--state-sampling`.
- New state-sampling mode:
  `top_score_desc`.
- Linux capped repeat-first action matrix:
  `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_score_top_max8cat_yolo_20260531_v1`.

Commands already run:

```bash
PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_sample_states_by_top_candidate_score -q

PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_cli_writes_json_and_csv -q

PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py -q

PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests -q

python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

Linux commands already run:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_sample_states_by_top_candidate_score \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_cli_writes_json_and_csv -q

OUT=runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_score_top_max8cat_yolo_20260531_v1

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json \
  --output "$OUT/dataset.json" \
  --csv-output "$OUT/rollouts.csv" \
  --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
  --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --split val_mini \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor \
  --branch-actions turn_left,turn_right,move_forward \
  --branch-followup-policy repeat_first_action \
  --rollout-horizon-steps 5 \
  --max-states-per-category 8 \
  --state-sampling top_score_desc

python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
  "$OUT/dataset.json" \
  --output "$OUT/report.json" \
  --csv-output "$OUT/states.csv"

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  "$OUT/report.json" \
  --output "$OUT/hard_states.json" \
  --csv-output "$OUT/hard_states.csv"

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  "$OUT/report.json" \
  --output "$OUT/hard_or_tie_states.json" \
  --csv-output "$OUT/hard_or_tie_states.csv" \
  --include-baseline-ties
```

What passed:

- RED tests failed first for missing `state_sampling` API support and missing
  `--state-sampling` CLI support.
- Local exporter test file: `12` passed.
- Local full objectnav core tests: `419` passed.
- Local `compileall`, `git diff --check`, and touched-file trailing whitespace
  scan passed.
- Linux targeted exporter tests: `2` passed.
- Linux score-aware repeat-first rollout export/report/mining completed.

Result:

- Exporter candidate-bearing states in the 20-episode trace:
  `879`, split `chair 477`, `bed 238`, `tv_monitor 159`, `sofa 5`.
- Score-aware selected dataset:
  `29` states and `87` rollouts with `18` positives and `0` invalid.
- Selected state categories:
  `tv_monitor 8`, `chair 8`, `bed 8`, `sofa 5`.
- Current-hidden report:
  `28` states and `84` action rows.
- Positive actions:
  `sofa 8`, `tv_monitor 10`; `chair` and `bed` still had no repeat-first
  recovery.
- Always-left-not-fastest hard states:
  `5/28`, split `sofa 3` and `tv_monitor 2`.
- Hard-or-tie states:
  `6/28`, split `sofa 4` and `tv_monitor 2`.

Interpretation:

- Score-aware sampling is implemented and verified, but it does not rescue the
  missing `chair`/`bed` recovery.
- The best selected `chair` and `bed` top scores are very low compared with
  `sofa` and `tv_monitor`, so the trace itself is not offering strong
  candidate states for those categories under this policy/prior.
- This is another negative diagnostic for the current repeat-first label, not a
  policy improvement.

Next recommended action:

1. Stop tuning utility models on repeat-first labels until label quality is
   improved.
2. Prototype exact state-restore or candidate-viewpoint labels.
3. Add phase-aware analysis for active-viewpoint orient/scan states and inspect
   `chair`/`bed` detector evidence near the selected trace states.

## 2026-05-31 Phase-Diverse Hard-State Probe

Current state:

- New design:
  `docs/design/2026-05-31-official-phase-diverse-rollout-export.md`.
- New experiment report:
  `docs/experiments/2026-05-31-official-phase-diverse-hard-state-probe.md`.
- New implementation plan:
  `docs/superpowers/plans/2026-05-31-official-phase-diverse-rollout-export.md`.
- Exporter API now accepts:
  `max_states_per_category_episode`.
- Exporter CLI now accepts:
  `--max-states-per-category-episode`.
- New state-sampling mode:
  `active_phase_path`.
- Linux trace-supervised datasets:
  `runs/habitat_official_objectnav/view_candidate_dataset_active_perception_yolo_20ep_80steps_20260531_v1`
  and
  `runs/habitat_official_objectnav/view_recall_dataset_active_perception_yolo_20ep_80steps_20260531_v1`.
- Linux capped repeat-first action matrix:
  `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_max8cat_max2episode_yolo_20260531_v1`.

Commands already run:

```bash
PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_sample_active_viewpoint_phases_across_episodes -q

PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_cli_writes_json_and_csv -q

PYTHONPATH=src/objectnav_core pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py -q

PYTHONPATH=src/objectnav_core pytest src/objectnav_core/tests -q

python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

Linux commands already run:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
export PYTHONPATH=src/objectnav_core

pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_sample_active_viewpoint_phases_across_episodes \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_cli_writes_json_and_csv -q

TRACE=runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1
VC_OUT=runs/habitat_official_objectnav/view_candidate_dataset_active_perception_yolo_20ep_80steps_20260531_v1
VR_OUT=runs/habitat_official_objectnav/view_recall_dataset_active_perception_yolo_20ep_80steps_20260531_v1

python -m objectnav_core.cli.export_habitat_official_view_candidate_dataset \
  "$TRACE/policy_trace.json" \
  --detector-trace "$TRACE/detector_trace.json" \
  --output "$VC_OUT/dataset.json" \
  --csv-output "$VC_OUT/candidates.csv" \
  --source-run-id memory_active_perception_frontier_yolo_20ep_80steps_20260531_v1 \
  --horizon-steps 5

python -m objectnav_core.cli.export_habitat_official_view_recall_dataset \
  "$TRACE/policy_trace.json" \
  --detector-trace "$TRACE/detector_trace.json" \
  --output "$VR_OUT/dataset.json" \
  --csv-output "$VR_OUT/examples.csv" \
  --source-run-id memory_active_perception_frontier_yolo_20ep_80steps_20260531_v1 \
  --horizon-steps 5

OUT=runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_max8cat_max2episode_yolo_20260531_v1

python -m objectnav_core.cli.export_habitat_official_candidate_rollout_dataset \
  "$TRACE/policy_trace.json" \
  --output "$OUT/dataset.json" \
  --csv-output "$OUT/rollouts.csv" \
  --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
  --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --split val_mini \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --detector-device auto \
  --target-detector-min-confidence 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor \
  --branch-actions turn_left,turn_right,move_forward \
  --branch-followup-policy repeat_first_action \
  --rollout-horizon-steps 5 \
  --max-states-per-category 8 \
  --max-states-per-category-episode 2 \
  --state-sampling active_phase_path

python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
  "$OUT/dataset.json" \
  --output "$OUT/report.json" \
  --csv-output "$OUT/states.csv"

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  "$OUT/report.json" \
  --output "$OUT/hard_states.json" \
  --csv-output "$OUT/hard_states.csv"

python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
  "$OUT/report.json" \
  --output "$OUT/hard_or_tie_states.json" \
  --csv-output "$OUT/hard_or_tie_states.csv" \
  --include-baseline-ties
```

What passed:

- RED tests failed first for missing API and CLI support.
- Local exporter tests: `13` passed.
- Local full objectnav core tests: `420` passed.
- Local compileall, `git diff --check`, and touched-file whitespace scan passed.
- Linux targeted exporter tests: `2` passed.
- Linux trace-supervised exports and phase-diverse rollout/report/mining
  completed.

Result:

- Trace-supervised selected-candidate positives:
  `10/879`, split `sofa 4`, `chair 4`, `tv_monitor 1`, `bed 1`.
- Phase-diverse rollout dataset:
  `24` states and `72` rollouts with `21` positives and `0` invalid.
- Selected categories:
  `chair 8`, `bed 7`, `tv_monitor 5`, `sofa 4`.
- Positive branch rollouts:
  `tv_monitor 7`, `sofa 6`, `bed 4`, `chair 4`.
- Current-hidden action-matrix report:
  `23` states and `69` action rows.
- Oracle-recovered states:
  `14/23`, split `tv_monitor 5`, `chair 4`, `sofa 3`, `bed 2`.
- Always-left-not-fastest hard states:
  `8/23`, split `chair 3`, `sofa 2`, `tv_monitor 2`, `bed 1`.
- Hard-or-tie states:
  `11/23`, split `chair 3`, `sofa 3`, `tv_monitor 3`, `bed 2`.

Interpretation:

- This is the first repeat-first action-matrix probe in the current sequence
  that produces recovered and hard states for all represented categories.
- Earlier `chair`/`bed` failures were partly sampling artifacts: score and
  first-N category sampling skipped rare low-score at-viewpoint recoveries.
- The online policy is still not good; the source run remains official-metric
  negative. This only improves the offline supervision substrate.

Next recommended action:

1. Add active-viewpoint phase/rank features to action-matrix state features.
2. Collect phase-diverse action matrices from more source traces.
3. Then test whether a learned action utility model can beat always-left on
   held-out source families; if not, proceed to exact state-restore labels.

## 2026-05-31 Active-Phase State Features and Utility Comparison

Current state:

- Active-viewpoint phase/rank fields are now part of candidate-rollout
  `state_features`.
- Design:
  `docs/design/2026-05-31-official-active-phase-state-features.md`.
- Experiment report:
  `docs/experiments/2026-05-31-official-active-phase-feature-utility-comparison.md`.
- Linux 20-episode feature-bearing matrix:
  `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_max8cat_max2episode_yolo_20260531_v1`.
- Linux five-source phase-feature report:
  `runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_report_all_sources_yolo_20260531_v1/report.json`.
- Linux utility-model comparison:
  `runs/habitat_official_objectnav/action_utility_model_repeat_first_phase_path_features_all_sources_yolo_20260531_v1/baseline_comparison.json`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check

ssh badger-linux 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_can_sample_active_viewpoint_phases_across_episodes \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_cli_writes_json_and_csv -q'

ssh badger-linux 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  OUT=runs/habitat_official_objectnav/action_rollout_matrix_repeat_first_phase_path_features_max8cat_max2episode_yolo_20260531_v1 && \
  /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.report_habitat_official_candidate_rollout_action_matrix \
    "$OUT/dataset.json" --output "$OUT/report.json" --csv-output "$OUT/states.csv" && \
  /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.mine_habitat_official_candidate_rollout_hard_states \
    "$OUT/report.json" --output "$OUT/hard_states.json" --csv-output "$OUT/hard_states.csv"'
```

Additional Linux commands generated bounded phase-feature matrices for the
4-episode original, rotation, path, and scan traces, combined those with the
20-episode matrix, and trained default/tuned utility models with
leave-one-source outputs.

What passed:

- RED tests failed first for missing active-phase feature keys.
- Local full objectnav core suite passed earlier in this slice: `420 passed`.
- Linux targeted exporter tests passed: `2 passed`.
- Real artifact audit found all six phase feature fields in rollout JSON,
  rollout CSV, report JSON, and report CSV.
- Feature-bearing 20-episode report/mining completed:
  `23` current-hidden states, `14` oracle-recovered, `8` strict hard states.
- Five-source phase-feature report completed:
  `31` current-hidden states and `93` action rows.
- Baseline comparison artifact was written.

Result:

- Phase-feature 20-episode dataset:
  `24` states, `72` rollouts, `21` positives, `0` invalid.
- Five-source hard states:
  `10/31` always-left-not-fastest, split `bed 1`, `chair 3`, `sofa 2`,
  `tv_monitor 4`.
- Tuned model full report:
  `19/31` fastest, `20/31` success, regret `0.030645`.
- Tuned model leave-one-source:
  `17/31` fastest, `17/31` success, regret `0.135484`.
- Always-left baseline:
  `12/31` fastest, `15/31` success, regret `0.154301`.
- Always-right baseline:
  `13/31` fastest, `14/31` success, regret `0.132796`.
- On the largest 20-episode holdout, tuned model regret was `0.182609`,
  worse than always-right at `0.131884`.

Interpretation:

- Phase features are validated as model-visible diagnostic fields.
- The learned utility model is still not policy-ready. Aggregate
  leave-one-source beats always-left, but the comparison is not robust because
  four held-out sources contain only `2` states each and the largest holdout
  loses to a constant always-right action by regret.
- This should trigger label redesign, not another small feature/model polish
  pass.

Next recommended action:

1. Prototype exact state-restore or candidate-viewpoint labels.
2. Add constant-action baseline comparison to every future action-utility
   report.
3. Collect larger independent phase-diverse traces before any online
   integration attempt.

## 2026-05-31 State-Restore Current-View Labels

Current state:

- New design:
  `docs/design/2026-05-31-official-state-restore-label-dataset.md`.
- New plan:
  `docs/superpowers/plans/2026-05-31-official-state-restore-label-dataset.md`.
- New experiment report:
  `docs/experiments/2026-05-31-official-state-restore-label-dataset.md`.
- New API:
  `export_official_candidate_state_restore_dataset(...)`.
- New CSV writer:
  `write_official_candidate_state_restore_dataset_csv(...)`.
- New CLI:
  `python -m objectnav_core.cli.export_habitat_official_candidate_state_restore_dataset`.
- Linux smoke artifact:
  `runs/habitat_official_objectnav/candidate_state_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_labels_exact_replayed_state \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_writes_csv \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_cli_writes_json_and_csv -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

ssh badger-linux 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_labels_exact_replayed_state \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_state_restore_dataset_cli_writes_json_and_csv \
    src/objectnav_core/tests/test_ros_packaging.py -q'

ssh badger-linux 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  OUT=runs/habitat_official_objectnav/candidate_state_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1 && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_habitat_official_candidate_state_restore_dataset \
    runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json \
    --output "$OUT/dataset.json" \
    --csv-output "$OUT/states.csv" \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-states-per-category 8 \
    --max-states-per-category-episode 2 \
    --state-sampling active_phase_path'
```

What passed:

- RED tests failed first for missing state-restore API, writer, and CLI.
- New local tests: `3 passed`.
- Focused local exporter/packaging gate: `17 passed`.
- Linux targeted tests: `3 passed`.
- Real Linux Habitat/Yolo smoke completed.

Result:

- State-restore smoke:
  `24` states, `24` valid restores, `0` invalid restores.
- Current-view target-visible:
  `1/24`, a `sofa` orient-at-viewpoint state.
- Hidden at restored current view:
  `23/24`, split `chair 8`, `bed 7`, `tv_monitor 5`, `sofa 3`.

Interpretation:

- The state-restore path is a clean replay/current-view label audit.
- It confirms most phase-diverse memory-query states are still hidden at the
  exact restored observation, so this is not enough for candidate ranking.
- The next useful label must evaluate candidate viewpoints directly, likely by
  carefully converting episode-relative grid cells to Habitat world poses and
  teleporting only for offline supervision.

Next recommended action:

1. Design and implement candidate-viewpoint teleport labels.
2. Use state-restore labels to filter current-visible states before action or
   candidate training.
3. Keep official online metrics separate from these teleport/current-view
   diagnostic labels.

## Latest Candidate-Viewpoint Restore State

The candidate-viewpoint label exporter is implemented, locally verified, and
smoke-tested on the Linux Habitat/Yolo setup.

New artifacts:

- Design:
  `docs/design/2026-05-31-official-candidate-viewpoint-restore-labels.md`
- Plan:
  `docs/superpowers/plans/2026-05-31-official-candidate-viewpoint-restore-labels.md`
- Experiment report:
  `docs/experiments/2026-05-31-official-candidate-viewpoint-restore-labels.md`
- API:
  `export_official_candidate_viewpoint_restore_dataset(...)`
- CSV writer:
  `write_official_candidate_viewpoint_restore_dataset_csv(...)`
- CLI:
  `python -m objectnav_core.cli.export_habitat_official_candidate_viewpoint_restore_dataset`

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_grid_cell_conversion_uses_episode_relative_xz \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_restore_dataset_labels_top_k_scan_viewpoints \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_restore_dataset_keeps_invalid_restore_auditable \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_restore_dataset_cli_writes_json_and_csv -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_restore_fallback_uses_episode_start_pose -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/tests/test_ros_packaging.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  OUT=runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1 && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_habitat_official_candidate_viewpoint_restore_dataset \
    runs/habitat_official_objectnav/memory_active_perception_frontier_yolo_discovery_prior_detector_trace_20ep_80steps_20260531_v1/policy_trace.json \
    --output "$OUT/dataset.json" \
    --csv-output "$OUT/candidate_viewpoints.csv" \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-states-per-category 8 \
    --max-states-per-category-episode 2 \
    --state-sampling active_phase_path \
    --candidates-per-state 5 \
    --viewpoint-heading-count 8'
```

What passed:

- RED tests failed first for missing candidate-viewpoint helper/API/CLI.
- New local candidate-viewpoint tests: `4 passed`.
- Habitat-style episode-start pose fallback test: `1 passed`.
- A real Linux smoke initially failed because Habitat-Sim candidate restore
  observations returned RGBA `rgb`; a regression test failed first and then
  passed after stripping the alpha channel.
- Focused local exporter/packaging gate after the RGBA fix: `23 passed`.
- Full local suite: `428 passed`.
- Local compileall, diff check, and touched-file whitespace scan passed.
- Linux targeted exporter/packaging tests: `23 passed`.
- Linux targeted compileall passed.
- Real Linux Habitat/Yolo candidate-viewpoint export completed.

Current implementation details:

- Candidate `viewpoint_cell` is inverted from the active-perception occupancy
  grid into episode-relative `x=right`, `z=forward`.
- Rows record grid size, cell size, origin, and candidate `x/z` so the
  coordinate assumption is auditable.
- The exporter expands each selected candidate-bearing state into top-K
  candidate rows.
- Candidate labels use a fixed heading sweep at the restored candidate
  viewpoint. These are scan labels, not one-step action labels.
- Invalid candidate restores remain in the dataset with
  `label_available=false`; they are not detector negatives.
- Real artifact:
  `runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1`.
- Real artifact summary:
  `24` states, `120` candidate rows, `120/120` valid candidate restores,
  `74/120` target-visible candidate rows, `69/120` hidden-to-visible candidate
  rows, `0` invalid candidate restores.
- State-level coverage:
  `16/24` states had at least one visible candidate viewpoint and `15/24` had
  at least one hidden-to-visible candidate viewpoint. The current-view
  state-restore artifact had only `1/24` target-visible restored states.

Immediate next action:

1. Use the candidate-viewpoint labels for a held-out candidate-ranking model
   comparison.
2. Keep source holdouts and constant baselines; do not claim online policy
   success from offline label richness.
3. Consider adding explicit memory-anchor coordinates to future traces so labels
   can compare uniform-scan visibility with anchor-facing visibility.

## Candidate-Viewpoint Ranker State

The first offline candidate-viewpoint ranker baseline is implemented, locally
verified, Linux-tested, and scored on the real candidate-viewpoint artifact.

New artifacts:

- Design:
  `docs/design/2026-05-31-official-candidate-viewpoint-ranker.md`
- Plan:
  `docs/superpowers/plans/2026-05-31-official-candidate-viewpoint-ranker.md`
- Experiment report:
  `docs/experiments/2026-05-31-official-candidate-viewpoint-ranker.md`
- API:
  `train_official_candidate_viewpoint_ranker_model(...)`
- Score API:
  `score_official_candidate_viewpoint_ranker_dataset(...)`
- Fold API:
  `evaluate_candidate_viewpoint_ranker_state_folds(...)`
- CLI:
  `python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker`

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py \
    src/objectnav_core/tests/test_ros_packaging.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  OUT=runs/habitat_official_objectnav/candidate_viewpoint_ranker_phase_path_features_max8cat_max2episode_yolo_20260531_v1 && \
  mkdir -p "$OUT" && \
  /home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1/dataset.json \
    --output "$OUT/model.json" \
    --scores-output "$OUT/scores.json" \
    --csv-output "$OUT/scores.csv" \
    --state-fold-output "$OUT/state_folds.json" \
    --fold-count 4'
```

What passed:

- RED tests failed first for missing model/CLI/package behavior.
- Focused local ranker and packaging tests: `5 passed`.
- Full local suite: `433 passed`.
- Local compileall, diff check, and touched-file whitespace scan passed.
- Linux targeted ranker and packaging tests: `5 passed`.
- Linux targeted compileall passed.
- Real Linux scoring artifact was written.

Current result:

- Output directory:
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_phase_path_features_max8cat_max2episode_yolo_20260531_v1`.
- Current-hidden filtered rows: `115` candidates from `23` states.
- Label split: `69` positive, `46` negative.
- Train-set candidate ROC-AUC: `0.959042`.
- State-level score report: oracle `15/23`, model `14/23`, top-rank `13/23`,
  top-score `13/23`.
- Four-fold state-holdout aggregate: oracle `15/23`, model `14/23`,
  top-rank `13/23`, top-score `13/23`.
- Category counts `[states, oracle, model, top_rank, top_score]`:
  `bed [7, 3, 2, 1, 1]`, `chair [8, 4, 4, 4, 4]`,
  `sofa [3, 3, 3, 3, 3]`, `tv_monitor [5, 5, 5, 5, 5]`.

Interpretation:

- Candidate-viewpoint labels now support a real offline ranking artifact and a
  transparent baseline comparison.
- The measured model gain is small: one extra recovered state over top-rank and
  top-score on a single source artifact.
- This is not an online policy result and not an official Habitat ObjectNav
  metric result.

Next recommended action:

1. Generate more source-diverse candidate-viewpoint restore artifacts.
2. Add leave-one-source validation for candidate-viewpoint ranker reports.
3. Only consider online integration if source-held-out ranker recovery beats
   simple baselines by a meaningful margin.

## Source-Diverse Candidate-Viewpoint Ranker State

The ranker now supports multi-dataset source tagging and leave-one-source
validation. A first source-diverse Linux run has been completed.

New implementation:

- `evaluate_candidate_viewpoint_ranker_leave_one_source(...)`
- CLI positional input now accepts one or more dataset paths.
- CLI option:
  `--leave-one-source-output <leave_one_source.json>`
- CLI-loaded rows override/add `source_dataset` with the source artifact path.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

python -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q'
```

Additional Linux commands generated four 4-episode candidate-viewpoint restore
datasets and then ran:

```bash
OUT=runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v1
/home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1/dataset.json \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_active_frontier_4ep_yolo_20260531_v1/dataset.json \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_rotation_aware_4ep_yolo_20260531_v1/dataset.json \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_path_aware_4ep_yolo_20260531_v1/dataset.json \
    runs/habitat_official_objectnav/candidate_viewpoint_restore_viewpoint_scan_4ep_yolo_20260531_v1/dataset.json \
    --output "$OUT/model.json" \
    --scores-output "$OUT/scores.json" \
    --csv-output "$OUT/scores.csv" \
    --state-fold-output "$OUT/state_folds.json" \
    --leave-one-source-output "$OUT/leave_one_source.json" \
    --fold-count 4
```

What passed:

- RED tests failed first for missing leave-one-source and multi-dataset CLI
  behavior.
- Focused local ranker tests: `6 passed`.
- Full local suite: `435 passed`.
- Local compileall, diff check, and whitespace scan passed.
- Linux focused ranker tests: `6 passed`.
- Linux targeted compileall passed.
- Source-diverse ranker artifact was written.

Current result:

- Output:
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v1`.
- Combined source candidates: `160`.
- Current-hidden, label-available candidates: `135`.
- Label split: `82` positive, `53` negative.
- Full-source score report: oracle `19/27`, model `18/27`, top-rank `14/27`,
  top-score `14/27`.
- Four-fold state-holdout: oracle `19/27`, model `18/27`, top-rank `14/27`,
  top-score `14/27`.
- Leave-one-source: oracle `19/27`, model `17/27`, top-rank `14/27`,
  top-score `14/27`.
- Largest 20-episode holdout: model `13/23`, top-rank `13/23`,
  top-score `13/23`, oracle `15/23`.

Interpretation:

- Source-held-out ranking beats simple baselines in aggregate, but the largest
  holdout is still a tie. The gain comes from smaller path-aware and
  viewpoint-scan holdouts.
- Two auxiliary sources produced only invalid candidate restores. This is an
  input-quality problem worth debugging before scaling training.
- This remains offline teleport/restore supervision, not online ObjectNav
  success or an official benchmark result.

Next recommended action:

1. Debug invalid candidate restores in 4-episode active-frontier and
   rotation-aware sources.
2. Generate larger, independent source-diverse candidate-viewpoint artifacts.
3. Add a source-family or leave-one-policy-family report before online policy
   integration.

## Frontier-Cell Candidate-Viewpoint Restore Fix

The invalid candidate restores in the active-frontier and rotation-aware
4-episode candidate-viewpoint artifacts have been debugged and fixed.

Root cause:

- These older frontier-style traces store candidate locations as
  `frontier_cell`.
- The candidate-viewpoint restore exporter only accepted `viewpoint_cell`.
- Rows were rejected before Habitat-Sim restore with
  `invalid_candidate_viewpoint_cell`.
- Path-aware and viewpoint-scan traces already had `viewpoint_cell`, which is
  why they were valid.

Fix:

- The exporter now falls back to `frontier_cell` when `viewpoint_cell` is
  missing.
- Regression test:
  `test_candidate_viewpoint_restore_dataset_uses_frontier_cell_when_viewpoint_missing`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_viewpoint_restore_dataset_uses_frontier_cell_when_viewpoint_missing -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q
```

Linux verification:

- Focused regression: `1 passed`.
- Targeted candidate-viewpoint/ranker tests: `8 passed`.
- Active-frontier v2 restore:
  `2` states, `10` candidates, `10` hidden-to-visible, `0` invalid.
- Rotation-aware v2 restore:
  `2` states, `10` candidates, `10` hidden-to-visible, `0` invalid.
- Source-diverse ranker v2:
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v2`.

Current result:

- Source-diverse v2 rows: `155` current-hidden, label-available candidates.
- Label split: `102` positive, `53` negative.
- Full-source and state-fold recovery: oracle `23/31`, model `22/31`,
  top-rank `18/31`, top-score `18/31`.
- Leave-one-source recovery: oracle `23/31`, model `22/31`, top-rank `18/31`,
  top-score `18/31`.
- Among oracle-recoverable leave-one-source states: model `22/23`, top-rank
  `18/23`, top-score `18/23`.
- Largest 20-episode holdout: model `14/23`, top-rank `13/23`,
  top-score `13/23`, oracle `15/23`.
- Among oracle-recoverable states in that largest holdout: model `14/15`,
  top-rank `13/15`, top-score `13/15`.

Next recommended action:

1. Build an online ranker-driven active-perception selection slice.
2. Compare it against existing top-rank/top-score candidate choice under
   official Habitat action execution.
3. Keep teleport/restore labels strictly offline for supervision/evaluation.

## Online Candidate-Viewpoint Ranker Integration State

The source-diverse candidate-viewpoint ranker has been wired into the official
online `memory_active_perception_frontier` policy as an optional ablation path,
but the first online YOLO smoke is a negative result.

Current state:

- New CLI/config flag:
  `--candidate-viewpoint-ranker-model-path`.
- New loader:
  `load_official_candidate_viewpoint_ranker_model(...)`.
- Online selector path:
  `_select_memory_active_perception_frontier(..., candidate_viewpoint_ranker_model=...)`.
- The no-model path preserves the existing hand-score active-perception policy.
- The model path only reranks hand-score top-K candidates. This guard is
  important because an initial smoke allowed the model to score all online
  frontier candidates and selected out-of-distribution hand-score ranks such as
  `40`, `53`, and `84`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q'
```

What passed:

- Focused local official/ranker tests: `74 passed`.
- Full local suite: `441 passed`.
- Local compileall and `git diff --check`: clean.
- Linux focused official/ranker tests: `74 passed`.
- Linux compileall and `git diff --check`: clean.
- Linux preflight with the real source-diverse v2 ranker model succeeded.

Diagnostic smoke:

- Artifact:
  `runs/habitat_official_objectnav/ranker_guided_active_perception_yolo_4ep_50steps_20260531_v2`.
- Ranker model:
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_yolo_20260531_v2/model.json`.
- Memory prior:
  `runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json`.
- Official metrics: success `0/4`, SPL `0.0`, SoftSPL
  `0.0009902771347611306`.
- Detector evidence: `0` target-match calls and `0` target-match detections.
- Policy trace: `49` ranker-active steps, mostly selecting hand-score rank `4`
  inside the bounded top-5 set.

Interpretation:

- This is not an online policy improvement.
- The result suggests offline teleport/restore candidate visibility labels do
  not directly transfer to online action execution with the current logistic
  ranker.
- Keep the optional model path for ablations, but do not make it the default.

Next recommended action:

1. Train an online rollout value model from actual downstream detector evidence
   or official progress instead of only teleport/restore visibility.
2. Alternatively, add a conservative blend where the ranker can override the
   hand-score choice only under a large margin and bounded travel-cost penalty.
3. Re-run official-action smokes before any benchmark or paper claim.

## Candidate-Rank Ablation State

The first follow-up ablation has been run. Removing `candidate_rank` from the
offline candidate-viewpoint ranker does not fix online transfer.

Current state:

- New ranker trainer option:
  `--exclude-feature <feature_name>`.
- Excluded feature names are recorded in
  `model.json` under `dataset.training_filter.excluded_feature_names`.
- No online evaluator code change was needed; online prediction already uses
  the model artifact's feature list.
- The no-`candidate_rank` model has `48` features instead of `49`.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py::test_candidate_viewpoint_ranker_can_exclude_candidate_rank_feature \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py::test_candidate_viewpoint_ranker_cli_excludes_requested_features -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q'
```

One failed command to know about:

- The first Linux training attempt used `OUT=...` in the same shell command as
  `--output $OUT/model.json`. Shell expansion produced `/model.json`, so the
  command failed with `PermissionError`. No useful artifact was written from
  that failed attempt. The rerun used explicit paths and succeeded.

Successful Linux artifacts:

- Offline no-rank model:
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/model.json`
- Offline score report:
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/scores.json`
- Leave-one-source report:
  `runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/leave_one_source.json`
- Online preflight:
  `runs/habitat_official_objectnav/ranker_guided_active_perception_no_candidate_rank_preflight_20260531_v1`
- Online YOLO smoke:
  `runs/habitat_official_objectnav/ranker_guided_active_perception_no_candidate_rank_yolo_4ep_50steps_20260531_v1`

What passed:

- Local focused ranker tests: `8 passed`.
- Linux focused ranker tests: `8 passed`.
- Preflight loaded the no-rank model and recorded `feature_count: 48`.
- Offline source-diverse no-rank recovery stayed at model `22/31`, oracle
  `23/31`, top-rank `18/31`, top-score `18/31`.
- Among oracle-recoverable states, no-rank recovery stayed `22/23`.

What failed / stayed negative:

- Online no-rank smoke metrics: success `0/4`, SPL `0.0`, SoftSPL
  `0.0009902771347611306`.
- Detector target-match calls remained `0`.
- Ranker-active steps remained `49`.
- Online selected hand-score ranks were still almost all rank `4`: `48/49`
  ranker-active steps selected rank `4`, and `1/49` selected rank `2`.

Interpretation:

- `candidate_rank` was not the root cause by itself.
- The no-rank model still favors poor online candidates through other features,
  including path/travel distance and geometry/state terms.
- This strengthens the case that offline teleport/restore visibility is the
  wrong direct online policy target.

Next recommended action:

1. Stop spending effort on single-feature offline-ranker ablations unless they
   directly test a specific online failure.
2. Build an online utility dataset where candidate choices are labeled by
   downstream detector target evidence, official progress, or short-horizon
   success proxy.
3. Keep source artifact and restored-state grouping for all train/holdout
   splits.

## Active-Perception Controller Mismatch State

The current online failure is now better localized. The offline candidate
branches can be recoverable under the exporter continuation, but the online
active-perception controller previously reselected viewpoints every step and
abandoned blocked active-perception targets without the local scan that made
offline branches useful.

Current state:

- `OfficialPolicyState` now tracks
  `active_perception_target_viewpoint_cell` for short-lived option commitment.
- `OfficialPolicyState` now tracks
  `active_perception_blocked_scan_viewpoint_cell` so an aligned but blocked
  target gets one bounded scan before fallback.
- The policy records `active_perception_commitment=continued` when it keeps the
  selected viewpoint across calls.
- The policy records `active_perception_phase=blocked_scan_anchor` and
  `decision=scan_blocked_active_perception_target` for the blocked local scan.
- This is a controller-alignment fix, not a learned-ranker result.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py -q

/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/ranker_guided_active_perception_no_candidate_rank_sticky_yolo_4ep_50steps_20260531_v1 \
    --policy memory_active_perception_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --candidate-viewpoint-ranker-model-path runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/model.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313

/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/ranker_guided_active_perception_no_candidate_rank_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1 \
    --policy memory_active_perception_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --candidate-viewpoint-ranker-model-path runs/habitat_official_objectnav/candidate_viewpoint_ranker_source_diverse_no_candidate_rank_yolo_20260531_v1/model.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313

/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/memory_active_perception_frontier_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1 \
    --policy memory_active_perception_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313
```

What passed:

- New controller regression tests passed after implementation.
- Sticky commitment appeared in traces as
  `active_perception_commitment=continued`.
- Blocked scan appeared in traces as
  `decision=scan_blocked_active_perception_target`.
- The matched hand-score run completed and wrote all expected artifacts:
  `summary.json`, `episodes.csv`, `policy_trace.json`,
  `detector_trace.json`, and `protocol_manifest.json`.

What failed / stayed negative:

- Sticky commitment alone did not improve the no-rank learned-ranker smoke:
  success `0/4`, SPL `0.0`, SoftSPL `0.0009902771347611306`, target-match
  calls `0`.
- Sticky plus blocked scan recovered only partial evidence for the no-rank
  learned-ranker smoke: success `0/4`, SPL `0.0`, SoftSPL
  `0.02518699682786324`, target-match calls `4`.
- The matched no-ranker hand-score smoke produced the same official metrics and
  target evidence, so the recovery is not attributable to the learned ranker.

Next recommended action:

1. Treat the current controller change as an alignment guardrail and keep it
   covered by unit tests.
2. Build online option-value labels using the exact sticky plus blocked-scan
   continuation before training the next selector.
3. Compare any future learned selector against the no-ranker hand-score policy
   under the same controller before making a policy-improvement claim.

## Online Option-Value Label State

The option-value labeler is now implemented and the first diagnostic loop has
completed. It should be treated as a supervision substrate, not a demonstrated
online policy improvement.

Current state:

- New exporter:
  `export_official_candidate_option_value_dataset(...)`.
- New CSV writer:
  `write_official_candidate_option_value_dataset_csv(...)`.
- New CLI:
  `python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset`.
- Candidate rows are under `candidate_viewpoints` so the existing
  candidate-viewpoint ranker can train with
  `--label hidden_to_visible_within_option_rollout`.
- The trainer now threads custom label names through state-fold and
  leave-one-source evaluation paths; earlier fold diagnostics silently used the
  old restore label.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_viewpoint_ranker_model.py \
  src/objectnav_core/objectnav_core/cli/train_habitat_official_candidate_viewpoint_ranker.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py

/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset \
    runs/habitat_official_objectnav/memory_active_perception_frontier_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1/policy_trace.json \
    --output runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1/dataset.json \
    --csv-output runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1/labels.csv \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-states 8 \
    --state-sampling active_phase_path \
    --candidates-per-state 5 \
    --option-horizon-steps 8 \
    --option-scan-steps 4 \
    --seed 313

/home/badger/anaconda3/bin/conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.train_habitat_official_candidate_viewpoint_ranker \
    runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1/dataset.json \
    --label hidden_to_visible_within_option_rollout \
    --output runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/model.json \
    --scores-output runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/scores.json \
    --csv-output runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/scores.csv \
    --state-fold-output runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/state_folds.json \
    --fold-count 4

/home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/option_value_ranker_guided_active_perception_yolo_4ep_50steps_20260531_v1 \
    --policy memory_active_perception_frontier \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --candidate-viewpoint-ranker-model-path runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2/model.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313
```

Successful Linux artifacts:

- Option-value dataset:
  `runs/habitat_official_objectnav/candidate_option_value_sticky_blocked_scan_yolo_4ep_20260531_v1`.
- Tiny option-value ranker:
  `runs/habitat_official_objectnav/candidate_option_value_ranker_sticky_blocked_scan_yolo_4ep_20260531_v2`.
- Online diagnostic:
  `runs/habitat_official_objectnav/option_value_ranker_guided_active_perception_yolo_4ep_50steps_20260531_v1`.

What passed:

- Focused local option/ranker gate: `37 passed`.
- Local `compileall`: exit `0`.
- Linux focused option/ranker gate: `37 passed`.
- Linux `compileall`: exit `0`.
- The option-value export produced `8` states, `40` candidate options, `0`
  invalid options, and `16` hidden-to-visible positives.
- All selected states were oracle-recoverable under the option rollout; top-rank
  and top-score recovered `0/8`.
- The tiny option-value ranker selected rank `3` on all `8` scored states and
  recovered `8/8` in same-trace state folds.

What failed / stayed negative:

- The matched online option-value run did not improve over the hand-score fixed
  controller. Success remained `0/4`, SPL `0.0`, SoftSPL
  `0.02518699682786324`, and target-match calls `4`.
- The model changed online candidate ranks but not online outcome: rank `3` on
  `40/44` ranker-active steps, rank `2` on `2/44`, and rank `4` on `2/44`.
- The result is not benchmark-valid because the memory prior and tiny model are
  diagnostic artifacts.

Next recommended action:

1. Expand the option-value dataset across more source traces and enforce
   source/state separation before drawing selector conclusions.
2. Add richer option utility targets: time-discounted detector evidence,
   official distance-progress delta, and stop-success eligibility.
3. Inspect continuation failures after selecting rank `2/3` candidates; the
   current bottleneck appears downstream of the initial candidate choice.
4. Keep the fixed-controller hand-score policy as the matched comparison for
   any future learned-selector smoke.

## Official Option-Utility Label State

The option-value exporter now has a richer utility layer:

- `initial_detector_confidence`
- `detector_confidence_gain`
- `initial_distance_to_goal_m`
- `final_distance_to_goal_m`
- `min_distance_to_goal_m`
- `distance_to_goal_delta_m`
- `best_distance_to_goal_delta_m`
- `stop_probe_success`
- `stop_probe_spl`
- `stop_probe_softspl`
- `stop_probe_distance_to_goal_m`

New labels:

- `detector_confidence_gain_within_option_rollout`
- `official_progress_within_option_rollout`
- `official_stop_success_after_option_rollout`

Important boundary:

- The STOP probe is offline supervision only. It is not included in
  `option_rollout_actions`.
- The ranker feature allowlist does not expose option outcome fields as online
  features.

Commands already run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py

PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset --help

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core python -m compileall -q \
    src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.export_habitat_official_candidate_option_value_dataset \
    runs/habitat_official_objectnav/memory_active_perception_frontier_sticky_blocked_scan_yolo_4ep_50steps_20260531_v1/policy_trace.json \
    --output runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_nodetector_1state_20260531_v1/dataset.json \
    --csv-output runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_nodetector_1state_20260531_v1/labels.csv \
    --detector none \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-states 1 \
    --state-sampling active_phase_path \
    --candidates-per-state 2 \
    --option-horizon-steps 4 \
    --option-scan-steps 2 \
    --option-progress-threshold-m 0.05 \
    --seed 313'
```

One sync correction:

- An initial `rsync` command copied six basenames into the remote repo root.
  Those misplaced files were removed immediately, then the same files were
  re-synced with `rsync -R` so their paths were preserved.

What passed:

- Local combined focused gate: `40 passed`.
- Local `compileall`: exit `0`.
- Linux combined focused gate: `40 passed`.
- Linux `compileall`: exit `0`.
- Real-Habitat no-detector export wrote `2` valid candidate rows with official
  metric fields populated.

What is not done:

- The broader YOLO option-value dataset has not yet been regenerated with the
  new utility labels.
- No selector has been trained on `official_progress_within_option_rollout` or
  `official_stop_success_after_option_rollout`.
- There is no new online policy win from this slice.

Next recommended action:

1. Re-export the option-value dataset with YOLO enabled and the new utility
   labels.
2. Count positive support for detector gain, official progress, and STOP
   success by source/state before training.
3. If support exists, train separate selectors for each label and compare them
   to fixed-controller hand-score under the same online smoke.

## Option-Utility YOLO Label-Support Check

The broader bounded YOLO utility export now exists on the Linux mirror:

`runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_yolo_4ep_20260531_v1`

The support report exists at:

`runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_yolo_4ep_20260531_v1/label_support.json`

Observed artifact settings:

- State sampling: `active_phase_path`.
- Candidate states: `8`.
- Candidate options: `40`.
- Candidates per state: `5`.
- Invalid options: `0`.
- Option horizon: `8`.
- Option scan steps: `4`.
- Official progress threshold: `0.05` m.

Support counts:

- `hidden_to_visible_within_option_rollout`: `16/40` positives,
  oracle-recoverable states `8/8`, positive ranks `2` and `3`.
- `detector_confidence_gain_within_option_rollout`: `16/40` positives,
  exactly matching hidden-to-visible on this artifact.
- `official_progress_within_option_rollout`: `0/40` positives.
- `official_stop_success_after_option_rollout`: `0/40` positives.

Additional field checks:

- Maximum `best_distance_to_goal_delta_m`: `0.0`.
- Maximum `distance_to_goal_delta_m`: `0.0`.
- Maximum `stop_probe_success`: `0.0`.
- Detector confidence gain was populated for `16` rows with gain `0.748715`.

Commands run during this handoff check:

```bash
ssh badger@100.88.131.52 'find /home/badger/Desktop/dual-anchor-lifelong-objectnav/runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_yolo_4ep_20260531_v1 -maxdepth 1 -type f -printf "%f\n" | sort'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && python3 -m json.tool runs/habitat_official_objectnav/candidate_option_utility_sticky_blocked_scan_yolo_4ep_20260531_v1/label_support.json'
```

What passed:

- The support report was present and internally consistent with the dataset
  summary.
- Detector-gain and hidden-to-visible labels have nonzero support.

What remains negative:

- Official progress and STOP-success labels have no positives in this tiny
  slice. Do not train selectors on those labels from this artifact.
- This is not an online policy win or benchmark result.

Next recommended action:

1. Scale the enriched YOLO export before using official progress or STOP-success
   targets.
2. Keep support counts grouped by source/state before training.
3. If staying on this artifact, only use detector/evidence gain as a diagnostic
   target, and treat it as equivalent to hidden-to-visible for now.

## Official Pathfinder Suffix Diagnostic

Current state:

- New diagnostic policy:
  `memory_active_perception_frontier_pathfinder_suffix`.
- This is an oracle diagnostic only. It uses Habitat episode goal/viewpoint
  positions after a target detector match, so it is not benchmark-valid and
  should not be compared as a final policy.
- The policy exists to isolate terminal approach/STOP from exploration plus
  memory reacquisition.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- `docs/design/2026-05-31-official-pathfinder-suffix-diagnostic.md`
- `docs/superpowers/plans/2026-05-31-official-pathfinder-suffix-diagnostic.md`
- `docs/experiments/2026-05-31-official-pathfinder-suffix-diagnostic.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py

PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_official_objectnav_eval --help

git diff --check

rsync -R docs/design/2026-05-31-official-pathfinder-suffix-diagnostic.md \
  docs/superpowers/plans/2026-05-31-official-pathfinder-suffix-diagnostic.md \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core python -m compileall -q \
    src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
    src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py'
```

Smoke artifacts:

- Radius `1.0`, 50 steps:
  `runs/habitat_official_objectnav/pathfinder_suffix_active_perception_yolo_4ep_50steps_20260531_v1`.
- Radius `0.05`, 100 steps:
  `runs/habitat_official_objectnav/pathfinder_suffix_active_perception_yolo_4ep_100steps_radius005_20260531_v1`.

What passed:

- Local focused eval/CLI gate: `76 passed`.
- Linux focused eval/CLI gate: `76 passed`.
- Local and Linux `compileall`: exit `0`.
- CLI help includes `--pathfinder-suffix-goal-radius-m`.
- `git diff --check`: clean.
- Habitat `ShortestPathFollower` exists in the Linux `habitat` env.

Key diagnostic results:

- Radius `1.0` run:
  - target-match calls: `1`
  - suffix episodes: `1`
  - success: `0/4`
  - SPL: `0.0`
  - SoftSPL: `0.226293450183814`
  - tv-monitor final distance: `0.7462759613990784`
- Radius `0.05` run:
  - target-match calls: `1`
  - suffix episodes: `1`
  - success: `1/4`
  - SPL: `0.24261777449152924`
  - SoftSPL: `0.24163039972246855`
  - successful episode: index `2`, id `0`, category `tv_monitor`
  - suffix activation step: `4`
  - final step: `47`
  - final distance: `0.061577994376420975`

Important interpretation:

- The `1.0` m suffix radius was too loose because the Habitat ObjectNav task
  config uses `distance_to: VIEW_POINTS` and `success_distance: 0.1`.
- The `0.05` m run gives the first nonzero official success in this diagnostic
  sequence.
- This supports the terminal-control-bottleneck hypothesis: at least one
  memory/exploration/detector episode can be solved when a competent suffix
  handles final approach and STOP.
- This does not prove the actual method is good enough for benchmark or paper
  claims, because the suffix is oracle.

Next recommended action:

1. Implement a non-oracle suffix: detector bbox plus depth projects a target
   coordinate, then a Habitat-compatible PointNav/VLFM-style local controller
   approaches that coordinate and stops.
2. Increase target-match and suffix-activation coverage; `1/4` activation is
   too sparse to support a strong memory-system claim.
3. Keep oracle suffix runs as failure decomposition only and label them
   separately in every report.

## 2026-05-31 TargetNav Target-Belief Follow-Up

Status: in progress; benchmark-valid target belief added, local backend still
not policy-ready.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-31-official-targetnav-interface.md`
- `docs/experiments/2026-05-31-official-targetnav-interface-yolo-smoke.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py

git diff --check

rsync -avR \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  source /home/badger/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_ros_packaging.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  source /home/badger/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
  PYTHONPATH=src/objectnav_core python -m compileall -q \
    src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
    src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_ros_packaging.py'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_belief_active_perception_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313'
```

What passed:

- Local focused eval/CLI/packaging gate: `83 passed`.
- Linux focused eval/CLI/packaging gate: `83 passed`.
- Local and Linux `compileall`: exit `0`.
- Local `git diff --check`: clean.
- TargetNav target-belief smoke completed and wrote:
  `runs/habitat_official_objectnav/targetnav_belief_active_perception_yolo_4ep_100steps_20260531_v1`.

What failed / negative result:

- Official TargetNav target-belief smoke remained at success `0/4`, SPL `0.0`,
  SoftSPL `0.0009902771347611306`, and mean distance
  `5.880594372749329`.
- Target-match calls increased from `1` to `48`, so target smoothing is not the
  bottleneck on this slice.
- The matched `tv_monitor` episode still spent `95` steps in
  `targetnav_occupancy_turn` and ended at distance `7.554370880126953`.

Interpretation:

- The current occupancy TargetNav backend is only a scaffold.
- For benchmark/paper data, the online policy must pair the memory/target
  belief layer with a standard sensor-only local navigation backend.
- Habitat pathfinder can remain a teacher/diagnostic to generate labels or
  decompose failures, but not an online benchmark component.

Next recommended action:

1. Build a benchmark-valid TargetNav local backend using one of:
   FMM/A* over depth-built cost maps, Habitat-baselines PointNav/DDPPO-style
   local navigation, or a learned local TargetNav policy trained from
   pathfinder teacher labels.
2. Use the existing Linux `third_party/habitat-lab/habitat-baselines` checkout
   as the first integration target.
3. Keep the memory contribution cleanly separated from local navigation in
   reports so the eventual paper claim is about lifelong object memory, not
   hand-tuned target servoing.

## 2026-05-31 TargetNav PointGoal Adapter Boundary

Status: local and Linux verification passed; online policy behavior unchanged.

Current state:

- `_targetnav_pointgoal_with_gps_compass(...)` converts TargetNav belief
  coordinates into Habitat polar `pointgoal_with_gps_compass` values.
- Input target belief remains episode-local with `x_m=right` and `z_m=forward`.
- Output is `[rho, -phi]`, matching the default Habitat polar PointGoal
  convention.
- The helper uses official GPS/compass observations and does not use
  `habitat_world`, pathfinder, shortest-path follower, or episode goal data.
- The helper is not yet consumed by an online PointNav/DDPPO policy.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-31-official-targetnav-interface.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py

git diff --check

rsync -avR \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_ros_packaging.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core python -m compileall -q \
    src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
    src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_ros_packaging.py'
```

What passed:

- Local focused eval/CLI/packaging gate: `85 passed`.
- Local `compileall`: exit `0`.
- Local `git diff --check`: clean.
- Linux focused eval/CLI/packaging gate: `85 passed`.
- Linux `compileall`: exit `0`.

What was not done:

- No online policy now consumes the PointGoal adapter.
- No new Habitat smoke was run for this slice because behavior is unchanged
  until a local navigator backend is wired in.
- No benchmark-valid success claim changes.

Next recommended action:

1. Inspect available Habitat-baselines PointNav/DDPPO checkpoint/config paths
   in the Linux mirror.
2. Add a pluggable TargetNav backend interface that can consume
   `_targetnav_pointgoal_with_gps_compass(...)`.
3. Keep a direct FMM fallback path in mind if Habitat-baselines integration is
   too heavy for the current official evaluator loop.

## 2026-05-31 TargetNav DDPPO Backend Boundary

Status: local and Linux unit verification passed; real checkpoint load/action
probe passed; four-episode official Habitat YOLO smoke completed with `0/4`
success.

Current state:

- New policy registered:
  `memory_active_perception_frontier_targetnav_ddppo`.
- The policy uses the existing detector/depth TargetNav belief and
  `_targetnav_pointgoal_with_gps_compass(...)`, then delegates local action
  selection to `HabitatPointNavDDPPOBackend`.
- `HabitatPointNavDDPPOBackend` lives in
  `src/objectnav_core/objectnav_core/evaluation/habitat_pointnav_ddppo_backend.py`.
- The backend uses lazy imports for `torch`, `gym`, and `habitat_baselines`, so
  local tests do not need the Linux Habitat runtime.
- Recurrent DDPPO state is reset once per episode; the real HM3D depth
  checkpoint produced hidden state shape `(1, 4, 512)` during the CPU probe.
- DDPPO action ids map to Habitat action names as:
  `0=stop`, `1=move_forward`, `2=turn_left`, `3=turn_right`.
- Official smoke output:
  `runs/habitat_official_objectnav/targetnav_ddppo_yolo_4ep_100steps_20260531_v1`.
  It activated DDPPO on the matched `tv_monitor` episode but official success
  remained `0/4`.

Files touched:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_pointnav_ddppo_backend.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- `src/objectnav_core/tests/test_habitat_pointnav_ddppo_backend.py`
- `docs/design/2026-05-31-official-targetnav-ddppo-backend.md`
- `docs/experiments/2026-05-31-official-targetnav-ddppo-yolo-smoke.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

Commands run:

```bash
pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_pointnav_ddppo_backend.py -q

python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_pointnav_ddppo_backend.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_pointnav_ddppo_backend.py

git diff --check

rsync -R \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_pointnav_ddppo_backend.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_pointnav_ddppo_backend.py \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/envs/habitat/bin/python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_habitat_pointnav_ddppo_backend.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  /home/badger/anaconda3/envs/habitat/bin/python -m compileall -q \
    src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
    src/objectnav_core/objectnav_core/evaluation/habitat_pointnav_ddppo_backend.py \
    src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_habitat_pointnav_ddppo_backend.py'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTHONPATH=src/objectnav_core /home/badger/anaconda3/envs/habitat/bin/python -c \
  "import numpy as np; from objectnav_core.evaluation.habitat_pointnav_ddppo_backend import HabitatPointNavDDPPOBackend; p=\"models/habitat/ddppo/hm3d_ddppo_pointnav_baselines_v1/hm3d-depth/ckpt.60.pth\"; b=HabitatPointNavDDPPOBackend.from_checkpoint(p, device=\"cpu\"); a=b.act(depth=np.full((256,256,1),0.5,dtype=np.float32), pointgoal_with_gps_compass=[1.0,0.0]); print({\"loaded\": True, \"action_id\": int(a), \"hidden_shape\": tuple(b.hidden_states.shape), \"prev_action\": int(b.prev_actions.reshape(-1)[0].item())})"'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_ddppo_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav_ddppo \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --targetnav-ddppo-checkpoint-path models/habitat/ddppo/hm3d_ddppo_pointnav_baselines_v1/hm3d-depth/ckpt.60.pth \
    --targetnav-ddppo-device cuda \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313'
```

Verification:

- Local focused eval/CLI/backend gate: `97 passed`.
- Local `compileall`: exit `0`.
- Local `git diff --check`: clean.
- Linux focused eval/CLI/backend gate in conda env `habitat`: `97 passed`.
- Linux `compileall`: exit `0`.
- Real HM3D depth DDPPO checkpoint probe passed:
  `loaded=True`, `action_id=3`, `hidden_shape=(1, 4, 512)`,
  `prev_action=3`.
- Official four-episode YOLO smoke completed with official metrics:
  success `0/4`, SPL `0.0`, SoftSPL `0.06665590634964569`, mean distance
  `5.384531855583191`.
- The smoke recorded `16` target-match calls, `18` target-match detections, and
  `95` `targetnav_ddppo_*` decisions.

What was not run:

- A larger official evaluation beyond the four-episode smoke was not run.
- No ablation was run to isolate whether remaining failure is target-belief
  noise, depth scaling, DDPPO transfer, or search/memory coverage.

Known risks:

- The first full official smoke may expose observation-contract mismatches that
  the unit/fake-env path cannot see; the four-episode smoke did not reveal a
  crash, but it did reveal unresolved policy quality issues.
- PointNav was trained on goal coordinates, while online TargetNav supplies
  detector-depth target beliefs; transfer quality is unknown until official
  metrics are collected.
- The old checkpoint compatibility shim is intentionally narrow and should only
  be used for trusted local Habitat model artifacts.

Next recommended action:

1. Inspect the policy trace for episode `tv_monitor`, where DDPPO was active
   but still ended at distance `5.570120811462402`.
2. Check whether the detector-depth target belief should be clamped, filtered,
   or converted differently before feeding PointNav.
3. If target belief quality is the blocker, train or fit a small adapter from
   detector-depth beliefs to PointNav-compatible local goals using pathfinder
   only as an offline teacher.

## 2026-05-31 TargetNav DDPPO Contract Diagnostic

Status: oracle diagnostic complete; root cause narrowed to DDPPO training
contract mismatch with the official ObjectNav environment.

Current state:

- Robust TargetNav belief smoothing was added and verified locally and on the
  Linux Habitat machine. It downweights high-uncertainty detector-depth
  measurements, especially max-range / edge-touching detections.
- The robust-belief YOLO smoke improved SoftSPL from
  `0.06665590634964569` to `0.07662481056928958` and mean distance from
  `5.384531855583191` to `5.309223055839539`, but success stayed `0/4`.
- Oracle-goal DDPPO on the `tv_monitor` episode failed under the default
  ObjectNav contract even when using Habitat-native pointgoal math:
  final distance `4.759258270263672`, success `0.0`.
- The in-repo TargetNav adapter and Habitat-native PointGoal math matched to
  about `5e-7`, so the `[rho, -phi]` sign convention is not the blocker.
- A contract ablation found the real failure mode:
  - default ObjectNav contract: failure, final distance `4.759258270263672`;
  - only `turn_angle=10`: failure but much closer, final distance
    `1.9689984321594238`;
  - checkpoint-matched turn/sensor/sliding contract: success `1.0`, final
    distance `0.029823284596204758`, SPL `0.9851193591581345`, SoftSPL
    `0.9812302867951809`.

Commands/artifacts:

```bash
runs/habitat_official_objectnav/targetnav_ddppo_robust_belief_yolo_4ep_100steps_20260531_v1
runs/habitat_official_objectnav/oracle_targetnav_ddppo_tv_monitor_20260531_v1
runs/habitat_official_objectnav/oracle_targetnav_ddppo_contract_ablation_tv_monitor_20260531_v1
```

What passed:

- Local focused eval/backend gate after robust belief smoothing: `99 passed`.
- Linux focused eval/backend gate after robust belief smoothing: `99 passed`.
- Linux `compileall`: clean.
- Oracle diagnostic with checkpoint-matched control/sensor contract succeeded
  on `tv_monitor`.

What failed:

- Benchmark-valid ObjectNav success remains `0/4`.
- Off-the-shelf HM3D PointNav DDPPO is not reliable under the default official
  ObjectNav action/sensor contract.

Next recommended action:

1. Stop investing in detector-belief smoothing as the primary fix for DDPPO
   failure; it is secondary.
2. Train or fine-tune a local PointNav/TargetNav policy under the official
   ObjectNav contract (`turn_angle=30`, 79 degree HFOV, 0.88m camera, depth
   `0.5-5.0`, no sliding), or deliberately switch to a non-DDPPO backend whose
   contract already matches the benchmark loop.
3. Keep the checkpoint-matched ObjectNav override as a diagnostic sanity check
   only. It changes benchmark conditions and must not be reported as official
   ObjectNav policy performance.

## 2026-05-31 TargetNav FMM Smoke and Official-Contract Dataset Export

Status: FMM implemented and smoke-tested; false-stop bug fixed; official
success still `0/4`. Offline oracle TargetNav local-policy dataset exporter is
implemented locally, but a real Linux Habitat export has not yet been run.

Current state:

- `memory_active_perception_frontier_targetnav_fmm` exists and uses the online
  depth-built occupancy map plus detector-depth target belief.
- Focused local and Linux tests pass for FMM registration, clear distance-field
  movement, blocked-forward replanning, fake-env policy dispatch, and the new
  no-false-stop regression.
- Initial FMM smoke wrote
  `runs/habitat_official_objectnav/targetnav_fmm_active_perception_yolo_4ep_100steps_20260531_v1`.
  It got success `0/4`, SoftSPL `0.0009902771347611306`, mean distance
  `5.880594372749329`, and only `2` target-match calls.
- Root cause found in the initial smoke: on `tv_monitor`, FMM stopped at step
  `13` with `pointgoal_with_gps_compass=[2.31275, -1.12022]` because the
  current cell was the only reachable free cell near the target in the sparse
  map.
- Fixed root cause in
  `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`:
  if FMM's selected reachable target cell is the current cell while the target
  pointgoal is outside the stop radius, it records
  `selected_current_cell_far_from_target` and falls back instead of stopping.
- Post-fix FMM smoke wrote
  `runs/habitat_official_objectnav/targetnav_fmm_no-false-stop_yolo_4ep_100steps_20260531_v1`.
  It got success `0/4`, SoftSPL `0.01716268349268174`, mean distance
  `5.758422017097473`, and `77` target-match calls. `tv_monitor` ran full
  budget instead of stopping early, but still failed through oscillatory local
  control and sparse-map fallback.
- Added offline dataset exporter files:
  - `src/objectnav_core/objectnav_core/evaluation/habitat_official_targetnav_local_policy_dataset.py`
  - `src/objectnav_core/objectnav_core/cli/export_habitat_official_targetnav_local_policy_dataset.py`
  - `src/objectnav_core/tests/test_habitat_official_targetnav_local_policy_dataset.py`
  - packaging entry point
    `objectnav_habitat_official_targetnav_local_policy_dataset`
- Exported examples are explicitly marked `source_validity=oracle_teacher_only`
  and are intended for offline training/diagnostics only, not online benchmark
  evaluation.

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_fmm_policy_records_backend_boundary \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_fmm_action_moves_toward_clear_distance_field_cell \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_fmm_action_replans_around_blocked_forward_cell \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_fmm_policy_uses_detector_depth_fmm_backend -q

pytest \
  src/objectnav_core/tests/test_habitat_official_targetnav_local_policy_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

rsync -avR \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/bin/conda run -n habitat python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_fmm_does_not_stop_when_only_current_cell_is_reachable \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_fmm_action_moves_toward_clear_distance_field_cell \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_fmm_action_replans_around_blocked_forward_cell \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_fmm_policy_uses_detector_depth_fmm_backend -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTHONPATH=src/objectnav_core /home/badger/anaconda3/bin/conda run -n habitat \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_fmm_no-false-stop_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav_fmm \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313'
```

What passed:

- FMM focused tests locally and on Linux.
- New TargetNav local-policy dataset fake-env and CLI tests locally.
- Two FMM official Habitat smokes completed without crashing and wrote official
  metrics through `habitat.Env.get_metrics`.

What failed / remains risky:

- FMM still has official success `0/4`.
- The post-fix `tv_monitor` trace shows many detector matches but oscillatory
  local behavior, not a clean approach.
- The non-`tv_monitor` episodes still mostly use fallback occupancy frontier
  because memory/category matching or detector reacquisition does not activate
  TargetNav.
- The dataset exporter has not yet run against real Habitat on Linux; only
  fake-env local tests have verified its schema and edge cases.

Next recommended action:

1. Run a tiny real Linux export with
   `objectnav_habitat_official_targetnav_local_policy_dataset`, e.g. one or two
   episodes with a small step cap, and record example/action counts.
2. Mine the post-fix FMM `tv_monitor` trace into hard local states for either
   unknown-as-cost FMM tuning or learned local-action supervision.
3. Keep FMM as the SemExp-style classical baseline, but do not claim it solves
   ObjectNav until official success improves beyond `0/4`.

## 2026-05-31 Official Memory Baseline Comparison

Status: first official comparison table pipeline implemented and smoke-run.
The result is diagnostic only; it is not a performance claim.

Current state:

- Added comparison module and CLI:
  - `src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_comparison.py`
  - `src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_comparison.py`
  - entry point `objectnav_habitat_official_memory_comparison`
- The comparison requires three labels: `memory_guided`, `no_memory`, and
  `naive_count`.
- It validates `official_metrics.measure_source == habitat.Env.get_metrics`
  before writing `comparison.json`, `comparison.csv`, and `comparison.md`.
- Added `--positive-count-threshold` to official memory discovery. Threshold
  `2` produces a documented positive-only `naive_count` prior artifact.
- Design doc:
  `docs/design/2026-05-31-official-memory-baseline-comparison.md`
- Experiment report:
  `docs/experiments/2026-05-31-official-memory-baseline-comparison.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_comparison.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_comparison.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_comparison.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_discovery.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_discovery.py

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m pytest \
    src/objectnav_core/tests/test_habitat_official_memory_comparison.py \
    src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
    src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
    src/objectnav_core/tests/test_ros_packaging.py -q'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_memory_discovery \
    --output runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_naive_count_threshold2_20260531_v1 \
    --policy occupancy_frontier \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --min-detection-confidence 0.25 \
    --positive-count-threshold 2 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 50 \
    --seed 313'

ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_memory_comparison \
    --output runs/habitat_official_objectnav/memory_baseline_comparison_yolo_4ep_100steps_20260531_v1 \
    --memory-guided-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --naive-count-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_naive_count_threshold2_20260531_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313'
```

Verification:

- Local focused tests: `16 passed`.
- Local `compileall`: clean.
- Linux focused tests in conda env `habitat`: `16 passed`.
- Linux `compileall`: clean.
- Positive-only naive prior export completed with `8` exported anchors.
- Official comparison completed and wrote Habitat official metrics.

Official comparison result:

| Method | SR | SPL | SoftSPL | DistanceToGoal |
|---|---:|---:|---:|---:|
| `memory_guided` | 0.0000 | 0.0000 | 0.0172 | 5.7584 |
| `no_memory` | 0.0000 | 0.0000 | 0.0332 | 5.6376 |
| `naive_count` | 0.0000 | 0.0000 | 0.0010 | 5.8806 |

What failed / remains risky:

- All rows have official success `0/4` and SPL `0.0`.
- `memory_guided` is worse than `no_memory` on SoftSPL and final distance in
  this smoke, so there is no performance claim yet.
- The current `memory_guided` row is still dominated by low-level FMM/TargetNav
  behavior, not by the intended upper-layer memory contribution.
- `naive_count` is positive-only in prior construction; the online trace does
  not yet expose a separate count gate after loading the prior.

Next recommended action:

1. Treat this comparison table as the required official-metric gate for future
   memory changes.
2. Build the black-box navigation boundary so the same memory table can be rerun
   with a stronger navigator without changing memory logic.
3. Use the existing comparison CLI after each backend/memory change; do not
   claim improvement unless `memory_guided` clearly beats both `no_memory` and
   `naive_count` on official metrics or solves a separate documented lifelong
   drift/stale-memory failure mode.

## 2026-05-31 Black-Box Navigation Backend Boundary

Status: core boundary and oracle executor implemented locally; official Habitat
policy integration is still the next step.

Current state:

- Added core navigation package files:
  - `src/objectnav_core/objectnav_core/navigation/backend.py`
  - `src/objectnav_core/objectnav_core/navigation/habitat_oracle.py`
  - `src/objectnav_core/objectnav_core/navigation/__init__.py`
- `NavigationBackend` now defines the small black-box interface:
  `get_pose`, `go_to`, `explore`, `status`, and `cancel`.
- `LegacyNavigationClientBackend` wraps existing clients such as
  `DiscreteStepNavigationClient`.
- `HabitatOracleFollowerBackend` wraps Habitat's shortest-path follower for
  oracle upper-bound simulation work and exposes `next_action()` for official
  discrete action loops.
- `OfficialPathfinderSuffixController` now uses `HabitatOracleFollowerBackend`
  internally, so the existing
  `memory_active_perception_frontier_pathfinder_suffix` diagnostic exercises
  the shared backend boundary.
- Oracle statuses include `benchmark_valid=False` and `privileged_oracle=True`.
  This backend is for upper-bound diagnostics, not official benchmark claims.
- Design and plan files:
  - `docs/design/2026-05-31-black-box-navigation-backend.md`
  - `docs/superpowers/plans/2026-05-31-black-box-navigation-backend.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_navigation_backend.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_navigation_backend.py \
  src/objectnav_core/tests/test_habitat_action_follower.py -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core/navigation \
  src/objectnav_core/tests/test_navigation_backend.py

rsync -avR \
  src/objectnav_core/objectnav_core/navigation/backend.py \
  src/objectnav_core/objectnav_core/navigation/habitat_oracle.py \
  src/objectnav_core/objectnav_core/navigation/__init__.py \
  src/objectnav_core/tests/test_navigation_backend.py \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m pytest \
    src/objectnav_core/tests/test_navigation_backend.py \
    src/objectnav_core/tests/test_habitat_action_follower.py -q'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m compileall -q \
    src/objectnav_core/objectnav_core/navigation \
    src/objectnav_core/tests/test_navigation_backend.py'
```

Verification:

- Red test failed before implementation with missing
  `objectnav_core.navigation.habitat_oracle`.
- Factory-error regression failed before the fix because a fallback follower
  factory exception propagated instead of returning failed backend status.
- Focused navigation backend tests: `12 passed`.
- Navigation backend plus existing Habitat action follower tests: `16 passed`.
- Local `compileall` over navigation code and tests: clean.
- Local `git diff --check`: clean.
- Linux conda env `habitat` navigation backend plus existing Habitat action
  follower tests: `16 passed`.
- Linux conda env `habitat` compileall over navigation code and tests: clean.
- Official-controller backend-factory regression failed before evaluator
  integration, then passed after `OfficialPathfinderSuffixController` was
  routed through the oracle backend.
- Local official evaluator plus navigation regression: `102 passed`.
- Linux official evaluator plus navigation regression in conda env `habitat`:
  `102 passed`.
- Linux backend-wired pathfinder suffix smoke:
  `runs/habitat_official_objectnav/pathfinder_suffix_oracle_backend_yolo_4ep_100steps_radius005_20260531_v1`.
  Metrics: success `1/4`, SPL `0.24261777449152924`, SoftSPL
  `0.24163039972246855`, mean distance `4.007396151311696`.
  The successful trace exposes `backend_id=pathfinder_suffix_oracle`,
  `privileged_oracle=true`, and `benchmark_valid=false`.

What failed / remains risky:

- The new backend is connected to the existing pathfinder suffix diagnostic,
  but not yet to the official memory comparison CLI as a selectable executor.
- The Linux diagnostic smoke uses `HabitatOracleFollowerBackend`, but it is
  still oracle-only and invalid for benchmark claims.
- The oracle backend requires explicit Habitat 3D goal metadata unless the goal
  is tagged `habitat_world`; episode-relative memory still needs a documented
  frame bridge before this can be used as a memory upper-bound experiment.

Next recommended action:

1. Add a backend selector to the official memory/TargetNav policy path so
   `HabitatOracleFollowerBackend`, FMM, DDPPO/learned local policy, and later
   Nav2 adapters can execute the same memory candidate output.
2. Rerun the official memory comparison table with non-oracle backends before
   making any benchmark-facing performance claim.

## 2026-05-31 Official TargetNav Backend Selector

Status: implemented locally and covered by focused tests.

Current state:

- The base official memory TargetNav policy
  `memory_active_perception_frontier_targetnav` now accepts a first-class
  `targetnav_backend` selector.
- The CLI exposes this as `--targetnav-backend` with supported choices from
  `SUPPORTED_TARGETNAV_BACKENDS`.
- The protocol manifest reports the effective backend for base-policy
  `occupancy_grid`, `fmm_grid`, `ddppo_pointnav`, and `oracle_follower`.
- `oracle_follower` TargetNav runs are marked with
  `source_validity=oracle_diagnostic_only` and
  `invalid_for_benchmark_claim_reason=targetnav_oracle_backend_diagnostic`.
- Legacy alias policies remain valid:
  `memory_active_perception_frontier_targetnav_fmm` and
  `memory_active_perception_frontier_targetnav_ddppo`.

Files touched:

- `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`
- `docs/design/2026-05-31-official-targetnav-backend-selector.md`
- `docs/experiments/2026-05-31-official-targetnav-backend-selector-smoke.md`
- `docs/superpowers/plans/2026-05-31-official-targetnav-backend-selector.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

Commands run:

```bash
pytest src/objectnav_core/tests/test_habitat_official_objectnav_cli.py::test_official_objectnav_cli_passes_targetnav_backend_option \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_oracle_backend_selector \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_fmm_backend_selector \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_ddppo_backend_selector -q

pytest src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_interface_boundary \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_oracle_backend_selector \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_fmm_backend_selector \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_ddppo_backend_selector \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_fmm_policy_records_backend_boundary \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_ddppo_policy_records_backend_boundary \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_policy_can_use_oracle_follower_backend_selector -q

pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_navigation_backend.py -q

python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/navigation

git diff --check

rsync -avR \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  docs/design/2026-05-31-official-targetnav-backend-selector.md \
  docs/superpowers/plans/2026-05-31-official-targetnav-backend-selector.md \
  docs/devlog/2026-05.md \
  docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py::test_official_objectnav_cli_passes_targetnav_backend_option \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_oracle_backend_selector \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_fmm_backend_selector \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_ddppo_backend_selector -q'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_navigation_backend.py -q'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m compileall \
    src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
    src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
    src/objectnav_core/objectnav_core/navigation'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_oracle_backend_selector_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav \
    --targetnav-backend oracle_follower \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313'
```

Verification:

- Initial selector tests failed as expected before implementation: `4 failed`.
- Selector tests after implementation: `4 passed`.
- Focused CLI/TargetNav regression: `19 passed`.
- Broader local evaluator/CLI/navigation regression: `114 passed`.
- `compileall`: clean.
- `git diff --check`: clean.
- Linux selector tests: `4 passed`.
- Linux broader evaluator/CLI/navigation regression: `114 passed`.
- Linux `compileall`: clean.
- Linux 1-episode smoke validated the manifest but did not activate the oracle
  follower because there were no target matches.
- Linux 4-episode smoke activated the oracle follower in the tv-monitor episode.
  Metrics: success `0/4`, SPL `0.0`, SoftSPL `0.226293450183814`, mean
  distance `4.17857064306736`, target-match detections `1`, and
  `38` `follow_pathfinder_suffix` decisions. The activated trace records
  `backend_id=pathfinder_suffix_oracle`, `reason=oracle_follower_stop`,
  `privileged_oracle=true`, and `benchmark_valid=false`.

What failed / remains risky:

- A first broader pytest command used a stale test name
  `test_memory_active_perception_targetnav_policy_records_backend_boundary` and
  therefore collected no tests. The command was corrected to
  `test_memory_active_perception_targetnav_policy_records_interface_boundary`.
- Oracle-backed runs are still diagnostic only and invalid for benchmark-facing
  ObjectNav claims.

Next recommended action:

1. Compare the same base TargetNav policy with `targetnav_backend=fmm_grid`
   and `targetnav_backend=ddppo_pointnav` where checkpoint/runtime contracts
   are available.
2. Use oracle diagnostics only to decompose memory quality from local-control
   failures; keep
   official benchmark claims on non-oracle backends.

## 2026-05-31 Official Memory Anchor TargetNav Backend

Status: implemented locally and synced to the Linux Habitat host.

Current state:

- Matching `episode_start_relative` memory anchors now become TargetNav goals in
  the base `memory_active_perception_frontier_targetnav` policy.
- For `targetnav_backend=fmm_grid` and `ddppo_pointnav`, the anchor is passed as
  `target_goal` with `targetnav_estimator=memory_anchor`.
- For `targetnav_backend=oracle_follower`, the anchor is converted from
  episode-relative `x/z` into a Habitat world goal using episode
  `start_position` and `start_rotation`.
- If the oracle path lacks episode start pose, the policy records
  `fallback_reason=missing_episode_start_pose_for_memory_anchor` and falls back
  instead of crashing.
- The design and experiment report are:
  - `docs/design/2026-05-31-official-memory-anchor-targetnav-backend.md`
  - `docs/experiments/2026-05-31-official-memory-anchor-targetnav-backend-smoke.md`

Commands run:

```bash
pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_fmm_backend_executes_matching_memory_anchor \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_oracle_backend_executes_matching_memory_anchor \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_oracle_memory_anchor_missing_start_pose_falls_back -q

pytest src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_navigation_backend.py -q

python -m compileall src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py

git diff --check

rsync -avR \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  docs/design/2026-05-31-official-memory-anchor-targetnav-backend.md \
  docs/superpowers/plans/2026-05-31-official-memory-anchor-targetnav-backend.md \
  badger@100.88.131.52:/home/badger/Desktop/dual-anchor-lifelong-objectnav/

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m pytest \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_navigation_backend.py -q'

ssh -o BatchMode=yes badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/targetnav_memory_anchor_oracle_backend_yolo_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav \
    --targetnav-backend oracle_follower \
    --memory-prior-path runs/habitat_official_objectnav/discovery_yolo_world_valmini_4ep_50steps_20260530_v1/memory_prior.json \
    --detector yolo_world \
    --detector-weights yolov8s-worldv2.pt \
    --detector-conf 0.25 \
    --detector-device auto \
    --target-detector-min-confidence 0.25 \
    --categories bed,chair,plant,sofa,toilet,tv_monitor \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313'
```

Verification:

- Initial memory-anchor backend tests failed as expected before implementation:
  `3 failed`.
- Memory-anchor backend tests after implementation: `3 passed`.
- Local focused evaluator/CLI/navigation regression: `117 passed`.
- Local `compileall`: clean.
- Local `git diff --check`: clean.
- Linux memory-anchor backend tests: `3 passed`.
- Linux focused evaluator/CLI/navigation regression: `117 passed`.
- Linux `compileall`: clean.
- Linux memory-anchor oracle smoke activated the remembered tv-monitor anchor at
  step `0`, with `follow_pathfinder_suffix=10`, zero fresh target matches, and
  oracle backend status `SUCCEEDED`, `privileged_oracle=true`,
  `benchmark_valid=false`.

What failed / remains risky:

- Official metrics stayed poor: success `0/4`, SPL `0.0`, SoftSPL
  `0.044980353551202196`, mean distance `5.548277020454407`.
- The tv-monitor memory anchor led the oracle backend to a location far from the
  official target, ending at distance `6.225101470947266`.
- This is not a backend-control failure anymore; it is evidence that the current
  YOLO-discovered memory prior is poorly localized or stale for this query.
- Oracle-backed numbers remain diagnostic only.

Next recommended action:

1. Add a ground-truth/oracle memory-prior upper-bound exporter so the transform
   can be validated against perfect memory and the gap to YOLO-discovered memory
   can be measured cleanly.
2. Then improve discovered-memory reliability with multi-view fusion,
   stale-anchor rejection, or learned candidate scoring.

## 2026-05-31 Official Grounding-DINO Memory Line

Status: implemented locally, synced to Linux, first diagnostic smoke completed.

Current state:

- Official detector-backed memory discovery now defaults to `grounding_dino`.
- Omitted detector weights now resolve per backend:
  - `grounding_dino` -> `IDEA-Research/grounding-dino-tiny`
  - `yolo_world` -> `yolov8s-worldv2.pt`
- Query/eval, memory-comparison, and candidate-label export CLIs keep their
  detector behavior but no longer pass YOLO weights when an operator explicitly
  selects `--detector grounding_dino` and omits `--detector-weights`.
- Design and experiment docs:
  - `docs/design/2026-05-31-official-grounding-dino-memory-line.md`
  - `docs/experiments/2026-05-31-official-grounding-dino-memory-discovery-smoke.md`

Commands run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_comparison.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_grounding_dino_adapter.py -q

python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check

rsync -avR \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_discovery.py \
  src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_comparison.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_viewpoint_restore_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_state_restore_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_option_value_dataset.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_memory_comparison.py \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  docs/design/2026-05-31-official-grounding-dino-memory-line.md \
  docs/superpowers/plans/2026-05-31-official-grounding-dino-memory-line.md \
  badger@100.88.131.52:~/Desktop/dual-anchor-lifelong-objectnav/

ssh -o BatchMode=yes badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && \
  source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
    src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_habitat_official_memory_comparison.py \
    src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
    src/objectnav_core/tests/test_grounding_dino_adapter.py -q'

ssh -o BatchMode=yes badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && \
  source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_memory_discovery \
    --output runs/habitat_official_objectnav/grounding_dino_discovery_prior_4ep_100steps_20260531_v1 \
    --max-episodes 4 \
    --max-steps 100 \
    --grounding-dino-max-image-side 384 \
    --min-detection-confidence 0.25'

ssh -o BatchMode=yes badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && \
  source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
  HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/grounding_dino_memory_oracle_backend_4ep_100steps_20260531_v1 \
    --policy memory_active_perception_frontier_targetnav \
    --memory-prior-path runs/habitat_official_objectnav/grounding_dino_discovery_prior_4ep_100steps_20260531_v1/memory_prior.json \
    --targetnav-backend oracle_follower \
    --max-episodes 4 \
    --max-steps 100 \
    --pathfinder-suffix-goal-radius-m 0.05'
```

Verification:

- Local focused tests: `62 passed`.
- Local compileall and `git diff --check`: clean.
- Linux focused tests: `62 passed`.
- Linux DINO discovery smoke:
  - raw detections `590`
  - label-filtered detections `589`
  - exported anchors `1`
  - anchor source
    `grounding_dino:IDEA-Research/grounding-dino-tiny:episode=5:step=0:detection=2`
- DINO chair anchor x/z error to oracle chair anchor: `5.648712 m`.
- DINO prior + oracle backend diagnostic:
  - success rate `0/4`
  - SPL `0.0`
  - SoftSPL `0.0917306745160412`
  - mean distance-to-goal `5.14483118057251`

What failed / remains risky:

- The DINO integration works, but the first official memory prior is not useful
  yet: only one target anchor was exported, and it is far from the oracle chair
  anchor.
- This run should be treated as a negative diagnostic, not a paper result.
- The next bottleneck is memory-anchor quality from detector evidence:
  viewpoint coverage, depth projection, and multi-view fusion.
- The vertical-aware oracle ceiling still has a chair failure (`3/4` success in
  the latest radius `0.05` smoke), so keep it diagnostic-only.

Next recommended action:

1. Add a visibility-aware DINO discovery diagnostic that records target-visible
   oracle rows, detector positives, and projected-anchor error against oracle
   anchors.
2. Use multi-view DINO detections or learned candidate scoring before rerunning
   larger official memory comparisons.
3. Debug the vertical oracle chair failure separately so the oracle ceiling is
   a cleaner upper bound.
