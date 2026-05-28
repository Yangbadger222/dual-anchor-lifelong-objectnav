# Experiment Report: Habitat Memory-Lifecycle Grounding-DINO

Date: 2026-05-29  
Owner: Codex  
Status: Completed geodesic lifecycle matrix

## Question

Can a Habitat-backed lifecycle protocol show that object memory reduces later
ObjectNav query cost, and does stale-memory repair improve over a positive-only
`naive_count` baseline when the same detector evidence is shared across modes?

## Hypothesis

Memory should beat `no_memory` because remembered verification poses avoid
search-proxy fallback. It should only beat `naive_count` when an old memory
anchor fails and later queries benefit from repair; a single valid memory query
should tie positive-only counting.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle`, `411ff49` |
| Machine | `badger-linux` |
| Python / env | `conda habitat`, Python `3.9` |
| Dataset | HM3D ObjectNav `val_mini` |
| Simulator | Habitat-Sim / Habitat-Lab in existing `habitat` env |
| Detector | Grounding-DINO `IDEA-Research/grounding-dino-tiny` |
| Resolution | Habitat render `1280x720`, DINO cap `384` |
| Noise | `clean,mild,heavy` RGB/depth profiles |
| Modes | `memory_guided,no_memory,naive_count` |
| Query repeats | `2` |
| Fallback | `search_proxy` with `3` random navigable waypoints |

## Commands

Focused Linux tests:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core \
  python -m pytest \
  src/objectnav_core/tests/test_habitat_memory_lifecycle_objectnav.py \
  src/objectnav_core/tests/test_cli_runner.py -q
```

Main repeated-query matrix:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
rm -rf runs/habitat_usability/habitat_memory_lifecycle_grounding_dino_repeated_v2_allcat
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_habitat_memory_lifecycle_objectnav \
  --output runs/habitat_usability/habitat_memory_lifecycle_grounding_dino_repeated_v2_allcat \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --rgb-noise-profile configs/noise/rgb_published_v1.yaml \
  --depth-noise-profile configs/noise/depth_realsense_d435_v1.yaml \
  --noise-levels clean,mild,heavy \
  --detector grounding_dino \
  --detector-weights IDEA-Research/grounding-dino-tiny \
  --detector-conf 0.25 \
  --grounding-dino-text-threshold 0.25 \
  --grounding-dino-max-image-side 384 \
  --modes memory_guided,no_memory,naive_count \
  --target-categories bed,chair,plant,sofa,toilet,tv_monitor \
  --episodes-per-category 2 \
  --max-groups 8 \
  --sensor-width 1280 \
  --sensor-height 720 \
  --search-proxy-waypoints 3 \
  --query-repeats 2 \
  --seed 313
```

## Metrics

### Main Matrix

Output:

`runs/habitat_usability/habitat_memory_lifecycle_grounding_dino_repeated_v2_allcat`

| Metric | memory_guided | naive_count | no_memory |
|---|---:|---:|---:|
| Episodes | `18` | `18` | `18` |
| Success episodes | `18` | `18` | `16` |
| Total path length | `302.429085 m` | `335.562126 m` | `380.772042 m` |
| Mean path length | `16.801616 m` | `18.642340 m` | `21.154002 m` |
| Memory reuse episodes | `16` | `14` | `0` |
| Fallback count | `2` | `4` | `18` |
| Stale check count | `2` | `0` | `0` |
| Detector miss count | `2` | `2` | `2` |

Derived comparison:

| Comparison | Value |
|---|---:|
| memory vs naive path delta | `33.133041 m` |
| memory vs naive reduction | `9.8739%` |
| memory vs naive success delta | `0` |
| memory vs no-memory path delta | `78.342957 m` |
| memory vs no-memory reduction | `20.5748%` |
| memory vs no-memory success delta | `+2` |

Episode selection:

| Metric | Value |
|---|---:|
| Candidate episodes | `12` |
| Selected lifecycle groups | `3` |
| Selected categories | `chair=1`, `plant=1`, `toilet=1` |
| Selected query episode IDs | `84`, `55`, `47` |

### Mechanism Rows

The clearest stale-repair behavior appears in `plant` under `heavy` noise:

| Mode | Repeat | Route | Path | Memory evidence | Fallback evidence |
|---|---:|---|---:|---|---|
| `memory_guided` | `0` | `memory|fallback` | `44.352586 m` | `non_confirmation`, `0` detector pixels | `positive`, `63139` pixels |
| `memory_guided` | `1` | `memory` | `19.153874 m` | repaired positive, `63139` pixels | `positive`, `63139` pixels |
| `naive_count` | `0` | `memory|fallback` | `44.352586 m` | `non_confirmation`, `0` pixels | `positive`, `63139` pixels |
| `naive_count` | `1` | `memory|fallback` | `44.352586 m` | still old non-confirming anchor | `positive`, `63139` pixels |

The same pattern appears for `chair` under `mild` noise. This is the first
Habitat-backed evidence that stale repair, not merely memory existence, creates
an advantage over positive-only counting.

### Control Matrix

A shared-evidence single-query matrix was also run:

`runs/habitat_usability/habitat_memory_lifecycle_grounding_dino_matrix_v2_shared`

Result:

- `memory_guided`: `6/6`, `136.043747 m`
- `naive_count`: `6/6`, `136.043747 m`
- `no_memory`: `6/6`, `166.583034 m`
- memory vs no-memory path reduction: `18.3328%`
- memory vs naive: exact tie

This control is important: when the memory anchor remains valid, our method
does not beat a fair positive-only baseline. The advantage appears only when a
stale anchor is repaired and reused on later queries.

## Coverage Audit

HM3D `val_mini` has all six ObjectNav categories:

| Category | Episode count |
|---|---:|
| `bed` | `7` |
| `chair` | `7` |
| `plant` | `5` |
| `sofa` | `3` |
| `toilet` | `5` |
| `tv_monitor` | `3` |

However, the lifecycle protocol requires at least two episodes sharing the same
scene, category, and `closest_goal_object_id`. Under that stricter instance
pairing, `val_mini` yields only three groups: `chair`, `plant`, and `toilet`.
Relaxing structured filters did not add more groups. To make a paper-grade
claim, the next run must use a larger split or a carefully justified
category-level pairing strategy.

## Observations

- The protocol now avoids two earlier fairness bugs:
  - `no_memory` no longer gets the oracle target shortest path as hidden prior;
    it pays a search-proxy route and stores the oracle shortest path only as a
    lower-bound field.
  - all modes share the same detector evidence for each group/noise cell.
- `memory_guided` beats `no_memory` in both path and success on the repeated
  lifecycle matrix.
- `memory_guided` beats `naive_count` only after repeated stale repair. This is
  the right research direction, but the current margin is modest and the sample
  is small.
- `naive_count` remains fair and simple: it only counts positives, does not use
  non-confirmation, and does not receive repaired anchors.
- The result is not official SPL. The current runner teleports to measured
  verification views and uses geodesic path accounting.

## Result

The current Habitat result is a useful research milestone, not a final paper
claim.

Supported now:

1. Lifelong memory can reduce repeated ObjectNav search cost versus no memory
   under Grounding-DINO and RGB/depth noise.
2. Stale repair can produce a measurable advantage over positive-only counting
   across repeated queries.
3. The current evidence is still too small and too proxy-based for a top-tier
   robotics claim.

## Follow-up

- Scale to a larger HM3D split so all six categories can form lifecycle groups.
- Add explicit removal/relocation lifecycle episodes instead of relying on
  detector misses at old anchors.
- Replace teleport-to-viewpoint evaluation with an action-level Habitat
  follower and report SPL-like metrics.
- Add baselines: category-level memory, semantic map memory, learned utility,
  and frontier/search policies with no oracle goal.
- Keep `naive_count` positive-only; do not grant it stale repair or
  non-confirmation.
