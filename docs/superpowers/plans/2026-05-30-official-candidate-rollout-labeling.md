# Official Candidate Rollout Labeling Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a replay-based diagnostic dataset exporter that assigns real short-horizon detector-recovery labels to active-perception candidates.

**Architecture:** Add a focused evaluation module that loads policy traces, replays each episode to candidate states, branches over candidate actions, and writes JSON/CSV rollout labels. Keep the rollout dataset separate from official ObjectNav metric summaries and online policy behavior.

**Tech Stack:** Python stdlib JSON/CSV/pathlib, existing Habitat official eval helpers, pytest fake envs for local tests, optional YOLO/Grounding-DINO detector adapters through the existing CLI pattern.

---

## File Structure

- Create `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`
  - Owns trace loading, replay, branch rollout labels, detector evidence, and CSV writing.
- Create `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py`
  - Owns argparse, detector construction reuse, env config arguments, JSON/CSV output.
- Create `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
  - Tests pure replay/branch behavior with fake env and detector.
- Modify `src/objectnav_core/setup.py`
  - Register `objectnav_habitat_official_candidate_rollout_dataset`.
- Modify `src/objectnav_core/tests/test_ros_packaging.py`
  - Assert console script registration.
- Update docs under `docs/devlog/`, `docs/experiments/`, and `docs/handoff/`.

## Chunk 1: Tests First

### Task 1: Rollout Labels From Same Branch State

**Files:**
- Create: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Create later: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write the failing test**

```python
def test_candidate_rollout_dataset_labels_candidates_from_same_replayed_state(tmp_path):
    policy_trace = write trace with step 0 move_forward and step 1 two top candidates
    env = fake env where candidate 0 turn_left reveals target and candidate 1 turn_right does not
    dataset = export_official_candidate_rollout_dataset(..., env_factory=lambda _: env)
    assert dataset["rollout_count"] == 2
    assert candidate rank 0 hidden_to_visible is True
    assert candidate rank 1 hidden_to_visible is False
    assert env.replay_prefixes include ["move_forward"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py::test_candidate_rollout_dataset_labels_candidates_from_same_replayed_state -q
```

Expected: FAIL with module/function import missing.

- [ ] **Step 3: Implement minimal module code**

Add `export_official_candidate_rollout_dataset` with trace loading, fake-env replay, branch rollout, detector calls, and summary counts.

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command. Expected: PASS.

### Task 2: CSV Writer

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py`

- [ ] **Step 1: Write failing CSV test**
- [ ] **Step 2: Run focused test and observe missing writer/field failure**
- [ ] **Step 3: Add `write_official_candidate_rollout_dataset_csv`**
- [ ] **Step 4: Run focused test and confirm PASS**

### Task 3: CLI And Packaging

**Files:**
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`
- Create: `src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py`
- Modify: `src/objectnav_core/setup.py`

- [ ] **Step 1: Write failing CLI test that calls `main()` with fake runner**
- [ ] **Step 2: Add failing packaging assertion for console script**
- [ ] **Step 3: Run focused tests and observe failures**
- [ ] **Step 4: Implement CLI and register script**
- [ ] **Step 5: Run focused tests and confirm PASS**

## Chunk 2: Documentation And Verification

### Task 4: Research Trail

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Create: `docs/experiments/2026-05-30-official-candidate-rollout-labeling.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Add devlog entry with changed files and reason**
- [ ] **Step 2: Add experiment report with local verification and planned Linux export command**
- [ ] **Step 3: Update handoff with current state, commands, risks, and next step**

### Task 5: Verification

- [ ] **Step 1: Run focused pytest**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest \
  src/objectnav_core/tests/test_habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/tests/test_ros_packaging.py -q
```

- [ ] **Step 2: Run compileall**

```bash
PYTHONPATH=src/objectnav_core python -m compileall \
  src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_rollout_dataset.py \
  src/objectnav_core/objectnav_core/cli/export_habitat_official_candidate_rollout_dataset.py
```

- [ ] **Step 3: Run whitespace check**

```bash
git diff --check
```

- [ ] **Step 4: Report any verification not run**

Linux Habitat export is expected to be the next step if local tests pass.
