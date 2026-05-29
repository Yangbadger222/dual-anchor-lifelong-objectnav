# Experiment Report: Dual-Anchor Pressure Smoke

Date: 2026-05-29  
Owner: Codex  
Status: Running

## Question

Can the dual-anchor Mahalanobis matching layer expose the three regimes needed
for the paper claim: accepted match, ambiguous same-class match, and outside-gate
rejection?

## Hypothesis

With deterministic 2D pose/covariance cases, the matcher should accept a clear
low-drift target, reject a high-drift target outside the chi-square gate, and
mark two nearby same-class candidates as ambiguous instead of over-trusting the
nearest one.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `codex/habitat-memory-lifecycle` / `62ff8cf` plus local pressure CLI changes |
| Machine | macOS local workstation |
| Dataset / bag / map | None; deterministic synthetic 2D pressure cases |
| Simulator / robot | None; Habitat-independent geometry layer |
| Key parameters | gate threshold `5.991`, ambiguity margin `0.5` |

## Command

```bash
PYTHONPATH=src/objectnav_core \
python -m objectnav_core.cli.run_dual_anchor_pressure \
  --output /tmp/dual_anchor_pressure_smoke
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Case count | 3 | clear match, ambiguous pair, outside gate |
| Accepted count | 1 | `clear_match_low_drift` |
| Ambiguous count | 1 | `ambiguous_same_class_instances` |
| Outside-gate count | 1 | `outside_gate_high_drift` |
| Failures | 0 | CLI exited `0` locally |

## Observations

- `clear_match_low_drift` selected `target` with best Mahalanobis-squared
  distance `0.1`; the distractor was far away at `19.6`.
- `ambiguous_same_class_instances` rejected both candidates because the best and
  second-best distances were both `0.025`.
- `outside_gate_high_drift` rejected the only target with distance `125.0`.

## Result

The smoke validates the geometry/association failure modes, not ObjectNav
success. It is useful because it makes cross-anchor ambiguity visible before the
closed-loop Habitat implementation is ready.

## Follow-up

- Rerun the same CLI on Linux in the `conda habitat` environment after the code
  is pushed.
- Extend this from deterministic 2D cases into a dual-session Habitat scenario
  where the matching decision changes whether the agent goes to memory or
  explores a frontier.
