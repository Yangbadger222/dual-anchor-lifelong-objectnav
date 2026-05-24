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

The core package is under `src/objectnav_core/objectnav_core`. It intentionally does not import ROS 2, Nav2, TF, detector models, RTK, or vehicle-specific launch files.

## ROS 2 Boundary

This repository is intended to become a ROS 2 workspace, but this computer does not need ROS installed to develop Phase 1A. The current `src/objectnav_core` package includes ROS 2 `ament_python` metadata (`package.xml`, `setup.py`, and `resource/objectnav_core`) so it can later be built with `colcon` on a ROS 2 machine.

On a ROS 2 machine, the expected future check is:

```bash
colcon build --packages-select objectnav_core
```

On this machine, use pytest for the ROS-free core until a ROS 2 environment or container is available.
