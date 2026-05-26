# Design Doc: Usability-Centered Lifelong Object Memory

Date: 2026-05-26  
Owner: Codex  
Status: Draft

## Goal

Define a new algorithmic direction for lifelong ObjectNav: maintain object memories according to whether they are useful and safe for navigation, not according to whether the system can perfectly prove object existence.

The design replaces the earlier "dual-anchor as main contribution" story with a narrower method contribution:

> A robot should delay committing noisy detections into long-term memory, retire memories that are no longer useful for navigation, and choose between trusting, verifying, searching, or retiring a memory under a finite task budget.

This direction is intended to support an algorithm-method paper while still fitting the existing hardware-independent ObjectNav core, ROS replay, and TurtleBot3/Nav2 simulation infrastructure.

## Non-Goals

- Do not claim to solve open-world ObjectNav end to end.
- Do not claim that the robot can reliably prove that an object no longer exists.
- Do not depend on RTK as the main novelty. Dual-anchor alignment remains useful infrastructure, not the paper's core method.
- Do not require a global high-resolution OctoMap or TSDF for the first method version.
- Do not solve full POMDP planning or global multi-hypothesis data association.
- Do not hand-author category-specific half-life tables for hundreds of object classes.
- Do not put large VLM/LLM calls in the high-frequency control loop.

## Background

The earlier dual-anchor design was valuable as a system architecture, but it was too optimistic as a paper contribution. Indoor RTK can fail, SLAM covariance may be poorly calibrated, RGB-D object localization is brittle, and combining Kabsch alignment, covariance propagation, and log-odds memory updates is likely to read as engineering integration rather than algorithmic novelty.

Recent discussion identified a more defensible problem:

> In lifelong ObjectNav, a memory can be physically true but useless for navigation, or physically uncertain but still worth using. The system needs to reason about usability, not only existence.

This matters because real low-cost RGB-D robots often cannot produce clean negative evidence. A RealSense depth frame may have holes, flying pixels, edge bleeding, reflective failures, and pose projection errors. A conservative FREE-space certificate will often be unavailable. If the algorithm only updates memory on perfect FREE evidence, ghost memories will persist forever. If it deletes on detector misses, it will erase real objects under occlusion or perception failure.

The resulting method centers on `P_usable`: whether a memory should participate in ObjectNav decisions.

## System Boundary

This design belongs in the ROS-free ObjectNav core and should be testable through deterministic simulation and trace-driven replay before live robot closure.

Two repositories have separate responsibilities:

- `/Users/badger/Desktop/dual-anchor-lifelong-objectnav`: algorithm core, deterministic simulation, trace replay, metrics, reports, and paper experiments.
- `/Users/badger/Desktop/XJTLU-autonomous-vehicle`: real-vehicle ROS 2 runtime, RTK, RGB-D camera integration, rosbag collection, Nav2 execution, FAST-LIO2/PGO localization, and final small live-robot closure.

The algorithm repository should not directly depend on XJTLU ROS packages. The XJTLU repository should export data through rosbag or a trace conversion layer, then the algorithm repository should consume a stable intermediate trace/evidence format.

The core owns:

- object-memory lifecycle states
- short-lived detection tracklets and candidate memory birth
- evidence classification and usability updates
- finite-budget trust / verify / search / retire decisions
- metrics for false writes, false deletion, repeated wasted navigation, and retired ghost memories

The core depends on adapters for:

- object detections or detector replay records
- RGB-D depth frames and camera intrinsics, when available
- robot pose and localization health
- local/global costmap snapshots
- Nav2 or A* path-cost queries for a small set of finalist actions

ROS-specific topic conversion, Nav2 action execution, TF lookup, and RViz visualization remain in `objectnav_ros`.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Object observation | `ObjectObservation` plus optional bbox, depth ROI, detector score, timestamp | Single observations are not durable memory writes. |
| Input | Depth evidence | RGB-D depth frame, camera info, pose at capture time | Used for local visibility classification when available. |
| Input | Pose / anchor health | Pose estimate, residual health, anchor transform health | Used to gate promotion and association, not blindly trusted as calibrated covariance. |
| Input | Costmap / reachability | Occupancy grid, local costmap, planner result, path-cost cache | Used by finite-budget decision and cache invalidation. |
| Input | Current ObjectNav query | target class / instance / description | Limits decisions to query-relevant memories. |
| Output | Memory update | object state, evidence log, usability belief | Stored in SQLite and exported to reports. |
| Output | Action decision | `trust_memory`, `verify_memory`, `search`, `retire`, or `defer` | Passed to planner/navigation layer. |
| Output | Metrics | false write, false deletion, wasted navigation, retire count, verification cost | Used for paper experiments. |

## Interfaces

Initial core interfaces should be ROS-free:

- `EvidenceBuffer.add_observation(obs, context) -> TrackletUpdate`
- `MemoryLifecycle.update_from_tracklets(tracklets) -> list[MemoryUpdate]`
- `VisibilityClassifier.classify(memory, depth_context) -> EvidenceType`
- `UsabilityUpdater.apply(memory, evidence) -> MemoryObject`
- `DecisionPolicy.choose(query, memories, budget, path_cost_provider) -> ObjectNavDecision`

Future persistence additions:

- `memory_objects`: add `p_existence`, `p_location_valid`, `p_usable`, `retired_reason`, `last_confirmed_at`, `last_usable_at`
- `memory_evidence`: evidence type, source, pose, depth status, path status, update magnitude
- `memory_tracklets`: short-lived tracklet records for debugging false-positive suppression
- `path_cost_cache`: candidate id, cost, costmap revision, validity region, invalidation reason

### XJTLU Real-Vehicle Interfaces

The real-vehicle experiments will run in `/Users/badger/Desktop/XJTLU-autonomous-vehicle`. That repository should be treated as the source of real robot traces, not as the place where the algorithm core is developed.

Current relevant launch modes:

| Mode | Command | Use for this research |
|---|---|---|
| Indoor Nav | `make launch-indoor-nav` | Indoor FAST-LIO2/PGO/Nav2 click-to-go trace collection without GNSS. |
| Explore | `make launch-explore` | Local navigation and costmap evidence collection. |
| Explore GPS | `make launch-explore-gps` | FAST-LIO2/PGO with GNSS factor and RTK health evidence once UM982 is validated. |
| Corridor | `make launch-corridor` | Outdoor RTK/GNSS route and path-cost evidence after fresh RTK route collection. |

Existing XJTLU bag interfaces already include:

| Evidence group | Topics |
|---|---|
| Localization | `/tf`, `/tf_static`, `/fastlio2/lio_odom`, `/pgo/optimized_odom` |
| RTK / GNSS | `/fix`, `/heading` when UM982 THS/HPR is available, raw NMEA logs under `runtime-data/logs/latest/data/` |
| Navigation action context | `/cmd_vel`, `/plan`, `/gps_corridor/status`, `/gps_corridor/alignment_status`, `/gps_corridor/goal_map`, `/gps_corridor/path_map` |
| Costmaps | `/local_costmap/costmap`, `/global_costmap/costmap`, and preferably costmap update topics when enabled |
| System health | `runtime-data/logs/latest/system/tegrastats.log`, `session_info.yaml`, Nav2 console logs |

Interfaces still needed after hardware installation:

| Evidence group | Expected topics / artifacts | Purpose |
|---|---|---|
| RGB-D | `/camera/color/image_raw`, `/camera/depth/image_rect_raw`, `/camera/color/camera_info`, camera TF | Estimate POSITIVE / NON_CONFIRMATION / OCCLUDED / UNKNOWN / FREE evidence. |
| Detector output | JSON topic, custom message, or bag sidecar with bbox/class/score/timestamp | Feed short-lived tracklets and delayed birth. |
| Camera calibration | `camera_link -> base_link` TF and depth/color alignment record | Keep projection errors auditable. |
| Manual labels | JSONL/CSV labels for object present/moved/occluded/removed/unreachable | Evaluate false deletion, ghost retirement, and replay correctness. |

The first XJTLU-side addition should be a research trace recorder, not the ObjectNav algorithm itself. A future command can be:

```bash
make launch-objectnav-trace
```

or, initially, an expanded bag script that records the topics above. The algorithm repository should then convert each bag into an intermediate trace:

```text
TraceEvent =
  timestamp
  robot_pose
  localization_health
  rtk_quality
  costmap_state_or_delta
  nav_status
  object_observation?
  depth_evidence_summary?
  manual_label?
```

## Data Flow

```text
Detector / replay observation
        |
        v
Short-lived evidence buffer
        |
        |  sequential evidence check
        v
Candidate memory birth / discard / ambiguous cluster
        |
        |  verification or repeated support
        v
Confirmed / reusable memory
        |
        |  query arrives
        v
Finite-budget decision: trust / verify / search / retire
        |
        +--> trust: navigate to stored verification viewpoint
        +--> verify: collect local evidence, then update usability
        +--> search: use default frontier/search policy
        +--> retire: archive from default navigation decisions
```

The key safety principle is that evidence can be logged without immediately changing durable memory. Promotion and retirement require accumulated evidence.

## Memory Representation

A durable memory should separate three beliefs:

```text
P_existence        object may still exist somewhere
P_location_valid   remembered location is still plausible
P_usable           memory should be used by ObjectNav decisions
```

`P_usable` is the primary decision variable. A memory can have moderate `P_existence` but low `P_usable` if its location is stale, path is blocked, it is persistently occluded, or it repeatedly fails to confirm.

Recommended states:

```text
tracklet
candidate
confirmed
reusable
stale
location_conflict
occluded
unverifiable
retired
missing
```

`missing` should be rare and should mean there is enough evidence to exclude the memory from normal operation. Most uncertain objects should become `retired` or `unverifiable`, not hard-deleted.

## Algorithm Step 1: Delayed Birth

### What It Does

Suppress isolated detector false positives before they enter long-term memory.

### How It Works

Each raw detection enters a short-lived tracklet buffer. The buffer only promotes a tracklet into a memory candidate when observations provide more evidence for a stable object than for clutter.

Instead of fixed thresholds like "3 consecutive frames" or "IoU > 0.5", use a bounded sequential likelihood ratio:

```text
L_h(t) = L_h(t-1) + log p(z_t | H_object, h) - log p(z_t | H_clutter)
```

where:

- `z_t` is the observation at time `t`
- `h` is a local object hypothesis
- `H_object` means the observation was generated by the object hypothesis
- `H_clutter` means the observation was generated by background clutter or a false positive

Decision:

```text
if L_h >= A: promote to candidate
if L_h <= B: discard tracklet
otherwise: keep short-lived
```

`A` and `B` should be risk boundaries, not scene geometry thresholds. For example, choose boundaries from acceptable false promotion and false rejection risk, then validate with replay.

### Avoiding Association Collapse

Do not force nearest-neighbor assignment when two same-class objects are close or detections jitter heavily. If local association entropy is high:

- keep observations in an ambiguous cluster
- do not update durable memories
- do not increase memory usability
- expire weak ambiguous evidence by TTL

The first implementation should use bounded MHT-lite:

- keep top-K local hypotheses per class and region
- use spatial indexing to compare only nearby hypotheses
- merge or retire weak hypotheses when memory pressure is high

## Algorithm Step 2: Delayed Promotion

### What It Does

Prevent a plausible candidate from becoming reusable memory until it has task-relevant support.

### How It Works

A candidate becomes `confirmed` or `reusable` only after enough evidence accumulates:

- repeated support from different frames or viewpoints
- localization health is acceptable
- a verification viewpoint is reachable or cached
- the object is confirmed from a diagnostic viewpoint when feasible

If pose or anchor health is poor, the system may store weak evidence but should not promote, merge, or overwrite durable memories.

This step is intentionally conservative. It is better to miss a few weak memories than to poison the long-term store with false positives.

## Algorithm Step 3: Evidence Classification

### What It Does

Classify negative or non-positive observations without pretending that detector miss means object disappearance.

### Evidence Types

```text
POSITIVE           target reobserved or strongly supported
FREE              remembered support region is conservatively empty
NON_CONFIRMATION  reasonable attempt, no confirmation, but not enough for FREE
OCCLUDED          expected region blocked by foreground geometry
UNKNOWN           depth invalid, pose uncertain, edge/flying-pixel risk, too few rays
ACCESS_BLOCKED    navigation cannot reach a useful verification pose
SCENE_CHANGED     local environment changed near memory or path
```

### How It Works

When RGB-D is available, project the memory support region into the current depth image. Use only a conservative eroded core, exclude high depth-gradient pixels, and account for pose uncertainty.

Classification should prefer `UNKNOWN` over false FREE:

```text
if depth health bad:
    UNKNOWN
elif projection confidence low:
    UNKNOWN
elif stable rays show foreground before support region:
    OCCLUDED
elif enough stable rays pass through the eroded support region:
    FREE
else:
    NON_CONFIRMATION or UNKNOWN
```

FREE is useful but expected to be rare. The algorithm must still progress under repeated NON_CONFIRMATION, OCCLUDED, UNKNOWN, and ACCESS_BLOCKED evidence by reducing `P_usable`.

## Algorithm Step 4: Usability Update

### What It Does

Update the memory's navigation usefulness without overclaiming physical disappearance.

### How It Works

Represent memory belief as:

```text
b_m = (p_e, p_l, p_u)
```

where:

- `p_e = P_existence`
- `p_l = P_location_valid`
- `p_u = P_usable`

Recommended qualitative updates:

| Evidence | `P_existence` | `P_location_valid` | `P_usable` |
|---|---:|---:|---:|
| POSITIVE | increase | increase | increase |
| FREE | slight decrease or unchanged | strong decrease | decrease |
| NON_CONFIRMATION | unchanged | slight decrease | decrease |
| OCCLUDED | unchanged | unchanged/slight decrease | decrease with persistence |
| UNKNOWN | unchanged | unchanged | slight decrease only if repeated and query-relevant |
| ACCESS_BLOCKED | unchanged | unchanged/slight decrease | decrease |
| SCENE_CHANGED | unchanged/slight decrease | decrease | decrease |

This is not a category half-life table. Decay is driven by observed events. Category priors should be coarse only:

```text
structural / furniture / movable / unknown
```

The event-driven hazard can be written as:

```text
lambda_u(m, t) =
  lambda_base
  + lambda_conflict(m, t)
  + lambda_access(m, t)
  + lambda_scene_change(m, t)
  + lambda_non_confirmation(m, t)
```

and:

```text
p_u(t + dt) = p_u(t) * exp(-lambda_u(m, t) * dt)
```

The same structure can be used for `p_e` and `p_l`, but the strongest event effects should apply to `p_u` and `p_l` first. `p_e` should decay slowly unless there is repeated strong evidence or long-term task failure.

## Algorithm Step 5: Finite-Budget Decision

### What It Does

Choose whether to trust, verify, search, or retire a memory under the current episode budget.

### How It Works

For a query-relevant memory `m`, define:

```text
P_v(m) = P(memory is valid for this query)
       ~= p_e * p_l * p_u
```

Then compare expected costs in meters or seconds:

```text
E[C_trust] =
  P_v * D_nav
  + (1 - P_v) * (D_nav + C_fail + E[C_search | failed])
```

```text
E[C_verify] =
  D_verify
  + sum_o P(o | verify, m) * E[C_after(o)]
```

```text
E[C_search] =
  cost(default_search_policy)
```

```text
E[C_retire] =
  E[C_search] + retire_penalty_if_user_requested_specific_instance
```

Choose:

```text
argmin { E[C_trust], E[C_verify], E[C_search], E[C_retire] }
```

`B_remain` is treated as a feasibility constraint and diagnostic, not as a hard cap inside expected cost. Clipping each branch with `min(B_remain, ...)` can make a likely failure look artificially cheap: when budget is low, the robot may prefer to trust a nearly invalid memory because the bad outcome has been truncated. Search cost must therefore be finite by construction, for example from a bounded default search policy over top-K rooms or a fixed episode horizon, rather than hidden by per-branch clipping.

### Retire Rule

Retire a memory from default decisions when:

```text
p_u < tau_retire
and not currently required as a user-specified instance
and either search is cheaper than verification or verification repeatedly failed
```

Retirement is reversible. A retired memory can be revived by future positive evidence.

## Algorithm Step 6: Path-Cost Management

### What It Does

Avoid high-frequency global planning for every memory while preventing stale path-cost caches from causing bad decisions.

### How It Works

Use two layers:

```text
D_coarse: cached topological or distance-field estimate
D_local: refreshed planner or A* cost for finalists
```

Decision process:

1. Filter query-relevant memories.
2. Rank by coarse cost and `P_usable`.
3. Select top-K finalists.
4. Refresh local path cost for finalists if the cache is stale or the path tube is affected.

Cache invalidation must account for inflated costmap effects:

```text
inflated_changed_region =
  dilation(changed_occupied_or_unknown_cells,
           robot_radius + safety_margin + costmap_inflation_radius)

path_tube =
  dilation(planned_path_polyline,
           robot_radius + tracking_error_margin)
```

Invalidate if:

```text
inflated_changed_region intersects path_tube
or path_tube_cost_delta > threshold
or planner reports blocked / large cost increase
or navigation recovery was triggered
or OCCLUDED / location_conflict evidence lies near the candidate path tube
```

Only finalists should trigger expensive planner calls. This keeps decision-making low-frequency and bounded.

## Algorithm Step 7: Opportunistic Verification

### What It Does

Use ongoing navigation to maintain nearby memories at low marginal cost.

### How It Works

When navigating to target `A`, check whether a memory `B` near the route can be verified with a small marginal cost:

```text
extra_cost(B along route) < opportunistic_budget
and memory B is query-relevant soon or high value
and verification does not endanger current task
```

If true, add a head turn, side-view check, or short local detour. This prevents memory maintenance from becoming only a separate expensive task.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| FREE evidence almost never appears | Replay reports high UNKNOWN/NON_CONFIRMATION ratio | Let usability decay through repeated non-confirmation, access failure, and scene change; do not depend on FREE as the only negative evidence. |
| False FREE from RGB-D edge artifacts | Depth gradient high, ray count low, pose uncertainty high, inconsistent frames | Return UNKNOWN; require repeated evidence before location conflict; never hard-delete on one frame. |
| Same-class objects cause wrong association | Local association entropy high, top hypotheses close in likelihood | Keep ambiguous cluster; do not update durable memory; bounded MHT-lite top-K. |
| SLAM covariance is overconfident | Innovation/residual statistics inconsistent with reported covariance | Apply covariance floors, health gates, or residual-quantile prediction sets; forbid promotion under poor localization health. |
| Ghost memories accumulate | Many memories have low `P_usable` but high `P_existence` | Retire/archive low-usability memories from default decisions; keep evidence logs for revival. |
| Long-term occlusion deadlock | Repeated OCCLUDED/ACCESS_BLOCKED without positive evidence | Lower `P_usable`; mark `unverifiable`; stop using in default ObjectNav until reobserved. |
| Cost cache is stale near changed obstacle | Inflated changed region intersects path tube or planner cost spikes | Refresh local cost for finalists; invalidate affected path cache. |
| OOD sensor failure produces many bad updates | Sudden batch of contradictory FREE/UNKNOWN or depth health collapse | Quarantine evidence batch; freeze negative updates; require sensor recovery before memory degradation. |

## Verification Plan

### Phase A: Deterministic Simulation

Extend the existing Phase 1A runner with:

- `P_existence`, `P_location_valid`, `P_usable`
- `retired` and `unverifiable` states
- non-confirmation and access-blocked evidence
- trust / verify / search / retire decisions

Expected checks:

- no single observation creates reusable memory
- no single miss deletes memory
- repeated non-confirmation lowers `P_usable`
- retired memory is excluded from default query decisions
- retired memory can be revived by positive evidence

### Phase B: RGB-D Trace Collection

Collect real sensor logs without closed-loop ObjectNav:

- RGB
- depth
- camera info
- TF / pose
- detector output
- costmap snapshots
- optional manual labels for object present / moved / occluded / removed

Measure:

- FREE / OCCLUDED / UNKNOWN / NON_CONFIRMATION ratios
- detector false positives and false negatives
- bbox jitter and projected support drift
- depth holes and flying-pixel risk
- how often path caches would be invalidated by inflated changes

### Phase C: Trace-Driven Replay

Run memory updates offline against real logs:

- compare aggressive delete-on-miss
- compare conservative FREE-only retirement
- compare naive confidence threshold memory
- compare usability-centered method

Primary metrics:

- memory reuse success
- false memory write rate
- false deletion rate
- repeated wasted navigation
- retired ghost memory count
- verification cost
- ObjectNav success under perception degradation

### Phase D: Small Live Robot Closure

Only after replay behavior is stable:

- fixed area
- small object class set
- limited query count
- manual ground-truth labels

Goal: demonstrate fewer wasted revisits and fewer false deletions than baselines, not open-world SOTA.

## Research Relevance

This design reframes the paper around a defensible algorithmic contribution:

> Lifelong ObjectNav memory should be optimized for task usability under unreliable perception, not for brittle proof of object existence.

The proposed method is distinct from:

- standard MOT, which tracks identity but does not model long-term navigation usability
- OctoMap-style occupancy updates, which model free/occupied space but not object-memory task value
- dual-anchor covariance propagation, which helps coordinate consistency but does not solve memory pollution or ghost memory

Potential paper contributions:

1. A memory representation that decouples existence, location validity, and navigation usability.
2. An event-driven usability update and retirement mechanism that works even when strong FREE evidence is rare.
3. A bounded expected-cost policy for trust / verify / search / retire decisions with path-cost cache invalidation based on inflated costmap changes.

## Open Questions

- What minimal evidence schema should be added to SQLite first without overfitting future experiments?
- Which object classes should be used for first RGB-D trace collection?
- Should initial `P_usable` updates be hand-specified event tables, learned from replay, or calibrated with simple logistic regression after enough labels exist?
- What is the smallest trace-driven replay format that preserves RGB-D, detector, pose, and costmap evidence?
- How should retired memories be exposed to the user: hidden by default, visible as archived, or revived only by positive evidence?
