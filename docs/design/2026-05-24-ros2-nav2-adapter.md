# Design Doc: ROS 2 Nav2 Adapter

Date: 2026-05-24  
Owner: Codex  
Status: Draft

## Goal

Define the first ROS 2 adapter layer that connects the hardware-independent ObjectNav core to a Nav2-based robot stack without adding ROS dependencies to `objectnav_core`.

The adapter should translate ROS 2 topics, TF, costmaps, object observations, visualization data, and Nav2 `NavigateToPose` actions into the stable core concepts already proven in Phase 1A.

## Non-Goals

- This design does not implement ROS 2 code yet.
- This design does not change `objectnav_core` imports or schemas.
- This design does not tune Nav2 controllers, costmaps, localization, FAST-LIO2, or PGO.
- This design does not add a real detector, VLM, RTK driver, or robot launch stack.
- This design does not run live robot trials.
- This design does not hard-code a vehicle, map path, route, camera device, detector model, or campus-specific frame.

## Background

Phase 1A now has a ROS-free executable core with deterministic mapping, frontier policies, A* path-cost estimation, memory, metrics, and report generation. The next integration step is to design the adapter that will eventually run on a ROS 2 machine or container.

The architecture boundary remains:

- `objectnav_core` owns ObjectNav state, memory semantics, candidate scoring, verification logic, metrics, and artifact generation.
- `objectnav_ros` owns ROS 2 subscriptions, publications, TF lookups, Nav2 actions, RViz markers, and deployment-specific parameters.

The user's current computer does not have ROS 2 installed. Therefore the immediate output should be design and later an adapter skeleton that can be syntax-checked where possible, but only built with `colcon` on a ROS 2 environment.

## System Boundary

### Owned by `objectnav_ros`

- ROS 2 package metadata and launch/config files.
- ROS 2 node lifecycle and parameters.
- Object goal intake from topic or action.
- Occupancy/costmap subscription and conversion to core grid-like inputs.
- TF pose lookup and localization-quality reporting.
- Nav2 `NavigateToPose` action client wrapper.
- Object observation subscription adapter.
- RViz marker publishers for frontiers, selected goals, and memory records.
- Adapter-level logs that identify ROS timestamps, frame ids, topic names, and Nav2 result codes.

### Owned by `objectnav_core`

- Target and trial state.
- Frontier and memory candidate scoring.
- Memory state transitions such as reusable, suspect missing, missing, and relocation evidence.
- Arrival verification decisions.
- SQLite memory and trial metrics.
- Report generation.

### Outside this boundary

- Low-level robot safety and emergency stop.
- SLAM, localization, FAST-LIO2, PGO, and map optimization.
- Nav2 planner/controller/recovery tuning.
- Detector training and camera calibration.
- RTK driver integration.

## Inputs and Outputs

| Direction | Name | ROS 2 Type / Core Form | Notes |
|---|---|---|---|
| Input | ObjectNav goal | topic/action to normalized core goal | First version can use a string class label such as `water_dispenser`. |
| Input | Occupancy/cost map | `nav_msgs/msg/OccupancyGrid` to core occupancy grid | Unknown, free, occupied thresholds must be parameters. |
| Input | Robot pose | TF `map -> base_link` or configured frames to `Pose2D` plus quality | Frame ids are parameters, not hard-coded. |
| Input | Object observation | custom or JSON-like message to `ObjectObservation` | Must include class, confidence, pose, anchor, frame, detector name, timestamp. |
| Input | Nav2 feedback/result | `NavigateToPose` feedback/result to navigation status | Adapter maps Nav2 result codes to core-compatible status/reason. |
| Output | Nav2 goal | `nav2_msgs/action/NavigateToPose` | Sent only by adapter after core selects a navigation goal. |
| Output | ObjectNav status | ROS topic | Includes active target, state, candidate type, and failure reason. |
| Output | Frontier markers | RViz markers | Debug output only; not consumed by core. |
| Output | Selected-goal marker | RViz marker | Shows selected viewpoint and yaw. |
| Output | Memory markers | RViz markers | Shows reusable, stale, missing, and relocated objects. |
| Output | Adapter logs | SQLite/event log payloads | Include ROS time, frame ids, topic names, and Nav2 status. |

## Interfaces

### Package layout target

```text
src/
  objectnav_core/
    objectnav_core/
      ...
  objectnav_ros/
    package.xml
    setup.py
    setup.cfg
    resource/objectnav_ros
    objectnav_ros/
      __init__.py
      nodes/
        objectnav_node.py
      adapters/
        costmap_adapter.py
        nav2_navigation_client.py
        object_observation_adapter.py
        tf_pose_provider.py
        visualization.py
      config/
        indoor_nav2_adapter.yaml
      launch/
        objectnav_adapter.launch.py
    tests/
      test_import_boundaries.py
      test_costmap_adapter.py
      test_nav2_status_mapping.py
```

### ROS 2 topics and actions

These names are design defaults. They must be configurable:

| Interface | Direction | Type | Purpose |
|---|---|---|---|
| `/objectnav/goal` | Subscribe | first version: `std_msgs/msg/String` | Start a target-class ObjectNav task. |
| `/objectnav/status` | Publish | first version: JSON string or future custom msg | Report state, target, candidate, and failure reason. |
| `/objectnav/selected_goal` | Publish | `geometry_msgs/msg/PoseStamped` | Show the selected Nav2 goal. |
| `/objectnav/frontier_markers` | Publish | `visualization_msgs/msg/MarkerArray` | RViz frontier debug markers. |
| `/objectnav/memory_markers` | Publish | `visualization_msgs/msg/MarkerArray` | RViz memory debug markers. |
| `/objectnav/object_observations` | Subscribe | first version: JSON string or future custom msg | Ingest projected object observations. |
| `/global_costmap/costmap` | Subscribe | `nav_msgs/msg/OccupancyGrid` | Provide occupancy-like grid input. |
| `/tf` and `/tf_static` | Subscribe through TF buffer | TF transforms | Provide robot pose and frame transforms. |
| `navigate_to_pose` | Action client | `nav2_msgs/action/NavigateToPose` | Execute selected viewpoints. |

### Parameters

Minimum adapter parameters:

| Parameter | Example | Reason |
|---|---|---|
| `map_frame` | `map` | Target frame for core map coordinates. |
| `base_frame` | `base_link` | Robot body frame for pose lookup. |
| `costmap_topic` | `/global_costmap/costmap` | Avoid hard-coded Nav2 topic names. |
| `navigate_to_pose_action` | `navigate_to_pose` | Allows namespaced robots. |
| `goal_topic` | `/objectnav/goal` | Allows test and deployment remapping. |
| `object_observation_topic` | `/objectnav/object_observations` | Allows detector adapter swap. |
| `memory_db_path` | configured path | Keeps experiment memory explicit. |
| `target_anchor_id` | `indoor_map_corridor_a` | Avoids implicit map identity. |
| `free_threshold` | `25` | OccupancyGrid conversion threshold. |
| `occupied_threshold` | `65` | OccupancyGrid conversion threshold. |
| `unknown_value` | `-1` | OccupancyGrid unknown convention. |
| `navigation_timeout_s` | `120.0` | Prevents silent hanging action goals. |
| `replan_interval_s` | `2.0` | Low-frequency event-driven replanning. |
| `publish_markers` | `true` | Debug output toggle. |

## Data Flow

1. `objectnav_node` receives an ObjectNav target goal.
2. The adapter normalizes the goal and starts or resumes the core task state.
3. `tf_pose_provider` looks up the current robot pose in `map_frame`.
4. `costmap_adapter` converts the latest ROS occupancy/costmap into the core occupancy-like grid representation.
5. The core queries memory and evaluates frontier or memory candidates.
6. The adapter publishes frontier and selected-goal debug markers.
7. `nav2_navigation_client` converts the selected core `Pose2D` viewpoint into `NavigateToPose.Goal`.
8. Nav2 executes the goal and returns feedback or result.
9. Object observations may arrive asynchronously and are converted into core `ObjectObservation` records.
10. On arrival, the core verifier decides verified, not found, ambiguous, suspect missing, or missing.
11. The adapter publishes `/objectnav/status`, updates markers, and writes trial events/metrics through core storage.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| TF unavailable | TF lookup timeout or exception | Publish status `waiting_for_pose`; do not send Nav2 goal. |
| Costmap unavailable | No map message received within timeout | Publish status `waiting_for_map`; do not replan. |
| Costmap frame mismatch | map message frame differs from `map_frame` | Reject map or require configured transform. |
| Goal pose outside known free map | costmap conversion or planner reports blocked | Ask core to choose another candidate or mark candidate unreachable. |
| Nav2 action server unavailable | action client wait timeout | Publish `navigation_unavailable`; keep task active but not executing. |
| Nav2 goal rejected | action response rejected | Log event, mark navigation failure, request replan. |
| Nav2 aborts or times out | result code or adapter timeout | Log result reason and request replan or fail task by policy. |
| Object observation frame mismatch | observation frame not transformable to `map_frame` | Reject observation and log adapter error. |
| Detector publishes stale observation | timestamp older than configured threshold | Ignore or mark low-confidence evidence. |
| Adapter leaks robot-specific assumptions into core | import/config review catches hard-coded topic, frame, path, device | Move value to adapter config and keep core unchanged. |

## Verification Plan

### On this non-ROS machine

- Keep `objectnav_core` ROS-free by scanning for `rclpy`, ROS messages, TF, and Nav2 imports under `src/objectnav_core/objectnav_core`.
- Add only design docs until a ROS 2 environment is available.
- Review package boundaries and parameter names.
- Verify docs do not contain unresolved placeholders.

### On a ROS 2 machine or container

1. Build packages:

   ```bash
   colcon build --packages-select objectnav_core objectnav_ros
   source install/setup.bash
   ```

2. Run adapter unit tests:

   ```bash
   colcon test --packages-select objectnav_ros
   colcon test-result --verbose
   ```

3. Run adapter-level tests with mocked ROS messages:
   - costmap conversion thresholds
   - TF pose conversion
   - Nav2 result-code mapping
   - object observation conversion and stale timestamp rejection
   - import boundary: `objectnav_core` does not import ROS

4. Run rosbag replay before live robot:
   - replay costmap, TF, and object observations
   - verify selected goals and markers are published
   - verify no Nav2 action is sent when map or pose is invalid

5. Only after replay passes, run live robot trials with safety supervision.

## Research Relevance

This adapter design protects the core research claim: the ObjectNav method is hardware-independent and can transfer to a ROS 2/Nav2 robot through explicit translation layers. It also gives future experiments a clean place to measure adapter failure modes separately from ObjectNav policy failures.

## Open Questions

- Should `/objectnav/goal` become a custom action before first live trials, or is `std_msgs/String` enough for early integration?
- Should object observations use a custom ROS message package, JSON strings, or an existing vision message type for the first adapter skeleton?
- Should the first Nav2 integration use only memory-target navigation before enabling frontier exploration on a live robot?
- Which ROS 2 distribution and Nav2 version should be the first supported integration target?
- Should adapter replay tests use recorded bags from the real stack or synthetic ROS messages first?
