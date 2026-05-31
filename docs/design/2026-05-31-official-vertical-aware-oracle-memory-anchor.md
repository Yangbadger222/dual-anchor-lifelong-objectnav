# Design Doc: Official Vertical-Aware Oracle Memory Anchor

Date: 2026-05-31
Owner: Codex
Status: Draft

## Goal

Make the official oracle-memory upper bound floor-aware by preserving optional
vertical displacement in memory anchors.

The previous oracle-memory exporter stored only `x_m` and `z_m`. In HM3D
multi-level scenes, this can reconstruct the correct horizontal target on the
wrong floor when the target viewpoint height differs from the episode start
height. This slice adds optional `y_m` support for oracle diagnostics while
keeping existing 2D memory priors valid.

## Non-Goals

- Do not require all memory priors to provide height.
- Do not convert benchmark-facing detector memory into privileged height.
- Do not claim oracle-height runs as benchmark-valid.
- Do not redesign FMM or occupancy-grid execution in this slice.
- Do not introduce persistent global world coordinates as the core memory
  representation.

## Background

The first oracle-memory upper-bound export produced four episode-specific
anchors. With `oracle_follower` and a tighter radius, it reached `2/4` success.
Inspection showed one major root cause: the chair episode selected a valid
Habitat view point at `y=0.229`, but the x/z-only reconstruction used the
episode start height `y=2.595`. The oracle follower then navigated to the
right horizontal location on the wrong floor and ended far from the official
`VIEW_POINTS` success set.

For lifelong ObjectNav, this is not just a diagnostic nuisance. A memory system
that ignores floor/vertical context will be brittle in multi-floor buildings.
The simulation diagnostic should expose that dimension rather than hide it.

## System Boundary

Owned by this slice:

- add optional `y_m` to `OfficialMemoryAnchor`;
- parse, emit, and debug `y_m` without breaking old anchors;
- export `y_m` as vertical offset from episode start height for oracle priors;
- reconstruct oracle backend world goals as `start_y + y_m` when available;
- add tests proving old anchors still fall back to start height and oracle
  anchors preserve floor height.

Outside this slice:

- learned floor estimation from RGB-D;
- multi-floor topological memory graphs;
- FMM or DDPPO executor repair;
- language query integration.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Habitat goal/viewpoint | `(x, y, z)` world position | Privileged oracle diagnostic label. |
| Input | Episode start pose | start position and rotation | Used to form relative `x/z` and `y` offset. |
| Output | Memory anchor | JSON with `x_m`, `z_m`, optional `y_m` | `y_m` is vertical displacement from episode start in meters. |
| Output | Oracle world goal | `(x, y, z)` | Uses `start_y + y_m` when available. |

## Interfaces

Existing memory-prior JSON remains valid:

```json
{"object_category": "chair", "x_m": 1.0, "z_m": 2.0}
```

Oracle/floor-aware priors may add:

```json
{"object_category": "chair", "x_m": 1.0, "y_m": -2.36588, "z_m": 2.0}
```

Internal helpers:

- `OfficialMemoryAnchor.y_m`
- `_targetnav_goal_from_memory_anchor(anchor)`
- `_memory_anchor_oracle_goal_position(state, anchor)`
- `make_official_oracle_memory_anchor(...)`
- `_world_position_to_episode_relative_xzy(...)`

## Data Flow

1. Oracle exporter selects a Habitat goal/viewpoint.
2. Convert horizontal displacement into episode-relative `x_m/z_m`.
3. Convert vertical displacement into `y_m = goal_y - start_y`.
4. Write `y_m` only when the source position has a valid vertical component.
5. During oracle backend activation, reconstruct world goal y as
   `start_position[1] + y_m`; if `y_m` is absent, preserve old behavior and use
   `start_position[1]`.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Old prior has no `y_m` | `anchor.y_m is None` | Use episode start height exactly as before. |
| `y_m` non-finite | parser validation | Reject malformed prior. |
| Wrong floor still selected | official metrics remain poor | Later export multiple viewpoints or choose success-aligned candidates. |
| Non-oracle backend ignores height | backend receives same x/z goal | Expected; FMM is 2D and remains diagnostic. |

## Verification Plan

1. Add failing tests for:
   - parser/payload round-trip of optional `y_m`;
   - oracle exporter emits negative/positive vertical offsets;
   - oracle goal reconstruction uses `start_y + y_m`;
   - old anchors without `y_m` keep previous start-height fallback.
2. Implement the minimal schema and transform change.
3. Run local focused tests and full objectnav_core tests.
4. Sync to Linux Habitat and run focused tests.
5. Re-export the 4-episode oracle prior and rerun oracle-memory +
   oracle-backend radius `0.2` smoke.

## Research Relevance

This supports a stronger memory story: lifelong object memory should encode the
object's reusable spatial anchor plus enough floor/vertical context to be
re-findable in multi-level indoor scenes. The optional height field is a
diagnostic bridge toward a future learned floor/topological-memory component,
not a hand-tuned benchmark trick.

## Open Questions

- Should future non-oracle memory use learned floor classification instead of
  metric height?
- Should the official memory schema allow multiple candidate viewpoints per
  object anchor with confidence over floor/viewpoint?
