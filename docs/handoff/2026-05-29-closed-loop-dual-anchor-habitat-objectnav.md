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
  has preflight and an oracle/action-level HM3D smoke path. It reuses existing
  Habitat episode/group selection and GreedyGeodesic route execution.

Not implemented yet:

- Grounding-DINO per-step Habitat closed-loop perception.
- True Habitat frontier mapping/exploration policy.
- Natural object relocation/removal in Habitat.
- SPL-like action-level ObjectNav metrics for memory-vs-frontier decisions.

## Files Touched

- `docs/design/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- `docs/devlog/2026-05.md`
- `docs/experiments/2026-05-29-dual-anchor-pressure-smoke.md`
- `docs/experiments/2026-05-29-closed-loop-dual-anchor-grid-smoke.md`
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
```

Linux command to run after push:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
git pull --ff-only origin codex/habitat-memory-lifecycle
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_dual_anchor_pressure.py src/objectnav_core/tests/test_dual_anchor_pressure_cli.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_dual_anchor_pressure --output runs/dual_anchor_pressure/pressure_cli_smoke_v1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_closed_loop_dual_anchor_benchmark.py src/objectnav_core/tests/test_closed_loop_dual_anchor_cli.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_closed_loop_dual_anchor_benchmark --output runs/dual_anchor_grid/closed_loop_smoke_v1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val --scene-root datasets/habitat/scene_datasets/hm3d --output runs/habitat_closed_loop_dual_anchor/oracle_action_smoke_v1 --target-categories plant,toilet --max-groups 1
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

Pending:

- Linux pull and Habitat oracle/action smoke after commit/push.

## Known Risks

- The current pressure runner is deterministic synthetic math, not Habitat.
- The closed-loop grid harness is option-level and config-truth, not Habitat.
- The Habitat closed-loop runner is currently oracle/action-level. It executes
  real Habitat GreedyGeodesic routes, but it does not yet run Grounding-DINO
  per-step perception or true frontier mapping.
- The first Linux Habitat smoke selected a plant group where direct memory and
  direct fallback routes were identical. `frontier_only` has since been changed
  to use deterministic `frontier_proxy_waypoints` before the fallback goal;
  rerun the smoke before interpreting policy deltas.
- The current grid smoke does not beat `naive_count`; after the shared gate,
  memory-guided and naive-count tie. Treat this as plumbing/pressure validation,
  not a headline result.
- The previous lifecycle results should not be promoted as the main benchmark.
- The next Habitat implementation must give frontier/no-memory/naive baselines
  the same perception, action budget, and gate semantics as memory-guided.
- Natural staleness may require a careful Habitat object hide/move protocol if
  HM3D mesh-level object relocation is not clean.

## Next Recommended Step

1. Push the closed-loop grid harness.
2. Verify it on Linux in the `habitat` conda environment.
3. Rerun the Habitat oracle/action smoke with `--max-groups 1`.
4. Replace oracle visibility with Grounding-DINO observations and add object
   relocation/removal pressure.

## Context for Next Contributor

The target paper story is now stricter: show that dual-anchor memory helps
lifelong ObjectNav under map-frame restarts, localization uncertainty, instance
ambiguity, and stale objects. A small advantage over a weak search proxy is not
enough.
