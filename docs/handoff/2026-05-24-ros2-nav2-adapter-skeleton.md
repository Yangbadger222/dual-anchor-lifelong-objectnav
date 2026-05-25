# Handoff: ROS 2 Nav2 Adapter Skeleton

Date: 2026-05-24  
Owner: Codex  
Status: Ready for Review

## Current State

The current environment has ROS 2 Humble available and the repository now has two `ament_python` packages:

- `objectnav_core`: ROS-free ObjectNav models, mapping, planning, memory, simulation, reporting, and Phase 1A CLI.
- `objectnav_ros`: first ROS 2 adapter skeleton for message conversion, a mock-testable Nav2 action-client wrapper, JSON object-observation intake, and a minimal `rclpy` node shell.

The adapter skeleton includes:

- `nav_msgs/msg/OccupancyGrid` to core `OccupancyGrid` conversion.
- `geometry_msgs/msg/PoseStamped` and `TransformStamped` conversion to/from core `Pose2D`.
- `nav2_msgs/action/NavigateToPose.Goal` creation from a core pose.
- `action_msgs/msg/GoalStatus` to core `NavigationStatus` mapping.
- `Nav2NavigationClient`, a thin asynchronous wrapper around Nav2 `NavigateToPose` that handles server availability, goal acceptance/rejection, result mapping, Nav2 error details, and cancel requests.
- `std_msgs/msg/String` JSON object-observation conversion to core `ObjectObservation`, including optional stale timestamp rejection.
- A minimal `objectnav_adapter` node that declares adapter parameters and publishes JSON status messages for goal and object-observation events.
- Launch/config files under `src/objectnav_ros/launch` and `src/objectnav_ros/config`.

Also fixed during this task:

- `src/objectnav_core/objectnav_core/models/__init__.py` was missing from tracked files because `.gitignore` used `models/`, which ignored the source package directory. The ignore rule is now `/models/`.
- ROS 2 generated directories `log/`, `build/`, and `install/` are ignored.

## Files Touched

- `.gitignore`
- `README.md`
- `docs/design/2026-05-24-ros2-nav2-adapter.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-24-ros2-nav2-adapter-skeleton.md`
- `runs/phase1a/latest/report.html`
- `runs/phase1a/latest/summary.json`
- `src/objectnav_core/objectnav_core/models/__init__.py`
- `src/objectnav_ros/**`

## Commands Run

```bash
git status --short --branch
colcon --help | head -40
python3 - <<'PY'
import rclpy
print('rclpy available')
PY
python3 - <<'PY'
mods=['rclpy','std_msgs.msg','geometry_msgs.msg','nav_msgs.msg','nav2_msgs.action','action_msgs.msg','tf2_ros','visualization_msgs.msg','ament_index_python']
for mod in mods:
    __import__(mod)
    print(mod, 'OK')
PY
python3 -m pytest src/objectnav_core/tests -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest src/objectnav_core/tests -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros python3 -m pytest src/objectnav_ros/tests -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_core/tests src/objectnav_ros/tests -q
python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_ros/objectnav_ros
PYTHONPATH=src/objectnav_core:${PYTHONPATH} python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
rg -n "rclpy|nav2_msgs|nav_msgs|geometry_msgs|sensor_msgs|tf2_ros|visualization_msgs" src/objectnav_core/objectnav_core
colcon build --packages-select objectnav_core objectnav_ros --event-handlers console_direct+
source install/setup.zsh && python3 - <<'PY'
from objectnav_core.models import make_default_corridor_scene
from objectnav_ros.adapters.nav2_navigation_client import make_navigate_to_pose_goal
scene = make_default_corridor_scene()
goal = make_navigate_to_pose_goal(scene.objects[0].pose_map, frame_id=scene.anchor.frame_id)
print(scene.scene_id)
print(goal.pose.header.frame_id)
PY
python3 -m py_compile src/objectnav_ros/launch/objectnav_adapter.launch.py
python3 - <<'PY'
from pathlib import Path
import yaml
path = Path('src/objectnav_ros/config/indoor_nav2_adapter.yaml')
print(yaml.safe_load(path.read_text(encoding='utf-8'))['objectnav_adapter']['ros__parameters']['map_frame'])
PY
source install/setup.zsh && ros2 pkg executables objectnav_ros && ros2 pkg prefix objectnav_ros
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+
colcon test-result --verbose
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests/test_nav2_status_mapping.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_core/tests src/objectnav_ros/tests -q
source install/setup.zsh && python3 - <<'PY'
from objectnav_core.models import NavigationStatus, Pose2D
from objectnav_ros.adapters.nav2_navigation_client import Nav2NavigationClient
class FakeActionClient:
    def wait_for_server(self, *, timeout_sec):
        return False
client = Nav2NavigationClient(None, action_client=FakeActionClient())
print(client.send_goal(Pose2D(x=1.0, y=2.0, yaw=0.0)).value)
print(client.result_reason)
print(NavigationStatus.FAILED.value)
PY
PYTHONPATH=src/objectnav_core:${PYTHONPATH} python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
```

## Verification

Passed:

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests -q`: 21 passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests -q`: 12 passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_core/tests src/objectnav_ros/tests -q`: 33 passed.
- `python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_ros/objectnav_ros`.
- `PYTHONPATH=src/objectnav_core:${PYTHONPATH} python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest`; four deterministic trials succeeded and artifacts were regenerated.
- Core-only ROS import scan returned no matches under `src/objectnav_core/objectnav_core`.
- `colcon build --packages-select objectnav_core objectnav_ros --event-handlers console_direct+`; both packages built.
- Installed-space import smoke test printed the expected scene id and `map` frame id.
- `python3 -m py_compile src/objectnav_ros/launch/objectnav_adapter.launch.py`.
- PyYAML parsed `src/objectnav_ros/config/indoor_nav2_adapter.yaml` and found `map_frame: map`.
- `source install/setup.zsh && ros2 pkg executables objectnav_ros && ros2 pkg prefix objectnav_ros`; ROS 2 found `objectnav_adapter` and the installed package prefix.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+`; 21 core tests and 12 adapter tests passed.
- `colcon test-result --verbose`; 33 tests, 0 errors, 0 failures, 0 skipped.
- After adding `Nav2NavigationClient`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests/test_nav2_status_mapping.py -q`; 7 passed.
- After adding `Nav2NavigationClient`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests -q`; 17 passed.
- After adding `Nav2NavigationClient`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_core/tests src/objectnav_ros/tests -q`; 38 passed.
- Re-ran `colcon build --packages-select objectnav_core objectnav_ros --event-handlers console_direct+`; both packages built.
- Re-ran `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+`; 21 core tests and 17 adapter tests passed.
- Re-ran `colcon test-result --verbose`; 38 tests, 0 errors, 0 failures, 0 skipped.
- Installed-space smoke test for `Nav2NavigationClient` with a fake unavailable action server returned `FAILED` and `action_server_unavailable`.
- Re-ran Phase 1A artifact generation; 4 runs, all successful.

Failed or corrected:

- Plain `python3 -m pytest ...` fails before collection because a system `anyio` pytest plugin expects a newer pytest API: `ModuleNotFoundError: No module named '_pytest.scope'`.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest ...` needs explicit `PYTHONPATH=src/objectnav_core`; this system pytest reports `pythonpath` in `pyproject.toml` as an unknown config option.
- For ROS adapter pytest, preserve the ROS environment path with `PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH}`. Replacing `PYTHONPATH` hides ROS packages such as `nav_msgs` and `std_msgs`.

Not run:

- No live Nav2 action-server test.
- No TF buffer lookup test against a running TF tree.
- No manual RViz GUI inspection or screenshot.
- No rosbag replay from a recorded bag.
- No robot trial.

## Known Risks

- `objectnav_ros` is a skeleton, not a full ObjectNav node. It does not yet execute the Phase 1A state machine.
- `Nav2NavigationClient` is unit-tested with fakes and can construct/send action goals through `rclpy`, but it has not been tested against a live Nav2 action server.
- Object observations currently use JSON in `std_msgs/String`; this is acceptable for early adapter testing but may need custom messages or actions before live robot work.
- Costmap conversion and synthetic replay assume zero map origin. Nonzero `OccupancyGrid.info.origin` and transformed costmap frames need explicit handling before recorded-bag/live use.
- The stale-observation check compares numeric timestamps only; clock-domain policy for ROS time vs wall time still needs a replay test.
- The restored default scene model passes tests but regenerated Phase 1A artifact metrics differ from the previous tracked summary because the missing model file had to be reconstructed from tests and artifacts.

## Next Recommended Step

1. Manually inspect `ros2 launch objectnav_ros synthetic_replay.launch.py` in RViz and save a verification note or screenshot.
2. Add a mocked action-server or launch-test harness before connecting to a live Nav2 stack.
3. Decide whether early `/objectnav/object_observations` should stay as JSON strings or move to a custom message package.
4. Only after replay passes, wire the ROS node to call core candidate selection and navigation dispatch.

## Context for Next Contributor

Keep `objectnav_core` free of ROS imports. All ROS 2, Nav2, TF, RViz, topic names, frame ids, and deployment-specific values belong in `objectnav_ros` or config files.

Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` for local pytest on this machine, and preserve `${PYTHONPATH}` when running ROS adapter tests so `/opt/ros/humble` Python packages remain visible.
