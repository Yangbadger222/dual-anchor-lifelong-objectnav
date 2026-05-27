# Experiment Report: Habitat ObjectNav Val-Mini Semantic Stress

Date: 2026-05-27
Owner: Codex
Status: Completed

## Question

Can the usability-memory semantic stress runner consume official HM3D ObjectNav
`val_mini` episode metadata, load the corresponding local HM3D scenes, extract
target-category semantic masks, corrupt them with the YOLO-breaker, and export a
trace for memory-policy analysis?

## Hypothesis

Clean masks from official ObjectNav target categories should produce high final
memory validity. Miss corruption should produce the largest validity drop through
missed visible targets. Fly-point and edge-break corruption should mostly be
downgraded to `UNKNOWN` by mask-quality gates. Mixed corruption may still create
single-frame false-positive confirmations.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `db13f53`, dirty worktree |
| Machine | `badger-linux`, Ubuntu Linux 6.8.0-111-generic, NVIDIA RTX 4070 Laptop GPU |
| Dataset / scene | HM3D ObjectNav `objectnav_hm3d_v1/val_mini`; local HM3D scenes `00800-TEEsavR23oF` and `00802-wcojb4TFT35` |
| Simulator / robot | Habitat-Sim 0.3.3 direct RGB-D-semantic sensors, no robot |
| Python / env | conda env `habitat`, Python 3.9.23 |
| Key parameters | 30 episodes, 7 rows per episode, seed `313`, sensor size `96`, start source `goal_viewpoint`, breaker modes `clean, miss, fly_point, edge_break, mixed` |

## Command

```bash
HABITAT_SIM_LOG=quiet MAGNUM_LOG=quiet \
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_objectnav_valmini_semantic_stress \
  --dataset-dir datasets/habitat/datasets/objectnav/hm3d/objectnav_hm3d_v1/val_mini \
  --scene-root datasets/habitat/scene_datasets/hm3d \
  --output runs/habitat_usability/hm3d_valmini_semantic_stress_30ep \
  --max-episodes 30 \
  --start-source goal_viewpoint \
  --seed 313 \
  --sensor-size 96
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Episodes completed | 30 | 15 each from `TEEsavR23oF` and `wcojb4TFT35` |
| Trace rows | 210 | reset + 6 scripted actions per episode |
| Target-visible episodes | 27 | Goal viewpoints make most targets visible but not all scripted rows keep them visible |
| Target-visible rows | 174 | Out of 210 rows |
| Scene semantic objects / categories | `661 / 130`, `1059 / 206` | From Habitat semantic scene metadata |
| Evidence counts | `POSITIVE=58`, `NON_CONFIRMATION=9`, `UNKNOWN=143` | No collision/access-blocked rows in this run |
| Decision counts | `VERIFY=175`, `TRUST=35` | No search/retire rows |
| Mean final `p_valid` | 0.757149 | Across all 30 episodes |
| Clean mean final `p_valid` | 0.970945 | 6 episodes |
| Miss mean final `p_valid` | 0.569045 | 11 missed-visible-target rows |
| Fly-point mean final `p_valid` | 0.780606 | Fragmentation mostly became `UNKNOWN` |
| Edge-break mean final `p_valid` | 0.721548 | Only 3 positive rows survived |
| Mixed mean final `p_valid` | 0.743600 | 4 false-positive-positive rows |
| False-positive-positive rows | 4 | Positive evidence with detector precision below 0.25 |
| Missed visible target rows | 11 | Oracle target visible but corrupted detector mask below threshold |

## Category Notes

| Category | Episodes | Target-visible rows | Mean final `p_valid` | Notes |
|---|---:|---:|---:|---|
| `bed` | 7 | 49 | 0.747451 | 2 missed-visible rows |
| `chair` | 7 | 16 | 0.739271 | 4 false-positive-positive rows, weaker visibility |
| `plant` | 5 | 35 | 0.681803 | 3 missed-visible rows |
| `sofa` | 3 | 21 | 0.701710 | Mostly `UNKNOWN`, only 1 positive row |
| `toilet` | 5 | 35 | 0.781403 | 4 missed-visible rows |
| `tv_monitor` | 3 | 18 | 0.962082 | Strongest category in this run |

## Observations

- The runner consumed official `val_mini/content/*.json.gz` episode files and
  resolved `hm3d/val/...` scene ids to the local `hm3d/habitat/...` asset layout
  without rewriting downloaded datasets.
- A run-local scene dataset config was generated under
  `runs/habitat_usability/hm3d_valmini_semantic_stress_30ep/`.
- Both local scenes loaded navmeshes and semantic metadata.
- `goal_viewpoint` starts were used to pressure the semantic memory layer rather
  than evaluate long-horizon navigation from official episode starts.
- Clean masks produced high validity. Miss corruption caused the clearest
  validity collapse. Mixed corruption still produced 4 low-precision positive
  rows, so the single-frame false-positive weakness remains.

## Result

The repository now has a reproducible official-episode semantic stress path. It
uses official HM3D ObjectNav `val_mini` scene/category/goal-viewpoint metadata,
local HM3D semantic assets, YOLO-breaker corruptions, and the usability-memory
policy in one command.

The memory system again looks reasonably robust to fragmented fly-point and
edge-break artifacts, but it is still vulnerable to plausible low-precision
positive masks that survive quality gates. Missed visible targets correctly
lower validity and keep the policy in `VERIFY`, but did not trigger retirement
in this run.

This is not an official ObjectNav benchmark result: no learned navigation policy
was run, no real YOLO model was run, and no success/SPL metric is reported.

## Follow-up Result

The requested temporal/multi-view confirmation gate and `episode_start` pass
were completed in
[`2026-05-27-habitat-valmini-episode-start-confirmation.md`](2026-05-27-habitat-valmini-episode-start-confirmation.md).
That run reduced false-positive-positive rows from `4` to `0` under the
goal-viewpoint setup, and found that official episode starts made the target
visible in only `6 / 30` episodes and `27 / 210` scripted rows.

## Follow-up

- Tune temporal/multi-view/mask-consistency confirmation so it is less
  conservative on clean repeated target views.
- Add optional debug PNG export for low-precision mixed positives and missed
  visible targets.
- Replace corrupted oracle masks with real detector masks once the memory
  acceptance rule is stricter.
