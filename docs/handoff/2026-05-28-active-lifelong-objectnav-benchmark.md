# Handoff: Active Lifelong ObjectNav Benchmark

Date: 2026-05-28  
Owner: Codex  
Status: Ready for Habitat Port

## Current State

The repository now has a deterministic active lifelong ObjectNav benchmark in
`objectnav_core`. It runs a multi-room / corridor fixture with three episodes:
discovery, reuse from a different start, and stale-memory repair.

The first artifact is:

`runs/lifelong_objectnav/active_memory_guided_benchmark_v1`

Headline local result:

- `memory_guided`: `3/3` success, `64.651365 m`, `18` frontier selections.
- `frontier_only`: `2/3` success, `127.497071 m`, `76` frontier selections.
- Path reduction ratio: `0.492919`.
- Relocation recorded by memory-guided stale repair: `true`.

This is a synthetic offline result. It is not a Habitat benchmark result and
should not be presented as a paper claim without the next Habitat validation.

## Files Touched

- `docs/design/2026-05-28-memory-guided-active-objectnav-benchmark.md`
- `docs/experiments/2026-05-28-active-lifelong-objectnav-benchmark-v1.md`
- `docs/devlog/2026-05.md`
- `src/objectnav_core/objectnav_core/models/__init__.py`
- `src/objectnav_core/objectnav_core/mapping/fixtures.py`
- `src/objectnav_core/objectnav_core/mapping/frontiers.py`
- `src/objectnav_core/objectnav_core/planning/frontier_policies.py`
- `src/objectnav_core/objectnav_core/planning/memory_guided.py`
- `src/objectnav_core/objectnav_core/evaluation/lifelong_objectnav_benchmark.py`
- `src/objectnav_core/objectnav_core/cli/run_lifelong_objectnav_benchmark.py`
- `src/objectnav_core/setup.py`
- `pyproject.toml`
- `src/objectnav_core/tests/test_lifelong_objectnav_benchmark.py`
- `src/objectnav_core/tests/test_cli_runner.py`

## Commands Run

```bash
git status --short --branch
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_lifelong_objectnav_benchmark.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_lifelong_objectnav_benchmark.py src/objectnav_core/tests/test_cli_runner.py -q
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_lifelong_objectnav_benchmark --output runs/lifelong_objectnav/active_memory_guided_benchmark_v1
ssh badger@100.88.131.52 'source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && python -m pip install "pydantic>=2,<3" PyYAML'
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && python -m pip install eval_type_backport && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_lifelong_objectnav_benchmark.py src/objectnav_core/tests/test_cli_runner.py -q'
ssh badger@100.88.131.52 'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && rm -rf runs/lifelong_objectnav/active_memory_guided_benchmark_v1 && PYTHONPATH=src/objectnav_core python -m objectnav_core.cli.run_lifelong_objectnav_benchmark --output runs/lifelong_objectnav/active_memory_guided_benchmark_v1'
```

## Verification

Passed locally:

- `3` active benchmark tests.
- `5` focused active benchmark + CLI tests.
- Artifact generation under
  `runs/lifelong_objectnav/active_memory_guided_benchmark_v1`.

Passed on Linux in `conda habitat` after pulling commit `adbd08f`:

- Focused benchmark/CLI tests: `5` passed.
- Benchmark artifact reproduced the local headline metrics:
  `memory_guided` `3/3`, `frontier_only` `2/3`, path reduction ratio
  `0.492919`, frontier reduction `58`.

Verification still needed:

- Full `objectnav_core` test suite after any follow-up edits.
- Habitat active port and Grounding-DINO run.

## Known Risks

- `frontier_only` currently fails stale repair in the synthetic fixture. This is
  useful evidence that memory repair matters, but it also means the current
  comparison mixes success and path-efficiency differences.
- The memory utility score is still a v1 hand-authored score. It should be
  replaced or extended with uncertainty-aware expected utility before a serious
  paper claim.
- Observations are config-truth, not Grounding-DINO.
- The navigation backend is A* over a designed grid, not Habitat actions or
  real Nav2.
- The Linux `conda habitat` environment is Python `3.9.23`; it needs
  `eval_type_backport` for Pydantic v2 model annotations. This dependency is
  now declared, but the remote environment must install it before tests pass.

## Next Recommended Step

1. Pull this code on Linux.
2. Run the focused active benchmark tests in `conda habitat`.
3. Add a Habitat active bridge that reuses the same candidate-scoring idea but
   executes Grounding-DINO RGB/depth-noise ObjectNav episodes.
4. Report path length, success, repeated exploration, stale-memory repair, and
   detector diagnostics. Stop optimizing replay trust-row counts as the primary
   target.

## Context for Next Contributor

The user explicitly wants a top-tier robotics direction, not a small replay
gate tweak. Treat this benchmark as the bridge from proof-of-mechanism to
Habitat/robot validation. The current code is intentionally conservative and
hardware-independent so it can later connect to ROS 2/Nav2 and language queries.
