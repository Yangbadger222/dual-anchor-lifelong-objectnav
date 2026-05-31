# Design Doc: Official Memory Anchor Quality Diagnostic

Date: 2026-05-31
Owner: Codex
Status: Implemented

## Goal

Add an offline diagnostic that compares a discovered official memory prior
against a reference prior and reports whether failures are caused by bad anchor
localization, bad confidence ranking, or missing anchors.

## Non-Goals

- Do not claim benchmark ObjectNav performance from this report.
- Do not use Habitat privileged metadata except through explicitly supplied
  reference priors.
- Do not replace navigation evaluation or official Habitat metrics.
- Do not decide navigability or line-of-sight yet; this first slice is
  prior-only.

## Background

The detector-positive viewpoint diagnostic now reaches `4/4` with corrected
Grounding-DINO category aliases and an oracle TargetNav backend. The
non-privileged opportunistic projected-anchor prior improved to `17` anchors
after aliasing but still reaches `0/4` with the same oracle backend. We need a
direct anchor-quality report that explains whether the projected prior has no
good anchor candidates, or whether a usable candidate is present but hidden by
confidence ranking.

## System Boundary

Create a report module and CLI:

- `objectnav_core.evaluation.habitat_official_memory_anchor_quality`
- `objectnav_core.cli.report_habitat_official_memory_anchor_quality`

The diagnostic owns loading two memory-prior JSON files, matching anchors with
the same category, compatible scene, and the same episode-selection semantics
used by the evaluator, comparing selected and nearest discovered anchors to a
reference anchor, and writing reproducible artifacts.

It depends on the existing official memory-prior schema and
`load_official_memory_prior`.

## Inputs and Outputs

| Direction | Name | Type / Format | Notes |
|---|---|---|---|
| Input | Candidate prior | `memory_prior.json` | Discovered or method prior under test. |
| Input | Reference prior | `memory_prior.json` | Oracle or detector-positive viewpoint diagnostic prior. |
| Input | Max good error | float meters | Threshold for report counts only. |
| Output | Report JSON | `anchor_quality.json` | Per-episode rows and aggregate metrics. |
| Output | Report CSV | `anchor_quality.csv` | Spreadsheet-friendly rows. |
| Output | Markdown | `anchor_quality.md` | Human-readable summary. |

## Interfaces

```bash
python -m objectnav_core.cli.report_habitat_official_memory_anchor_quality \
  --candidate-prior runs/.../grounding_dino_discovery_prior_alias_4ep_100steps_20260531_v1/memory_prior.json \
  --reference-prior runs/.../oracle_memory_prior_valmini_4ep_20260531_v1/memory_prior.json \
  --output-dir runs/.../grounding_dino_discovery_anchor_quality_20260531_v1
```

## Data Flow

1. Load candidate and reference anchors through the official prior loader.
2. Group reference anchors by `(episode_id, object_category)`.
3. For each reference row, collect candidate anchors with matching category,
   compatible scene id, and either exact episode id or wildcard/missing
   episode id.
4. Pick the policy-selected candidate by exact-episode priority and confidence,
   matching existing `select_official_memory_anchor` behavior.
5. Compute x/z Euclidean error for the selected anchor and the nearest anchor.
6. Record the nearest anchor rank under confidence sorting.
7. Aggregate coverage, selected-anchor quality, nearest-anchor quality, and
   ranking gap metrics.
8. Write JSON, CSV, and Markdown artifacts.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Missing/invalid prior | loader exception | fail fast with the path in the message. |
| Reference has duplicate keys | grouped rows include multiple references | compare candidates to the first reference and report duplicate count. |
| Candidate lacks episode ids | wildcard candidate counts | report separately from exact episode matches. |
| Candidate has good nearest anchor but bad selected anchor | selected vs nearest error gap | report nearest rank and rank gap explicitly. |
| y/floor unavailable | `y_error_m=null` | keep x/z report valid and mark vertical comparison unavailable. |

## Verification Plan

1. RED/GREEN unit test for selected-vs-nearest ranking behavior.
2. RED/GREEN unit test for missing candidates and JSON/CSV/Markdown outputs.
3. CLI argument forwarding test.
4. Run focused tests, compileall, and `git diff --check` locally.
5. Sync to Linux and run the report on the alias opportunistic prior versus a
   reference prior.

## Implementation Notes

Implemented:

- `src/objectnav_core/objectnav_core/evaluation/habitat_official_memory_anchor_quality.py`
- `src/objectnav_core/objectnav_core/cli/report_habitat_official_memory_anchor_quality.py`
- `src/objectnav_core/tests/test_habitat_official_memory_anchor_quality.py`
- setup entry point `objectnav_habitat_official_memory_anchor_quality`

The first report exposed that the legacy opportunistic prior omitted structured
`episode_id` fields even though the source string contained episode ids. The
official selector treats missing episode ids as wildcard anchors, so the report
now separates exact and wildcard matches. Discovery export now writes
structured `episode_id` fields for new priors.

## Research Relevance

This turns the current `4/4` privileged viewpoint versus `0/4` opportunistic
split into measurable anchor-quality evidence. It can show whether the next
method should focus on multi-view localization, candidate ranking, or
exploration coverage before spending more time on navigation backends.

## Open Questions

- Should the reference be the object-center oracle, detector-positive viewpoint
  prior, or both? The CLI supports either.
- Should a later Habitat-backed extension add navigability, floor, and
  visibility checks from simulator state?
