# Experiment Report: Official Detector Memory Discovery Loop Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Can an injected detector running inside the official observation loop produce
an episode-relative memory prior that the official `memory_guided_frontier`
policy can load and act on?

## Hypothesis

A matching detector bbox with valid depth should project into an
`episode_start_relative` anchor, serialize through `memory_prior.json`, and be
selected by `memory_guided_frontier` without falling back to occupancy
frontier.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, uncommitted working tree |
| Machine | macOS local workspace and Linux mirror `100.88.131.52` |
| Dataset / bag / map | Synthetic fake Habitat-like observations |
| Simulator / robot | Fake official-env fixtures; no live Habitat simulator in this smoke |
| Key parameters | `policy=noop` for discovery, `memory_guided_frontier` for query, `max_episodes=1`, `max_steps<=3`, `max_anchors_per_episode=1` cap regression |

## Command

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests -q

PYTHONPATH=src/objectnav_core python -m compileall -q \
  src/objectnav_core/objectnav_core src/objectnav_core/tests

git diff --check
```

Linux focused command:

```bash
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  PYTHONPATH=src/objectnav_core \
  python -m pytest \
    src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
    src/objectnav_core/tests/test_official_episode_memory.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
    src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
    src/objectnav_core/tests/test_lifecycle_memory_prior_export.py -q
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Discovery unit/integration tests | 5 passed | Local fake-env detector smoke |
| Focused official-memory tests | 44 passed | Local final run |
| Full local test suite | 335 passed | Local final run |
| Local compile check | 0 failures | `compileall` clean |
| Local whitespace check | 0 failures | `git diff --check` clean |
| Linux focused official-memory tests | 44 passed | Conda env `habitat` |
| Linux whitespace check | 0 failures | `git diff --check` clean |

## Observations

- The discovery prior round-trips through `load_official_memory_prior`.
- Generated anchors are `coordinate_frame="episode_start_relative"`.
- A generated forward anchor makes `memory_guided_frontier` move toward memory
  and then stop at memory radius without `fallback_reason`.
- The confidence-cap regression initially failed because the loop kept detector
  order. Sorting projected candidates by confidence fixed this.

## Result

The detector-injected discovery core loop is a working bridge artifact:
official RGB-D observations can produce actionable episode-relative prior JSON
for the current official memory policy.

This is not a benchmark result. It uses synthetic fake observations and an
injected static detector, not a real detector over Habitat discovery/query
episodes.

## Follow-up

- Add real detector model wiring or a discovery CLI.
- Run a documented official Habitat discovery/query smoke with generated
  priors.
- Add detector-backed stop confirmation before using the policy for stronger
  claims.
