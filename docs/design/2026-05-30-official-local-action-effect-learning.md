# Design Doc: Official Local Action-Effect Learning Dataset

Date: 2026-05-30
Owner: Codex
Status: Implemented; initial YOLO trace export completed

## Goal

Create a benchmark-safe learning substrate for official Habitat ObjectNav local
control. The system should turn `policy_trace.json` and `detector_trace.json`
from official query runs into self-supervised action-effect examples, so the
next controller can learn which discrete action preserves or improves target
detector evidence instead of relying on another hand-authored one-step rule.

## Non-Goals

- Do not change official Habitat metric handling or report non-official metrics
  as benchmark results.
- Do not use semantic oracle masks, target geodesic distance, Habitat success
  labels, pathfinder shortcuts, or future observations as online policy inputs.
- Do not replace `memory_evidence_frontier` in this slice.
- Do not train a final local controller in this first step. The deliverable is a
  reproducible dataset/export interface that can support learned scoring next.
- Do not tune around the four-episode YOLO smoke. The exporter must work on any
  official policy trace with optional detector trace evidence.

## Background

The official YOLO query smoke exposed a local-control bottleneck. The
`memory_evidence_frontier` policy removed the repeated
`center_detector_target` / `reacquire_detector_target` loop and improved
SoftSPL, but it still solved `0/4` episodes. In the target `tv_monitor`
episode, the policy observed the target at the image edge, learned that a
centering turn lost it, moved forward three times, and then lost target evidence
entirely. It spent the remaining budget oscillating between memory-belief
turning and blocked fallback.

That trace argues for a short-horizon local action scorer. To make that scorer
publishable and robot-relevant, the first artifact should be a clean
self-supervised action-effect dataset: what did the robot see before an action,
what action did it execute, and whether the next observation retained,
acquired, lost, or improved target evidence.

## System Boundary

Add a small official-evaluation data module:

- `objectnav_core.evaluation.habitat_official_local_action_dataset`
- CLI:
  `objectnav_core.cli.export_habitat_official_local_action_dataset`
- focused tests under `src/objectnav_core/tests/`

The module consumes already-written official artifacts. It does not import or
instantiate Habitat. It depends only on JSON traces produced by
`habitat_official_objectnav_eval.py`.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Policy trace | `policy_trace.json` | Uses step metadata, action, decision, pose, heading, and policy debug payloads. |
| Input | Detector trace | `detector_trace.json` | Uses target-match detections by episode and step; optional but required for target-evidence labels. |
| Output | Dataset report | JSON | Includes schema version, summary counts, examples, and source artifact metadata. |
| Output | Flat examples | CSV | One row per action-effect example for quick inspection/training. |

## Interfaces

Python API:

- `export_official_local_action_dataset(policy_trace_path, detector_trace_path, source_run_id=None)`
- `write_official_local_action_dataset_csv(dataset, path)`

CLI:

```bash
python -m objectnav_core.cli.export_habitat_official_local_action_dataset \
  <policy_trace.json> \
  --detector-trace <detector_trace.json> \
  --output <dataset.json> \
  --csv-output <examples.csv>
```

## Data Flow

1. Load `policy_trace.json` and index steps by `(episode_index, step_index)`.
2. Load `detector_trace.json` and select the highest-confidence target-match
   detection for each `(episode_index, step_index)`.
3. For each policy step with a following step in the same episode, create an
   action-effect example.
4. Features describe only information available before the action:
   policy, decision, action, target category, pose, heading, current target
   visibility, current confidence, bbox area, center offset, and optional debug
   flags such as suppressed detector-centering action.
5. Labels describe the next observation:
   target retained, acquired, lost, visible after action, confidence delta, bbox
   area delta, absolute-center-offset delta, pose delta, and heading delta.
6. The exporter writes a JSON report plus a CSV table with stable column names.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Policy and detector traces are from different runs | Episode/step coverage is sparse or metadata mismatches | Record missing detector evidence counts and fail only on malformed files; keep source paths in the report. |
| Detector trace lacks target matches | Summary shows zero visible-before/after examples | Still export negative/search examples; do not fabricate labels. |
| Multiple target detections in one frame | More than one matching detection for a step | Use highest confidence as the primary evidence and record match count. |
| Debug payload schema evolves | Optional fields missing | Default optional feature fields to `null`/`0` and keep schema versioned. |
| Dataset is mistaken for benchmark evidence | Docs and report label it as training/diagnostic data | Official success/SPL remain sourced only from Habitat summaries. |

## Verification Plan

1. RED API test with synthetic traces:
   - one visible target before action,
   - visible improved evidence after action,
   - one target-lost transition,
   - one target-acquired transition.
2. RED CSV test proving stable headers and flattened examples.
3. RED CLI test proving JSON and CSV outputs are written and include source
   trace metadata.
4. GREEN implementation with no Habitat dependency.
5. Run focused local tests for the new module/CLI.
6. Run `py_compile` for the new module and CLI.
7. Run `git diff --check`.
8. If SSH remains reachable, export the dataset from the latest Linux
   `memory_evidence_frontier` YOLO artifact and record summary counts in a
   follow-up experiment note.

## Research Relevance

This is the bridge from a hand-written local servo to a learned local
action-effect model. The lifelong-memory story remains intact: memory proposes
where to search, detector evidence grounds the target, and an action-effect
model learns how the robot should move locally when evidence is fragile. The
same interface can later ingest real-robot traces, making the simulator-to-car
path cleaner than Habitat-specific heuristics.

## Open Questions

- Whether to train the first scorer as a classifier over target retention /
  acquisition or as a small value regressor over continuous evidence quality.
- Whether negative no-target search steps should be downsampled or kept with
  per-decision balancing during training.
- Whether online deployment should be a new policy variant or a scorer plugged
  into `memory_evidence_frontier`.
