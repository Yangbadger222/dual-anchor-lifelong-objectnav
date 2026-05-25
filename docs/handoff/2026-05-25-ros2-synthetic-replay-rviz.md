# Handoff: ROS 2 Synthetic Replay And RViz Markers

Date: 2026-05-25  
Owner: Codex  
Status: Ready for Review

## Current State

The first synthetic ROS replay and RViz-marker slice is implemented and tuned after the first manual RViz review.

Implemented:

- `objectnav_synthetic_replay` console script.
- `synthetic_replay.launch.py` launching both `objectnav_adapter` and `objectnav_synthetic_replay`.
- `synthetic_replay_rviz.launch.py` launching the replay nodes plus RViz.
- `rviz/synthetic_replay.rviz` with the costmap, TF, selected-goal, frontier-marker, and memory-marker displays.
- Synthetic replay publishers for:
  - `/objectnav/goal`
  - `/global_costmap/costmap` with reliable transient-local QoS
  - `/objectnav/object_observations` once the replay robot has detector visibility
  - `/objectnav/debug_markers`
  - `map -> base_link` TF
- Progressive costmap reveal and moving `base_link` pose in the replay loop.
- Adapter-node costmap subscription.
- Frontier extraction from replayed costmaps.
- `/objectnav/frontier_markers` `MarkerArray` publication.
- `/objectnav/selected_goal` `PoseStamped` publication for the first reachable replay frontier.
- `/objectnav/memory_markers` `MarkerArray` publication from accepted object observations.
- Clean SIGINT shutdown for `objectnav_adapter` and `objectnav_synthetic_replay`.
- Unit tests for synthetic message builders, progressive reveal, visibility-gated observation, marker builders, RViz config, costmap roundtrip, and replay callback behavior.

The user manually inspected the first RViz view and said it was broadly OK, but no repo-local screenshot or verification artifact has been saved yet.

This still does not run the full ObjectNav state machine in ROS and does not send live Nav2 goals.

## Files Touched

- `README.md`
- `docs/design/2026-05-25-ros2-synthetic-replay-rviz.md`
- `docs/devlog/2026-05.md`
- `docs/handoff/2026-05-24-ros2-nav2-adapter-skeleton.md`
- `docs/handoff/2026-05-25-ros2-synthetic-replay-rviz.md`
- `src/objectnav_ros/package.xml`
- `src/objectnav_ros/setup.py`
- `src/objectnav_ros/config/indoor_nav2_adapter.yaml`
- `src/objectnav_ros/launch/objectnav_adapter.launch.py`
- `src/objectnav_ros/launch/synthetic_replay.launch.py`
- `src/objectnav_ros/launch/synthetic_replay_rviz.launch.py`
- `src/objectnav_ros/rviz/synthetic_replay.rviz`
- `src/objectnav_ros/objectnav_ros/adapters/costmap_adapter.py`
- `src/objectnav_ros/objectnav_ros/adapters/visualization.py`
- `src/objectnav_ros/objectnav_ros/nodes/objectnav_node.py`
- `src/objectnav_ros/objectnav_ros/nodes/synthetic_replay_node.py`
- `src/objectnav_ros/tests/test_costmap_adapter.py`
- `src/objectnav_ros/tests/test_objectnav_node_replay.py`
- `src/objectnav_ros/tests/test_rviz_config.py`
- `src/objectnav_ros/tests/test_synthetic_replay.py`
- `src/objectnav_ros/tests/test_visualization.py`
- `runs/phase1a/latest/report.html`
- `runs/phase1a/latest/summary.json`

## Commands Run

```bash
git status --short --branch
sed -n '1,260p' src/objectnav_ros/objectnav_ros/nodes/objectnav_node.py
sed -n '1,280p' docs/design/2026-05-24-ros2-nav2-adapter.md
sed -n '1,220p' docs/handoff/2026-05-24-ros2-nav2-adapter-skeleton.md
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests/test_costmap_adapter.py src/objectnav_ros/tests/test_synthetic_replay.py src/objectnav_ros/tests/test_visualization.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests/test_objectnav_node_replay.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_core/tests src/objectnav_ros/tests -q
python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_ros/objectnav_ros
python3 -m py_compile src/objectnav_ros/launch/objectnav_adapter.launch.py src/objectnav_ros/launch/synthetic_replay.launch.py
rg -n "rclpy|nav2_msgs|nav_msgs|geometry_msgs|sensor_msgs|tf2_ros|visualization_msgs" src/objectnav_core/objectnav_core
PYTHONPATH=src/objectnav_core:${PYTHONPATH} python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 - <<'PY'
from objectnav_ros.nodes.synthetic_replay_node import make_synthetic_costmap_message, make_synthetic_observation_message, make_synthetic_base_transform
costmap = make_synthetic_costmap_message(frame_id='map')
obs = make_synthetic_observation_message(timestamp=1.0)
tf = make_synthetic_base_transform()
print({'costmap_cells': len(costmap.data), 'observation_bytes': len(obs.data), 'tf': f'{tf.header.frame_id}->{tf.child_frame_id}'})
PY
colcon build --packages-select objectnav_core objectnav_ros --event-handlers console_direct+
source install/setup.zsh && ros2 pkg executables objectnav_ros && python3 - <<'PY'
from objectnav_ros.nodes.synthetic_replay_node import make_synthetic_costmap_message, make_synthetic_observation_message
costmap = make_synthetic_costmap_message(frame_id='map')
observation = make_synthetic_observation_message(timestamp=1.0)
print({'cells': len(costmap.data), 'observation_has_target': 'water_dispenser' in observation.data})
PY
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+
colcon test-result --verbose
timeout 6s bash -lc 'source install/setup.bash && ros2 launch objectnav_ros synthetic_replay.launch.py'
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests/test_rviz_config.py -q
python3 -m py_compile src/objectnav_ros/launch/synthetic_replay_rviz.launch.py
timeout 18s bash -lc '
set -e
source install/setup.bash
ros2 launch objectnav_ros synthetic_replay.launch.py >/tmp/objectnav_synthetic_replay_smoke.log 2>&1 &
launch_pid=$!
cleanup() { kill ${launch_pid} >/dev/null 2>&1 || true; wait ${launch_pid} >/dev/null 2>&1 || true; }
trap cleanup EXIT
sleep 4
status=$(timeout 6s ros2 topic echo --once /objectnav/status std_msgs/msg/String --field data)
goal_frame=$(timeout 6s ros2 topic echo --once /objectnav/selected_goal geometry_msgs/msg/PoseStamped --field header.frame_id)
frontier_topic=$(timeout 6s ros2 topic info /objectnav/frontier_markers)
memory_topic=$(timeout 6s ros2 topic info /objectnav/memory_markers)
printf "status=%s\n" "$status"
printf "selected_goal_frame=%s\n" "$goal_frame"
printf "frontier_topic=%s\n" "$frontier_topic"
printf "memory_topic=%s\n" "$memory_topic"
'
timeout 8s bash -lc 'source install/setup.bash && ros2 launch objectnav_ros synthetic_replay_rviz.launch.py'
```

Additional commands run after the first RViz review:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_ros/tests/test_synthetic_replay.py src/objectnav_ros/tests/test_visualization.py src/objectnav_ros/tests/test_rviz_config.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core:src/objectnav_ros:${PYTHONPATH} python3 -m pytest src/objectnav_core/tests src/objectnav_ros/tests -q
python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_ros/objectnav_ros
python3 -m py_compile src/objectnav_ros/launch/objectnav_adapter.launch.py src/objectnav_ros/launch/synthetic_replay.launch.py src/objectnav_ros/launch/synthetic_replay_rviz.launch.py
rg -n "rclpy|nav2_msgs|nav_msgs|geometry_msgs|sensor_msgs|tf2_ros|visualization_msgs" src/objectnav_core/objectnav_core
PYTHONPATH=src/objectnav_core:${PYTHONPATH} python3 -m objectnav_core.cli.run_phase1a --output runs/phase1a/latest
colcon build --packages-select objectnav_core objectnav_ros --event-handlers console_direct+
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+
colcon test-result --verbose
timeout 30s bash -lc '
set -e
export ROS_DOMAIN_ID=45
source install/setup.bash
setsid ros2 launch objectnav_ros synthetic_replay.launch.py >/tmp/objectnav_synthetic_replay_domain45.log 2>&1 &
launch_pid=$!
cleanup() {
  kill -INT -${launch_pid} >/dev/null 2>&1 || true
  wait ${launch_pid} >/dev/null 2>&1 || true
}
trap cleanup EXIT
sleep 5
status=$(timeout 10s ros2 topic echo --once /objectnav/status std_msgs/msg/String --field data)
goal_frame=$(timeout 10s ros2 topic echo --once /objectnav/selected_goal geometry_msgs/msg/PoseStamped --field header.frame_id)
debug_line=$(timeout 10s ros2 topic echo --once /objectnav/debug_markers visualization_msgs/msg/MarkerArray | grep -m1 "Synthetic ObjectNav replay")
qos_lines=$(timeout 10s ros2 topic info /global_costmap/costmap -v | grep -E "Publisher count|Node name|Reliability|Durability" | head -8)
printf "status=%s\ngoal_frame=%s\ndebug_line=%s\n%s\n" "$status" "$goal_frame" "$debug_line" "$qos_lines"
'
timeout 12s bash -lc '
set -e
export ROS_DOMAIN_ID=44
source install/setup.bash
setsid ros2 launch objectnav_ros synthetic_replay_rviz.launch.py >/tmp/objectnav_synthetic_replay_rviz_domain44.log 2>&1 &
launch_pid=$!
sleep 7
kill -INT -${launch_pid} >/dev/null 2>&1 || true
wait ${launch_pid} >/dev/null 2>&1 || true
cat /tmp/objectnav_synthetic_replay_rviz_domain44.log
'
```

## Verification

Passed:

- Focused synthetic replay/visualization/RViz config tests: 13 passed.
- Adapter replay callback test: 1 passed.
- Adapter test suite: 32 passed.
- Core + adapter test suite: 53 passed.
- `python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_ros/objectnav_ros`.
- Launch files compile with `python3 -m py_compile`.
- Core-only ROS import scan returned no matches under `src/objectnav_core/objectnav_core`.
- Phase 1A artifact generation: 4 runs, all successful.
- Synthetic message smoke test created a 2880-cell costmap, JSON observation, and `map->base_link` TF.
- `colcon build --packages-select objectnav_core objectnav_ros --event-handlers console_direct+`: both packages built.
- Installed-space smoke test found `objectnav_adapter` and `objectnav_synthetic_replay`, and synthetic builders worked from installed modules.
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 colcon test --packages-select objectnav_core objectnav_ros --event-handlers console_direct+`: 21 core tests and 32 adapter tests passed.
- `colcon test-result --verbose`: 53 tests, 0 errors, 0 failures, 0 skipped.
- `timeout 6s bash -lc 'source install/setup.bash && ros2 launch objectnav_ros synthetic_replay.launch.py'` started both ROS nodes; exit code 124 was expected because `timeout` stopped the launch.
- RViz config tests: 2 passed.
- `python3 -m py_compile src/objectnav_ros/launch/synthetic_replay_rviz.launch.py`.
- Topic smoke passed: `/objectnav/status` produced an `observation_received` payload, `/objectnav/selected_goal` had frame `map`, and frontier/memory marker topics each had one publisher.
- `timeout 8s bash -lc 'source install/setup.bash && ros2 launch objectnav_ros synthetic_replay_rviz.launch.py'` started `objectnav_adapter`, `objectnav_synthetic_replay`, and `rviz2`; RViz reported OpenGL support and costmap creation. Exit code 124 was expected because `timeout` stopped the launch.
- Isolated-domain topic smoke passed with `ROS_DOMAIN_ID=45`: `/objectnav/status`, `/objectnav/selected_goal`, `/objectnav/debug_markers`, and `/global_costmap/costmap` were available, and the replay costmap publisher reported `RELIABLE` + `TRANSIENT_LOCAL`.
- Isolated-domain RViz smoke passed with `ROS_DOMAIN_ID=44`: `objectnav_adapter`, `objectnav_synthetic_replay`, and `rviz2` started, RViz created the 120 x 24 map, and all processes finished cleanly after SIGINT.
- Manual user RViz inspection was broadly OK, but no screenshot was committed.

Not run:

- No repo-local RViz screenshot or durable visual verification record.
- No recorded rosbag replay.
- No live Nav2 action server.
- No Gazebo.
- No robot trial.

## Known Risks

- Synthetic replay uses the Phase 1A corridor fixture and zero map origin; recorded bags with nonzero origins or transformed costmap frames still need handling.
- The adapter publishes the first reachable frontier viewpoint for replay visibility. It does not yet run the full ObjectNav manager or memory-aware candidate selection in ROS.
- Memory markers come directly from accepted replay object observations; persisted SQLite memory is not yet connected to ROS marker publication.
- Marker appearance has unit-test coverage but no visual RViz screenshot verification yet.
- A previous RViz/replay launch may still be active in the user's ROS graph. Close old windows/nodes before judging the current replay, or verify in an isolated `ROS_DOMAIN_ID`.

## Next Recommended Step

1. Close any old RViz/replay launch, then re-open RViz with the synthetic replay launch and visually inspect `/global_costmap/costmap`, `/objectnav/selected_goal`, `/objectnav/frontier_markers`, `/objectnav/memory_markers`, and `/objectnav/debug_markers`.
2. Save a verification record or screenshot after visual inspection.
3. Add a mocked Nav2 action server or launch-test harness.
4. Add recorded-bag replay only after synthetic replay looks correct in RViz.

## Context for Next Contributor

Use:

```bash
source install/setup.zsh
ros2 launch objectnav_ros synthetic_replay_rviz.launch.py
```

Then inspect the marker topics in RViz. This launch intentionally does not connect to a real Nav2 server or drive a robot.
