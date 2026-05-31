# Official Temporal Learned Local Frontier Policy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add past-only temporal local-action features to the online learned local frontier policy.

**Architecture:** Store compact per-step local-action history in `OfficialPolicyState`, derive v2-compatible temporal feature values when scoring learned-local candidates, and record those values in policy traces.

**Tech Stack:** Python stdlib, NumPy-backed existing official evaluator, pytest.

---

## Chunk 1: Online Temporal Feature Parity

### Task 1: RED online temporal-history test

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_objectnav_eval.py`

- [ ] **Step 1: Write failing test**

Add a learned-local policy test with a hand-authored model using
`action_turn_left__recent_target_visible_count` and
`action_move_forward__recent_target_visible_count`.

- [ ] **Step 2: Run RED**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest -q \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py::test_memory_learned_local_frontier_scores_with_online_temporal_history
```

Expected: fail because online model examples do not include temporal history.

### Task 2: GREEN policy-state history

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_objectnav_eval.py`

- [ ] **Step 1: Add compact local-action history to `OfficialPolicyState`**

Store previous step metadata and target-visible detector evidence after action
selection and before `env.step`.

- [ ] **Step 2: Add temporal features to `_local_action_model_example`**

Compute v2-compatible past-only temporal features from state history.

- [ ] **Step 3: Record compact debug values**

Add trace debug fields for the online temporal feature values used by the
learned-local scorer.

- [ ] **Step 4: Run the RED test**

Expected: pass.

- [ ] **Step 5: Run focused official gate**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_objectnav_eval.py \
  src/objectnav_core/tests/test_habitat_official_objectnav_cli.py \
  src/objectnav_core/tests/test_habitat_official_local_action_dataset.py \
  src/objectnav_core/tests/test_habitat_official_local_action_model.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery.py \
  src/objectnav_core/tests/test_habitat_official_memory_discovery_cli.py \
  src/objectnav_core/tests/test_official_episode_memory.py \
  src/objectnav_core/tests/test_lifecycle_memory_prior_export.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```
