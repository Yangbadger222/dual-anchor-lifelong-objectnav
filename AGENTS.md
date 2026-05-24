# AGENTS.md

This repository is a research and engineering workspace for Dual-Anchor Lifelong Semantic ObjectNav. Agents and human contributors must treat it as a long-running, reproducible research project, not a scratchpad.

## Core Principle

No meaningful work should be invisible. Each task must leave a clear trail of:

1. what was planned
2. what changed
3. why it changed
4. how it was verified
5. what remains risky or unfinished

## Required Workflow

### 1. Start With Context

Before changing code, configs, experiments, or docs:

- read the relevant files first
- check `git status --short --branch`
- identify whether the task is exploratory, implementation, experiment, paper-writing, or integration
- look for existing notes in `docs/devlog/`, `docs/design/`, `docs/handoff/`, and `docs/experiments/`

Do not write from memory when local files can answer the question.

### 2. Classify the Task

Use this rule:

| Task type | Documentation requirement |
|---|---|
| Small typo or formatting fix | short note in final response is enough |
| Small experiment or prototype | devlog entry required |
| New module, algorithm, workflow, interface, dataset, or experiment protocol | design doc + devlog required |
| Work that another person/agent must continue | handoff doc required |
| Result that may support a paper claim | experiment report required |
| Integration with robot, ROS 2, Nav2, sensors, maps, or runtime logs | design doc + verification record + handoff required |

When uncertain, choose the stricter row.

### 3. Design Before Implementation

For non-trivial work, create or update a design document in `docs/design/` before implementation.

Use [docs/templates/design_doc.md](docs/templates/design_doc.md).

The design must include:

- goal
- non-goals
- system boundary
- inputs and outputs
- interfaces
- data flow
- failure modes
- verification plan
- paper/research relevance, if applicable

### 4. Keep a Devlog

Each meaningful task must add a dated devlog entry in `docs/devlog/YYYY-MM.md`.

Use [docs/templates/devlog_entry.md](docs/templates/devlog_entry.md).

Each entry must include:

- files changed
- change summary
- reason
- verification
- effect on future work

### 5. Maintain Handoff Notes

If work is incomplete, risky, blocked, or likely to be resumed later, create or update a handoff file in `docs/handoff/`.

Use [docs/templates/handoff.md](docs/templates/handoff.md).

The handoff must tell the next contributor:

- current state
- exact commands already run
- what passed
- what failed
- next recommended action
- risks and assumptions

### 6. Verify Before Claiming Success

Do not say a task is complete unless verification was actually run.

Acceptable verification depends on the task:

- docs-only: inspect rendered/linked Markdown and check file paths
- Python module: run relevant unit tests or at least import/syntax checks
- ROS 2 package: build the selected package and source the workspace afterward
- algorithm change: run deterministic sample input or replay
- experiment claim: attach an experiment report with logs, metrics, and conditions

If verification cannot be run, say so explicitly and explain why.

### 7. Keep Interfaces Hardware-Independent

The research system should develop independently from a specific vehicle when possible.

Prefer boundaries based on:

- ROS 2 messages, topics, services, and actions
- recorded bags
- simulation inputs
- mock detectors
- stable JSON/YAML/SQLite formats

Avoid hard-coding a vehicle, device path, map, route, camera, model, or campus-specific assumption into core logic. Put deployment-specific values in configs.

### 8. Preserve Research Reproducibility

For experiments, record:

- date and environment
- code commit or branch
- dataset, map, bag, or scene
- command used
- parameters
- metrics
- failures
- qualitative observations

Use [docs/templates/experiment_report.md](docs/templates/experiment_report.md).

### 9. Use Explicit Git Hygiene

- Keep commits focused.
- Do not mix unrelated changes.
- Stage files explicitly.
- Commit messages must explain what changed and why.
- Do not commit large logs, datasets, model weights, generated bags, or private credentials.
- Never force-push shared branches unless the project owner explicitly asks.

### 10. Agent Final Response Requirements

When an agent finishes work, the final response must include:

- what changed
- where the main files are
- what verification was run
- what was not done
- next recommended step, if useful

Do not hide uncertainty. Good handoffs are more valuable than confident guesses.

