# Experiment Report: Official Oracle Memory Prior Upper Bound Smoke

Date: 2026-05-31
Owner: Codex
Status: Completed

## Question

Can privileged Habitat goal/viewpoint labels be exported as episode-specific
official memory anchors, then routed through the existing TargetNav backend
selector to separate memory quality from executor quality?

## Hypothesis

The oracle memory prior should activate immediately as a `memory_anchor` goal.
With the oracle follower backend and a tight enough follower radius, it should
produce a clear diagnostic upper bound. With FMM, failures should mostly expose
the local execution bottleneck rather than memory localization quality.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, working tree with oracle-memory-prior changes |
| Machine | Linux Habitat host `badger@100.88.131.52` |
| Dataset / bag / map | HM3D ObjectNav `val_mini` |
| Simulator / robot | Habitat-Lab / Habitat-Sim |
| Key parameters | `max_episodes=4`, seed `313`, prior source `habitat_official_oracle_memory_prior`, coordinate frame `episode_start_relative` |

## Command

```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 badger@100.88.131.52 \
  'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
   source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
   export PYTHONPATH=src/objectnav_core HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet && \
   python -m objectnav_core.cli.export_habitat_official_oracle_memory_prior \
     --output runs/habitat_official_objectnav/oracle_memory_prior_valmini_4ep_20260531_v1/memory_prior.json \
     --max-episodes 4 \
     --seed 313'
```

```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 badger@100.88.131.52 \
  'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
   source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
   export PYTHONPATH=src/objectnav_core HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet && \
   python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
     --output runs/habitat_official_objectnav/oracle_memory_oracle_backend_radius02_4ep_150steps_20260531_v1 \
     --policy memory_active_perception_frontier_targetnav \
     --targetnav-backend oracle_follower \
     --pathfinder-suffix-goal-radius-m 0.2 \
     --memory-prior-path runs/habitat_official_objectnav/oracle_memory_prior_valmini_4ep_20260531_v1/memory_prior.json \
     --max-episodes 4 \
     --max-steps 150 \
     --seed 313'
```

```bash
ssh -o BatchMode=yes -o ConnectTimeout=5 badger@100.88.131.52 \
  'cd /home/badger/Desktop/dual-anchor-lifelong-objectnav && \
   source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && \
   export PYTHONPATH=src/objectnav_core HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet && \
   python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
     --output runs/habitat_official_objectnav/oracle_memory_fmm_backend_4ep_150steps_20260531_v1 \
     --policy memory_active_perception_frontier_targetnav \
     --targetnav-backend fmm_grid \
     --memory-prior-path runs/habitat_official_objectnav/oracle_memory_prior_valmini_4ep_20260531_v1/memory_prior.json \
     --max-episodes 4 \
     --max-steps 150 \
     --seed 313'
```

## Metrics

| Run | Success rate | SPL | SoftSPL | Mean distance | Notes |
|---|---:|---:|---:|---:|---|
| Export | 4 anchors | n/a | n/a | n/a | Zero skipped episodes. |
| Oracle memory + oracle backend, radius `1.0` | `0.0000` | `0.0000` | `0.6810` | `2.2272` | Oracle path activated, but follower stopped too early. |
| Oracle memory + oracle backend, radius `0.2` | `0.5000` | `0.4503` | `0.7533` | `1.5385` | Diagnostic upper-bound path is alive. |
| Oracle memory + FMM backend | `0.0000` | `0.0000` | `0.0010` | `5.8806` | Local-control/grid execution bottleneck remains. |

## Observations

- The exported prior contains four anchors tagged with
  `source_validity=oracle_diagnostic_only` and
  `metadata_source=habitat_official_oracle_memory_prior`.
- Anchors include `episode_id`, so same-scene/same-category anchors can coexist
  without the selector silently choosing the wrong memory.
- The oracle backend trace records `backend_id=pathfinder_suffix_oracle`,
  `privileged_oracle=true`, and `benchmark_valid=false`.
- The default oracle follower radius `1.0` is too loose for official success on
  this slice. Tightening to `0.2` recovers two successes.
- FMM with perfect memory still spends the budget moving, turning, or falling
  back to scan/orient behavior, confirming executor/local-map limitations.

## Result

The exporter and eval path now support an oracle-memory upper-bound diagnostic.
This does not produce a benchmark-valid result, but it gives a useful
decomposition:

- noisy YOLO memory + oracle backend failed earlier because memory quality was
  poor;
- oracle memory + oracle backend can succeed on the same official eval path;
- oracle memory + FMM still fails, so FMM is not the right executor for a
  top-tier paper story.

## Follow-up

- Improve the oracle-memory upper bound by exporting multiple candidate
  viewpoints per episode or selecting viewpoints that better satisfy official
  visibility/success constraints.
- Use oracle memory + oracle backend as the positive diagnostic ceiling, and
  YOLO/discovered memory + oracle backend as the memory-quality gap.
- Keep benchmark-facing claims on non-oracle memory priors and non-oracle
  backends only.
