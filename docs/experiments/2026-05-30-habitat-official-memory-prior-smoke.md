# Experiment Report: Habitat Official Memory-Prior ObjectNav Smoke

Date: 2026-05-30
Owner: Codex
Status: Completed mechanism smoke, not a benchmark result

## Question

Can the official Habitat-Lab ObjectNav action loop consume a remembered object
anchor from an external memory prior, emit official discrete actions, and keep
official metrics under `habitat.Env.get_metrics()`?

## Environment

| Item | Value |
|---|---|
| Branch | `codex/habitat-memory-lifecycle` |
| Machine | `badger-linux` |
| Conda env | `habitat` |
| Habitat-Lab | `0.3.3` |
| Dataset | HM3D ObjectNav `val_mini` |
| Policy | `memory_guided_frontier` |
| Memory prior | Synthetic start anchor, not benchmark-valid |

## Command

The smoke used a one-anchor JSON prior:

```json
{
  "anchors": [
    {
      "object_category": "chair",
      "x_m": 0.0,
      "z_m": 0.0,
      "confidence": 1.0,
      "source": "synthetic_start_anchor:not_benchmark_valid"
    }
  ]
}
```

Run command:

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
/home/badger/anaconda3/bin/conda run -n habitat env \
  PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_official_objectnav_eval \
    --output runs/habitat_official_objectnav/memory_guided_frontier_synthetic_prior_1ep_20260530_v1 \
    --config-path third_party/habitat-lab/habitat-lab/habitat/config/benchmark/nav/objectnav/objectnav_hm3d.yaml \
    --dataset-data-path datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini/val_mini.json.gz \
    --scene-root datasets/habitat/scene_datasets/hm3d \
    --split val_mini \
    --policy memory_guided_frontier \
    --memory-prior-path runs/habitat_official_objectnav/memory_guided_frontier_synthetic_prior_1ep_20260530_v1/memory_prior.json \
    --memory-stop-radius-m 0.35 \
    --memory-bearing-tolerance-deg 20 \
    --memory-min-confidence 0.5 \
    --max-episodes 1 \
    --max-steps 20 \
    --validate-habitat
```

## Artifacts

- `runs/habitat_official_objectnav/memory_guided_frontier_synthetic_prior_1ep_20260530_v1/summary.json`
- `runs/habitat_official_objectnav/memory_guided_frontier_synthetic_prior_1ep_20260530_v1/episodes.csv`
- `runs/habitat_official_objectnav/memory_guided_frontier_synthetic_prior_1ep_20260530_v1/protocol_manifest.json`
- `runs/habitat_official_objectnav/memory_guided_frontier_synthetic_prior_1ep_20260530_v1/memory_prior.json`

## Result

| Episodes | Success | SPL | SoftSPL | Distance to goal | Actions |
|---:|---:|---:|---:|---:|---:|
| `1` | `0.0` | `0.0` | `0.0` | `8.412616729736328` | `1` |

The episode debug payload recorded:

- `policy_kind=memory_guided_occupancy_frontier`
- `memory_prior.decision=stop_at_memory`
- `memory_prior.selected_source=synthetic_start_anchor:not_benchmark_valid`
- `memory_prior.range_m=0.0`

The protocol manifest recorded:

- `memory_prior.anchor_count=1`
- `memory_prior.source_validity=not_benchmark_validated`
- `invalid_for_benchmark_claim_reason=memory_prior_source_not_benchmark_validated`

## Interpretation

This proves the first official-loop memory-prior plumbing works: memory enters
through an external artifact, action selection happens through the official
discrete action interface, and metrics remain Habitat-provided.

This is not a policy win. The prior was synthetic and intentionally invalid for
benchmark claims. The next meaningful experiment must generate memory priors
from a documented discovery process or detector cache, then compare against
`occupancy_frontier` under the same official protocol.
