# Handoff: Localization-Only Bag Audit

Date: 2026-05-26  
Owner: Codex  
Status: Ready for Review

## Current State

A ROS-runtime-free localization bag audit has been implemented in `objectnav_core`. It reads ROS 2 SQLite bags directly, decodes selected CDR message types, reports FAST-LIO/GNSS health, and writes JSON, CSV, and HTML artifacts.

The tool has been run on two selected bags and on all 90 metadata-backed sessions under `/Users/badger/Desktop/my_local_data/logs`.

## Files Touched

- `README.md`
- `docs/design/2026-05-26-localization-only-bag-audit.md`
- `docs/experiments/2026-05-26-localization-only-bag-audit.md`
- `docs/handoff/2026-05-26-localization-only-bag-audit.md`
- `docs/superpowers/plans/2026-05-26-localization-only-bag-audit.md`
- `docs/devlog/2026-05.md`
- `src/objectnav_core/setup.py`
- `src/objectnav_core/objectnav_core/cli/run_localization_bag_audit.py`
- `src/objectnav_core/objectnav_core/evaluation/localization_bag_audit.py`
- `src/objectnav_core/tests/test_localization_bag_audit.py`
- `src/objectnav_core/tests/test_ros_packaging.py`

## Commands Run

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_localization_bag_audit.py -q
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests/test_localization_bag_audit.py src/objectnav_core/tests/test_ros_packaging.py -q
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_localization_bag_audit --output runs/localization_bag_audit/best_so_far --bag /Users/badger/Desktop/my_local_data/logs/2026-03-25-17-46-15/bag
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_localization_bag_audit --output runs/localization_bag_audit/latest --bag /Users/badger/Desktop/my_local_data/logs/2026-03-25-17-46-15/bag --bag /Users/badger/Desktop/my_local_data/logs/2026-03-22-21-05-17/bag
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_localization_bag_audit --output runs/localization_bag_audit/all_sessions --data-root /Users/badger/Desktop/my_local_data/logs
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest src/objectnav_core/tests -q
python3 -m compileall -q src/objectnav_core/objectnav_core
```

## Verification

Passed:

- Focused audit tests.
- CLI and ROS-packaging focused tests.
- Real two-bag audit.
- Real 90-session audit.
- Full `src/objectnav_core/tests`: 37 tests passed.
- Python compile check: exited successfully.

## Known Risks

- The CDR decoder is intentionally minimal. It supports only the audited message types and should be extended test-first.
- The GPS-LIO alignment is a diagnostic similarity fit, not ground truth.
- `usable` means a bag passed this coarse offline audit, not that GNSS is RTK-grade.
- Very short motion can overfit alignment, so a 5 m motion-spread floor is now enforced.
- Generated artifacts under `runs/localization_bag_audit/*` are intentionally ignored and should not be committed.

## Next Recommended Step

1. Review `runs/localization_bag_audit/all_sessions/audit_report.html` and `session_metrics.csv`.
2. Pick 2-3 representative sessions for manual trajectory visualization.
3. Once RTK/depth data exists, rerun the same audit and compare `anchor_health` distributions against the G60 baseline.

## Context for Next Contributor

The key result is that G60 `/fix` can be present and valid while GPS-LIO alignment remains too weak for long-term anchoring. Use this to justify conservative anchor-health gating before writing object memories into a global anchor.
