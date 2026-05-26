# Experiment Report: Localization-Only Bag Audit

Date: 2026-05-26  
Owner: Codex  
Status: Completed

## Question

Can the existing XJTLU FAST-LIO + G60 GPS bags be used before Habitat and RGB-D replay to validate the localization replay interface and diagnose whether GNSS should be trusted as a long-term anchor?

## Hypothesis

The bags should be useful for replay plumbing and anchor-health diagnostics, but G60 GPS should often be classified as `weak_alignment`, `gnss_rejected`, or `lio_only` rather than accepted as a reliable global anchor.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, base commit `e828e1f`, with uncommitted implementation changes |
| Machine | macOS Darwin arm64 |
| Dataset / bag / map | `/Users/badger/Desktop/my_local_data/logs` |
| Simulator / robot | XJTLU recorded ROS 2 bags from G60/FAST-LIO corridor sessions |
| Key parameters | explicit two-bag audit plus full 90-session data-root audit |
| Python | `Python 3.13.12` |

## Command

Focused two-bag audit:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_localization_bag_audit \
  --output runs/localization_bag_audit/latest \
  --bag /Users/badger/Desktop/my_local_data/logs/2026-03-25-17-46-15/bag \
  --bag /Users/badger/Desktop/my_local_data/logs/2026-03-22-21-05-17/bag
```

Full data-root audit:

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_localization_bag_audit \
  --output runs/localization_bag_audit/all_sessions \
  --data-root /Users/badger/Desktop/my_local_data/logs
```

## Metrics

Focused audit:

| Metric | `2026-03-25-17-46-15` | `2026-03-22-21-05-17` | Notes |
|---|---:|---:|---|
| Anchor health | `gnss_rejected` | `weak_alignment` | Neither should be treated as a strong GNSS anchor. |
| Duration | 285.88 s | 2171.59 s | Short best-so-far bag and long stress bag. |
| FAST-LIO samples | 2851 | 3373 | Long bag contains a large LIO timestamp gap. |
| FAST-LIO path length | 265.32 m | 123.76 m | Step-derived path length, not ground truth. |
| `/fix` samples | 286 | 2171 | GPS stream is present. |
| `/fix` valid ratio | 1.000 | 1.000 | Valid status alone is not enough. |
| GPS-LIO pair count | 284 | 335 | Nearest-time pairs within 0.5 s. |
| GPS-LIO RMS residual | 15.94 m | 3.80 m | Short bag rejected; long bag marginal. |
| GPS-LIO p95 residual | 15.62 m | 7.75 m | Long bag still too weak for confident anchoring. |

Full 90-session audit:

| Anchor health | Count |
|---|---:|
| `weak_alignment` | 46 |
| `gnss_rejected` | 17 |
| `lio_only` | 17 |
| `usable` | 9 |
| `insufficient_lio` | 1 |

Artifact sizes:

| Artifact | Rows / Size | Notes |
|---|---:|---|
| `runs/localization_bag_audit/latest/session_metrics.csv` | 3 lines | Header plus two sessions. |
| `runs/localization_bag_audit/latest/fix_samples.csv` | 2458 lines | Header plus decoded fixes. |
| `runs/localization_bag_audit/latest/lio_samples.csv` | 6225 lines | Header plus decoded LIO samples. |
| `runs/localization_bag_audit/all_sessions/session_metrics.csv` | 91 lines | Header plus 90 sessions. |
| `runs/localization_bag_audit/all_sessions/fix_samples.csv` | 15498 lines | Full decoded fixes. |
| `runs/localization_bag_audit/all_sessions/lio_samples.csv` | 80339 lines | Full decoded LIO samples. |

## Observations

- The bag interface is usable without ROS runtime: the tool decoded `/fix`, `/fastlio2/lio_odom`, `/gps_corridor/alignment_status`, and `Float64MultiArray` alignment topics directly from SQLite/CDR.
- The best-so-far corridor session has a continuous-looking GPS stream, but GPS-LIO residuals are too large for a trusted anchor. This is exactly the failure mode where `/fix.status` alone would be misleading.
- The long session has a major FAST-LIO timestamp gap and marginal GPS-LIO residuals, so it is useful as a stress bag but not as clean validation data.
- Across 90 sessions, only 9 were classified `usable` after adding a 5 m motion-spread floor. Most bags are weak, rejected, or LIO-only, which supports conservative anchor-health gating.

## Result

The existing bags are worth using before Habitat, but only as localization replay and anchor-health evidence. They should not be used as ObjectNav memory benchmark evidence because they do not contain RGB-D/depth object observations.

The practical result is clear: G60 GPS can be present and marked valid while still being too inconsistent with FAST-LIO for global memory anchoring. The ObjectNav stack should default to `lio_only` or `weak_alignment` unless RTK-quality evidence or a low-residual alignment window is available.

## Follow-up

- Use this audit as the first XJTLU bag gate before connecting RGB-D and RTK.
- Add RTK bags once the UM982/depth camera setup is ready and compare health distributions.
- Add a stable sidecar trace export in the XJTLU repo so future ObjectNav evidence extraction does not depend on direct bag parsing.
