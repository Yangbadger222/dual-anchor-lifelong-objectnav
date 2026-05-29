# Handoff: Closed-Loop Dual-Anchor Habitat ObjectNav

Date: 2026-05-29  
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
  shared gate.
- Repaired-memory direct route accounting for repeated stale queries.
- Expected-utility memory-vs-frontier decisions using `--memory-valid-prior`.
- Category-balanced group selection before duplicate categories when
  `--max-groups` is set.
- A Markdown and Chinese HTML experiment report for the latest Habitat
  oracle/action smoke.
- A Markdown experiment report for the Grounding-DINO candidate-gate smoke:
  `docs/experiments/2026-05-29-habitat-closed-loop-grounding-dino-candidate-gate.md`.

Not implemented yet:

- Grounding-DINO per-step Habitat closed-loop perception. The current detector
  path verifies selected memory/fallback candidate views only.
- True Habitat frontier mapping/exploration policy.
- Natural object relocation/removal in Habitat.
- SPL-like action-level ObjectNav metrics for memory-vs-frontier decisions.

## Files Touched

- `docs/design/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- `docs/devlog/2026-05.md`
- `docs/experiments/2026-05-29-dual-anchor-pressure-smoke.md`
- `docs/experiments/2026-05-29-closed-loop-dual-anchor-grid-smoke.md`
- `docs/experiments/2026-05-29-habitat-closed-loop-grounding-dino-candidate-gate.md`
- `docs/experiments/2026-05-29-habitat-closed-loop-dual-anchor-oracle-action-smoke.md`
- `docs/experiments/2026-05-29-habitat-closed-loop-dual-anchor-oracle-action-smoke.zh.html`
- `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- `docs/superpowers/plans/2026-05-29-closed-loop-dual-anchor-grid-benchmark.md`
- `docs/superpowers/plans/2026-05-29-habitat-closed-loop-dual-anchor-smoke.md`
- `src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`
- `src/objectnav_core/objectnav_core/cli/run_closed_loop_dual_anchor_benchmark.py`
- `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- `src/objectnav_core/objectnav_core/evaluation/closed_loop_dual_anchor_benchmark.py`
- `src/objectnav_core/objectnav_core/geometry/dual_anchor.py`
- `src/objectnav_core/objectnav_core/evaluation/dual_anchor_pressure.py`
- `src/objectnav_core/objectnav_core/cli/run_dual_anchor_pressure.py`
- `src/objectnav_core/objectnav_core/planning/memory_guided.py`
- `src/objectnav_core/tests/test_closed_loop_dual_anchor_benchmark.py`
- `src/objectnav_core/tests/test_closed_loop_dual_anchor_cli.py`
- `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`
- `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py`
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

## Known Risks

- The current pressure runner is deterministic synthetic math, not Habitat.
- The closed-loop grid harness is option-level and config-truth, not Habitat.
- The Habitat closed-loop runner is currently option-level. It executes real
  Habitat GreedyGeodesic routes and can use Grounding-DINO at selected
  memory/fallback candidate views, but it does not yet run per-action perception
  or true frontier mapping.
- `navmesh_frontier` is target-agnostic with respect to sampled route goals, but
  it is still a navmesh probe approximation, not an occupancy frontier built
  from depth observations. It has only been verified locally with unit tests and
  still needs a Linux Habitat smoke.
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

## Next Recommended Step

1. Run a Linux Habitat smoke with `--frontier-mode navmesh_frontier` and inspect
   probe source/evidence fields before scaling.
2. Add a true occupancy/frontier exploration policy; `navmesh_frontier` is only
   an intermediate target-agnostic probe baseline.
3. Move Grounding-DINO from selected candidate-view verification to per-action
   observation and stopping decisions.
4. Implement natural Habitat object relocation/removal or a clearly labeled
   semantic-object hide/replace protocol.
5. Scale the balanced runs beyond six groups and report confidence intervals.
6. Estimate `memory_valid_prior` from evidence, covariance, object class, and
   session age instead of fixing it by hand.
7. Convert the smoke metrics into SPL-like metrics only after per-action
   perception and a real frontier policy are in place.

## Context for Next Contributor

The target paper story is now stricter: show that dual-anchor memory helps
lifelong ObjectNav under map-frame restarts, localization uncertainty, instance
ambiguity, and stale objects. A small advantage over a weak search proxy is not
enough.
