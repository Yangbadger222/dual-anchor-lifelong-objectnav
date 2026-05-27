# Experiment Report: Habitat Usability Replay

Date: 2026-05-27  
Owner: Codex  
Status: Completed

## Question

Can the current usability-memory algorithm run on multi-episode Habitat traces, and does it make qualitatively sensible decisions when evidence alternates between confirmation, local non-confirmation, access-blocked events, and far random anchors?

## Hypothesis

If the Habitat trace adapter is usable, then real Habitat RGB-D/navmesh/collision rows should replay through `UsabilityUpdater` and `UsabilityDecisionPolicy` without requiring Habitat as a core import dependency. Confirmed near anchors should end with higher `p_valid`; random or repeatedly blocked anchors should end with lower `p_valid` and more `SEARCH`/`RETIRE` decisions.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, `db13f53`, dirty worktree |
| Machine | `badger-linux`, Ubuntu Linux 6.8.0-111-generic, NVIDIA RTX 4070 Laptop GPU |
| Dataset / scene | HM3D example scenes `CFVBbU9Rsyb`, `NBg5UqG3di3`, `GLAQ4DNUx5U`; official HM3D ObjectNav v1 episodes downloaded but official HM3D v0.1 val scenes missing |
| Simulator / robot | Habitat-Lab 0.3.3 + Habitat-Sim 0.3.3, no robot |
| Python / env | conda env `habitat`, Python 3.9.23 |
| Key parameters | 30 episodes, seed `101`, sensor size `96`, positive radius `1.25`, free radius `2.5` |

## Command

Official HM3D ObjectNav episode archive:

```bash
curl -L --fail --retry 3 --retry-delay 5 -C - \
  -o datasets/habitat/downloads/objectnav_hm3d_v1.zip \
  https://dl.fbaipublicfiles.com/habitat/data/datasets/objectnav/hm3d/v1/objectnav_hm3d_v1.zip
mkdir -p datasets/habitat/datasets/objectnav/hm3d
unzip -q -o datasets/habitat/downloads/objectnav_hm3d_v1.zip \
  -d datasets/habitat/datasets/objectnav/hm3d
ln -sfn objectnav_hm3d_v1 datasets/habitat/datasets/objectnav/hm3d/v1
```

Official HM3D scene attempt:

```bash
conda run -n habitat python -m habitat_sim.utils.datasets_download \
  --uids hm3d_minival_v0.1 \
  --data-path datasets/habitat/ \
  --no-replace
```

This failed because the downloader requires a Matterport/HM3D username.

Multi-episode replay:

```bash
conda run -n habitat env PYTHONPATH=src/objectnav_core \
  python -m objectnav_core.cli.run_habitat_usability_replay \
  --scene datasets/habitat/scene_datasets/hm3d/example/00337-CFVBbU9Rsyb/CFVBbU9Rsyb.basis.glb \
  --scene datasets/habitat/scene_datasets/hm3d/example/00770-NBg5UqG3di3/NBg5UqG3di3.basis.glb \
  --scene datasets/habitat/scene_datasets/hm3d/example/00861-GLAQ4DNUx5U/GLAQ4DNUx5U.basis.glb \
  --scene-dataset-config datasets/habitat/scene_datasets/hm3d/example/hm3d_annotated_basis.scene_dataset_config.json \
  --output runs/habitat_usability/hm3d_usability_replay_30ep \
  --episodes 30 \
  --seed 101 \
  --sensor-size 96
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Official HM3D ObjectNav `val_mini` episodes | 30 | 2 unique official HM3D v0.1 val scenes; local scene assets missing |
| Official HM3D ObjectNav `val` episodes | 2000 | 20 unique official HM3D v0.1 val scenes; local scene assets missing |
| Replay episodes completed | 30 | Synthetic ObjectNav-v1 episodes on HM3D example scenes |
| Replay trace rows | 210 | 7 rows per episode including reset and stop |
| Positive evidence rows | 62 | Distance-based confirmation proxy |
| Free evidence rows | 27 | Local searched-space proxy |
| Non-confirmation rows | 44 | Far or no-progress proxy |
| Access-blocked rows | 47 | Habitat collision proxy |
| Unknown rows | 30 | Reset observations |
| Decision counts | `VERIFY=128`, `TRUST=26`, `SEARCH=27`, `RETIRE=29` | Policy output after each evidence update |
| Near-anchor mean final `p_valid` | 0.814795 | 10 episodes |
| Local-verify mean final `p_valid` | 0.303595 | 10 episodes |
| Random-anchor mean final `p_valid` | 0.113509 | 10 episodes |
| Overall mean final `p_valid` | 0.410633 | Across 30 episodes |

## Observations

- The official HM3D ObjectNav episode archive is available and was downloaded, but the scenes it references are not locally present.
- `hm3d_minival_v0.1` scene download is not anonymous; Habitat-Sim requires a username argument for that dataset.
- The replay runner kept Habitat imports optional: unit tests import the module without importing `habitat` or `habitat_sim`.
- The 30-episode replay produced all expected artifacts: aggregate Habitat trace, usability replay CSV, JSON summary, HTML report, per-episode smoke artifacts, and command log.
- The policy behaves conservatively: `VERIFY` dominates, confirmed near anchors produce high final validity, and random anchors remain low.
- The HM3D example subset emits many missing-glob warnings because its scene-dataset config references full HM3D splits not present locally.

## Result

The algorithm is usable as an offline Habitat trace consumer: it can ingest multi-episode Habitat RGB-D/navmesh/collision traces, convert them into evidence events, update memory belief, and emit policy decisions.

The result is positive for integration and decision behavior, but it is not yet a benchmark claim. It does not include detector output, semantic visibility, success/SPL, official HM3D scenes, or official ObjectNav measurements.

## Follow-up

- Provide Matterport/HM3D credentials or pre-downloaded HM3D v0.1 val/minival scene assets.
- Run official HM3D ObjectNav `val_mini` with measurements enabled once scenes are available.
- Add semantic/object visibility evidence instead of distance-only proxies.
- Add a detector replay path after oracle/proxy evidence is stable.
