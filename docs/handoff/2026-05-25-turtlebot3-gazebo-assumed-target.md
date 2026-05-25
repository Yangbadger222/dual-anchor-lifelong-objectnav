# Handoff: TurtleBot3 Gazebo Assumed-Target Nav2 Smoke

Date: 2026-05-25  
Owner: Codex  
Status: Full Gazebo/Nav2 Smoke Passed

## Current State

After reviewing the existing architecture, ROS 2 adapter, synthetic replay, and handoff documents, the selected simulation direction is:

1. Keep the current synthetic replay as the adapter/RViz visibility test.
2. Add a TurtleBot3 Gazebo + Nav2 smoke slice before real robot work.
3. Treat `water_dispenser` as an assumed configured map-frame target pose rather than a detected object.
4. Use the existing `Nav2NavigationClient` to send the configured verification pose to a live Nav2 action server.

This is intentionally narrower than full ObjectNav in Gazebo. It tests the live Nav2 action boundary with a reproducible open-source robot and map.

Implemented in this slice:

- `assumed_target_nav2_smoke` console script.
- `config/turtlebot3_assumed_targets.yaml`, with `water_dispenser` mapped to `(x=1.5, y=0.0, yaw=0.0)` in `map`.
- `launch/turtlebot3_assumed_target_nav2.launch.py`, wrapping TurtleBot3 Gazebo, TurtleBot3 Navigation2, and the smoke node.
- Launch-time Gazebo Classic mitigation: default `GAZEBO_MODEL_DATABASE_URI` to empty and prepend local TurtleBot3/Gazebo model paths so `/spawn_entity` is not blocked by the online model database.
- Tests for assumed target parsing, trigger matching, status JSON, node trigger behavior, and launch/config installation.

The launch defaults `send_goal_on_start=false`, so the operator can set AMCL initial pose first and then trigger the goal with `/objectnav/goal`.

Full simulation status:

- TurtleBot3 `waffle` spawned successfully in Gazebo.
- `/odom` was published by the TurtleBot3 diff-drive plugin.
- Nav2 `/navigate_to_pose` action server was available.
- Publishing initial pose `x=-2.0`, `y=-0.5`, `yaw=0.0`, then triggering `water_dispenser`, drove to the configured target.
- `/objectnav/status` reported `navigation_status=SUCCEEDED` and `result_reason=nav2_succeeded`.

## Local Environment Findings

Available locally in the ROS 2 Humble environment:

- `turtlebot3_gazebo`
- `turtlebot3_navigation2`
- `turtlebot3_description`
- `nav2_bringup`
- `nav2_map_server`
- `nav2_amcl`
- `slam_toolbox`
- `gazebo_ros`
- `/usr/bin/gazebo`
- `/usr/bin/gz`
- `/usr/bin/ign`

Useful installed files:

- `/opt/ros/humble/share/turtlebot3_gazebo/launch/turtlebot3_world.launch.py`
- `/opt/ros/humble/share/turtlebot3_gazebo/worlds/turtlebot3_world.world`
- `/opt/ros/humble/share/turtlebot3_navigation2/launch/navigation2.launch.py`
- `/opt/ros/humble/share/turtlebot3_navigation2/map/map.yaml`
- `/opt/ros/humble/share/turtlebot3_navigation2/param/humble/waffle.yaml`

Important note:

- `turtlebot3_navigation2/launch/navigation2.launch.py` requires `TURTLEBOT3_MODEL`; without it, launch argument inspection raises `KeyError: 'TURTLEBOT3_MODEL'`.
- The TurtleBot3 map has a nonzero origin: `origin: [-10.000000, -10.000000, 0.000000]`. Current ObjectNav core grid helpers assume zero origin, so the first TurtleBot3 smoke should send a configured map-frame Nav2 goal directly and defer origin-aware frontier selection.

## Files Added

- `docs/design/2026-05-25-turtlebot3-gazebo-assumed-target.md`
- `docs/handoff/2026-05-25-turtlebot3-gazebo-assumed-target.md`
- `docs/devlog/2026-05.md`
- `README.md`
- `src/objectnav_ros/config/turtlebot3_assumed_targets.yaml`
- `src/objectnav_ros/launch/turtlebot3_assumed_target_nav2.launch.py`
- `src/objectnav_ros/objectnav_ros/nodes/assumed_target_nav2_smoke.py`
- `src/objectnav_ros/tests/test_assumed_target_nav2_smoke.py`
- `src/objectnav_ros/setup.py`
- `src/objectnav_ros/package.xml`

## Commands Run

```bash
git status --short --branch
rg --files docs README.md src/objectnav_ros src/objectnav_core | sort
sed -n '1,180p' README.md
sed -n '1,260p' docs/design/2026-05-24-ros2-nav2-adapter.md
sed -n '1,260p' docs/design/2026-05-25-ros2-synthetic-replay-rviz.md
sed -n '1,280p' docs/handoff/2026-05-25-ros2-synthetic-replay-rviz.md
sed -n '1,700p' docs/design/2026-05-24-system-architecture.md
sed -n '1,260p' docs/handoff/2026-05-24-ros2-nav2-adapter-skeleton.md
sed -n '1,260p' docs/design/2026-05-24-astar-grid-navigation.md
sed -n '1,260p' docs/design/2026-05-24-baseline-frontier-policies.md
source install/setup.zsh && ros2 pkg list | rg -i "turtlebot|nav2|gazebo|slam_toolbox|map_server|amcl"
which gazebo || true
which gz || true
which ign || true
which ros2 || true
source install/setup.zsh && for p in turtlebot3_gazebo turtlebot3_navigation2 turtlebot3_description nav2_bringup gazebo_ros; do echo "$p $(ros2 pkg prefix $p 2>/dev/null || true)"; done
source install/setup.zsh && find $(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo -maxdepth 3 -type f | sort | sed -n '1,160p'
source install/setup.zsh && find $(ros2 pkg prefix turtlebot3_navigation2)/share/turtlebot3_navigation2 -maxdepth 3 -type f | sort | sed -n '1,180p'
source install/setup.zsh && ros2 launch turtlebot3_gazebo turtlebot3_world.launch.py --show-args
source install/setup.zsh && ros2 launch turtlebot3_navigation2 navigation2.launch.py --show-args
source install/setup.zsh && TURTLEBOT3_MODEL=waffle ros2 launch turtlebot3_navigation2 navigation2.launch.py --show-args
sed -n '1,260p' /opt/ros/humble/share/turtlebot3_gazebo/launch/turtlebot3_world.launch.py
sed -n '1,320p' /opt/ros/humble/share/turtlebot3_navigation2/launch/navigation2.launch.py
sed -n '1,120p' /opt/ros/humble/share/turtlebot3_navigation2/map/map.yaml
file /opt/ros/humble/share/turtlebot3_navigation2/map/map.pgm
sed -n '1,260p' src/objectnav_ros/objectnav_ros/adapters/costmap_adapter.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests/test_assumed_target_nav2_smoke.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_core/tests src/objectnav_ros/tests -q
python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_ros/objectnav_ros
python3 -m py_compile src/objectnav_ros/launch/objectnav_adapter.launch.py src/objectnav_ros/launch/synthetic_replay.launch.py src/objectnav_ros/launch/synthetic_replay_rviz.launch.py src/objectnav_ros/launch/turtlebot3_assumed_target_nav2.launch.py
colcon build --packages-select objectnav_core objectnav_ros --event-handlers console_direct+
source install/setup.zsh && ros2 pkg executables objectnav_ros
source install/setup.zsh && ros2 launch objectnav_ros turtlebot3_assumed_target_nav2.launch.py --show-args
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+
colcon test-result --verbose
timeout 20s bash -lc '
set -e
export ROS_DOMAIN_ID=49
source install/setup.bash
setsid ros2 launch objectnav_ros turtlebot3_assumed_target_nav2.launch.py start_gazebo:=false start_nav2:=false use_sim_time:=false >/tmp/objectnav_tb3_assumed_node_smoke.log 2>&1 &
launch_pid=$!
cleanup() {
  kill -INT -${launch_pid} >/dev/null 2>&1 || true
  wait ${launch_pid} >/dev/null 2>&1 || true
}
trap cleanup EXIT
sleep 3
status=$(timeout 8s ros2 topic echo --once /objectnav/status std_msgs/msg/String)
goal=$(timeout 8s ros2 topic echo --once /objectnav/selected_goal geometry_msgs/msg/PoseStamped)
printf "status_msg=%s\nselected_goal_msg=%s\n" "$status" "$goal"
'
timeout 20s bash -lc '
set -e
export ROS_DOMAIN_ID=51
source install/setup.bash
setsid ros2 run objectnav_ros assumed_target_nav2_smoke --ros-args -p use_sim_time:=false -p navigation_timeout_s:=0.5 >/tmp/objectnav_tb3_assumed_trigger_smoke.log 2>&1 &
node_pid=$!
cleanup() {
  kill -INT -${node_pid} >/dev/null 2>&1 || true
  wait ${node_pid} >/dev/null 2>&1 || true
}
trap cleanup EXIT
sleep 2
ros2 topic pub --once /objectnav/goal std_msgs/msg/String "{data: water_dispenser}" >/tmp/objectnav_tb3_assumed_trigger_pub.log 2>&1
sleep 1
result=$(timeout 8s ros2 topic echo --once /objectnav/status std_msgs/msg/String)
printf "result=%s\n" "$result"
printf "%s\n" "$result" | grep "action_server_unavailable" >/dev/null
'
ROS_DOMAIN_ID=73 bash -lc '
source /opt/ros/humble/setup.bash
ros2 daemon stop >/tmp/gazebo_factory_probe_daemon.log 2>&1 || true
gzserver --verbose /opt/ros/humble/share/turtlebot3_gazebo/worlds/turtlebot3_world.world -s libgazebo_ros_init.so -s libgazebo_ros_factory.so >/tmp/gazebo_factory_probe2.log 2>&1 &
pid=$!
for i in $(seq 1 40); do
  ros2 service list | grep -qx /spawn_entity && break
  sleep 1
done
ros2 service list | sort
kill -KILL "$pid" 2>/dev/null || true
'
ROS_DOMAIN_ID=76 bash -lc '
source /opt/ros/humble/setup.bash
ros2 daemon stop >/tmp/gazebo_launch_probe_nomodeldb_daemon.log 2>&1 || true
export GAZEBO_MODEL_DATABASE_URI=
ros2 launch gazebo_ros gzserver.launch.py world:=/opt/ros/humble/share/turtlebot3_gazebo/worlds/empty_world.world verbose:=true >/tmp/gazebo_launch_probe_nomodeldb.log 2>&1 &
pid=$!
for i in $(seq 1 30); do
  ros2 service list | grep -qx /spawn_entity && break
  sleep 1
done
ros2 service list | sort
kill -INT "$pid" 2>/dev/null || true
sleep 2
kill -KILL "$pid" 2>/dev/null || true
'
ROS_DOMAIN_ID=78 bash -lc '
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 daemon stop >/tmp/objectnav_tb3_full_smoke_nomodeldb_daemon.log 2>&1 || true
ros2 launch objectnav_ros turtlebot3_assumed_target_nav2.launch.py >/tmp/objectnav_tb3_full_smoke_nomodeldb.log 2>&1 &
launch_pid=$!
# Waited for /spawn_entity, /clock, /odom, and /navigate_to_pose.
# Published /initialpose at x=-2.0, y=-0.5, yaw=0.0.
# Published /objectnav/goal with data=water_dispenser.
# Observed /objectnav/status with navigation_status=SUCCEEDED and result_reason=nav2_succeeded.
kill -INT "$launch_pid" 2>/dev/null || true
sleep 5
kill -KILL "$launch_pid" 2>/dev/null || true
'
python3 -m py_compile src/objectnav_ros/launch/turtlebot3_assumed_target_nav2.launch.py
bash -lc 'source /opt/ros/humble/setup.bash; source install/setup.bash; PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q src/objectnav_ros/tests/test_assumed_target_nav2_smoke.py'
bash -lc 'source /opt/ros/humble/setup.bash; colcon build --packages-select objectnav_ros --symlink-install'
bash -lc 'source /opt/ros/humble/setup.bash; PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+'
colcon test-result --verbose
```

## Verification

Passed:

- Documentation and local package inspection completed.
- TurtleBot3 Gazebo and TurtleBot3 Navigation2 packages are present.
- TurtleBot3 world, map, RViz, and Nav2 parameter files are present.
- Gazebo binaries are present.
- `TURTLEBOT3_MODEL=waffle ros2 launch turtlebot3_navigation2 navigation2.launch.py --show-args` succeeds and exposes the expected Nav2 launch arguments.
- Focused assumed-target tests: 5 passed.
- Core + adapter pytest suite: 58 passed.
- `python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_ros/objectnav_ros`.
- Launch files compile with `python3 -m py_compile`.
- `colcon build --packages-select objectnav_core objectnav_ros --event-handlers console_direct+`: both packages built.
- Installed-space executable check found `assumed_target_nav2_smoke`, `objectnav_adapter`, and `objectnav_synthetic_replay`.
- Installed-space launch argument check for `turtlebot3_assumed_target_nav2.launch.py` passed.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+`: 21 core tests and 37 adapter tests passed.
- `colcon test-result --verbose`: 58 tests, 0 errors, 0 failures, 0 skipped.
- Node-only launch smoke passed with `start_gazebo:=false start_nav2:=false use_sim_time:=false`; `/objectnav/status` and `/objectnav/selected_goal` were published from installed space.
- Trigger smoke without Nav2 passed; publishing `water_dispenser` to `/objectnav/goal` produced an `action_server_unavailable` status as expected.
- Full TurtleBot3 Gazebo/Nav2 smoke passed in `ROS_DOMAIN_ID=78`:
  - `/spawn_entity` ready after 2 seconds.
  - TurtleBot3 `waffle` spawned successfully.
  - `/odom` and `/navigate_to_pose` were available.
  - `/initialpose` was published at `x=-2.0`, `y=-0.5`, `yaw=0.0`.
  - `/objectnav/goal` with `water_dispenser` was accepted by the smoke node.
  - `/objectnav/status` reported `SUCCEEDED` with `nav2_succeeded`.
- After the final launch-code update, `python3 -m py_compile src/objectnav_ros/launch/turtlebot3_assumed_target_nav2.launch.py` passed.
- After the final launch-code update, focused assumed-target tests passed: 5 tests.
- After the final launch-code update, `colcon build --packages-select objectnav_ros --symlink-install` passed.
- After the final launch-code update, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+` passed with 21 core tests and 37 ROS tests.
- After the final launch-code update, `colcon test-result --verbose` reported 58 tests, 0 errors, 0 failures, 0 skipped.

Failed or corrected:

- `ros2 launch turtlebot3_navigation2 navigation2.launch.py --show-args` fails when `TURTLEBOT3_MODEL` is unset. The future launch wrapper should set or document this explicitly.
- The first full wrapper run failed because the top-level `params_file` launch argument leaked into Gazebo's nested `gzserver.launch.py`, causing `gzserver` to receive the Nav2 params file. The wrapper now uses `nav2_params_file` for Nav2 and leaves Gazebo's `params_file` empty.
- The next full wrapper run failed because `/spawn_entity` did not appear while Gazebo Classic stalled on the online model database. The wrapper now defaults `GAZEBO_MODEL_DATABASE_URI` to empty and prepends local model paths before including TurtleBot3 Gazebo.

Not run:

- No real robot test was run.
- No detector/perception stack was connected.
- No full ObjectNav state machine was run inside ROS.
- No repo-local screenshot artifact was saved.

## Next Recommended Step

The actual TurtleBot3 Gazebo/Nav2 smoke has passed. To reproduce it manually:

```bash
source install/setup.zsh
ros2 launch objectnav_ros turtlebot3_assumed_target_nav2.launch.py
```

Then set the TurtleBot3 initial pose in RViz near the Gazebo spawn pose, approximately `x=-2.0`, `y=-0.5`, and trigger the assumed target:

```bash
ros2 topic pub --once /objectnav/goal std_msgs/msg/String "{data: water_dispenser}"
```

Recommended next engineering step: add origin-aware `OccupancyGrid` handling before connecting full frontier exploration to TurtleBot3 maps, because the verified TurtleBot3 map origin is `[-10.0, -10.0, 0.0]`. A secondary useful step is to turn the successful smoke procedure into a launch test or documented CI/manual smoke script.

## Risks And Assumptions

- The TurtleBot3 map origin is nonzero, while current core grid conversion drops `OccupancyGrid.info.origin`. Avoid using core frontier selection on TurtleBot3 maps until origin support is designed and tested.
- A configured target pose must be checked in RViz because an unreachable target will make Nav2 fail for the right reason.
- Gazebo GUI may be slower or unavailable on some machines; keep a headless smoke path possible.
- This smoke validates Nav2 execution, not semantic detection or memory repair.
