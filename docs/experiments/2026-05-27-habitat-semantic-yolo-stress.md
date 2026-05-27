# Experiment Report: Habitat Semantic YOLO-Breaker Stress

Date: 2026-05-27  
Owner: Codex  
Status: Completed

## Question

Can the usability-memory system consume Habitat semantic sensor masks, and how does it behave when the target mask is corrupted with detector-like failures: missed detections, false-positive fly points, and edge-break mask damage?

## Hypothesis

Clean semantic masks should produce stable positive evidence and high final memory validity. Missed visible targets should push the memory toward verification and lower validity. Fragmented fly-point and edge-break masks should be downgraded to `UNKNOWN` by mask-quality gates, but mixed corruption may still create false-positive confirmations.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `db13f53`, dirty worktree |
| Machine | `badger-linux`, Ubuntu Linux 6.8.0-111-generic, NVIDIA RTX 4070 Laptop GPU |
| Dataset / scene | HM3D example `00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb` with semantic annotations |
| Simulator / robot | Habitat-Sim 0.3.3 direct RGB-D-semantic sensors, no robot |
| Python / env | conda env `habitat`, Python 3.9.23 |
| Key parameters | 30 episodes, 7 rows per episode, seed `211`, sensor size `96`, breaker modes `clean, miss, fly_point, edge_break, mixed` |

## Command

```bash
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_semantic_yolo_stress \
  --scene datasets/habitat/scene_datasets/hm3d/example/00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb \
  --scene-dataset-config datasets/habitat/scene_datasets/hm3d/example/hm3d_annotated_basis.scene_dataset_config.json \
  --output runs/habitat_usability/hm3d_semantic_yolo_stress_30ep \
  --episodes 30 \
  --seed 211 \
  --sensor-size 96
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Episodes completed | 30 | 6 episodes per breaker mode |
| Trace rows | 210 | reset + 6 actions per episode |
| Semantic objects / categories | 908 / 124 | From Habitat semantic scene |
| Evidence counts | `POSITIVE=71`, `NON_CONFIRMATION=13`, `UNKNOWN=126` | No collision/access-blocked rows in this run |
| Decision counts | `VERIFY=176`, `TRUST=34` | No search/retire rows after out-of-view absence was treated as unknown |
| Clean mean final `p_valid` | 0.908939 | Baseline with uncorrupted masks |
| Miss mean final `p_valid` | 0.610724 | 16 missed-visible-target rows |
| Fly-point mean final `p_valid` | 0.847893 | Fragmentation gate converted most rows to `UNKNOWN` |
| Edge-break mean final `p_valid` | 0.866955 | Edge/fragmentation damage mostly reduced confidence rather than deleting memory |
| Mixed mean final `p_valid` | 0.860801 | 9 false-positive-positive rows |
| False-positive-positive rows | 9 | Positive evidence with detector precision below 0.25 |
| Missed visible target rows | 16 | Oracle target visible but corrupted detector mask below threshold |

## Observations

- Habitat-Sim direct sensors returned `rgb`, `depth`, and `semantic` observations. The semantic mask is a `uint32` id image.
- Target semantic ids were selected from actually visible semantic masks, with structural categories such as wall/floor/door/railing avoided when possible.
- Treating "target absent from the current frame" as `FREE` was too aggressive; the final run treats it as `UNKNOWN` unless the oracle target is visible and the detector misses it.
- The mask-quality gate catches many fly-point and edge-break artifacts by using component count, largest-component ratio, and edge-touch ratio.
- The mixed breaker still produced 9 false-positive-positive rows, which means single-frame false positives can still inflate memory when they survive the quality gate.

## Result

The semantic sensor path is now functional and the usability-memory system can be stressed with corrupted semantic masks. The system is robust to many fragmented fly-point and edge-break artifacts because they become `UNKNOWN`, but it is not fully robust to plausible single-frame false positives. Missed visible targets reduce validity, but did not force retirement in this 30-episode run.

This is a stronger simulation stress test than the previous distance-proxy replay, but it still uses oracle semantic ids corrupted into detector-like masks. It does not run a real YOLO model and does not report official ObjectNav success/SPL.

## Follow-up

- Add temporal consistency before accepting `POSITIVE` evidence from small or low-precision masks.
- Add multi-view confirmation before raising `p_location_valid` strongly.
- Save optional debug mask PNGs for representative clean, miss, fly-point, edge-break, and mixed rows.
- Run the same breaker against official HM3D ObjectNav episodes once HM3D v0.1 scene assets are available.
