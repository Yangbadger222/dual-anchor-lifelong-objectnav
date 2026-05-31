# Design Doc: Official Detector Memory Discovery CLI

Date: 2026-05-30
Owner: Codex
Status: Implemented, smoke-tested, not benchmark-validated

## Goal

Expose the tested official memory-discovery loop as a reproducible command-line
entry point that can run Habitat ObjectNav discovery episodes with a real
detector adapter and write official memory-prior artifacts.

## Non-Goals

- Do not claim benchmark performance from discovery artifacts alone.
- Do not add GPT/language grounding in this slice.
- Do not change the official evaluator's metric source or action semantics.
- Do not make lifecycle `habitat_world` anchors actionable.
- Do not implement learned memory scoring here; this is operational detector
  wiring for the existing discovery core.

## Background

The project now has an official Habitat ObjectNav evaluator, a guarded memory
prior policy, an episode-relative detector projection helper, and a tested
`run_habitat_official_memory_discovery(...)` core loop. That loop is useful for
unit and integration tests, but operators still need a stable CLI to run real
detectors on Linux and save artifacts that can be fed into
`memory_guided_frontier`.

## System Boundary

Add:

- `objectnav_core.cli.run_habitat_official_memory_discovery`

The CLI owns:

- parsing Habitat config, dataset, split, policy, and step limits;
- parsing detector backend settings;
- constructing a `YoloWorldDetector` or `GroundingDinoDetector`;
- invoking `run_habitat_official_memory_discovery`;
- printing the JSON summary.

The discovery core remains responsible for stepping the official environment,
filtering detections, projecting anchors, and writing artifacts.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Habitat config | path | Defaults to official HM3D ObjectNav config. |
| Input | Dataset data path | path | Defaults to `val_mini.json.gz`. |
| Input | Scene root | path | Defaults to HM3D scene root. |
| Input | Detector backend | enum | `yolo_world` or `grounding_dino`. |
| Input | Detector categories | comma-separated labels | Defaults to ObjectNav categories. |
| Output | Memory prior | JSON | Written by discovery core. |
| Output | Detection trace | CSV | Written by discovery core. |
| Output | Summary | JSON/stdout | Includes detector/config metadata and caveats. |

## Interfaces

```bash
python -m objectnav_core.cli.run_habitat_official_memory_discovery \
  --output runs/habitat_official_objectnav/discovery_yolo_1ep \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt \
  --detector-conf 0.25 \
  --categories bed,chair,plant,sofa,toilet,tv_monitor \
  --policy occupancy_frontier \
  --max-episodes 1 \
  --max-steps 100
```

Console script:

```bash
objectnav_habitat_official_memory_discovery ...
```

## Data Flow

1. Parse CLI arguments.
2. Build detector categories from comma-separated labels.
3. Construct the requested detector adapter.
4. Pass detector adapter plus official Habitat run parameters to the discovery
   core loop.
5. Write artifacts through the discovery core.
6. Print summary JSON for logs and automation.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Empty detector categories | CLI validation | fail before loading Habitat/model. |
| Missing detector dependency | detector constructor raises | surface actionable adapter error. |
| Unsupported detector | argparse choices | fail before side effects. |
| Detector labels differ from ObjectNav labels | discovery label normalization | use categories with underscores or spaces; trace CSV exposes raw labels. |
| Discovery artifact used as benchmark claim | summary caveat | mark source as not benchmark-validated. |

## Verification Plan

1. Unit-test the CLI parser exposes detector and discovery arguments.
2. Unit-test `main(..., detector_factory=..., runner=...)` builds the requested
   detector and forwards discovery arguments without loading Habitat.
3. Unit-test comma-separated categories reject empty input.
4. Unit-test `setup.py` exposes the console script.
5. Run local focused tests and full suite.
6. Sync to Linux and run focused official-memory/CLI tests in conda env
   `habitat`.
7. If dependencies are present, run Linux real-detector discovery/query smokes
   and record generated artifact paths. If unavailable, record the blocker
   explicitly without treating it as completion.

## Research Relevance

This turns the detector-backed memory path from a tested library function into
a reproducible experiment command. It is required before fair discovery/query
comparisons, but it is still infrastructure: paper-facing claims still require
real detector artifacts, official query runs, and a comparison against the
corrected no-memory baseline.
