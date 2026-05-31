# Design Doc: Official Query Detector Injection CLI

Date: 2026-05-30
Owner: Codex
Status: Implemented and verified locally/Linux

## Goal

Make official ObjectNav query smokes with current-view detectors reproducible
from the existing command-line evaluator, so YOLO/Grounding-DINO query runs
cannot accidentally omit `target_detector_adapter`.

## Non-Goals

- Do not change official Habitat metrics or policy behavior.
- Do not make detector-backed runs benchmark claims.
- Do not load detector dependencies for default no-detector or preflight-only
  commands.
- Do not add a new policy.

## System Boundary

Modify:

- `objectnav_core.cli.run_habitat_official_objectnav_eval`
- focused CLI tests
- packaging/docs trail if needed

The evaluator core already accepts `target_detector_adapter` and
`target_detector_min_confidence`; this slice exposes those hooks in the CLI.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | `--detector` | enum | `none`, `yolo_world`, or `grounding_dino`. Defaults to `none`. |
| Input | `--detector-weights` | string | YOLO weights or Grounding-DINO model id. |
| Input | `--detector-conf` | float | Detector backend confidence threshold. |
| Input | `--target-detector-min-confidence` | float | Query target-match gate passed to the evaluator. |
| Input | `--categories` | CSV | Detector prompt labels. Defaults to ObjectNav categories. |
| Input | Grounding-DINO options | floats/ints | Text threshold and max image side. |
| Output | Existing summary artifacts | JSON/CSV | Detector trace appears only when a detector is injected. |

## Data Flow

1. Parse the existing official eval arguments.
2. If `--preflight-only` or `--detector none`, do not build a detector.
3. Otherwise parse categories and build the requested detector adapter.
4. Pass the adapter and target confidence gate into
   `run_habitat_official_objectnav_eval`.
5. Preserve all existing CLI defaults and preflight behavior.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Empty category list | parser error | Require at least one category. |
| Detector dependency missing | detector constructor raises | User can run preflight or choose `--detector none`. |
| Detector accidentally omitted | output lacks detector trace | CLI now has explicit detector args and tests. |
| Preflight loads heavy detector | unit test/default behavior | Skip detector construction for `--preflight-only`. |

## Verification Plan

1. RED CLI test proving detector args are parsed and passed to the runner via a
   fake detector factory.
2. GREEN implementation with default no-detector behavior preserved.
3. Focused CLI tests.
4. Focused official gate, compileall, and `git diff --check` locally and on
   Linux after sync.

## Implementation Notes

- Added `--detector {none,yolo_world,grounding_dino}`, detector backend
  options, prompt categories, and `--target-detector-min-confidence` to
  `run_habitat_official_objectnav_eval.py`.
- The default remains `--detector none`; preflight-only runs do not construct a
  detector.
- Added a `detector_factory` and `runner` test seam in `main` so unit tests can
  prove injection without importing Habitat or detector weights.
- Local verification on 2026-05-30 passed:
  CLI tests (`8 passed`), focused official gate (`90 passed`), compileall, and
  `git diff --check`.
- Linux verification on 2026-05-30 passed:
  focused official gate (`90 passed`), CLI help showed detector flags,
  compileall, and `git diff --check`.

## Research Relevance

The temporal learned-local smoke produced one invalid no-detector artifact
because the console CLI could not inject the YOLO adapter. Reproducible
detector-backed query commands are required before any future official-smoke
comparison can support a paper-quality engineering claim.
