# Decision Record: Publication Target — Robotics Systems Venues, No ObjectNav Benchmark Grinding

Date: 2026-05-27
Status: Accepted

## Decision

This project targets **robotics systems venues** (ICRA / IROS / RA-L / CoRL)
for publication. It will **not** spend effort pushing for competitive
success/SPL on the HM3D ObjectNav leaderboard.

The validation strategy follows the existing design doc
[docs/design/2026-05-27-rgb-noise-sim-to-real-objectnav-memory-validation.md](../design/2026-05-27-rgb-noise-sim-to-real-objectnav-memory-validation.md):
RGB noise injection + real off-the-shelf detector + revisit controller +
lifelong memory harness + memory on/off ablation, followed by real-robot
deployment.

## Context

The user asked whether benchmark numbers (HM3D ObjectNav success / SPL) are
needed for publication. The central contribution of this work is a
**dual-anchor lifelong semantic memory** for ObjectNav, whose value lies in
cross-episode reuse, revisit efficiency, and sim-to-real robustness under
realistic perception noise. The standard HM3D ObjectNav benchmark is
single-episode and does not measure cross-episode memory reuse.

The user's stated workflow is "validate in simulation, then deploy on the
real robot", which matches the robotics-systems publication pattern, not
the vision/AI benchmark-leaderboard pattern.

## Options Considered

| Option | Pros | Cons |
|---|---|---|
| A. Robotics systems venues (ICRA / IROS / RA-L / CoRL), no benchmark grinding (**chosen**) | Matches user's sim-to-real workflow. Lets us define cross-episode metrics that actually showcase the memory contribution. Real-robot demo is the headline. Aligns with existing design doc and existing usability/memory code. | Cannot claim SOTA on HM3D leaderboard. Reviewers may still ask for at least one comparison number — must be addressed in writing, not by competing. |
| B. Vision / AI venues (CVPR / NeurIPS / ICCV), plug memory module into existing nav backbones (SemExp / PIRLNav) and report HM3D SPL gains | Strong if the relative SPL gain is large. Reaches a wider audience. | Requires integrating and re-running 1–2 navigation backbones on full HM3D val (~2000 episodes), multi-GPU compute, and reimplementing baselines fairly. Memory contribution is partially hidden by single-episode SPL. Roughly 2–3× the engineering work of option A. |
| C. Workshop submission first (CoRL/ICRA/NeurIPS lifelong/long-horizon workshops), conference later | Low bar, fast turnaround, validates the story before a main submission. | Limited prestige; cannot be the final destination. |

## Consequences

What becomes easier:

- No need to implement or wrap a learned navigation policy (DD-PPO, SemExp,
  PIRLNav) for the main result.
- `planning/` modules stay optional for v1; can be developed for real-robot
  use without blocking the paper.
- Experiment matrix shrinks to the 6-cell grid in the design doc instead of
  full HM3D val splits.
- Custom metrics (`time-to-trust`, `cross-episode recall`,
  `redundant verification cost`) are first-class instead of justification
  text.

What becomes harder / riskier:

- Reviewers may demand at least one comparison number; the paper must
  proactively explain why standard ObjectNav SPL is not the right
  measurement, in one explicit paragraph. The current design doc's
  "Research Relevance" section is the seed of that paragraph.
- Real-robot deployment becomes load-bearing for acceptance. If the real
  robot is not ready in time, the strongest claim collapses; a backup
  workshop submission must be considered.
- Less directly comparable to other ObjectNav papers, so framing must lean
  on the **lifelong / sim-to-real** axis, not the **ObjectNav** axis.

## Review Trigger

Revisit this decision if any of:

- The real-robot platform is delayed past the planned ICRA/IROS submission
  window.
- Reviewer feedback (workshop or arXiv preprint) explicitly asks for HM3D
  leaderboard numbers as a precondition.
- A collaborator joins who can take ownership of the navigation-policy
  integration, lowering the cost of option B.
- A new HM3D ObjectNav protocol emerges that natively measures
  cross-episode reuse, making leaderboard participation aligned with the
  memory contribution.
