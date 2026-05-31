# Official Candidate-Viewpoint Ranker Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train and evaluate a deterministic candidate-viewpoint ranker from candidate-viewpoint restore labels, with explicit top-rank/top-score/oracle baselines.

**Architecture:** Add a focused model module beside the existing official view-recall/action-utility models. The model consumes restore dataset rows, extracts pre-label candidate/state features, scores candidates within each restored state, and emits JSON/CSV reports plus state-fold evaluation.

**Tech Stack:** Python, pytest, deterministic logistic regression, existing CLI/package patterns.

---

## Chunk 1: Model API

### Task 1: Training and Feature Extraction

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_viewpoint_ranker_model.py`
- Create: `src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py`

- [x] **Step 1: Write failing training test**

Add a synthetic candidate-viewpoint dataset with two states and mixed positive
candidates. Assert the model task name, label counts, feature names, and that
label/leakage fields are excluded.

- [x] **Step 2: Run the test to verify RED**

Expected: FAIL because the module does not exist.

- [x] **Step 3: Implement minimal logistic training**

Implement parsing, current-hidden filtering, feature extraction, standardization,
and deterministic logistic optimization.

- [x] **Step 4: Run focused test to verify GREEN**

Expected: PASS.

### Task 2: State-Level Scoring and Baselines

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_viewpoint_ranker_model.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py`

- [x] **Step 1: Write failing scoring test**

Assert score report groups candidates by state and reports model-selected,
top-rank, top-score, and oracle recovery counts.

- [x] **Step 2: Run test to verify RED**

Expected: FAIL until scoring exists.

- [x] **Step 3: Implement scoring and CSV writer**

Add state grouping, candidate predictions, aggregate counts, and CSV output.

- [x] **Step 4: Run focused tests**

Expected: PASS.

### Task 3: State-Fold Evaluation

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_viewpoint_ranker_model.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py`

- [x] **Step 1: Write failing fold test**

Assert train and holdout states are disjoint and aggregate fold counts are
reported.

- [x] **Step 2: Implement state-fold evaluation**

Split state keys deterministically by index modulo fold count.

- [x] **Step 3: Run focused tests**

Expected: PASS.

## Chunk 2: CLI and Packaging

### Task 4: CLI

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/train_habitat_official_candidate_viewpoint_ranker.py`
- Modify: `src/objectnav_core/setup.py`
- Modify: `src/objectnav_core/tests/test_ros_packaging.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py`

- [x] **Step 1: Write failing CLI test**

Assert CLI writes model JSON, score JSON, score CSV, and fold JSON.

- [x] **Step 2: Implement CLI and package entry point**

Follow existing official model CLI style.

- [x] **Step 3: Run focused tests**

Expected: PASS.

## Chunk 3: Verification and Real Artifact Evaluation

### Task 5: Local Verification and Docs

**Files:**
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`
- Create: `docs/experiments/2026-05-31-official-candidate-viewpoint-ranker.md`
- Modify: `docs/design/2026-05-31-official-candidate-viewpoint-ranker.md`

- [x] **Step 1: Run focused and full tests**
- [x] **Step 2: Run compileall, diff check, and whitespace scan**
- [x] **Step 3: Update docs with actual results**

### Task 6: Linux Evaluation

**Files:**
- Sync touched files to Linux mirror.

- [x] **Step 1: Run targeted Linux tests in conda env `habitat`**
- [x] **Step 2: Train/score on real candidate-viewpoint artifact**
- [x] **Step 3: Record model vs top-rank/top-score/oracle results**

Real artifact input:

```bash
runs/habitat_official_objectnav/candidate_viewpoint_restore_phase_path_features_max8cat_max2episode_yolo_20260531_v1/dataset.json
```

## Chunk 4: Source-Diverse Validation

### Task 7: Leave-One-Source Ranker Evaluation

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_official_candidate_viewpoint_ranker_model.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py`

- [x] **Step 1: Write failing leave-one-source test**

Use a synthetic dataset with two `source_dataset` values. Assert each split
holds out exactly one source, no train candidate uses the held-out source, and
aggregate model/top-rank/top-score/oracle counts are reported.

- [x] **Step 2: Implement leave-one-source evaluation**

Train on all current-hidden candidates except one source and score the held-out
source with current-hidden filtering already applied.

- [x] **Step 3: Run focused ranker tests**

Expected: PASS.

### Task 8: Multi-Dataset CLI

**Files:**
- Modify: `src/objectnav_core/objectnav_core/cli/train_habitat_official_candidate_viewpoint_ranker.py`
- Modify: `src/objectnav_core/tests/test_habitat_official_candidate_viewpoint_ranker_model.py`

- [x] **Step 1: Write failing CLI test**

Assert the CLI accepts multiple dataset paths, tags rows by `source_dataset`,
and writes `--leave-one-source-output`.

- [x] **Step 2: Implement multi-dataset loading and output**

Preserve single-dataset behavior, merge candidate rows for model training, and
record source paths in rows before training/scoring.

- [x] **Step 3: Run focused ranker tests**

Expected: PASS.

### Task 9: Source-Diverse Linux Artifact Evaluation

**Files:**
- Modify: `docs/experiments/2026-05-31-official-candidate-viewpoint-ranker.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [x] **Step 1: Generate candidate-viewpoint restore labels for multiple existing policy traces**
- [x] **Step 2: Run ranker leave-one-source validation**
- [x] **Step 3: Record whether source-held-out recovery beats simple baselines**
