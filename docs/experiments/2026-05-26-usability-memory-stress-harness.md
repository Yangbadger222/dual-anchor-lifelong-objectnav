# Experiment Report: Usability Memory Stress Harness

Date: 2026-05-26  
Owner: Codex  
Status: Completed

## Question

Can the first ROS-free usability-memory model be stress-tested before RTK, RGB-D, detector, or real-robot integration is ready?

## Hypothesis

A minimal `P_existence`, `P_location_valid`, and `P_usable` model should separate three failure modes that were discussed as central risks:

- ghost memories should retire from default navigation decisions without claiming the object no longer exists
- occluded/unknown observations should avoid false deletion and remain recoverable by later positive evidence
- quarantined negative evidence from suspected OOD sensor failure should not clear memory

The bounded trust/verify/search/retire policy should also exercise all decision branches under a fixed random sweep.

## Environment

| Item | Value |
|---|---|
| Branch / commit | `main`, base commit `e828e1f`, with uncommitted implementation changes |
| Machine | macOS Darwin 25.4.0 arm64 |
| Dataset / bag / map | Synthetic deterministic scenarios and seeded Monte Carlo sweep |
| Simulator / robot | None |
| Key parameters | seed `13`, Monte Carlo runs `200`, default retire threshold `0.2` |
| Python | `Python 3.13.12` |

## Command

```bash
PYTHONPATH=src/objectnav_core python3 -m objectnav_core.cli.run_usability_stress --output runs/usability_stress/latest --seed 13 --monte-carlo-runs 200
```

## Metrics

| Metric | Value | Notes |
|---|---:|---|
| Monte Carlo rows | 200 | Written to `runs/usability_stress/latest/decision_boundary.csv` |
| Trust decisions | 6 | Fixed seed sweep after removing per-branch budget clipping |
| Verify decisions | 19 | Fixed seed sweep after removing per-branch budget clipping |
| Search decisions | 136 | Fixed seed sweep after removing per-branch budget clipping |
| Retire decisions | 39 | Fixed seed sweep after removing per-branch budget clipping |
| Ghost retirement | true | Final `p_usable=0.1102`, while `p_existence=0.95` |
| False deletion guard retired | false | Final `p_existence=0.9450`, `p_usable=0.7745` after positive recovery |
| OOD quarantine retired | false | Final belief unchanged at `0.9/0.9/0.9` |

## Observations

- Repeated non-confirmation plus access-blocked evidence retired the ghost memory from default navigation while preserving high existence probability.
- Occluded and unknown observations alone did not erase the memory; later positive evidence restored high usability.
- Quarantined FREE evidence was ignored, matching the intended fail-closed behavior for suspected bad depth batches.
- The random sweep covered every decision branch, which is useful for regression testing but is not yet a benchmark result.
- A low-validity sample with `P_v=0.0324`, `D_verify=2.3922`, and `C_search=57.5906` exposed a budget-clipping pathology. Removing per-branch `min(B_remaining, ...)` raised `C_trust` from `46.15` to `76.22`, making trust no longer competitive.

## Result

The first algorithm slice is executable as a pure Python stress harness. It is suitable for testing lifecycle semantics before sensor integration. The budget-clipping correction prevents low remaining budget from making failure look artificially cheap, but the result does not yet validate the model on real RGB-D logs, SLAM drift, cluttered scenes, or Nav2 path costs.

## Follow-up

- Add adversarial sweeps for nearby same-class objects, wrong data association, and stale path-cost estimates.
- Add trace replay once RGB-D/depth/detector observations are recorded from the XJTLU vehicle stack.
- Treat these synthetic results as regression checks, not paper evidence, until real trace replay is available.
