# Design Doc: 2D Grid Trace Generator

Date: 2026-05-26  
Owner: Codex  
Status: Implemented

## Goal

Add a lightweight Python 2D trace generator that can run the usability-memory algorithm before Habitat, RGB-D logs, RTK, or real-robot integration are ready.

The generator should produce the same kind of intermediate evidence events that future Habitat replay and XJTLU rosbag replay will produce, so the algorithm core can be tested through one stable interface.

## Non-Goals

- Do not render RGB images or depth maps.
- Do not claim RealSense-level sensor fidelity.
- Do not replace Habitat or real rosbag replay.
- Do not tune paper metrics from this synthetic trace alone.
- Do not add ROS 2, Nav2, GroundingDINO, RTK, or vehicle-specific dependencies.

## Background

The usability-memory route now has a pure Python belief update and decision policy. The first stress harness attacks isolated mathematical cases, but it does not yet generate a sequential trace with robot pose, evidence, navigation cost, and association ambiguity.

The next bridge is a small grid world that emits trace events using statistical scene outcomes. Habitat will later test depth-noise evidence extraction with a stronger physical simulator, and XJTLU bags will test real sensor/runtime behavior.

## System Boundary

The 2D trace generator owns:

- seeded synthetic scenario generation
- per-step `TraceEvent` records
- replay of events through `UsabilityUpdater`
- decision logging through `UsabilityDecisionPolicy`
- summary, CSV, and HTML report artifacts

It depends on:

- `objectnav_core.memory.usability`
- standard-library JSON/CSV/path utilities

It does not depend on ROS, Habitat, detector models, numpy, or real robot logs.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Seed | integer | Makes the trace deterministic. |
| Input | Episodes | integer | Number of generated mini-scenarios. |
| Input | Steps per episode | integer | Number of trace events per episode. |
| Input | Scenario parameters | Python defaults | Encodes obstacle, occlusion, false-negative, and association ambiguity rates. |
| Output | `events.csv` | CSV | Flat trace with evidence, belief, decision, and cost columns. |
| Output | `summary.json` | JSON | Aggregate evidence counts, decision counts, and scenario outcomes. |
| Output | `trace_report.html` | HTML | Human-readable fixed-seed run report. |

## Interfaces

CLI:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_grid_trace_experiment \
  --output runs/grid_trace/latest \
  --seed 17 \
  --episodes 100000 \
  --steps-per-episode 8
```

Python API:

```python
from objectnav_core.evaluation.grid_trace_experiment import run_grid_trace_experiment

summary = run_grid_trace_experiment("runs/grid_trace/latest", seed=17)
```

Trace row fields include:

- `episode_id`
- `scenario`
- `step_index`
- `robot_x`, `robot_y`, `robot_yaw`
- `target_x`, `target_y`
- `evidence_type`
- `evidence_strength`
- `path_blocked`
- `association_candidates`
- `true_memory_id`, `nearest_memory_id`, `jpda_memory_id`
- `association_margin`, `association_entropy`, `false_positive`
- `d_nav`, `d_verify`, `c_search`, `b_remaining`
- `obstacle_intersects_path`, `inflation_intersects_path`
- `stale_cost`, `cached_d_nav`, `cached_d_verify`, `fresh_d_nav`, `fresh_d_verify`
- `decision_stale`, `decision_refreshed`, `decision_flipped_after_refresh`
- `nearest_wrong_association`, `jpda_rejected_ambiguous`, `ghost_positive_write_prevented`
- `p_existence`, `p_location_valid`, `p_usable`, `p_valid`
- `decision`
- `cost_trust`, `cost_verify`, `cost_search`, `cost_retire`

## Data Flow

1. The generator cycles through predefined scenario families: stable visible object, removed or moved object, occluded then revealed object, blocked access, OOD depth failure, nearby same-class ambiguity, inflated corridor blockage, stale path-cost cache, and multi-object association ambiguity.
2. Each step samples a statistical outcome with a seeded RNG.
3. The outcome becomes an `EvidenceEvent`.
4. The current belief is updated by `UsabilityUpdater`.
5. A bounded decision context is produced from grid-style distances and scenario costs.
6. `UsabilityDecisionPolicy` chooses trust, verify, search, or retire.
7. The event, belief, decision, and costs are written to artifacts.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Synthetic trace mistaken for physical sensor validation | Experiment report labels it as 2D statistical trace | Use Habitat and real bag replay before paper claims. |
| Scenario probabilities become hidden tuning knobs | Parameters stay centralized and fixed-seed reports record them | Treat this as regression/adversarial testing, not final benchmark. |
| Trace schema diverges from Habitat or rosbag replay | Tests assert required event fields | Keep Habitat/rosbag converters targeting the same fields. |
| Generator hides association failures | Summary reports nearest-neighbor wrong association, JPDA-lite rejection, and prevented ghost writes | Keep true/nearest/JPDA assignment fields in every event row. |
| Verify remains artificially cheap | Decision-rate summary stays verify-heavy | Add inflation and stale-cache scenarios that force path-cost jumps. |

## Verification Plan

- Unit test deterministic trace generation for a fixed seed.
- Unit test artifact writing and required columns.
- Unit test evidence and decision count summaries.
- Run the CLI once with a fixed seed and 100000 episodes, then record the result in an experiment report.
- Run the full core test suite and Python compile check.

## Research Relevance

This supports the paper route by separating three experiment layers:

1. 2D grid trace: fast adversarial logic testing.
2. Habitat noisy depth: physically richer evidence extraction.
3. XJTLU bag replay and live robot: real system validation.

The 2D trace generator should expose state-machine failures early, especially false trust, ghost memory accumulation, over-retirement, association ambiguity, stale path-cost decisions, inflation-layer blockage, and low-cost verification edge cases.

## Open Questions

- Should opportunistic verification receive an explicit memory-maintenance value before search?
- Which scenario parameters should be replaced first by Habitat or real bag statistics?
- Should the JPDA-lite gate become a full multi-hypothesis tracker before Habitat integration?
