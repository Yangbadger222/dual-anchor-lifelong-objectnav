# Official TargetNav Backend Selector Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `targetnav_backend` a first-class selector for the base official TargetNav memory policy.

**Architecture:** Keep the existing policy implementations and backend functions. Add a CLI selector, pass it into the run config, and make manifest reporting use the effective backend selected by either the base policy config or the legacy alias policy names.

**Tech Stack:** Python, argparse, pytest, existing Habitat official evaluator tests.

---

## Chunk 1: Selector Plumbing

### Task 1: Verify Existing Red Tests

**Files:**
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Run selector tests**

Run:

```bash
pytest src/objectnav_core/tests/test_habitat_official_objectnav_cli.py::test_official_objectnav_cli_passes_targetnav_backend_option src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_oracle_backend_selector -q
```

Expected before implementation: FAIL because argparse lacks `--targetnav-backend` and the manifest reports `occupancy_grid` for the oracle selector.

### Task 2: Add CLI Backend Option

**Files:**
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py`

- [x] **Step 1: Import supported backend choices**

Import `SUPPORTED_TARGETNAV_BACKENDS` from the official evaluator module.

- [x] **Step 2: Add parser argument**

Add `--targetnav-backend` with `choices=SUPPORTED_TARGETNAV_BACKENDS` and default `occupancy_grid`.

- [x] **Step 3: Pass through to runner kwargs**

Set `kwargs["targetnav_backend"] = args.targetnav_backend`.

### Task 3: Fix Manifest Effective Backend

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [x] **Step 1: Compute effective backend**

For `memory_active_perception_frontier_targetnav`, use `config.targetnav_backend`. Preserve legacy alias mappings for FMM and DDPPO.

- [x] **Step 2: Compute source validity from effective backend**

Use `oracle_diagnostic_only` for `oracle_follower`, `sensor_depth_learned_pointnav_policy` for `ddppo_pointnav`, and `sensor_depth_local_planner` for non-oracle sensor-depth planners.

- [x] **Step 3: Include checkpoint metadata for effective DDPPO**

Include checkpoint/device metadata when either the DDPPO alias policy or the base policy with `targetnav_backend="ddppo_pointnav"` is selected.

### Task 4: Verify Green

**Files:**
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_cli.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [x] **Step 1: Run selector tests**

Run:

```bash
pytest src/objectnav_core/tests/test_habitat_official_objectnav_cli.py::test_official_objectnav_cli_passes_targetnav_backend_option src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_oracle_backend_selector -q
```

Expected: PASS.

- [x] **Step 2: Run focused TargetNav regression tests**

Run:

```bash
pytest src/objectnav_core/tests/test_habitat_official_objectnav_cli.py src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_interface_boundary src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_oracle_backend_selector src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_fmm_backend_selector src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_policy_records_ddppo_backend_selector src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_fmm_policy_records_backend_boundary src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_active_perception_targetnav_ddppo_policy_records_backend_boundary src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_targetnav_policy_can_use_oracle_follower_backend_selector -q
```

Expected: PASS.

- [x] **Step 3: Run syntax/import check**

Run:

```bash
python -m compileall src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py src/objectnav_core/objectnav_core/cli/run_habitat_official_objectnav_eval.py
```

Expected: no compile errors.
