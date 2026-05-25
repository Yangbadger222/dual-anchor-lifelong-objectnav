# Design Doc: ROS 2 Synthetic Replay And RViz Markers

Date: 2026-05-25  
Owner: Codex  
Status: Implemented

## Goal

Add the first ROS 2 replay and visualization slice for `objectnav_ros` so adapter behavior can be inspected in RViz before Gazebo or robot trials.

The slice should publish synthetic ROS messages, consume them through the adapter node, and expose selected goals, frontier markers, memory markers, replay debug markers, and status without sending live robot commands.

## Non-Goals

- Do not run Gazebo.
- Do not connect to a live Nav2 action server.
- Do not execute robot motion.
- Do not add detector, VLM, camera, depth, RTK, or vehicle launch dependencies.
- Do not move ObjectNav decision logic into `objectnav_core` ROS imports.

## Background

Phase 1A has a deterministic ROS-free ObjectNav core. The first `objectnav_ros` skeleton can build with ROS 2 Humble and has conversion adapters plus a mock-tested Nav2 action-client wrapper.

The next integration risk is observability: before a real Nav2 goal is sent, we need to see whether costmaps, frontiers, selected goals, and memory observations land in the correct frame and topic shape. RViz markers and synthetic replay are the cheapest way to catch frame, threshold, topic, and visualization mistakes.

## System Boundary

Owned by this slice:

- A synthetic replay node that publishes a deterministic but progressive costmap, target goal, visibility-gated object observation, moving base transform, and debug legend marker.
- Adapter-node subscriptions for costmap replay.
- RViz marker helper functions for frontiers and object memory.
- Publications for `/objectnav/selected_goal`, `/objectnav/frontier_markers`, `/objectnav/memory_markers`, and `/objectnav/debug_markers`.
- A reusable RViz config for synthetic replay inspection.

Not owned by this slice:

- Nav2 live execution.
- Full ObjectNav state-machine execution in ROS.
- TF lookup as the authoritative pose provider.
- Archived RViz screenshots or durable qualitative verification records.
- Gazebo worlds and physics.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Synthetic goal | `std_msgs/msg/String` | Target class such as `water_dispenser`. |
| Input | Synthetic costmap | `nav_msgs/msg/OccupancyGrid` | Generated from the Phase 1A corridor fixture with progressive reveal; publisher uses reliable transient-local QoS for RViz late joiners. |
| Input | Synthetic object observation | `std_msgs/msg/String` JSON | Same schema accepted by `object_observation_adapter`; published only once the replay robot has detector visibility. |
| Input | Synthetic TF | `TransformStamped` via `tf2_ros.TransformBroadcaster` | Moving `map -> base_link`, for RViz context. |
| Output | Status | `std_msgs/msg/String` JSON | Ready, goal received, costmap received, selected goal, observation received/rejected. |
| Output | Selected goal | `geometry_msgs/msg/PoseStamped` | First replay-selected frontier viewpoint in `map` frame. |
| Output | Frontier markers | `visualization_msgs/msg/MarkerArray` | CUBE_LIST marker in the configured map frame. |
| Output | Memory markers | `visualization_msgs/msg/MarkerArray` | Object observation marker and text label. |
| Output | Replay debug markers | `visualization_msgs/msg/MarkerArray` | Text legend with current replay step and `base_link` pose. |

## Interfaces

New or expanded package entries:

- `objectnav_synthetic_replay = objectnav_ros.nodes.synthetic_replay_node:main`
- `objectnav_ros.adapters.visualization`
- `launch/synthetic_replay.launch.py`
- `launch/synthetic_replay_rviz.launch.py`
- `rviz/synthetic_replay.rviz`

Default topics:

- `/objectnav/goal`
- `/objectnav/status`
- `/objectnav/selected_goal`
- `/objectnav/frontier_markers`
- `/objectnav/memory_markers`
- `/objectnav/debug_markers`
- `/objectnav/object_observations`
- `/global_costmap/costmap`
- `/tf`

## Data Flow

1. `objectnav_synthetic_replay` periodically publishes a `water_dispenser` goal, a progressively revealed corridor costmap, replay debug markers, and a moving `map -> base_link` transform.
2. `objectnav_adapter` receives the goal and records the active target class.
3. `objectnav_adapter` receives the costmap, converts it to core `OccupancyGrid`, extracts frontiers, and publishes frontier markers.
4. If an active target and reachable frontier exist, `objectnav_adapter` publishes a selected frontier viewpoint as `PoseStamped`.
5. Once the synthetic detector has range, FOV, and line-of-sight visibility, `objectnav_synthetic_replay` publishes the object observation.
6. `objectnav_adapter` receives object observations, validates JSON/staleness, and publishes memory markers.
7. Status messages describe every accepted or rejected replay step.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Costmap conversion fails | Exception from `occupancy_grid_to_core_grid` | Publish status `costmap_rejected`; do not publish selected goal. |
| No frontier exists | Empty frontier list | Publish status `frontiers_empty`; no selected goal. |
| Frontier viewpoint fails | `plan_frontier_viewpoint` raises `ValueError` | Publish status `selected_goal_unavailable`. |
| Marker publication disabled | `publish_markers=false` | Publish status and selected goal only. |
| Observation JSON invalid/stale | Adapter exception | Publish status `observation_rejected`; do not publish memory marker. |
| RViz frame mismatch | Markers or selected goal show wrong frame | Keep `map_frame` configurable and covered in marker tests. |
| Old replay launch remains active | Duplicate node names or QoS warnings in RViz/topic info | Close the old launch or use an isolated `ROS_DOMAIN_ID` for verification. |

## Verification Plan

- Unit-test synthetic message builders, progressive reveal, and visibility-gated observation.
- Unit-test marker helper outputs for frame ids, namespaces, marker types, and point counts.
- Unit-test adapter node callback behavior with fake publishers where possible.
- Run core and adapter pytest.
- Run `colcon build` and `colcon test`.
- Run a non-GUI smoke test that starts from installed Python modules and builds synthetic replay messages.
- Run a topic smoke test against the launched replay nodes.
- Run a short RViz launch smoke test to confirm RViz starts, loads the synthetic costmap config, and exits cleanly under SIGINT.
- Treat manual visual inspection as provisional until a screenshot or verification record is saved in the repo.

## Research Relevance

This slice makes the ROS boundary inspectable before expensive simulation or risky robot trials. It supports the paper claim that the ObjectNav core transfers through explicit adapters by making adapter failures visible and testable separately from algorithm failures.

## Open Questions

- Should synthetic replay later write a verification record with screenshots?
- Should selected-goal publication remain frontier-only for replay, or move behind the full core state machine after a mocked Nav2 harness exists?
