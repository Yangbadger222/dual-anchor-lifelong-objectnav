# Experiment Report: Habitat Goal-Object Relocation Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed smoke; not benchmark evidence

## Question

Does the new `goal_object_relocation` challenge run in real Habitat, produce
auditable old-instance to new-instance rows, and create healthier stale-memory
decision boundaries than the previous stable replay pool?

## Hypothesis

Pairing same-scene, same-category object instances should make a remembered
pose valid for discovery but stale for query. `memory_guided` should avoid
naive stale-memory reuse when the remembered instance does not verify against
the query instance. Detector-backed event posterior may not flip yet, because
the first smoke uses only two groups and detector events may appear in fallback
contexts rather than memory-validity contexts.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `43c0193` |
| Machine | Linux `badger@100.88.131.52` |
| Conda env | `habitat` |
| Dataset | HM3D ObjectNav `val` |
| Simulator | Habitat-Sim |
| Challenge | `goal_object_relocation` |
| Frontier | `navmesh_frontier`, 3 probes, 2 headings |
| Route observation | `option_end` |
| Sensor | 640 x 360 |
| Categories | `bed,chair,plant,sofa,toilet,tv_monitor` |

## Commands

Remote verification:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
git pull --ff-only origin codex/habitat-memory-lifecycle
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
python -m pytest \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py \
  src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
```

Oracle relocation smoke:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/oracle_goal_object_relocation_navmesh_smoke_2group_20260530_v1 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 2 \
  --sensor-width 640 \
  --sensor-height 360 \
  --challenge goal_object_relocation \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode evidence \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 3 \
  --frontier-probe-heading-count 2
```

Grounding-DINO relocation smoke:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/grounding_dino_goal_object_relocation_navmesh_event_posterior_smoke_2group_20260530_v1 \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --max-groups 2 \
  --sensor-width 640 \
  --sensor-height 360 \
  --challenge goal_object_relocation \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode event_posterior \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 3 \
  --frontier-probe-heading-count 2 \
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
  --detector-prompt-mode target \
  --detector-confirmation-mode multiview
```

Decision-sensitivity mining:

```bash
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.mine_habitat_decision_sensitivity \
  runs/habitat_closed_loop_dual_anchor/oracle_goal_object_relocation_navmesh_smoke_2group_20260530_v1/summary.json \
  --output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_oracle_goal_object_relocation_smoke_2group_20260530_v1/report.json \
  --csv-output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_oracle_goal_object_relocation_smoke_2group_20260530_v1/candidates.csv \
  --top-k 20

PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.mine_habitat_decision_sensitivity \
  runs/habitat_closed_loop_dual_anchor/grounding_dino_goal_object_relocation_navmesh_event_posterior_smoke_2group_20260530_v1/summary.json \
  --output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_grounding_dino_goal_object_relocation_smoke_2group_20260530_v1/report.json \
  --csv-output runs/habitat_closed_loop_dual_anchor/decision_sensitivity_grounding_dino_goal_object_relocation_smoke_2group_20260530_v1/candidates.csv \
  --top-k 20
```

## Selected Pairs

Both oracle and Grounding-DINO smokes selected the same relocated pairs:

| Category | Relocation group |
|---|---|
| `bed` | `hm3d/val/00814-p53SfW6mjZe/p53SfW6mjZe.basis.glb|bed|relocated:goal_object:194->goal_object:698` |
| `chair` | `hm3d/val/00814-p53SfW6mjZe/p53SfW6mjZe.basis.glb|chair|relocated:goal_object:13->goal_object:483` |

Rows include `memory_instance_id` and `target_instance_id`, so the old and new
object identities are recoverable without parsing the group id.

## Metrics

Oracle policy summary:

| Policy | Success | Actions | Bucket |
|---|---:|---:|---|
| `memory_guided` | 1/2 | 489 | `harmful_memory_reuse_avoided`: 2 |
| `frontier_only` | 1/2 | 489 | `frontier_only`: 2 |
| `naive_count` | 0/2 | 386 | `naive_memory_reuse`: 2 |

Grounding-DINO policy summary:

| Policy | Success | Actions | Bucket |
|---|---:|---:|---|
| `memory_guided` | 0/2 | 727 | `harmful_memory_reuse_avoided`: 2 |
| `frontier_only` | 0/2 | 727 | `frontier_only`: 2 |
| `naive_count` | 0/2 | 401 | `naive_memory_reuse`: 2 |

Decision-sensitivity mining:

| Run | Candidates | Boundary rows | Counterfactual flips |
|---|---:|---:|---:|
| Oracle relocation smoke | 1 | 1 reliability-sensitive | 0 |
| Grounding-DINO relocation smoke | 2 | 2 reliability-sensitive | 0 |

Best mined rows:

| Detector | Category | Boundary reliability | Actual reliability | Interval gap | Event count |
|---|---|---:|---:|---:|---:|
| Oracle | `bed` | 0.567084 | 0.287500 | 0.279584 | 0 |
| Grounding-DINO | `bed` | 0.555147 | 0.287500 | 0.267647 | 0 |
| Grounding-DINO | `chair` | 0.815385 | 0.287500 | 0.527885 | 0 |

## Observations

- The relocation builder worked in a real Habitat run and selected auditable
  old-object to new-object pairs in the same HM3D scene.
- Query-time memory verification failed against the new object in both smokes,
  which is the intended stale-memory pressure.
- `memory_guided` selected frontier first for both pairs, while `naive_count`
  attempted stale memory first.
- The oracle smoke produced one successful frontier row for the `chair` pair.
  The detector smoke did not achieve success on either pair under this tiny
  two-group configuration.
- Grounding-DINO produced runtime confirmation events, but they were in
  fallback context. The event-posterior reliability used for memory validity
  stayed at the evidence value `0.2875`, so there was no event-posterior flip.
- This is a better experiment geometry than the previous boundary-edge cases:
  mined rows are reliability-sensitive, but the reliability interval is still
  well below the boundary.

## Result

The relocation proxy is implemented and real-Habitat runnable. It creates a
meaningful stale-memory condition and exposes reliability-sensitive boundaries,
but this two-group smoke does not demonstrate an event-posterior policy flip.
The honest claim is now stronger but still limited: the method can avoid stale
instance memory in the relocation proxy, while detector-event calibration has
not yet changed a decision.

## Follow-up

- Run a broader relocation sweep and mine for smaller
  `boundary_reliability_interval_gap` values.
- Add a selector for relocated pairs with larger old-to-new geodesic separation
  and stronger fallback success.
- Investigate whether detector confirmation events should contribute to
  memory-validity reliability when the context is fallback discovery of the new
  instance, or whether that should remain excluded.
