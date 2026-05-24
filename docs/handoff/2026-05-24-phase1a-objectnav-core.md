# Handoff: Phase 1A ObjectNav Core Slice

Date: 2026-05-24  
Owner: Codex  
Status: Ready for Review

## Current State

Phase 1A now has a first ROS-free executable core under `src/objectnav_core`.

The user's current computer does not have ROS installed. The project is still ROS 2-oriented: `src/objectnav_core` now has `ament_python` package metadata so it can later be built with `colcon` on a ROS 2 machine or container. Local development on this computer should continue through pytest.

Implemented:

- Pydantic scene, anchor, pose, memory, observation, event, and metric models.
- A deterministic straight-corridor fixture with boundary walls, known start area, and unknown forward area.
- Forward-sector map reveal.
- Frontier extraction and known-side frontier viewpoint planning.
- Wall-adjacent water-dispenser verification viewpoint planning.
- Config-truth fake detector with range, horizontal FOV, active-object, and line-of-sight checks.
- Deterministic discrete-step navigation client.
- SQLite memory store with object records, object observations, object relations, trial events, indexes, and JSON export.
- Phase 1A trial runner for:
  - `discover_and_verify`
  - `reuse_same_start`
  - `reuse_different_start`
  - `missing_and_relocation`
- CLI artifact runner:
  - `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`
  - writes `memory.sqlite`, `summary.json`, `memory_snapshot.json`, and `events.jsonl`
- ROS 2 `ament_python` metadata for `objectnav_core`: `package.xml`, `setup.py`, `setup.cfg`, and `resource/objectnav_core`.

No ROS 2, Nav2, TF, RTK, real detector, VLM, or robot adapter code has been added.

## Files Touched

- `pyproject.toml`
- `src/objectnav_core/package.xml`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/setup.cfg`
- `src/objectnav_core/resource/objectnav_core`
- `.gitignore`
- `README.md`
- `docs/design/2026-05-24-system-architecture.md`
- `docs/superpowers/plans/2026-05-24-phase1a-objectnav-core.md`
- `docs/devlog/2026-05.md`
- `src/objectnav_core/objectnav_core/**`
- `src/objectnav_core/tests/**`
- `runs/phase1a/latest/**`

## Commands Run

```bash
python3 -m pip install pytest
python3 -m pytest --version
python3 -m pytest src/objectnav_core/tests/test_models.py -v
python3 -m pytest src/objectnav_core/tests/test_mapping.py -v
python3 -m pytest src/objectnav_core/tests/test_simulation.py -v
python3 -m pytest src/objectnav_core/tests/test_trials.py -v
python3 -m pytest src/objectnav_core/tests -v
python3 -m compileall -q src/objectnav_core/objectnav_core
python3 -m pytest src/objectnav_core/tests/test_ros_packaging.py -v
python3 -m pytest src/objectnav_core/tests/test_cli_runner.py -v
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
rg -n "rclpy|nav2|NavigateToPose|sensor_msgs|geometry_msgs|tf2_ros|/global_costmap|/tf" src/objectnav_core/objectnav_core src/objectnav_core/tests
rg -n "TODO|FIXME|Pending|<Title>|<name|placeholder|YYYY-MM-DD" README.md pyproject.toml docs/superpowers/plans/2026-05-24-phase1a-objectnav-core.md docs/devlog/2026-05.md docs/handoff/2026-05-24-phase1a-objectnav-core.md src/objectnav_core
```

## Verification

Passed:

- `python3 -m pytest src/objectnav_core/tests -v`
- 14 tests passed after adding the CLI artifact runner.
- `python3 -m compileall -q src/objectnav_core/objectnav_core`
- `python3 -m pytest src/objectnav_core/tests/test_ros_packaging.py -v`
- `python3 -m pytest src/objectnav_core/tests/test_cli_runner.py -v`
- `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`
- ROS-coupling scan found no matches in core code or tests.
- Tests cover models, scene validation, corridor fixture, forward-sector reveal, frontier viewpoint planning, verification viewpoint planning, fake detector gating, discrete navigation, frontier scoring, SQLite memory, reusable memory query, relation recording, and four deterministic Phase 1A runs.

Noted:

- Placeholder scan output includes historical devlog mentions of placeholder scans, the implementation plan's own verification checklist item, and the `placeholders` SQL helper variable in `sqlite_store.py`; no unresolved template placeholders were identified.

Not run:

- No ROS 2 build.
- No `colcon build` because this computer does not have a ROS 2 environment.
- No Nav2 adapter test.
- No robot trial.
- No detector/VLM/perception replay.

## Known Risks

- Trial runner is intentionally simplified and deterministic. It proves the core contract, not physical robot behavior.
- Navigation is straight-line discrete stepping, not A* and not Nav2.
- The missing/relocation run uses scripted object hiding and relocation.
- Metrics are present in model form but not yet fully persisted in the `trial_metrics` table.
- The SQLite store is enough for Phase 1A tests but needs more query and migration discipline before larger experiments.

## Next Recommended Step

1. Persist `TrialMetrics` rows to SQLite.
2. Add an A* navigation client while keeping the `NavigationClient` behavior compatible.
3. Add baseline policy switches for nearest frontier and information gain.
4. Add experiment report generation from `summary.json` and `events.jsonl`.
5. Only after those pass, begin Phase 5-style offline perception adapter experiments.

## Context for Next Contributor

Keep `objectnav_core` ROS-free. Any future ROS 2, Nav2, TF, detector, RTK, or RViz code should live in a separate adapter package and translate into the core interfaces.
