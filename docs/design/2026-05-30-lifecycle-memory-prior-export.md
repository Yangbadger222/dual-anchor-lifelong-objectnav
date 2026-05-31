# Design Doc: Lifecycle Memory Prior Export

Date: 2026-05-30
Owner: Codex
Status: Implemented first slice

## Goal

Export remembered object anchors from existing lifecycle SQLite memory artifacts
into the official Habitat ObjectNav memory-prior JSON format consumed by
`memory_guided_frontier`.

This turns memory priors from hand-written smoke inputs into documented
artifacts produced by the project memory stack. The first slice is explicitly
frame-safe: lifecycle DB anchors are exported as Habitat world-frame anchors,
not as episode-start-relative GPS anchors.

## Non-Goals

- Do not claim exported lifecycle memories are official benchmark-valid by
  default. The source run must still document whether anchors came from
  detector-backed discovery, oracle masks, or synthetic protocols.
- Do not alter the lifecycle SQLite schema in this slice.
- Do not run detector inference or generate new memories here; this is an
  exporter only.
- Do not solve stale-memory validity learning here.
- Do not silently transform Habitat world coordinates into official
  episode-start-relative coordinates without a documented transform.

## Background

`memory_guided_frontier` can already consume JSON anchors with category,
optional scene id, `x_m`, `z_m`, confidence, and source. The older lifecycle
runner writes `lifecycle_memory.sqlite` with:

- `object_instance_anchors(scene_id, episode_dataset_version, category,
  instance_id, anchor_x, anchor_z, updated_at)`
- `usability_beliefs(..., p_existence, p_location_valid, p_usable, updated_at)`

Those two tables are enough to create a memory prior where confidence is the
product of existence, location-validity, and usability belief when available.

## System Boundary

The exporter owns:

- reading a lifecycle memory SQLite file in read-only mode;
- joining anchors with optional beliefs;
- filtering by dataset version, scene, category, and minimum confidence;
- writing official memory-prior JSON.

It depends on the existing lifecycle memory schema and the official memory
prior parser for validation. It does not modify the source database or call
Habitat. It also does not make exported world-frame anchors actionable inside
the official policy by itself.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Lifecycle memory | SQLite file | Usually `lifecycle_memory.sqlite` from a prior run. |
| Input | Filters | CLI flags | Optional dataset version, scene id, categories, min confidence. |
| Output | Memory prior | JSON | `{"anchors": [...]}` compatible with official adapter. Lifecycle exports default to `coordinate_frame="habitat_world"`. |
| Output | Summary | JSON/stdout | Anchor count, source db, filters, confidence mode. |

## Interfaces

CLI:

```bash
python -m objectnav_core.cli.export_lifecycle_memory_prior \
  --memory-db runs/.../lifecycle_memory.sqlite \
  --output runs/.../official_memory_prior.json \
  --source-tag lifecycle_detector_positive \
  --min-confidence 0.5
```

Output anchor:

```json
{
  "object_category": "chair",
  "scene_id": "00802-wcojb4TFT35",
  "x_m": 1.25,
  "z_m": -0.5,
  "confidence": 0.903168,
  "source": "lifecycle_detector_positive:goal_object:123",
  "coordinate_frame": "habitat_world"
}
```

Frame semantics:

- `habitat_world`: coordinates from lifecycle memory DB artifacts. These are
  useful for auditing and future transforms, but the current official policy
  must not act on them directly because official `gps` observations are
  episode-start-relative.
- `episode_start_relative`: coordinates already expressed in the official
  `gps` frame for the current ObjectNav episode. Only this frame is actionable
  by `memory_guided_frontier` today.

## Data Flow

1. Open the SQLite database read-only.
2. Read all rows from `object_instance_anchors`.
3. Left-join the matching `usability_beliefs` row by scene, dataset version,
   category, and instance id.
4. Compute confidence:
   `p_existence * p_location_valid * p_usable`, or `1.0` if no belief exists.
5. Apply filters.
6. Label each exported anchor with the configured coordinate frame; the default
   is `habitat_world`.
7. Emit deterministic JSON sorted by scene/category/instance id.
8. Validate the written JSON with `load_official_memory_prior`.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Missing DB | path validation | fail with clear error. |
| DB lacks anchor table | SQLite schema check | fail and report expected table. |
| Anchor has no belief | left join returns null | export with confidence `1.0` and source caveat. |
| Confidence below threshold | filter count | omit and report filtered count. |
| Source run used oracle anchors | `--source-tag` / docs | preserve in source string; do not claim benchmark validity. |
| World-frame anchor fed to official policy | `coordinate_frame="habitat_world"` | official selector ignores it until a valid episode-frame transform exists. |

## Verification Plan

1. Unit-test export from a temporary `LifelongMemoryHarness` DB with one anchor
   and belief.
2. Unit-test confidence filtering and missing-belief fallback.
3. Unit-test CLI writes JSON and summary.
4. Unit-test that lifecycle exports preserve `coordinate_frame="habitat_world"`
   and that the official selector rejects unsupported coordinate frames.
5. Run local focused tests, full tests, `py_compile`, and `git diff --check`.
6. Run Linux focused tests in conda env `habitat`.
7. If an existing lifecycle memory DB is available on Linux, export it and
   preflight `memory_guided_frontier` with the exported JSON.

Implemented first-slice verification:

- Local focused exporter/official tests: `31` passed.
- Local full test suite: `322` passed.
- Local `compileall` and `git diff --check` returned cleanly.
- Linux focused exporter/official tests in conda env `habitat`: `31` passed.
- Linux real export:
  `runs/habitat_official_objectnav/lifecycle_memory_prior_export_grounding_dino_detector_anchor_matrix_20260530_v1/official_memory_prior.json`
  with `12` anchors, all `coordinate_frame="habitat_world"`.
- Linux official guard smoke:
  `runs/habitat_official_objectnav/memory_guided_frontier_world_prior_guard_1ep_20260530_v1`
  loaded the real export and fell back with
  `fallback_reason=no_matching_memory`, confirming the world-frame guard.

## Research Relevance

This creates the next reproducibility step for the paper story: official
ObjectNav memory policies can now consume memories produced by prior project
runs. The resulting runs are still only as valid as their memory source, but
the artifact chain becomes explicit and auditable instead of hand-authored.

The frame boundary is part of the research value. Exported lifecycle memories
are honest bridge artifacts today; they become official policy inputs only
after the project implements a valid world-to-episode transform or an
episode-relative discovery/memory logging pipeline.

## Open Questions

- Which lifecycle runs should be considered non-oracle enough for the first
  serious official-memory comparison?
- What is the cleanest source for an official episode-start-relative memory:
  a documented transform from lifecycle world anchors, or direct logging from
  the official observation stream?
- Should confidence eventually come from learned validity calibration rather
  than the current belief-product baseline?
