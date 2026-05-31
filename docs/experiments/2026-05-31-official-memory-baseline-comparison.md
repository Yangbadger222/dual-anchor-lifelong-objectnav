# Experiment Report: Official Memory Baseline Comparison Smoke

Date: 2026-05-31
Owner: Codex
Status: TargetNav-equated diagnostic complete

## Question

Can the project compare `memory_guided`, `no_memory`, and `naive_count` under
the same terminal TargetNav backend so row differences isolate memory target
selection instead of local controller behavior?

## Environment

- Machine: Linux workstation `badger@100.88.131.52`
- Repo path: `/home/badger/Desktop/dual-anchor-lifelong-objectnav`
- Python: `/home/badger/anaconda3/envs/habitat/bin/python`
- Split: HM3D ObjectNav `val_mini`
- Episode cap: `4`
- Step cap: `100`
- Detector / memory source: Grounding-DINO
  `IDEA-Research/grounding-dino-tiny` discovery priors
- Shared terminal backend: `oracle_follower`
- Metric source: Habitat-Lab `env.get_metrics()`

## Commands

Create the positive-only `naive_count` memory prior:

```bash
cd /home/badger/Desktop/dual-anchor-lifelong-objectnav
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_memory_discovery \
    --output runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_episode_ids_threshold2_4ep_100steps_20260531_v1 \
    --policy occupancy_frontier \
    --detector grounding_dino \
    --grounding-dino-max-image-side 384 \
    --min-detection-confidence 0.25 \
    --positive-count-threshold 2 \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313
```

Run the targetnav-equated comparison table:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet PYTHONPATH=src/objectnav_core \
  /home/badger/anaconda3/envs/habitat/bin/python -m \
  objectnav_core.cli.run_habitat_official_memory_comparison \
    --output runs/habitat_official_objectnav/targetnav_equated_grounding_dino_memory_comparison_4ep_100steps_20260531_v1 \
    --memory-guided-prior-path runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_episode_ids_4ep_100steps_20260531_v1/memory_prior.json \
    --naive-count-prior-path runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_episode_ids_threshold2_4ep_100steps_20260531_v1/memory_prior.json \
    --targetnav-backend oracle_follower \
    --pathfinder-suffix-goal-radius-m 0.05 \
    --max-episodes 4 \
    --max-steps 100 \
    --seed 313
```

## Artifacts

- Memory-guided prior:
  `runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_episode_ids_4ep_100steps_20260531_v1/memory_prior.json`
- Naive-count prior:
  `runs/habitat_official_objectnav/grounding_dino_discovery_prior_alias_episode_ids_threshold2_4ep_100steps_20260531_v1/memory_prior.json`
- Comparison report:
  `runs/habitat_official_objectnav/targetnav_equated_grounding_dino_memory_comparison_4ep_100steps_20260531_v1/comparison.json`
- Comparison CSV:
  `runs/habitat_official_objectnav/targetnav_equated_grounding_dino_memory_comparison_4ep_100steps_20260531_v1/comparison.csv`
- Comparison Markdown:
  `runs/habitat_official_objectnav/targetnav_equated_grounding_dino_memory_comparison_4ep_100steps_20260531_v1/comparison.md`

## Naive Prior Summary

| Metric | Value |
|---|---:|
| Episodes | 4 |
| Observations | 400 |
| Detector detections | 666 |
| Label-filtered detections | 620 |
| Exported anchors | 16 |
| Positive-count threshold | 2 |
| Positive-count-threshold filtered anchors | 1 |
| Anchor-cap filtered candidates | 30 |

The prior metadata records `positive_count_threshold=2` and uses the documented
positive-only source boundary. It is still an immediate projected-detection
memory source, not the proposed confirmed-viewpoint memory system.

## Official Metrics

| Method | Official policy | Episodes | SR | SPL | SoftSPL | DistanceToGoal | Caveat |
|---|---|---:|---:|---:|---:|---:|---|
| `memory_guided` | `memory_active_perception_frontier_targetnav` | 4 | 0.0000 | 0.0000 | 0.1914 | 5.9202 | `targetnav_oracle_backend_diagnostic` |
| `no_memory` | `no_memory_targetnav` | 4 | 0.5000 | 0.4673 | 0.4615 | 2.8931 | `targetnav_oracle_backend_diagnostic` |
| `naive_count` | `naive_count_targetnav` | 4 | 0.0000 | 0.0000 | 0.1914 | 5.9202 | `targetnav_oracle_backend_diagnostic` |

Comparison deltas:

| Delta | Value |
|---|---:|
| `memory_guided` vs `no_memory` SR | -0.5000 |
| `memory_guided` vs `no_memory` SPL | -0.4673 |
| `memory_guided` vs `no_memory` SoftSPL | -0.2701 |
| `memory_guided` vs `no_memory` distance reduction | -3.0272 m |
| `memory_guided` vs `naive_count` SR | 0.0000 |
| `memory_guided` vs `naive_count` SPL | 0.0000 |
| `memory_guided` vs `naive_count` SoftSPL | 0.0000 |
| `memory_guided` vs `naive_count` distance reduction | 0.0000 m |

## Interpretation

This run is a clean negative diagnostic. All three rows share the same
`oracle_follower` terminal backend, so the performance gap is not a low-level
controller difference. The detector-triggered `no_memory_targetnav` row solves
`2/4` episodes, while both memory rows fail `0/4` and finish farther from the
goal.

That result strengthens the current research pivot: the system should not chase
terminal-controller tuning as the contribution. The bottleneck is memory target
quality: immediate projected DINO anchors are not reliable enough lifelong
targets, and the next method should write or select confirmed viewpoints that
are useful for reacquisition.

## Verification

Implementation verification completed before the smoke:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_memory_comparison.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

Result: `118 passed` locally and `118 passed` in the Linux `habitat` conda env.
Local and Linux `compileall` checks over the touched evaluator/comparison/CLI
modules were clean.

Current artifact verification:

- Read remote
  `runs/habitat_official_objectnav/targetnav_equated_grounding_dino_memory_comparison_4ep_100steps_20260531_v1/comparison.json`.
- Confirmed all rows report `metric_source=habitat.Env.get_metrics`.
- Compared the JSON metrics with the generated `comparison.md` table.

## Risks and Follow-up

- The comparison is only four `val_mini` episodes, so it is a diagnostic smoke,
  not a publishable performance table.
- All rows use the privileged `oracle_follower` backend and carry
  `targetnav_oracle_backend_diagnostic`.
- The memory rows are worse than the no-memory row in this smoke. Treat this as
  evidence that current memory writes are harmful, not as evidence against
  lifelong memory as the paper direction.
- The next useful step is a better memory write/selection policy based on
  detector-confirmed viewpoints or active perception, then rerun this same
  targetnav-equated comparison before scaling.
