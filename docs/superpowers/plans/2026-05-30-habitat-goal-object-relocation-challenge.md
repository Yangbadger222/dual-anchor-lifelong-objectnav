# Habitat Goal-Object Relocation Challenge Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an instance-scoped Habitat relocation challenge where discovery memory comes from one goal object and the query targets a different same-category goal object in the same scene.

**Architecture:** Extend the closed-loop Habitat runner's challenge/group-selection layer while preserving existing policy arithmetic. Relocated groups carry old and new instance ids; discovery candidate generation uses old ids, while query-time verification and frontier probing use new ids.

**Tech Stack:** Python, pytest, Habitat runner helpers, existing Grounding-DINO/oracle evidence plumbing, JSON summaries.

---

## File Structure

- Modify `src/objectnav_core/objectnav_core/evaluation/habitat_memory_lifecycle_objectnav.py`
  - Add optional old/current instance metadata to `LifecycleGroup`.
- Modify `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
  - Add `goal_object_relocation` challenge support.
  - Build relocated groups from base lifecycle groups.
  - Resolve memory-discovery and query-verification semantic ids separately.
- Modify `src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`
  - Accept the new challenge via existing choices, if choices are duplicated in CLI.
- Modify `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`
  - Add helper tests for relocation pairing and semantic-id routing.
- Modify `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py`
  - Add CLI/preflight forwarding coverage if needed.
- Add docs/devlog and handoff entries after verification.

## Chunk 1: Relocated Group Construction

### Task 1: Add metadata to lifecycle groups

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_lifecycle_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [ ] **Step 1: Write failing test for relocated group metadata**

Add a test that creates simple group objects for the same scene/category with different `goal_object:*` ids, calls the new relocation helper, and expects:

```python
assert relocated[0].group_id == "scene.glb|chair|relocated:goal_object:1->goal_object:2"
assert relocated[0].memory_instance_id == "goal_object:1"
assert relocated[0].target_instance_id == "goal_object:2"
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py::test_build_goal_object_relocation_groups_pairs_same_scene_category_instances -q
```

Expected: FAIL because the helper/fields do not exist.

- [ ] **Step 3: Implement minimal group metadata and pairing helper**

Add optional fields to `LifecycleGroup`:

```python
memory_instance_id: str | None = None
target_instance_id: str | None = None
```

Add a helper in the closed-loop module:

```python
def _build_goal_object_relocation_groups(groups):
    ...
```

Pair only same scene/category groups with distinct `goal_object:` ids.

- [ ] **Step 4: Run the focused test**

Expected: PASS.

## Chunk 2: Semantic Id Routing

### Task 2: Resolve old and new goal-object ids

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py`

- [ ] **Step 1: Write failing tests for semantic id routing**

Add tests for:

```python
memory_ids, query_ids = closed_loop._semantic_ids_for_closed_loop_group(
    semantic_id_to_category={1: "chair", 2: "chair", 3: "plant"},
    group=relocated_group,
    challenge="goal_object_relocation",
)
assert memory_ids == (1,)
assert query_ids == (2,)
```

Also assert regular `stable` still returns category ids for both memory and query.

- [ ] **Step 2: Run tests and verify failure**

Run the new tests by name. Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement semantic routing helper**

Parse `goal_object:<int>` ids. If the id resolves to the requested category,
return that singleton. Otherwise fall back to `_semantic_ids_for_target_category`.

- [ ] **Step 4: Wire helper into the runner**

Use memory ids for `_sample_replay_view_candidates(... discovery_episode ...)`.
Use query ids for fallback candidate generation, memory route verification,
fallback verification, route observations, and navmesh probe verification.

- [ ] **Step 5: Run focused closed-loop tests**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py -q
```

Expected: all pass.

## Chunk 3: CLI and Preflight

### Task 3: Accept the new challenge end to end

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py`
- Modify: `src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py`
- Test: `src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py`

- [ ] **Step 1: Write failing CLI/preflight test**

Add a test that invokes the CLI preflight with:

```bash
--challenge goal_object_relocation
```

and asserts the forwarded `challenge` value.

- [ ] **Step 2: Run the test and verify failure**

Expected: FAIL because the challenge choice is not accepted.

- [ ] **Step 3: Add challenge constant support**

Extend `SUPPORTED_CHALLENGES` with `goal_object_relocation` and ensure preflight
uses relocated groups before selection when requested.

- [ ] **Step 4: Run focused CLI tests**

Expected: PASS.

## Chunk 4: Verification and Linux Smoke

### Task 4: Verify locally and remotely

**Files:**
- Modify docs after commands complete.

- [ ] **Step 1: Run local verification**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/objectnav_core/cli/run_habitat_closed_loop_dual_anchor_objectnav.py
git diff --check
```

- [ ] **Step 2: Commit and push implementation**

Use a focused commit message such as:

```bash
git commit -m "feat: add habitat goal-object relocation challenge"
```

- [ ] **Step 3: Pull on Linux and run focused tests**

```bash
ssh badger@100.88.131.52 'cd ~/Desktop/dual-anchor-lifelong-objectnav && git pull --ff-only origin codex/habitat-memory-lifecycle && source ~/anaconda3/etc/profile.d/conda.sh && conda activate habitat && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_objectnav.py src/objectnav_core/tests/test_habitat_closed_loop_dual_anchor_cli.py -q'
```

- [ ] **Step 4: Run a small Linux preflight**

Use `--challenge goal_object_relocation` and `--preflight-only`.

- [ ] **Step 5: Run a selected-pair oracle or Grounding-DINO smoke**

Start with one category/pair from a scene known to have multiple instances.
Record output under `runs/habitat_closed_loop_dual_anchor/...goal_object_relocation...`.

- [ ] **Step 6: Mine the result**

Run the decision-sensitivity miner on the new summary and inspect boundary
region, post-memory fallback horizon, and detector-event fields.

## Chunk 5: Documentation

### Task 5: Record evidence

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-30-habitat-goal-object-relocation-smoke.md` if a real Linux smoke completes.

- [ ] **Step 1: Add devlog entry**

Include files changed, why relocation challenge was needed, commands run, and
verification status.

- [ ] **Step 2: Add/update handoff**

State current implementation status, artifact paths, passed/failed commands,
and next recommended action.

- [ ] **Step 3: Add experiment report if Linux smoke ran**

Report metrics honestly. Do not claim a benchmark improvement unless the run
actually supports it.

- [ ] **Step 4: Run `git diff --check`, commit, and push docs**
