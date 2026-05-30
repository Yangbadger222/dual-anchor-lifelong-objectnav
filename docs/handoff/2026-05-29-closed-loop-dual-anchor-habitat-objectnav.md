# Handoff: Closed-Loop Dual-Anchor Habitat ObjectNav

Date: 2026-05-30
Owner: Codex  
Status: In Progress

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
