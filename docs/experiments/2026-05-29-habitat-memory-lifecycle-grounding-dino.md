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

## Full HM3D Val Bootstrap and Detector Debug

Date: 2026-05-29
Machine: Linux `badger@100.88.131.52`, conda env `habitat`
Branch / commit: `codex/habitat-memory-lifecycle`, after `d5eab7b`

### Dataset Setup

The full HM3D `val` scene assets were unpacked into
`datasets/habitat/versioned_data/hm3d-0.2/hm3d/val`:

- `hm3d-val-habitat-v0.2.tar`
- `hm3d-val-semantic-annots-v0.2.tar`
- `hm3d-val-semantic-configs-v0.2.tar`

Post-extract audit:

- `hm3d/val` scene directories: `100` plus root directory.
- relevant scene/semantic files counted under `hm3d/val`: `272`.
- full ObjectNav `val` episodes: `2000`.
- strict lifecycle groups under default structured filters: `88` total,
  covering all six categories: `bed=17`, `chair=16`, `plant=3`, `sofa=17`,
  `toilet=21`, `tv_monitor=14`.

### Oracle Val Smoke

Run:

`runs/habitat_usability/habitat_memory_lifecycle_val_oracle_smoke`

Parameters: full HM3D `val`, six categories, one group per category, clean,
`query_repeats=2`, `oracle_bbox`.

Result:

- `memory_guided`: `12/12`, `171.492954 m`
- `naive_count`: `12/12`, `171.492954 m`
- `no_memory`: `12/12`, `424.086844 m`
- memory vs no-memory path reduction: `59.5618%`
- memory vs naive: tie, as expected when all anchors remain valid.

### Grounding-DINO Val Clean Smoke

Run:

`runs/habitat_usability/habitat_memory_lifecycle_val_grounding_dino_6cat_clean_smoke`

Parameters: full HM3D `val`, six categories, one group per category, clean,
`query_repeats=2`, Grounding-DINO tiny, detector prompt mode `target`.

Result:

- `memory_guided`: `8/12`, `292.560370 m`
- `naive_count`: `8/12`, `292.560370 m`
- `no_memory`: `8/12`, `424.086844 m`
- memory vs no-memory path reduction: `31.0140%`
- memory vs naive: tie.

Failure attribution:

- `chair`: detector produced a large overlapping box (`precision=0.73196`,
  `recall=0.366132`) but the evidence classifier rejected it as
  `fragmented_detector_mask` after the trace was extended with evidence
  reasons. This is a gate/calibration issue, not a pure detector absence.
- `tv_monitor`: Grounding-DINO produced no accepted detection at the selected
  viewpoint (`detector_pixels=0`, `oracle_target_pixels=684994`), so this is a
  detector/prompt/viewpoint failure.

### Alias Prompt Control

Run:

`runs/habitat_usability/habitat_memory_lifecycle_val_grounding_dino_6cat_alias_clean_smoke`

Parameters: same as above, but `--detector-prompt-mode target_aliases`.

Result:

- `memory_guided`: `6/12`, `398.033676 m`
- `naive_count`: `6/12`, `398.033676 m`
- `no_memory`: `6/12`, `424.086844 m`

The alias prompt did not fix `tv_monitor` and caused `sofa` to miss. Therefore
global synonym prompts are not a valid fix. The next protocol revision is to
choose memory anchors from detector-qualified discovery viewpoints instead of
blindly using the first Habitat goal viewpoint.

### Protocol Revision

The runner now records `detector_prompt_mode`, `anchor_strategy`,
`memory_anchor_source`, `memory_evidence_reason`, and
`fallback_evidence_reason`. The default anchor strategy is now
`detector_positive`: select a discovery viewpoint that actually passes
detector-backed verification before treating it as memory. This aligns the
simulation with the intended robot memory system: no object is remembered unless
the robot saw and confirmed it.

An attempted full candidate scan was interrupted after several minutes because
Grounding-DINO and connected-component mask scoring over every discovery
viewpoint was too slow for iterative smoke testing. The runner now sorts
discovery viewpoints by Habitat target pixels and verifies only the top
`--anchor-candidate-limit` candidates by default (`4`).

Metric note: `detector_miss_count` now counts misses only on the route a mode
actually attempted. A missed fallback view is not charged to `memory_guided`
when memory already succeeded and fallback was never used.

### Detector-Qualified Val Matrix V1

Run:

`runs/habitat_usability/habitat_memory_lifecycle_val_grounding_dino_detector_anchor_matrix_v1`

Parameters: full HM3D `val`, six categories, two groups per category,
`clean,mild,heavy`, `query_repeats=2`, Grounding-DINO tiny,
`--anchor-strategy detector_positive`, `--anchor-candidate-limit 4`, detector
prompt mode `target`.

Result:

- `memory_guided`: `68/72`, `974.499584 m`
- `naive_count`: `68/72`, `974.499584 m`
- `no_memory`: `62/72`, `2547.505218 m`
- memory vs no-memory path reduction: `61.7469%`
- memory vs no-memory success delta: `+6`
- memory vs naive: tie.

Interpretation:

- Detector-qualified memory gives a strong advantage over no-memory search in
  this geodesic proxy because remembered detector-confirmed viewpoints avoid
  fallback views where DINO misses `chair` and `tv_monitor`.
- The tie with `naive_count` is expected for a non-stale protocol: both modes
  are allowed to travel to the same detector-confirmed memory anchor and both
  stop when the shared current-view gate succeeds.
- This matrix supports the value of confirmed memory for repeated search, but
  it does not yet isolate the proposed stale-repair contribution over a fair
  positive-count baseline. The next experiment must add explicit stale or
  relocation lifecycle events.

Failure attribution:

- The four memory/naive failures all occur on `tv_monitor` under `mild` and
  `heavy` noise. The trace shows `missed_visible_oracle_target`: Habitat GT has
  hundreds of thousands of target pixels, but Grounding-DINO returns zero
  accepted boxes.
- Debug PNGs were exported to
  `runs/habitat_usability/habitat_memory_lifecycle_val_grounding_dino_detector_anchor_matrix_v1/debug_tv_monitor_failures/`.
  Clean `goal_viewpoint:3` is positive, but all top-4 memory candidates become
  non-confirmations under `mild` and `heavy`. This points to detector/noise
  robustness rather than missing Habitat GT.

### Synthetic Stale Relocation Protocol

After the detector-qualified stable matrix, `memory_guided` still ties
`naive_count` because no stale lifecycle event occurs. The runner now supports
`--lifecycle-challenge synthetic_stale_relocation` to isolate stale repair:

- discovery still selects a detector-confirmed memory anchor;
- at query time the old memory anchor is marked as stale;
- the first query falls back to a detector-verified current target view;
- `memory_guided` can repair the anchor and reuse the fallback anchor on the
  second repeated query;
- `naive_count` remains positive-only and does not receive repair state.

This is explicitly a synthetic lifecycle stress test, not an official Habitat
object relocation. It is the next required experiment because the stable matrix
only proves memory helps versus no-memory search, not versus a fair count-only
memory baseline.
