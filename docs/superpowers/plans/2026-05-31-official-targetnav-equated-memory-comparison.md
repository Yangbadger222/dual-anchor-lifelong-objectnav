# Official TargetNav-Equated Memory Comparison Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class official ObjectNav policies for `no_memory_targetnav` and `naive_count_targetnav`, then use them in the memory comparison table so all rows share the same terminal TargetNav backend.

**Architecture:** Reuse the existing `memory_active_perception_frontier_targetnav` controller and gate the memory-anchor branch by policy. `no_memory_targetnav` keeps detector-triggered TargetNav and frontier exploration but never loads memory. `naive_count_targetnav` is an explicit alias for the same TargetNav path using a positive-only prior, so reports preserve the baseline's identity.

**Tech Stack:** Python, pytest, existing Habitat official evaluator, existing comparison CLI.

---

### Task 1: Add TargetNav Baseline Policies

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`
- Test: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write failing tests**

Add tests showing:

```python
def test_no_memory_targetnav_uses_detector_but_not_memory_anchor():
    ...

def test_naive_count_targetnav_executes_matching_memory_anchor():
    ...
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_no_memory_targetnav_uses_detector_but_not_memory_anchor \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_naive_count_targetnav_executes_matching_memory_anchor -q
```

Expected: fail because the policy names are unsupported.

- [ ] **Step 3: Implement policy aliases**

Add both policy names to `SUPPORTED_OFFICIAL_POLICIES`, validation, policy kind, targetnav manifest, benchmark caveat logic, and `_select_policy_action`. Route `no_memory_targetnav` through TargetNav with `use_memory=False`; route `naive_count_targetnav` with `use_memory=True`.

- [ ] **Step 4: Verify GREEN**

Run the two focused tests above and confirm they pass.

### Task 2: Update Comparison Defaults and CLI Choices

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_comparison.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_comparison.py`
- Test: `src/objectnav_core/tests/test_habitat_official_memory_comparison.py`

- [ ] **Step 1: Write failing tests**

Update expected defaults to:

```python
no_memory -> no_memory_targetnav
naive_count -> naive_count_targetnav
memory_guided -> memory_active_perception_frontier_targetnav
```

Add an assertion that `targetnav_backend="oracle_follower"` is forwarded to all three rows.

- [ ] **Step 2: Run comparison tests to verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_memory_comparison.py -q
```

Expected: fail on old default mappings or missing backend argument.

- [ ] **Step 3: Implement comparison update**

Update default specs and expose `--targetnav-backend` in the comparison CLI.

- [ ] **Step 4: Verify GREEN**

Run the comparison tests again.

### Task 3: Documentation and Verification

**Files:**
- Modify: `docs/design/2026-05-31-official-memory-baseline-comparison.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-31-official-robot-viewpoint-memory-anchor.md`

- [ ] **Step 1: Run focused local verification**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python3 -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_memory_comparison.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
python3 -m compileall -q src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_comparison.py src/objectnav_core/objectnav_core/cli/run_habitat_official_memory_comparison.py
git diff --check
```

- [ ] **Step 2: Run remote focused tests**

Run the same focused tests on `badger@100.88.131.52` with `/home/badger/anaconda3/envs/habitat/bin/python`.

- [ ] **Step 3: Run a 4-episode oracle-backend comparison**

Use the existing proposed and naive-count priors if available. Report SR/SPL/SoftSPL/DistanceToGoal and caveat the oracle backend as diagnostic.
