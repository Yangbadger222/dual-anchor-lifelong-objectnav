# Dual-Anchor Lifelong ObjectNav

Research repository for a hardware-independent semantic ObjectNav layer that can be developed offline, evaluated in simulation or rosbag replay, and later integrated with a ROS 2 autonomous vehicle stack.

The project is intentionally documentation-first. Before adding substantial code, read [AGENTS.md](AGENTS.md) and use the templates under [docs/templates](docs/templates).

## Working Rule

Every meaningful change must leave behind enough context for the next human or AI agent to continue safely:

- design intent
- implementation notes
- verification evidence
- known risks
- handoff status

## Phase 1A Quick Start

The first runnable slice is a ROS-free indoor water-dispenser ObjectNav core. It uses a deterministic corridor fixture, fake object observations, SQLite memory, and pytest.

Run the current Phase 1A checks:

```bash
python3 -m pip install pytest
python3 -m pytest src/objectnav_core/tests -v
```

Run the deterministic Phase 1A trial suite and write experiment artifacts:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
```

This writes:

- `runs/phase1a/latest/memory.sqlite`
- `runs/phase1a/latest/summary.json`
- `runs/phase1a/latest/memory_snapshot.json`
- `runs/phase1a/latest/events.jsonl`
- `runs/phase1a/latest/report.html`

Regenerate only the HTML report from an existing artifact directory:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.generate_phase1a_report --input runs/phase1a/latest
```

The core package is under `src/objectnav_core/objectnav_core`. It intentionally does not import ROS 2, Nav2, TF, detector models, RTK, or vehicle-specific launch files.

## Repository Map

The current project layout is documented in [`docs/repository-file-management.md`](docs/repository-file-management.md). Use that file when deciding where to put new designs, simulation protocols, generated outputs, datasets, or handoff notes.

## Usability Memory Stress Test

The first algorithm-focused slice is a ROS-free stress harness for usability-centered object memory. It tests the math model before real RTK, RGB-D, detector, or robot closure are involved.

Run it with:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_usability_stress --output runs/usability_stress/latest --seed 13 --monte-carlo-runs 200
```

This writes:

- `runs/usability_stress/latest/summary.json`
- `runs/usability_stress/latest/decision_boundary.csv`
- `runs/usability_stress/latest/stress_report.html`

The stress harness covers ghost-memory retirement, false-deletion guards, quarantined negative evidence, and bounded trust/verify/search/retire decision sweeps.

## 2D Grid Trace Experiment

The next pre-robot layer is a lightweight statistical 2D trace generator. It emits sequential evidence events, robot/target poses, navigation costs, stale/fresh path costs, multi-object association replay fields, belief values, and trust/verify/search/retire decisions.

Run it with:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_grid_trace_experiment --output runs/grid_trace/latest --seed 17 --episodes 100000 --steps-per-episode 8
```

This writes:

- `runs/grid_trace/latest/summary.json`
- `runs/grid_trace/latest/events.csv`
- `runs/grid_trace/latest/trace_report.html`

The 100000-episode run writes about 800000 event rows; `events.csv` is large and intentionally ignored under `runs/`. Use fewer episodes for a quick smoke. This is not a sensor-realistic simulator. It is a fast logic harness before Habitat noisy-depth replay and XJTLU real-bag replay.

## Localization-Only Bag Audit

Existing XJTLU corridor bags can be audited before Habitat or RGB-D replay. This is a localization and anchor-health preflight, not an ObjectNav perception result.

Run it with explicit bags:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_localization_bag_audit \
  --output runs/localization_bag_audit/latest \
  --bag /Users/badger/Desktop/my_local_data/logs/2026-03-25-17-46-15/bag \
  --bag /Users/badger/Desktop/my_local_data/logs/2026-03-22-21-05-17/bag
```

This writes:

- `runs/localization_bag_audit/latest/summary.json`
- `runs/localization_bag_audit/latest/session_metrics.csv`
- `runs/localization_bag_audit/latest/topic_counts.csv`
- `runs/localization_bag_audit/latest/fix_samples.csv`
- `runs/localization_bag_audit/latest/lio_samples.csv`
- `runs/localization_bag_audit/latest/audit_report.html`

The audit reads ROS 2 SQLite bags directly and intentionally avoids `rclpy`, `ros2 bag`, TF2, Nav2, detector, RTK, or vehicle-specific imports.

## Habitat-Sim Next Step

The next simulation protocol is documented as a Chinese HTML operation guide:

```text
docs/simulation/2026-05-26-habitat-sim-usability-memory.zh.html
```

It describes the staged Habitat-Sim route, trace schema, evidence extraction rules, baseline plan, metrics, and expected artifact layout before any Habitat-specific code is added.

## ROS 2 Boundary

This repository is intended to become a ROS 2 workspace, but this computer does not need ROS installed to develop Phase 1A. The current `src/objectnav_core` package includes ROS 2 `ament_python` metadata (`package.xml`, `setup.py`, and `resource/objectnav_core`) so it can later be built with `colcon` on a ROS 2 machine.

On a ROS 2 machine, the expected future check is:

```bash
colcon build --packages-select objectnav_core objectnav_ros
source install/setup.zsh
colcon test --packages-select objectnav_core objectnav_ros
colcon test-result --verbose
```

The first ROS 2 adapter skeleton lives under `src/objectnav_ros`. It currently provides message conversion, a mock-testable Nav2 `NavigateToPose` action-client wrapper, JSON object-observation conversion, a minimal `rclpy` node shell, launch/config files, synthetic replay, RViz markers, and adapter unit tests. It does not yet run the full ObjectNav state machine inside ROS or perform robot trials.

Run the synthetic replay and RViz inspection launch:

```bash
source install/setup.zsh
ros2 launch objectnav_ros synthetic_replay_rviz.launch.py
```

For a non-GUI replay run, use:

```bash
ros2 launch objectnav_ros synthetic_replay.launch.py
```

The RViz launch starts `objectnav_adapter`, `objectnav_synthetic_replay`, and RViz with `synthetic_replay.rviz`. The replay progressively reveals the corridor costmap, moves `map -> base_link`, publishes the object observation only when visible, and overlays a small legend marker. Inspect these topics:

- `/objectnav/status`
- `/objectnav/selected_goal`
- `/objectnav/frontier_markers`
- `/objectnav/memory_markers`
- `/objectnav/debug_markers`
- `/global_costmap/costmap`

If an older RViz/replay launch is already running, close it before re-launching so RViz sees the current transient-local costmap publisher and updated replay behavior.

Run the TurtleBot3 Gazebo/Nav2 assumed-target smoke after building:

```bash
source install/setup.zsh
ros2 launch objectnav_ros turtlebot3_assumed_target_nav2.launch.py
```

This launch uses open-source TurtleBot3 Gazebo and Navigation2 assets. It treats `water_dispenser` as a configured map-frame goal pose instead of a detected object. The default launch does not send the goal immediately; after Nav2 is localized, trigger it with:

```bash
ros2 topic pub --once /objectnav/goal std_msgs/msg/String "{data: water_dispenser}"
```

For the verified TurtleBot3 smoke, initialize AMCL near the Gazebo spawn pose (`x=-2.0`, `y=-0.5`, `yaw=0.0`). The wrapper launch also disables Gazebo Classic's online model database lookup by default so startup does not depend on `models.gazebosim.org`.
