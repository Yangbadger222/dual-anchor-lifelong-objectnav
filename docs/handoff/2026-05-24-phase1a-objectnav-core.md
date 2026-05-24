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
- Deterministic A* grid navigation client for ROS-free path-cost and reachability checks.
- Frontier baseline policy switches for `first_frontier`, `nearest_frontier`, and `information_gain`.
- SQLite memory store with object records, object observations, object relations, trial events, trial metrics, indexes, and JSON export.
- Generated Phase 1A static HTML report from JSON, JSONL, and SQLite artifacts.
- ROS 2/Nav2 adapter design for a future `objectnav_ros` package that keeps `objectnav_core` ROS-free.
- Phase 1A trial runner for:
  - `discover_and_verify`
  - `reuse_same_start`
  - `reuse_different_start`
  - `missing_and_relocation`
- CLI artifact runner:
  - `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`
  - writes `memory.sqlite`, `summary.json`, `memory_snapshot.json`, `events.jsonl`, and `report.html`
- CLI report generator:
  - `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.generate_phase1a_report --input runs/phase1a/latest`
  - rewrites `report.html` from an existing artifact directory
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

Additional files touched for the trial-metrics persistence update:

- `src/objectnav_core/objectnav_core/memory/sqlite_store.py`
- `src/objectnav_core/objectnav_core/simulation/trials.py`
- `src/objectnav_core/tests/test_trials.py`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-24-phase1a-objectnav-core.md`

Additional files touched for the baseline frontier policy update:

- `src/objectnav_core/objectnav_core/planning/frontier_policies.py`
- `src/objectnav_core/objectnav_core/simulation/trials.py`
- `src/objectnav_core/tests/test_simulation.py`
- `src/objectnav_core/tests/test_trials.py`
- `docs/design/2026-05-24-baseline-frontier-policies.md`
- `docs/superpowers/plans/2026-05-24-baseline-frontier-policies.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-24-phase1a-objectnav-core.md`

Additional files touched for the A* grid navigation update:

- `src/objectnav_core/objectnav_core/simulation/navigation.py`
- `src/objectnav_core/tests/test_simulation.py`
- `docs/design/2026-05-24-astar-grid-navigation.md`
- `docs/superpowers/plans/2026-05-24-astar-grid-navigation.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-24-phase1a-objectnav-core.md`

Additional files touched for the Phase 1A report generator update:

- `README.md`
- `runs/phase1a/latest/report.html`
- `runs/phase1a/latest/summary.json`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/objectnav_core/cli/generate_phase1a_report.py`
- `src/objectnav_core/objectnav_core/cli/run_phase1a.py`
- `src/objectnav_core/objectnav_core/evaluation/report.py`
- `src/objectnav_core/tests/test_cli_runner.py`
- `src/objectnav_core/tests/test_ros_packaging.py`
- `docs/design/2026-05-24-phase1a-report-generator.md`
- `docs/superpowers/plans/2026-05-24-phase1a-report-generator.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-24-phase1a-objectnav-core.md`

Additional files touched for the ROS 2/Nav2 adapter design update:

- `docs/design/2026-05-24-ros2-nav2-adapter.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-24-phase1a-objectnav-core.md`

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
python3 -m pytest src/objectnav_core/tests/test_trials.py -v
python3 -m pytest src/objectnav_core/tests -v
python3 -m compileall -q src/objectnav_core/objectnav_core
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
python3 - <<'PY'
import json
import sqlite3
from pathlib import Path
path = Path('runs/phase1a/latest/memory.sqlite')
with sqlite3.connect(path) as con:
    count = con.execute('SELECT COUNT(*) FROM trial_metrics').fetchone()[0]
    ids = [row[0] for row in con.execute('SELECT trial_id FROM trial_metrics ORDER BY trial_id')]
print(json.dumps({'trial_metrics_count': count, 'trial_ids': ids}, indent=2))
PY
rg -n "rclpy|nav2|NavigateToPose|sensor_msgs|geometry_msgs|tf2_ros|/global_costmap|/tf" src/objectnav_core/objectnav_core
rg -n "TODO|FIXME|Pending|<Title>|<name|placeholder|YYYY-MM-DD" README.md pyproject.toml docs src/objectnav_core
python3 -m pytest src/objectnav_core/tests/test_simulation.py -v
python3 -m pytest src/objectnav_core/tests -v
python3 -m compileall -q src/objectnav_core/objectnav_core
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
python3 - <<'PY'
import json
import sqlite3
from pathlib import Path
with sqlite3.connect(Path('runs/phase1a/latest/memory.sqlite')) as con:
    rows = con.execute('SELECT trial_id, metrics_json FROM trial_metrics ORDER BY trial_id').fetchall()
print(json.dumps({
    'trial_metrics_count': len(rows),
    'trial_ids': [row[0] for row in rows],
    'all_success': all(json.loads(row[1])['success'] for row in rows),
}, indent=2))
PY
rg -n "rclpy|nav2|NavigateToPose|sensor_msgs|geometry_msgs|tf2_ros|/global_costmap|/tf" src/objectnav_core/objectnav_core
python3 -m pytest src/objectnav_core/tests/test_simulation.py -v
python3 -m pytest src/objectnav_core/tests/test_trials.py -v
python3 -m pytest src/objectnav_core/tests -v
python3 -m compileall -q src/objectnav_core/objectnav_core
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
python3 - <<'PY'
import json
import sqlite3
from pathlib import Path
with sqlite3.connect(Path('runs/phase1a/latest/memory.sqlite')) as con:
    rows = con.execute('SELECT trial_id, metrics_json FROM trial_metrics ORDER BY trial_id').fetchall()
print(json.dumps({
    'trial_metrics_count': len(rows),
    'trial_ids': [row[0] for row in rows],
    'all_success': all(json.loads(row[1])['success'] for row in rows),
    'discover_candidates': json.loads(dict(rows)['discover_and_verify'])['selected_candidate_types'],
}, indent=2))
PY
rg -n "rclpy|nav2|NavigateToPose|sensor_msgs|geometry_msgs|tf2_ros|/global_costmap|/tf" src/objectnav_core/objectnav_core
python3 -m pytest src/objectnav_core/tests/test_cli_runner.py -v
python3 -m pytest src/objectnav_core/tests -v
python3 -m compileall -q src/objectnav_core/objectnav_core
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.generate_phase1a_report --input runs/phase1a/latest
python3 - <<'PY'
import json
import sqlite3
from html.parser import HTMLParser
from pathlib import Path
class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=set(); self.hrefs=[]
    def handle_starttag(self, tag, attrs):
        data=dict(attrs)
        if data.get('id'):
            self.ids.add(data['id'])
        if tag == 'a' and data.get('href'):
            self.hrefs.append(data['href'])
report = Path('runs/phase1a/latest/report.html')
parser = AnchorParser()
parser.feed(report.read_text(encoding='utf-8'))
missing = sorted(href[1:] for href in parser.hrefs if href.startswith('#') and href[1:] not in parser.ids)
with sqlite3.connect(Path('runs/phase1a/latest/memory.sqlite')) as con:
    rows = con.execute('SELECT trial_id, metrics_json FROM trial_metrics ORDER BY trial_id').fetchall()
print(json.dumps({
    'report_exists': report.exists(),
    'missing_anchors': missing,
    'trial_metrics_count': len(rows),
    'all_success': all(json.loads(row[1])['success'] for row in rows),
    'artifact_files': json.loads(Path('runs/phase1a/latest/summary.json').read_text(encoding='utf-8'))['artifact_files'],
}, indent=2))
PY
rg -n "rclpy|nav2|NavigateToPose|sensor_msgs|geometry_msgs|tf2_ros|/global_costmap|/tf" src/objectnav_core/objectnav_core
test -f docs/design/2026-05-24-ros2-nav2-adapter.md
rg -n "^## |^### " docs/design/2026-05-24-ros2-nav2-adapter.md
python3 -m pytest src/objectnav_core/tests -v
python3 -m compileall -q src/objectnav_core/objectnav_core
rg -n "rclpy|nav2|NavigateToPose|sensor_msgs|geometry_msgs|tf2_ros|/global_costmap|/tf" src/objectnav_core/objectnav_core
rg -n "TODO|FIXME|Pending|<Title>|<name|placeholder|YYYY-MM-DD" README.md pyproject.toml docs src/objectnav_core
```

## Verification

Passed:

- `python3 -m pytest src/objectnav_core/tests -v`
- 14 tests passed after adding the CLI artifact runner.
- `python3 -m compileall -q src/objectnav_core/objectnav_core`
- `python3 -m pytest src/objectnav_core/tests/test_ros_packaging.py -v`
- `python3 -m pytest src/objectnav_core/tests/test_cli_runner.py -v`
- `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`
- `python3 -m pytest src/objectnav_core/tests/test_trials.py -v`
- `python3 -m pytest src/objectnav_core/tests -v`
- `python3 -m compileall -q src/objectnav_core/objectnav_core`
- `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`
- Direct SQLite check confirmed 4 `trial_metrics` rows for `discover_and_verify`, `reuse_same_start`, `reuse_different_start`, and `missing_and_relocation`.
- `python3 -m pytest src/objectnav_core/tests/test_simulation.py -v`
- `python3 -m pytest src/objectnav_core/tests -v`
- `python3 -m compileall -q src/objectnav_core/objectnav_core`
- `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`
- Direct SQLite check confirmed 4 successful `trial_metrics` rows after the A* update.
- `python3 -m pytest src/objectnav_core/tests/test_simulation.py -v`
- `python3 -m pytest src/objectnav_core/tests/test_trials.py -v`
- `python3 -m pytest src/objectnav_core/tests -v`
- `python3 -m compileall -q src/objectnav_core/objectnav_core`
- `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`
- Direct SQLite check confirmed 4 successful `trial_metrics` rows after the baseline policy update.
- Direct SQLite check confirmed the default `discover_and_verify` candidate types remain `frontier` and `object_verification`.
- `python3 -m pytest src/objectnav_core/tests/test_cli_runner.py -v`
- `python3 -m pytest src/objectnav_core/tests -v`
- `python3 -m compileall -q src/objectnav_core/objectnav_core`
- `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`
- `PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.generate_phase1a_report --input runs/phase1a/latest`
- Generated HTML anchor check found no missing internal anchors.
- Direct SQLite check confirmed 4 successful `trial_metrics` rows after the report-generator update.
- The latest summary artifact manifest includes `report.html`.
- Core-only ROS-coupling scan found no matches under `src/objectnav_core/objectnav_core`.
- `test -f docs/design/2026-05-24-ros2-nav2-adapter.md`
- `rg -n "^## |^### " docs/design/2026-05-24-ros2-nav2-adapter.md` returned the expected ROS adapter design headings.
- `python3 -m pytest src/objectnav_core/tests -v`
- `python3 -m compileall -q src/objectnav_core/objectnav_core`
- Latest core-only ROS-coupling scan found no matches under `src/objectnav_core/objectnav_core`.
- Tests cover models, scene validation, corridor fixture, forward-sector reveal, frontier viewpoint planning, verification viewpoint planning, fake detector gating, discrete navigation, A* navigation, frontier baseline policy selection, frontier scoring, SQLite memory, reusable memory query, relation recording, trial-metrics persistence, generated report artifacts, and four deterministic Phase 1A runs.

Noted:

- Placeholder scan output includes template files, historical devlog mentions of placeholder scans, the implementation plan's verification checklist item, and the `placeholders` SQL helper variable in `sqlite_store.py`; no unresolved working-document placeholders were identified.

Not run:

- No ROS 2 build.
- No `colcon build` because this computer does not have a ROS 2 environment.
- No `objectnav_ros` package implementation yet.
- No Nav2 adapter test.
- No robot trial.
- No detector/VLM/perception replay.

## Known Risks

- Trial runner is intentionally simplified and deterministic. It proves the core contract, not physical robot behavior.
- The default Phase 1A trial runner still uses `first_frontier` selection and straight-line discrete execution.
- A* path cost is used by `nearest_frontier` and `information_gain` selection, but A* is not yet used as the trial execution backend.
- A* is 4-connected and does not model robot footprint inflation, dynamic obstacles, recovery behaviors, or Nav2 controller behavior.
- Information gain is currently frontier cell count, not a richer unknown-area or semantic-search estimate.
- The missing/relocation run uses scripted object hiding and relocation.
- Trial metrics are persisted as one JSON payload per `trial_id`; there is still no schema migration/versioning layer for larger experiments.
- The generated report is static HTML; it summarizes score terms but does not yet include map/path diagrams or multi-policy comparisons.
- The SQLite store is enough for Phase 1A tests but needs more query and migration discipline before larger experiments.
- The ROS 2/Nav2 adapter is design-only; package code, colcon build, ROS message conversion, TF integration, Nav2 action mapping, and replay tests are not implemented.
- The first goal and object-observation ROS message shapes are still open.
- The first supported ROS 2 distribution and Nav2 version are not yet pinned.

## Next Recommended Step

1. Create an implementation plan for a minimal `objectnav_ros` adapter skeleton in a ROS 2 environment or container.
2. Decide whether early ObjectNav goals and object observations should use `std_msgs/String`/JSON strings, custom messages, or a custom action.
3. Add adapter-level tests for costmap conversion, TF pose conversion, Nav2 result mapping, object-observation conversion, stale timestamps, and import boundaries.
4. Add rosbag or synthetic-message replay before live Nav2 robot trials.
5. Decide whether Phase 1A should expose frontier policy selection through the CLI before larger baseline runs.

## Context for Next Contributor

Keep `objectnav_core` ROS-free. Any future ROS 2, Nav2, TF, detector, RTK, or RViz code should live in a separate adapter package and translate into the core interfaces.
