# Design Doc: Localization-Only Bag Audit

Date: 2026-05-26  
Owner: Codex  
Status: Implemented

## Goal

Add a ROS-runtime-free audit tool that reads recorded XJTLU ROS 2 bags and summarizes localization health before Habitat, RGB-D, RTK, or live ObjectNav integration.

The first use is to inspect existing FAST-LIO + G60 GPS corridor bags under `/Users/badger/Desktop/my_local_data` and decide whether bad GNSS is being rejected or would contaminate long-term anchors.

## Non-Goals

- Do not evaluate ObjectNav memory success, detector reliability, depth evidence, or active verification.
- Do not require `rclpy`, `ros2 bag`, Nav2, TF2, or a sourced ROS workspace on the analysis machine.
- Do not modify, reindex, or replay bags in place.
- Do not treat G60 GPS as ground truth.
- Do not publish paper benchmark claims from this audit alone.

## Background

The current algorithm route needs real replay evidence, but the available data predates the new RGB-D and RTK setup. These bags still contain useful localization streams: `/fastlio2/lio_odom`, `/fix`, `/tf`, `/gps_corridor/*`, costmaps, plans, and velocity commands.

This makes them useful for a localization-only preflight check. The result should answer whether the bag interface is usable, whether FAST-LIO trajectories are continuous, whether G60 GPS is valid or rejected, and whether anchor-health gating should fall back to `lio_only` rather than trusting bad GNSS.

## System Boundary

The audit tool owns:

- discovery of ROS 2 SQLite bag folders
- parsing `metadata.yaml` and the SQLite `topics` / `messages` tables
- minimal CDR decoding for selected message types
- FAST-LIO trajectory continuity metrics
- NavSatFix validity and jump metrics
- local SE(2) alignment residual between valid GPS ENU samples and LIO xy samples
- CSV, JSON, and HTML report artifacts

It depends on:

- Python standard library
- `PyYAML`
- no ROS runtime packages

It does not own:

- bag recording
- XJTLU vehicle launch files
- full TF tree reconstruction
- RGB-D/depth evidence extraction
- ObjectNav belief updates

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Bag path | ROS 2 sqlite bag directory | Directory containing `metadata.yaml` and `bag_0.db3`. |
| Input | Data root | Directory | Optional scan root containing many `logs/*/bag` folders. |
| Input | Output directory | Directory | New report artifacts are written here. |
| Output | `summary.json` | JSON | Per-session metrics and aggregate counts. |
| Output | `session_metrics.csv` | CSV | One row per bag session. |
| Output | `topic_counts.csv` | CSV | Topic names, types, and message counts. |
| Output | `fix_samples.csv` | CSV | Decoded `/fix` samples with validity and local ENU coordinates. |
| Output | `lio_samples.csv` | CSV | Decoded `/fastlio2/lio_odom` samples with xy/yaw and speed. |
| Output | `audit_report.html` | HTML | Human-readable report for quick review. |

## Interfaces

CLI:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_localization_bag_audit \
  --output runs/localization_bag_audit/latest \
  --bag /Users/badger/Desktop/my_local_data/logs/2026-03-25-17-46-15/bag \
  --bag /Users/badger/Desktop/my_local_data/logs/2026-03-22-21-05-17/bag
```

Python API:

```python
from objectnav_core.evaluation.localization_bag_audit import run_localization_bag_audit

summary = run_localization_bag_audit(
    output_dir="runs/localization_bag_audit/latest",
    bag_paths=[
        "/Users/badger/Desktop/my_local_data/logs/2026-03-25-17-46-15/bag",
    ],
)
```

## Data Flow

1. Resolve explicit `--bag` paths and/or scan `--data-root` for bag folders.
2. Read `metadata.yaml` to collect duration, message count, and topic counts.
3. Open each SQLite bag read-only.
4. Decode only required topics:
   - `/fastlio2/lio_odom`
   - `/fix`
   - `/gps_corridor/enu_to_map`
   - `/gps_corridor/pgo_enu_to_map`
   - `/gps_corridor/alignment_debug`
   - `/gps_corridor/alignment_status`
5. Convert valid GPS fixes to local ENU coordinates relative to the first valid fix in the session.
6. Pair valid GPS and LIO samples by nearest timestamp.
7. Fit a 2D similarity transform from GPS ENU to LIO xy and report residuals.
8. Classify anchor health as `lio_only`, `gnss_rejected`, `weak_alignment`, `usable`, or `insufficient_lio`.
9. Write JSON, CSV, and HTML artifacts.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Bag missing metadata or SQLite file | File checks fail before parsing | Report the bag as invalid without stopping other bags. |
| CDR parser sees an unsupported message type | Topic is skipped unless required | Keep parser limited to known message schemas and add tests before expanding. |
| GPS has no valid fixes | Valid fix ratio is zero | Classify as `lio_only` or `gnss_rejected`; do not align. |
| GPS appears valid but jumps strongly | ENU speed/jump metrics exceed thresholds | Classify as `gnss_rejected` or `weak_alignment`. |
| LIO trajectory has jumps or gaps | Step, speed, and timestamp-gap metrics exceed thresholds | Mark localization health risky and record warnings. |
| Audit result gets mistaken for ObjectNav validation | Experiment report labels scope as localization-only | Use Habitat and RGB-D/real bag evidence before ObjectNav claims. |

## Verification Plan

- Write tests for minimal CDR decoding of `NavSatFix`, `Odometry`, `Float64MultiArray`, and `String`.
- Write a synthetic SQLite bag fixture test with `/fix` and `/fastlio2/lio_odom`.
- Verify the CLI writes JSON, CSV, and HTML artifacts.
- Run the focused audit tests and the full core test suite.
- Run the tool on the short best-so-far corridor bag and the long corridor stress bag from `/Users/badger/Desktop/my_local_data`.

## Research Relevance

This audit supports the paper/system story by creating a replay-first bridge before real RGB-D and RTK data are available. It can provide evidence for a conservative anchor-health policy: low-quality GNSS should be diagnosed and rejected, while FAST-LIO-only operation remains a valid fallback.

The result is not a benchmark for the proposed ObjectNav memory algorithm. It is a preflight check for real-vehicle data plumbing and anchor reliability.

## Open Questions

- Which threshold should separate `weak_alignment` from `gnss_rejected` once RTK data exists?
- Should future audits compare `/gps_corridor/pgo_enu_to_map` against the offline fitted transform?
- Should the XJTLU repo export a stable trace sidecar so the algorithm repo does not need to parse every bag directly?
