# Memory-Validity Logistic Baseline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an offline deterministic logistic-regression baseline that trains on exported Habitat memory-validity datasets without future leakage.

**Architecture:** The trainer lives beside the dataset exporter in `objectnav_core.evaluation`, consumes the exporter JSON schema, and writes a self-contained JSON model report with preprocessing statistics, weights, and metrics. A small CLI mirrors the exporter CLI and does not change the online Habitat runner yet.

**Tech Stack:** Python standard library, existing pytest suite, existing `objectnav_core` CLI/module layout.

---

## Chunk 1: Offline Trainer

### Task 1: Model API and Metrics

**Files:**
- Create: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_model.py`

- [ ] **Step 1: Write failing test for synthetic separation**

Create a test that builds a tiny exporter-style dataset with two invalid examples and two valid examples. Train with `train_memory_validity_logistic_model(...)` and assert valid examples receive higher predicted probabilities than invalid examples, metrics include accuracy/log-loss/Brier score, and the persisted `feature_names` match the requested feature list.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_memory_validity_model.py -q
```

Expected: fail because `habitat_memory_validity_model` does not exist.

- [ ] **Step 3: Implement minimal deterministic trainer**

Implement:
- `train_memory_validity_logistic_model(dataset, feature_names=None, epochs=400, learning_rate=0.1, l2=0.001)`
- `predict_memory_validity(model, features)`

Use only numeric exporter features, impute missing/non-numeric values with per-feature means, standardize by per-feature scale, optimize logistic loss with deterministic full-batch gradient descent, and report accuracy/log_loss/brier_score/positive_count/negative_count/example_count.

- [ ] **Step 4: Run focused model tests and verify GREEN**

Run the same focused pytest command. Expected: pass.

### Task 2: Persistence Behavior

**Files:**
- Modify: `src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_model.py`

- [ ] **Step 1: Write failing test for missing-value persistence**

Add a test that trains with missing feature values, predicts from a feature dict missing at least one trained feature, and asserts prediction is finite and identical after JSON round-trip through `model` data.

- [ ] **Step 2: Run the focused test and verify RED**

Expected: fail until imputation/prediction behavior is complete.

- [ ] **Step 3: Implement robust preprocessing**

Store `feature_means`, `feature_scales`, `missing_value_count`, and `warnings` in the model report. Prediction should use stored means/scales and ignore unknown feature keys.

- [ ] **Step 4: Run focused model tests and verify GREEN**

Run focused model tests again.

## Chunk 2: CLI

### Task 3: Training CLI

**Files:**
- Create: `src/objectnav_core/objectnav_core/cli/train_habitat_memory_validity_model.py`
- Test: `src/objectnav_core/tests/test_habitat_memory_validity_model.py`

- [ ] **Step 1: Write failing CLI test**

Add a test that writes a tiny dataset JSON, invokes `main([dataset, "--output", model_json])`, and asserts the output JSON contains task name, feature names, weights, metrics, and examples count.

- [ ] **Step 2: Run focused test and verify RED**

Expected: fail because the CLI does not exist.

- [ ] **Step 3: Implement CLI**

Parse dataset path, output path, optional `--features`, `--epochs`, `--learning-rate`, and `--l2`. Write sorted/indented JSON and return `0`.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run focused model tests again.

## Chunk 3: Documentation and Verification

### Task 4: Research Trace

**Files:**
- Modify: `docs/design/2026-05-30-memory-validity-logistic-baseline.md`
- Modify: `docs/devlog/2026-05.md`
- Modify: `docs/handoff/2026-05-29-closed-loop-dual-anchor-habitat-objectnav.md`

- [ ] **Step 1: Update design status and interfaces**

Mark the design as implemented locally and record that online runner integration remains outside this step.

- [ ] **Step 2: Add devlog entry**

Record files changed, reason, verification, and remaining risk.

- [ ] **Step 3: Update handoff**

Add the trainer/CLI as the next local capability and note that real Habitat dataset export/training still depends on Linux reachability.

### Task 5: Final Verification

- [ ] **Step 1: Run focused suite**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests/test_habitat_memory_validity_model.py src/objectnav_core/tests/test_habitat_memory_validity_dataset.py -q
```

- [ ] **Step 2: Compile touched modules**

```bash
python -m py_compile src/objectnav_core/objectnav_core/evaluation/habitat_memory_validity_model.py src/objectnav_core/objectnav_core/cli/train_habitat_memory_validity_model.py
```

- [ ] **Step 3: Run full local core suite**

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src/objectnav_core python -m pytest src/objectnav_core/tests -q
```

- [ ] **Step 4: Check whitespace**

```bash
git diff --check
```
