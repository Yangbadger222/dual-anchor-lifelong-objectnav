# Design Doc: Agent Workflow and Documentation System

Date: 2026-05-24  
Owner: Codex  
Status: Implemented

## Goal

Define a strong but usable working standard for human contributors and AI agents in this repository.

The system must ensure that future work on Dual-Anchor Lifelong ObjectNav remains reproducible, reviewable, and easy to continue across sessions.

## Non-Goals

- This document does not define the ObjectNav algorithm itself.
- This document does not scaffold runtime code.
- This document does not choose a ROS 2 package layout.
- This document does not replace future architecture design docs.

## Background

This repository starts as a hardware-independent research workspace. The intended project will likely include:

- offline algorithm development
- simulation or rosbag replay
- semantic memory design
- later ROS 2 / Nav2 integration
- experiments that may support a paper

That makes continuity more important than speed alone. A future contributor must be able to understand the reason behind each major change, not just see the final files.

## Approaches Considered

| Approach | Pros | Cons |
|---|---|---|
| Strict research workflow for every change | Maximum traceability and paper readiness | Too heavy for small prototypes and early exploration |
| Lightweight engineering workflow | Faster iteration | Easy to lose decisions, failures, and experiment context |
| Mixed workflow with strict rules for core work | Good balance between research rigor and practical speed | Requires contributors to classify tasks honestly |

## Decision

Use a mixed workflow:

- Core modules, algorithms, interfaces, experiments, and robot integration require design docs, devlogs, verification records, and handoff notes when needed.
- Small typos or formatting fixes can be documented only in the final response.
- Small prototypes require at least a devlog entry.
- Paper-relevant experiments require experiment reports.

When uncertain, contributors must choose the stricter documentation level.

## System Boundary

This workflow governs:

- AI agent behavior
- human contributor behavior
- documentation structure
- verification expectations
- handoff expectations
- git hygiene expectations

It does not enforce behavior automatically through CI yet. Enforcement is currently social and procedural through `AGENTS.md`.

## Required Artifacts

| Artifact | Path | Required For |
|---|---|---|
| Agent rules | `AGENTS.md` | All contributors |
| Design docs | `docs/design/` | Non-trivial architecture, module, interface, algorithm, or integration work |
| Devlogs | `docs/devlog/YYYY-MM.md` | Meaningful changes |
| Handoffs | `docs/handoff/` | Paused, blocked, risky, or continued work |
| Experiment reports | `docs/experiments/` | Results that may guide research or paper claims |
| Decision records | `docs/decisions/` | Important choices that may be revisited |
| Templates | `docs/templates/` | Repeatable documentation format |

## Data Flow

For non-trivial tasks:

1. Read repository context.
2. Create or update a design doc.
3. Implement the change.
4. Verify the change.
5. Record the result in the monthly devlog.
6. Create a handoff if work is incomplete, risky, or likely to continue.
7. Summarize changed files and verification in the final response.

For experiments:

1. Define the question and hypothesis.
2. Record environment and command.
3. Run the experiment.
4. Save metrics and observations.
5. State whether the result supports, weakens, or invalidates the hypothesis.

## Failure Modes

| Failure | Detection | Recovery / Mitigation |
|---|---|---|
| Contributors skip docs | Missing devlog/design/handoff for meaningful changes | Add the missing documentation before merging or continuing |
| Docs become too heavy | Small tasks take longer than the actual work | Use devlog-only mode for small prototypes |
| Handoffs lack useful context | Next contributor cannot resume safely | Require commands run, verification, risks, and next step |
| Paper claims become unsupported | No experiment report or reproducible setup | Do not use the claim until experiment documentation exists |
| Hardware assumptions leak into core logic | Vehicle-specific paths or sensor assumptions appear in core modules | Move deployment details into configs and document interface boundaries |

## Verification Plan

Initial verification:

- create the required directory structure
- create required templates
- create root `AGENTS.md`
- create initial devlog and handoff notes
- inspect Git status and unresolved placeholders

Future verification:

- check that each substantial PR or task has matching documentation
- optionally add CI or scripts to validate required docs once the project structure stabilizes

## Research Relevance

This workflow supports paper-quality development by preserving:

- design rationale
- experiment conditions
- negative results
- verification evidence
- integration boundaries

That is especially important for a system paper where reproducibility and real-world failure analysis are part of the contribution.

## Open Questions

- Should documentation be bilingual later, or should this research repository stay English-first?
- Should CI enforce Markdown link checks and required file patterns?
- Should experiment reports eventually include machine-readable metrics files?

