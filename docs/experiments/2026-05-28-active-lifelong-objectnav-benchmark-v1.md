# Experiment Report: Active Lifelong ObjectNav Benchmark V1

Date: 2026-05-28  
Owner: Codex  
Status: Synthetic Offline Result

## Goal

Create the first active benchmark artifact for the project direction: ObjectNav
with reusable object memory across discovery, later query, and stale-memory
repair.

## Environment

- Machine: macOS local workspace
- Code branch: `main`
- Runtime: `PYTHONPATH=src/objectnav_core python3`
- Detector: config-truth synthetic observations
- Simulator: ROS-free deterministic multi-room / corridor grid

## Command

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_lifelong_objectnav_benchmark \
  --output runs/lifelong_objectnav/active_memory_guided_benchmark_v1
```

## Artifacts

- `runs/lifelong_objectnav/active_memory_guided_benchmark_v1/summary.json`
- `runs/lifelong_objectnav/active_memory_guided_benchmark_v1/report.html`
- `runs/lifelong_objectnav/active_memory_guided_benchmark_v1/memory_guided/memory.sqlite`
- `runs/lifelong_objectnav/active_memory_guided_benchmark_v1/memory_guided/events.csv`
- `runs/lifelong_objectnav/active_memory_guided_benchmark_v1/frontier_only/memory.sqlite`
- `runs/lifelong_objectnav/active_memory_guided_benchmark_v1/frontier_only/events.csv`

## Protocol

The benchmark runs three episodes per policy:

1. `discover`: no reusable memory; explore until the object is observed and
   verified.
2. `reuse_different_start`: query the same object class from a different start.
3. `stale_repair`: move the object nearby, verify that the old memory is stale,
   search, and bind the new instance as a relocation.

Policies:

- `memory_guided`: scores reusable object memory against frontier search.
- `frontier_only`: ignores persisted object memory and searches from scratch.

## Result

| Metric | memory_guided | frontier_only |
|---|---:|---:|
| Success episodes | 3 / 3 | 2 / 3 |
| Total path length | 64.651365 m | 127.497071 m |
| Total nav goals | 22 | 78 |
| Frontier selections | 18 | 76 |
| Memory reuse episodes | 2 | 0 |
| Relocation recorded | true | false |
| Mean repeated exploration ratio | 0.533333 | 0.965432 |

Derived comparison:

- Path reduction: `62.845706 m`
- Path reduction ratio: `0.492919`
- Frontier-selection reduction: `58`
- Success delta: `+1`

## Interpretation

This is the first local active result that supports the intended paper story:
memory can reduce repeated exploration and can trigger stale-memory repair.

It is not a Habitat or robot result. The detector is synthetic, the navigation
backend is A*, and the scene is a designed fixture. The result should be used
as an engineering milestone and as the protocol template for the next Habitat
closed-loop run, not as a publication claim by itself.

## Risks

- `frontier_only` fails the stale-repair episode in this fixture, so the current
  comparison mixes path-efficiency improvement with success-rate improvement.
- The frontier baseline is simple; a stronger frontier / room-search policy may
  reduce the gap.
- The memory policy uses a hand-authored utility score in v1. This must evolve
  into uncertainty-aware instance memory and expected information gain before a
  top-tier paper claim.
- The fixture uses config-truth observations instead of Grounding-DINO.

## Next Step

Port this active protocol to Habitat with Grounding-DINO, RGB/depth noise, and
an action-level or geodesic follower. The next key metric is not replay trust
rows; it is path length, search effort, success, and stale-memory repair across
long-range ObjectNav episodes.
