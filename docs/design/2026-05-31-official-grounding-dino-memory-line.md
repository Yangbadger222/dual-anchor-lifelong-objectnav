# Design Doc: Official Grounding-DINO Memory Line

Date: 2026-05-31
Owner: Codex
Status: Implemented; first remote smoke completed

## Goal

Move the official detector-backed memory-discovery line from YOLO-World to the
previously qualified Grounding-DINO adapter, while keeping YOLO available as an
explicit ablation backend.

## Non-Goals

- Do not remove YOLO-World support.
- Do not claim detector-backed official ObjectNav benchmark performance from a
  smoke run.
- Do not change Habitat official metrics, action semantics, or memory-anchor
  coordinate frames.
- Do not add language understanding in this slice.

## Background

Earlier Habitat lifecycle experiments found Grounding-DINO
`IDEA-Research/grounding-dino-tiny` more useful than YOLO-World for the selected
ObjectNav categories, especially `plant`, sparse `chair`, and `tv_monitor`
views. The official CLI already accepts `grounding_dino`, but several CLIs still
default `--detector-weights` to `yolov8s-worldv2.pt`. That makes DINO runs
brittle: an operator can select `--detector grounding_dino` and accidentally
try to load a YOLO checkpoint as a Hugging Face model id.

The vertical-aware oracle-memory diagnostic is still a ceiling tool rather than
a benchmark claim. The latest remote smoke exported `y_m` for all four oracle
anchors and produced `3/4` official success with the oracle backend; the chair
episode remains a diagnostic failure and should be carried as caveat, not hidden.

## System Boundary

This slice owns the official detector CLI defaults and the first DINO-backed
memory-discovery smoke. It depends on:

- `GroundingDinoDetector` and `YoloWorldDetector` adapter contracts;
- official memory-discovery and official ObjectNav eval CLIs;
- existing Habitat official run summaries and protocol manifests.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Detector backend | CLI enum | `grounding_dino` becomes the discovery default; YOLO remains explicit. |
| Input | Detector weights | string or omitted | Omitted weights resolve per backend. |
| Input | Grounding-DINO thresholds | CLI floats/ints | Use `conf=0.25`, `text_threshold=0.25`, `max_image_side=384` for remote smoke. |
| Output | Memory prior | JSON | Detector-backed, not benchmark-validated. |
| Output | Detections trace | CSV | Used to audit DINO evidence and category failures. |
| Output | Experiment report | Markdown | Records commands, artifacts, and caveats. |

## Interfaces

Discovery default:

```bash
python -m objectnav_core.cli.run_habitat_official_memory_discovery \
  --output runs/habitat_official_objectnav/dino_discovery_smoke \
  --grounding-dino-max-image-side 384 \
  --max-episodes 4 \
  --max-steps 100
```

Explicit YOLO ablation remains possible:

```bash
python -m objectnav_core.cli.run_habitat_official_memory_discovery \
  --output runs/habitat_official_objectnav/yolo_discovery_ablation \
  --detector yolo_world \
  --detector-weights yolov8s-worldv2.pt
```

Query/eval CLIs keep `--detector none` as the default. When an operator passes
`--detector grounding_dino` without `--detector-weights`, the CLI should resolve
to `IDEA-Research/grounding-dino-tiny`.

## Data Flow

1. Parse detector backend and optional detector weights.
2. Resolve detector weights from the selected backend when weights are omitted.
3. Construct the requested detector adapter with backend-specific keyword args.
4. Run official discovery to export memory anchors and detection evidence.
5. Feed the discovered prior into the existing official memory comparison path
   after the oracle ceiling caveat is documented.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| DINO run accidentally uses YOLO weights | CLI unit test on omitted weights | Resolve default weights per backend. |
| ObjectNav category uses machine label syntax | Adapter alias test and trace evidence | Prompt with human-readable aliases and map back to canonical category. |
| Discovery smoke OOMs on remote GPU | Remote command fails or logs CUDA OOM | Keep `--grounding-dino-max-image-side 384`. |
| Detector-backed anchors are treated as benchmark claims | Manifest/report caveats | Keep `source_validity=not_benchmark_validated`. |
| DINO misses sparse categories | Detections CSV and summary counts | Report category-specific failures; do not overclaim. |
| Oracle ceiling remains imperfect | Experiment report caveat | Keep oracle backend diagnostic-only and investigate separately. |

## Verification Plan

1. Add RED tests showing DINO discovery defaults are selected and omitted DINO
   weights resolve to `IDEA-Research/grounding-dino-tiny`.
2. Add RED tests for official query/comparison/candidate-label CLIs proving
   explicit `--detector grounding_dino` without weights uses the DINO model id.
3. Implement minimal detector-weight resolution in CLI code.
4. Run focused CLI tests, Grounding-DINO adapter tests, compile checks, and
   `git diff --check`.
5. Sync to the Linux Habitat host.
6. Run focused remote tests in conda env `habitat`.
7. Run a small DINO official discovery smoke and record artifacts.

## Research Relevance

This makes the detector-backed memory line more credible for a paper-quality
ObjectNav story. The aim is not a small hand-tuned gain over YOLO; the aim is to
separate memory quality from detector fragility and to compare discovered memory
against the oracle-memory diagnostic ceiling without relying on a detector that
was already known to be a weak link.

## Open Questions

- The vertical-aware oracle ceiling still has a chair failure; this should be
  debugged before using it as a full upper bound.
- The first official DINO smoke revealed a memory-anchor quality bottleneck:
  the only exported DINO chair anchor was about `5.65 m` away in x/z from the
  oracle chair anchor and produced `0/4` SR even with the oracle backend.
- A follow-up trace found `tv_monitor` was also hurt by prompt syntax:
  prompting `tv_monitor` with an underscore suppressed the target label. The
  adapter now prompts `tv_monitor` as `tv monitor. television. tv.` and maps
  those aliases back to the canonical ObjectNav category.
