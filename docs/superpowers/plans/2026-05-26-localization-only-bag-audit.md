# Localization-Only Bag Audit Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a ROS-runtime-free localization audit that reads existing XJTLU ROS 2 SQLite bags and reports FAST-LIO/G60 GPS health.

**Architecture:** Add a focused `objectnav_core.evaluation.localization_bag_audit` module with minimal CDR decoders for only the message types needed by the audit. Expose it through a CLI, write deterministic CSV/JSON/HTML artifacts, and keep the core free of ROS imports.

**Tech Stack:** Python standard library, SQLite, PyYAML, pytest.

---

### Task 1: Audit Tests

**Files:**
- Create: `src/objectnav_core/tests/test_localization_bag_audit.py`

- [x] Write tests that build a tiny SQLite rosbag fixture with `/fix`, `/fastlio2/lio_odom`, `/gps_corridor/alignment_status`, and `/gps_corridor/alignment_debug`.
- [x] Run the focused test and verify it fails because `objectnav_core.evaluation.localization_bag_audit` does not exist yet.

### Task 2: Core Audit Module

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/localization_bag_audit.py`

- [x] Implement minimal CDR reader helpers for strings, primitive fields, arrays, `NavSatFix`, `Odometry`, `Float64MultiArray`, and `String`.
- [x] Implement bag discovery, SQLite topic/message reads, LIO metrics, GPS metrics, nearest-time pairing, SE(2) alignment, anchor-health classification, and artifact writing.
- [x] Run the focused test and verify it passes.

### Task 3: CLI And Packaging

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/run_localization_bag_audit.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`
- Modify: `README.md`

- [x] Add CLI flags for `--output`, repeated `--bag`, `--data-root`, and `--limit`.
- [x] Add console script metadata without adding ROS runtime dependencies.
- [x] Update packaging tests and README.
- [x] Run focused packaging and CLI tests.

### Task 4: Real Data Audit

**Files:**
- Create: `docs/experiments/2026-05-26-localization-only-bag-audit.md`
- Modify: `docs/devlog/2026-05.md`
- Create: `docs/handoff/2026-05-26-localization-only-bag-audit.md`

- [x] Run the audit on `/Users/badger/Desktop/my_local_data/logs/2026-03-25-17-46-15/bag`.
- [x] Run the audit on `/Users/badger/Desktop/my_local_data/logs/2026-03-22-21-05-17/bag`.
- [x] Record commands, metrics, limitations, and next steps.

### Task 5: Verification

**Files:**
- No new files.

- [x] Run focused audit tests.
- [x] Run full `src/objectnav_core/tests`.
- [x] Run `python3 -m compileall -q src/objectnav_core/objectnav_core`.
- [x] Confirm generated run artifacts exist and remain under ignored `runs/`.
