# Design Doc: TurtleBot3 Gazebo Assumed-Target Nav2 Smoke

Date: 2026-05-25  
Owner: Codex  
Status: Full TurtleBot3 Gazebo/Nav2 smoke passed

## Goal

Add the first Gazebo/Nav2 simulation slice using open-source TurtleBot3 assets before any real-robot trial.

The goal is to prove that the project can command a live Nav2 `NavigateToPose` action server in a reproducible simulator while keeping object semantics simple: a configured map pose is treated as the assumed location of a `water_dispenser`.

## Non-Goals

- Do not add real perception, detector models, camera projection, VLMs, or object recognition.
- Do not create a custom Gazebo robot or vehicle model.
- Do not require the real autonomous vehicle stack.
- Do not claim ObjectNav exploration success from this slice.
- Do not move ROS, Gazebo, or Nav2 dependencies into `objectnav_core`.
- Do not depend on a private map, campus route, or hardware-specific frame.

## Background

The current project state is:

- `objectnav_core` has deterministic ROS-free Phase 1A trials.
- `objectnav_ros` has ROS message adapters, a mock-testable Nav2 action-client wrapper, synthetic replay, and RViz markers.
- Synthetic replay verifies topic/frame visibility but does not run a live Nav2 action server.
- The local ROS 2 Humble environment already has `turtlebot3_gazebo`, `turtlebot3_navigation2`, `nav2_bringup`, `gazebo_ros`, and Gazebo binaries available.

The next integration risk is not object detection. It is whether the adapter boundary can safely command and observe a real Nav2 server. TurtleBot3 gives a reproducible open-source robot, world, map, and Nav2 configuration for that check.

## System Boundary

Owned by this slice:

- A TurtleBot3 Gazebo/Nav2 smoke launch or documented launch sequence.
- A small assumed-target configuration for semantic labels mapped to Nav2 goal poses.
- A ROS-side smoke node or CLI that sends the configured verification pose through the existing `Nav2NavigationClient`.
- Status output and optional RViz selected-goal marker for the assumed semantic target.
- Verification notes for launch, localization, action-server availability, goal dispatch, and result status.

Not owned by this slice:

- Full ObjectNav state-machine execution in ROS.
- Frontier exploration in the TurtleBot3 map.
- Costmap-origin-aware ObjectNav frontier selection.
- Real object detection or arrival verification from images.
- Real robot operation.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | TurtleBot3 model | Environment variable | Start with `TURTLEBOT3_MODEL=waffle` or another installed TurtleBot3 model. |
| Input | Gazebo world | `.world` | Prefer `turtlebot3_gazebo/worlds/turtlebot3_world.world` for first smoke. |
| Input | Nav2 map | `.yaml` + `.pgm` | Prefer `turtlebot3_navigation2/map/map.yaml`; origin is nonzero and must be handled carefully. |
| Input | Initial pose | `geometry_msgs/msg/PoseWithCovarianceStamped` | Scripted publish to `/initialpose` or manual RViz set pose. |
| Input | Assumed semantic target | YAML or node parameters | Example: `class_name=water_dispenser`, `pose={x, y, yaw}` in the Nav2 map frame. |
| Output | Nav2 goal | `nav2_msgs/action/NavigateToPose` | Sent through the existing `Nav2NavigationClient`. |
| Output | ObjectNav status | `std_msgs/msg/String` JSON | Include target label, goal pose, action status, and failure reason. |
| Output | Selected-goal marker | RViz marker or pose topic | Debug visualization for the assumed target pose. |
| Output | Verification record | Handoff/devlog or experiment report | Command, map, model, target pose, result, and failure notes. |

## Interfaces

Candidate package additions under `src/objectnav_ros`:

- `config/turtlebot3_assumed_targets.yaml`
- `launch/turtlebot3_assumed_target_nav2.launch.py`
- `objectnav_ros/nodes/assumed_target_nav2_smoke.py`
- focused tests for config parsing, goal construction, status mapping, and launch-file compilation

Implemented first:

- `assumed_target_nav2_smoke = objectnav_ros.nodes.assumed_target_nav2_smoke:main`
- `src/objectnav_ros/config/turtlebot3_assumed_targets.yaml`
- `src/objectnav_ros/launch/turtlebot3_assumed_target_nav2.launch.py`
- `src/objectnav_ros/tests/test_assumed_target_nav2_smoke.py`

Open-source TurtleBot3 launch assets already present locally:

- `turtlebot3_gazebo/launch/turtlebot3_world.launch.py`
- `turtlebot3_navigation2/launch/navigation2.launch.py`
- `turtlebot3_navigation2/map/map.yaml`
- `turtlebot3_navigation2/param/humble/waffle.yaml`

Default ROS interfaces:

- `/initialpose`
- `/map`
- `/tf`
- `/navigate_to_pose`
- `/objectnav/status`
- `/objectnav/selected_goal`

## Data Flow

1. Set `TURTLEBOT3_MODEL` and start TurtleBot3 Gazebo with the open-source TurtleBot3 world.
2. Start TurtleBot3 Nav2 with `use_sim_time:=true` and the matching open-source map.
3. Publish or manually set the TurtleBot3 initial pose near the Gazebo spawn pose.
4. Load an assumed semantic target from config, for example `water_dispenser` at a reachable map-frame verification pose.
5. The smoke node publishes the selected goal for RViz and sends the pose through `Nav2NavigationClient`.
6. Nav2 drives the TurtleBot3 to the pose and returns action feedback/result.
7. The smoke node publishes final status and records enough information for a verification note.

The first implementation defaults `send_goal_on_start=false`. This allows the operator to localize TurtleBot3 first, then trigger the assumed semantic goal with:

```bash
ros2 topic pub --once /objectnav/goal std_msgs/msg/String "{data: water_dispenser}"
```

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| `TURTLEBOT3_MODEL` missing | TurtleBot3 navigation launch raises `KeyError` | Export `TURTLEBOT3_MODEL=waffle` in launch docs or wrapper launch. |
| Gazebo GUI unavailable | `gzclient` fails or no display | Allow headless `gzserver` smoke first, then GUI/RViz manual check. |
| Gazebo Classic online model lookup stalls world load | `/spawn_entity` never appears; log stalls at `models.gazebosim.org` | Default the launch to local model lookup by setting `GAZEBO_MODEL_DATABASE_URI=""` and prepending local model paths. |
| TurtleBot spawn pose does not match map initial pose | AMCL poor localization or Nav2 cannot plan | Script `/initialpose` from the chosen world/map pair and document it. |
| Nav2 action server unavailable | `Nav2NavigationClient` reports `action_server_unavailable` | Keep status visible; do not send repeated goals. |
| Assumed target pose is unreachable | Nav2 aborts or planner reports failure | Move the configured pose to a known reachable free cell; record failed pose. |
| Map origin is nonzero | Core grid assumptions produce shifted goals | For this smoke, send configured map-frame Nav2 goals directly; defer origin-aware frontier selection to a later slice. |
| Old ROS graph pollutes verification | Duplicate nodes or stale topics | Use an isolated `ROS_DOMAIN_ID` for smoke tests. |

## Verification Plan

Phase 0, already checked locally:

- Confirm TurtleBot3, Nav2, Gazebo, and Gazebo ROS packages exist.
- Confirm TurtleBot3 world, map, and Nav2 parameter files exist.
- Confirm `TURTLEBOT3_MODEL` is required by TurtleBot3 navigation launch.

Phase 1, implementation verification:

- Add tests for assumed-target config parsing and Nav2 goal construction.
- Run `python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_ros/objectnav_ros`.
- Run focused `objectnav_ros` tests with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
- Run `colcon build --packages-select objectnav_core objectnav_ros`.
- Run `colcon test --packages-select objectnav_core objectnav_ros`.
- Run a core-only ROS import scan under `src/objectnav_core/objectnav_core`.

Current implementation verification completed:

- Focused assumed-target tests passed.
- Core + ROS pytest suite passed with 58 tests.
- `colcon build --packages-select objectnav_core objectnav_ros` passed.
- `colcon test --packages-select objectnav_core objectnav_ros` passed.
- Installed-space launch argument inspection passed.
- Node-only launch smoke passed with Gazebo/Nav2 disabled.
- Trigger smoke without a Nav2 server reported `action_server_unavailable` as expected.

Phase 2, simulation smoke completed:

- First full run exposed a launch-argument leak: using top-level `params_file` caused Gazebo `gzserver` to receive the Nav2 params file. The wrapper argument was renamed to `nav2_params_file`.
- The next full run exposed a Gazebo Classic model-database stall: `/spawn_entity` did not appear while Gazebo tried `http://models.gazebosim.org`. The launch now defaults `GAZEBO_MODEL_DATABASE_URI` to empty and prepends local Gazebo/TurtleBot3 model paths.
- Ran the full launch in isolated `ROS_DOMAIN_ID=78`.
- Verified `/spawn_entity` appeared after 2 seconds.
- Verified `/clock`, `/odom`, and `/navigate_to_pose` were available.
- Published initial pose `x=-2.0`, `y=-0.5`, `yaw=0.0` on `/initialpose`.
- Triggered the assumed target with `ros2 topic pub --once /objectnav/goal std_msgs/msg/String "{data: water_dispenser}"`.
- Nav2 returned `SUCCEEDED`; `/objectnav/status` reported `navigation_status=SUCCEEDED` and `result_reason=nav2_succeeded`.
- Main runtime log for this verification: `/tmp/objectnav_tb3_full_smoke_nomodeldb.log`.

## Research Relevance

This slice is a bridge between synthetic replay and real robot trials. It exercises real Nav2 behavior with a reproducible open-source robot and map while preserving the paper story: semantic ObjectNav logic remains hardware-independent, and platform-specific execution stays behind adapters.

Using an assumed target pose is intentional. It isolates the navigation and adapter contract before perception noise can hide integration bugs.

## Resolved Choices And Open Questions

- Use `waffle` as the first verified TurtleBot3 model.
- Use initial pose `x=-2.0`, `y=-0.5`, `yaw=0.0` for this TurtleBot3 world/map pair.
- Use `(x=1.5, y=0.0, yaw=0.0)` in `map` as the first verified assumed `water_dispenser` pose.
- Should this smoke node remain a test utility, or become the first ROS wrapper around the full ObjectNav manager later?
- The next technical question is whether to automate this smoke as a launch test or move directly to origin-aware `OccupancyGrid` conversion and full ObjectNav state-machine wiring.
