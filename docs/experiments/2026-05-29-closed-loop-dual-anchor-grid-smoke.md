# Experiment Report: Closed-Loop Dual-Anchor Grid Smoke

Date: 2026-05-29  
Owner: Codex  
Status: Running

## Question

Can the simulator exercise the real paper mechanics before Habitat integration:
closed-loop memory-vs-frontier decisions, multi-session frame restart,
Mahalanobis ambiguity rejection, and natural stale repair?

## Hypothesis

In a deterministic multi-room grid, memory-guided should reuse an accepted
cross-session memory, defer to frontier under ambiguous same-class matching, and
repair a stale memory when the old object is absent and a replacement object is
found.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / local closed-loop grid changes |
| Machine | macOS local workstation |
| Dataset / bag / map | Deterministic `make_default_multiroom_lifelong_scene` grid |
| Simulator / robot | Grid A* option-level loop, not Habitat |
| Key parameters | gate threshold `5.991`, ambiguity margin `0.5`, frame transform `dx=0.2`, `dy=-0.15` |

## Command

```bash
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_closed_loop_dual_anchor_benchmark \
  --output /tmp/closed_loop_dual_anchor_grid_smoke
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Policies | 3 | `memory_guided`, `frontier_only`, `naive_count` |
| Episodes per policy | 4 | discover, reuse, ambiguity, stale repair |
| Memory-guided success | 4/4 | Grid/config-truth smoke |
| Frontier-only success | 4/4 | Same smoke |
| Naive-count success | 4/4 | Same smoke |
| Memory-guided total path | `67.210933 m` | Includes discover and session-2 rows |
| Frontier-only total path | `81.389524 m` | Memory path reduction `17.4207%` |
| Naive-count total path | `67.210933 m` | Ties memory-guided after shared gate |
| Memory-guided stale repairs | 1 | Old memory fails, replacement `plant_002` verified |

## Observations

- `session_2_reuse`: memory-guided selects `memory`, records
  `matching_reason=accepted`, and verifies `plant_001`.
- `session_2_ambiguous`: memory-guided and naive-count both select `frontier`
  because the shared dual-anchor gate records `matching_reason=ambiguous`.
- `session_2_stale_repair`: memory-guided first selects `memory`, observes no
  current object at the old pose, then explores and verifies moved object
  `plant_002`.
- The non-identity frame transform is recorded on session-2 rows:
  `dx=0.2`, `dy=-0.15`, `dyaw=0.0`, covariance diagonal `0.05`.

## Result

The harness now measures the right mechanics at option-level grid resolution.
It does **not** yet show our method beating `naive_count`; with the fair shared
decision gate, the two tie in this small deterministic slice. That is a useful
negative/neutral result: the simulator is stricter now, and the next work must
create harder Habitat scenarios where uncertainty propagation and stale-memory
repair matter beyond a positive counter.

## Follow-up

- Verify this harness on Linux after commit/push.
- Port the same schema into Habitat with real action loops, Grounding-DINO
  observations, and object relocation/removal.
- Add pressure cases where covariance calibration and multi-instance ambiguity
  affect long-horizon exploration cost, not just a single option choice.
