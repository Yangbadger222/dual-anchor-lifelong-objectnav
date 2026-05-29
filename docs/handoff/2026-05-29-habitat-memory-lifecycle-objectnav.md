# Handoff: Habitat Memory-Lifecycle ObjectNav

Date: 2026-05-29  
Owner: Codex  
Status: In Progress - Full Val Enabled, Detector-Qualified Anchor Follow-up Pending

## Current State

Branch `codex/habitat-memory-lifecycle` contains a Habitat-backed geodesic
lifecycle protocol for ObjectNav memory.

Full HM3D `val` scene assets have now been unpacked on the Linux machine under
`datasets/habitat/versioned_data/hm3d-0.2/hm3d/val`. Full `val` lifecycle group
coverage is available: `88` strict same-instance groups across all six target
categories.

The strongest completed run is:

`runs/habitat_usability/habitat_memory_lifecycle_grounding_dino_repeated_v2_allcat`

Headline:

- `memory_guided`: `18/18`, `302.429085 m`
- `naive_count`: `18/18`, `335.562126 m`
- `no_memory`: `16/18`, `380.772042 m`
- memory vs naive path reduction: `9.8739%`
- memory vs no-memory path reduction: `20.5748%`

This is not official Habitat SPL. It is a geodesic lifecycle proxy with
teleport-to-verification views.

New full-val sanity results:

- Oracle clean six-category smoke:
  `runs/habitat_usability/habitat_memory_lifecycle_val_oracle_smoke`
  produced `12/12` success for all modes; memory path reduction vs no-memory
  was `59.5618%`.
- Grounding-DINO clean six-category smoke:
  `runs/habitat_usability/habitat_memory_lifecycle_val_grounding_dino_6cat_clean_smoke`
  produced `8/12` success. Failures were `chair` gate rejection and
  `tv_monitor` detector miss.
- Global `target_aliases` prompt control worsened to `6/12`, so do not use it
  as a blanket fix.

## Files Touched

- `docs/design/2026-05-28-habitat-memory-lifecycle-objectnav.md`
- `docs/superpowers/plans/2026-05-28-habitat-memory-lifecycle-objectnav.md`
- `docs/experiments/2026-05-29-habitat-memory-lifecycle-grounding-dino.md`
- `docs/handoff/2026-05-29-habitat-memory-lifecycle-objectnav.md`
- `docs/devlog/2026-05.md`
- `src/objectnav_core/objectnav_core/evaluation/habitat_memory_lifecycle_objectnav.py`
- `src/objectnav_core/objectnav_core/cli/run_habitat_memory_lifecycle_objectnav.py`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/tests/test_habitat_memory_lifecycle_objectnav.py`
- `src/objectnav_core/tests/test_cli_runner.py`

Recent code also adds:

- `--detector-prompt-mode`
- `--anchor-strategy`
- trace fields for `memory_anchor_source` and evidence reasons

## Commands Run

Local verification:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_habitat_memory_lifecycle_objectnav.py src/objectnav_core/tests/test_cli_runner.py -q
python3 -m compileall -q src/objectnav_core/objectnav_core src/objectnav_core/tests
git diff --check
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests -q
```

Linux focused verification:

```bash
cd ~/Desktop/dual-anchor-lifelong-objectnav
source ~/anaconda3/etc/profile.d/conda.sh
conda activate habitat
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_memory_lifecycle_objectnav.py src/objectnav_core/tests/test_cli_runner.py -q
```

Main Linux experiment:

```bash
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

## Verification

Passed locally:

- Focused lifecycle/CLI tests: `12` passed.
- Full core tests: `159` passed.
- Compileall and `git diff --check`.

Passed on Linux:

- Focused lifecycle/CLI tests: `12` passed.
- Oracle lifecycle smoke.
- Grounding-DINO clean smoke.
- Grounding-DINO shared-evidence single-query matrix.
- Grounding-DINO repeated-query matrix.

## Known Risks

- Current evaluation is geodesic and teleport-to-viewpoint based, not an
  action-level ObjectNav benchmark.
- `search_proxy` is a deterministic proxy for no-memory search cost, not a
  learned or frontier closed-loop policy.
- `val_mini` only forms three strict same-instance lifecycle groups:
  `chair`, `plant`, and `toilet`; full `val` now solves coverage but is more
  detector-sensitive.
- The memory-vs-naive advantage is modest (`9.8739%` path reduction) and appears
  only in repeated stale-repair cells.
- The detector can still dominate outcomes. Grounding-DINO is adequate for the
  selected groups, but larger splits may expose new category failures.
- Grounding-DINO full-val clean smoke exposed `chair` gate calibration and
  `tv_monitor` viewpoint/prompt failures. The next run should use the new
  `detector_positive` anchor strategy, then export PNGs for remaining failures.

## Next Recommended Step

1. Pull the latest branch on Linux and run the full-val six-category clean
   Grounding-DINO smoke with `--anchor-strategy detector_positive` and default
   `--detector-prompt-mode target`.
2. Inspect `summary.json["episode_selection"]` and trace rows for remaining
   failures, especially `chair` and `tv_monitor`.
3. Export PNGs for failed detector-qualified anchors before tuning thresholds.
4. Add explicit object removal/relocation lifecycle scenarios instead of only
   relying on detector misses at stale anchors.
5. Replace teleport-to-viewpoint with an action-level Habitat follower and
   report SPL-like metrics.
6. Only after those pass, compare against stronger semantic-map and frontier
   baselines.

## Context for Next Contributor

Do not claim this is top-tier-ready yet. The important result is narrower:
stale-repair memory has now produced a Habitat-backed measurable advantage over
a fair positive-only baseline, but the sample size and protocol are still too
small for a paper claim.
