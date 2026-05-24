# Design Doc: Hardware-Independent Dual-Anchor Lifelong ObjectNav Architecture

Date: 2026-05-24  
Owner: Codex  
Status: Draft

## Goal

Define the first system architecture for Dual-Anchor Lifelong Semantic ObjectNav.

The main goal is to develop and verify the ObjectNav system independently from a specific vehicle first, then connect it to the real FAST-LIO2 + PGO + Nav2 autonomous vehicle through explicit adapters. This keeps the research system general, easier to test, and easier to defend as a paper contribution.

## Non-Goals

- This design does not implement the runtime package.
- This design does not choose final detector weights, camera hardware, RTK hardware, or vehicle-specific launch files.
- This design does not train an end-to-end policy or build a full semantic SLAM system.
- This design does not put VLM or LLM calls in the real-time control loop.
- This design does not claim experimental results. Results require separate experiment reports.

## Background

The project already has a real autonomous navigation base in mind:

- FAST-LIO2 for LiDAR-inertial odometry
- PGO for global map correction
- Nav2 / MPPI for navigation and local control
- occupancy grid or costmap inputs for exploration
- planned RTK / ENU support for outdoor anchoring

The ObjectNav layer should add semantic goal seeking above this base. The key research direction is not "attach a detector to a robot." The stronger direction is a modular system that combines active exploration, semantic observations, long-term memory, dual anchors, and arrival verification.

The user explicitly wants to first develop this system away from the physical vehicle, test it, and later attach it to the real robot. This design treats that as a core architectural requirement.

## Approaches Considered

| Approach | Pros | Cons | Decision |
|---|---|---|---|
| Build directly inside the real ROS 2 vehicle stack | Fast path to a demo if the robot is available | Hardware, calibration, launch, and safety issues can hide algorithm problems; lower generality | Do not start here |
| Build a pure offline research core first | Easy unit tests, replay, baselines, and paper-ready ablations | Needs adapter work before real robot demos | Use as the core approach |
| Build a ROS 2 package first but keep hardware behind interfaces | Keeps future integration close to deployment | Can still leak vehicle assumptions into core logic | Use later for adapters |

## Decision

Use a three-layer architecture:

1. Hardware-independent ObjectNav core
2. Replay and simulation harness
3. Robot adapters for ROS 2, Nav2, sensors, and anchors

The core owns ObjectNav decisions and memory semantics. The robot layer only translates between real ROS 2 interfaces and core interfaces.

## System Boundary

### Owned by the ObjectNav core

- ObjectNav task state machine
- frontier extraction from occupancy-like grids
- frontier and target candidate scoring
- memory-aware semantic frontier policy
- semantic memory schema and query/update behavior
- fresh, verified, stale, missing, and ambiguous memory states
- arrival verification decision interface
- trial event logging and metrics schema
- baseline policy selection

### Owned by replay and simulation harnesses

- deterministic grid maps
- fake object sources
- recorded map, pose, image, and object-observation playback
- scripted target movement or stale-memory cases
- metric calculation from saved trial events

### Owned by robot adapters

- ROS 2 topic subscriptions and publications
- Nav2 `NavigateToPose` action client
- TF lookup and frame transforms
- camera, depth, point cloud, and detector adapter code
- RTK / ENU anchor adapter
- RViz markers and launch files

### Outside this system boundary

- low-level motor control
- SLAM and localization algorithms
- Nav2 controller tuning
- physical safety behavior
- detector model training
- dataset collection infrastructure

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Object goal | structured goal or ROS topic, for example target class `trash_bin` | Should support text labels but core should receive a normalized class or query object |
| Input | Occupancy or cost map | grid with resolution, origin, free, occupied, unknown cells | Comes from offline map, simulation, rosbag, or `/global_costmap/costmap` |
| Input | Robot pose | timestamped pose with covariance | Can be simulated, replayed, or from TF/localization |
| Input | Object observation | class, confidence, pose estimate, covariance, detector name, anchor type | Fake first, detector/projector later |
| Input | Anchor state | map anchor, RTK/ENU anchor, covariance, transform quality | Used for uncertainty-aware scoring |
| Input | Session config | scene id, map id, target class, baseline policy, thresholds | Required for reproducible experiments |
| Output | Selected navigation goal | pose candidate with source and score terms | Can become a Nav2 goal through adapter |
| Output | ObjectNav status | state, active target, candidate id, reason for transition | Useful for logs and RViz |
| Output | Memory update | object, place, frontier, anchor, and edge records | Persisted in SQLite or JSON |
| Output | Trial log | events, metrics, failures, command parameters | Required for experiment reports |
| Output | Visualization data | frontier markers, memory markers, selected goal | Optional outside ROS, required for robot debugging |

## Interfaces

### Core interfaces

The core should be written against abstract interfaces, even if the first implementation is simple Python:

| Interface | Responsibility |
|---|---|
| `MapProvider` | Provide the latest occupancy-like grid and map metadata |
| `PoseProvider` | Provide current robot pose and localization quality |
| `ObjectObservationSource` | Provide detected or fake object observations |
| `MemoryStore` | Query and update object, place, frontier, anchor, and session memory |
| `GoalSelector` | Score candidate memory targets and frontier targets |
| `NavigationClient` | Send, cancel, and report navigation goals |
| `ArrivalVerifier` | Confirm, reject, or mark target observation ambiguous near a goal |
| `TrialLogger` | Persist structured events and summary metrics |

### Future ROS 2 interface targets

These names are design targets, not yet implemented:

| Interface | Type | Purpose |
|---|---|---|
| `/objectnav/goal` | topic or action | Start an ObjectNav task |
| `/objectnav/status` | topic | Report state machine transitions and active target |
| `/objectnav/frontiers` | topic | Publish frontier candidates |
| `/objectnav/selected_goal` | topic | Publish selected navigation goal |
| `/objectnav/object_observations` | topic | Publish projected object observations |
| `/objectnav/memory_markers` | topic | Visualize memory in RViz |
| `Nav2 NavigateToPose` | action | Execute selected goals |
| `/semantic_memory/query` | service | Query stored objects or places |
| `/semantic_memory/update` | service | Insert or update memory records |
| `/semantic_memory/mark_stale` | service | Mark stale or missing memory |

### Persistence format

Start with SQLite for reproducible queries and experiment logs. JSON may be used for a tiny prototype, but paper-oriented trials should use a stable schema.

Minimum tables:

- `objects`
- `places`
- `frontiers`
- `anchors`
- `edges`
- `sessions`
- `trial_events`
- `trial_metrics`

## Data Flow

1. A task starts with a normalized object goal, for example `trash_bin`.
2. `ObjectNavManager` queries `MemoryStore`.
3. If reliable memory exists, the manager creates a memory-target candidate.
4. If no reliable memory exists, or if memory is stale, the manager requests frontier candidates from the current grid.
5. `GoalSelector` scores memory candidates and frontier candidates with:
   - target belief
   - information gain
   - memory prior
   - path cost
   - revisit penalty
   - anchor uncertainty
   - stale-memory risk
6. `NavigationClient` sends the selected pose to a replay navigator, simulator navigator, or Nav2 adapter.
7. During navigation, object observations may interrupt exploration and produce a direct object target.
8. On arrival, `ArrivalVerifier` returns `verified`, `not_found`, or `ambiguous`.
9. `MemoryStore` updates object state:
   - `verified` or `fresh` after confirmation
   - `stale` when confidence or age is weak
   - `missing` when a remembered object is not found
   - `ambiguous` when evidence is conflicting
10. `TrialLogger` records every transition, decision, score, navigation result, verification result, and final metric.

## Architecture Phases

### Phase 0: Architecture and documentation

- Create this system architecture design.
- Keep the hardware-independent boundary explicit.
- Define the first implementation plan after review.

### Phase 1A: Indoor water dispenser closed loop

Build the first deterministic loop without depending on outdoor RTK, indoor-outdoor transition logic, or a live detector.

The first target class is `water_dispenser`, in a straight indoor corridor with one wall-adjacent water dispenser. The only active anchor is `indoor_map`, but the data model must already carry `anchor_id`, `anchor_type`, and `frame_id` so the same interfaces can support outdoor ENU later.

The first closed loop is:

`goal -> memory query -> frontier selection -> visibility-triggered fake detection -> verification viewpoint -> arrival verification -> memory update -> memory reuse`

Expected modules:

- object goal and task state model
- grid map fixture loader
- frontier extractor
- nearest and information-gain selectors
- `ConfigTruthObjectSource` for deterministic fake detections
- `ManualInjectedObjectSource` for later RViz or live-debug injection
- visibility-triggered fake detector
- verification viewpoint planner
- SQLite memory store with JSON snapshot export
- trial logger

Key Phase 1A assumptions:

- the robot uses a fixed front-facing camera
- the detector cannot rely on a gimbal or vertical camera motion
- the navigation target is a verification viewpoint, not the object center
- the initial viewpoint for a wall-adjacent water dispenser should be roughly 1.2 m in front of the object, yawed toward the object center
- if the preferred viewpoint lies inside obstacle or inflation space, the planner should retreat along the candidate view direction until it finds a reachable pose or marks the viewpoint unreachable

The scene config should support hidden ground truth for repeatable fake detection:

```yaml
scene_id: straight_corridor_one_water_dispenser_unknown
anchor:
  anchor_id: indoor_map_corridor_a
  anchor_type: indoor_map
  frame_id: map

map:
  resolution_m: 0.1
  width_m: 12.0
  height_m: 2.4
  known_at_start:
    x_min: 0.0
    x_max: 3.0
    y_min: 0.0
    y_max: 2.4

reveal_model:
  type: forward_sector
  max_range_m: 3.0
  horizontal_fov_deg: 120
  update_on_pose_change_m: 0.2
  update_on_yaw_change_deg: 10
  raycast_step_m: 0.05

objects:
  - object_id: water_dispenser_001
    class_name: water_dispenser
    pose_map: {x: 8.0, y: 0.25, yaw: 1.5708}
    size_hint: {width: 0.45, depth: 0.45, height: 1.30}
    placement: wall_adjacent
    preferred_standoff_m: 1.2

fake_detector:
  max_range_m: 4.0
  min_range_m: 0.8
  horizontal_fov_deg: 70
  require_line_of_sight: true
```

The first map fixture should start as a partially unknown straight corridor:

- `map` frame, meters
- 12.0 m long, 2.4 m wide
- boundary walls at `x = 0`, `x = 12`, `y = 0`, and `y = 2.4`
- known free area from `x = 0` to `x = 3`
- unknown free area from `x = 3` to `x = 12`
- start `S0 = (1.0, 1.2, 0.0)`
- alternate start `S1 = (2.2, 1.2, 0.0)`
- water dispenser at `(8.0, 0.25)`, adjacent to the lower wall

The offline reveal model should be `forward_sector`, not radius reveal. It simulates a forward-facing mapping sensor:

- reveal unknown cells only inside a forward sector from the robot pose
- respect line of sight with walls and obstacles by raycasting
- keep cells outside the sector unknown
- use a wider mapping/reveal field of view than the fake camera detector, for example 120 degrees for mapping and 70 degrees for fake camera detection

Frontier goals should also use viewpoint semantics. A frontier cluster is an unknown boundary next to known free space, but the navigation goal should be a reachable free cell on the known side of the frontier, yawed toward the frontier centroid. The system should not navigate to the raw frontier centroid when that centroid lies on or beyond the unknown boundary.

The Phase 1A frontier score should remain simple:

```text
score = information_gain - path_cost - revisit_penalty
```

The manager replans only on events:

- current goal reached
- current goal invalidated
- fake detector observes `water_dispenser`
- current frontier disappears after map reveal
- replan interval timeout, for example 2 s

The first navigation backend should implement the `NavigationClient` interface with deterministic discrete stepping:

- `send_goal(goal_pose)`
- `cancel_goal()`
- `tick(dt)`
- status values: `IDLE`, `ACTIVE`, `SUCCEEDED`, `FAILED`, `CANCELED`
- result reason

The first implementation may move directly toward the goal with a fixed step size and yaw interpolation. Later replacements should include an A* grid navigation client and a Nav2 `NavigateToPose` adapter without changing the manager.

The first package layout should separate core logic from ROS:

```text
src/
  objectnav_core/
    objectnav_core/
      models/
      mapping/
      planning/
      memory/
      simulation/
      evaluation/
    tests/

  objectnav_ros/        # later adapter package
    objectnav_ros/
```

`objectnav_core` must not import `rclpy` or ROS messages. `objectnav_ros` should translate ROS topics, TF, Nav2 actions, and visualization messages into core interfaces.

Core models should use Pydantic:

- validate scene configs, trial configs, memory records, and trial events
- use enums or literals for anchor type, memory state, navigation status, event type, and relation type
- keep ROS message shapes out of the core schema
- allow YAML config loading and JSON snapshot export through validated models

SQLite is the primary memory and trial backend. JSON is only for debug snapshots and human-readable exports.

Runtime rule:

- SQLite does not participate in high-frequency full-table scans
- the manager uses an active in-memory candidate cache during ticks
- SQLite queries happen on task start, memory mutation, replan events, or low-frequency refresh
- queries are shaped as bounded class/state/anchor queries, not `SELECT *`

Minimum Phase 1A SQLite tables:

- `anchors`
- `objects`
- `object_viewpoints`
- `object_observations`
- `object_relations`
- `trial_events`
- `trial_metrics`

Minimum indexes:

```sql
CREATE INDEX idx_objects_class_state_anchor
ON objects(class_name, state, anchor_id);

CREATE INDEX idx_objects_anchor_xy
ON objects(anchor_id, x, y);

CREATE INDEX idx_observations_object_time
ON object_observations(object_id, timestamp);

CREATE INDEX idx_trial_events_trial_time
ON trial_events(trial_id, timestamp);
```

Trial logging should record key events and candidate scores at each replan, but not every tick. Required event classes include task/state events, map/frontier events, object observation events, navigation events, verification events, memory mutation events, and relocation test interventions.

Default Phase 1A metrics:

- `success`
- `failure_reason`
- `final_state`
- `path_length_m`
- `elapsed_time_s`
- `num_nav_goals`
- `num_nav_failures`
- `frontier_count_total`
- `frontier_selected_count`
- `repeated_exploration_ratio`
- `map_coverage_at_success`
- `unknown_area_reduction`
- `time_to_first_observation_s`
- `time_to_verify_s`
- `observation_count`
- `verification_attempt_count`
- `failed_viewpoint_count`
- `memory_reused`
- `memory_query_count`
- `memory_hit_count`
- `memory_state_transition_count`
- `stale_recheck_count`
- `missing_detection_success`
- `relocation_recorded`
- `num_replans`
- `selected_candidate_types`
- `final_candidate_score`

Optional debug metrics:

- `sqlite_query_count`
- `sqlite_query_time_ms`
- `active_memory_cache_hits`
- `candidate_count_per_replan`
- `module_runtime_ms`

The fake detector must not publish the object immediately. It should publish a `water_dispenser` observation only when the robot enters the configured visibility sector:

- distance is within the detector range
- horizontal angle is inside the camera field of view
- line of sight is not blocked in the grid or costmap
- the object is active in the scene config

Memory states required in Phase 1A:

- `observed`
- `verified`
- `reusable`
- `stale`
- `suspect_missing`
- `missing`

The state flow is:

1. fake detector sees the water dispenser: `observed`
2. robot reaches a verification viewpoint and sees it again: `verified`
3. verified memory becomes available for future tasks: `reusable`
4. age, manual test control, or weak evidence marks memory for recheck: `stale`
5. robot reaches the saved viewpoint but cannot see the object: `suspect_missing`
6. a second failed confirmation after a local yaw scan marks the object: `missing`
7. missing memory returns the manager to exploration

Phase 1A should require two failed checks before marking memory `missing`:

1. first failure at the saved verification viewpoint marks `suspect_missing`
2. second failure after an in-place yaw scan, for example expected yaw +/- 25 degrees, marks `missing`

Later versions can add alternate nearby viewpoints. The first offline version should use yaw scan because it is deterministic and matches a fixed front-facing camera.

Phase 1A should include four deterministic runs:

| Run | Name | Purpose |
|---|---|---|
| A | `discover_and_verify` | Empty memory. Explore, detect the water dispenser, verify it, and save reusable memory. |
| B | `reuse_same_start` | Same start as Run A. Query memory and navigate directly to the saved verification viewpoint. |
| C | `reuse_different_start` | Different start in the same corridor. Reuse the same object memory to prove this is target memory, not route replay. |
| D | `missing_and_relocation` | First hide the original object to exercise `suspect_missing -> missing`; then move the object to another corridor location and record relocation evidence. |

For relocation in Phase 1A, use conservative instance behavior:

- old object becomes `missing`
- new object becomes `verified`
- add an edge such as `possible_relocation_of(new_object_id, old_object_id)`
- do not merge the objects until later visual appearance, size, or local-place descriptors make identity matching safer

### Phase 1B: Outdoor-compatible interfaces

Before outdoor implementation, the Phase 1A schema and APIs must already be compatible with `outdoor_enu` anchors. Code may still run indoor-only, but object observations and memory records must not assume that every pose belongs to a LiDAR map frame.

Required interface constraints:

- every object observation carries `anchor_id`, `anchor_type`, and `frame_id`
- every stored object keeps pose covariance and source metadata
- `MemoryStore` queries include anchor filters and spatial bounds
- `GoalSelector` receives anchor uncertainty as an explicit score term, even if Phase 1A sets it to a stable indoor value

### Phase 2: Outdoor-only ObjectNav

Run the same ObjectNav and memory interfaces with a single `outdoor_enu` anchor. This phase validates RTK / ENU memory and revisit behavior without indoor-outdoor transition logic.

Expected work:

- outdoor map or route fixtures
- RTK / ENU pose provider
- outdoor object source
- outdoor replay or live trials
- covariance-aware memory reuse

### Phase 3: Dual-anchor transition zone

Only after indoor-only and outdoor-only runs work should the system handle building entrances or semi-outdoor transition zones.

Transition-zone work includes:

- anchor health state for indoor map and outdoor ENU anchors
- versioned `map <-> ENU` transform estimates
- transform covariance and quality thresholds
- hysteresis so the system does not rapidly switch anchors near a doorway
- multi-anchor object evidence for objects observed near the boundary

Objects in a transition zone should not be force-converted from one frame into the other. The system should keep native observations and promote them to reusable memory only when anchor health and repeated evidence are strong enough.

### Phase 4: Baselines and replay experiments

Add repeatable baselines:

- B1: nearest frontier
- B2: information gain frontier
- B3: semantic frontier
- B4: semantic frontier with memory but no verifier or repair
- Ours: dual-anchor memory-aware ObjectNav with verifier and repair

This phase must produce experiment reports before any paper claim.

### Phase 5: Perception without real-robot dependency

Use recorded images, video, or bags to test detection and projection:

- closed-set detector for early target classes
- optional open-vocabulary detector for later expansion
- object projection into map-frame pose
- arrival verifier with replayed near-goal images

### Phase 6: Robot integration

Connect the stable core to the real stack through ROS 2 adapters:

- Nav2 `NavigateToPose`
- `/global_costmap/costmap`
- TF and localization quality
- image, camera info, depth, point cloud, detector outputs
- RTK / ENU anchor input
- RViz visualization

### Phase 7: Integrated dual-anchor real-world evaluation

After indoor-only, outdoor-only, perception, and robot adapters are stable, run integrated real-world dual-anchor trials:

- indoor corridor water dispenser trials
- outdoor object trials
- transition-zone trials near building entrances
- stale, missing, and relocation repair trials

## Related Work Positioning

Recent ObjectNav and open-vocabulary robot systems are moving away from monolithic deep reinforcement learning and toward modular systems that combine foundation-model semantics, explicit memory, exploration, and classical navigation.

This project is closest to the lifelong semantic-memory line, but it should not claim novelty merely from using memory. Several recent systems already make memory central:

| Work | Relevant idea | Lesson for this project | Differentiation for this project |
|---|---|---|---|
| [OK-Robot](https://arxiv.org/abs/2401.12202) | Systems-first open-knowledge mobile manipulation with semantic memory, navigation primitives, and grasping | Component interfaces and practical heuristics matter as much as the model choice | OK-Robot uses a pre-scanned static home memory for pick-and-drop; this project targets online ObjectNav memory, verifier-driven repair, and dual-anchor navigation |
| [GOAT](https://arxiv.org/abs/2311.06430) | Multimodal, lifelong, platform-agnostic navigation with instance-aware semantic memory | Lifelong ObjectNav improves with repeated experience and must support category, language, and image-like goal forms later | This project focuses first on coordinate-anchor reliability, stale/missing/relocation state transitions, and adapter-level transfer to FAST-LIO2/Nav2/RTK stacks |
| [3D-Mem](https://arxiv.org/abs/2411.17735) | Snapshot-based 3D scene memory with memory snapshots and frontier snapshots | Frontier memory should preserve visual context, not only object labels | Phase 1A intentionally starts with symbolic object memory and deterministic frontier fixtures; snapshot/VLM memory can be added after the core loop is testable |
| [DynaMem](https://arxiv.org/abs/2411.04999) | Online dynamic spatio-semantic memory for moving, appearing, and disappearing objects | Static maps are a weak assumption in real homes and labs | This project narrows to ObjectNav first, then makes dynamic memory auditable through explicit verifier states, trial logs, and anchor-aware storage |
| [OpenIN](https://arxiv.org/abs/2501.04279) | Instance-oriented open-vocabulary navigation in dynamic domestic scenes | Same-class instances and moved objects need relational memory, not only class labels | Phase 1A records conservative `possible_relocation_of` evidence and avoids unsafe instance merges until stronger descriptors exist |
| [SCOPE](https://arxiv.org/abs/2511.08935) | VLM-estimated exploration potential over frontiers | Frontiers are not just geometry; they carry semantic search value | This project keeps semantic frontier scoring as a replaceable low-frequency module, with deterministic frontier baselines first |
| [R2F](https://arxiv.org/abs/2603.08475) | LLM-free frontier scoring with language-aligned sparse frontier features | Real-time deployment is hurt by repeated large-model calls | This project should not put VLM/LLM calls in the high-frequency navigation loop |
| [SysNav](https://arxiv.org/abs/2603.06914) | Real-world, cross-embodiment ObjectNav by decoupling semantic reasoning, planning, and motion control | System-level decomposition is now a serious research direction, not just engineering taste | This project adds dual-anchor memory, stale/missing repair, and indoor/outdoor coordinate uncertainty to the system-level story |
| [TrajRAG](https://arxiv.org/abs/2605.01700) | Retrieval over geometric-semantic trajectory experience for zero-shot ObjectNav | Internet-scale commonsense alone is not enough; embodied experience should be accumulated and retrieved | This project accumulates object, viewpoint, frontier, and anchor evidence in a queryable memory store rather than discarding episode observations |
| [NavFoM](https://arxiv.org/abs/2509.12129) | Cross-embodiment navigation foundation model | Foundation navigation models may become useful policy or prior modules | This project should integrate such models as optional adapters or baselines after core interfaces and replay evaluation exist |

## Research Pain Points Addressed

The strongest paper angle is not "we use a VLM for ObjectNav." The stronger angle is that real long-running ObjectNav needs trustworthy memory under localization, environment, and embodiment changes.

This architecture targets six current pain points:

1. **Static semantic memory breaks in lived-in environments.** Objects appear, disappear, or move. The system therefore needs `stale`, `suspect_missing`, `missing`, and relocation evidence instead of a one-shot object database.
2. **ObjectNav systems often confuse perception failure with world change.** A failed observation near a target may mean bad viewpoint, poor localization, occlusion, costmap inflation, or true object removal. The two-check missing policy and verifier state machine make this ambiguity explicit.
3. **Foundation models are expensive and spatially brittle inside real-time navigation loops.** The core should support VLM/VLA/LLM adapters, but high-frequency replanning should use cached candidates, bounded queries, and classical navigation constraints.
4. **Navigation targets are not object centroids.** Real robots need reachable verification viewpoints that respect FOV, obstacle inflation, robot footprint, and sensor geometry.
5. **Most memory systems assume one stable coordinate world.** Indoor SLAM maps, outdoor RTK/ENU frames, and doorway transition zones can disagree. Dual-anchor memory lets observations remain in their native anchor until transform quality is good enough.
6. **Published ObjectNav gains are hard to reproduce without structured logs.** Trial events, candidate scores, memory transitions, and failure labels are first-class outputs so future paper claims can be audited.

This means the central research question should be:

> How can a robot reuse semantic ObjectNav memory across sessions while remaining robust to stale objects, missing targets, coordinate-anchor uncertainty, and later real-robot integration?

## Model Integration Timing

The model integration should be staged. The project should earn the right to add models by first proving the system contract with deterministic evidence.

| Stage | Model policy | Why |
|---|---|---|
| Phase 1A | No learned detector in the main loop; use fake observations from hidden scene truth | This isolates frontier logic, memory state transitions, verification viewpoints, SQLite behavior, and metrics |
| Phase 1B / Phase 2 | Still keep the default deterministic path; optionally add recorded-image closed-set perception as a side experiment | This tests anchor and projection interfaces without letting perception noise hide core bugs |
| Phase 4 | Add model-free and model-light baselines before open-vocabulary models | The paper needs to show what memory and verifier add beyond nearest frontier or information-gain exploration |
| Phase 5 | First serious model integration, offline/replay only | Detector, segmenter, embedding, and verifier adapters can be evaluated against saved images, bags, and manually checked object poses |
| Phase 6 | Real robot perception adapter, throttled and asynchronous | Model outputs should become timestamped evidence records, not direct Nav2 commands |
| Phase 7+ | Optional VLM/LLM/VLA reasoning at low frequency | Use large models for semantic frontier scoring, query disambiguation, scene summaries, or candidate explanation, not for 10 Hz local replanning |

Minimum gates before adding an open-vocabulary or VLM component to the main method:

- Phase 1A deterministic runs pass and produce stable metrics.
- The `ObjectObservationSource` and `ArrivalVerifier` interfaces are already covered by tests.
- Replay data exists for at least one target class with manually checked target locations or verification labels.
- Model outputs include confidence, source metadata, timestamp, anchor id, and failure reason.
- The system can run the same trial with the model disabled, fake detector enabled, and baseline policies enabled.
- Large-model calls are event-driven or low-frequency, never required for local collision avoidance or high-frequency control.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Core code starts depending on vehicle-specific paths or launch files | Review imports, configs, and tests for hardware assumptions | Move details into adapters and configs |
| Offline success does not transfer to real robot | Replay metrics pass but robot trials fail | Add recorded bags and adapter-level tests before live tests |
| Frontier selector loops between poor candidates | Repeated frontier ids, low progress, high revisit ratio | Add revisit penalty, blacklist failed frontiers, and log selection reasons |
| Stale memory sends robot to missing objects | Arrival verifier returns `not_found` | Mark memory `missing`, lower score, and return to exploration |
| A remembered object is not visible from the saved pose | Fixed front-facing camera cannot see the object, or object is outside FOV | Navigate to a verification viewpoint rather than the object center; allow viewpoint retreat or local rescan |
| A missing object is actually a viewpoint or localization failure | Failed verification with poor localization, unreachable viewpoint, or weak line of sight | Use `suspect_missing` before `missing`; require repeated checks and acceptable localization quality |
| A moved object is incorrectly merged with a missing object | New detection near an old missing object is assumed to be the same physical instance | Record `possible_relocation_of` relation first; merge only after stronger descriptors exist |
| Detector false positives corrupt memory | Low repeat observation count or failed verification | Require verification or multiple observations before `verified` |
| Anchor transform uncertainty makes memory unreliable | High covariance or localization quality warnings | Penalize anchor uncertainty and prefer exploration |
| Metrics are not comparable across baselines | Missing session config or inconsistent seeds/maps | Require session config and trial logs for every run |
| Documentation drifts from implementation | Modules or interfaces appear without design/devlog updates | Update design docs and devlog before claiming completion |

## Verification Plan

### Documentation verification for this task

- Confirm the design doc follows `docs/templates/design_doc.md`.
- Confirm the Chinese HTML reading version exists and links only to local content or intentional external references.
- Confirm the monthly devlog records the new design artifact.

### Phase 1A verification

- Unit-test frontier extraction on deterministic grid fixtures.
- Unit-test memory state transitions.
- Run `discover_and_verify` and assert the water dispenser becomes `reusable`.
- Run `reuse_same_start` and assert memory reuse reduces exploration.
- Run `reuse_different_start` and assert the saved target memory is still usable.
- Run `missing_and_relocation` and assert the old object becomes `missing`, the new object becomes `verified`, and a `possible_relocation_of` edge is recorded.

### Phase 1B verification

- Run the same memory schema and query API with an `outdoor_enu` anchor fixture.
- Confirm object observations and memory records do not assume `indoor_map`.

### Phase 2 verification

- Run the same ObjectNav flow with a single `outdoor_enu` anchor.
- Confirm outdoor memory reuse works without indoor map assumptions.
- Record RTK / ENU covariance in trial logs.

### Phase 3 verification

- Simulate anchor health changes and transition-zone object observations.
- Verify the system does not force-promote uncertain transition-zone observations into reusable memory.

### Phase 4 verification

- Run each baseline on the same maps, targets, and seeds.
- Save `trial_events` and `trial_metrics`.
- Create experiment reports for any result used in writing.

### Phase 5 verification

- Evaluate detector precision/recall on the first target classes.
- Evaluate 3D projection error against manually checked points.
- Evaluate arrival verification accuracy on near-goal image sequences.

### Phase 6 verification

- Run the same memory query interface with indoor map anchors and outdoor RTK/ENU anchors.
- Record covariance and transform quality in trial logs.

### Phase 7 verification

- Build the ROS 2 package.
- Source the workspace after build.
- Replay recorded bags before live robot tests.
- Run live robot trials only after adapter-level replay passes.
- Test stale, missing, relocation, and transition-zone repair in integrated trials.

## Research Relevance

This architecture supports the paper story in four ways:

1. It makes the contribution more general than one vehicle-specific integration.
2. It creates clean baseline and ablation boundaries.
3. It supports reproducible offline, replay, and real-robot evaluation.
4. It frames dual-anchor lifelong memory as a system contribution rather than a model demo.

The intended paper claim should be about a hardware-independent Dual-Anchor Lifelong Semantic ObjectNav system that transfers to a real ROS 2 autonomous vehicle through stable adapters.

## Open Questions

- Should the first core implementation be a pure Python package, an `ament_python` ROS 2 package with ROS-free inner modules, or both?
- Should Phase 1 use SQLite immediately, or start with JSON and migrate before experiments?
- What exact deterministic grid geometry should represent `straight_corridor_one_water_dispenser`?
- What recorded data is already available for replay, if any?
- What minimum real-robot trial count is realistic before the first workshop or conference deadline?
