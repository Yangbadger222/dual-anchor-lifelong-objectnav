# Design Doc: Official Memory-Prior ObjectNav Policy

Date: 2026-05-30
Owner: Codex
Status: Implemented first slice

## Goal

Add the first official Habitat-Lab action-loop policy that can use remembered
object anchors. The policy should let a prior memory source bias navigation and
stopping while Habitat-Lab still computes `success`, `spl`, `soft_spl`, and
`distance_to_goal` through `habitat.Env.get_metrics()`.

## Non-Goals

- Do not claim benchmark performance from hand-authored or oracle memory files.
- Do not use Habitat pathfinder, GreedyGeodesicFollower, target object pose,
  semantic oracle masks, or teleports inside the official action policy.
- Do not solve language grounding in this slice.
- Do not replace the lifecycle memory system; this slice only creates the
  official-loop input boundary it can later feed.

## Background

The project now has an official Habitat ObjectNav adapter with `noop`,
`random`, `frontier_only`, and `occupancy_frontier`. These policies prove that
official metrics are plumbed correctly, but none can use lifelong memory yet.
The older lifecycle runner records useful memory anchors, stale repair, and
detector evidence, but it relies on route/proxy accounting and is not official
ObjectNav SPL.

The next publishable direction needs both pieces: official action stepping and
a memory interface that can be populated by prior exploration, detector logs,
or later real-robot sessions.

## System Boundary

This slice extends the official adapter with a memory-prior policy:

- owns parsing a small JSON memory prior artifact;
- selects episode-start-relative anchors by current episode scene/category when
  possible;
- converts remembered `x,z` positions into relative bearing/range from official
  `gps` and `compass` observations;
- emits only official discrete actions: `move_forward`, `turn_left`,
  `turn_right`, and `stop`;
- falls back to `occupancy_frontier` behavior when no usable anchor exists.

It depends on official Habitat observations and external memory artifacts. It
does not own detector inference, memory discovery, language parsing, or learned
validity calibration. It also does not act on lifecycle DB `habitat_world`
anchors directly, because official `gps` is episode-start-relative.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Memory prior | JSON file | List of anchors with category, optional scene id, `x_m`, `z_m`, confidence, source, and optional `coordinate_frame`. |
| Input | Observation | Habitat observation dict | Uses `depth`, `gps`, and `compass`; target category comes from the episode metadata/object goal. |
| Input | Policy config | CLI flags | Memory stop radius, bearing tolerance, confidence threshold. |
| Output | Actions | Habitat discrete action strings | No route follower or oracle action source. |
| Output | Debug telemetry | `policy_debug.memory_prior` | Anchor selected, range, bearing error, confidence, source, fallback reason. |
| Output | Metrics | `summary.json`, `episodes.csv` | Official metrics still copied from `env.get_metrics()`. |

## Interfaces

Memory prior JSON:

```json
{
  "anchors": [
    {
      "object_category": "chair",
      "scene_id": "optional scene id or suffix",
      "x_m": 1.25,
      "z_m": -0.75,
      "confidence": 0.92,
      "source": "detector_positive:previous_session",
      "coordinate_frame": "episode_start_relative"
    }
  ]
}
```

If `coordinate_frame` is omitted, the parser treats the anchor as
`episode_start_relative` for backward compatibility with the first synthetic
smoke. Lifecycle DB exports use `coordinate_frame="habitat_world"` and are
ignored by the action selector until a valid transform or episode-relative
memory source exists.

For `episode_start_relative` anchors, `x_m` is the right/lateral coordinate and
`z_m` is the forward coordinate in the episode-start frame. Habitat-Lab's
official 2D `gps` sensor emits `[forward, right]`, so the adapter swaps those
components at the observation boundary before applying memory bearing logic.
Habitat compass is also negated because right turns decrease the raw compass
value.

CLI additions:

```bash
python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
  --policy memory_guided_frontier \
  --memory-prior-path runs/.../memory_prior.json \
  --memory-stop-radius-m 0.35 \
  --memory-bearing-tolerance-deg 20 \
  --memory-min-confidence 0.5
```

The protocol manifest records the memory prior path, confidence threshold, and
a benchmark caveat when the memory source is not produced by a documented
non-oracle discovery run.

## Data Flow

1. CLI parses memory-prior flags into `OfficialObjectNavRunConfig`.
2. Preflight validates JSON shape without importing Habitat when
   `--validate-habitat` is absent.
3. Each episode initializes policy state with the episode category and scene id.
4. The policy selects the highest-confidence matching
   `episode_start_relative` memory anchor.
5. If an anchor exists and the agent is inside `memory_stop_radius_m`, emit
   `stop`.
6. If an anchor exists but is not aligned, turn toward the remembered bearing.
7. If aligned and center depth is clear, move forward.
8. If no anchor exists, confidence is too low, or the depth corridor is blocked,
   fall back to occupancy-frontier exploration.
9. After the episode, write official metrics plus memory debug telemetry.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Memory JSON malformed | local parse/validation test | fail preflight with actionable error. |
| Memory source is oracle or hand-authored | manifest source/caveat | mark run invalid for benchmark claims. |
| Anchor in wrong scene/category | no matching anchor or scene mismatch | fall back to `occupancy_frontier`. |
| Anchor in unsupported coordinate frame | selector rejects non-`episode_start_relative` frames | fall back to `occupancy_frontier`; do not fake an official memory signal. |
| Anchor stale or inaccurate | official failure or large residual distance | record attempted memory and fallback reason for later validity learning. |
| Agent near remembered anchor but target absent | official `success=0` after stop | preserve as stale-memory negative evidence. |
| Obstacle blocks direct approach | depth clear check fails | use occupancy-frontier fallback/turn burst instead of pushing forward. |

## Verification Plan

1. Unit-test memory-prior parsing, validation, and manifest recording.
2. Unit-test anchor selection by category and optional scene id.
3. Unit-test compact Habitat scene-key matching and rejection of unsupported
   coordinate frames.
4. Unit-test action choices: stop within radius, turn toward bearing, move when
   aligned and clear, fallback when missing/blocked.
5. Unit-test debug telemetry and no local recomputation of official metrics.
6. Run local focused adapter/CLI tests and the full local core suite.
7. Run Linux focused tests in conda env `habitat`.
8. Run a tiny official smoke with a clearly labeled synthetic memory prior. The
   result is a plumbing/mechanism check only, not a paper claim.

Implemented first-slice verification:

- Local focused official adapter/CLI tests: `26` passed.
- Linux focused official adapter/CLI tests in conda env `habitat`: `26` passed.
- Linux official smoke:
  `runs/habitat_official_objectnav/memory_guided_frontier_synthetic_prior_1ep_20260530_v1`.
- The smoke selected the synthetic `chair` memory anchor, emitted one `stop`
  action, and preserved Habitat-provided official metrics. It is explicitly
  invalid for benchmark claims because the memory prior was synthetic.

Frame-safety extension:

- The memory-prior parser now records `coordinate_frame`.
- The selector only acts on `episode_start_relative` anchors by default.
- Lifecycle DB exports are labeled `habitat_world`, so they are bridge
  artifacts rather than direct official policy inputs.
- Local focused exporter/official-policy tests: `31` passed.
- Linux focused exporter/official-policy tests in conda env `habitat`:
  `31` passed.
- Linux guard smoke
  `runs/habitat_official_objectnav/memory_guided_frontier_world_prior_guard_1ep_20260530_v1`
  loaded a real lifecycle export with `12` `habitat_world` anchors and recorded
  `fallback_reason=no_matching_memory`.
- GPS/compass frame correction:
  `runs/habitat_official_objectnav/memory_guided_frontier_episode_frame_forward_probe_1ep_20260530_v1`
  confirmed a synthetic `episode_start_relative` forward anchor emits
  `move_forward` actions in the real official Habitat loop.

## Research Relevance

This creates the missing bridge between lifelong memory and official ObjectNav
metrics. It lets future experiments compare:

- no-memory occupancy frontier;
- memory with documented prior discovery;
- stale or relocated memory;
- learned memory-validity gating;
- later language-to-category or language-to-instance grounding.

The key paper value is not that a hand-written coordinate improves one smoke
episode. The value is an auditable protocol where memory source, validity,
stale failures, and official SR/SPL are recorded together.

The current lifecycle exporter adds the artifact chain but not yet the final
coordinate bridge. The next benchmark-facing step must produce
episode-start-relative memories from a documented, non-oracle source.

## Open Questions

- Should official benchmark-facing memory priors come from a preceding Habitat
  exploration episode, from the existing lifecycle memory artifact, or from a
  detector cache keyed by observation bytes?
- What stop radius should match real robot uncertainty without tuning to HM3D?
- How should multiple same-category memories be ranked before learned validity
  is connected?
