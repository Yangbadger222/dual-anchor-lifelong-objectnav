# Experiment Report: Habitat Memory-Local Active Search Selected Replay

Date: 2026-05-30
Owner: Codex
Status: Completed

## Question

Does deterministic memory-centered local active search improve the selected
relocation failures compared with the current navmesh post-memory frontier
repair?

## Hypothesis

Using the remembered object anchor as a local radial search prior should reduce
post-memory search cost. It should only be considered progress if it preserves
or improves success on the selected relocation rows, especially the relocated
`sofa` row that the navmesh post-memory route already repairs.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, `74e63ab` |
| Machine | `badger-linux` |
| Habitat | Habitat-Lab / Habitat-Sim `0.3.3` |
| Dataset / scene | HM3D ObjectNav `val` |
| Detector | Grounding-DINO tiny |
| Confirmation | `multiview` |
| Route observation | `per_action` |
| Noise | clean RGB/depth profiles |
| Official measures | Not used in this replay; see official-measure alignment design. |

## Commands

The local-active run used:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/event_posterior_relocation_selected_memory_local_active_per_action_accounting_fix_20260530_v1 \
  --target-categories sofa,tv_monitor,chair,toilet \
  --selected-group-ids 'hm3d/val/00820-mL8ThkuaVTM/mL8ThkuaVTM.basis.glb|sofa|relocated:goal_object:220->goal_object:341,hm3d/val/00814-p53SfW6mjZe/p53SfW6mjZe.basis.glb|tv_monitor|relocated:goal_object:435->goal_object:57,hm3d/val/00814-p53SfW6mjZe/p53SfW6mjZe.basis.glb|chair|relocated:goal_object:483->goal_object:13,hm3d/val/00814-p53SfW6mjZe/p53SfW6mjZe.basis.glb|toilet|relocated:goal_object:260->goal_object:714' \
  --sensor-width 640 \
  --sensor-height 360 \
  --challenge goal_object_relocation \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode event_posterior \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 3 \
  --frontier-probe-heading-count 2 \
  --post-memory-search-mode memory_local_active \
  --local-search-radii-m 1.0,2.0,4.0 \
  --local-search-probe-count 8 \
  --local-search-heading-count 4 \
  --local-search-score-mode distance_prior \
  --route-observation-mode per_action \
  --detector-confirmation-mode multiview \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --grounding-dino-max-image-side 384 \
  --rgb-noise-profile configs/noise/rgb_published_v1.yaml \
  --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml \
  --noise-level clean \
  --min-target-pixels 24 \
  --min-detector-pixels 20 \
  --max-detection-area-ratio 0.7 \
  --detector-prompt-mode target
```

The matched navmesh baseline used the same command with:

```bash
--output runs/habitat_closed_loop_dual_anchor/event_posterior_relocation_selected_navmesh_per_action_accounting_fix_20260530_v1
--post-memory-search-mode frontier_mode
```

## Metrics

| Post-memory search | Memory-guided success | Memory-guided actions | Frontier-only success | Frontier-only actions |
|---|---:|---:|---:|---:|
| `navmesh_frontier` via `frontier_mode` | `1/4` | `1195` | `0/4` | `1312` |
| `memory_local_active` | `0/4` | `767` | `0/4` | `1312` |

Selected memory-guided rows:

| Category | Navmesh result | Local-active result | Interpretation |
|---|---|---|---|
| `sofa` | success, `171` actions, `memory_missed_then_frontier_repaired` | fail, `149` actions, `memory_then_frontier_failed` | Local radial probes lose the known positive repair. |
| `tv_monitor` | fail, `490` corrected actions | fail, `217` actions | Local search is cheaper but still misses. |
| `chair` reverse | fail, `104` actions, frontier-first | fail, `104` actions, frontier-first | No effect because expected utility selects query-start frontier. |
| `toilet` | fail, `430` actions, frontier-first | fail, `297` actions, memory-then-local failed | Local search changes the decision but still misses. |

## Accounting Fix

During this replay, failed post-memory repair attempts exposed an internal
accounting bug: if memory-first attempted a post-memory search and that search
failed, the row previously recorded only the memory leg. Commit `74e63ab` fixes
this so failed post-memory repair costs are included in `action_count` and
`selected_candidate_types` records `["memory", "frontier"]`.

The matched navmesh and local-active artifacts above were rerun after that fix.

## Result

The first deterministic radial `memory_local_active` policy is not a successful
algorithmic improvement. It lowers action counts on failures, but it regresses
the relocated `sofa` row that navmesh post-memory search already repairs and it
does not recover `tv_monitor`, `chair`, or `toilet`.

This is a useful negative result. Memory-conditioned local search still looks
like the right research direction, but the local policy must become more
observability-aware:

- use depth/occupancy frontiers or view cones, not only radial navmesh rings;
- keep a route-level evidence map of observed and unobserved sectors;
- learn or estimate candidate value from replay traces;
- evaluate through official Habitat-Lab measures before any SOTA comparison.

## Follow-up

- Do not scale this deterministic radial local-active policy to balanced6 as a
  claimed improvement.
- Implement official Habitat-Lab measure alignment next so SR/SPL are available.
- After official preflight, revisit local search as an occupancy/depth-informed
  or learned candidate scorer with candidate trace logging.
