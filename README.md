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
