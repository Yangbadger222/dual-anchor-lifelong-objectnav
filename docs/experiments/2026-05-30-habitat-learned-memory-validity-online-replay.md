# Experiment Report: Habitat Learned Memory Validity Online Replay

Date: 2026-05-30  
Owner: Codex  
Status: Completed

## Question

Can an offline learned memory-validity model drive an actual online
memory-vs-frontier policy flip in the Habitat closed-loop dual-anchor runner?

## Hypothesis

On the relocated `sofa` row where event-posterior reliability reused stale
memory, the evidence-only learned validity model should lower the memory-valid
probability enough to choose `frontier_first`.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `6162b8a` |
| Machine | `badger-linux` |
| Dataset / scene | HM3D ObjectNav `val`, `hm3d/val/00820-mL8ThkuaVTM/mL8ThkuaVTM.basis.glb` |
| Simulator / detector | Habitat-Sim, Grounding-DINO tiny |
| Challenge | `goal_object_relocation` |
| Selected group | `hm3d/val/00820-mL8ThkuaVTM/mL8ThkuaVTM.basis.glb|sofa|relocated:goal_object:220->goal_object:341` |
| Frontier / observation | `navmesh_frontier`, `frontier_probe_count=3`, `frontier_probe_heading_count=2`, `route_observation_mode=option_end` |
| Learned model | `runs/habitat_closed_loop_dual_anchor/memory_validity_learning_grounding_dino_stable_relocation_balanced6_evidence_only_20260530_v1/model.json` |

## Command

Baseline event-posterior replay:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_closed_loop_dual_anchor_objectnav \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_closed_loop_dual_anchor/event_posterior_sofa_relocation_baseline_online_20260530_v1 \
  --target-categories sofa \
  --selected-group-ids 'hm3d/val/00820-mL8ThkuaVTM/mL8ThkuaVTM.basis.glb|sofa|relocated:goal_object:220->goal_object:341' \
  --sensor-width 640 \
  --sensor-height 360 \
  --challenge goal_object_relocation \
  --query-repeats 1 \
  --memory-valid-prior 0.5 \
  --memory-reliability-mode event_posterior \
  --frontier-mode navmesh_frontier \
  --frontier-probe-count 3 \
  --frontier-probe-heading-count 2 \
  --route-observation-mode option_end \
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

Learned replay used the same command with:

```bash
--output runs/habitat_closed_loop_dual_anchor/learned_validity_sofa_relocation_evidence_only_online_20260530_v1 \
--memory-validity-model runs/habitat_closed_loop_dual_anchor/memory_validity_learning_grounding_dino_stable_relocation_balanced6_evidence_only_20260530_v1/model.json
```

## Metrics

| Metric | Baseline Event Posterior | Learned Validity | Notes |
|---|---:|---:|---|
| Memory-valid probability | `0.2875` | `0.006685` | Learned row records base reliability value `0.2875`. |
| Expected memory-first actions | `199.3375` | `258.589465` | Computed before decision. |
| Expected frontier-first actions | `246.0` | `246.0` | Same selected group and frontier settings. |
| Memory decision | `memory_first` | `frontier_first` | Actual online policy flip. |
| Memory decision bucket | `memory_attempt_failed` | `harmful_memory_reuse_avoided` | Learned policy avoids stale-memory reuse. |
| Memory evidence valid | `false` | `false` | `shared_gate_success=false`, detector precision `0.0`. |
| Success episodes | `0/1` | `0/1` | Mechanism result, not benchmark improvement. |
| Memory-guided action count | `49` | `246` | Baseline fails after memory attempt; learned chooses frontier. |

## Observations

- The learned replay is the first confirmed online Habitat row where a learned
  detector-backed pre-decision validity signal changes the memory-vs-frontier
  decision.
- The offline scorer predicted the same probability and decision for this row:
  evidence-only learned validity `0.006685`, boundary `0.066351`, learned
  decision `frontier_first`.
- The fixed/evidence/event-posterior decision-sensitivity miner still reports
  `0` heuristic counterfactual flips on the same stable-plus-relocation inputs.
- The selected row is not a performance win. The target remains unfound in both
  A and B, so this result should be used as a mechanism milestone and a
  debugging target for better frontier/search behavior.

## Result

The experiment demonstrates the missing mechanism: an offline learned
memory-validity model can now drive an actual online Habitat policy flip from
`memory_first` to `frontier_first` on a stale relocated object row. It does not
yet establish ObjectNav benchmark superiority.

## Follow-up

- Scale learned replay to a balanced stable-plus-relocation matrix with
  category/scene holdouts.
- Improve the frontier/search policy so avoiding stale memory can translate
  into successful target recovery rather than only a decision flip.
- Compare evidence-only, route-aware, and full audit-feature models without
  relying on relocation-specific metadata.
