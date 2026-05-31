# Design Doc: Official Active-Perception Memory Frontier Policy

Date: 2026-05-30
Owner: Codex
Status: Implemented and smoke-tested; diagnostic negative official success

## Goal

Add an official Habitat query policy that actively seeks detector evidence near
remembered object anchors. The policy should decide which frontier viewpoint is
most likely to reveal the remembered target, instead of only reacting after a
current-view detector match or blindly walking toward the memory belief.

## Non-Goals

- Do not use lifecycle/exported `habitat_world` anchors for official query
  memory. Official query memory remains episode-relative.
- Do not claim benchmark improvement from a small diagnostic smoke.
- Do not hard-code a vehicle, scene, category, or route.
- Do not add language/GPT integration in this slice.
- Do not replace official Habitat success/SPL/SoftSPL metrics.

## Background

The temporal learned-local controller is active online, but the learned-local
branch fires only a few times per four-episode smoke. The limiting problem is
earlier in the query process: the agent often fails to choose viewpoints that
will reacquire detector evidence around the remembered object. A paper-quality
lifelong-memory ObjectNav system needs an active perception layer that reasons
about where evidence can be gathered.

## System Boundary

Modify:

- `objectnav_core.evaluation.habitat_official_objectnav_eval`
- focused official ObjectNav evaluator tests
- official CLI tests if policy registration affects CLI choices
- docs/devlog/handoff and an experiment report after smoke

This slice stays inside the official Habitat evaluator path and uses the
existing occupancy frontier map, detector adapter, and memory-prior interfaces.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Memory anchors | `OfficialMemoryAnchor` | Episode-relative, selected by category/scene/confidence. |
| Input | Occupancy map | `OccupancyFrontierMap` | Built online from depth observations. |
| Input | Observation | Habitat RGB-D/GPS/compass | No prior map. |
| Input | Detector adapter | Optional | If target is visible, detector behavior remains first priority. |
| Output | Action | Habitat action string | Same discrete action set as existing policies. |
| Output | Debug payload | JSON-serializable dict | Candidate scores and selected frontier evidence terms. |

## Data Flow

1. Run the same detector-first behavior as `memory_evidence_frontier`.
2. If target evidence is absent, update the online occupancy frontier map.
3. Select the matching episode-relative memory anchor.
4. Enumerate frontier cells from the online occupancy map.
5. For each frontier, compute:
   - anchor belief likelihood from distance to remembered object;
   - expected view quality from standoff distance between the frontier
     viewpoint and the anchor;
   - information gain as belief times view quality;
   - travel penalty from the current cell to the frontier.
6. Pick the frontier maximizing expected information gain minus travel cost.
7. Turn toward the selected frontier if needed, move forward when aligned and
   the center depth is clear, otherwise fall back to occupancy frontier.

## Scoring

For a frontier position `f` and memory anchor `a`:

```text
belief = anchor.confidence * exp(-||f - a||^2 / (2 * sigma^2))
view_distance_quality = exp(-((||f - a|| - preferred_view_distance)^2) / (2 * view_sigma^2))
view_bearing_quality = 1.0
expected_evidence = belief * view_distance_quality * view_bearing_quality
score = expected_evidence - travel_distance_weight * travel_distance
```

This is still a lightweight model, but it is an explicit active-perception
objective rather than a hand-authored action loop. Later work can replace the
view-quality prior with learned detector recall or value estimates while
preserving the interface.

The `view_bearing_quality` term is intentionally rotation-aware. A frontier is
a candidate viewpoint, not a fixed camera pose: after the agent reaches that
viewpoint it can rotate in place before sensing the remembered anchor. The first
implementation incorrectly multiplied evidence by the cosine between the
approach bearing and the future sensing bearing, which zeroed valid side or
standoff viewpoints and made the selector collapse toward travel cost in a
detector-backed smoke.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| No matching anchor | Debug `fallback_reason=no_matching_memory` | Use occupancy frontier. |
| No frontiers | Selector returns `None` | Use occupancy frontier. |
| Chosen frontier corridor blocked | Center depth blocked | Fall back to occupancy frontier turn burst. |
| Scoring degenerates to nearest frontier | Candidate-score tests | Include view-quality terms and debug candidate scores. |
| Approach-heading term suppresses side views | Regression where side viewpoint keeps positive evidence | Keep prospective viewpoint evidence independent of approach heading. |
| Small smoke remains negative | Official metrics | Record as diagnostic; do not overclaim. |

## Verification Plan

1. RED pure selector test where the nearest frontier is not selected because a
   farther frontier has better expected view quality around the anchor.
2. GREEN selector implementation with JSON-safe debug fields.
3. RED policy registration/action-loop test proving the new policy records
   active-perception debug and uses the selected frontier.
4. GREEN integration into supported policies, manifest policy kind, and CLI
   choices.
5. Local focused official gate, compileall, and `git diff --check`.
6. Sync to Linux and run the same focused gate.
7. Run a small detector-backed official YOLO smoke through the new CLI path and
   document official metrics plus detector/policy traces.

## Implementation Notes

- Added `_select_memory_active_perception_frontier` with belief, view-quality,
  expected-evidence, travel-cost, and top-candidate debug terms.
- Added official policy `memory_active_perception_frontier`.
- Detector-first behavior matches the evidence frontier path; the new active
  perception selector is used when target detector evidence is absent.
- Local verification on 2026-05-30 passed: official evaluator tests
  (`51 passed`), CLI tests (`8 passed`), focused gate (`93 passed`),
  compileall, `git diff --check`, and CLI help confirmed the policy choice.
- After the first detector-backed smoke showed zero expected evidence for top
  real candidates, added a side-view regression and removed the
  approach-heading cosine from view evidence. Local focused gate passed with
  `94 passed`, plus compileall and `git diff --check`.
- Linux rerun on the same four-episode YOLO setup passed the focused gate
  (`94 passed`), compileall, and `git diff --check`. The rotation-aware smoke
  produced official success `0/4`, SPL `0.0`, SoftSPL
  `0.03315001996589104`, selected active-perception expected evidence
  `0.4498654945233323..0.519892411627075`, and no zero-evidence inspected top
  candidates. This remains diagnostic, not a benchmark result.

## Research Relevance

This policy targets the core lifelong-memory claim: a robot without a prior map
should remember where an object was seen and actively choose viewpoints that can
confirm or refute that memory later. It is also a cleaner bridge to real robot
deployment because the boundary depends on memory anchors, online occupancy,
detector evidence, and discrete navigation actions rather than simulator-only
oracle state.
